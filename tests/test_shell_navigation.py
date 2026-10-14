"""总卡片（外壳）导航 —— 回归测试（2026-10-14）。

车主反馈
--------
「不是说13个就是车控的，不要搞13张。只要一张显示就好了。
  现在其他人设置第一页主页，下面的都无法操作。点击都回到首页」

查出两个真 bug：
① **子卡片从不派发 `lx-navigate`**，只调 `history.pushState` + `location-changed`。
   外壳本来靠猴补丁拦 `pushState`，一旦被 HA 路由绕过，点击就会**真的切 HA 视图**
   → 表现为"点击都回到首页"。
② **入口接线写在 `_build()` 里、且在快捷键网格的早退之后**：
       if (!avail.length) { q.innerHTML = "…"; return; }   // ★ 早退
       … wire("#c-batt", …)                                  // ← 被跳过
   首帧实体未就绪（HA 刚启动）→ `avail=0` → 入口永远接不上线，且 `_build` 只跑一次
   → 整个车控页变成"只能看不能点"。

本文件把这两条钉住。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
APP_HOME = CARDS / "lixiang-app-home.js"
SHELL = CARDS / "lixiang-app.js"

PAGE_CARDS = sorted(
    p for p in CARDS.glob("lixiang-*.js")
    if re.search(r"-(page|home)\.js$", p.name)
)


def _strip_comments(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i)
            i = n if j < 0 else j + 2
        else:
            out.append(s[i]); i += 1
    return "".join(out)


class TestChildrenDispatchNavigateEvent:
    def test_there_are_page_cards(self):
        assert len(PAGE_CARDS) >= 10, f"页面卡片太少（{len(PAGE_CARDS)}），断言可能空转"

    def test_every_page_card_has_helper(self):
        """有导航的页面卡必须有 lxNavigate（lixiang-info-page 是共享渲染器、无导航，跳过）。"""
        checked = 0
        for f in PAGE_CARDS:
            src = _strip_comments(f.read_text(encoding="utf-8"))
            if "history.pushState" not in src:
                continue                      # 该卡片本身不导航
            checked += 1
            assert "function lxNavigate" in src, (
                f"{f.name}: 缺 lxNavigate 助手（子卡片必须显式通知外壳，否则会跳回首页）")
            assert "lx-navigate" in src, f"{f.name}: 未派发 lx-navigate 事件"
        assert checked >= 10, f"实际检查的卡片太少（{checked}），断言可能空转"

    def test_helper_asks_parent_first(self):
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        i = s.find("function lxNavigate")
        body = s[i:i + 700]
        assert "cancelable: true" in body, "事件必须可取消（父级 preventDefault 表示已接管）"
        assert "if (handled) return;" in body, "被父级接管后不得再改 URL"
        assert "history.pushState" in body, "未被接管时必须回退 HA 路由（保持独立用法可用）"

    def test_no_bare_pushstate_left_in_page_cards(self):
        """页面卡里不应再有"裸 pushState + location-changed"的旧写法。"""
        for f in PAGE_CARDS:
            s = _strip_comments(f.read_text(encoding="utf-8"))
            pat = re.compile(
                r'history\.pushState\(null,\s*"",[^)]*\);\s*\n\s*'
                r'(?:this\.)?dispatchEvent\(\s*new CustomEvent\("location-changed"')
            assert not pat.search(s), (
                f"{f.name}: 仍有旧导航写法（未先问外壳）—— 会导致『点击回到首页』")


class TestShellHandlesNavigate:
    def test_shell_listens_and_prevents_default(self):
        s = _strip_comments(SHELL.read_text(encoding="utf-8"))
        assert 'addEventListener("lx-navigate"' in s, "外壳未监听 lx-navigate"
        i = s.find('addEventListener("lx-navigate"')
        seg = s[i:i + 400]
        assert "preventDefault()" in seg, "外壳接管时必须 preventDefault（阻止改 URL）"
        assert "this.show(" in seg, "外壳接管时应内部切换页面"

    def test_shell_installs_pushstate_hook_as_fallback(self):
        s = _strip_comments(SHELL.read_text(encoding="utf-8"))
        assert "_installNavHook" in s and "__lxNavTargets" in s, "缺少 pushState 兜底拦截"


class TestEntryWiringNotSkipped:
    """★ 核心：入口接线不能被"快捷键为空"的早退跳过。"""

    def _build_body(self) -> str:
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        i = s.find("_build() {")
        assert i > 0
        m = re.search(r"\n  _\w+\(", s[i + 10:])
        return s[i:i + 10 + m.start()] if m else s[i:]

    def test_wire_nav_called_from_build(self):
        body = self._build_body()
        assert "this._wireNav();" in body, "_build() 没有接线入口（应为无条件调用）"

    def test_no_early_return_before_wire(self):
        body = self._build_body()
        cut = body.find("this._wireNav();")
        assert cut > 0
        head = body[:cut]
        # 早退模式：`return;`（非 return 值）
        assert not re.search(r"\n\s+return;\s*\n", head), (
            "_build() 在接线之前仍有 return;（快捷键为空时会跳过入口接线 → 页面点不动）")

    def test_grid_render_extracted_and_repeatable(self):
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        assert "_renderQuick(warmup)" in s, "快捷键网格渲染未抽成可重复调用的方法"
        assert "_renderQuick(warmup) {" in s, "缺 _renderQuick 定义"
        body = self._build_body()
        assert "this._renderQuick(warmup);" in body, "_build() 未调用 _renderQuick"

    def test_grid_rebuilds_when_entities_arrive(self):
        """首帧没实体 → 网格为空；实体到位后必须能重建（否则永远显示『暂无』）。"""
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        assert re.search(r'if \(!this\.querySelector\("#quick \.q"\)\) this\._renderQuick\(false\);', s), (
            "更新链路里缺少「网格为空则重建」的逻辑？")

    def test_wire_nav_is_idempotent(self):
        s = _strip_comments(APP_HOME.read_text(encoding="utf-8"))
        i = s.find("_wireNav() {")
        assert i > 0, "缺 _wireNav 定义"
        body = s[i:i + 200]
        assert "_navWired" in body, "_wireNav 必须幂等（否则每次调用都重复挂监听）"
