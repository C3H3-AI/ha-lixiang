"""二级页「手机右划返回」必须回到车控主页，而不是退出到 HA 主界面。

★ 2026-10-28 车主反馈：左上角返回按钮正常，但手机右划会退回 HA 主页。
根因：外壳（lixiang-app）拦截 pushState 后只做内部切换、**不入历史栈**，
      右划触发浏览器 history.back()，栈里没有内部页面 → 直接退回 HA 视图。
修法：进二级页压带 __lxNav 标记、URL 不变的栈位 + capture 阶段接管 popstate。
"""
from __future__ import annotations

import re
from pathlib import Path

CARDS = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"


def _app_src() -> str:
    return (CARDS / "lixiang-app.js").read_text(encoding="utf-8")


class TestBackGesture:
    def test_popstate_guard_installed(self):
        """必须注册 popstate 监听（否则右划不被接管）。"""
        src = _app_src()
        assert "addEventListener(\"popstate\"" in src, "缺少 popstate 监听 —— 右划会退回 HA"
        assert "stopImmediatePropagation" in src, "必须拦下 HA 的默认响应"

    def test_popstate_registered_in_capture_phase(self):
        """capture 阶段才能抢在 HA 之前执行。"""
        src = _app_src()
        m = re.search(r'addEventListener\("popstate"[^)]*\)', src)
        assert m, "找不到 popstate 注册"
        assert ", true)" in m.group(0), "popstate 必须以 capture=true 注册（抢在 HA 前）"

    def test_enters_subpage_pushes_marked_state(self):
        """进二级页要压栈，且带 __lxNav 标记。"""
        src = _app_src()
        assert "__lxNav:" in src, "压栈状态必须带 __lxNav 标记"
        assert "_syncHistory" in src, "缺少历史栈同步逻辑"

    def test_url_unchanged_when_pushing(self):
        """压栈必须用 location.href（URL 不变），否则 HA 会去切不存在的视图。"""
        src = _app_src()
        block = src[src.index("_syncHistory(prev, key) {"):src.index("_onPop(ev) {")]
        assert "location.href" in block, "压栈应保持当前 URL"

    def test_on_pop_returns_to_app(self):
        """popstate 里必须切回 app 主页。"""
        src = _app_src()
        block = src[src.index("_onPop(ev) {"):src.index("_childConfig() {")]
        assert 'show("app")' in block, "右划必须切回车控主页"

    def test_cleanup_removes_listener(self):
        """卡片卸载时要移除监听，避免泄漏。"""
        src = _app_src()
        assert "removeEventListener(\"popstate\"" in src, "卸载时必须移除 popstate 监听"

    def test_popping_guard_prevents_loop(self):
        """popstate 触发的切换不能再压栈/弹栈，否则死循环。"""
        src = _app_src()
        assert "_popping" in src, "缺少防循环标志"
        block = src[src.index("_syncHistory(prev, key) {"):src.index("_onPop(ev) {")]
        assert "this._popping" in block, "_syncHistory 必须检查 _popping"
