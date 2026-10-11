"""老平台车型（M 系 / M01 / 理想ONE）实时状态 —— real-time-state 通道。

★ 2026-10-11 逆向结论（APK 8.27.0，代码级证据）
------------------------------------------------
| 环节 | 证据 | 产物 |
|---|---|---|
| 端点 | `NetApiConst.GET_VEHICLE_STATE(vin)` → `Pair("/ssp-as-mobile-api/v3-0/vehicles/" + vin + "/real-time-state", "get")` | `smali_classes11/.../constant/NetApiConst$Companion.smali` |
| 响应模型 | `DynamicInfoRes`（25 个顶层字段 + 子 bean） | `.../m/model/res/DynamicInfoRes.smali` |
| M 系解析 | `LXM01StateDelegate`（14 个 get*） | `.../m/delegate/LXM01StateDelegate$*.smali` |
| 平台开关 | `LXVehicleManagerFactory.delegateMap` 键 = 整数 **1** → M 系代理；X 系走 VSS / LiMesh | `.../entrance/LXVehicleManagerFactory.smali` |

与旧结论一致：`isM() = platform === '1'`，M01B 是 68 个配置里唯一 `platform == '1'`。

为什么需要它
------------
VSS（`vss:get-batch`）对 M 系**恒返 `access_denied`** —— 理想ONE 车主日志实证：
49 分钟内 `实时信号=0 条`（一条实时数据都没有）。而上面这条端点是
**社区方案 hasscc 的默认数据源**（新车型 L6 反而报 100035）。

★ 关键设计：本模块把 `DynamicInfoRes` 映射进**与我们 VSS 相同的 signal-key 空间**
  （`{key: {"value": .., "ts": ..}}`），因此上层实体 / 渲染 / 卡片**一行都不用改**。

★ 值语义必须与 VSS 侧一致（否则渲染会错）：
  · 门：`0/1`（`Semantics.DOOR_OPEN`，==1 才开）
  · 窗：数值 `%`（渲染层 `int(val)`）
  · 电量：数值 `%`
  · 续航：数值 `km`
  · 充电状态：数值（3 = 充电中，见 `rendering.render_value`）

⚠️ 待实车验证：本映射依据静态逆向 + hasscc 互证建立；字段是否真的返回、
   值的量纲是否符合预期，需由理想ONE 车主用 `lixiang_auto.dump_realtime_state`
   回传真实响应后核对（本模块刻意做成纯函数，便于拿真实 payload 直接跑断言）。
"""
from __future__ import annotations

import json

from typing import Any

#: App 里 M 系的判定值（LXVehicleManagerFactory.delegateMap 的键）
M_SERIES_PLATFORM = "1"

#: 座位 → 信号键（实测字段 seatStatus.<座>SeatHeatVentState.value）
_SEAT_MAP = {
    "fl": "seat_heat_vent_fl",
    "fr": "seat_heat_vent_fr",
    "rl": "seat_heat_vent_rl",
    "rr": "seat_heat_vent_rr",
}

#: M 系空调字段 → **复用 L 系已有信号键**（一个概念一个实体，不新建重复项）
#: 依据：L 系走 VSS（Vehicle.Cabin.AC.*），M 系走 real-time-state；
#:     两条通道语义相同 → 共用同一批实体，UI/自动化不用分车型写两套。
#: ⚠️ 各档位语义（风量 1-3、出风模式 0-4）**未实测**，沿用旧表 → 属 [推断]
_AC_MAP = {
    "acOffStatus": "ac_on",            # ★ 注意：字段是 OffStatus，0=关 → 需取反
    "acAutoStatus": "ac_auto_mode",
    "acWindSpeed": "ac_fan_speed_level",
    "acFLTempStatus": "ac_set_temp_fl",
    "acFRTempStatus": "ac_set_temp_fr",
    "acDefrostModeSts": "ac_defrost",
    "acWindTempStatus": "ac_wind_mode",
}

#: 需要取反的字段（字段名说的是"关"，而我们统一用"开=1"）
_AC_INVERT = {"acOffStatus"}

#: vehOnlineStatus.status 的休眠态字符串（实测 2026-10-11 理想ONE："Sleeping"）
#: ⚠️ 其余取值（在线/唤醒中…）未见样本 → 一律按"在线"处理，属 [推断]
_SLEEP_STATES = {"sleeping", "sleep", "asleep", "offline", "standby", "powersave"}

#: DynamicInfoRes.doorSwitchStatus 字段 → 我们的信号键
_DOOR_MAP = {
    "mainDoor": "door_main",
    "copilotDoor": "door_copilot",
    "backLeftDoor": "door_back_left",
    "backRightDoor": "door_back_right",
    "trunkDoor": "door_trunk",
}

#: DynamicInfoRes.windowSwitchStatus 字段 → 我们的信号键
_WINDOW_MAP = {
    "mainWindow": "window_main",
    "copilotWindow": "window_copilot",
    "backLeftWindow": "window_back_left",
    "backRightWindow": "window_back_right",
    "skylightWindow": "window_skylight",
}


def is_m_series(ability: Any) -> bool:
    """该车型是否属于 M 系（理想ONE 等老平台）→ 需走 real-time-state。

    ★ 判据直接对齐 App：`platform == '1'`（M01A / M01B）。
      能力表里有 `platform` 与 `unityModel`，两者应一致；能力表缺失时
      退回 `unityModel` 以 `M0` 开头（M01A / M01B），避免误判 X 系。
    """
    if ability is None:
        return False
    plat = str(getattr(ability, "platform", "") or "").strip()
    if plat == M_SERIES_PLATFORM:
        return True
    unity = str(getattr(ability, "unity_model", "") or "").strip().upper()
    return unity.startswith("M0")


def _dig(obj: Any, *path: str) -> dict:
    """按路径取子对象（任一层缺失/非 dict → 返回 {}）。"""
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(key)
    return cur if isinstance(cur, dict) else {}


def _raw(val: Any) -> Any:
    """取值：兼容 `{"value": ..}` 形态（bean 里常见），并原样透传标量。"""
    if isinstance(val, dict):
        return val.get("value")
    return val


def _num(val: Any) -> float | int | None:
    """转成数值（电量 %、续航 km 用）。非数字返回 None。"""
    v = _raw(val)
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _int01(val: Any) -> int | None:
    """门/开关：归一到 0 / 1（VSS 侧 `Semantics.DOOR_OPEN` 就是 ==1 才开）。"""
    v = _raw(val)
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if int(v) else 0
    s = str(v).strip().lower()
    if s in ("true", "on", "open", "1", "opened"):
        return 1
    if s in ("false", "off", "closed", "close", "0", ""):
        return 0
    try:
        return 1 if int(float(s)) else 0
    except (TypeError, ValueError):
        return None


def _window_pct(val: Any) -> float | int | None:
    """车窗开度（%）。

    ★ App 侧字段是 `openStatus`（String），语义**待实车确认**：
      · 数值（如 "0" / "40"）→ 直接当百分比（我们的 `window_*` 单位就是 %）
      · 非数值（"open" / "closed"）→ 退化为 100 / 0
    两种都先兜住，等理想ONE 车主回传真实响应后收敛。
    """
    v = _raw(val)
    if v is None:
        return None
    n = _num(v)
    if n is not None:
        return n
    s = str(v).strip().lower()
    if s in ("open", "opened", "true", "on"):
        return 100
    if s in ("closed", "close", "false", "off"):
        return 0
    return None


def map_realtime_state(res: Any) -> dict[str, dict]:
    """把 `real-time-state` 的响应体（DynamicInfoRes）映射成信号字典。

    入参：`DynamicInfoRes` 本身（即接口 `data` 字段）。
    出参：`{信号键: {"value": .., "ts": ..}}`，可直接并入 `data["vss"]`。
    """
    out: dict[str, dict] = {}
    if not isinstance(res, dict):
        return out

    ts = res.get("timestamp") or res.get("systemCurrentTime") or 0
    ts = str(ts or 0)

    def put(key: str | None, value: Any) -> None:
        if not key or value is None:
            return
        out[key] = {"value": value, "ts": ts}

    # 电量 / 续航（chargeSetting.enduranceStatus）
    endu = _dig(res, "chargeSetting", "enduranceStatus")
    put("battery_level", _num(endu.get("residueBattery")))
    put("range_elec_cltc", _num(endu.get("batteryEndurance")))
    put("range_fuel_cltc", _num(endu.get("fuelEndurance")))

    # 充电状态（chargeSetting.chargeStatus）
    cst = _dig(res, "chargeSetting", "chargeStatus")
    put("charge_status", _num(cst.get("chargeStatus")))

    # 车内温度（temperatureStatus.indoorTemperature）
    put("inside_temp", _num(_dig(res, "temperatureStatus").get("indoorTemperature")))
    # 空气污染指数（temperatureStatus.airPollutionIndex —— App 的 getAirQuality）
    put("air_pollution", _num(_dig(res, "temperatureStatus").get("airPollutionIndex")))

    # 位置：device_tracker 读的是 **JSON 字符串**（含 v/lat/lon/alt/dir…）
    #   —— App 侧 locationStatus = {alt, ct, dir, lat, lon}，这里拼成同结构
    _loc = res.get("locationStatus")
    if isinstance(_loc, dict):
        _lat, _lon = _num(_loc.get("lat")), _num(_loc.get("lon"))
        if _lat is not None and _lon is not None:
            put("location", json.dumps({
                "v": 1, "lat": _lat, "lon": _lon,
                "alt": _num(_loc.get("alt")),
                "dir": _num(_loc.get("dir")),
            }, ensure_ascii=False))

    # 在线状态（vehOnlineStatus.status）—— 供 coordinator 的 vehicle_status 兜底使用
    #   ★ 实测（2026-10-11 理想ONE 车主回传 real-time-state 原始响应）：
    #     status 是**字符串枚举**，休眠时实测为 "Sleeping"，**不是 0/1**
    #   → 之前用 _int01 解析必然得到 None（在线状态永远 unknown）
    _on = _raw(_dig(res, "vehOnlineStatus").get("status"))
    if isinstance(_on, str) and _on.strip():
        put("online_5g", 0 if _on.strip().lower() in _SLEEP_STATES else 1)

    # ---- 2026-10-11 按车主回传的实测响应扩展 ----
    # 依据：real-time-state v3 原始响应（realtime_state_v3 / ok=true, code=0）
    # ⚠️ 下面的【档位语义】目前只有"关=0"这一档被实测覆盖；1/2/3 各档含义仍属 [推断]，
    #    与 translations.py 里 SeatHeatState/SeatVentilationState 的旧表一致（同样未实测）。

    # 座椅加热/通风（seatStatus.<座位>SeatHeatVentState.value）
    seats = res.get("seatStatus")
    if isinstance(seats, dict):
        for src, key in _SEAT_MAP.items():
            _v = _num(_dig(seats, f"{src}SeatHeatVentState").get("value")
                      if isinstance(seats.get(f"{src}SeatHeatVentState"), dict)
                      else seats.get(f"{src}SeatHeatVentState"))
            if _v is None:
                _v = _num(seats.get(f"{src}SeatHeatVent"))
            if _v is not None:
                put(key, _v)

    # 空调（airConditioningStatus.*，多数是 {value, timestamp} 形态）
    acs = res.get("airConditioningStatus")
    if isinstance(acs, dict):
        for src, key in _AC_MAP.items():
            _v = _num(acs.get(src))
            if _v is None:
                continue
            if src in _AC_INVERT:
                # acOffStatus 语义 = "是否关闭"（实测 0）→ 我们的 ac_on 语义 = "是否开启"
                #   取反：0(不关) → 1(开)；1(关) → 0(关)
                _v = 0 if _v else 1
            put(key, _v)

    # 剩余油量（chargeSetting.enduranceStatus.residueFuel，单位 L）
    _rf = _num(_dig(res, "chargeSetting", "enduranceStatus").get("residueFuel"))
    if _rf is not None:
        put("fuel_level", _rf)

    # 挡位（travelStatus.gear，实测 "P"）
    _g = _raw(_dig(res, "travelStatus").get("gear"))
    if isinstance(_g, str) and _g.strip():
        put("gear", _g.strip())

    # 环形灯（ringLightStatus.status，实测 "1"；⚠️ 0/1 语义未实测）
    _rl = _num(_dig(res, "ringLightStatus").get("status"))
    if _rl is not None:
        put("ring_light", _rl)

    # 车内是否有钥匙（keyInCarWarning.warning，实测 "0"）
    _ki = _num(_dig(res, "keyInCarWarning").get("warning"))
    if _ki is not None:
        put("key_in_car_warning", _ki)

    # 五门（★ App 侧：doorSwitchStatus.<门>.isOpen，类型是 String）
    doors = res.get("doorSwitchStatus")
    if isinstance(doors, dict):
        for src, key in _DOOR_MAP.items():
            put(key, _int01(_dig(doors, src).get("isOpen") or doors.get(src)))

    # 车窗 + 天窗（★ App 侧：windowSwitchStatus.<窗>.openStatus，类型是 String）
    wins = res.get("windowSwitchStatus")
    if isinstance(wins, dict):
        for src, key in _WINDOW_MAP.items():
            put(key, _window_pct(_dig(wins, src).get("openStatus")
                                 or wins.get(src)))

    return out
