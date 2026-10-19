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
    # ★ 2026-10-19：附带 M 系【原始枚举码】，供 rendering 走官方映射表。
    #   （X 系那套归一化码与 M 系不同：X=0/40/50/… ，M=10 NotCharging 等）
    put("__m01_charge", _num(cst.get("chargeStatus")))

    # ★★★ 2026-10-18：理想ONE【专属】的 3 项功能 —— 权威清单 LXMVehicleConfig2025.json
    #   与 X 系表比对后确认只有 M 系有：SetChargeLimit（充电阈值）/
    #   SetChargeInsulation（充电保温）/ SetChargeAppointment（预约充电）。
    #   数据【本来就在 real-time-state 里】，此前没映射 → ONE 上这三项全 unknown。
    #
    #   实测（2026-10-17，ONE 家人账号）：
    #     chargingTarget    = {"target": "100"}                      → 充电阈值
    #     batteryWarmSwitch = {"switchState": "0"}                   → 充电保温
    #     appointmentTime   = {"chargeOnOff":0, "startTime":"23:00",
    #                          "endTime":"06:00", "isContinue":true} → 预约充电

    # ① 充电阈值（与 X 系「充电上限」同义 → 复用 charge_limit，number 实体直接可用）
    _tgt = _dig(res, "chargeSetting", "chargingTarget")
    put("charge_limit", _num(_tgt.get("target")))

    # ② 充电保温（M 系专属开关）
    _warm = _dig(res, "chargeSetting", "batteryWarmSwitch")
    put("battery_insulation", _int01(_warm.get("switchState")))

    # ③ 预约充电（M 系专属：开关 + 起止时间）
    _appt = _dig(res, "chargeSetting", "appointmentTime")
    if _appt:
        put("charge_appointment", _int01(_appt.get("chargeOnOff")))
        _st = _raw(_appt.get("startTime"))
        _et = _raw(_appt.get("endTime"))
        if isinstance(_st, str) and _st.strip():
            put("charge_appointment_start", _st.strip())
        if isinstance(_et, str) and _et.strip():
            put("charge_appointment_end", _et.strip())

    # ★ 2026-10-12 新增：未达充电上限继续充电（**仅 M 系有**，见 signals.py）
    #   官方车型定义里这条能力只存在于 M01A/M01B（L 系整条标签不存在），
    #   所以实体侧用 requires="version:upperLimitCharging" 门控。
    #
    #   ⚠️ 字段名来源与置信度：
    #     值名 `upperlimitContinue`（注意是**小写 u**）来自 App 的
    #     index.vehicle.bundle 字符串表，与同段的
    #     isSupportUpperLimitCharging / UpperLimitSwitchValue /
    #     getUpperlimitContinueText / isShowUpperLimitTips 属同一功能组。
    #     但**未在 M 系真机上确认**该字段确实出现在 real-time-state 的
    #     chargeSetting 下 —— 若无此字段，_dig 返回 {}，put 跳过，
    #     实体表现为 unknown（不会报错、不会误报）。
    #     M 系车主实测后请据实修正本行。
    _ul = _dig(res, "chargeSetting", "upperlimitContinue")
    if _ul:
        put("upperlimit_continue", _int01(_ul.get("upperlimitContinue")))

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
    # ★ 2026-10-17：实体用的键是 `online_status`（signals.py），而这里原先只写
    #   `online_5g` → 「在线状态」实体永远 unknown。两个键都写（消费方不同）。
    if isinstance(_on, str) and _on.strip():
        put("online_status", 0 if _on.strip().lower() in _SLEEP_STATES else 1)

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

    # 剩余油量（chargeSetting.enduranceStatus.residueFuel，单位 %）
      # ★ 2026-10-14：原注释写 L 有误，证据见 sensor.py 中 fuel_level 注释
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

        # ★ 2026-10-18：整车【锁车状态】—— 此前只映射了 isOpen（门开合），
        #   漏了 isLock（门锁）→ 理想ONE 的 `lock.车锁` 实体永远 unknown。
        #
        #   实测响应：doorSwitchStatus.mainDoor = {"isOpen":"0", "isLock":"1"}
        #
        #   ★ 语义与取值（有据，非猜）：
        #     · 我方 lock.py：`lock_main` 且 `int(value) == 0 → locked`（0 = 已落锁）
        #     · 官方语义：Vehicle.Body.DoorLockStatus.MainDoor，
        #       semantics = Semantics.LOCKED（值表示"是否落锁"）
        #     · 该次采样时车辆【离线/休眠】—— 休眠的车必然是落锁的，
        #       而响应 isLock="1" → 可判定 **isLock=1 表示"已落锁"**
        #     → 因此需【取反】写入：1 → 0（locked），0 → 1（unlocked）
        #   ⚠️ 若后续拿到"解锁"状态的样本，请复核此取反（本项目规则：据实修正）。
        _lock_raw = _int01(_dig(doors, "mainDoor").get("isLock"))
        if _lock_raw is None:
            _md = doors.get("mainDoor")
            if isinstance(_md, dict):
                _lock_raw = _int01(_md.get("isLock"))
        if _lock_raw is not None:
            put("lock_main", 1 - _lock_raw)          # ★ 取反：1(落锁) → 0(locked)

    # 车窗 + 天窗（★ App 侧：windowSwitchStatus.<窗>.openStatus，类型是 String）
    wins = res.get("windowSwitchStatus")
    if isinstance(wins, dict):
        for src, key in _WINDOW_MAP.items():
            put(key, _window_pct(_dig(wins, src).get("openStatus")
                                 or wins.get(src)))

    # ==================================================================
    # ★ 2026-10-12：补齐 DynamicInfoRes 剩余字段
    #
    #   依据：`DynamicInfoRes` 在 App 里共 **26 个顶层字段**（smali 实测），
    #   本文件此前只消费了 11 个，剩下的一律丢弃 —— 于是 M 系车主的
    #   充电口盖 / 方向盘加热 / 里程统计 / OTA 版本 等实体长期 unknown。
    #
    #   下面分两类：
    #     A. 填进**已有信号**（这些信号在 L 系由 VSS 提供，M 系一直没有值）；
    #     B. 填进**新增的 M 系专属信号**（见 signals.py 的 platform:1 段）。
    # ==================================================================

    # ── A1. 充电口盖（caseCoverStatus.switchState: String）
    #   映射到已有信号 charge_port_lid（Semantics.CHARGE_LID）
    _ccv = _dig(res, "caseCoverStatus").get("switchState")
    if _ccv is not None:
        put("charge_port_lid", _int01(_ccv))

    # ── A2. 方向盘加热（wheelWarmStatus.warmOnOff: String）
    #   映射到已有信号 wheel_heat（L 系走 VSS，M 系此前恒为 unknown）
    _ww = _raw(_dig(res, "wheelWarmStatus").get("warmOnOff"))
    if _ww is not None:
        put("wheel_heat", _int01(_ww))

    # ── A3. OTA 目标版本（otaUpgradeInfo.targetVersion: String）
    #   映射到已有信号 ota_version（"车机版本"）
    _ota = _dig(res, "otaUpgradeInfo")
    _otv = _raw(_ota.get("targetVersion"))
    if isinstance(_otv, str) and _otv.strip():
        put("ota_version", _otv.strip())

    # ── A4. 月度里程 / 能耗（monthTravelData: 8 个 Double）
    #   已有信号：stat_total_mileage / stat_elec_mileage / stat_engine_mileage
    #           month_charge_kwh
    _mtd = _dig(res, "monthTravelData")
    put("stat_total_mileage", _num(_mtd.get("totalMileage")))
    put("stat_elec_mileage", _num(_mtd.get("elecMileage")))
    put("stat_engine_mileage", _num(_mtd.get("fuelMileage")))
    put("month_charge_kwh", _num(_mtd.get("totalElecEnergy")))

    # ── B. 新增 M 系专属信号（signals.py 里 requires="platform:1"）
    #
    #   B1. 实时告警条数（vehRealtimeAlarm.alarmCount: Int）
    put("veh_alarm_count", _num(_dig(res, "vehRealtimeAlarm").get("alarmCount")))

    #   B2. 保养到期项数（vehRealtimeMaint.expireItemCount: Int）
    put("maint_expire_count",
        _num(_dig(res, "vehRealtimeMaint").get("expireItemCount")))

    #   B3. 电源模式（vehPowerMode.powerMode / powerModeFlag: String）
    _pm = _raw(_dig(res, "vehPowerMode").get("powerMode"))
    if isinstance(_pm, str) and _pm.strip():
        put("power_mode", _pm.strip())
        # ★ 2026-10-20：附带原始码供 rendering 走官方枚举
        #   （车主截图显示「电源模式 = 2」裸值 —— 实际是"整车通电"）
        put("__m01_power_mode", _pm.strip())

    #   B4. 远程启动状态（remoteStartStatus.startStatus: String）
    _rs = _raw(_dig(res, "remoteStartStatus").get("startStatus"))
    if isinstance(_rs, str) and _rs.strip():
        put("remote_start_status", _rs.strip())

    #   B5-B7. 今日行程（vehEnergy.todayEnergy: {mileage, elecEnergy, fuelConsumption}）
    _te = _dig(res, "vehEnergy", "todayEnergy")
    put("today_mileage", _num(_te.get("mileage")))
    put("today_elec_energy", _num(_te.get("elecEnergy")))
    put("today_fuel_consumption", _num(_te.get("fuelConsumption")))

    #   B8-B10. 月度油耗 / 节省 / 平均电耗油耗
    put("month_fuel_energy", _num(_mtd.get("totalFuelEnergy")))
    put("month_save_money", _num(_mtd.get("saveMoney")))
    put("month_avg_elec_energy", _num(_mtd.get("avgElecEnergy")))
    put("month_avg_fuel_energy", _num(_mtd.get("avgFuelEnergy")))

    # ── 其它 M 系状态（2026-10-18 补齐）────────────────────────
    #
    # ★ 依据 ONE 实车 real-time-state 响应（2026-10-17 采样）：
    #   wheelWarmStatus   = {"warmOnOff":"0", ...}    → 方向盘/座椅加热总开关
    #   ringLightStatus   = {"status":"1", ...}        → 环形灯
    #   remoteStartStatus = {"startStatus":"0", ...}   → 远程启动状态
    _whl = _dig(res, "wheelWarmStatus")
    put("wheel_heat_switch", _int01(_whl.get("warmOnOff")))

    _ring = _dig(res, "ringLightStatus")
    put("ring_light_status", _int01(_ring.get("status")))

    _rs = _dig(res, "remoteStartStatus")
    put("remote_start_state", _int01(_rs.get("startStatus")))

    # ★ versionSupport：App 自己的功能支持表（1=支持 / 0=不支持）。
    #   ONE 实车实测 15 项 —— 据此判断某功能【这台车】到底有没有，
    #   比「App 静态能力表有没有这条标签」更准（那是全局表，这是本车实际上报）。
    #   ONE 实测：acAppointment=1 / energyCostV2=1 / familyKey=1 /
    #            independentTemperatureCtrl=1 / rapidTemCtrl=1 / taskMaster=1
    #            chargingRecord=0 / energyCost=0 / wakeupHu=0 / rapidVent=0
    _vs = res.get("versionSupport")
    if isinstance(_vs, dict):
        for _k, _v in _vs.items():
            if isinstance(_v, (int, bool)):
                put("support_" + _k, int(_v))


    # ── 充电电压 / 电流（2026-10-19 补齐）──────────────────────────
    #   实测 ONE 响应：chargeSetting.chargeStatus = {
    #     "chargeStatus": 10, "voltage": 377.0, "current": 0.0, …}
    #   键名沿用 signals.py 已有的 charge_voltage_ac / charge_current_ac
    _cs = _dig(res, "chargeSetting", "chargeStatus")
    put("charge_voltage_ac", _num(_cs.get("voltage")))
    put("charge_current_ac", _num(_cs.get("current")))

    # ── 车外温度（2026-10-19 新增）─────────────────────────────────
    #   实测：temperatureStatus.outdoorTemperature = 17.5（℃）
    #   注意：signals.py 里本来没有「车外温度」键 —— 需同时补 SignalSpec
    _tsx = _dig(res, "temperatureStatus")
    put("outside_temp", _num(_tsx.get("outdoorTemperature")))

    # ── 四座加热通风档位（2026-10-19 补齐）────────────────────────
    #   实测：seatStatus = {flSeatHeatVent: 0, frSeatHeatVent: 0,
    #                       rlSeatHeatVent: 0, rrSeatHeatVent: 0}
    _seat = _dig(res, "seatStatus")
    put("seat_heat_vent_fl", _num(_seat.get("flSeatHeatVent")))
    put("seat_heat_vent_fr", _num(_seat.get("frSeatHeatVent")))
    put("seat_heat_vent_rl", _num(_seat.get("rlSeatHeatVent")))
    put("seat_heat_vent_rr", _num(_seat.get("rrSeatHeatVent")))


    # ── 其余四门「锁」状态（2026-10-19 补齐）──────────────────────
    #   实测：doorSwitchStatus.<门> = {"isOpen": 0, "isLock": 1, …}
    #   （此前只映射了主驾门锁）
    _door2 = _dig(res, "doorSwitchStatus")
    put("lock_copilot", _int01(_dig(_door2, "copilotDoor").get("isLock")))
    put("lock_back_left", _int01(_dig(_door2, "backLeftDoor").get("isLock")))
    put("lock_back_right", _int01(_dig(_door2, "backRightDoor").get("isLock")))

    return out
