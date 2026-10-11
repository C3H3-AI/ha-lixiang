"""车辆设置页 —— 数据驱动改造（2026-10-11）。

背景
----
改造前 `lixiang-setting-page.js` 的 `_build()` 里手写了大段 innerHTML，
每个功能一行 `S.includes("xxx") ? swRow(...) : ""`：

- **改一个功能要动两处**（`_grpKeys` 的分组数组 + 模板里的三元表达式）
- 区块里**一个功能都不支持时仍会渲染一个空盒子**（只有行被过滤，`<div class="sec">` 还在）

改造后：
- 页面结构由一张 `SECTIONS` 表决定（key / 类型 / 名称 / 图标 / 副标题）
- 行与**区块**都按「实体是否存在」过滤 → 这台车没有的功能整块不出现
- 顺带与首页一致：**不猜车型**，能力由实体存在性表达

★ 测试直接执行源文件里的真方法（按大括号配平抽取），不在测试里抄副本 ——
  本轮首页那次教训：测副本时"删掉产品代码"这种变异照样全绿。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-setting-page.js"


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
    """按大括号配平抽出**方法定义**（行首缩进 → 不匹配调用点）。"""
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
    """方法定义 → 对象字面量成员（去掉外层花括号，补逗号）。"""
    code = code.strip()
    sig = code.split("{", 1)[0]
    body = code[code.index("{") + 1: code.rindex("}")]
    return f"{sig}{{{body}}},"


def harness(consts: str = "") -> str:
    """拼宿主：注入 _grp/_st 依赖 + 被测方法（真实现，非副本）。"""
    src = PAGE.read_text(encoding="utf-8")
    members = "\n".join(
        _as_member(extract_method(src, n))
        for n in ("_rowSupported", "_renderSections", "_sections"))
    return (
        "const __iconBase = '/local/lixiang-icons';\n"
        f"{consts}\n"
        "const G = {\n"
        "  _config: CFG, _hass: { states: STATES },\n"
        "  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; },\n"
        "  _grp(group, key) { const m = (this._config[group] || {})[key];\n"
        "    if (typeof m === 'string' && m.includes('.')) return m;\n"
        "    if (m && typeof m === 'object' && m.entity) return Object.assign({}, m);\n"
        "    return null; },\n"
        "  _grpKeys() { return []; },\n"
        f"{members}\n"
        "};\n"
    )


class TestSectionsTable:
    """表结构本身也要校验（否则"表驱动"可能退化成空表）。"""

    def _table(self):
        js = ("const CFG = {};\nconst STATES = {};\n" + harness()
              + "process.stdout.write(JSON.stringify(G._sections()));")
        return json.loads(run_node(js))

    def test_table_shape(self):
        """四个区块、每个都有行。"""
        got = self._table()
        assert [x["title"] for x in got] == ["空调与舒适", "充电", "安全与辅助", "远程操作"]
        assert all(len(x["rows"]) > 0 for x in got), "有区块为空行 → 表没填全"

    def test_every_row_has_type(self):
        """每行 [key, type, name, icon?] 的 type 必须合法。"""
        got = self._table()
        for sec in got:
            for r in sec["rows"]:
                assert len(r) >= 3, f"行定义太短: {r}"
                assert r[1] in ("sw", "sel", "num", "rng", "btn"), f"非法 type: {r}"

    def test_no_duplicate_keys(self):
        """同一 key 不能在两个区块里出现（否则 DOM id/data 属性会撞）。"""
        got = self._table()
        keys = [r[0] for sec in got for r in sec["rows"]]
        assert len(keys) == len(set(keys)), f"重复 key: {keys}"

    def test_button_prefix_kept(self):
        """buttons 组历史上用 btn_ 前缀（btn_start），表里是 start → 别丢。"""
        src = PAGE.read_text(encoding="utf-8")
        assert 'this._grp("buttons", "btn_" + key)' in src, (
            "必须兼容 btn_ 前缀的历史键名，否则远程启动/闪灯等会消失")


class TestRowFiltering:
    def _rows(self, cfg, states):
        js = (f"const CFG = {json.dumps(cfg, ensure_ascii=False)};\n"
              f"const STATES = {json.dumps(states, ensure_ascii=False)};\n"
              + harness() +
              "const html = G._renderSections();\n"
              "process.stdout.write(JSON.stringify({\n"
              "  secs: (html.match(/<div class=\"sec\">/g) || []).length,\n"
              "  rows: (html.match(/class=\"row/g) || []).length,\n"
              "  html }));")
        return json.loads(run_node(js))

    def test_only_available_rows_render(self):
        cfg = {"switches": {"sentry": "switch.x_sentry", "steer_heat": "switch.x_heat"},
               "numbers": {"ac_temp": "number.x_temp"},
               "buttons": {"find": "button.x_find"}}
        states = {"switch.x_sentry": {"state": "on"}, "switch.x_heat": {"state": "off"},
                  "number.x_temp": {"state": "22"}, "button.x_find": {"state": "unknown"}}
        got = self._rows(cfg, states)
        # 4 个区块里只有「安全与辅助」(sentry)、「远程操作」(find)、「空调与舒适」(ac_temp) 有行
        assert got["secs"] == 3, f"区块数应为 3（充电/其他无实体），实际 {got['secs']}"
        assert 'data-sw="sentry"' in got["html"] and 'data-sw="steer_heat"' in got["html"]
        assert 'data-btn="find"' in got["html"]

    def test_empty_section_disappears(self):
        """★ 整块都不支持 → 区块本身也不出现（原来会留一个空盒子）。"""
        got = self._rows({}, {})
        assert got["secs"] == 0, f"无任何实体时不该渲染区块，实际 {got['secs']}"
        assert "<h2>" not in got["html"]

    def test_row_types_render_correct_markup(self):
        cfg = {"switches": {"sentry": "switch.a"}, "selects": {"charge_mode": "select.b"},
               "numbers": {"ac_temp": "number.c", "charge_limit": "number.d"},
               "buttons": {"find": "button.e"}}
        states = {k: {"state": "0"} for k in ("switch.a", "select.b", "number.c", "number.d", "button.e")}
        html = self._rows(cfg, states)["html"]
        assert 'data-swtoggle="sentry"' in html          # sw
        assert 'data-selval="charge_mode"' in html       # sel
        assert 'data-numval="ac_temp"' in html           # num
        assert 'data-range="charge_limit"' in html       # rng
        assert 'data-btn="find"' in html                  # btn
        assert 'aria-label="降低"' in html and 'aria-label="升高"' in html, "步进按钮要有无障碍标签"

    def test_m_series_partial_support(self):
        """理想ONE 场景：空调有、尾门/滑门类没有 → 只出该出的区块。"""
        cfg = {"numbers": {"ac_temp": "number.m_ac"}, "switches": {"ac_defrost": "switch.m_defrost"}}
        states = {"number.m_ac": {"state": "21"}, "switch.m_defrost": {"state": "0"}}
        got = self._rows(cfg, states)
        assert got["secs"] == 1, "只有「空调与舒适」该出现"
        assert 'data-numval="ac_temp"' in got["html"]
        assert 'data-sw="ac_defrost"' in got["html"]


class TestWiring:
    def test_build_uses_render_sections(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "${this._renderSections()}" in src, "_build 必须调用表驱动渲染"
        assert "<div class=\"sec\">" not in src.split("_build() {", 1)[1][:4000], (
            "_build 里不该再手写 sec 区块（应交给 _renderSections）")

    def test_old_templates_removed(self):
        src = PAGE.read_text(encoding="utf-8")
        for name in ("swRow", "selRow", "numRow", "btnRow"):
            assert f"const {name} =" not in src, f"{name} 局部模板已被表驱动取代，应删除"

    def test_toast_and_topbar_kept(self):
        """★ 重构不能丢外壳：顶栏 / 返回 / toast 必须还在。"""
        src = PAGE.read_text(encoding="utf-8")
        for token in ('id="back"', 'id="refresh"', 'class="toast"', 'id="ptr"'):
            assert token in src, f"外壳元素 {token} 丢了"

    def test_update_loop_intact(self):
        """回读循环不能被重构破坏（它独立于模板）。"""
        src = PAGE.read_text(encoding="utf-8")
        assert "_grpKeys(\"switches\").forEach" in src or '_grpKeys("switches").forEach' in src
        assert "_grpKeys(\"numbers\").forEach" in src or '_grpKeys("numbers").forEach' in src


class TestGuardSelfCheck:
    def test_harness_uses_real_source(self):
        h = harness()
        assert "_renderSections" in h and "_rowSupported" in h and "_sections" in h

    def test_extractor_rejects_call_site_only(self):
        with pytest.raises(ValueError):
            extract_method("  this._renderSections();", "_renderSections")