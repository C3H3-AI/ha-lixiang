"""M 系（理想ONE）车控命令构造 —— 依据 a0.smali 的 a()~k() 逐方法反汇编。

★★ 为什么需要这个模块 ★★
M 系的 AC 家族与 X 系是**两套协议**：
  X 系：cmdKey 固定 remoteVehACSmartControl，
        cmdData = {acCtrlType, acCtrlValue, acCtrlTemp}
  M 系：**换 commandKey**（remote_fl_seat_heat_adjust / remote_sw_heat_on /
        remote_ai_temp_ctrl_off …）+ cmdData 用 {Type:"编号", Temp:"21.5"} 或
        {FLLevel:"2", FLLevelFeedBack:"1"}
若直接把 X 系 cmdData 发过去，服务端不认识这些字段 ⇒ 车控失败。
"""

from __future__ import annotations

from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "m01_control", MOD / "m01_control.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load()


class TestLevelParsing:
    def test_off_is_zero(self):
        assert mc.parse_level("OFF") == 0
        assert mc.parse_level("") == 0
        assert mc.parse_level(None) == 0

    def test_level_strings(self):
        assert mc.parse_level("LEVEL1") == 1
        assert mc.parse_level("LEVEL3") == 3

    def test_numbers(self):
        assert mc.parse_level(2) == 2
        assert mc.parse_level("2") == 2
        assert mc.parse_level(2.0) == 2

    def test_clamped(self):
        assert mc.parse_level(99) == 6
        assert mc.parse_level(-5) == 0


class TestSeatMapping:
    """座椅四角：Type = 基号 + 档位（基号 FL=3 / FR=7 / RL=11 / RR=15）。"""

    @pytest.mark.parametrize("corner,base", [
        ("fl", 3), ("fr", 7), ("rl", 11), ("rr", 15)])
    def test_levels_map_to_base_plus_level(self, corner, base):
        for level in (1, 2, 3):
            key, data = mc.build_seat(corner, level, ac_on=True)
            assert key == "remote_ac_ctrl_new"
            assert data["Type"] == str(base + level)

    @pytest.mark.parametrize("corner,field", [
        ("fl", "FLLevel"), ("fr", "FRLevel"),
        ("rl", "RLLevel"), ("rr", "RRLevel")])
    def test_ac_off_uses_dedicated_key(self, corner, field):
        """空调未开 → 走专用座椅键，且 FLLevel = 档位+1（官方实现）。"""
        key, data = mc.build_seat(corner, 2, ac_on=False)
        assert key == f"remote_{corner}_seat_heat_adjust"
        assert data[field] == "3"                    # 档位 2 → Level 3
        assert data[field + "FeedBack"] == "2"       # 回显原档位

    @pytest.mark.parametrize("corner", ["fl", "fr", "rl", "rr"])
    def test_off_always_uses_dedicated_key(self, corner):
        """★ 关闭一律走专用键 —— 不依赖空调状态（四座都成立）。"""
        for ac_on in (True, False, None):
            key, data = mc.build_seat(corner, 0, ac_on=ac_on)
            assert key == f"remote_{corner}_seat_heat_adjust"
            assert data[f"remote_{corner}_seat_heat_adjust" and
                        [k for k in data if k.endswith("Level")][0]] == "1"

    def test_vent_level_6_uses_vent_type(self):
        """档位 6（通风档）前两座有专门编号：FL=25 / FR=27。"""
        assert mc.build_seat("fl", 6, ac_on=True)[1]["Type"] == "25"
        assert mc.build_seat("fr", 6, ac_on=True)[1]["Type"] == "27"

    def test_temp_only_when_ac_on(self):
        _, data = mc.build_seat("fl", 2, ac_on=True, temp=21.5)
        assert data["Temp"] == "21.5"


class TestWheelHeat:
    def test_ac_on_uses_type_code(self):
        key, data = mc.build_wheel_heat(on=True, ac_on=True)
        assert key == "remote_ac_ctrl_new"
        assert data["Type"] == "1"
        key, data = mc.build_wheel_heat(on=False, ac_on=True)
        assert data["Type"] == "2"

    def test_ac_off_uses_dedicated_key(self):
        key, data = mc.build_wheel_heat(on=True, ac_on=False)
        assert key == "remote_sw_heat_on"
        assert data["SteerSet"] == "1"
        # SteerSet 本就在 9 字段模板里，这里是覆盖而非新增 ⇒ 仍是 9 个
        assert len(data) == 9
        assert set(data) == set(mc.AC_LEVELS_DEFAULT)

    def test_off_key(self):
        assert mc.build_wheel_heat(on=False, ac_on=False)[0] == "remote_sw_heat_off"


class TestAcSwitch:
    def test_on_normal(self):
        key, data = mc.build_ac_switch(on=True, temp=22.0)
        assert key == "remote_ac_ctrl_new"
        assert data["Type"] == "19"
        assert data["Temp"] == "22"

    def test_on_auto(self):
        assert mc.build_ac_switch(on=True, auto=True)[1]["Type"] == "20"

    def test_off(self):
        key, data = mc.build_ac_switch(on=False)
        assert key == "remote_ai_temp_ctrl_off"
        assert data == {}


class TestAcTemp:
    def test_ac_on_adjusts(self):
        key, data = mc.build_ac_temp(21.5, ac_on=True)
        assert key == "remote_ac_ctrl_new"
        assert data == {"Type": "21", "Temp": "21.5"}

    def test_ac_off_turns_on_with_levels(self):
        key, data = mc.build_ac_temp(21.5, ac_on=False)
        assert key == "remote_ai_temp_ctrl_ex_on"
        assert data["Temp"] == "21.5"
        assert "FLLevel" in data, "开机要带 a0.j() 的 9 字段"

    def test_no_temp_returns_empty_string(self):
        _, data = mc.build_ac_temp(None, ac_on=True)
        assert data["Temp"] == ""


class TestTranslate:
    """X 系 cmdData → M 系 (commandKey, cmdData)。"""

    def test_unknown_returns_none(self):
        assert mc.translate({"foo": "bar"}, ac_on=True) is None
        assert mc.translate(None, ac_on=True) is None
        assert mc.translate({}, ac_on=True) is None

    @pytest.mark.parametrize("ctype,corner", [
        ("flSeatHeatSw", "fl"), ("flSeatVentSw", "fl"),
        ("frSeatHeatSw", "fr"), ("rlSeatVentSw", "rl"),
        ("rrSeatSw", "rr")])
    def test_seat_types_routed(self, ctype, corner):
        key, _ = mc.translate(
            {"acCtrlType": ctype, "acCtrlValue": "LEVEL1"}, ac_on=False)
        assert key == f"remote_{corner}_seat_heat_adjust"

    def test_wheel_heat_routed(self):
        key, _ = mc.translate(
            {"acCtrlType": "strgWhlHeatSw", "acCtrlValue": "ON"}, ac_on=False)
        assert key == "remote_sw_heat_on"

    def test_ac_switch_routed(self):
        key, _ = mc.translate(
            {"acCtrlType": "frtACSw", "acCtrlValue": "OFF"}, ac_on=True)
        assert key == "remote_ai_temp_ctrl_off"

    def test_rapid_modes(self):
        assert mc.translate(
            {"acCtrlType": "acHeatFast", "acCtrlValue": "ON"},
            ac_on=True)[1]["Type"] == "23"
        assert mc.translate(
            {"acCtrlType": "acCoolFast", "acCtrlValue": "ON"},
            ac_on=True)[1]["Type"] == "22"


class TestAllValuesAreStrings:
    """★ M 系 cmdData 的值【全部是字符串】（官方用 String.valueOf）★

    发数字类型可能被服务端判非法 —— 这条是防回归的关键。
    """

    def test_seat_values_are_str(self):
        for ac_on in (True, False, None):
            _, data = mc.build_seat("fl", 2, ac_on=ac_on, temp=21.5)
            for k, v in data.items():
                assert isinstance(v, str), f"{k} 应是字符串，实际 {type(v)}"

    def test_wheel_values_are_str(self):
        _, data = mc.build_wheel_heat(on=True, ac_on=False)
        for k, v in data.items():
            assert isinstance(v, str)

    def test_ac_values_are_str(self):
        for key, data in (mc.build_ac_switch(on=True, temp=22.0),
                          mc.build_ac_temp(21.5, ac_on=True),
                          mc.build_rapid(heat=True)):
            for k, v in data.items():
                assert isinstance(v, str), f"{k} 应是字符串"


class TestOfficialLevelsTemplate:
    def test_template_has_nine_fields(self):
        """a0.j() 的模板是 9 个字段（4 座 × 2 + SteerSet）。"""
        assert len(mc.AC_LEVELS_DEFAULT) == 9
        for k in ("FLLevel", "FLLevelFeedBack", "FRLevel", "FRLevelFeedBack",
                  "RLLevel", "RLLevelFeedBack", "RRLevel", "RRLevelFeedBack",
                  "SteerSet"):
            assert k in mc.AC_LEVELS_DEFAULT

    def test_template_values_are_official(self):
        """官方 j()：Level="1"、FeedBack="0"、SteerSet="0"。"""
        for k, v in mc.AC_LEVELS_DEFAULT.items():
            if k == "SteerSet":
                assert v == "0"
            elif k.endswith("FeedBack"):
                assert v == "0"
            else:
                assert v == "1"


class TestWiring:
    def test_li_api_calls_translate(self):
        src = (MOD / "li_api.py").read_text(encoding="utf-8")
        assert "m01_control" in src, "li_api 未接入 M 系 AC 翻译"
        assert "_m01_ac_is_on" in src, "缺空调状态判断（官方按空调状态选 commandKey）"

    def test_ac_state_reads_offstatus(self):
        """★ acOffStatus 是「关」状态 ⇒ 0 表示没关（即开着），必须取反。"""
        src = (MOD / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def _m01_ac_is_on")
        body = src[i:i + 1200]
        assert "acOffStatus" in body
        assert "== 0" in body, "OffStatus=0 表示空调开着（取反）"


class TestOfficialCommandKeyMap:
    """★ 官方 commandKeyMap（VehicleControlModel.smali，19 条）必须原样保留。

    这是 M 系「能力名 → 实际 commandKey」的权威映射。数字键（50.0/55.0/…）
    说明服务端确实接受数字字符串当 commandKey —— 这是 M 系老协议特色。
    """

    def test_map_has_nineteen_entries(self):
        assert len(mc.OFFICIAL_COMMAND_KEY_MAP) == 19

    def test_named_keys(self):
        m = mc.OFFICIAL_COMMAND_KEY_MAP
        assert m["LXVehicleControlTypeDoorlock"] == "remote_central_lock_lock"
        assert m["LXVehicleControlTypeDoorUnlock"] == "remote_central_lock_unlock"
        assert m["LXVehicleControlTypeOpenWindow"] == "remote_window_open"
        assert m["LXVehicleControlTypeOpenTrunk"] == "remote_plg_open"
        assert m["LXVehicleControlTypeLocation"] == "remote_veh_search"
        assert m["LXVehicleControlTypeOpenAC"] == "remote_ac_ctrl_new"
        assert m["LXVehicleControlTypeStartCharging"] == "remote_charging_start"

    def test_numeric_keys_present(self):
        m = mc.OFFICIAL_COMMAND_KEY_MAP
        assert m["LXVehicleControlTypeStartPhoto"] == "50.0"
        assert m["LXVehicleControlTypeSentry"] == "55.0"
        assert m["LXVehicleControlTypeWakeUp"] == "60.0"
        assert m["LXVehicleControlTypeChargingTarget"] == "101.0"

    def test_numeric_keys_not_activated(self):
        """★ 数字键的 cmdData 无证据 ⇒ 不得出现在可下发路径里。"""
        assert set(mc.NUMERIC_COMMAND_KEYS) == {
            "50.0", "55.0", "60.0", "100.0", "101.0", "102.0", "103.0", "104.0"}
        # build_* / translate 不应产出数字键
        for ac_on in (True, False, None):
            for fn in (lambda: mc.build_seat("fl", 2, ac_on=ac_on),
                       lambda: mc.build_wheel_heat(on=True, ac_on=ac_on),
                       lambda: mc.build_ac_switch(on=True, temp=22.0),
                       lambda: mc.build_ac_temp(21.0, ac_on=ac_on)):
                key, _ = fn()
                assert key not in mc.NUMERIC_COMMAND_KEYS, (
                    f"{key} 是数字键，但其 cmdData 尚无证据，不应下发")


class TestSettingCommandParams:
    """M 系「设置类」命令的参数体系（MSubKeyConst / MParamsConst 实证）。

    官方构造（VehicleControlDockingDelegate.smali）：
        cmdData = LinkedHashMap{"sub_key": "MinusScreen"}
    """

    def test_param_names(self):
        assert mc.SUB_KEY_PARAM == "sub_key"
        assert mc.INTERVAL_TIME_PARAM == "interval_time"

    def test_sub_keys_match_official(self):
        """sub_key 取值必须与 MSubKeyConst 完全一致。"""
        assert set(mc.SUB_KEYS.values()) == {
            "photo", "charge", "OTA", "Healthy", "Maintain", "MinusScreen",
            "AcAppointment"}

    def test_numeric_capabilities_mostly_have_dedicated_endpoints(self):
        """★ 数字键 8 条里 7 条已有专用端点（更可靠）⇒ 不必猜 cmdData。"""
        src = (MOD / "li_api.py").read_text(encoding="utf-8")
        for ep in ("EP_SVM_TAKE_PHOTO", "EP_WAKEUP", "EP_BATTERY_WARM",
                   "EP_CHARGE_THRESHOLD", "EP_CHARGE_APPOINTMENT",
                   "EP_AC_APPOINTMENT", "EP_OTA_UPGRADE"):
            assert ep in src, f"{ep} 缺失（数字键能力的专用端点）"

    def test_sentry_not_activated(self):
        """哨兵（55.0）cmdData 无证据 ⇒ 不得出现在可下发路径。"""
        assert mc.SENTRY_COMMAND_KEY == "55.0"
        for ac_on in (True, False, None):
            for fn in (lambda: mc.build_seat("fl", 1, ac_on=ac_on),
                       lambda: mc.build_wheel_heat(on=True, ac_on=ac_on),
                       lambda: mc.build_ac_switch(on=True, temp=22.0)):
                key, _ = fn()
                assert key != mc.SENTRY_COMMAND_KEY


class TestSentryCoverage:
    """★ 哨兵模式补齐（M 系）。

    · X 系：cmdKey = `sentinelModeSetting`
    · M 系：官方 commandKeyMap → **"55.0"**（数字字符串）
    · payload：沿用同构的 {"sentinelSwitch": 0/1, "timestap": 毫秒}
      ⚠️ `timestap` 是 App 的拼写（少一个 m），必须照抄
      ★ payload 属于「同应用同概念」推论，非直接静态实证 —— 已在源码注释标明
    """

    def test_li_api_maps_sentry_to_numeric_key(self):
        src = (MOD / "li_api.py").read_text(encoding="utf-8")
        assert '"sentinelModeSetting": "55.0"' in src, (
            "M 系哨兵 cmdKey 应为 55.0（官方 commandKeyMap）")

    def test_sentry_payload_not_stripped(self):
        """哨兵需要带 cmdData ⇒ 必须在白名单里，否则会被清空。"""
        src = (MOD / "li_api.py").read_text(encoding="utf-8")
        i = src.find("_M01_CMDDATA_KEYS")
        j = src.find(")", i)
        assert '"55.0"' in src[i:j], "哨兵须在 cmdData 白名单（否则参数被清空）"

    def test_sentry_key_is_in_official_map(self):
        """交叉校验：官方表里 Sentry 确实是 55.0。"""
        assert mc.OFFICIAL_COMMAND_KEY_MAP.get(
            "LXVehicleControlTypeSentry") == "55.0"
