"""理想汽车模式选择实体（select 平台）.

提供空调控制模式选择（前排空调开关 vs 前排自动空调）—— 这两个 acCtrlType
均已实测可用（cmd_table_verified.json: acCtrlType=frtACSw / frtACAUTOSw 均可）。

★ 说明: 本项目【没有】把充电上限/能量回收做成 select，因为:
  - 充电上限的写入命令不在已实测命令表内（cmdKey/cmdData 均未确认）；
  - 能量回收等级同理。
  宁可少做，也不给出虚假的可控能力。这两项目前仅作 sensor 只读展示。

当前实体用途: 维护"下次开空调时使用的 acCtrlType"，持久化在实体属性里，
由 climate 实体读取（见 climate.AC_TYPE_*）。这是一个配置型 select，不发命令。

⚠️ 修改该 select 本身不下发车控命令。
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .gate import require_control
from .entity_helper import route_id_of_vin
from .device import build_device_info
from .li_api import job_channel_readonly_attrs

_LOGGER = logging.getLogger(LOGGER_NAME)

# 显示名 → acCtrlType（两者均已实测可用）
AC_TYPE_OPTIONS = {
    "前排空调": "frtACSw",
    "前排自动空调": "frtACAUTOSw",
}
_OPTION_TO_TYPE = AC_TYPE_OPTIONS
_TYPE_TO_OPTION = {v: k for k, v in AC_TYPE_OPTIONS.items()}

DEFAULT_OPTION = "前排空调"

# ★ 2026-09-24 新增：充电模式
#   枚举来源（App index.vehicle.js）：
#     w = { StartOnTime: 0, EndOnTime: 1, LowestPrice: 2 }
# ★ 名称按 App 文案（ChargeSetting.AppointmentTime）：
#   scheduledStart = "按时开始"
#   scheduledEnd   = "按时结束"
#   OffPeakCharging = "低价充电"
CHARGING_MODES = {
    "按时开始": 0,      # StartOnTime —— "{开始时间}开始充电，充到上限结束"
    "按时结束": 1,      # EndOnTime   —— "预估时长，在{结束时间}前充满"
    "低价充电": 2,      # LowestPrice —— "{开始时间}开始充电，{结束时间}前结束"
}
_MODE_TO_VALUE = CHARGING_MODES
_VALUE_TO_MODE = {v: k for k, v in CHARGING_MODES.items()}
DEFAULT_CHARGING_MODE = "低价充电"


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
        _LOGGER.warning("无密码登录凭据，跳过 select 实体")
        return
    async_add_entities([
        LiCarAcTypeSelect(coordinator, li_api, device_info, vin),
        # ★ 2026-09-24 新增：充电模式（预约/结束/低价充电）
        LiCarChargingModeSelect(coordinator, li_api, device_info, vin),
    ])


class LiCarAcTypeSelect(CoordinatorEntity, SelectEntity):
    """空调控制类型选择（配置型，仅维护 acCtrlType，不下发命令）."""

    _attr_has_entity_name = True
    _attr_name = "空调控制类型"
    _attr_icon = "mdi:air-conditioner"
    _attr_options = list(AC_TYPE_OPTIONS.keys())

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_sel_ac_ctrl_type"
        self._attr_device_info = device_info
        self._option = DEFAULT_OPTION

    @property
    def current_option(self) -> str:
        return self._option

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "ac_ctrl_type": _OPTION_TO_TYPE.get(self._option, ""),
            "role": "配置型（修改此项本身不下发车控命令）",
            "options_map": dict(AC_TYPE_OPTIONS),
        }

    @require_control
    async def async_select_option(self, option: str) -> None:
        if option not in AC_TYPE_OPTIONS:
            _LOGGER.warning("未知空调控制类型: %s", option)
            return
        self._option = option
        _LOGGER.info("空调控制类型设为 %s (%s)", option, _OPTION_TO_TYPE[option])
        self.async_write_ha_state()


class LiCarChargingModeSelect(CoordinatorEntity, SelectEntity):
    """充电模式选择（预约充电 / 结束充满 / 低价充电）.

    ★ 命令（App index.vehicle.js 实证）：
        cmdKey: remote_charge_control
        cmdData: {
          statusControlRequest: 255,
          controlType: '3',
          OrderChargingSwitch: "1"/"0",
          OrderChargingMode: `${mode}`,      ← 0/1/2
          reserveStartTime: "HH:mm",
          NewReserveFinishTime: "HH:mm",
          isContinue: "0"/"1"
        }

    ★ 枚举：
        0 = 开始时间充电（StartOnTime）
        1 = 结束时间充满（EndOnTime）
        2 = 低价充电（LowestPrice，谷电时段）

    ★ App 联动（源码发现）：
        切到「低价充电」时会自动关闭电池保温（BatteryInsulation='0'）
    """

    _attr_has_entity_name = True
    _attr_name = "充电模式"
    _attr_icon = "mdi:ev-station"
    _attr_options = list(CHARGING_MODES.keys())

    # 状态源（VSS 信号 key）
    _STATE_KEY = "charge_order_mode"
    _START_KEY = "scheduled_charge_start"
    _END_KEY = "scheduled_charge_end"

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_sel_charging_mode"
        self._attr_device_info = device_info
        self._optimistic: str | None = None
        self._optimistic_until: float = 0.0
        self._last_result: dict | None = None

    def _vss(self, key: str) -> str | None:
        sig = (self.coordinator.data or {}).get("vss", {}).get(key) or {}
        v = sig.get("value")
        return str(v) if v is not None else None

    @property
    def current_option(self) -> str | None:
        import time as _t

        raw = self._vss(self._STATE_KEY)
        vss_mode: str | None = None
        if raw is not None:
            try:
                vss_mode = _VALUE_TO_MODE.get(int(float(raw)))
            except (TypeError, ValueError):
                vss_mode = None

        # 乐观更新（同其他平台）
        if self._optimistic is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_mode is None or vss_mode != self._optimistic:
                    return self._optimistic
            self._optimistic = None
            self._optimistic_until = 0.0

        return vss_mode

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "cmd_key": "remote_charge_control",
            "control_type": "3",
            "modes": dict(CHARGING_MODES),
            "start_time": self._vss(self._START_KEY),
            "end_time": self._vss(self._END_KEY),
        }
        # ★ 2026-09-28：走 JOB 通道 → 标注只读原因
        attrs.update(job_channel_readonly_attrs("remote_charge_control"))
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_select_option(self, option: str) -> None:
        if option not in CHARGING_MODES:
            _LOGGER.warning("未知充电模式: %s", option)
            return
        mode = CHARGING_MODES[option]
        start = self._vss(self._START_KEY) or "23:00"
        end = self._vss(self._END_KEY) or "08:00"

        cmd_data = {
            "statusControlRequest": 255,
            "controlType": "3",
            "OrderChargingSwitch": "1",
            "OrderChargingMode": str(mode),
            "reserveStartTime": start,
            "NewReserveFinishTime": end,
            "isContinue": "0",
        }
        # ★ App 联动：低价充电时关闭电池保温
        if mode == CHARGING_MODES["低价充电"]:
            cmd_data["batteryInsulation"] = "0"

        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, "remote_charge_control", cmd_data)
            self._last_result = res
            import time as _t
            self._optimistic = option
            self._optimistic_until = _t.monotonic() + 150.0
            _LOGGER.info("充电模式设为 %s（%d）: %s", option, mode, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("充电模式设置失败: %s", err)
            raise
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


def option_to_type(option: str) -> str:
    """选项名 → acCtrlType（供 climate 复用）."""
    return _OPTION_TO_TYPE.get(option, AC_TYPE_OPTIONS[DEFAULT_OPTION])


def type_to_option(ac_type: str) -> str:
    """acCtrlType → 选项名."""
    return _TYPE_TO_OPTION.get(ac_type, DEFAULT_OPTION)
