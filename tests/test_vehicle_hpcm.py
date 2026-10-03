"""整车配置表（Vehicle.HU.Diag.Hpcm）测试 —— 2026-09-27 新增

★ 来源：App 的 LXLiMeshStateDelegate.getHmiPlatform()
    raw = cache.getString(vin, "Vehicle.HU.Diag.Hpcm")
    map = fromJson(raw, Map<String,String>)
    hmiPlatform = map.get("hmi_platform") ?: "0"

★★ 关键：App 的 SS3/SS4 判定就是 `hmi_platform == "1"`
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"

# 实测数据（我们的 L6 Pro）
L6_PRO = {
    "eea": "2.0", "hmi_platform": "6", "hc_frunk": "0", "soft_close_frunk": "1",
    "hc_car_refrigeratory": "0", "hc_rear_seat_ven": "1",
    "hc_rear_seat_ven_layout": "2", "rear_steering": "1",
    "fragrance_system": "1", "hc_hud_size": "3", "hc_multi_zone_ac": "1",
    "hc_rear_ac_panel": "1", "hc_touchbar": "1", "hc_co2_sensor": "1",
    "hc_psd": "0", "hc_automatic_door": "0", "hc_lidar": "0",
    "hc_year": "24", "sales_cnr": "15",
}
# 假想的 L9（六座，有滑门/冰箱/后排屏）
L9 = {
    "eea": "3.0", "hmi_platform": "1", "hc_frunk": "1", "soft_close_frunk": "1",
    "hc_car_refrigeratory": "1", "hc_rear_display_screen": "1",
    "hc_psd": "1", "hc_automatic_door": "1", "hc_empress_seat": "1",
    "hc_rear_seat_ven": "1", "hc_year": "25",
}


def _load():
    """加载 vehicle_hpcm 模块（隔离 HA 依赖）。"""
    src = (_INTEG / "vehicle_hpcm.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", 'LOGGER_NAME = "t"')
    mod = types.ModuleType("hpcm_test")
    exec(compile(src, "vehicle_hpcm.py", "exec"), mod.__dict__)
    return mod


vc = _load()


class TestParse:
    def test_parse_dict(self):
        h = vc.parse_hpcm_value(L6_PRO)
        assert h.available
        assert h.hmi_platform == "6"

    def test_parse_json_string(self):
        h = vc.parse_hpcm_value(json.dumps(L6_PRO))
        assert h.available
        assert h.get("hc_frunk") == "0"

    def test_parse_none(self):
        h = vc.parse_hpcm_value(None)
        assert not h.available
        assert h.hmi_platform == "0"

    def test_parse_bad_json(self):
        h = vc.parse_hpcm_value("{not json")
        assert not h.available

    def test_parse_empty_string(self):
        assert not vc.parse_hpcm_value("").available

    def test_parse_list_is_invalid(self):
        assert not vc.parse_hpcm_value("[1,2]").available


class TestSS4Detection:
    """★★ 核心：SS3/SS4 判定。"""

    def test_l6_is_ss3(self):
        """我们的 L6 Pro：hmi_platform=6 → SS3。"""
        h = vc.parse_hpcm_value(L6_PRO)
        assert not h.is_ss4()
        assert h.hmi_platform == "6"

    def test_l9_is_ss4(self):
        """假想 L9：hmi_platform=1 → SS4。"""
        h = vc.parse_hpcm_value(L9)
        assert h.is_ss4()

    def test_zero_is_ss3(self):
        h = vc.parse_hpcm_value({"hmi_platform": "0"})
        assert not h.is_ss4()

    def test_missing_defaults_ss3(self):
        """没有字段 → 默认 "0" → SS3（保守）。"""
        h = vc.parse_hpcm_value({"other": "1"})
        assert h.hmi_platform == "0"
        assert not h.is_ss4()

    def test_only_exactly_1_is_ss4(self):
        """★ 精确比较：必须是字符串 "1"，"10" 不算。"""
        assert not vc.parse_hpcm_value({"hmi_platform": "10"}).is_ss4()
        assert not vc.parse_hpcm_value({"hmi_platform": "01"}).is_ss4()
        assert vc.parse_hpcm_value({"hmi_platform": "1"}).is_ss4()


class TestFeatureDetection:
    def test_l6_features(self):
        h = vc.parse_hpcm_value(L6_PRO)
        # ✅ 有
        assert h.has("soft_close_frunk")
        assert h.has("hc_rear_seat_ven")
        assert h.has("rear_steering")
        assert h.has("fragrance_system")
        # ❌ 无
        assert not h.has("hc_frunk")
        assert not h.has("hc_car_refrigeratory")
        assert not h.has("hc_psd")
        assert not h.has("hc_lidar")

    def test_l9_features(self):
        h = vc.parse_hpcm_value(L9)
        assert h.has("hc_frunk")
        assert h.has("hc_car_refrigeratory")
        assert h.has("hc_rear_display_screen")
        assert h.has("hc_psd")
        assert h.has("hc_empress_seat")

    def test_unavailable_returns_false(self):
        """★ 未解析到 → 一律 False（保守，不误报）。"""
        h = vc.parse_hpcm_value(None)
        for f in ("hc_frunk", "hc_psd", "hc_car_refrigeratory"):
            assert not h.has(f)

    def test_supported_features_list(self):
        h = vc.parse_hpcm_value(L6_PRO)
        names = h.supported_features()
        assert "电吸前备箱" in names
        assert "后轮转向" in names
        assert "前备箱" not in names  # hc_frunk=0

    def test_unsupported_lists_only_present_fields(self):
        h = vc.parse_hpcm_value(L6_PRO)
        unsup = h.unsupported_features()
        assert "前备箱" in unsup      # 字段存在且为 0
        assert "滑门" not in unsup    # 字段名不对

    def test_value_of_by_chinese_name(self):
        h = vc.parse_hpcm_value(L6_PRO)
        assert h.value_of("前备箱") == "0"
        assert h.value_of("电吸前备箱") == "1"

    def test_empty_string_is_false(self):
        h = vc.parse_hpcm_value({"hc_frunk": ""})
        assert not h.has("hc_frunk")


class TestHelperFields:
    def test_eea(self):
        assert vc.parse_hpcm_value(L6_PRO).eea == "2.0"

    def test_car_of_year(self):
        assert vc.parse_hpcm_value(L6_PRO).car_of_year == "24"

    def test_raw_copy(self):
        h = vc.parse_hpcm_value(L6_PRO)
        raw = h.raw
        raw["hacked"] = 1
        assert not h.has("hacked")  # 副本，不影响内部


class TestGetFromCoordinator:
    def test_from_vss_hu_diag(self):
        coord = types.SimpleNamespace(data={
            "vss": {"hu_diag": {"value": json.dumps(L6_PRO), "ts": "x"}}
        })
        h = vc.get_hpcm(coord)
        assert h.available
        assert h.hmi_platform == "6"

    def test_from_vss_path(self):
        coord = types.SimpleNamespace(data={
            "vss": {"Vehicle.HU.Diag.Hpcm": {"value": json.dumps(L9)}}
        })
        assert vc.get_hpcm(coord).is_ss4()

    def test_missing(self):
        coord = types.SimpleNamespace(data={"vss": {}})
        assert not vc.get_hpcm(coord).available

    def test_bad_coordinator(self):
        assert not vc.get_hpcm(object()).available
        assert not vc.get_hpcm(None).available


class TestDump:
    def test_dump_shape(self):
        h = vc.parse_hpcm_value(L6_PRO)
        d = h.dump()
        assert d["hmi_platform"] == "6"
        assert d["is_ss4"] is False
        assert d["eea"] == "2.0"
        assert isinstance(d["supported"], list)
        assert "raw" in d


class TestFeatureFieldTable:
    """★ 字段表本身的守卫。"""

    def test_has_frunk_field(self):
        assert "hc_frunk" in vc.FEATURE_FIELDS

    def test_has_psd_field(self):
        assert "hc_psd" in vc.FEATURE_FIELDS

    def test_no_duplicate_names(self):
        names = list(vc.FEATURE_FIELDS.values())
        assert len(names) == len(set(names)), "功能中文名有重复"

    def test_hpcm_path_matches_app(self):
        assert vc.HPCM_PATH == "Vehicle.HU.Diag.Hpcm"


class TestFrunkLogicGuard:
    """★ 守卫：前备箱判定只能看 hc_frunk（不看 soft_close_frunk）。"""

    @staticmethod
    def _cover_src() -> str:
        return (_INTEG / "cover.py").read_text(encoding="utf-8")

    def test_frunk_uses_hc_frunk(self):
        s = self._cover_src()
        i = s.find("frunk_ok")
        blk = s[i:i + 1200]
        assert 'hpcm.has("hc_frunk")' in blk

    def test_soft_close_frunk_not_the_gate(self):
        """⚠️ L6 Pro: hc_frunk=0 但 soft_close_frunk=1 —— 不能误判。"""
        s = self._cover_src()
        i = s.find("if hpcm.available:")
        blk = s[i:i + 900]
        # soft_close_frunk 只应出现在注释里，不应出现在 has() 调用里
        assert 'hpcm.has("soft_close_frunk")' not in blk

    def test_l6_has_no_frunk(self):
        """实测数据：L6 Pro 无前备箱。"""
        h = vc.parse_hpcm_value(L6_PRO)
        assert not h.has("hc_frunk")
        assert h.has("soft_close_frunk")  # 电吸字段为 1（陷阱）


class TestAuthorityShortCircuit:
    """★★ 守卫：Hpcm 的否定结论必须【短路】，不能被兜底覆盖。

    ⚠️ 曾经踩的坑：L6 的 hc_frunk="0"（无前备箱），
       但 VSS 里有 DoorLockStatus.FrontTrunkDoor（全车型都有）
       → 兜底逻辑把 frunk_ok 改回 True → 错误创建实体。
    """

    @staticmethod
    def _cover_src() -> str:
        return (_INTEG / "cover.py").read_text(encoding="utf-8")

    def test_has_decided_flag(self):
        s = self._cover_src()
        assert "frunk_decided" in s, "缺少权威短路标志"

    def test_decided_set_after_hpcm(self):
        s = self._cover_src()
        i = s.find('"hc_frunk" in hpcm.raw')
        assert i > 0
        blk = s[i:i + 400]
        assert "frunk_decided = True" in blk, "Hpcm 判定后必须设短路标志"

    def test_fallback_guarded_by_decided(self):
        s = self._cover_src()
        # 兜底必须包在 `if not frunk_decided:` 里
        i = s.find("if not frunk_decided:")
        assert i > 0, "兜底未被短路保护"

    def test_no_doorkey_fallback(self):
        """⚠️ 不能用 DoorLockStatus.FrontTrunkDoor（全车型都有，会误判）。"""
        s = self._cover_src()
        i = s.find("VSS 兜底判定前备箱")
        assert i > 0
        blk = s[i:i + 400]
        assert "DoorLockStatus.FrontTrunkDoor" not in blk, \
            "不能用通用锁信号兜底（L6 也有，会误判）"

    def test_hpcm_absent_field_does_not_decide(self):
        """Hpcm 没有 hc_frunk 字段时不应短路（让兜底生效）。"""
        h = vc.parse_hpcm_value({"hmi_platform": "6"})
        assert h.available
        assert "hc_frunk" not in h.raw
