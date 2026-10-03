"""理想汽车时间设置实体（time 平台）.

★ 2026-09-24 新增（用户反馈"开始充电时间应该是时间设置"）：

  原先预约时间只有只读 sensor，无法设置。
  实际 App 里它们是【可设置的时间】：

    ReserveStartTime       → 充电开始时间（"23:00"）
    NewReserveFinishTime   → 充电结束时间（"08:00"）

★ 命令（App index.vehicle.js 实证）：
    cmdKey: remote_charge_control
    cmdData: {
      statusControlRequest: 255,
      controlType: '3',
      OrderChargingSwitch: "1"/"0",
      OrderChargingMode: `${mode}`,        ← 0=按时开始 1=按时结束 2=低价充电
      reserveStartTime: "HH:mm",
      NewReserveFinishTime: "HH:mm",
      isContinue: "0"/"1"
    }

★ App 的三种模式（从文案还原）：
    0 = 按时开始："{开始时间}开始充电，充到充电上限结束"
    1 = 按时结束："预估所需时长，在{结束时间}前完成充电"
    2 = 低价充电："{开始时间}开始充电，{结束时间}前结束"

  时间字段是【三个模式共用】的一组区间设置。
"""

from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin
from .gate import require_control
from .device import build_device_info
from .li_api import job_channel_readonly_attrs

_LOGGER = logging.getLogger(LOGGER_NAME)

CMD_CHARGE = "remote_charge_control"

# 乐观更新有效期（秒）—— 与其他平台一致
OPTIMISTIC_TTL = 150.0

# (后缀, 名称, 图标, 状态信号 key, 命令字段名, 默认值)
TIME_ENTITIES = (
    ("charge_start_time", "充电开始时间", "mdi:clock-start",
     "scheduled_charge_start", "reserveStartTime", "23:00"),
    ("charge_end_time", "充电结束时间", "mdi:clock-end",
     "scheduled_charge_end", "NewReserveFinishTime", "08:00"),
)


def _parse_hhmm(raw) -> dt_time | None:
    """把 "23:00" / "23:00:00" 解析成 dt_time；失败返回 None."""
    if raw is None:
        return None
    s = str(raw).strip().strip('"')
    if not s:
        return None
    parts = s.split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return dt_time(hour=hh, minute=mm)


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
        _LOGGER.warning("无密码登录凭据，跳过 time 实体")
        return

    async_add_entities([
        LiCarTime(coordinator, li_api, device_info, vin, *spec)
        for spec in TIME_ENTITIES
    ])


class LiCarTime(CoordinatorEntity, TimeEntity):
    """充电时间设置（开始 / 结束）."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, li_api, device_info, vin: str,
                 suffix: str, name: str, icon: str,
                 state_key: str, cmd_field: str, default: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._state_key = state_key
        self._cmd_field = cmd_field
        self._default = default
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_time_{suffix}"
        self._attr_device_info = device_info
        self._optimistic: dt_time | None = None
        self._optimistic_until: float = 0.0
        self._last_result: dict | None = None

    # ---------- 状态读取 ----------

    def _vss_raw(self, key: str) -> str | None:
        sig = (self.coordinator.data or {}).get("vss", {}).get(key) or {}
        v = sig.get("value")
        return str(v) if v is not None else None

    @property
    def native_value(self) -> dt_time | None:
        """当前时间值（乐观更新带 TTL）."""
        import time as _t

        vss_time = _parse_hhmm(self._vss_raw(self._state_key))

        if self._optimistic is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_time is None or vss_time != self._optimistic:
                    return self._optimistic
            self._optimistic = None
            self._optimistic_until = 0.0

        return vss_time if vss_time is not None else _parse_hhmm(self._default)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "cmd_key": CMD_CHARGE,
            "control_type": "3",
            "signal": self._state_key,
            "command_field": self._cmd_field,
            "note": "三个充电模式（按时开始/按时结束/低价充电）共用此时间区间",
        }
        # ★ 2026-09-28：走 JOB 通道 → 标注只读原因
        attrs.update(job_channel_readonly_attrs(CMD_CHARGE))
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    # ---------- 设置 ----------

    @require_control
    async def async_set_value(self, value: dt_time) -> None:
        """设置时间（连同当前模式一起下发，因为 App 是把它们打包发的）."""
        hhmm = f"{value.hour:02d}:{value.minute:02d}"

        # 读当前：开始时间、结束时间、模式
        start = self._vss_raw("scheduled_charge_start") or "23:00"
        end = self._vss_raw("scheduled_charge_end") or "08:00"
        mode = self._vss_raw("charge_order_mode") or "2"
        switch = self._vss_raw("scheduled_charge_switch") or "1"

        # 用用户设置的值覆盖对应字段
        if self._cmd_field == "reserveStartTime":
            start = hhmm
        else:
            end = hhmm

        cmd_data = {
            "statusControlRequest": 255,
            "controlType": "3",
            "OrderChargingSwitch": "1" if str(switch) in ("1", "True", "true") else "0",
            "OrderChargingMode": str(mode),
            "reserveStartTime": str(start).strip('"'),
            "NewReserveFinishTime": str(end).strip('"'),
            "isContinue": "0",
        }

        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_CHARGE, cmd_data)
            self._last_result = res
            import time as _t
            self._optimistic = value
            self._optimistic_until = _t.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("充电时间设置 %s=%s（完整报文 %s）",
                         self._cmd_field, hhmm, cmd_data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("充电时间设置失败: %s", err)
            raise

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
