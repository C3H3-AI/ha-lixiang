"""理想ONE 实时状态映射 —— **真实响应**回归测试（2026-10-11）。

依据：车主回传的 `lixiang_auto.dump_realtime_state` 探针 JSON
（VIN `LW433B111M1027177`，`realtime_state_v3` 返回 `ok=true, code=0, SUCCESS`）。

本测试用**真实响应片段**驱动映射，而不是手搓的假数据 —— 这样才能验证
"字段名/形态/类型"是否真的对得上（2026-10-11 就靠它发现了 `online_5g`
永远 unknown 的问题：`vehOnlineStatus.status` 是**字符串枚举 "Sleeping"**，
而代码当时用 `_int01()` 解析 0/1，必然得到 None）。

实测得到的量纲校准（本文件锁定，防漂移）：
  · residueBattery = 98      → 电量 %            ✅
  · batteryEndurance = 152   → 纯电续航 km        ✅
  · fuelEndurance = 202      → 燃油续航 km        ✅
  · residueFuel = 28         → 剩余油量 L         ✅
  · indoorTemperature = 21.0 → 车内温度 °C        ✅
  · airPollutionIndex = 3    → 空气污染指数        ✅
  · mainDoor.isOpen = "0"    → 门关闭             ✅
  · mainWindow.openStatus=0  → 车窗关闭           ✅
  · travelStatus.gear = "P"  → 挡位               ✅
"""
from __future__ import annotations

import json

import pytest

from m01_state import map_realtime_state

# ── 真实响应（车主 2026-10-11 回传，节选自 raw.data，未做任何改动）────────────
REAL_RESPONSE = {
    "timestamp": 1791628550583,
    "systemCurrentTime": 1791683158949,
    "chargeSetting": {
        "timestamp": 1791628550583,
        "chargeStatus": {
            "chargeStatus": "10", "chargeMode": None, "surplusTime": "-2147483648",
            "voltage": "393.7", "current": "0.0", "power": "-2147483648",
        },
        "enduranceStatus": {
            "batteryEndurance": "152", "fuelEndurance": "202",
            "residueBattery": "98", "residueFuel": "28", "vcuFenceSts": "1",
        },
        "chargingTarget": {"target": "100"},
    },
    "doorSwitchStatus": {
        "mainDoor": {"isOpen": "0", "actionTime": 1791628545582, "isLock": "1", "lockTime": 1791628545582},
        "copilotDoor": {"isOpen": "0", "actionTime": 1791628545582, "isLock": "1", "lockTime": 1791628545582},
        "backRightDoor": {"isOpen": "0", "actionTime": 1791628545582, "isLock": "1", "lockTime": 1791628545582},
        "backLeftDoor": {"isOpen": "0", "actionTime": 1791628545582, "isLock": "1", "lockTime": 1791628545582},
        "trunkDoor": {"isOpen": "0", "actionTime": 1791628545582, "isLock": "1", "lockTime": 1791628545582},
    },
    "windowSwitchStatus": {
        "mainWindow": {"openStatus": "0", "actionTime": 1791628545582},
        "copilotWindow": {"openStatus": "0", "actionTime": 1791628545582},
        "backRightWindow": {"openStatus": "0", "actionTime": 1791628545582},
        "backLeftWindow": {"openStatus": "0", "actionTime": 1791628545582},
        "skylightWindow": {"openStatus": "0", "actionTime": 1791628549409},
    },
    "rearviewMirrorFoldStatus": {"status": "0", "timestamp": 1791628545582},
    "temperatureStatus": {
        "indoorTemperature": "21.0", "outdoorTemperature": "20.5", "airPollutionIndex": "3",
    },
    "airConditioningStatus": {
        "acOffStatus": {"value": "0", "timestamp": 1791628545582},
        "acAutoStatus": {"value": "0", "timestamp": 1791628545582},
        "acWindSpeed": {"value": "1", "timestamp": 1791628545582},
        "acFLTempStatus": {"value": "21.5", "timestamp": 1791628545582},
        "acFRTempStatus": {"value": "21.5", "timestamp": 1791628545582},
        "acWindTempStatus": {"value": "0", "timestamp": 1791628545582},
        "acDefrostModeSts": {"value": "0", "timestamp": 1791628545582},
    },
    "seatStatus": {
        "flSeatHeatVent": "0", "frSeatHeatVent": "0", "rlSeatHeatVent": "0", "rrSeatHeatVent": "0",
        "flSeatHeatVentState": {"value": "0", "timestamp": 1791628545582},
        "frSeatHeatVentState": {"value": "0", "timestamp": 1791628545582},
        "rlSeatHeatVentState": {"value": "0", "timestamp": 1791628545582},
        "rrSeatHeatVentState": {"value": "0", "timestamp": 1791628545582},
    },
    "travelStatus": {"gear": "P", "timestamp": 1791628548410},
    "locationStatus": {
        "lon": 103.739957, "lat": 36.100944, "dir": 191.1, "alt": 1482.8, "ct": 1791626498214,
    },
    # ★ 关键：status 是**字符串枚举**，休眠时为 "Sleeping"（不是 0/1）
    "vehOnlineStatus": {"status": "Sleeping", "deviceStatus": None, "timestamp": 1791683127767},
    "vehPowerMode": {
        "powerMode": "0", "powerModeFlag": "0",
        "powerModeState": {"status": "0", "timestamp": 1791628549409},
        "powerModeFlagState": {"status": "0", "timestamp": 1791628549409},
    },
    "ringLightStatus": {"status": "1", "timestamp": 1791628550583},
    "keyInCarWarning": {"warning": "0", "timestamp": 1791628545582},
    "caseCoverStatus": {"switchState": "0", "timestamp": 1791628545582},
    "remoteStartStatus": {"startStatus": "0", "timestamp": 1791628545582},
    "forgetCloseDoorWarning": {"warning": "0", "timestamp": 1791628545582},
    "vehRealtimeAlarm": {"timestamp": 1791628550583, "alarms": [], "alarmCount": 0},
}


def _v(out: dict, key: str):
    sig = out.get(key)
    return None if sig is None else sig.get("value")


class TestRealResponseParsing:
    """★ 用真实响应驱动 —— 验证字段名/形态/类型真的对得上。"""

    def setup_method(self):
        self.out = map_realtime_state(REAL_RESPONSE)

    def test_endurance_units(self):
        assert _v(self.out, "battery_level") == 98      # %
        assert _v(self.out, "range_elec_cltc") == 152   # km
        assert _v(self.out, "range_fuel_cltc") == 202   # km
        assert _v(self.out, "fuel_level") == 28         # L（本次新增）

    def test_charge_and_temps(self):
        assert _v(self.out, "charge_status") == 10
        assert _v(self.out, "inside_temp") == 21.0
        assert _v(self.out, "air_pollution") == 3

    def test_doors_and_windows_closed(self):
        for k in ("door_main", "door_copilot", "door_back_left", "door_back_right", "door_trunk"):
            assert _v(self.out, k) == 0, f"{k} 应为关闭(0)"
        for k in ("window_main", "window_copilot", "window_back_left",
                  "window_back_right", "window_skylight"):
            assert _v(self.out, k) == 0, f"{k} 应为关闭(0)"

    def test_gear_is_string(self):
        assert _v(self.out, "gear") == "P"

    def test_seat_and_ac(self):
        for k in ("seat_heat_vent_fl", "seat_heat_vent_fr",
                  "seat_heat_vent_rl", "seat_heat_vent_rr"):
            assert _v(self.out, k) == 0, f"{k} 应为 0（关闭）"
        # ★ 空调**复用 L 系已有信号键**（一个概念一个实体，不按车型分叉）
        # 实测 acOffStatus = "0"，语义是"**不**处于关闭状态" → 即空调是**开**的
        # ⚠️ 字段名带 Off 而我们统一"1=开"，故必须取反（代码里已标注这一点）
        assert _v(self.out, "ac_on") == 1

    def test_ac_reuses_l_series_keys(self):
        """★ M 系空调不新建实体，复用 L 系的键（UI/自动化不用写两套）。"""
        assert _v(self.out, "ac_auto_mode") == 0
        assert _v(self.out, "ac_fan_speed_level") == 1
        assert _v(self.out, "ac_set_temp_fl") == 21.5
        assert _v(self.out, "ac_set_temp_fr") == 21.5
        assert _v(self.out, "ac_wind_mode") == 0

    def test_location_json(self):
        loc = json.loads(_v(self.out, "location"))
        assert loc["lat"] == 36.100944
        assert loc["lon"] == 103.739957
        assert loc["alt"] == 1482.8


class TestOnlineStatusStringEnum:
    """★ 这次实测抓到的真 bug：status 是字符串枚举，用 `_int01()` 必然 None。"""

    def test_sleeping_maps_to_off(self):
        out = map_realtime_state(REAL_RESPONSE)
        assert _v(out, "online_5g") == 0, '"Sleeping" 必须解析为 0（休眠）'

    @pytest.mark.parametrize("raw,expect", [
        ("Sleeping", 0), ("sleeping", 0), ("SLEEP", 0),
        ("Awake", 1), ("Online", 1), ("Active", 1),
    ])
    def test_enum_variants(self, raw, expect):
        res = dict(REAL_RESPONSE)
        res["vehOnlineStatus"] = {"status": raw}
        assert _v(map_realtime_state(res), "online_5g") == expect

    def test_numeric_still_works(self):
        """兼容：若某些固件仍给 0/1，不能因此崩掉。"""
        res = dict(REAL_RESPONSE)
        res["vehOnlineStatus"] = {"status": "1"}
        assert _v(map_realtime_state(res), "online_5g") == 1


class TestRobustness:
    def test_missing_sections_do_not_crash(self):
        for missing in ("seatStatus", "airConditioningStatus", "locationStatus",
                        "vehOnlineStatus", "windowSwitchStatus", "ringLightStatus"):
            res = {k: v for k, v in REAL_RESPONSE.items() if k != missing}
            map_realtime_state(res)          # 不抛异常即可

    def test_empty_response(self):
        assert map_realtime_state({}) == {}
