"""派生信号（computed）必须有实体状态 —— 回归测试（2026-10-10）。

真事故
------
总续航 `sensor.*_zong_xu_hang_cltc/wltc` 恒为 **unknown**，而协调器日志算得
好好的：`派生信号 range_total_cltc = 978.0`（纯电 85 + 燃油 893）。

根因：`LiCarSensor.native_value` 里有一条「从未上报」判定 ——
派生信号是本地算出来的，**没有 ts**，于是落进该分支；首轮又必然
`_last_value is None` → 直接 `return None`，`_last_value` 永远建立不起来
→ 永久 unknown（死锁）。

`available` 里早已对 computed 做过豁免（见下），`native_value` 漏了同类豁免 ——
所以本文件除了行为用例，还加一条**一致性守卫**：
`available` 与 `native_value` 必须都豁免 computed，避免将来只在其中一处修。

测试环境没有 homeassistant → 用 AST 抽出真实 `native_value` 属性函数，
注入假 self 来跑。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
SENSOR = CC / "sensor.py"


def _src() -> str:
    return SENSOR.read_text(encoding="utf-8")


def _load_native_value():
    """抽出 LiCarSensor.native_value 的**函数体**（去掉 @property 装饰器）。"""
    tree = ast.parse(_src())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LiCarSensor":
            for sub in node.body:
                if (isinstance(sub, ast.FunctionDef)
                        and sub.name == "native_value"):
                    # ★ 直接复用原节点（保留 lineno 等字段），只摘掉 @property：
                    #   重新构造 FunctionDef 会因缺 lineno 编译失败。
                    sub.decorator_list = []
                    ns = {"STATE_UNKNOWN": "unknown"}
                    exec(compile(ast.Module(body=[sub], type_ignores=[]),
                                 "<nv>", "exec"), ns)
                    return ns["native_value"]
    raise AssertionError("找不到 LiCarSensor.native_value")


class _FakeEntity:
    """只提供 native_value 需要的接口。"""

    def __init__(self, value, sig, unsupported=(), last=None, key="range_total_cltc"):
        self._value = value          # _compute_value() 的结果
        self._sig = sig              # _vss() 的结果
        self._last_value = last
        self._last_ts = None
        self._unsupported = set(unsupported)
        self.entity_description = type("D", (), {"key": key})()

    @property
    def coordinator(self):
        return type("C", (), {"data": {"unsupported_keys": self._unsupported}})()

    def _compute_value(self):
        return self._value

    def _vss(self):
        return self._sig


def _call(**kw) -> object:
    fn = _load_native_value()
    ent = _FakeEntity(**kw)
    return fn(ent)


class TestComputedSignalState:
    def test_computed_signal_yields_state(self):
        """★ 核心回归：派生信号（无 ts、computed）必须给出值。

        修复前：`_last_value is None` → return None → 永久 unknown。
        """
        got = _call(value=978.0, sig={"value": 978.0, "computed": True})
        assert got == 978.0, "派生信号被「从未上报」判定吃掉了（总续航 unknown 的根因）"

    def test_computed_signal_caches_last_value(self):
        """拿到值后必须写入 _last_value（否则下一轮还会被判 None）。"""
        fn = _load_native_value()
        ent = _FakeEntity(value=978.0, sig={"value": 978.0, "computed": True})
        assert fn(ent) == 978.0
        assert ent._last_value == 978.0

    def test_computed_signal_without_value_falls_back(self):
        """派生算不出值（None）时：有历史值就回退，没有就 None。"""
        assert _call(value=None, sig={"value": None, "computed": True},
                     last=900.0) == 900.0
        assert _call(value=None, sig={"value": None, "computed": True}) is None

    def test_genuine_never_reported_still_unknown(self):
        """★ 原有守卫必须保留：真·从未上报（ts=="0"）且无历史值 → None。

        否则会退化成显示误导性的 0（硬件不存在的信号）。
        """
        assert _call(value=0, sig={"value": 0, "ts": "0"}) is None
        assert _call(value=0, sig={"value": 0, "ts": ""}) is None
        # 有历史值时仍回退（sticky 语义）
        assert _call(value=0, sig={"value": 0, "ts": "0"}, last=7) == 0

    def test_non_vss_signal_still_works(self):
        """非 VSS 信号（_vss() 为 None，如 online_status）不受影响。"""
        assert _call(value="在线", sig=None) == "在线"

    def test_unsupported_key_returns_none(self):
        """车型不支持的信号仍然隐藏（不能因为本次修复又冒出来）。"""
        assert _call(value=1, sig={"value": 1, "ts": "2026-10-10"},
                     unsupported=("range_total_cltc",)) is None


class TestComputedExemptionConsistency:
    """★ 一致性守卫：`available` 与 `native_value` 必须都豁免 computed。"""

    def _prop_src(self, name: str) -> str:
        tree = ast.parse(_src())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "LiCarSensor":
                for sub in node.body:
                    if (isinstance(sub, ast.FunctionDef)
                            and sub.name == name):
                        return ast.get_source_segment(_src(), sub) or ""
        raise AssertionError(f"找不到 LiCarSensor.{name}")

    def test_available_exempts_computed(self):
        body = self._prop_src("available")
        assert 'sig.get("computed")' in body or "sig.get('computed')" in body, (
            "available 必须豁免 computed（派生信号无 ts）")

    def test_native_value_exempts_computed(self):
        """★ 本次修的正是这里：漏了这一处豁免 → 实体永远 unknown。"""
        body = self._prop_src("native_value")
        assert 'sig_now.get("computed")' in body, (
            "native_value 的「从未上报」判定必须豁免 computed —— "
            "否则派生信号（总续航等）恒为 unknown")

    def test_both_guards_mention_computed_together(self):
        """哨兵：两个属性都要提 computed，避免只在其中一处修（本次事故形态）。"""
        both = self._prop_src("available") + self._prop_src("native_value")
        assert both.count("computed") >= 2, (
            "computed 豁免必须在 available 与 native_value 两处都出现")
