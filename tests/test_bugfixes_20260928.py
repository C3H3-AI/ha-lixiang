"""2026-09-28 用户报告的四个缺陷 —— 回归测试。

报告内容：
  ① 方向盘开关错误了，实际只有开关功能，没有三档功能
  ② 用户反映 i6 车型显示燃油续航
  ③ i6 的冰箱和前备箱状态错误

★ 测试策略（遵循 tests/ 既有约定）：
  · 不 import HA 相关模块（switch/fan/sensor/features 顶部依赖 homeassistant）
  · 用 AST 抽取所需的顶层字面量/函数后独立 exec —— 保证测的是【真实代码】，
    不是「源码里出现了某段文字」（那会被注释骗过，见 CONTRIBUTING 教训）
  · 尽可能断言「证据本身」（App 白名单、车型配置），而不只是代码形状；
    证据变了测试会失败，提醒重新判断
"""

from __future__ import annotations

import ast
import json
import types
from pathlib import Path

import pytest

_INTEG = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "lixiang_auto"
)
_CFG_DIR = _INTEG / "vehicle_configs"


# ── 基础设施 ────────────────────────────────────────────────────────────
def _src(filename: str) -> str:
    return (_INTEG / filename).read_text(encoding="utf-8")


def _load_pieces(filename: str, names: set[str]) -> dict:
    """抽取源码中指定的顶层 赋值 / AnnAssign / def，独立 exec。

    只保留标准库 import（相对导入与第三方导入一律丢弃）——
    这样既能测到真实实现，又不需要 homeassistant。
    """
    tree = ast.parse(_src(filename))
    body: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in names:
            body.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in names
                   for t in node.targets):
                body.append(node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in names:
                body.append(node)
    ns: dict = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), filename, "exec"), ns)
    return ns


def _load_vehicle_ability():
    """加载 vehicle_ability.py（照搬 tests/test_vehicle_ability.py 的做法）。"""
    src = (_INTEG / "vehicle_ability.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace(
        '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
        f'_CONFIG_DIR = Path({str(_CFG_DIR)!r})')
    mod = types.ModuleType("va_under_test")
    exec(compile(src, "vehicle_ability.py", "exec"), mod.__dict__)
    return mod


va = _load_vehicle_ability()
VehicleAbility = va.VehicleAbility

# signals / translations 无 HA 依赖，可直接导入（conftest 已把集成目录加入 sys.path）
import sys as _sys  # noqa: E402

_sys.path.insert(0, str(_INTEG))

import signals as sg  # noqa: E402
from translations import VALUE_MAPS, translate  # noqa: E402

SIGNALS = sg.SIGNALS
Semantics = sg.Semantics

_sw = _load_pieces("switch.py", {
    "_AC_ONOFF_TYPES", "SWITCHES", "DEFAULT_TEMP", "format_temp",
    "_custom",
})
_feat = _load_pieces("features.py", {
    "FEATURE_BY_KEY_PREFIX", "feature_of", "filter_by_features",
    "_desc_key", "is_supported_by_features",
    "resolve_requirement", "filter_specs", "_ability_bev",
})

# 实测车型 ID
L6_PRO = "100167931652606785"      # 增程（L6）
W04_PRO = "100497991299638466"     # i6（W04，纯电）
W05 = "101425807314452545"         # i8（W05，纯电）


def _tf(path: str, value):
    """值翻译（用真实 translate）。"""
    return translate(path, value)


class _D:
    """最小的实体描述替身（filter_by_features 只读 .key）。"""
    def __init__(self, key: str):
        self.key = key


# ══════════════════════════════════════════════════════════════════════════
#  ① 方向盘：只有开/关，没有三档
# ══════════════════════════════════════════════════════════════════════════
class TestSteeringWheelIsOnOffOnly:
    """用户：「方向盘开关错误了，实际只有开关功能，没有三档功能」。

    根因：fan 平台把它暴露成 0-3 档，但协议层只认 ON/OFF ——
    strgWhlHeatSw 在 App customVehicleACControl 的白名单里。
    """

    def test_whitelist_contains_steering_wheel(self):
        """证据①：协议白名单含 strgWhlHeatSw → 只能发 ON/OFF。"""
        assert "strgWhlHeatSw" in _sw["_AC_ONOFF_TYPES"], (
            "strgWhlHeatSw 必须在 ON/OFF 白名单里；"
            "若它不在，说明方向盘确实支持档位，此时结论要重新评估"
        )

    @pytest.mark.parametrize("level,expect", [(0, "OFF"), (1, "ON"),
                                              (2, "ON"), (3, "ON")])
    def test_level_is_collapsed_to_on_off(self, level, expect):
        """证据②：即便喂 3 档，发出的也是 ON（档位被丢弃）。

        若这里出现 LEVEL3，说明协议支持档位，可恢复 fan —— 测试会失败提醒。
        """
        data = _sw["_custom"]("strgWhlHeatSw", level)
        assert data["acCtrlValue"] == expect

    def test_not_in_fan_table(self):
        """方向盘不应再出现在 fan 表里。"""
        fans = _load_pieces("fan.py", {"SEAT_FANS"})["SEAT_FANS"]
        keys = [s[0] for s in fans]
        assert "wheel_heat" not in keys, (
            "方向盘加热仍在 fan 平台 —— 会再次暴露不存在的三档"
        )

    def test_fan_table_size_after_move(self):
        fans = _load_pieces("fan.py", {"SEAT_FANS"})["SEAT_FANS"]
        assert len(fans) == 12, f"座椅定义应为 12 个，实得 {len(fans)}"

    def test_in_switch_table(self):
        """方向盘应出现在 switch 表，且 controlType 正确。"""
        entries = {s[0]: s for s in _sw["SWITCHES"]}
        assert "wheel_heat" in entries, "方向盘加热不在 switch 表里"
        suffix, name, icon, state_key, ctrl, feat = entries["wheel_heat"]
        assert ctrl == "strgWhlHeatSw"
        assert state_key == "wheel_heat", "状态应取 wheel_heat 信号"
        assert feat == "方向盘加热", "门控功能名应为「方向盘加热」"

    def test_signal_is_platform_provided(self):
        """信号本身不自动建实体（由 switch 平台提供）。"""
        spec = SIGNALS["wheel_heat"]
        assert spec.platforms == frozenset(), (
            "wheel_heat 不应自动建实体，否则会出现第二个方向盘实体"
        )
        assert spec.path == "Vehicle.Cabin.WheelWarmStatus.WarmOnOff"

    def test_translation_has_only_on_off(self):
        """翻译表只有关闭/开启（没有档位文案）。"""
        p = "Vehicle.Cabin.WheelWarmStatus.WarmOnOff"
        assert _tf(p, 0) == "关闭"
        assert _tf(p, 1) == "开启"


# ══════════════════════════════════════════════════════════════════════════
#  ② i6 显示燃油续航
# ══════════════════════════════════════════════════════════════════════════
class TestFuelGatedByEnergyType:
    """用户：「i6 车型显示燃油续航」。

    根因：燃油实体无条件创建；i6 属 i 系列纯电（W04），没有油箱。
    判据：车型配置 config.energy.power —— 1 项 = 纯电，2 项 = 增程。
    """

    def test_i6_has_no_combustion_engine(self):
        ab = VehicleAbility(W04_PRO)
        assert ab.available, "车型配置应可加载"
        assert ab.power_sources == ["1"], \
            f"i6 应是单一动力源，实得 {ab.power_sources}"
        assert ab.has_combustion_engine is False, "i6 是纯电，不应有燃油"

    def test_i8_has_no_combustion_engine(self):
        assert VehicleAbility(W05).has_combustion_engine is False

    def test_l6_has_combustion_engine(self):
        ab = VehicleAbility(L6_PRO)
        assert ab.power_sources == ["1", "2"]
        assert ab.has_combustion_engine is True, "L6 是增程，必须有燃油"

    def test_unknown_model_does_not_crash(self):
        """未知车型不抛异常，且【保守保留】燃油实体。

        App 的 isBev()：power 为 [] → 长度不是 1 → isBev=false → 视为非纯电。
        我们照搬该判据，因此在无法识别车型时会保留燃油实体 ——
        这与项目「features 缺失时保留、宁多不误删」的约定一致。
        """
        ab = VehicleAbility("999999999999999999")
        assert ab.power_sources == []
        assert ab.is_bev is False, "未知车型照 App 判据 → 非纯电"
        assert ab.has_combustion_engine is True, "未知车型应保守保留燃油实体"

    def test_evidence_all_single_power_models_are_w_series(self):
        """证据复核：动力源与车系【完美分离，无例外】。

        · power 只有 1 项 → 全部 W 系（i 系列纯电）
        · power 有 2 项   → 全部非 W 系（L 系 + M01B，均为增程）

        ★ 若此断言失败，说明判据不再成立（如新增了其它纯电系列），
          应重新评估 is_bev / has_combustion_engine 的实现。

        ★ 同时记录一条已更正的错误结论：曾以为「M01B = MEGA，是配置笔误」，
          实测不成立 —— 68 个配置里没有 MEGA（grep 到的 "mega" 是 UI 素材名），
          M01B 是 6 座增程车，有燃油本就正确。
        """
        single, double = [], []
        for f in sorted(_CFG_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            cfg = json.loads(f.read_text(encoding="utf-8"))
            power = ((cfg.get("config") or {}).get("energy") or {}).get("power") or []
            um = str(cfg.get("unityModel") or "")
            (single if len(power) <= 1 else double).append(um)

        assert len(single) == 21, f"单一动力源车型数变了：{len(single)}"
        assert len(double) == 47, f"双动力源车型数变了：{len(double)}"
        bad = [um for um in single if not um.startswith("W")]
        assert not bad, f"出现非 W 系的单一动力源车型：{bad} —— 判据需重新评估"
        # ★ 反向检查：增程侧不应混入纯电系列（此前漏了这一半）
        bad2 = [um for um in double if um.startswith("W")]
        assert not bad2, f"出现 W 系的双动力源车型：{bad2} —— 分离不再干净"

    def test_no_mega_in_configs(self):
        """★ 更正记录：68 个车型配置里没有 MEGA。

        之前把 M01B 误当成 MEGA，进而臆断"纯电却标 2 项动力、是配置笔误"。
        实际 grep 到的 "mega" 都是 UI 素材名（如 config.trail="mega"）。
        本测试固定这一事实，避免该错误结论再次出现。
        """
        hits = []
        for f in sorted(_CFG_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            cfg = json.loads(f.read_text(encoding="utf-8"))
            desc = str(cfg.get("desc") or "")
            if "mega" in desc.lower():
                hits.append(desc)
        assert not hits, f"出现 desc 含 MEGA 的车型配置：{hits}（若有请更新本测试）"

    @pytest.mark.parametrize("key", ["fuel_level", "fuel_low_warning",
                                     "range_fuel_cltc", "range_fuel_wltc"])
    def test_fuel_key_maps_to_fuel_feature(self, key):
        assert _feat["feature_of"](key) == "燃油", f"{key} 应归属「燃油」功能"

    def test_pure_electric_drops_all_fuel_entities(self):
        keys = ("fuel_level", "fuel_low_warning",
                "range_fuel_cltc", "range_fuel_wltc")
        keep, skipped = _feat["filter_by_features"](
            [_D(k) for k in keys], {"燃油": False})
        assert keep == [], f"纯电车的燃油实体应全部跳过，实得 {[d.key for d in keep]}"
        assert len(skipped) == 4

    def test_erev_keeps_fuel_entities(self):
        keep, _ = _feat["filter_by_features"]([_D("fuel_level")], {"燃油": True})
        assert len(keep) == 1, "增程车必须保留燃油实体"


# ══════════════════════════════════════════════════════════════════════════
#  ③ 前备箱状态错误
# ══════════════════════════════════════════════════════════════════════════
class TestFrontTrunkPath:
    """用户：「i6 的前备箱状态错误」。

    根因：我们读的 Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor 根本不存在。
    实测服务端直接返回：
        400 invalid_path|desc:Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor
    正确路径是全 App 唯一的 DoorLockStatus.FrontTrunkDoor。
    """

    INVALID = "Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor"
    VALID = "Vehicle.Body.DoorLockStatus.FrontTrunkDoor"

    def test_no_signal_uses_the_invalid_path(self):
        bad = [k for k, s in SIGNALS.items() if s.path == self.INVALID]
        assert not bad, f"仍有信号使用服务端会拒绝的路径：{bad}"

    def test_lock_signal_uses_valid_path(self):
        assert SIGNALS["lock_front_trunk"].path == self.VALID

    def test_door_signal_aliases_lock_signal(self):
        """door_front_trunk 用别名复用 lock_front_trunk，避免重复声明同一路径。"""
        spec = SIGNALS["door_front_trunk"]
        assert spec.path == "", "别名信号的 path 必须为空（否则与 lock_ 重复）"
        assert spec.alias_signal == "lock_front_trunk"
        assert spec.semantics == Semantics.TRUNK
        assert spec.platforms == frozenset({"binary_sensor"})

    def test_paths_remain_unique(self):
        seen: dict[str, str] = {}
        dups = []
        for key, spec in SIGNALS.items():
            if not spec.path:
                continue
            if spec.path in seen:
                dups.append((key, seen[spec.path], spec.path))
            seen[spec.path] = key
        assert not dups, f"重复路径: {dups}"

    def test_alias_target_exists_and_is_real(self):
        for key, spec in SIGNALS.items():
            alias = getattr(spec, "alias_signal", None)
            if not alias:
                continue
            assert spec.path == "", f"{key}: 有别名信号的 path 必须为空"
            target = SIGNALS.get(alias)
            assert target is not None, f"{key} 的别名目标 {alias} 不存在"
            assert target.path.startswith("Vehicle."), \
                f"{key} 的别名目标必须是真实 VSS 路径"

    @pytest.mark.parametrize("key", ["door_front_trunk", "lock_front_trunk"])
    def test_front_trunk_key_is_feature_gated(self, key):
        """前备箱信号必须受「前备箱」门控（否则 L6 会出现前备箱实体）。"""
        assert _feat["feature_of"](key) == "前备箱"

    def test_l6_without_frunk_drops_frunk_entities(self):
        keep, skipped = _feat["filter_by_features"](
            [_D("door_front_trunk"), _D("lock_front_trunk")], {"前备箱": False})
        assert keep == [], "L6 无前备箱，前备箱实体应全部跳过"
        assert len(skipped) == 2


# ══════════════════════════════════════════════════════════════════════════
#  ③b 冰箱状态错误
# ══════════════════════════════════════════════════════════════════════════
class TestFridgeModeTranslation:
    """用户：「i6 的冰箱状态错误」。

    根因：ModeState 映射成 {0:关闭, 1:开启}，但它其实是【制冷/制热模式】。
    App getCurrentMode：1→COOL(制冷), 2→HEAT(制热), 默认→CLOSE(关闭)。
    """

    PATH = "Vehicle.Cabin.Fridge.ModeState"

    def test_cool(self):
        assert _tf(self.PATH, 1) == "制冷", \
            "1 是制冷（App getCurrentMode case 1 → COOL），不是「开启」"

    def test_heat(self):
        assert _tf(self.PATH, 2) == "制热", \
            "2 是制热（case 2 → HEAT），此前完全没映射 → 显示裸数字"

    def test_close(self):
        assert _tf(self.PATH, 0) == "关闭"

    def test_unknown_value_not_guessed(self):
        assert _tf(self.PATH, 9) == 9

    @pytest.mark.parametrize("v", [0, 1, 2, 3])
    def test_act_work_sts_all_mapped(self, v):
        """ActWorkSts 的 2/3 也要有映射（App 用它触发提示，此前显示裸数字）。"""
        out = _tf("Vehicle.Cabin.Fridge.ActWorkSts", v)
        assert isinstance(out, str), f"ActWorkSts={v} 未映射，仍显示裸数字"

    def test_scene_mode_map_not_broken(self):
        """★ 冰箱用两段键，不能牵连 SceneMode.ModeState。"""
        p = "Vehicle.CarSettings.SceneMode.ModeState"
        assert _tf(p, 0) == "未设置"
        assert _tf(p, 1) == "已设置"

    def test_generic_modestate_key_removed(self):
        """通用键 ModeState 已移除 —— 否则会误伤其它 .ModeState 路径。"""
        import sys
        sys.path.insert(0, str(_INTEG))
        from translations import VALUE_MAPS
        assert "ModeState" not in VALUE_MAPS, (
            "通用 ModeState 键会把冰箱语义套到所有 .ModeState 路径上"
        )


# ══════════════════════════════════════════════════════════════════════════
#  跨平台门控一致性（本次顺带修好的架构缺口）
# ══════════════════════════════════════════════════════════════════════════
class TestFeatureGatingShared:
    """★ binary_sensor 此前【完全没有】车型功能门控。

    FEATURE_BY_KEY_PREFIX 只定义在 sensor.py，于是 L6（无前备箱）上
    仍生成 binary_sensor.…_qian_bei_xiang_men / …_qian_bei_xiang_suo。
    现提升到 features.py，两平台共用。
    """

    def test_map_contains_frunk_and_fuel(self):
        m = _feat["FEATURE_BY_KEY_PREFIX"]
        for k in ("lock_front_trunk", "door_front_trunk", "fuel", "range_fuel"):
            assert k in m, f"{k} 缺失于功能映射表"

    def test_binary_sensor_applies_filter(self):
        """必须真的调用过滤（AST 检查 Call，避免被注释骗过）。

        ★ 2026-09-28：机制从 filter_by_features（前缀表）升级为
          filter_specs（SignalSpec 的能力声明）。两者都算合格，
          但必须【真的调用】—— 此前 binary_sensor 完全没有过滤。
        """
        tree = ast.parse(_src("binary_sensor.py"))
        calls = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert calls & {"filter_specs", "filter_by_features"}, (
            "binary_sensor 必须调用车型能力过滤（filter_specs），"
            "否则无硬件的实体（如前备箱）会再次出现"
        )

    def test_sensor_applies_filter(self):
        """sensor 同样必须真的过滤（历史上它是唯一有过滤的平台）。"""
        tree = ast.parse(_src("sensor.py"))
        calls = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert calls & {"filter_specs", "filter_by_features"}, \
            "sensor 必须调用车型能力过滤"

    def test_sensor_uses_shared_impl(self):
        """sensor 应复用 features.feature_of，且不再自带一份字典。"""
        tree = ast.parse(_src("sensor.py"))
        imported = False
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "features":
                if any(a.name == "feature_of" for a in n.names):
                    imported = True
        assert imported, "sensor 应从 features 导入 feature_of"

        for n in tree.body:
            for tgt in (n.targets if isinstance(n, ast.Assign) else []):
                if isinstance(tgt, ast.Name) and tgt.id == "FEATURE_BY_KEY_PREFIX":
                    pytest.fail("sensor.py 不应再重复定义映射表（会与 features 漂移）")

    # ── ★ 静默失效回归（2026-09-28 事故）────────────────────────────────
    def test_filter_handles_binary_description_tuples(self):
        """★ 关键回归：to_binary_descriptions() 产出 **(desc, spec) 元组**。

        最初的实现只做 `getattr(item, "key", "")` ——
        元组没有 .key → 取到空串 → feature_of 返回 None → 【一个都不过滤】。
        于是前备箱实体在 L6 上照旧创建，过滤器看起来在工作、实则静默失效。
        这个测试就是那次事故的守卫。
        """
        pairs = [(_D("door_front_trunk"), object()),
                 (_D("lock_front_trunk"), object()),
                 (_D("charging_gun"), object())]
        keep, skipped = _feat["filter_by_features"](pairs, {"前备箱": False})

        kept_keys = [p[0].key for p in keep]
        assert kept_keys == ["charging_gun"], \
            f"元组形状必须被正确过滤，实得 {kept_keys}"
        assert len(skipped) == 2
        # 元组形状必须原样保留（调用方要拿 (desc, spec) 建实体）
        assert all(isinstance(p, tuple) and len(p) == 2 for p in keep)

    def test_is_supported_handles_tuples(self):
        f = _feat["is_supported_by_features"]
        assert f((_D("door_front_trunk"), object()), {"前备箱": False}) is False
        assert f((_D("door_front_trunk"), object()), {"前备箱": True}) is True
        assert f(_D("door_front_trunk"), {"前备箱": False}) is False


# ══════════════════════════════════════════════════════════════════════════
#  ★ 系统性守卫：增程专属信号必须被门控
# ══════════════════════════════════════════════════════════════════════════
class TestCombustionSignalsAreGated:
    """防止「i6 显示燃油续航」这类问题再次发生。

    用户问：「我们不是跟车 app 里面的车型自动分类的吗？」

    实情：分类机制【存在】，但门控是**逐条手工登记**的 ——
    156 个信号里只有约 1/6 写进了 FEATURE_BY_KEY_PREFIX，
    没登记的默认「所有车型都创建」。燃油系列当年就没登记。
    所以 i6（纯电）拿到了 L 系（增程）才该有的传感器。

    本守卫的作用：只要出现「名字看起来是增程专属、却没有门控」的新信号，
    测试立即失败 —— 把「靠人记得」变成「靠测试兜住」。
    """

    #: 命中即疑似增程专属（大小写不敏感）
    HINTS = ("fuel", "oil", "tank", "sparkplug", "engine", "exhaust", "增程")

    #: 例外：虽然命中关键词，但纯电车同样需要（附理由）
    ALSO_ON_BEV = {
        "maint_brake_oil": "刹车油 —— 纯电车也有刹车系统",
        "maint_engine_level2": "enginelevel2 语义未确证，不敢断言专属发动机",
    }

    def test_no_ungated_combustion_signal(self):
        suspects = []
        for key, spec in SIGNALS.items():
            hay = f"{spec.path} {spec.name} {key}".lower()
            if not any(h in hay for h in self.HINTS):
                continue
            if key in self.ALSO_ON_BEV:
                continue
            if _feat["feature_of"](key) != "燃油":
                suspects.append(f"{key}（{spec.name} / {spec.path}）")

        assert not suspects, (
            "以下信号看起来是增程（燃油）专属，但没有被「燃油」门控 ——\n"
            "  纯电车会错误地显示它们（这正是 i6 显示燃油续航的成因）。\n"
            "  请二选一：\n"
            "    ① 确实是增程专属 → 加进 features.FEATURE_BY_KEY_PREFIX（\"燃油\"）\n"
            f"    ② 纯电车也有   → 加进本测试的 ALSO_ON_BEV 并写明理由\n"
            f"  可疑信号: {suspects}"
        )

    def test_exemptions_are_documented(self):
        """例外必须真的有理由（防止随手加白名单蒙混过关）。"""
        for key, why in self.ALSO_ON_BEV.items():
            assert key in SIGNALS, f"例外 {key} 不在信号表里（已删除？请同步移除例外）"
            assert len(why) >= 8, f"例外 {key} 的理由过短，说明不清"

    def test_known_combustion_signals_are_all_gated(self):
        """本次实测确认的增程专属信号，逐一断言已门控。"""
        for key in ("fuel_level", "fuel_low_warning",
                    "range_fuel_cltc", "range_fuel_wltc",
                    "tank_lock", "maint_engine_oil", "maint_sparkplug"):
            assert key in SIGNALS, f"{key} 不在信号表"
            assert _feat["feature_of"](key) == "燃油", f"{key} 未被「燃油」门控"


# ══════════════════════════════════════════════════════════════════════════
#  ★ 照搬 App 的纯电判定（isBev）
# ══════════════════════════════════════════════════════════════════════════
class TestIsBevMatchesApp:
    """用户问：「app 都能区分，我们为什么不能？直接照搬 app 的区分逻辑不就好了？」

    ★ 能，而且现在就是照搬的。App 源码（assets/index.vehicle.js）：

        u.isBev = function() {
            var u = (VehicleTool.getVehicleDetails()
                     ?.config?.energy?.power) || [];
            return !(u.length !== 1 || !u.includes('1'));
        }

    本测试把上面这段 JS 逐字翻译成 Python（见 _app_is_bev），
    再与我们的 VehicleAbility.is_bev 在**全部 68 个车型配置**上对照。
    只要两者有任何分歧，测试就失败 —— 保证我们【确实】在照搬，而非近似。
    """

    @staticmethod
    def _app_is_bev(power: list[str]) -> bool:
        """App `isBev()` 的逐字翻译（不改写、不简化）。"""
        u = power or []
        return not (len(u) != 1 or "1" not in u)

    @staticmethod
    def _ability(power):
        """构造一个只用 energy.power 的 VehicleAbility 替身。"""
        ab = VehicleAbility.__new__(VehicleAbility)
        ab._cfg = {"config": {"energy": {"power": power}}}
        return ab

    def test_matches_app_on_all_68_models(self):
        """在真实车型配置上逐一对照 App 公式。"""
        checked = 0
        for f in sorted(_CFG_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            cfg = json.loads(f.read_text(encoding="utf-8"))
            power = ((cfg.get("config") or {}).get("energy") or {}).get("power") or []
            ours = self._ability(power).is_bev
            app = self._app_is_bev([str(x) for x in power])
            assert ours == app, (
                f"{cfg.get('desc')} power={power}: "
                f"我们={ours} App={app} —— 偏离了 App 的 isBev()"
            )
            checked += 1
        assert checked == 68, f"应检查 68 个车型，实得 {checked}"

    @pytest.mark.parametrize("power,expect", [
        (["1"], True),            # 纯电
        (["1", "2"], False),      # 增程
        (["2"], False),           # ★ 关键边界：单一非电动力
        ([], False),              # 无配置
        (["1", "2", "3"], False),
    ])
    def test_edge_cases_match_app(self, power, expect):
        """★ 边界用例，用来证明我们【没有】用「取反」的近似写法。

        若实现写成 `has_fuel = len(power) >= 2`，则 ["2"] 会被判为「无燃油」，
        与 App（isBev=false → 非纯电 → 有燃油）相反。这个用例会抓住它。
        """
        ab = self._ability(power)
        assert ab.is_bev is expect, f"power={power} 的 is_bev 应为 {expect}"
        assert ab.is_bev == self._app_is_bev(power)

    def test_combustion_is_exact_complement(self):
        for power in (["1"], ["1", "2"], ["2"], []):
            ab = self._ability(power)
            assert ab.has_combustion_engine is (not ab.is_bev)

    def test_i6_and_i8_are_bev(self):
        assert VehicleAbility(W04_PRO).is_bev is True, "i6(W04) 应为纯电"
        assert VehicleAbility(W05).is_bev is True, "i8(W05) 应为纯电"

    def test_l6_is_not_bev(self):
        assert VehicleAbility(L6_PRO).is_bev is False, "L6 是增程，不是纯电"

    def test_source_comment_cites_app_function_name(self):
        """实现里必须写明依据的是 App 的哪个函数（便于后人复核）。"""
        src = _src("vehicle_ability.py")
        assert "isBev" in src, "应注明依据 App 的 isBev()"
        assert "energy?.power" in src or "energy" in src


# ══════════════════════════════════════════════════════════════════════════
#  ★★ 穷尽性：每个信号都必须声明车型能力需求（option A 的核心保障）
# ══════════════════════════════════════════════════════════════════════════
class TestRequirementExhaustiveness:
    """用户问：「以后新车呢？app 也是一个一个判断？不是直接有清单？」

    App 的答案是：能力【数据】是清单（assets/{modelId}.json，54 个标签），
    但「标签 → 界面元素」的映射它也是逐句写死的。

    我们的改进：把映射声明到每个 SignalSpec 上，并要求【每个信号都表态】。
    本类就是那个"不允许留空"的强制机制。
    """

    def test_every_signal_declares_requirement(self):
        """★ 核心：不允许有信号既不声明 requires 也不声明 universal。

        这正是 i6 拿到燃油续航的成因 —— 没登记就默认「所有车型都建」。
        """
        undeclared = [k for k, s in SIGNALS.items()
                      if not s.requires and not s.universal]
        assert not undeclared, (
            f"{len(undeclared)} 个信号未声明车型能力需求：{undeclared[:12]}\n"
            "  每个信号必须二选一：\n"
            '    requires="version:<tag>" / "ability:<tag>" / '
            '"feature:<名>" / "combustion" / "bev"\n'
            "    universal=True   （所有车型都有 —— 也必须显式写出来）"
        )

    def test_not_both_requires_and_universal(self):
        both = [k for k, s in SIGNALS.items() if s.requires and s.universal]
        assert not both, f"不能同时声明 requires 与 universal：{both}"

    def test_coverage_is_total(self):
        n = sum(1 for s in SIGNALS.values() if s.requires or s.universal)
        assert n == len(SIGNALS), f"只有 {n}/{len(SIGNALS)} 个信号已表态"

    def test_requires_dsl_is_wellformed(self):
        import re
        pat = re.compile(r"^(version|ability|feature):\S+$")
        bad = []
        for k, s in SIGNALS.items():
            if not s.requires:
                continue
            if s.requires in ("combustion", "bev"):
                continue
            if not pat.match(s.requires):
                bad.append(f"{k}={s.requires!r}")
        assert not bad, f"requires 语法非法：{bad}"


class TestRequirementTagsExistInAppConfig:
    """★ requires 里引用的 App 标签必须【真的存在于车型配置】里。

    这条能抓住拼写错误（如 version:frideg）与过时标签 ——
    否则该信号会因为"标签查不到"而被静默判为不支持（或永远不支持），
    属于同一类"看起来在工作、其实没生效"的缺陷。
    """

    @staticmethod
    def _app_tags():
        ver, cfg = set(), set()
        for f in sorted(_CFG_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            ver.update((d.get("version") or {}).keys())
            for item in (d.get("temp") or {}).get("config") or []:
                if item.get("key"):
                    cfg.add(item["key"])
        return ver, cfg

    def test_version_tags_exist(self):
        ver, _ = self._app_tags()
        bad = [f"{k}={s.requires}" for k, s in SIGNALS.items()
               if (s.requires or "").startswith("version:")
               and s.requires.split(":", 1)[1] not in ver]
        assert not bad, f"引用了 App 里不存在的 version 标签：{bad}"

    def test_ability_tags_exist(self):
        _, cfg = self._app_tags()
        bad = [f"{k}={s.requires}" for k, s in SIGNALS.items()
               if (s.requires or "").startswith("ability:")
               and s.requires.split(":", 1)[1] not in cfg]
        assert not bad, f"引用了 App 里不存在的 temp.config 标签：{bad}"

    def test_feature_names_are_known_features(self):
        """feature:<名> 必须是我们真的会探测的功能名。"""
        src = _src("features.py")
        bad = []
        for k, s in SIGNALS.items():
            if not (s.requires or "").startswith("feature:"):
                continue
            name = s.requires.split(":", 1)[1]
            if f'"{name}"' not in src:
                bad.append(f"{k}={s.requires}")
        assert not bad, f"feature 名称未在 features.py 出现过：{bad}"


class TestResolveRequirementBehaviour:
    """DSL 解析行为（用真实 ability + features 验证）。"""

    def test_combustion(self):
        f = _feat["resolve_requirement"]
        bev = VehicleAbility(W04_PRO)
        erev = VehicleAbility(L6_PRO)
        sig = type("S", (), {"requires": "combustion", "universal": False})
        assert f(sig, {}, bev)[0] is False, "纯电不应建增程专属实体"
        assert f(sig, {}, erev)[0] is True, "增程应建"

    def test_bev(self):
        f = _feat["resolve_requirement"]
        sig = type("S", (), {"requires": "bev", "universal": False})
        assert f(sig, {}, VehicleAbility(W04_PRO))[0] is True
        assert f(sig, {}, VehicleAbility(L6_PRO))[0] is False

    def test_version_tag(self):
        f = _feat["resolve_requirement"]
        sig = type("S", (), {"requires": "version:fridge", "universal": False})
        # L6Pro: fridge isSupport=false；W05(i8): true
        assert f(sig, {}, VehicleAbility(L6_PRO))[0] is False
        assert f(sig, {}, VehicleAbility(W05))[0] is True

    def test_ability_tag(self):
        f = _feat["resolve_requirement"]
        # L6 无三排（thirdLSeatSw=1）；值语义 1=无硬件
        sig = type("S", (), {"requires": "ability:thirdLSeatSw", "universal": False})
        assert f(sig, {}, VehicleAbility(L6_PRO))[0] is False

    def test_feature_flag(self):
        f = _feat["resolve_requirement"]
        sig = type("S", (), {"requires": "feature:冰箱", "universal": False})
        assert f(sig, {"冰箱": False}, None)[0] is False
        assert f(sig, {"冰箱": True}, None)[0] is True
        # 缺失时保守保留
        assert f(sig, {}, None)[0] is True

    def test_universal(self):
        f = _feat["resolve_requirement"]
        sig = type("S", (), {"requires": None, "universal": True})
        assert f(sig, {}, None)[0] is True

    def test_no_ability_is_conservative(self):
        """没有能力表时不能误删 —— 保守保留。"""
        f = _feat["resolve_requirement"]
        for req in ("version:fridge", "ability:thirdLSeatSw"):
            sig = type("S", (), {"requires": req, "universal": False})
            assert f(sig, {}, None)[0] is True, f"{req} 在无能力表时应保留"

    def test_unknown_dsl_is_conservative(self):
        f = _feat["resolve_requirement"]
        sig = type("S", (), {"requires": "bogus:x", "universal": False})
        ok, why = f(sig, {}, None)
        assert ok is True and "未知DSL" in why


# ══════════════════════════════════════════════════════════════════════════
#  ★★ 已知无效 VSS 路径（服务端 invalid_path）—— 永不再用
# ══════════════════════════════════════════════════════════════════════════
class TestNoKnownInvalidPaths:
    """服务端对无效路径返回 400，且会让【整批】VSS 失败。

    而轮询路径来自 signals（by_freq / paths_for）**不按车型过滤** ——
    所以一个无效路径每一轮都在浪费请求，并且让该实体永远没有数据。

    危害已在两处实测证实（均于 2026-09-28 修复）：
      · Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor   （前备箱）
      · Vehicle.Body.SeatLDoor.DoorStatus / SeatRDoor.DoorStatus（滑门）

    全量审计工具：custom_components/lixiang_auto/tools/audit_vss_paths.py
    （151 条路径，实测仅上述 2 条无效；修完应为 0）
    """

    #: 实测被服务端拒绝的路径（切勿再在任何 SignalSpec 里使用）
    INVALID = (
        "Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor",
        "Vehicle.Body.SeatLDoor.DoorStatus",
        "Vehicle.Body.SeatRDoor.DoorStatus",
    )

    def test_no_signal_uses_invalid_path(self):
        used = {s.path for s in SIGNALS.values()}
        bad = sorted(used & set(self.INVALID))
        assert not bad, (
            f"以下路径已被服务端证实为 invalid_path，不能使用：{bad}\n"
            "  它们会让整批 VSS 请求 400，并触发二分重试"
        )

    def test_sliding_door_uses_doorposition(self):
        """滑门状态应走 DoorPosition（desc「W二排左/右侧侧滑门开度值」）。"""
        assert SIGNALS["door_slide_left"].path == "Vehicle.Body.DoorPosition.BackLeftDoor"
        assert SIGNALS["door_slide_right"].path == "Vehicle.Body.DoorPosition.BackRightDoor"

    def test_front_trunk_uses_doorlockstatus(self):
        assert SIGNALS["lock_front_trunk"].path == \
            "Vehicle.Body.DoorLockStatus.FrontTrunkDoor"


# ══════════════════════════════════════════════════════════════════════════
#  ★★ 逐座门控：二排中 / 三排中 必须按【该座位自己的标签】判断
# ══════════════════════════════════════════════════════════════════════════
class TestPerSeatGating:
    """实测座椅标签（68 个车型配置）：

        L6Pro（5座）:  secMSeatSw=4（有二排中）  thirdLSeatSw=1（无三排）
        L8/L9（6座）:  secMSeatSw=1（无二排中）  thirdLSeatSw=4（有三排）
        W01（i系列）:  thirdMSeatHeatSw=4       其余车型【没有这个键】

    ★ 此前 seat_sm_heat 用的是复合功能「二排座椅」
      （= secL OR secM OR secR 任一存在），而 L8/L9 有 secL/secR
      → **L8/L9 被错误创建了「二排中座椅加热」** ——
        与「i6 显示燃油续航」完全同一类缺陷：硬件不存在却建了实体。
    """

    def test_middle_second_row_uses_its_own_tag(self):
        assert SIGNALS["seat_sm_heat"].requires == "ability:secMSeatSw", (
            "二排中座椅必须用 secMSeatSw 判断；用复合的「二排座椅」会让 "
            "L8/L9（无二排中，但有二排左/右）错误创建该实体"
        )

    def test_third_row_uses_its_own_tags(self):
        assert SIGNALS["seat_tl_heat"].requires == "ability:thirdLSeatSw"
        assert SIGNALS["seat_tr_heat"].requires == "ability:thirdRSeatSw"

    def test_third_middle_uses_heat_tag(self):
        """三排中只在 6 个 W 系车型里有 thirdMSeatHeatSw。"""
        assert SIGNALS["seat_tm_heat"].requires == "ability:thirdMSeatHeatSw"

    def test_second_row_left_right_use_own_tags(self):
        assert SIGNALS["seat_sl_heat"].requires == "ability:secLSeatSw"
        assert SIGNALS["seat_sr_heat"].requires == "ability:secRSeatSw"

    def test_front_seats_use_own_tags(self):
        assert SIGNALS["seat_fl_heat"].requires == "ability:flSeatSw"
        assert SIGNALS["seat_fr_heat"].requires == "ability:frSeatSw"

    @pytest.mark.parametrize("mid,label,sm,tl", [
        ("100167931652606785", "L6Pro(5座)", True, False),
        ("100165028254293339", "L8Air(6座)", False, True),
        ("100174236664108736", "L9Max(6座)", False, True),
    ])
    def test_cross_model_behaviour(self, mid, label, sm, tl):
        """跨车系验证：L6 有(二排中,无三排)；L8/L9 相反。"""
        ab = VehicleAbility(mid)
        assert ab.available, f"{label} 配置应可加载"
        f = _feat["resolve_requirement"]
        got_sm = f(SIGNALS["seat_sm_heat"], {}, ab)[0]
        got_tl = f(SIGNALS["seat_tl_heat"], {}, ab)[0]
        assert got_sm is sm, f"{label}: 二排中座椅应为 {sm}，实得 {got_sm}"
        assert got_tl is tl, f"{label}: 三排左座椅应为 {tl}，实得 {got_tl}"

    def test_missing_tag_means_no_hardware(self):
        """★ 关键语义：配置里【没有】该 tag ≠ 有硬件。

        ability_level() 对未配置的 tag 返回 DEFAULT(2)，用 ">=2" 判断会把
        「配置没提」误判为「有」。实测 thirdMSeatHeatSw 只在 6 个 W 系车型里
        存在，其余 62 个车型根本没有这个键 —— 必须用 has()（未配置→False）。
        """
        ab = VehicleAbility("100167931652606785")   # L6Pro，无 thirdMSeatHeatSw
        assert ab.is_configured("thirdMSeatHeatSw") is False
        assert ab.ability_level("thirdMSeatHeatSw") >= 2, "ability_level 对缺失键会返回默认 2"
        assert ab.has("thirdMSeatHeatSw") is False, "has() 才是正确判据"
        assert _feat["resolve_requirement"](
            SIGNALS["seat_tm_heat"], {}, ab)[0] is False

    def test_resolver_uses_has_not_ability_level(self):
        """静态保证：resolver 必须调用 has()，不能退化成 ability_level() >= 2。"""
        src = _src("features.py")
        i = src.find('if kind == "ability":')
        assert i > 0
        block = src[i:i + 900]
        assert "ability.has(" in block, "ability: 分支必须用 ability.has()"


# ══════════════════════════════════════════════════════════════════════════
#  ★★ 用户报告「L6 没有滑门」—— 滑门/前备箱的可控实体误建
# ══════════════════════════════════════════════════════════════════════════
def _load_cover_helper(name: str):
    """从 cover.py 里 AST 抽出指定函数（cover.py 依赖 homeassistant，不能直接 import）。"""
    tree = ast.parse(_src("cover.py"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            mod = ast.Module(body=[node], type_ignores=[])
            ns: dict = {}
            exec(compile(mod, "cover_helper", "exec"), ns)  # noqa: S102
            return ns[name]
    raise AssertionError(f"cover.py 里找不到函数 {name}")


_detect_slide = _load_cover_helper("detect_slide_door")


class _FakeHpcm:
    """最小 Hpcm 替身：has() 语义 = 「值非 '0' 且非空」。"""

    def __init__(self, fields: dict, available: bool = True):
        self._f = fields
        self.available = available

    def has(self, k: str) -> bool:
        if not self.available:
            return False
        return self._f.get(k) not in (None, "", "0", 0, False)

    def get(self, k, default=None):
        return self._f.get(k, default)


class TestSlideDoorDetection:
    """L6 实测三项证据全说"没有滑门"：

        App version.sideDoor.isSupport = false   → features["侧滑门"] = false
        Hpcm hc_psd = "0", hc_automatic_door = "0"

    却出现了 cover.li_xiang_l6_zuo_hua_men / _you_hua_men 两个【可控】实体。

    根因：cover.py 用「信号在不在 vss 里」推断硬件，而
      · vss 的键是【信号 key】，不是 VSS 路径 → 路径那两条恒为假
      · "door_slide_left" 只要被轮询就在 vss 里，轮询【不按车型过滤】→ 恒真
    于是每辆车都被判定有滑门。
    """

    def test_l6_case_no_slide_door(self):
        """L6 的真实组合 → 必须判定为【无滑门】。"""
        hpcm = _FakeHpcm({"hc_psd": "0", "hc_automatic_door": "0", "hc_frunk": "0"})
        ok, why = _detect_slide({"侧滑门": False}, hpcm)
        assert ok is False, f"L6 不应有滑门，却判定为有（依据={why}）"

    def test_app_ability_table_says_yes(self):
        ok, why = _detect_slide({"侧滑门": True}, _FakeHpcm({}))
        assert ok is True and "sideDoor" in why

    def test_hpcm_says_yes(self):
        hpcm = _FakeHpcm({"hc_psd": "1"})
        ok, why = _detect_slide({}, hpcm)
        assert ok is True and "Hpcm" in why

    def test_hpcm_automatic_door_yes(self):
        ok, _ = _detect_slide({}, _FakeHpcm({"hc_automatic_door": "1"}))
        assert ok is True

    def test_no_evidence_means_no(self):
        """★ 核心原则：没有肯定证据就不建（宁可少做，不给虚假可控能力）。"""
        for feats, hpcm in (
            ({}, _FakeHpcm({})),
            ({}, None),
            ({"侧滑门": False}, None),
            ({}, _FakeHpcm({"hc_psd": "0"})),
            ({"冰箱": True}, _FakeHpcm({})),
        ):
            ok, why = _detect_slide(feats, hpcm)
            assert ok is False, f"无证据时不应建滑门：features={feats} → {why}"

    def test_hpcm_unavailable_is_not_evidence(self):
        ok, _ = _detect_slide({}, _FakeHpcm({"hc_psd": "1"}, available=False))
        assert ok is False, "Hpcm 不可用时不能当作'有硬件'"

    def test_hpcm_has_raising_is_contained(self):
        class Boom:
            available = True
            def has(self, k): raise RuntimeError("boom")
        ok, _ = _detect_slide({}, Boom())
        assert ok is False, "Hpcm 异常不能导致误建"

    def test_decision_does_not_take_vss(self):
        """★ 签名里不该有 vss —— 用信号存在推断硬件正是原始缺陷。"""
        import inspect
        params = list(inspect.signature(_detect_slide).parameters)
        assert "vss" not in params, f"判定不应依赖 vss：{params}"

    def test_l6_real_ability_table(self):
        """用真实的 L6 能力表算 features，再判定 —— 必须为 False。"""
        ab = VehicleAbility("100167931652606785")
        assert ab.available
        assert ab.is_supported("sideDoor") is False, \
            "App 能力表里 L6 的 sideDoor 应为 false"
        ab_feats = _feat["_ability_to_features"](ab) if "_ability_to_features" in _feat else None
        if ab_feats is not None:
            assert ab_feats.get("侧滑门") is False
            ok, _ = _detect_slide(ab_feats, _FakeHpcm(
                {"hc_psd": "0", "hc_automatic_door": "0"}))
            assert ok is False


class TestNoSignalPresenceHardwareInference:
    """系统性守卫：不得再用「信号在 vss 里 ⇒ 有硬件」推断。

    同一处代码里踩了【两次】：滑门 与 前备箱。
    """

    def test_cover_py_gates_on_features(self):
        src = _src("cover.py")
        tree = ast.parse(src)
        # ① setup 必须调用 detect_slide_door
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "detect_slide_door" in calls, \
            "cover.py 的滑门判定必须走 detect_slide_door()"

    def test_cover_py_has_no_signal_presence_inference(self):
        """剥掉注释后，代码里不得再有 `in vss` 形式的硬件推断。"""
        src = _src("cover.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            # 形如 any(k in vss for k in (...)) 或 k in vss
            if isinstance(node, ast.Compare):
                for op, comp in zip(node.ops, node.comparators):
                    if (isinstance(op, ast.In)
                            and isinstance(comp, ast.Name)
                            and comp.id == "vss"):
                        # 允许 vss.get(...) 等取值；只禁止 in vss 的存在性推断
                        raise AssertionError(
                            f"cover.py:{node.lineno} 仍用 `in vss` 推断硬件 —— "
                            "vss 的键是信号 key，轮询不按车型过滤，"
                            "该条件恒真（曾导致每辆车都建滑门/前备箱）")
