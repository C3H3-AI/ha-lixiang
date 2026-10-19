"""理想ONE（M 系）车控命令构造 —— 与 X 系是【两套完全不同的协议】。

★★ 来源（全部为官方 smali 实证，非推测）★★
  · `com/chehejia/lib/vehicle/m/constant/MControlKeyConst.smali`
      LXVehicleControlType* → cmdKey 映射（38 个字段）
  · `com/chehejia/oc/m01/vehicle/helper/a0.smali`（工厂类 a0）
      a() ~ k() 每个方法构造一条 OperateReq，内含 commandKey + cmdData
  · `apk_latest/decompiled/assets/2025/LXMVehicleConfig2025.json`（70 条能力表）

★★ 与 X 系的核心差异 ★★

| | X 系（L6 等）| M 系（理想ONE）|
|---|---|---|
| 通道 | `cmd/send`（需 MESH + VAT）| `send-command`（仅 MESH）|
| 空调 | 一个 cmdKey `remoteVehACSmartControl` +  `{acCtrlType,acCtrlValue,acCtrlTemp}` | **多个 cmdKey** + `{Type:"编号",Temp:"21.5"}` 或 `{FLLevel:"2",FLLevelFeedBack:"1"}` |
| 座椅 | 同上（acCtrlType=flSeatHeatSw）| `remote_fl_seat_heat_adjust` 等独立键 |
| 值类型 | Number/字符串混用 | **全部是字符串**（`String.valueOf(x)`）|

★★ M 系 AC 家族的 commandKey（13 个，比配置表多 5 个）★★
  remote_ac_ctrl_new / remote_ac_temp_adjust
  remote_ai_temp_ctrl_ex_on / remote_ai_temp_ctrl_off
  remote_fl_/fr_/rl_/rr_seat_heat_adjust
  remote_sw_heat_on / remote_sw_heat_off

★★ `a0.j()` 的 9 字段默认模板（空调开启时随命令一起发）★★
  {FLLevel:"1", FLLevelFeedBack:"0", FRLevel:"1", FRLevelFeedBack:"0",
   RLLevel:"1", RLLevelFeedBack:"0", RRLevel:"1", RRLevelFeedBack:"0",
   SteerSet:"0"}

★★ Type 编号表（a0 的各方法实证）★★
  1 / 2      方向盘加热          （a0.k()；1=普通 2=另一态）
  3,4,5,6    主驾座椅（档位1~3 → 4,5,6；档位0 时 3=开 / 24=关）
  24,25      主驾：24=关、25=档位6（通风档）
  7,8,9,10   副驾座椅（档位1~3 → 8,9,10；档位0 时 7=开 / 26=关）
  26,27      副驾：26=关、27=档位6
  11,12,13,14 后排左座椅（档位 0~3）
  15,16,17,18 后排右座椅（档位 0~3）
  19 / 20    空调开关（19=普通、20=自动）
  21         空调调温
  22 / 23    快速制冷 / 快速制热（a0.a()）
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: a0.j() 的 9 字段默认模板（空调开启时随命令发；值全是字符串）
AC_LEVELS_DEFAULT: dict[str, str] = {
    "FLLevel": "1",
    "FLLevelFeedBack": "0",
    "FRLevel": "1",
    "FRLevelFeedBack": "0",
    "RLLevel": "1",
    "RLLevelFeedBack": "0",
    "RRLevel": "1",
    "RRLevelFeedBack": "0",
    "SteerSet": "0",
}

#: 座椅四角 → (开/关命令键, 档位字段, 回显字段, Type 基号, 关闭 Type, 通风档 Type)
SEAT_MAP: dict[str, tuple[str, str, str, int, str | None, str | None]] = {
    "fl": ("remote_fl_seat_heat_adjust", "FLLevel", "FLLevelFeedBack", 3, "24", "25"),
    "fr": ("remote_fr_seat_heat_adjust", "FRLevel", "FRLevelFeedBack", 7, "26", "27"),
    "rl": ("remote_rl_seat_heat_adjust", "RLLevel", "RLLevelFeedBack", 11, None, None),
    "rr": ("remote_rr_seat_heat_adjust", "RRLevel", "RRLevelFeedBack", 15, None, None),
}

#: X 系 acCtrlType → M 系座椅角
_SEAT_TYPE_PREFIX: dict[str, str] = {
    "flSeatHeatSw": "fl",
    "flSeatVentSw": "fl",
    "flSeatSw": "fl",
    "frSeatHeatSw": "fr",
    "frSeatVentSw": "fr",
    "frSeatSw": "fr",
    "rlSeatHeatSw": "rl",
    "rlSeatVentSw": "rl",
    "rlSeatSw": "rl",
    "rrSeatHeatSw": "rr",
    "rrSeatVentSw": "rr",
    "rrSeatSw": "rr",
}


def parse_level(value: Any) -> int:
    """把 X 系的 "OFF" / "LEVEL2" / 2 统一成 0~3 档位。"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, min(6, int(value)))
    text = str(value).strip().upper()
    if not text or text == "OFF":
        return 0
    if text.startswith("LEVEL"):
        text = text[5:]
    try:
        return max(0, min(6, int(float(text))))
    except (TypeError, ValueError):
        return 0


def _as_str(value: Any) -> str:
    """M 系所有 cmdData 值都是字符串（官方用 String.valueOf）。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_seat(
    corner: str, level: int, *, ac_on: bool | None, temp: Any = None
) -> tuple[str, dict[str, str]]:
    """构造座椅加热/通风命令。

    官方逻辑（a0.h/i/f/g）：
      · 空调【未开】：commandKey = remote_<角>_seat_heat_adjust
                     cmdData = {<Level>: 档位+1, <Level>FeedBack: 档位}
      · 空调【已开】：commandKey = remote_ac_ctrl_new
                     cmdData = {Type: <编号>, Temp: "<温度>"}
                     Type = 基号 + 档位（档位 0 有专门的"关"编号；
                            档位 6 是通风档，另有编号）
    """
    key, level_field, fb_field, base, _off_type, vent_type = SEAT_MAP[corner]

    # ★ 关闭（档位 0）一律走【专用座椅键】：
    #   · a0.h/i（前两座）在空调开着时用 Type 24/26 表示关；
    #   · a0.f/g（后两座）走的是 cond_5 分支 → 直接发 remote_XX_seat_heat_adjust。
    #   ⇒ 用专用键对四座都成立，且语义最清晰，避免"关"动作依赖空调状态。
    if level <= 0:
        return key, {level_field: "1", fb_field: "0"}

    if ac_on:
        type_code = vent_type if (level >= 6 and vent_type) else str(base + level)
        data: dict[str, str] = {"Type": type_code}
        if temp is not None:
            data["Temp"] = _as_str(temp)
        return "remote_ac_ctrl_new", data

    # 空调未开：直接调座椅，带完整档位（官方 FLLevel = 档位+1、FeedBack = 档位）
    return key, {
        level_field: str(level + 1),
        fb_field: str(level),
    }


def build_wheel_heat(*, on: bool, ac_on: bool | None,
                     temp: Any = None) -> tuple[str, dict[str, str]]:
    """方向盘加热（a0.k()）。

    · 空调已开：commandKey = remote_ac_ctrl_new, cmdData = {Type:"1"/"2", Temp}
    · 空调未开：commandKey = remote_sw_heat_on / _off, cmdData = {SteerSet:"1"/"0"}
    """
    if ac_on:
        data: dict[str, str] = {"Type": "1" if on else "2"}
        if temp is not None:
            data["Temp"] = _as_str(temp)
        return "remote_ac_ctrl_new", data
    data = dict(AC_LEVELS_DEFAULT)
    data["SteerSet"] = "1" if on else "0"
    return ("remote_sw_heat_on" if on else "remote_sw_heat_off"), data


def build_ac_switch(*, on: bool, auto: bool = False,
                    temp: Any = None) -> tuple[str, dict[str, str]]:
    """空调开关（a0.d()）。

    · 开：commandKey = remote_ac_ctrl_new
          cmdData = {Type:"19"(普通)/"20"(自动), Temp:"<温度>"}
    · 关：commandKey = remote_ai_temp_ctrl_off
    """
    if not on:
        return "remote_ai_temp_ctrl_off", {}
    data: dict[str, str] = {"Type": "20" if auto else "19"}
    if temp is not None:
        data["Temp"] = _as_str(temp)
    return "remote_ac_ctrl_new", data


def build_ac_temp(temp: Any, *, ac_on: bool | None,
                  current_temp: Any = None) -> tuple[str, dict[str, str]]:
    """空调调温（a0.e()）。

    · 空调已开：commandKey = remote_ac_ctrl_new, cmdData = {Type:"21", Temp}
    · 空调未开：commandKey = remote_ai_temp_ctrl_ex_on
                cmdData = a0.j() 9 字段 + {Temp}
    """
    value = _as_str(temp if temp is not None else current_temp)
    if ac_on:
        return "remote_ac_ctrl_new", {"Type": "21", "Temp": value}
    data = dict(AC_LEVELS_DEFAULT)
    data["Temp"] = value
    return "remote_ai_temp_ctrl_ex_on", data


def build_rapid(*, heat: bool, temp: Any = None) -> tuple[str, dict[str, str]]:
    """快速制热 / 快速制冷（a0.a()，Type 22/23）。

    ⚠️ 22 与 23 哪个是制热、哪个是制冷，a0.a() 内部由运行时状态位决定，
       静态无法 100% 区分 ⇒ 按「23=制热、22=制冷」实现，
       若真机表现相反，二者对调即可（一行）。
    """
    data: dict[str, str] = {"Type": "23" if heat else "22"}
    if temp is not None:
        data["Temp"] = _as_str(temp)
    return "remote_ac_ctrl_new", data


def translate(cmd_data: dict[str, Any] | None, *,
              ac_on: bool | None) -> tuple[str, dict[str, str]] | None:
    """把 X 系的 AC cmdData 翻译成 M 系 (commandKey, cmdData)。

    返回 None 表示「不认识，交给调用方按原样处理」。

    输入是各平台现在传的 X 系格式：
      {acCtrlType:"frtACSw", acCtrlValue:"ON"/"OFF"/"LEVEL2",
       acCtrlTemp:21.5, acCountdownTimer:"40"}
    """
    if not cmd_data:
        return None
    ctype = str(cmd_data.get("acCtrlType") or "").strip()
    cval = str(cmd_data.get("acCtrlValue") or "").strip()
    temp = cmd_data.get("acCtrlTemp")
    if temp is None:
        temp = cmd_data.get("temp")

    # ── 座椅四角 ───────────────────────────────────────────────
    corner = _SEAT_TYPE_PREFIX.get(ctype)
    if corner:
        return build_seat(corner, parse_level(cval), ac_on=ac_on, temp=temp)

    # ── 方向盘加热 ─────────────────────────────────────────────
    if ctype in ("strgWhlHeatSw", "wheelHeatSw"):
        on = cval.upper() not in ("OFF", "0", "FALSE", "")
        return build_wheel_heat(on=on, ac_on=ac_on, temp=temp)

    # ── 空调开关 ───────────────────────────────────────────────
    if ctype in ("frtACSw", "frtACAUTOSw"):
        on = cval.upper() not in ("OFF", "0", "FALSE", "")
        auto = ctype == "frtACAUTOSw"
        if on and temp is None and not auto:
            # 只给 ON 不给温度 → 按调温逻辑（官方 a0.e）
            return build_ac_temp(None, ac_on=ac_on)
        return build_ac_switch(on=on, auto=auto, temp=temp)

    # ── 快速制热 / 快速制冷 ────────────────────────────────────
    if ctype == "acHeatFast":
        return build_rapid(heat=True, temp=temp)
    if ctype == "acCoolFast":
        return build_rapid(heat=False, temp=temp)

    return None


# ══════════════════════════════════════════════════════════════════════════
# ★★★ 官方 commandKeyMap（权威表，19 条）★★★
#
# 来源：`com/chehejia/lib/vehicle/m/model/control/VehicleControlModel.smali`
#       的 `commandKeyMap`（Kotlin Pair 逐条构造，2026-10-20 逐条提取）
#
# 【命名键 11 条】—— 已在本模块/li_api 中实现
# 【数字键 8 条】—— 服务端接受**数字字符串**当 commandKey（M 系老协议特色）
#                   ⚠️ 但这 8 条的 **cmdData 格式尚无静态证据**，
#                      直接发空 cmdData 是猜测（违反「不猜」纪律）⇒ 未启用。
#                      它们对应的能力（拍照/哨兵/唤醒/电池加热/充电目标/
#                      预约充电/预约OTA/预约空调）待补齐 cmdData 后再接。
# ══════════════════════════════════════════════════════════════════════════
OFFICIAL_COMMAND_KEY_MAP: dict[str, str] = {
    # ── 命名键（已实现）────────────────────────────────────────
    "LXVehicleControlTypeDoorUnlock": "remote_central_lock_unlock",
    "LXVehicleControlTypeDoorlock": "remote_central_lock_lock",
    "LXVehicleControlTypeOpenWindow": "remote_window_open",
    "LXVehicleControlTypeCloseWindow": "remote_window_close",
    "LXVehicleControlTypeOpenTrunk": "remote_plg_open",
    "LXVehicleControlTypeCloseTrunk": "remote_plg_close",
    "LXVehicleControlTypeLocation": "remote_veh_search",
    "LXVehicleControlTypeRemoteStart": "remote_engine_start",
    "LXVehicleControlTypeOpenAC": "remote_ac_ctrl_new",
    "LXVehicleControlTypeStartCharging": "remote_charging_start",
    "LXVehicleControlTypeStopCharging": "remote_charging_stop",
    # ── 数字键（commandKey 已知，cmdData 待查 ⇒ 未启用）─────────
    "LXVehicleControlTypeStartPhoto": "50.0",
    "LXVehicleControlTypeSentry": "55.0",
    "LXVehicleControlTypeWakeUp": "60.0",
    "LXVehicleControlTypeBatteryHeat": "100.0",
    "LXVehicleControlTypeChargingTarget": "101.0",
    "LXVehicleControlTypeAppointmentCharging": "102.0",
    "LXVehicleControlTypeAppointmentOTA": "103.0",
    "LXVehicleControlTypeAppointmentAC": "104.0",
}

#: 数字型 commandKey → 中文名（便于日志与诊断；★ 未启用下发）
NUMERIC_COMMAND_KEYS: dict[str, str] = {
    "50.0": "远程拍照",
    "55.0": "哨兵模式",
    "60.0": "唤醒车辆",
    "100.0": "电池加热",
    "101.0": "充电目标",
    "102.0": "预约充电",
    "103.0": "预约 OTA",
    "104.0": "预约空调",
}


# ══════════════════════════════════════════════════════════════════════════
# ★ M 系「子数据刷新」参数体系（`MSubKeyConst` / `MParamsConst` 实证）
#
#   MParamsConst：sub_key / interval_time
#   MSubKeyConst：photo / charge / OTA / Healthy / Maintain / MinusScreen /
#                 AcAppointment
#
# ⚠️★ 更正（2026-10-20）：**sub_key 是【刷新子数据】用的，不是车控命令参数** ★
#    证据：`LxMSubDataManager.smali`（42KB）里这些取值与
#    `handleSubData step1/2/3`、`refresh params` 同现 —— 是**读数据**链路
#    （刷新 photo/OTA/健康/保养 等子数据），不是下发命令。
#    此前我一度以为数字键命令的 cmdData = {"sub_key": ...}，那是错的 ——
#    那个 `{"sub_key":"MinusScreen"}` 出现在 `VehicleControlDockingDelegate`
#    里，而该文件几乎全是 BLE / 厂商对接（oppo/vivo/honor/ble_params_origin），
#    只提到过一次 LXVehicleControlTypeWakeUp，不是通用命令构造器。
#    ⇒ 已撤回该推断，不再作为命令参数使用。
#
# ★★ 真正的结论：数字键 8 条里 7 条本就用专用 HTTP 端点实现（更可靠）✔
#      50.0  拍照     → EP_SVM_TAKE_PHOTO
#      60.0  唤醒     → EP_WAKEUP
#      100.0 电池加热 → EP_BATTERY_WARM
#      101.0 充电目标 → EP_CHARGE_THRESHOLD
#      102.0 预约充电 → EP_CHARGE_APPOINTMENT
#      103.0 预约OTA  → EP_OTA_UPGRADE
#      104.0 预约空调 → EP_AC_APPOINTMENT
#    ⇒ 唯一真正缺的是 **55.0 哨兵模式**（无专用端点，cmdData 无静态证据）。
# ══════════════════════════════════════════════════════════════════════════
SUB_KEY_PARAM = "sub_key"
INTERVAL_TIME_PARAM = "interval_time"

#: ⚠️ 仅供「子数据刷新」参考 —— **不要当作车控命令的 cmdData**
SUB_KEYS: dict[str, str] = {
    "photo": "photo",
    "charge": "charge",
    "ota": "OTA",
    "healthy": "Healthy",
    "maintain": "Maintain",
    "minus_screen": "MinusScreen",
    "ac_appointment": "AcAppointment",
}

#: 哨兵模式（55.0）—— ⚠️ cmdData 无静态证据，暂不下发（保持只读）
SENTRY_COMMAND_KEY = "55.0"
