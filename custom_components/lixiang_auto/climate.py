"""理想汽车空调实体（climate 平台）— 车控 cmd/send 实测打通.

命令（2026-09-22 实测 pushState=5 / resultCode=0）:
  开空调: remoteVehACSmartControl
    {"acCtrlValue":"ON","acCtrlType":"frtACSw",
     "acCountdownTimer":"15","acCtrlTemp":26}
  关空调: remoteVehACSmartControl
    {"acCtrlValue":"OFF","acCtrlType":"frtACSw","acCountdownTimer":"15"}

★★ 类型陷阱（实测踩过）:
  acCtrlTemp 必须是 **Number**（26 或 26.0），传字符串 "26" 会被服务端拒绝。
  而 acCtrlValue / acCtrlType / acCountdownTimer 必须是 **String**。
  acCtrlType: frtACSw（前排空调开关）/ frtACAUTOSw（自动）均可。

状态读取: VSS 实时信号（Vehicle.Cabin.AC.*）
  ac_on        ← Vehicle.Cabin.AC.ExSpeedStatus（风速非 0 判为开启）
  ac_set_temp  ← Vehicle.Cabin.AC.SetTemp
  inside_temp  ← Vehicle.Cabin.AC.FrtACIncarTemp
  ac_defrost   ← Vehicle.Cabin.AC.DefrostModeStatus

⚠️ 车控会真实作用于车辆。
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .gate import require_control
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

CMD_AC = "remoteVehACSmartControl"

MIN_TEMP = 16
MAX_TEMP = 30
DEFAULT_TEMP = 26

# ★ 2026-09-24 乐观更新有效期（秒）
#   依据：HA 轮询间隔 DEFAULT_SCAN_INTERVAL_SECONDS = 60 秒
#   取 2.5 倍轮询周期 = 150 秒 → 保证至少 2 次轮询机会让 VSS 追上
#   （过短：VSS 还没更新乐观值就失效 → 显示回退；
#     过长：服务端真实变化被掩盖过久）
OPTIMISTIC_TTL = 150.0
TARGET_STEP = 1.0
# 空调运行倒计时（分钟，字符串）
AC_COUNTDOWN = "15"

# 空调控制类型
AC_TYPE_FRONT = "frtACSw"          # 前排空调开关（实测可用）
AC_TYPE_AUTO = "frtACAUTOSw"       # 前排自动空调（实测亦可）

# 状态 VSS key
KEY_AC_ON = "ac_on"                # ★ 空调真实开关信号（Vehicle.Cabin.AC.FOffStatus）
KEY_FAN_SPEED = "ac_fan_speed"     # 语义实为"快冷快热"（getNeedRapidCoolheat）
KEY_SET_TEMP = "ac_set_temp"
KEY_INSIDE_TEMP = "inside_temp"
KEY_DEFROST = "ac_defrost"


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
        _LOGGER.warning("无密码登录凭据，跳过 climate 实体")
        return
    async_add_entities([LiCarClimate(coordinator, li_api, device_info, vin)])


class LiCarClimate(CoordinatorEntity, ClimateEntity):
    """理想汽车前排空调."""

    _attr_has_entity_name = True
    _attr_name = "空调"
    _attr_icon = "mdi:air-conditioner"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TARGET_STEP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_climate_front"
        self._attr_device_info = device_info
        # 本地乐观状态: 车控下发后 VSS 可能延迟数十秒才刷新
        self._optimistic_on: bool | None = None
        self._optimistic_mode: HVACMode | None = None
        self._optimistic_temp: float | None = None
        self._optimistic_until: float = 0.0
        self._last_result: dict | None = None

    # ---------- 状态读取 ----------

    def _sig(self, key: str) -> Any:
        sig = (self.coordinator.data or {}).get("vss", {}).get(key)
        return None if not sig else sig.get("value")

    def _ac_running(self) -> bool | None:
        """空调是否运行。

        ★ 2026-09-23 修复：改用 Vehicle.Cabin.AC.FOffStatus（App 官方信号）
          App 源码（LiMeshPathHelper）里 LXVehicleInfoKeyAC → FOffStatus，
          XAcDataHandle 逻辑：FOffStatus==1 → setACSwitch(true)。
          实测：开空调=1，关=0，且时间戳随操作实时更新。

        旧实现用 ExSpeedStatus（风速），但远程开空调时该信号不上报（恒为 0），
        导致"实际已开启但 HA 显示关闭"。
        """
        val = self._sig(KEY_AC_ON)
        if val is not None:
            try:
                return int(float(val)) == 1
            except (TypeError, ValueError):
                return str(val).strip().upper() not in ("0", "OFF", "FALSE")
        # 回退：用风速推断（旧逻辑）
        val = self._sig(KEY_FAN_SPEED)
        if val is None:
            return None
        try:
            return int(float(val)) > 0
        except (TypeError, ValueError):
            return str(val).strip().upper() not in ("0", "OFF", "FALSE", "CLOSED", "NONE")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """当前模式: 关闭 / 制冷 / 制热 / 自动.

        车辆未上报明确模式时: 若空调运行且车内温度高于设定温度 → 制冷, 否则制热。
        """
        if self._optimistic_on is False:
            return HVACMode.OFF
        running = self._ac_running()
        if running is None:
            return self._optimistic_mode or HVACMode.OFF
        if not running:
            return HVACMode.OFF
        # 运行中: 优先用上次下发的模式, 否则按温差推断
        if self._optimistic_mode and self._optimistic_mode != HVACMode.OFF:
            return self._optimistic_mode
        inside, target = self._sig(KEY_INSIDE_TEMP), self.target_temperature
        try:
            if inside is not None and target is not None:
                return (HVACMode.COOL if float(inside) > float(target)
                        else HVACMode.HEAT)
        except (TypeError, ValueError):
            pass
        return HVACMode.COOL

    @property
    def current_temperature(self) -> float | None:
        """车内温度."""
        val = self._sig(KEY_INSIDE_TEMP)
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """设定温度.

        ★ 2026-09-24 修复：乐观更新带 TTL
          （原先"VSS 优先"，设置后立刻被旧值覆盖）
        """
        import time as _t

        vss_t: float | None = None
        try:
            t = float(self._sig(KEY_SET_TEMP))
            if MIN_TEMP <= t <= MAX_TEMP:
                vss_t = t
        except (TypeError, ValueError):
            pass

        if self._optimistic_temp is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_t is None or abs(vss_t - self._optimistic_temp) > 0.1:
                    return self._optimistic_temp
            self._optimistic_temp = None

        return vss_t if vss_t is not None else DEFAULT_TEMP

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "countdown_minutes": AC_COUNTDOWN,
            "ac_ctrl_type": AC_TYPE_FRONT,
        }
        defrost = self._sig(KEY_DEFROST)
        if defrost is not None:
            attrs["defrost"] = bool(defrost)
        fan = self._sig(KEY_FAN_SPEED)
        if fan is not None:
            attrs["fan_speed"] = fan
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    # ---------- 控制 ----------

    @require_control
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        # 开空调 + 设定温度一并下发
        temp = self.target_temperature or DEFAULT_TEMP
        await self._send_ac_on(float(temp), mode=hvac_mode)

    @require_control
    async def async_turn_on(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self._send_ac_on(float(temp) if temp is not None else (self.target_temperature or DEFAULT_TEMP))

    @require_control
    async def async_turn_off(self, **kwargs: Any) -> None:
        cmd_data = {
            "acCtrlValue": "OFF",
            "acCtrlType": AC_TYPE_FRONT,
            "acCountdownTimer": AC_COUNTDOWN,
        }
        await self._dispatch(cmd_data)
        self._optimistic_on = False
        self._optimistic_mode = HVACMode.OFF
        import time as _t1
        self._optimistic_until = _t1.monotonic() + OPTIMISTIC_TTL

    @require_control
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """调温: 若空调已开则仅改温度, 未开则一并开机."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        temp = max(MIN_TEMP, min(MAX_TEMP, float(temp)))
        self._optimistic_temp = temp
        import time as _t2
        self._optimistic_until = _t2.monotonic() + OPTIMISTIC_TTL
        running = self._ac_running()
        if self._optimistic_on is False or running is False:
            # 空调当前关闭 → 只记录温度, 等用户开机时下发
            self.async_write_ha_state()
            return
        await self._send_ac_on(temp, mode=self._optimistic_mode)

    async def _send_ac_on(self, temp: float, mode: HVACMode | None = None) -> None:
        cmd_data = {
            "acCtrlValue": "ON",
            "acCtrlType": AC_TYPE_FRONT,
            "acCountdownTimer": AC_COUNTDOWN,
            # ★ 必须是 Number, 不能 str()
            "acCtrlTemp": _temp_as_number(temp),
        }
        await self._dispatch(cmd_data)
        self._optimistic_on = True
        self._optimistic_mode = mode if mode not in (None, HVACMode.OFF) else HVACMode.COOL
        self._optimistic_temp = temp
        import time as _t3
        self._optimistic_until = _t3.monotonic() + OPTIMISTIC_TTL

    async def _dispatch(self, cmd_data: dict) -> None:
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_AC, cmd_data)
            self._last_result = res
            _LOGGER.info("空调控制 %s 已执行: %s", cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("空调控制 %s 失败: %s", cmd_data, err)
            # 下发失败 → 回滚乐观状态, 避免 UI 显示假成功
            self._optimistic_on = None
            self._optimistic_mode = None
            raise
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


def _temp_as_number(temp: float) -> int | float:
    """acCtrlTemp 序列化为 Number（整数优先）. 见模块 docstring 类型陷阱."""
    f = float(temp)
    return int(f) if f.is_integer() else round(f, 1)
