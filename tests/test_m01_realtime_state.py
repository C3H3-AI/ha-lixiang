"""老平台（M 系 / 理想ONE）real-time-state 通道 —— 回归测试（2026-10-11）。

依据（静态逆向，APK 8.27.0）
---------------------------
- 端点：`NetApiConst.GET_VEHICLE_STATE(vin)` →
  `GET /ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state`
- 响应：`DynamicInfoRes`；M 系由 `LXM01StateDelegate` 解析
- 平台：App 用 `platform == '1'` 选 M 系代理（X 系走 VSS / LiMesh）

为什么必须有这些测试
-------------------
映射是**照着逆向字段名写的**，没有真实响应可跑（我们只有 L6，该端点返回 100035）。
所以：① 值语义必须锁死（门 0/1、窗 %、续航 km……与 VSS 侧一致，否则渲染会错）；
② 字段路径必须锁死（将来漏一个就少一个实体）；
③ 平台判定必须锁死（误判会把 X 系也拖到这条通道上）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
sys.path.insert(0, str(CC))

import m01_state  # noqa: E402

COORD = CC / "coordinator.py"
INIT = CC / "__init__.py"


#: 典型 DynamicInfoRes（字段名来自 smali 的 DynamicInfoRes$* 定义）
SAMPLE = {
    "timestamp": 1760000000000,
    "vehPowerMode": {"value": 2},
    "chargeSetting": {
        "enduranceStatus": {
            "residueBattery": 46,
            "batteryEndurance": 180,
            "fuelEndurance": 620,
            "residueFuel": 30,
        },
        "chargeStatus": {"chargeStatus": 3, "current": 16, "voltage": 220},
    },
    "doorSwitchStatus": {
        "mainDoor": 0,
        "copilotDoor": 0,
        "backLeftDoor": 1,
        "backRightDoor": 0,
        "trunkDoor": 0,
    },
    "windowSwitchStatus": {
        "mainWindow": 0,
        "copilotWindow": 0,
        "backLeftWindow": 40,
        "backRightWindow": 0,
        "skylightWindow": 0,
    },
}


class TestMapper:
    def test_battery_and_ranges(self):
        out = m01_state.map_realtime_state(SAMPLE)
        assert out["battery_level"]["value"] == 46, out.get("battery_level")
        assert out["range_elec_cltc"]["value"] == 180, out.get("range_elec_cltc")
        assert out["range_fuel_cltc"]["value"] == 620, out.get("range_fuel_cltc")

    def test_charge_status(self):
        """★ 充电状态是数值枚举（rendering 里 3 = 充电中）—— 不能被转成字符串。"""
        out = m01_state.map_realtime_state(SAMPLE)
        assert out["charge_status"]["value"] == 3, out.get("charge_status")

    def test_doors_are_zero_one(self):
        """★ 门必须归一成 0/1（VSS 侧 Semantics.DOOR_OPEN 就是 ==1 才开）。"""
        out = m01_state.map_realtime_state(SAMPLE)
        assert out["door_back_left"]["value"] == 1
        assert all(out[f"door_{k}"]["value"] == 0
                   for k in ("main", "copilot", "back_right", "trunk"))

    def test_windows_are_numeric(self):
        out = m01_state.map_realtime_state(SAMPLE)
        assert out["window_back_left"]["value"] == 40
        assert out["window_main"]["value"] == 0

    def test_timestamp_carried(self):
        out = m01_state.map_realtime_state(SAMPLE)
        assert out["battery_level"]["ts"] == "1760000000000"

    def test_tolerates_bean_value_shape(self):
        """字段可能是 `{"value": ..}` 形态（bean），必须能取到。"""
        payload = {"chargeSetting": {"enduranceStatus": {"residueBattery": {"value": 55}}}}
        assert m01_state.map_realtime_state(payload)["battery_level"]["value"] == 55

    def test_door_values_are_normalized_from_arbitrary_numbers(self):
        """★ 门值必须归一成 0/1 —— 服务端给 2、-1、0.0 之类也要压到 0/1。

        （只测 0/1 样例是假测试：把归一逻辑删掉照样全绿，2026-10-11 踩到。）
        """
        out = m01_state.map_realtime_state({
            "doorSwitchStatus": {"mainDoor": 2, "copilotDoor": -1,
                                 "backLeftDoor": 0.0, "trunkDoor": 3}})
        assert out["door_main"]["value"] == 1, out["door_main"]
        assert out["door_copilot"]["value"] == 1, out["door_copilot"]
        assert out["door_back_left"]["value"] == 0, out["door_back_left"]
        assert out["door_trunk"]["value"] == 1, out["door_trunk"]

    def test_door_truthy_strings(self):
        assert m01_state.map_realtime_state(
            {"doorSwitchStatus": {"mainDoor": "true"}})["door_main"]["value"] == 1
        assert m01_state.map_realtime_state(
            {"doorSwitchStatus": {"mainDoor": "closed"}})["door_main"]["value"] == 0

    def test_missing_sections_are_skipped(self):
        out = m01_state.map_realtime_state({"timestamp": 1})
        assert out == {}, out

    def test_invalid_input(self):
        assert m01_state.map_realtime_state(None) == {}
        assert m01_state.map_realtime_state({}) == {}
        assert m01_state.map_realtime_state("oops") == {}

    def test_garbage_values_dropped(self):
        out = m01_state.map_realtime_state(
            {"chargeSetting": {"enduranceStatus": {"residueBattery": "N/A"}}})
        assert "battery_level" not in out


class TestExtendedFields:
    """App 能显示全部功能 → 这些字段在 ONE 上应当都有值。"""

    def test_inside_temp(self):
        out = m01_state.map_realtime_state(
            {"temperatureStatus": {"indoorTemperature": "23.5",
                                   "outdoorTemperature": "31"}})
        assert out["inside_temp"]["value"] == 23.5

    def test_location_is_json_string(self):
        """★ device_tracker 解析的是 JSON 字符串，不是 dict。"""
        out = m01_state.map_realtime_state(
            {"locationStatus": {"lat": "31.23", "lon": "121.47",
                                "alt": "12", "dir": "90"}})
        raw = out["location"]["value"]
        assert isinstance(raw, str), type(raw)
        import json as _json
        loc = _json.loads(raw)
        assert loc["v"] == 1 and loc["lat"] == 31.23 and loc["lon"] == 121.47
        assert loc["alt"] == 12

    def test_location_without_coords_is_skipped(self):
        out = m01_state.map_realtime_state({"locationStatus": {"alt": "1"}})
        assert "location" not in out

    def test_online_status(self):
        out = m01_state.map_realtime_state({"vehOnlineStatus": {"status": "1"}})
        assert out["online_5g"]["value"] == 1


class TestNestedBeanShape:
    """★ App 实测结构：门/窗是 bean 对象，值在 `isOpen` / `openStatus`（String）。"""

    BEAN = {
        "timestamp": 7,
        "doorSwitchStatus": {
            "mainDoor": {"isOpen": "0", "isLock": "1", "actionTime": 1},
            "backLeftDoor": {"isOpen": "1", "isLock": "1", "actionTime": 1},
            "trunkDoor": {"isOpen": "false", "isLock": "1"},
        },
        "windowSwitchStatus": {
            "mainWindow": {"openStatus": "0", "actionTime": 1},
            "backLeftWindow": {"openStatus": "40", "actionTime": 1},
            "skylightWindow": {"openStatus": "closed"},
        },
    }

    def test_doors_from_bean(self):
        out = m01_state.map_realtime_state(self.BEAN)
        assert out["door_main"]["value"] == 0
        assert out["door_back_left"]["value"] == 1
        assert out["door_trunk"]["value"] == 0

    def test_windows_from_bean(self):
        out = m01_state.map_realtime_state(self.BEAN)
        assert out["window_main"]["value"] == 0
        assert out["window_back_left"]["value"] == 40
        assert out["window_skylight"]["value"] == 0

    def test_window_open_keyword(self):
        """非数值 openStatus：open → 100、closed → 0（语义待实车确认，先兜住）。"""
        out = m01_state.map_realtime_state(
            {"windowSwitchStatus": {"mainWindow": {"openStatus": "open"}}})
        assert out["window_main"]["value"] == 100


class TestPlatformGate:
    class _A:
        def __init__(self, platform="", unity=""):
            self.platform = platform
            self.unity_model = unity

    def test_m_series_by_platform(self):
        """★ App 的判据就是 platform == '1'。"""
        assert m01_state.is_m_series(self._A(platform="1")) is True

    def test_m_series_by_unity_model(self):
        assert m01_state.is_m_series(self._A(unity="M01B")) is True

    def test_x_series_is_not(self):
        assert m01_state.is_m_series(self._A(platform="0", unity="X04")) is False

    def test_none_ability(self):
        assert m01_state.is_m_series(None) is False


class TestWiring:
    def test_coordinator_merges_and_fills_gaps_only(self):
        src = COORD.read_text(encoding="utf-8")
        assert "data[\"vss\"].setdefault(_k, _v)" in src, (
            "必须只补 VSS 没拿到的键 —— 否则会覆盖 VSS 的真实值")

    def test_coordinator_gated(self):
        src = COORD.read_text(encoding="utf-8")
        assert "if self._use_realtime_state or getattr(self, \"_vss_denied_notified\", False):" in src

    def test_network_call_has_credential_check(self):
        """新增的网络分支必须做凭据判定（既有守卫会查，这里再锁一次语义）。"""
        src = COORD.read_text(encoding="utf-8")
        i = src.index("real-time-state 拉取失败")
        assert "_fail_if_credential(_err)" in src[max(0, i - 400):i + 200]

    def test_init_enables_for_m_series(self):
        src = INIT.read_text(encoding="utf-8")
        assert "from .m01_state import is_m_series" in src
        assert "coordinator.enable_realtime_state(True)" in src

    def test_endpoint_matches_reverse_engineering(self):
        """★ 端点必须与 App 的 NetApiConst.GET_VEHICLE_STATE 一致。"""
        src = (CC / "li_api.py").read_text(encoding="utf-8")
        assert "/ssp-as-mobile-api/v3-0/vehicles/{self._vin}/real-time-state" in src
