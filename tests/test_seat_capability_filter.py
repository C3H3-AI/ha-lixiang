"""座椅页 —— 模式能力过滤 + 空排隐藏（2026-10-11）。

背景
----
座椅页与空调页同构，但**多一个层级的问题**：

1. 模式区（空调/极速制冷/极速制热/除雪除冰）原先是局部 `MODES` + 无条件全部渲染
2. ★ **座椅区**：`row2seat`（主驾/副驾）与 `row3seat`（二排左/中/右）是**硬编码布局**。
   即使每个座椅的按钮都按 `_eid()` 过滤掉了，整排容器**仍会渲染**
   → 出现"一个空座椅图形，点不动"（5 座车的二排中、或只有前排加热的车）

改造后
------
- `_modes()` / `_modeSupported()`：与空调页同构
- `_seatHtml()` 无任何可控件 → 返回空串；整排全空 → 整排容器不出现
- 回读 `MODES` 从 `_modes()` 派生（消除第二份硬编码）

★ 测试从源文件抽取真方法执行，不抄副本。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-seat-page.js"


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


ICONS = ("const ICON_HEAT = 'H'; const ICON_FAN = 'F';")


def harness(cfg: dict, states: dict, methods=("_modes", "_modeSupported", "_seatHtml"),
            call: str = "") -> str:
    src = PAGE.read_text(encoding="utf-8")
    members = "\n".join(_as_member(extract_method(src, n)) for n in methods)
    return (
        f"{ICONS}\n"
        "const __iconBase = '/local/lixiang-icons';\n"
        f"const CFG = {json.dumps(cfg, ensure_ascii=False)};\n"
        f"const STATES = {json.dumps(states, ensure_ascii=False)};\n"
        "const WARMUP = false;\n"
        "const G = {\n"
        "  _config: CFG, _hass: { states: STATES },\n"
        "  _autoBind: () => ({}),\n"
        "  _eid(f) { const m = this._config[f];\n"
        "    if (typeof m === 'string' && m.includes('.')) return m;\n"
        "    return null; },\n"
        "  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; },\n"
        f"{members}\n"
        "};\n"
        + call
    )


MODES_CFG = {"ac": "climate.x", "ac_fast_cold": "switch.x_cold",
             "ac_fast_hot": "switch.x_hot", "ac_defrost": "switch.x_def"}


def mode_support(cfg, states, warmup=False):
    """返回 {modeKey: supported}（warmup 显式传入，避免读错分支）"""
    call = ("process.stdout.write(JSON.stringify(G._modes().map(m => "
            f"[m.key, G._modeSupported(m, {str(warmup).lower()})])));\n")
    return dict(json.loads(run_node(harness(cfg, states, call=call))))


def seat_html(cfg, states, keys, label, opts=None):
    opts_js = json.dumps(opts or {}, ensure_ascii=False)
    call = ("process.stdout.write(G._seatHtml("
            f"{json.dumps(keys, ensure_ascii=False)}, {json.dumps(label, ensure_ascii=False)}, {opts_js}));\n")
    return run_node(harness(cfg, states, methods=("_seatHtml",), call=call))


class TestModeFilter:
    def test_all_available_when_entities_exist(self):
        states = {v: {"state": "off"} for v in MODES_CFG.values()}
        got = mode_support(MODES_CFG, states)
        assert set(got) == {"ac", "cool", "heat", "defrost"}
        assert all(got.values())

    def test_missing_entity_hides_mode(self):
        cfg = dict(MODES_CFG); cfg.pop("ac_fast_hot")
        states = {v: {"state": "off"} for v in cfg.values()}
        got = mode_support(cfg, states)
        assert got["heat"] is False and got["cool"] is True

    def test_warmup_lenient(self):
        assert mode_support(MODES_CFG, {}, warmup=True)["ac"] is True
        assert mode_support(MODES_CFG, {}, warmup=False)["ac"] is False

    def test_mode_fields_present(self):
        call = "process.stdout.write(JSON.stringify(G._modes().map(m => [!!m.name, !!m.icon, !!m.src])));\n"
        got = json.loads(run_node(harness(MODES_CFG, {}, call=call)))
        assert all(all(x) for x in got), "每个模式都要有 name/icon/src"


class TestSeatRowHiding:
    """★ 整排无控件 → 整排不渲染（本轮新增的核心）。"""

    def test_seat_with_both_shows(self):
        html = seat_html({"seat_fl_heat": "fan.x_h", "seat_fl_vent": "fan.x_v"},
                         {"fan.x_h": {"state": "0"}, "fan.x_v": {"state": "0"}},
                         {"heat": "seat_fl_heat", "vent": "seat_fl_vent"}, "主驾")
        assert 'data-seat="主驾"' in html
        assert 'data-fan="seat_fl_heat"' in html
        assert 'data-fan="seat_fl_vent"' in html

    def test_seat_with_only_heat(self):
        html = seat_html({"seat_fl_heat": "fan.x_h"}, {"fan.x_h": {"state": "0"}},
                         {"heat": "seat_fl_heat", "vent": "seat_fl_vent"}, "主驾")
        assert 'data-fan="seat_fl_heat"' in html
        assert "data-fan=\"seat_fl_vent\"" not in html, "无通风实体就不该渲染通风按钮"

    def test_seat_without_any_returns_empty(self):
        """★ 关键：无任何控件的座椅（5 座车的二排中）→ 返回空串。"""
        html = seat_html({}, {}, {"heat": "seat_rc_heat"}, "二排中", {"bench": True})
        assert html == "", f"无控件座椅应返回空串，实际 {html[:60]!r}"

    def test_bench_flag_preserved(self):
        html = seat_html({"seat_rl_heat": "fan.x"}, {"fan.x": {"state": "0"}},
                         {"heat": "seat_rl_heat"}, "二排左", {"bench": True})
        assert 'class="seat bench"' in html

    def test_config_without_entity_id(self):
        html = seat_html({"seat_fl_heat": {"name": "x"}}, {}, {"heat": "seat_fl_heat"}, "主驾")
        assert html == "", "配置里没给实体 id → 视为不支持"


class TestWiring:
    def test_build_filters_modes(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("const modes = this._modes()")
        blk = src[i:i + 320]
        assert "filter(m => this._modeSupported(m))" in blk
        assert "mempty" in blk, "无可用模式要有空态"

    def test_rows_built_dynamically(self):
        """★ 座椅排必须是「拼出来 + 空则不输出」，不能硬编码两个空容器。"""
        src = PAGE.read_text(encoding="utf-8")
        assert "row2seat" in src and "row3seat" in src
        assert ".filter(Boolean).join" in src, "座椅排应由过滤后的片段拼成"
        assert 'r2 ? `<div class="row2seat">' in src or 'r2 ? `<div class="row2seat">' in src.replace("'", "`")

    def test_readback_map_derived(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("const MODES = {}")
        blk = src[i:i + 200]
        assert "this._modes().forEach" in blk, "回读 MAP 应由 _modes() 派生"

    def test_shell_kept(self):
        src = PAGE.read_text(encoding="utf-8")
        for token in ('id="back"', 'id="dec"', 'id="inc"', 'class="toast"', 'class="sched"'):
            assert token in src, f"外壳元素 {token} 丢了"

    def test_empty_style_present(self):
        assert ".mempty" in PAGE.read_text(encoding="utf-8")


class TestGuardSelfCheck:
    def test_harness_uses_real_source(self):
        assert "_seatHtml" in harness({}, {}, methods=("_seatHtml",))

    def test_extractor_rejects_call_site(self):
        with pytest.raises(ValueError):
            extract_method("  this._modes();", "_modes")