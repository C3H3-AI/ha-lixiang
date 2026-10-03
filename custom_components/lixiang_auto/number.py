"""理想汽车数值设置实体（number 平台）.

功能（仅保留已实测命令）:
  - 空调设定温度: remoteVehACSmartControl
      {"acCtrlValue":"ON","acCtrlType":"frtACSw","acCountdownTimer":"15",
       "acCtrlTemp":<16-30>}     ← acCtrlTemp 必须是 Number, 不能 str()

★ 旧实现用 remote_ac_temp_adjust + {"temperature":..} 是错的（APK 枚举值），
  已修正为真实的 remoteVehACSmartControl + acCtrlTemp。

⚠️ 充电上限（charge_limit）—— 可写平台，但命令【走 LiNdn 通道，当前不可用】：
  本节此前写「充电上限已移除，只作为 sensor 只读展示」，
  与实现不符 —— 下面 async_setup_entry 里它一直是一个
  【完整可写】的 LiCarNumber(cmd_key=CMD_CHARGE, ...)。
  现按真实行为更正：

    · 实体【保留】（用户可能已用它的状态做自动化，遵循"只增不删"）
    · cmdData 参数是正确的（见 docs/接口参数清单.md），不需要改
    · 但 cmdKey=remote_charge_control 走理想 App 的 LiNdn（JOB）长连接，
      HTTP cmd/send 不支持 → 必然 resultCode=2009
    · 因此：extra_state_attributes 标注只读原因；
      写入时由 li_api 在【发送前】抛 LiChannelNotSupported，
      用户看到「充电走 LiNdn 通道，当前版本不支持控制」而非「执行失败」

⚡ 已验证可用的：空调设定温度（remoteVehACSmartControl）。

状态读取: VSS 实时信号 ac_set_temp (Vehicle.Cabin.AC.SetTemp)

⚠️ 写入会真实作用于车辆。
"""

from __future__ import annotations

import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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

CMD_AC = "remoteVehACSmartControl"
AC_TYPE_FRONT = "frtACSw"
AC_COUNTDOWN = "15"

# ★ 2026-09-24 新增：充电设置
#   命令来源（App index.vehicle.js）：
#     cmdKey: remote_charge_control
#     controlType='1' → chargingLimit（充电上限）
CMD_CHARGE = "remote_charge_control"
# ★ 2026-09-25 修正（teammate 从 App 截图 + 反编译核实）：
#   App 的充电上限滑块范围是 80~100（步进 1）：
#     minValue:80, maxValue:100, step:1, lowerLimit:U（= max(动态, 80)）
#   依据：index.vehicle.js 的 ChargeSetting.ChargingLimit 滑块配置
#   原先我写 50~100 步进 5 是【猜的】，与 App 不符。
CHARGE_MIN = 80
CHARGE_MAX = 100
CHARGE_STEP = 1

# ★ 2026-09-24 乐观更新有效期（秒）
#   依据：HA 轮询间隔 DEFAULT_SCAN_INTERVAL_SECONDS = 60 秒
#   取 2.5 倍轮询周期 = 150 秒 → 保证至少 2 次轮询机会让 VSS 追上
#   （过短：VSS 还没更新乐观值就失效 → 显示回退；
#     过长：服务端真实变化被掩盖过久）
OPTIMISTIC_TTL = 150.0

AC_MIN_TEMP = 16
AC_MAX_TEMP = 30


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
        _LOGGER.warning("无密码登录凭据，跳过 number 实体")
        return
    async_add_entities([
        LiCarNumber(
            coordinator, li_api, device_info, vin,
            suffix="ac_set_temp", name="空调设定温度",
            icon="mdi:thermostat", state_key="ac_set_temp",
            cmd_key=CMD_AC, data_builder=_ac_temp_payload,
            minimum=AC_MIN_TEMP, maximum=AC_MAX_TEMP, step=1,
            unit=UnitOfTemperature.CELSIUS,
            device_class=NumberDeviceClass.TEMPERATURE,
        ),
        # ★ 2026-09-24 新增：充电上限
        #   App 命令：controlType='1', chargingLimit
        LiCarNumber(
            coordinator, li_api, device_info, vin,
            suffix="charge_limit", name="充电上限",
            icon="mdi:battery-charging-80", state_key="charge_limit",
            cmd_key=CMD_CHARGE, data_builder=_charge_limit_payload,
            minimum=CHARGE_MIN, maximum=CHARGE_MAX, step=CHARGE_STEP,
            unit=PERCENTAGE,
            device_class=None,
        ),
    ])


def _charge_limit_payload(value: float) -> dict:
    """构造充电上限报文.

    ★ App 实现（index.vehicle.js）：
        cmdData: {statusControlRequest: 255, controlType: '1',
                  chargingLimit: `${value}`}
    """
    return {
        "statusControlRequest": 255,
        "controlType": "1",
        "chargingLimit": str(int(value)),
    }


def _ac_temp_payload(value: float) -> dict:
    """构造空调设定温度报文. ★ acCtrlTemp 必须是 Number."""
    f = float(value)
    return {
        "acCtrlValue": "ON",
        "acCtrlType": AC_TYPE_FRONT,
        "acCountdownTimer": AC_COUNTDOWN,
        "acCtrlTemp": int(f) if f.is_integer() else round(f, 1),
    }




class LiCarNumber(CoordinatorEntity, NumberEntity):
    """理想车数值设置."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, li_api, device_info, vin: str, *,
                 suffix: str, name: str, icon: str, state_key: str,
                 cmd_key: str, data_builder,
                 minimum: float, maximum: float, step: float,
                 unit: str | None, device_class) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._state_key = state_key
        self._cmd_key = cmd_key
        self._data_builder = data_builder
        self._attr_name = name
        self._attr_icon = icon
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_num_{suffix}"
        self._attr_device_info = device_info
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        if unit:
            self._attr_native_unit_of_measurement = unit
        if device_class is not None:
            self._attr_device_class = device_class
        self._optimistic_value: float | None = None
        self._optimistic_until: float = 0.0
        self._last_result: dict | None = None

    @property
    def native_value(self) -> float | None:
        """★ 2026-09-24：乐观更新带 TTL（同 fan/switch 的修复）

        避免"设置后立即被旧 VSS 值覆盖"。
        """
        import time as _t

        vss_val: float | None = None
        sig = (self.coordinator.data or {}).get("vss", {}).get(self._state_key)
        if sig and sig.get("value") is not None:
            try:
                vss_val = float(sig["value"])
            except (TypeError, ValueError):
                vss_val = None

        if self._optimistic_value is not None:
            if _t.monotonic() < self._optimistic_until:
                # 数值型：允许小误差（0.1）
                if vss_val is None or abs(vss_val - self._optimistic_value) > 0.1:
                    return self._optimistic_value
            self._optimistic_value = None
            self._optimistic_until = 0.0

        return vss_val

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"cmd_key": self._cmd_key}
        # ★ 2026-09-28：走 JOB 通道（充电上限）→ 标注只读原因，
        #   让用户知道"点了会失败"是已知限制而不是集成坏了。
        attrs.update(job_channel_readonly_attrs(self._cmd_key))
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_set_native_value(self, value: float) -> None:
        cmd_data = self._data_builder(value)
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, self._cmd_key, cmd_data)
            self._last_result = res
            self._optimistic_value = float(value)
            import time as _t2
            self._optimistic_until = _t2.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", self._cmd_key, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", self._cmd_key, cmd_data, err)
            self._optimistic_value = None
            raise
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
