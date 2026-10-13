"""卡片容器查询（container query）—— 回归测试（2026-10-14）。

背景：一个**真实发生过、且没被任何测试拦住**的缺陷
------------------------------------------------
v1.5.7 给卡片加了窄屏断点，写法是：

    :host { container-type: inline-size; }
    @container (max-width: 480px) { .row2 { grid-template-columns: 1fr; } }

但集成的卡片**用的是 light DOM**（`this.appendChild(style)`），
`:host` 只在 shadow DOM 里成立 → `container-type` 从未生效 →
**所有 `@container` 断点一次都没触发过**。

实测（无头浏览器，400px 宽）：
  · 修复前 `.row2` 仍是 2 列、charge 页三栏仍是 3 列
  · 把 `container-type` 挪到 `.root`（真实元素）后 → 1 列 / 2 列，桌面端不受影响

同时发现 v1.5.7 的提交说明声称"app-home 也加了断点"，但 diff 里只有 11 张
页面卡 —— app-home **从未有过断点**。本测试把这两点都钉住。

这两个断言用**源码静态检查**，因为它们描述的正是"源码写法与运行时效果脱节"，
只有把写法约束住才能避免重演。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"

APP_HOME = CARDS / "lixiang-app-home.js"


def _strip_comments(s: str) -> str:
    """去掉 JS 注释 —— 否则注释里提到的 container-type 会污染断言。

    ★ 这不是洁癖：修复时正是注释里写了 `:host{container-type}`（含反引号），
      把模板字符串提前闭合导致运行期 SyntaxError，而 `node --check` 没报。
    """
    out, i, n = [], 0, len(s)
    while i < n:
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i)
            i = n if j < 0 else j + 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _cards_with_container_rules() -> list[Path]:
    out = []
    for f in sorted(CARDS.glob("*.js")):
        if "@container" in _strip_comments(f.read_text(encoding="utf-8")):
            out.append(f)
    return out


class TestContainerTypeIsEffective:
    def test_some_cards_actually_use_container_queries(self):
        """没有卡片用容器查询的话，下面的断言会变成空转。"""
        files = _cards_with_container_rules()
        assert len(files) >= 8, f"用容器查询的卡片太少（{len(files)}）—— 断言可能空转"

    def test_container_type_not_only_on_host(self):
        """★ 核心断言：container-type 不能只挂在 `:host` 上。

        light DOM 卡片的 `:host` 规则不匹配任何元素 → 容器查询永不触发。
        除非该卡片真的用了 shadow DOM（`attachShadow`）。
        """
        bad = []
        for f in _cards_with_container_rules():
            s = _strip_comments(f.read_text(encoding="utf-8"))
            decls = re.findall(r"([^{}]+)\{([^}]*container-type[^}]*)\}", s)
            on_real_selector = [sel for sel, _ in decls if ":host" not in sel]
            uses_shadow = "attachShadow" in s
            if not on_real_selector and not uses_shadow:
                bad.append(f.name)
        assert not bad, (
            "这些卡片有 @container 规则，但 container-type 只写在 :host 上"
            "（light DOM 下不生效，断点永远不会触发）：\n  " + "\n  ".join(bad))

    def test_real_container_element_is_root(self):
        """容器必须挂在真实根元素上（本集成统一是 `.root`）。"""
        for f in _cards_with_container_rules():
            s = _strip_comments(f.read_text(encoding="utf-8"))
            if "attachShadow" in s:
                continue
            m = re.search(r"\.root\s*\{[^}]*container-type", s)
            assert m, f"{f.name}: .root 上没有 container-type，窄屏断点不会生效"


class TestAppHomeMobileBreakpoints:
    """app-home 的手机断点 —— v1.5.7 曾声称加过，实际从未加。"""

    def test_has_mobile_breakpoint(self):
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        assert "@container (max-width: 480px)" in s, (
            "app-home 缺少 ≤480px 断点（v1.5.7 的提交说明曾声称有，实际没有）")

    def test_mobile_breakpoint_covers_quick_grid(self):
        """手机上快捷键要从 4 列收成 2 列。"""
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        i = s.find("@container (max-width: 480px)")
        seg = s[i:i + 600]
        assert "repeat(2,minmax(0,1fr))" in seg.replace(" ", ""), (
            "手机断点里没有把 .quick 收成 2 列")

    def test_mobile_breakpoint_covers_row2_and_entries(self):
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        i = s.find("@container (max-width: 480px)")
        seg = s[i:i + 600]
        assert ".row2" in seg and ".entries" in seg, "手机断点没覆盖 .row2 / .entries"


class TestNoStrayBacktickInStyleTemplate:
    """STYLE 是模板字符串：正文里出现反引号会把它提前闭合。

    实测踩过：注释里写 `:host{container-type}` → 运行期 SyntaxError，
    而 `node --check` 不报（对 module 的模板字符串不做这层检查）。
    """

    @pytest.mark.parametrize("f", sorted(CARDS.glob("*.js")), ids=lambda p: p.name)
    def test_template_literal_balanced(self, f: Path):
        s = f.read_text(encoding="utf-8")
        m = re.search(r"const STYLE\s*=\s*`", s)
        if not m:
            pytest.skip("无 STYLE 模板")
        start = m.end() - 1                      # 指向开引号
        end = s.find("`;", start + 1)
        assert end > 0, f"{f.name}: STYLE 模板未正常闭合（疑似内部有裸反引号）"
        inner = s[start + 1:end]
        assert "`" not in inner, (
            f"{f.name}: STYLE 模板内部出现反引号 —— 会提前闭合模板字符串")
