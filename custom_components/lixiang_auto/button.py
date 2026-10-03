"""理想汽车按钮实体（button 平台）— 一次性车控命令（已实测打通）.

功能（2026-09-22 实测 pushState=5 / resultCode=0）:
  - 寻车:     remoteVehSearch      {"searchType":"0"}                 ✅ 已实测成功
  - 开尾门:   remoteVehPlgControl  {"plgPosi":"100"}                  ✅ 格式已实测
  - 关尾门:   remoteVehPlgControl  {"plgPosi":"0"}
  - 开窗:     remoteVehWdwControl  {"flWindPosi":"99",...}            ✅ 格式已实测
  - 关窗:     remoteVehWdwControl  {"flWindPosi":"0",...}             ✅ 已实测成功
  - 远程启动: remoteVehAuth        {}                                 ✅ 已实测成功

★ 旧的 remote_veh_search / remote_plg_open 等下划线命名是错的（APK 字符串枚举值，
  不是真实 cmdKey），已按实测结果修正为真实 cmdKey。

⚠️ 车控会真实作用于车辆。
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .gate import require_control
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

# 车窗四位置（前左/前右/后左/后右）



# (唯一后缀, 名称, 图标, cmdKey, cmdData, 是否等待结果)
# ★ 2026-09-24 精简（用户反馈"开窗关窗开两个实体好像是多余的"）：
#   删除了 4 个被 cover 替代的按钮：
#     plg_open / plg_close      → cover.wei_men（尾门）
#     window_open / window_close → cover.che_chuang（车窗）
#
#   HA 的 cover 域本身支持 open_cover / close_cover / stop_cover，
#   且带状态读回 → 比两个 button 更符合惯例。
BUTTONS = (
    ("veh_search", "寻车", "mdi:car-search",
     "remoteVehSearch", {"searchType": "0"}, False),
    # ★ 2026-09-24 改名（用户要求）：远程启动 → 远程授权 → 授权驾驶
    #   依据：App 的实现类是 XHttpRemoteStartControl，
    #        但 cmdKey 是 remoteVehAuth（Auth = 授权驾驶）
    ("engine_start", "授权驾驶", "mdi:key-chain",
     "remoteVehAuth", {}, True),
    # ★ 2026-09-24 补充：其余 App 支持的车控
    #   参数来源：MControlKeyConst + 车控命令全集报告
    #
    # 闪灯（searchType=1，Integer）
    ("flash_light", "闪灯", "mdi:car-light-high",
     "remoteVehSearch", {"searchType": 1}, False),
    # 鸣笛（searchType=2，Integer）
    ("whistle", "鸣笛", "mdi:bullhorn",
     "remoteVehSearch", {"searchType": 2}, False),
    # ★ 2026-09-24 移除哨兵开关按钮（用户建议）：
    #   改用 switch.sentry（有状态可读），见 switch.py
    #   （SettingsStatus.sentinelSwitch 能读到当前状态）
    # 远程拍照
    #   ⚠️ 同样用 "timestap"；vehImage 固定 "veh_svm_image"
    ("svm_photo", "远程拍照", "mdi:camera",
     "mobileVehSvm", {"vehImage": "veh_svm_image"}, True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator, li_api = data["coordinator"], data.get("li_api")
    vin = config_entry.data.get(CONF_VIN) or ""
    identifiers = {(DOMAIN, vin)} if vin else {(DOMAIN, config_entry.entry_id)}
    # ★ 名字全取自服务端（vehicleNickname / spu），不硬编码车型
    _d = hass.data[DOMAIN][config_entry.entry_id]
    device_info = build_device_info(
        _d.get("coordinator"), config_entry, _d.get("li_api"),
        ability=_d.get("ability"),
    )
    if li_api is None:
        _LOGGER.warning("无密码登录凭据，跳过 button 实体")
        return
    async_add_entities([
        LiCarButton(coordinator, li_api, device_info, vin, *spec) for spec in BUTTONS
    ])


class LiCarButton(CoordinatorEntity, ButtonEntity):
    """理想车控按钮."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, li_api, device_info, vin: str,
                 suffix: str, name: str, icon: str,
                 cmd_key: str, cmd_data: dict, wait_result: bool) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._cmd_key = cmd_key
        self._cmd_data = cmd_data
        self._wait_result = wait_result
        self._attr_name = name
        self._attr_icon = icon
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_btn_{suffix}"
        self._attr_device_info = device_info
        self._last_result: dict | None = None

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"cmd_key": self._cmd_key, "cmd_data": self._cmd_data}
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_press(self, **kwargs: Any) -> None:
        """下发命令.

        寻车/闪灯/鸣笛 (wait_result=False) 用 fire-and-forget:
        这类命令无明确终态，轮询只会白等到超时。

        ★ 2026-09-24：哨兵与 SVM 的 cmdData 需要 "timestap" 字段
          （App 的拼写就是少一个 m，必须照抄）——
          这里自动注入当前毫秒时间戳。
        """
        import time as _t

        cmd_data = dict(self._cmd_data)
        # 哨兵 / 拍照 需要时间戳（字段名 timestap，非 timestamp）
        if self._cmd_key in ("sentinelModeSetting", "mobileVehSvm"):
            cmd_data["timestap"] = int(_t.time() * 1000)

        try:
            if self._wait_result:
                res = await self.hass.async_add_executor_job(
                    self._api.send_command, self._cmd_key, cmd_data)
            else:
                res = await self.hass.async_add_executor_job(
                    self._api.send_command_fire_and_forget,
                    self._cmd_key, cmd_data)
            self._last_result = res
            _LOGGER.info("车控 %s %s 已执行: %s", self._cmd_key, self._cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", self._cmd_key, self._cmd_data, err)
            raise
        await self.coordinator.async_request_refresh()
