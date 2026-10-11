"""首页「插电标识」（2026-10-12）。

背景
----
车主两次发来 App 首页截图（同一分钟、同一电量 100%），差异是：

    图 A：车辆图**小**，**无充电桩**  → 直接打开
    图 B：车辆图**大**，**有充电桩**  → 向上滑动后

车主明确：**「插电的时候显示」** —— 也就是**充电桩只在插枪时出现**。

App 是静态图方案；我们用 **3D 车模 + 徽标**表达同一信息，并且把徽标放在**头部**
（而不是 3D 区域）—— 这样 3D 展开/收起时都能看到。

判据
----
`ac_gun`（交流充电枪）/ `dc_gun`（直流充电枪）任一为 on → 显示；
两者都 off 或实体不存在 → 整块隐藏（不留空隙）。

真机实测（2026-10-12）：`ac_gun=on`、`dc_gun=off` → 应显示「交流慢充已插枪」。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
HOME = CARDS / "lixiang-app-home.js"
BIND = CARDS / "lixiang-auto-bind.js"


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


def _strip_comments(s: str) -> str:
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'^\s*//.*$', '', s, flags=re.M)
    return s


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:700]
    return r.stdout


def _plug_block() -> str:
    """从源码抽出**完整**的插电判定块（含 if/else），不抄副本。

    ★ 初版按行过滤"只留判定逻辑"，结果把 if/else 的内容也删掉了 →
      抽出来是个空壳，node 直接语法错误。改为整块取出，用 stub 承接 DOM 操作。
    """
    s = _src()
    i = s.index('const plugEl = q("#v-plug");')
    j = s.index('\n', s.index('plugEl.style.display = "none";', i)) + 1
    # 补上收尾的 if 大括号
    tail = s[j:]
    k = tail.index("\n    }") + len("\n    }")
    return s[i:j + k]


class TestMarkup:
    def test_badge_present(self):
        s = _src()
        assert 'class="plug" id="v-plug"' in s, "缺插电徽标"
        assert 'id="v-plug-t"' in s, "缺徽标文案节点"

    def test_hidden_by_default(self):
        s = _src()
        i = s.index('id="v-plug"')
        assert "display:none" in s[max(0, i - 120):i + 120], "徽标默认应隐藏"

    def test_in_header_not_3d_area(self):
        """★ 徽标必须在**头部** —— 3D 收起后仍要可见。"""
        s = s_ = _src()
        i_head = s.index('class="head" id="head"')
        i_plug = s.index('id="v-plug"')
        i_big3d = s.index('class="big3d"') if 'class="big3d"' in s else len(s)
        assert i_head < i_plug < i_big3d, "徽标不在头部区间"

    def test_uses_charging_icon(self):
        s = _src()
        i = s.index('id="v-plug"')
        assert "icon_charge_lighting" in s[i:i + 300], "缺充电图标"

    def test_css_present(self):
        s = _src()
        assert re.search(r'^\s*\.plug\s*\{', s, re.M), "缺 .plug 样式"
        assert ".plug img" in s and "dark" in s.lower(), "缺图标尺寸或暗色适配"


class TestBindings:
    def test_ac_and_dc_gun_rules_exist(self):
        """判据依赖 ac_gun / dc_gun —— auto-bind 必须能给出它们。"""
        ab = BIND.read_text(encoding="utf-8")
        assert "ac_gun:" in ab and "dc_gun:" in ab, "auto-bind 缺 ac_gun/dc_gun 规则"

    def test_matches_live_entities(self):
        """真机实测的枪状态实体名（防止规则漂移）。"""
        ab = BIND.read_text(encoding="utf-8")
        i = ab.index("ac_gun:")
        seg = ab[i:i + 200]
        assert "充电枪" in seg, f"ac_gun 规则未按「充电枪」匹配: {seg[:80]}"


class TestLogic:
    """node 真跑判定块，覆盖四种组合（含"一个都没插"必须隐藏）。"""

    def _run(self, ac, dc):
        code = (
            "let shown = 'none', text = '';\n"
            "const plugBox = { style: { set display(v) { shown = v; } } };\n"
            "const plugTxt = { set textContent(v) { text = v; } };\n"
            "const q = (s) => s === '#v-plug' ? plugBox\n"
            "                 : s === '#v-plug-t' ? plugTxt : null;\n"
            "const G = {\n"
            "  _on: (v) => v === true,\n"
            f"  _eid: (k) => k === 'ac_gun' ? {'true' if ac else 'null'} "
            f": (k === 'dc_gun' ? {'true' if dc else 'null'} : null),\n"
            "};\n"
            + _plug_block().replace("this._on", "G._on").replace("this._eid", "G._eid")
            + "console.log(JSON.stringify({ shown, text }));\n"
        )
        return json.loads(run_node(code))

    def test_ac_only(self):
        r = self._run(True, False)
        assert r["shown"] == "", "交流枪插入应显示"
        assert "交流" in r["text"], f"文案应说明是交流枪: {r['text']}"

    def test_dc_only(self):
        r = self._run(False, True)
        assert r["shown"] == "", "直流枪插入应显示"
        assert "直流" in r["text"], f"文案应说明是直流枪: {r['text']}"

    def test_both_prefers_dc(self):
        r = self._run(True, True)
        assert r["shown"] == ""
        assert "直流" in r["text"], "两枪都插时应优先提示直流"

    def test_none_hidden(self):
        """★ 没插枪必须隐藏（否则就是个假状态 —— 本项目已踩过 key_connected 的坑）。"""
        r = self._run(False, False)
        assert r["shown"] == "none", f"未插枪时徽标必须隐藏，实际显示 {r['shown']!r}"


class TestNoFakeStatusRegression:
    """回归：不能再出现「拿不存在的绑定键显示状态」这类假状态。"""

    def test_key_connected_still_absent(self):
        ab = BIND.read_text(encoding="utf-8")
        assert "key_connected" not in ab, "key_connected 又回来了？"

    def test_plug_uses_real_keys(self):
        s = _strip_comments(_src())
        assert 'this._eid("ac_gun")' in s and 'this._eid("dc_gun")' in s, \
            "插电标识必须用真实绑定键"


class TestSyntax:
    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(HOME)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]