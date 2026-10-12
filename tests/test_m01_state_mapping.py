"""M 系（理想ONE）real-time-state 映射完整性测试。

★ 2026-10-12 背景：
   App 的 `DynamicInfoRes` 共 **26 个顶层字段**（smali 实测，
   `com/chehejia/lib/vehicle/m/model/res/DynamicInfoRes.smali`），
   但 `m01_state.map_realtime_state()` 原先只消费 11 个 ——
   于是 M 系车主的「充电口盖 / 方向盘加热 / 里程统计 / OTA 版本」等
   实体长期显示 unknown（字段就在响应里，我们丢掉了）。

   本文件锁定**补全后的映射**，防止将来重构又把它丢掉。

证据来源（均可复查）：
  · DynamicInfoRes.smali 的 26 个顶层 `.field`
  · 各嵌套 bean 的子字段（WheelWarmStatusBean.warmOnOff 等）
  · 测试机真机验证：M 系通道（/real-time-state）
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_INTEG = _ROOT / "custom_components" / "lixiang_auto"
sys.path.insert(0, str(_INTEG))


def _load_m01_state():
    """直接 exec 加载 m01_state.py。

    ★ 不能 `from lixiang_auto import m01_state` —— 包的 __init__.py 会
      import homeassistant，而测试环境没有 HA（conftest 只把集成目录
      加进 sys.path，使 `import signals` 这类模块级导入可用）。
    m01_state.py 本身只依赖标准库，所以直接 exec 最干净。
    """
    src = (_INTEG / "m01_state.py").read_text(encoding="utf-8")
    mod = types.ModuleType("m01_state_under_test")
    mod.__file__ = str(_INTEG / "m01_state.py")
    exec(compile(src, "m01_state.py", "exec"), mod.__dict__)
    return mod


m = _load_m01_state()
import signals as sg  # noqa: E402


def _load_features():
    """exec 加载 features.py。

    features.py 有两个相对导入（const / vehicle_ability），测试环境没有 HA 包：
      ① 按 tests/test_bugfixes_20260928.py 的做法，先把 vehicle_ability
         以顶层模块身份预载进 sys.modules（同样替换它的 `from .const`）
      ② 再把 features 的 `from .const` 替换、`from .vehicle_ability` 改顶层
    """
    if "vehicle_ability" not in sys.modules:
        va_src = (_INTEG / "vehicle_ability.py").read_text(encoding="utf-8")
        va_src = va_src.replace("from .const import LOGGER_NAME",
                                "LOGGER_NAME = 'test'")
        va_src = va_src.replace(
            '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
            f'_CONFIG_DIR = Path({str(_INTEG / "vehicle_configs")!r})')
        va = types.ModuleType("vehicle_ability")
        va.__file__ = str(_INTEG / "vehicle_ability.py")
        exec(compile(va_src, "vehicle_ability.py", "exec"), va.__dict__)
        sys.modules["vehicle_ability"] = va

    src = (_INTEG / "features.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace("from .vehicle_ability import VehicleAbility, get_ability",
                      "from vehicle_ability import VehicleAbility, get_ability")
    mod = types.ModuleType("features_under_test")
    mod.__file__ = str(_INTEG / "features.py")
    exec(compile(src, "features.py", "exec"), mod.__dict__)
    return mod


_f = _load_features()


# ---------------------------------------------------------------------------
# 一份"照 App bean 结构写的"合成响应
# ---------------------------------------------------------------------------
def _fixture() -> dict:
    """模拟 real-time-state 的 data（DynamicInfoRes）。

    字段名/嵌套层级都照 smali 里的 bean 抄，不是编的。
    """
    return {
        "timestamp": 1760000000000,
        # ── 原有 11 个字段（抽样，确保没被破坏）────────────────
        "chargeSetting": {
            "enduranceStatus": {
                "residueBattery": "62",
                "batteryEndurance": "310",
                "fuelEndurance": "480",
                "residueFuel": "28.5",
            },
            "chargeStatus": {"chargeStatus": "2"},
            "upperlimitContinue": {"upperlimitContinue": "1"},
        },
        "temperatureStatus": {
            "indoorTemperature": "22.5",
            "airPollutionIndex": "35",
        },
        "vehOnlineStatus": {"status": "Awake"},
        "travelStatus": {"gear": "P"},
        "ringLightStatus": {"status": "1"},
        "keyInCarWarning": {"warning": "0"},
        "locationStatus": {"lat": 30.1, "lon": 120.2, "alt": 10, "dir": 90},
        "seatStatus": {
            "flSeatHeatVentState": {"value": "2"},
            "frSeatHeatVentState": {"value": "0"},
            "rlSeatHeatVentState": {"value": "1"},
            "rrSeatHeatVentState": {"value": "0"},
        },
        "airConditioningStatus": {
            "acOffStatus": "0",
            "acAutoStatus": "1",
            "acWindSpeed": "3",
            "acFLTempStatus": "23",
            "acFRTempStatus": "23",
            "acDefrostModeSts": "0",
            "acWindTempStatus": "1",
        },
        "doorSwitchStatus": {
            "mainDoor": {"isOpen": "0"},
            "copilotDoor": {"isOpen": "0"},
            "backLeftDoor": {"isOpen": "1"},
            "backRightDoor": {"isOpen": "0"},
            "trunkDoor": {"isOpen": "0"},
        },
        "windowSwitchStatus": {
            "mainWindow": {"openStatus": "0"},
            "copilotWindow": {"openStatus": "0"},
            "backLeftWindow": {"openStatus": "40"},
            "backRightWindow": {"openStatus": "0"},
            "skylightWindow": {"openStatus": "0"},
        },
        # ── ★ 本次新增的 11 个字段 ────────────────────────────
        "caseCoverStatus": {"switchState": "1", "timestamp": 1760000000000},
        "wheelWarmStatus": {"warmOnOff": "1", "timestamp": 1760000000000},
        "otaUpgradeInfo": {
            "baseVersion": "5.0.0", "targetVersion": "5.1.0",
            "errorType": 0, "upgradeEventTypeCode": 1,
            "upgradeTriggerType": 0, "vin": "TESTVIN",
        },
        "monthTravelData": {
            "totalMileage": 1185.5, "elecMileage": 800.0, "fuelMileage": 385.5,
            "totalElecEnergy": 210.5, "totalFuelEnergy": 32.8,
            "avgElecEnergy": 26.3, "avgFuelEnergy": 8.5, "saveMoney": 412.0,
        },
        "vehRealtimeAlarm": {"alarmCount": 2},
        "vehRealtimeMaint": {"expireItemCount": 1, "vin": "TESTVIN"},
        "vehPowerMode": {"powerMode": "READY", "powerModeFlag": "1"},
        "remoteStartStatus": {"startStatus": "0", "timestamp": 1760000000000},
        "vehEnergy": {
            "todayEnergy": {
                "mileage": 42.7, "elecEnergy": 9.8, "fuelConsumption": 0.0,
            },
        },
    }


@pytest.fixture()
def mapped() -> dict:
    return m.map_realtime_state(_fixture())


# ---------------------------------------------------------------------------
# 1. 新增字段全部映射到（回归守卫）
# ---------------------------------------------------------------------------
EXPECTED_NEW = {
    # 填进【已有信号】的 5 个（M 系此前一直是 unknown）
    "charge_port_lid": 1,
    "wheel_heat": 1,
    "ota_version": "5.1.0",
    "stat_total_mileage": 1185.5,
    "stat_elec_mileage": 800.0,
    "stat_engine_mileage": 385.5,
    "month_charge_kwh": 210.5,
    # 填进【新增 M 系专属信号】的 11 个
    "veh_alarm_count": 2,
    "maint_expire_count": 1,
    "power_mode": "READY",
    "remote_start_status": "0",
    "today_mileage": 42.7,
    "today_elec_energy": 9.8,
    "today_fuel_consumption": 0.0,
    "month_fuel_energy": 32.8,
    "month_save_money": 412.0,
    "month_avg_elec_energy": 26.3,
    "month_avg_fuel_energy": 8.5,
}


class TestNewFieldsAreMapped:
    def test_all_expected_keys_present(self, mapped):
        missing = [k for k in EXPECTED_NEW if k not in mapped]
        assert not missing, f"这些字段没被映射（又丢了？）: {missing}"

    @pytest.mark.parametrize("key,expect", sorted(EXPECTED_NEW.items()))
    def test_value_correct(self, mapped, key, expect):
        assert mapped[key]["value"] == expect, (
            f"{key}: 期望 {expect!r}，实际 {mapped[key]['value']!r}")

    def test_ts_propagated(self, mapped):
        """每条映射都要带 ts（coordinator 靠它判断新鲜度）。"""
        for k, v in mapped.items():
            assert v.get("ts"), f"{k} 缺 ts"

    def test_zero_is_not_dropped(self, mapped):
        """★ 0 是合法值，不能被当成"空"丢掉。

        踩过的坑：`if value:` 会把 0/0.0 判为假 → 油箱空/油耗 0 时实体 unknown。
        """
        assert mapped["today_fuel_consumption"]["value"] == 0.0
        assert mapped["remote_start_status"]["value"] == "0"


# ---------------------------------------------------------------------------
# 2. 新信号必须是 M 系专属（否则 L 系会多出永远 unknown 的实体）
# ---------------------------------------------------------------------------
NEW_SIGNAL_KEYS = {
    "veh_alarm_count", "maint_expire_count", "power_mode",
    "remote_start_status", "today_mileage", "today_elec_energy",
    "today_fuel_consumption", "month_fuel_energy", "month_save_money",
    "month_avg_elec_energy", "month_avg_fuel_energy",
}


class TestNewSignalsAreMSeriesOnly:
    def test_keys_exist_in_signal_table(self):
        missing = NEW_SIGNAL_KEYS - set(sg.SIGNALS)
        assert not missing, f"信号表里没有: {missing}"

    @pytest.mark.parametrize("key", sorted(NEW_SIGNAL_KEYS))
    def test_gated_by_platform_1(self, key):
        spec = sg.SIGNALS[key]
        assert spec.requires == "platform:1", (
            f"{key}: requires={spec.requires!r}，应为 'platform:1' "
            f"（这些字段只存在于 M 系的 DynamicInfoRes）")

    @pytest.mark.parametrize("key", sorted(NEW_SIGNAL_KEYS))
    def test_path_is_empty(self, key):
        """值由 m01_state 注入，不走 VSS 路径解析。"""
        assert sg.SIGNALS[key].path == "", f"{key}: path 应为空"


# ---------------------------------------------------------------------------
# 3. 燃油信号必须被「燃油」门控（纯电车不该看到）
# ---------------------------------------------------------------------------
class TestFuelSignalsGated:
    @pytest.mark.parametrize("key", [
        "today_fuel_consumption", "month_fuel_energy", "month_avg_fuel_energy",
    ])
    def test_gated_as_combustion(self, key):
        assert _f.feature_of(key) == "燃油", (
            f"{key} 是增程专属（M 系有油箱，纯电 i 系没有）—— "
            f"必须被「燃油」门控，否则 i6 之类纯电车会显示油耗")


# ---------------------------------------------------------------------------
# 4. 兼容性：原有字段没被破坏
# ---------------------------------------------------------------------------
class TestExistingFieldsIntact:
    @pytest.mark.parametrize("key,expect", [
        ("battery_level", 62),
        ("range_elec_cltc", 310),
        ("range_fuel_cltc", 480),
        ("fuel_level", 28.5),
        ("inside_temp", 22.5),
        ("air_pollution", 35),
        ("gear", "P"),
        ("ring_light", 1),
        ("key_in_car_warning", 0),
        ("upperlimit_continue", 1),
        ("ac_auto_mode", 1),
        ("ac_fan_speed_level", 3),
        ("door_back_left", 1),
        ("door_main", 0),
        ("window_back_left", 40),
        ("window_main", 0),
        ("seat_heat_vent_fl", 2),
        ("seat_heat_vent_rl", 1),
    ])
    def test_unchanged(self, mapped, key, expect):
        assert mapped[key]["value"] == expect, f"{key} 映射被改坏了"

    def test_online_awake_is_1(self, mapped):
        assert mapped["online_5g"]["value"] == 1

    def test_location_is_json(self, mapped):
        import json
        loc = json.loads(mapped["location"]["value"])
        assert loc["lat"] == 30.1 and loc["lon"] == 120.2


# ---------------------------------------------------------------------------
# 5. 健壮性：字段缺失/类型异常不能抛
# ---------------------------------------------------------------------------
class TestRobustness:
    @pytest.mark.parametrize("payload", [
        None, {}, [], "not a dict", 42,
        {"caseCoverStatus": None},
        {"wheelWarmStatus": "unexpected"},
        {"monthTravelData": []},
        {"otaUpgradeInfo": {"targetVersion": None}},
        {"vehEnergy": {"todayEnergy": None}},
        {"vehRealtimeAlarm": {"alarmCount": "abc"}},
        {"vehPowerMode": {"powerMode": ""}},       # 空串 → 跳过
        {"remoteStartStatus": {"startStatus": "  "}},
        {"monthTravelData": {"totalMileage": "not-a-number"}},
    ])
    def test_never_raises(self, payload):
        out = m.map_realtime_state(payload)
        assert isinstance(out, dict)

    def test_empty_string_value_skipped(self):
        """空字符串不该产生实体值（否则显示空）。"""
        out = m.map_realtime_state({"vehPowerMode": {"powerMode": ""}})
        assert "power_mode" not in out

    def test_nonnumeric_skipped(self):
        out = m.map_realtime_state(
            {"vehRealtimeAlarm": {"alarmCount": "abc"}})
        assert "veh_alarm_count" not in out
