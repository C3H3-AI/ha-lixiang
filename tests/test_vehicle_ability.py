"""车型能力表测试（vehicle_ability.py）—— 2026-09-26 新增

背景：从「手工硬编码 KNOWN_FEATURES」改为「读 APK 内置的车型配置 JSON」，
      完全复刻 App 的 VehicleDetails 机制。

数据：68 个车型 JSON（从官方 APK 8.27.0 的 assets/{modelId}.json 提取）
关键：值语义 —— 1 = 无硬件；>=2 = 有硬件
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
_CONFIG_DIR = _INTEG / "vehicle_configs"


def _load_module():
    """加载 vehicle_ability.py（绕过 HA 依赖）。"""
    import types
    src = (_INTEG / "vehicle_ability.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace(
        '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
        f'_CONFIG_DIR = Path({str(_CONFIG_DIR)!r})')
    mod = types.ModuleType("va_test")
    exec(compile(src, "vehicle_ability.py", "exec"), mod.__dict__)
    return mod


va = _load_module()

# 实测样本（modelId 来自 get_vehicles()）
L6_PRO = "100167931652606785"
L8_AIR = "100165028254293339"
L9_MAX = "100174236664108736"
M01B = "100204301435085761"


class TestDataSource:
    """数据文件本身。"""

    def test_config_dir_exists(self):
        assert _CONFIG_DIR.is_dir(), "vehicle_configs 目录缺失"

    def test_has_68_models(self):
        """从 APK 提取的车型数。"""
        jsons = [f for f in _CONFIG_DIR.glob("*.json") if not f.name.startswith("_")]
        assert len(jsons) >= 60, f"车型数偏少: {len(jsons)}"

    def test_index_exists(self):
        idx = va.load_model_index()
        assert len(idx) >= 60
        assert L6_PRO in idx

    def test_names_exist(self):
        names = va.load_ability_names()
        assert len(names) >= 30
        assert names.get("strgWhlHeatSw"), "方向盘加热名称缺失"


class TestLoadConfig:
    def test_load_known(self):
        cfg = va.load_vehicle_config(L6_PRO)
        assert cfg is not None
        assert cfg["desc"] == "L6Pro"

    def test_load_unknown(self):
        assert va.load_vehicle_config("999999999999999999") is None

    def test_reject_non_digit(self):
        """防路径穿越。"""
        assert va.load_vehicle_config("../../etc/passwd") is None
        assert va.load_vehicle_config("abc") is None

    def test_load_empty(self):
        assert va.load_vehicle_config("") is None
        assert va.load_vehicle_config(None) is None


class TestAbilityLevel:
    """等价 App 的 getAbilityLeven。"""

    def test_l6_pro_seats(self):
        ab = va.VehicleAbility(L6_PRO)
        # 五座车：主/副驾 + 二排左中右
        assert ab.ability_level("flSeatSw") >= 2
        assert ab.ability_level("frSeatSw") >= 2
        assert ab.ability_level("secLSeatSw") >= 2
        assert ab.ability_level("secMSeatSw") >= 2
        assert ab.ability_level("secRSeatSw") >= 2
        # 无三排
        assert ab.ability_level("thirdLSeatSw") == 1
        assert ab.ability_level("thirdRSeatSw") == 1

    def test_has_semantics(self):
        """has() 等价于 level >= 2。"""
        ab = va.VehicleAbility(L6_PRO)
        assert ab.has("secMSeatSw") is True
        assert ab.has("thirdLSeatSw") is False

    def test_unknown_tag_defaults_to_2(self):
        """App 对未知 tag 返回 2（与 JS 一致）。"""
        ab = va.VehicleAbility(L6_PRO)
        assert ab.ability_level("nonexistentTag") == va.DEFAULT_ABILITY_LEVEL

    def test_no_config_returns_default(self):
        ab = va.VehicleAbility("999999999999999999")
        assert ab.available is False


class TestVehicleSeat:
    """等价 App 的 vehicleSeat()。"""

    def test_l6_is_five_seats(self):
        assert va.VehicleAbility(L6_PRO).vehicle_seat() == 5
        assert va.VehicleAbility(L6_PRO).seat_layout() == "五座"

    def test_l8_is_six_seats(self):
        assert va.VehicleAbility(L8_AIR).vehicle_seat() == 6
        assert va.VehicleAbility(L8_AIR).seat_layout() == "六座"

    def test_l9_is_six_seats(self):
        assert va.VehicleAbility(L9_MAX).vehicle_seat() == 6


class TestIsSupported:
    """等价 App 的 isSupportCheck。"""

    def test_depart_on_time_supported(self):
        """按时出发：68 个车型全支持。"""
        for mid in (L6_PRO, L8_AIR, L9_MAX):
            assert va.VehicleAbility(mid).is_supported("departOnTime"), mid

    def test_fridge_not_on_l6(self):
        """L6 无冰箱（isSupport=false）。"""
        assert va.VehicleAbility(L6_PRO).is_supported("fridge") is False

    def test_fridge_on_l9(self):
        """L9 有冰箱。"""
        assert va.VehicleAbility(L9_MAX).is_supported("fridge") is True

    def test_unknown_tag_not_supported(self):
        assert va.VehicleAbility(L6_PRO).is_supported("nonexistent") is False

    def test_sentry_supported(self):
        assert va.VehicleAbility(L6_PRO).is_supported("sentry") is True


class TestCompareVersions:
    def test_basic(self):
        assert va.compare_versions("8.0.0", "7.0.0") == 1
        assert va.compare_versions("7.0.0", "8.0.0") == -1
        assert va.compare_versions("7.0.0", "7.0.0") == 0

    def test_different_length(self):
        assert va.compare_versions("7.1", "7.1.0") == 0
        assert va.compare_versions("7.2", "7.1.9") == 1

    def test_suffix(self):
        assert va.compare_versions("8.0.0-beta", "8.0.0") == 0

    def test_empty(self):
        assert va.compare_versions("", "") == 0


class TestThirdRowGeneration:
    """★ 核心：三排座椅实体的自动生成（解决 L8/L9）。"""

    THIRD_TAGS = ("thirdLSeatSw", "thirdMSeatHeatSw", "thirdRSeatSw")

    def test_l6_has_no_third_row(self):
        ab = va.VehicleAbility(L6_PRO)
        n = sum(1 for t in self.THIRD_TAGS if ab.has(t))
        assert n == 0, f"L6 不该有三排实体，实际 {n} 个"

    def test_l8_has_third_row(self):
        ab = va.VehicleAbility(L8_AIR)
        assert ab.has("thirdLSeatSw"), "L8 应有三排左"
        assert ab.has("thirdRSeatSw"), "L8 应有三排右"
        n = sum(1 for t in self.THIRD_TAGS if ab.has(t))
        assert n >= 2, f"L8 三排实体数偏少: {n}"

    def test_l9_has_third_row(self):
        ab = va.VehicleAbility(L9_MAX)
        assert ab.has("thirdLSeatSw")
        assert ab.has("thirdRSeatSw")

    def test_m01b_no_third_row(self):
        """M01B 是 6 座但无三排（第三排 value=1）。"""
        ab = va.VehicleAbility(M01B)
        assert not ab.has("thirdLSeatSw"), "M01B 不该有三排"


class TestSecondRowMiddle:
    """二排中座椅（L6/L7 有，L8/L9 无）。"""

    def test_l6_has_middle(self):
        assert va.VehicleAbility(L6_PRO).has("secMSeatSw")

    def test_l8_no_middle(self):
        assert not va.VehicleAbility(L8_AIR).has("secMSeatSw")


class TestDump:
    def test_dump_structure(self):
        d = va.VehicleAbility(L6_PRO).dump()
        assert d["desc"] == "L6Pro"
        assert d["available"] is True
        assert d["seat_layout"] == "五座"
        assert "seat_abilities" in d
        assert "features_supported" in d

    def test_dump_unavailable(self):
        d = va.VehicleAbility("999999999999999999").dump()
        assert d["available"] is False


class TestNameLookup:
    def test_name_of_known(self):
        ab = va.VehicleAbility(L6_PRO)
        assert ab.name_of("strgWhlHeatSw") == "方向盘加热"
        assert ab.name_of("departOnTime") == "按时出发"

    def test_name_of_unknown(self):
        """未知 tag 返回 tag 本身（不崩）。"""
        ab = va.VehicleAbility(L6_PRO)
        assert ab.name_of("brandNewTag") == "brandNewTag"


class TestListModels:
    def test_list_returns_models(self):
        models = va.list_known_models()
        assert len(models) >= 60
        assert all("modelId" in m for m in models)


class TestDumpServiceContract:
    """诊断服务 dump_ability 的约定（2026-09-26 新增）。"""

    @staticmethod
    def _src(name: str) -> str:
        return (_INTEG / name).read_text(encoding="utf-8")

    def test_service_constant_defined(self):
        s = self._src("__init__.py")
        assert 'SERVICE_DUMP_ABILITY = "dump_ability"' in s

    def test_service_registered(self):
        s = self._src("__init__.py")
        assert "async_register(DOMAIN, SERVICE_DUMP_ABILITY" in s

    def test_service_in_cleanup(self):
        """卸载时要一并移除。"""
        s = self._src("__init__.py")
        m = [ln for ln in s.split("\n") if "for svc in (SERVICE_REFRESH" in ln]
        assert m, "未找到服务清理列表"
        assert "SERVICE_DUMP_ABILITY" in m[0]

    def test_services_yaml_has_entry(self):
        s = self._src("services.yaml")
        assert "dump_ability:" in s
        assert "导出车型能力表" in s

    def test_dump_writes_json(self):
        """handler 要把 dump() 结果写成 JSON。"""
        s = self._src("__init__.py")
        assert "lixiang_ability_" in s
        assert "ab.dump()" in s

    def test_dump_includes_detected_features(self):
        """导出内容要含 features（便于排查实体缺失）。"""
        s = self._src("__init__.py")
        assert 'dump["features_detected"] = feats' in s


class TestAppNames:
    """实体名对齐 App（2026-09-26 新增）。"""

    def test_names_file_exists(self):
        assert (_CONFIG_DIR / "_names_app.json").is_file()

    def test_app_name_lookup(self):
        """名字应来自 App（如「车锁」而非我们自造的「车门锁」）。"""
        assert va.app_name("lock") == "车锁"
        assert va.app_name("window") == "车窗"
        assert va.app_name("door_trunk") == "尾门"
        assert va.app_name("driving_auth") == "授权驾驶"
        assert va.app_name("find_car") == "寻车"

    def test_app_name_english(self):
        assert va.app_name("lock", "en") == "Lock"
        assert va.app_name("window", "en") == "Windows"
        assert va.app_name("door_trunk", "en") == "Tailgate"

    def test_app_name_fallback(self):
        """未知 key 返回 default 或 key 本身（不崩）。"""
        assert va.app_name("nonexistent", default="X") == "X"
        assert va.app_name("nonexistent") == "nonexistent"

    def test_seat_names_present(self):
        for k in ("seat_fl_heat", "seat_sm_heat", "seat_tl_heat", "seat_tr_heat"):
            v = va.app_name(k)
            assert v and v != k, f"{k} 缺名字"

    def test_fast_cool_hot_match_app(self):
        """App 用「快速制冷/制热」（res/values strings fast_cold/fast_hot）。"""
        assert va.app_name("fast_cool") == "快速制冷"
        assert va.app_name("fast_hot") == "快速制热"
        assert va.app_name("deicing") == "除雪除冰"

    def test_all_entries_have_source(self):
        """每条都要标明来源（可追溯）。"""
        raw = json.loads((_CONFIG_DIR / "_names_app.json").read_text(encoding="utf-8"))
        for k, v in raw.items():
            if k.startswith("_"):
                continue
            assert v.get("source"), f"{k} 缺 source"
            assert v.get("zh"), f"{k} 缺 zh"

    def test_lock_py_uses_app_name(self):
        """lock.py 应从 app_name 取名（而不是硬编码）。"""
        s = (_INTEG / "lock.py").read_text(encoding="utf-8")
        assert 'app_name("lock"' in s
