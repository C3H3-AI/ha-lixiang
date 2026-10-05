"""理想汽车开关实体（switch 平台）— 车控 cmd/send.

命令（来自 cmd_table_verified.json）:

  方向盘加热 / 座椅加热 / 座椅通风 用 remoteVehACSmartControl 的"自定义控制"形式:
    {"key":"remoteVehACSmartControl","controlType":"strgWhlHeatSw",
     "temp":22.5,"level":0-3,"TimeOut":"40"}
    controlType 取值:
      strgWhlHeatSw  方向盘加热   (实测表内)
      frSeatHeatSw   副驾座椅加热 (实测表内)
      frSeatVentSw   副驾座椅通风 (实测表内)
      flSeatHeatSw   主驾座椅加热 (推断, 同族命名)
      flSeatVentSw   主驾座椅通风 (推断, 同族命名)
    level 0 = 关闭, 1-3 = 档位

★ 旧的 remote_charging_start / remote_sw_heat_on / remote_ai_open 等下划线命名是错的
  （APK 字符串枚举值，不是真实 cmdKey）。

⚠️ 充电类开关（预约充电 / 电池保温）—— 保留实体，但【当前不可控制】：
  cmdKey = remote_charge_control 走理想 App 的 LiNdn（JOB）长连接，
  HTTP cmd/send 不支持 → 必然 resultCode=2009（已实测）。
  · 实体保留（用户可能已用其状态做自动化，遵循"只增不删"）
  · cmdData 参数正确（见 docs/接口参数清单.md），不改
  · extra_state_attributes 标注「只读原因」
  · 写入时由 li_api 在发送前抛 LiChannelNotSupported，给出明确原因

状态读取: VSS 实时信号

⚠️ 车控会真实作用于车辆。
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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

#: ★ 2026-09-28：走 JOB（LiNdn）通道的 switch control_type。
#:   这两个开关的 cmdKey 都是 remote_charge_control → HTTP 必然 2009。
#:   （__CHARGING__ 同理，但它已不在 SWITCHES 列表中，保留为防御）
_JOB_CHANNEL_CONTROL_TYPES = frozenset({
    "__SCHEDULED__",    # 预约充电
    "__INSULATION__",   # 电池保温
    "__CHARGING__",     # 充电启停（已停用，防御性保留）
})

CMD_AC = "remoteVehACSmartControl"
DEFAULT_LEVEL = 1          # 开启时的默认档位 (0=关, 1-3)

# ★ 2026-09-24 乐观更新有效期（秒）
#   依据：HA 轮询间隔 DEFAULT_SCAN_INTERVAL_SECONDS = 60 秒
#   取 2.5 倍轮询周期 = 150 秒 → 保证至少 2 次轮询机会让 VSS 追上
#   （过短：VSS 还没更新乐观值就失效 → 显示回退；
#     过长：服务端真实变化被掩盖过久）
OPTIMISTIC_TTL = 150.0
DEFAULT_TIMEOUT = "40"     # 运行时长(分钟)
DEFAULT_TEMP = 22.5

# 白名单类 controlType: acCtrlValue 只用 "ON"/"OFF"
# (来源: XVehicleJobHelper$Companion.customVehicleACControl 的 listOf 白名单)
_AC_ONOFF_TYPES = frozenset({
    "strgWhlHeatSw", "acHeatFast", "dfstSw", "acCoolFast",
})


def format_temp(temp: float | None) -> float:
    """温度量化到 0.5 的整数倍 (App formatTemp 行为), 缺省 16.0."""
    try:
        t = float(temp) if temp is not None else 16.0
    except (TypeError, ValueError):
        t = 16.0
    return round(t * 2) / 2


def _custom(control_type: str, level: int) -> dict:
    """构造 remoteVehACSmartControl 自定义控制报文 (真实 cmdData).

    ★ 2026-09-23 修正 (由队友 cmd-table 从 XVehicleJobHelper$Companion
      .customVehicleACControl 字节码逐条复现, Lead 已复核):

      RN 侧入参 {key,controlType,temp,level,TimeOut} 是【翻译层输入】,
      真正发出去的 cmdData 只有 4 个字段:
        {"acCtrlType": controlType, "acCtrlValue": <见下>,
         "acCountdownTimer": 30, "acCtrlTemp": <Number>}

      旧实现照抄 RN 入参会失败!

      acCtrlValue 编码规则:
        白名单类 (方向盘/除霜/快热/快冷) -> level>0 ? "ON" : "OFF"
        座椅类   (flSeatHeatSw 等)       -> level>0 ? "LEVEL"+level : "OFF"
    """
    if level is None or level <= 0:
        ctrl_value = "OFF"
    elif control_type in _AC_ONOFF_TYPES:
        ctrl_value = "ON"
    else:
        ctrl_value = f"LEVEL{int(level)}"
    return {
        "acCtrlType": control_type,
        "acCtrlValue": ctrl_value,
        "acCountdownTimer": 30,
        # ★ acCtrlTemp 必须是 Number (Float/Double), 不能是字符串
        "acCtrlTemp": format_temp(DEFAULT_TEMP),
    }


# (唯一后缀, 名称, 图标, 状态key, controlType)
# (唯一后缀, 名称, 图标, 状态key, controlType, 所属功能)
SWITCHES = (
    # ★ 2026-09-28 方向盘加热从 fan 平台迁回 switch（用户反馈「只有开关，没有三档」）
    #
    #   曾放在 fan 平台暴露 0-3 档 —— 那是错的，协议层无法下发档位：
    #     · 本文件的 _AC_ONOFF_TYPES 白名单【本来】就含 strgWhlHeatSw
    #       → _build_ac_ctrl_data 一律折成 "ON"/"OFF"，档位被静默丢弃
    #     · 白名单来源：App 的 XVehicleJobHelper$Companion
    #         .customVehicleACControl 的 listOf
    #     · VSS 路径 WheelWarmStatus.WarmOnOff（OnOff 语义）
    #     · 翻译表 WarmOnOff 仅 {0:关闭, 1:开启}
    #   → 真正的能力就是【开/关】。详见 fan.py 中同段说明。
    #
    #   状态源：wheel_heat 信号（path Vehicle.Cabin.WheelWarmStatus.WarmOnOff）
    #   门控：features["方向盘加热"]（= 能力表 strgWhlHeatSw 存在）
    ("wheel_heat", "方向盘加热", "mdi:steering",
     "wheel_heat", "strgWhlHeatSw", "方向盘加热"),

    # ★ 2026-09-24 补充：空调快捷功能
    #   controlType 来自 VehicleControlModel$Companion
    #   这三个是"白名单类"→ acCtrlValue 只用 "ON"/"OFF"
    ("ac_heat_fast", "空调快速制热", "mdi:fire",
     "ac_fan_speed", "acHeatFast", "空调"),   # ★ state_key=ac_fan_speed (ExSpeedStatus)，
                                                 #   原 key 在 VSS 不存在 → unknown
    ("ac_cool_fast", "空调快速制冷", "mdi:snowflake",
     "ac_fan_speed", "acCoolFast", "空调"),   # ★ 同上
    ("ac_defrost", "除雪除冰", "mdi:snowflake-melt",
     "ac_defrost", "dfstSw", "空调"),
    # ★ 2026-09-24 补充：充电启停
    #   ★ 这个开关的 cmdKey 不是固定的（与其他不同）：
    #     App 用 cmdData.statusControlRequest 决定：
    #       0     → cmdKey = "remote_charging_stop"
    #       非 0  → cmdKey = "remote_charging_start"
    #     cmdData 本身是空 {}（由 send_command 注入 token 等）
    #   → 需要特殊处理（见 LiCarSwitch._send）
    #   ⚠️ 状态读取用 charge_status（ChargeStatus == 3 → 充电中）
    # ★ 2026-09-24 恢复充电启停（用户反馈 + 重新逆向）
    #
    #   ⚠️ 之前移除是【错误判断】：
    #     我曾用 remote_charging_start / remote_charging_stop 作为 cmdKey，
    #     实测返回 resultCode=2009，误以为"功能不支持"。
    #
    #   ✅ 真实实现（App 的 index.vehicle.js 反编译）：
    #     cmdKey: remote_charge_control
    #     cmdData: {
    #       statusControlRequest: 255,
    #       controlType: "3",              ← 3 = 充电启停
    #       OrderChargingSwitch: "1"/"0",  ← 开/关
    #       OrderChargingMode: "...",
    #       reserveStartTime: ..., NewReserveFinishTime: ..., isContinue: ...
    #     }
    #     jobService: mob.metaJobService.remoteChargingControl
    #
    #   其他 controlType：
    #     "1" → chargingLimit（充电限值）
    #     "2" → batteryInsulation（电池保温）
    #
    #   ★ 2009 的原因是 cmdKey 不存在，不是功能不支持。
    # ★ 2026-09-24 修正（用户反馈"充电开关提示错误"）：
    #   ❌ 原来的「充电」用 ChargeStatus==3（正在充电）判断，
    #      语义混乱：App 里这是【状态】不是【开关】，
    #      满电或未插枪时显示"关闭"，与用户预期不符。
    #   ✅ 改为 App 真正提供的开关：预约充电
    #      AppointmentSettings.title = "预约充电"
    #      状态源：ScheduledCharging.Switch
    ("scheduled_charge", "预约充电", "mdi:calendar-clock",
     "scheduled_charge_switch", "__SCHEDULED__", None),
    # ★ 2026-09-24 新增：电池保温
    #   App 命令：cmdKey=remote_charge_control
    #            controlType='2', batteryInsulation: "1"/"0"
    ("battery_insulation", "电池保温", "mdi:thermometer-lines",
     "battery_insulation", "__INSULATION__", None),
    # ★ 2026-09-24 新增（用户建议）：哨兵从两个 button 改为一个 switch
    #   状态源：sentry_switch = SettingsStatus.sentinelSwitch（可靠）
    #   命令：sentinelModeSetting {"sentinelSwitch":0/1}
    ("sentry", "哨兵模式", "mdi:shield-car",
     "sentry_switch", "__SENTRY__", "哨兵"),
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
        _LOGGER.warning("无密码登录凭据，跳过 switch 实体")
        return
    # 按车型功能过滤（features 由 __init__.py 探测; 缺失则全部创建）
    features = (hass.data[DOMAIN][config_entry.entry_id].get("features") or {})
    specs = [
        spec for spec in SWITCHES
        if len(spec) < 6 or features.get(spec[5], True)
    ]
    skipped = [spec[1] for spec in SWITCHES if spec not in specs]
    if skipped:
        _LOGGER.info("车型不支持, 跳过开关: %s", skipped)

    async_add_entities([
        LiCarSwitch(coordinator, li_api, device_info, vin, *spec[:5])
        for spec in specs
    ])


class LiCarSwitch(CoordinatorEntity, SwitchEntity):
    """理想车控开关（座椅/方向盘加热通风）."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, li_api, device_info, vin: str,
                 suffix: str, name: str, icon: str,
                 state_key: str, control_type: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._state_key = state_key
        self._control_type = control_type
        self._attr_name = name
        self._attr_icon = icon
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_sw_{suffix}"
        self._attr_device_info = device_info
        self._optimistic_on: bool | None = None
        # ★ 乐观值有效期（monotonic 时间戳）
        self._optimistic_until: float = 0.0
        self._last_result: dict | None = None

    @property
    def is_on(self) -> bool | None:
        """开关状态.

        ★ 充电开关特例（2026-09-24）：
          ChargeStatus 的语义是枚举（不是 0/1）：
            3 = 充电中 → on
            其他（5 已停止 / 7 告警 / 15 未插枪 等）→ off
          依据：App 的 XChargeDataHandle.getChargeState()
        """
        import time as _t

        sig = (self.coordinator.data or {}).get("vss", {}).get(self._state_key)
        vss_val: bool | None = None

        if sig and sig.get("value") is not None:
            v = sig["value"]
            if self._control_type == "__SCHEDULED__":
                # 预约充电开关：Switch 信号是 "0"/"1" 或 True/False
                s2 = str(v).lower()
                vss_val = s2 in ("1", "true")
            elif self._control_type == "__CHARGING__":
                try:
                    vss_val = int(float(v)) == 3      # 3 = 充电中
                except (TypeError, ValueError):
                    vss_val = None
            elif self._control_type == "__INSULATION__":
                # ★ 电池保温：值是 "0"/"1" 或 True/False
                s2 = str(v).lower()
                vss_val = s2 in ("1", "true")
            elif self._control_type == "__SENTRY__":
                # ★ 哨兵状态是 JSON：{"sentinelSwitch": 0/1}
                import json as _json
                try:
                    o = _json.loads(v) if isinstance(v, str) else v
                    vss_val = bool(int(o.get("sentinelSwitch", 0)))
                except (ValueError, TypeError, AttributeError):
                    vss_val = None
            else:
                try:
                    vss_val = int(float(v)) != 0
                except (TypeError, ValueError):
                    vss_val = bool(v)

        # ★ 2026-09-24 修复（用户反馈座椅档位切换后显示"关闭"）：
        #   原逻辑 VSS 优先，但 VSS 上报有延迟 →
        #   发命令后立刻拉 VSS（旧值）→ 显示错误状态。
        #
        #   新逻辑（乐观更新带 TTL）：
        #     ① 乐观值未过期 且 与 VSS 不一致 → 用乐观值
        #     ② 一致或过期 → 清除乐观值，用 VSS
        if self._optimistic_on is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_val is None or vss_val != self._optimistic_on:
                    return self._optimistic_on
            self._optimistic_on = None
            self._optimistic_until = 0.0

        return vss_val

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "cmd_key": CMD_AC,
            "control_type": self._control_type,
        }
        if self._control_type == "__CHARGING__":
            # ★ 2026-09-24 充电开关特例：
            #   充电启停有【前置条件】，不满足时点了没反应是正常的。
            #   这里显式暴露条件，避免用户困惑。
            vss = (self.coordinator.data or {}).get("vss", {})

            def _num(k: str):
                sig = vss.get(k) or {}
                v = sig.get("value")
                try:
                    return int(float(v)) if v is not None else None
                except (TypeError, ValueError):
                    return None

            gun_ac = _num("charge_gun_ac")      # 2 = 交流枪已插
            soc = _num("battery_level")
            cs = _num("charge_status")

            attrs.update({
                "cmd_key": "remote_charge_control",
                "control_type": "3 (充电启停)",
                "gun_plugged": gun_ac == 2,
                "battery_level": soc,
                "charge_status_raw": cs,
                "requirement": "需插枪 + 电量未满 + 车辆在线",
            })
            # 条件不满足时给出明确原因
            reasons = []
            if gun_ac != 2:
                reasons.append("未插充电枪")
            if soc is not None and soc >= 100:
                reasons.append("电量已满")
            if reasons:
                attrs["cannot_start_reason"] = "、".join(reasons) + "，开启充电不会有实际效果"
        else:
            attrs["level_range"] = "0(关)/1-3(档位)"
        # ★ 2026-09-28：预约充电 / 电池保温走 JOB 通道 → 标注只读原因
        #   注意：__CHARGING__ 分支上面已写 cmd_key=remote_charge_control，
        #   但那条分支已被 __SCHEDULED__ 取代（见 SWITCHES 列表），
        #   这里统一按 control_type 判定，避免遗漏。
        if self._control_type in _JOB_CHANNEL_CONTROL_TYPES:
            attrs.update(job_channel_readonly_attrs("remote_charge_control"))
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(DEFAULT_LEVEL)

    @require_control
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(0)

    async def _send(self, level: int) -> None:
        """下发命令.

        ★ 三种模式（2026-09-24）：
          ① 常规（空调/座椅）：cmdKey 固定 remoteVehACSmartControl
             cmdData = {acCtrlType, acCtrlValue, acCountdownTimer, acCtrlTemp}
          ② 充电启停：cmdKey = remote_charge_control
             cmdData = {statusControlRequest:255, controlType:"3",
                        OrderChargingSwitch:"1"/"0"}
          ③ 电池保温：cmdKey = remote_charge_control
             cmdData = {statusControlRequest:255, controlType:"2",
                        batteryInsulation:"1"/"0"}
          ④ 哨兵：cmdKey = sentinelModeSetting

          ⚠️ 历史错误：曾用 remote_charging_start/stop 作为 cmdKey
             （这两个不存在）→ 返回 2009。已于 2026-09-24 修正。
        """
        if self._control_type == "__SCHEDULED__":
            # ★ 预约充电开关：
            #   App 是把「开关 + 模式 + 时间区间」打包下发的：
            #     controlType='3', OrderChargingSwitch, OrderChargingMode,
            #     reserveStartTime, NewReserveFinishTime, isContinue
            #   这里读当前模式/时间，只改开关位。
            import time as _t
            vss = (self.coordinator.data or {}).get("vss", {})

            def _raw(k: str, dflt: str) -> str:
                sig = vss.get(k) or {}
                v = sig.get("value")
                return str(v).strip('"') if v is not None else dflt

            cmd_key = "remote_charge_control"
            cmd_data = {
                "statusControlRequest": 255,
                "controlType": "3",
                "OrderChargingSwitch": "1" if level != 0 else "0",
                "OrderChargingMode": _raw("charge_order_mode", "2"),
                "reserveStartTime": _raw("scheduled_charge_start", "23:00"),
                "NewReserveFinishTime": _raw("scheduled_charge_end", "08:00"),
                "isContinue": "0",
            }
        elif self._control_type == "__INSULATION__":
            # ★ 2026-09-24 新增：电池保温
            #   App: controlType='2', batteryInsulation: "1"/"0"
            cmd_key = "remote_charge_control"
            cmd_data = {
                "statusControlRequest": 255,
                "controlType": "2",
                "batteryInsulation": "1" if level != 0 else "0",
            }
        elif self._control_type == "__SENTRY__":
            # ★ 哨兵：cmdKey = sentinelModeSetting
            #   ⚠️ 时间戳字段拼写是 "timestap"（少一个 m）—— App 就这么拼，必须照抄
            import time as _t
            cmd_key = "sentinelModeSetting"
            cmd_data = {
                "sentinelSwitch": 1 if level != 0 else 0,
                "timestap": int(_t.time() * 1000),
            }
        else:
            cmd_key = CMD_AC
            cmd_data = _custom(self._control_type, level)

        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, cmd_key, cmd_data)
            self._last_result = res
            self._optimistic_on = level != 0
            # ★ 记录有效期起点
            import time as _t2
            self._optimistic_until = _t2.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", cmd_key, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", cmd_key, cmd_data, err)
            self._optimistic_on = None
            raise
        await self.coordinator.async_request_refresh()
