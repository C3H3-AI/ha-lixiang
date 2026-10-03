"""理想汽车 · 服务器通知（notify 平台 + 事件）

背景（2026-09-23 逆向）
--------------------
App 的通知来自服务器的 MMS 服务（阿里云推送下发）：
    GET /mms-api/v1-0/message?appId=chj_app_m01&channelType=1&pageSize=20&pageNumber=1
返回每条通知:
    {
      requestId, messageId, title, summary,
      category,     # 'vehicle' = 车辆通知（充电完成/电量不足告警...）
                    # 'notice'  = 系统通知
      tag: [...],   # 'sys_app_push_notice' 等
      status,       # 0 = 未读
      sendOn,       # 服务器发送时间（ms）
      action,       # JSON: {"router": "...", "type": 5}
    }
实测总数 2165 条，其中 category='vehicle' 含:
    "充电完成" / "电量不足告警" 等 ★

本模块
------
1. 提供 notify 实体（`notify.li_auto_l6_*`）用于手动发测试通知
2. 周期性拉取服务器通知，把【新的车辆通知（预警）】以 HA 事件形式抛出:
       event_type = "lixiang_auto_notification"
       data = {title, summary, category, tag, sendOn, requestId}
   用户可据此写 automation。
3. 记录已见 requestId，避免重复触发。
4. ★ 默认只推 category='vehicle'（真正的车辆预警）,
      过滤掉 category='notice'（含大量广告/营销推送）。

   实测 category 分布（50 条样本）:
       vehicle: 25 条  → "充电完成" / "电量不足告警" 等 ✅ 预警
       notice:  25 条  → "新车上市" / "试驾邀请" / "代金券" 等 ⚠️ 多为广告
   其他字段（tag / action.messageType / action.type）无法区分广告。

用户自动化示例
--------------
    - alias: 理想车辆告警
      trigger:
        - platform: event
          event_type: lixiang_auto_notification
          event_data:
            category: vehicle
      action:
        - service: notify.mobile_app_xxx
          data:
            title: "{{ trigger.event.data.title }}"
            message: "{{ trigger.event.data.summary }}"
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

EVENT_NOTIFICATION = "lixiang_auto_notification"
POLL_INTERVAL = timedelta(seconds=60)     # 通知轮询间隔
MAX_SEEN = 500                            # 已见 requestId 上限

# ★ 默认只推送【车辆通知（预警）】—— category='vehicle'
#   实测 notice 类里混了大量广告（新车上市/试驾邀请/代金券等），
#   因此默认过滤掉，避免 HA 通知被广告淹没。
#   如需接收全部通知，把此值设为 None。
DEFAULT_CATEGORIES: set[str] | None = {"vehicle"}

# vehicle 类通知的关键词（用于进一步识别真正的"预警"，可选）
VEHICLE_ALERT_KEYWORDS = (
    "告警", "异常", "故障", "警告", "不足", "失败",
    "碰撞", "位移", "震动", "被撬", "胎压", "低电量",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.debug("notify.async_setup_entry")
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data.get("coordinator")
    li_api = data.get("li_api")
    vin = config_entry.data.get(CONF_VIN) or ""
    _LOGGER.debug("notify: li_api=%s vin=%s", bool(li_api), vin)
    identifiers = {(DOMAIN, vin)} if vin else {(DOMAIN, config_entry.entry_id)}
    # ★ 名字全取自服务端（vehicleNickname / spu），不硬编码车型
    device_info = build_device_info(
        coordinator, config_entry, li_api,
        ability=data.get("ability"),
    )
    if li_api is None:
        _LOGGER.warning("无密码登录凭据，跳过 notify 实体")
        return

    # ① 先启动通知轮询（不依赖实体创建）
    session = _NotifyPoller(hass, li_api, config_entry.entry_id)
    data["notify_poller"] = session
    session.start()
    _LOGGER.info("通知轮询已启动（间隔 %s）", POLL_INTERVAL)

    # ② 再创建实体
    entities = [LiCarNotifier(li_api, device_info, vin)]
    async_add_entities(entities)


class LiCarNotifier(NotifyEntity):
    """理想汽车通知实体（用于手动发通知 / 占位）。"""

    _attr_has_entity_name = True
    _attr_name = "通知"
    _attr_icon = "mdi:bell-ring"

    def __init__(self, li_api, device_info, vin: str) -> None:
        self._api = li_api
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_notify"
        self._attr_device_info = device_info

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """本地事件（理想服务器不支持发送，只用来产生事件）。"""
        self.hass.bus.async_fire(EVENT_NOTIFICATION, {
            "title": title or "理想汽车",
            "summary": message,
            "category": "local",
            "tag": [],
            "source": "manual",
        })
        _LOGGER.info("本地通知事件已发出: %s / %s", title, message)


class _NotifyPoller:
    """轮询服务器通知，抛 HA 事件。"""

    def __init__(self, hass: HomeAssistant, li_api, entry_id: str) -> None:
        self._hass = hass
        self._api = li_api
        self._entry_id = entry_id
        self._seen: set[str] = set()
        self._first_run = True
        self._unsub = None

    def start(self) -> None:
        self._unsub = async_track_time_interval(
            self._hass, self._async_poll, POLL_INTERVAL)
        # 立即拉一次（只记录，不触发事件，避免重启后刷屏）
        self._hass.async_create_task(self._async_poll(None))

    def stop(self) -> None:
        """★ 取消定时器（修复：之前从未调用，重载后 poller 叠加）。

        __init__.py 的 async_unload_entry 会调用此方法。
        不解绑会导致：重载集成后每 60 秒重复请求 MMS API（加倍风控风险），
        且同一通知被多次触发事件。
        """
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
            _LOGGER.debug("通知轮询已停止")

    async def _async_poll(self, _now) -> None:
        
        try:
            msgs = await self._hass.async_add_executor_job(
                self._api.get_notifications, 1, 20, 1)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("拉取服务器通知失败: %s", err)
            return

        _LOGGER.debug("拉到 %d 条通知", len(msgs))
        new_items = []
        for m in msgs:
            rid = m.get("requestId") or m.get("messageId")
            if not rid or rid in self._seen:
                continue
            self._seen.add(rid)
            new_items.append(m)

        # 裁剪 seen
        if len(self._seen) > MAX_SEEN:
            self._seen = set(list(self._seen)[-MAX_SEEN:])

        if self._first_run:
            self._first_run = False
            _LOGGER.info("通知轮询已启动，首轮记录 %d 条（不触发事件）", len(new_items))
            return

        for m in new_items:
            # ★ 默认只推车辆通知（预警），过滤广告
            if DEFAULT_CATEGORIES is not None and \
                    m.get("category") not in DEFAULT_CATEGORIES:
                continue
            payload = {
                "requestId": m.get("requestId"),
                "messageId": m.get("messageId"),
                "title": m.get("title"),
                "summary": m.get("summary"),
                "category": m.get("category"),
                "tag": m.get("tag") or [],
                "status": m.get("status"),
                "sendOn": m.get("sendOn"),
                "action": m.get("action"),
                "sendBy": m.get("sendBy"),
                "vin": m.get("businessInfo") or None,
            }
            self._hass.bus.async_fire(EVENT_NOTIFICATION, payload)
            _LOGGER.info(
                "★ 新通知事件 [%s] %s | %s",
                payload["category"], payload["title"], payload["summary"])
