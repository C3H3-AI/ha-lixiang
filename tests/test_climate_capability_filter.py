"""空调页模式区 —— 按车型能力过滤（2026-10-11）。

背景
----
模式按钮（空调 / 极速制冷 / 极速制热 / 除雪除冰 / 后视镜加热）原先是
`_build()` 里一个局部 `MODES` 数组 + **无条件全部渲染** →
没有该功能的车也会出现入口，点了只弹 toast「未接入」。

改造后
------
1. `MODES` 提为 `_modes()` 方法（可测、可复用）
2. 渲染前 `_modeSupported()` 过滤，判据 = **实体是否存在**
   （服务端已按车型能力门控；前端不猜车型 —— 与首页/设置页同一套思路）
3. 无可用模式时显示空态
4. ★ 顺带修一个**潜在漂移**：更新循环里另有一份硬编码 `MAP`
   （ac/cool/heat/defrost/mirror → 字段），改模式表时容易漏改
   → 改为从 `_modes()` 派生，**单一数据源**

★ 测试从源文件抽取真方法执行，不在测试里抄副本。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-climate-page.js"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:700]
    return r.stdout


def extract_method(src: str, name: str) -> str:
    i = src.index(f"\n  {name}(")
    j = src.index("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError(f"{name} 大括号不配平")


def _as_member(code: str) -> str:
    code = code.strip()
    sig = code.split("{", 1)[0]
    body = code[code.index("{") + 1: code.rindex("}")]
    return f"{sig}{{{body}}},"


def harness(cfg: dict, states: dict, warmup: bool = False) -> str:
    src = PAGE.read_text(encoding="utf-8")
    members = "\n".join(_as_member(extract_method(src, n)) for n in ("_modes", "_modeSupported"))
    return (
        "const __iconBase = '/local/lixiang-icons';\n"
        f"const CFG = {json.dumps(cfg, ensure_ascii=False)};\n"
        f"const STATES = {json.dumps(states, ensure_ascii=False)};\n"
        f"const WARMUP = {str(warmup).lower()};\n"
        "const G = {\n"
        "  _config: CFG, _hass: { states: STATES },\n"
        "  _autoBind: () => ({}),\n"
        "  _eid(f) { const m = this._config[f];\n"
        "    if (typeof m === 'string' && m.includes('.')) return m;\n"
        "    return null; },\n"
        "  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; },\n"
        f"{members}\n"
        "};\n"
        "process.stdout.write(JSON.stringify(G._modes().map(m => [m.key, G._modeSupported(m, WARMUP)])));\n"
    )


def keys(cfg, states, warmup=False) -> dict:
    return dict(json.loads(run_node(harness(cfg, states, warmup))))


FULL = {"ac": "climate.x", "ac_fast_cold": "switch.x_cold", "ac_fast_hot": "switch.x_hot",
        "ac_defrost": "switch.x_def", "mirror": "switch.x_mirror"}


class TestModeTable:
    def test_five_modes_present(self):
        got = keys(FULL, {v: {"state": "off"} for v in FULL.values()})
        assert set(got) == {"ac", "cool", "heat", "defrost", "mirror"}
        assert all(got.values()), "全部实体存在时都该可用"

    @pytest.mark.parametrize("expr,label", [
        ("[!!m.icon, !!m.name]", "图标/名称齐全"),
        ("m.kind", "kind 合法"),
        ("!!m.field", "field 必须显式给出"),
    ])
    def test_mode_fields_valid(self, expr, label):
        """★ kind/field 决定调用哪个域的服务与实体 —— 缺一个就点不动。"""
        js = harness(FULL, {}).replace(
            "process.stdout.write(JSON.stringify(G._modes().map(m => [m.key, G._modeSupported(m, WARMUP)])));",
            f"process.stdout.write(JSON.stringify(G._modes().map(m => {expr})));")
        got = json.loads(run_node(js))
        if "kind 合法" in label:
            for k in got:
                assert k in ("climate", "switch", "input_boolean", "fan"), f"非法 kind: {k}"
        else:
            assert all(all(x) if isinstance(x, list) else x for x in got), f"{label} 有缺失"


class TestCapabilityFilter:
    def test_missing_entity_hides_mode(self):
        """★ 没有的模式不出现（如纯电车没有极速制热）。"""
        cfg = dict(FULL); cfg.pop("ac_fast_hot")
        got = keys(cfg, {v: {"state": "off"} for v in cfg.values()})
        assert got["heat"] is False, "实体缺失的模式应不可用"
        assert got["cool"] is True

    def test_all_missing_empty_result(self):
        got = keys({}, {})
        assert not any(got.values()), "无任何实体 → 全部不可用（触发空态）"

    def test_config_without_entity_id(self):
        """配置里没写实体（如只写了 {name:...}）→ 不可用。"""
        got = keys({"ac": {"name": "空调"}}, {})
        assert got["ac"] is False

    def test_warmup_lenient(self):
        """★ 首帧实体表未就绪：config 声明过就先渲染，避免闪烁。"""
        got = keys(FULL, {}, warmup=True)
        assert got["ac"] is True, "首帧不应隐藏已配置的模式"
        cold = keys(FULL, {}, warmup=False)
        assert cold["ac"] is False, "非首帧时实体不存在就该隐藏"

    def test_m_series_scenario(self):
        """理想ONE 场景：空调有、除霜/极速制热未必有 → 只出该出的。"""
        cfg = {"ac": "climate.m01", "mirror": "switch.m_mirror"}
        states = {"climate.m01": {"state": "off"}, "switch.m_mirror": {"state": "off"}}
        got = keys(cfg, states)
        assert got["ac"] is True and got["mirror"] is True
        assert got["cool"] is False and got["heat"] is False and got["defrost"] is False


class TestWiring:
    def test_build_filters(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("const modes = this._modes()")
        blk = src[i:i + 400]
        assert "filter(m => this._modeSupported(m))" in blk, "渲染前必须过滤模式"
        assert "mempty" in blk, "无可用模式时要显示空态"

    def test_map_derived_from_modes(self):
        """★ 更新循环的 MAP 必须从 _modes() 派生（不能留第二份硬编码）。"""
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("const MAP = {}")
        blk = src[i:i + 220]
        assert "this._modes().forEach" in blk, "MAP 应由 _modes() 派生"
        # 旧的硬编码形式（ac_fast_cold 等字面量）不应再出现在 MAP 定义里
        assert "ac_fast_cold:" not in blk, "MAP 里仍有硬编码字段（会与模式表漂移）"

    def test_empty_style_present(self):
        assert ".mempty" in PAGE.read_text(encoding="utf-8")

    def test_shell_kept(self):
        """外壳（顶栏/返回/温度盘/定时区/toast）不能丢。"""
        src = PAGE.read_text(encoding="utf-8")
        for token in ('id="back"', 'id="dec"', 'id="inc"', 'id="scheds"', 'class="toast"'):
            assert token in src, f"外壳元素 {token} 丢了"

    def test_tapmode_still_guards_missing(self):
        """点击路径仍要有兜底（配置写了但实体后来没了的情况）。"""
        src = PAGE.read_text(encoding="utf-8")
        assert "未接入" in src, "_tapMode 应保留「未接入」的兜底提示"


class TestGuardSelfCheck:
    def test_harness_uses_real_source(self):
        h = harness(FULL, {})
        assert "_modes" in h and "_modeSupported" in h

    def test_extractor_rejects_call_site(self):
        with pytest.raises(ValueError):
            extract_method("  this._modeSupported(m);", "_modeSupported")