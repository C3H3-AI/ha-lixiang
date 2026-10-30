"""总入口卡片 `lixiang-app` —— 一张卡片承载全部页面（2026-10-11）。

为什么做
--------
原先用户要用上这套 UI 需要 **27 次手工操作**：
注册 14 个资源 + 建 13 个 dashboard 视图 + 加 13 次卡片。

现在：
```
① 注册 1 个资源（lixiang-app.js）
② 建 1 个视图
③ 加 1 张卡片：type: custom:lixiang-app
```

设计要点
--------
· **动态 import 全部子卡片** —— 用 `import.meta.url` 解析同级目录，
  兼容 `/lixiang_auto/…` 与 `/local/lixiang-cards/…` 两种部署
· **导航拦截** —— 12 个子卡片写法完全一致（`pushState` + `location-changed`），
  与其改 12 个文件，不如在总卡片里拦截「能映射到内部页面的 URL」→ **子卡片零改动**
  （非本卡片的 URL 原样放行；断开时恢复原函数，用引用计数避免多实例互相拆台）
· **向后兼容** —— 子卡片未被拦截时仍走 HA 路由，所以**多视图用法照样可用**
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
APP = CARDS / "lixiang-app.js"

#: 应与内部页面表一致的子卡片
EXPECT_PAGES = {
    "app", "charge", "energy", "health", "setting", "scene", "climate",
    "seat", "location", "vinfo", "task", "ad", "bindings", "sentry",
}


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:700]
    return r.stdout


def _src() -> str:
    return APP.read_text(encoding="utf-8")


class TestCardRegistered:
    def test_element_registered(self):
        assert 'customElements.define(CARD_TAG, LixiangApp)' in _src()
        assert 'const CARD_TAG = "lixiang-app"' in _src()

    def test_listed_in_custom_cards(self):
        """出现在卡片选择器里，用户才能从 UI 添加。"""
        s = _src()
        assert "window.customCards" in s and "type: CARD_TAG" in s

    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(APP)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]


class TestPageTable:
    def _pages(self) -> dict:
        s = _src()
        i = s.index("const PAGES = {")
        j = s.index("};", i)
        return {m.group(1): m.group(2) for m in
                re.finditer(r'(\w+):\s*"([a-z-]+)"', s[i:j])}

    def test_all_pages_mapped(self):
        assert set(self._pages()) == EXPECT_PAGES, "内部页面表应与卡片清单一致"

    def test_every_mapped_card_file_exists(self):
        """★ 映射的元素名必须有对应的 JS 文件（否则动态 import 会静默失败）。"""
        for key, tag in self._pages().items():
            f = CARDS / f"{tag}.js"
            assert f.exists(), f"{key} → {tag}.js 不存在"

    def test_key_mappings_are_semantically_correct(self):
        """★ 只验证"映射的名字是存在的卡片"是不够的 ——
        `app → lixiang-charge-page` 那个名字也存在，却显然是错的（本测试初版被骗过）。
        这里按首页导航图显式锁定每一页对应的卡片。
        """
        pages = self._pages()
        expect = {
            "app": "lixiang-app-home",
            "charge": "lixiang-charge-page",
            "energy": "lixiang-energy-page",
            "health": "lixiang-health-page",
            "setting": "lixiang-setting-page",
            "scene": "lixiang-scene-page",
            "climate": "lixiang-climate-page",
            "seat": "lixiang-seat-page",
            "location": "lixiang-location-page",
            "vinfo": "lixiang-vehicle-info-page",
            "task": "lixiang-task-page",
            "ad": "lixiang-ad-page",
            "bindings": "lixiang-bindings-card",
        }
        for k, want in expect.items():
            assert pages.get(k) == want, f"{k} 应映射到 {want}，实际 {pages.get(k)}"

    def test_element_names_match_registration(self):
        """★ 映射的元素名必须与子卡片真实注册的 CARD_TAG 一致。"""
        for key, tag in self._pages().items():
            src = (CARDS / f"{tag}.js").read_text(encoding="utf-8")
            m = re.search(r'const CARD_TAG\s*=\s*"([a-z-]+)"', src)
            assert m, f"{tag}.js 找不到 CARD_TAG"
            assert m.group(1) == tag, f"{tag}.js 注册的是 {m.group(1)}，映射不一致"


class TestDynamicLoading:
    def test_uses_import_meta_url(self):
        """★ 必须用 import.meta.url —— 否则从 /local/ 部署时路径会错。"""
        s = _src()
        assert "new URL(\".\", import.meta.url)" in s, "应用 import.meta.url 解析同级目录"

    def test_single_card_failure_tolerated(self):
        """单个子卡片加载失败不应拖垮整体。"""
        s = _src()
        i = s.index("function _loadCards()")
        blk = s[i:i + 900]
        assert "catch(" in blk or ".catch(" in blk, "应有单卡失败兜底"

    def test_loading_cached(self):
        """全局只加载一次（多个卡片实例共享）。"""
        s = _src()
        assert "__loading" in s and "if (__loading) return __loading" in s


class TestNavigationHook:
    def test_pushstate_intercepted(self):
        s = _src()
        assert "_installNavHook" in s
        assert "history.pushState = " in s, "应替换 history.pushState"

    def test_only_known_paths_intercepted(self):
        """★ 只拦能映射到内部页面的 URL，其余原样放行（不影响 HA 自身导航）。"""
        s = _src()
        i = s.index("window.__lxNavHook = function")
        blk = s[i:i + 700]
        assert "t._keyOf(path)" in blk, "应先用页面表判断"
        assert "return orig(state, title, url)" in blk, "未命中必须回退原函数"

    def test_restores_on_disconnect(self):
        """★ 断开时恢复原 pushState（否则会污染整个 HA 页面）。"""
        s = _src()
        assert "disconnectedCallback" in s
        assert "history.pushState = window.__lxNavOrigPush" in s

    def test_refcount_for_multiple_instances(self):
        """★ 引用计数 —— 两个总卡片实例时，前者断开不应拆掉后者要用的钩子。"""
        s = _src()
        assert "__lxNavRefs" in s
        assert "__lxNavRefs -= 1" in s and "__lxNavRefs += 1" in s
        assert "__lxNavRefs <= 0" in s, "只在归零时才恢复"

    def test_internal_event_also_supported(self):
        """双保险：子卡片若派发 lx-navigate 也能处理。"""
        assert "lx-navigate" in _src()


class TestRendering:
    def test_child_instances_cached(self):
        """子卡片只创建一次（保留展开状态/滚动位置）。"""
        s = _src()
        i = s.index("show(key) {")
        blk = s[i:i + 900]
        # ★ 必须断言**完整表达式** —— 只查 "_instances[tag]" 的话，
        #   `let el = null` 这种"不查缓存"的变异照样满足（本测试初版就被骗过）
        assert "let el = this._instances[tag]" in blk, "应从缓存取实例（否则每次重建、丢状态）"
        assert "this._instances[tag] = el" in blk, "创建后要存回缓存"

    def test_hass_pushed_to_all(self):
        """hass 必须传给所有已创建子卡片（含未显示的，避免切回来是空白）。"""
        s = _src()
        i = s.index("_pushHass() {")
        blk = s[i:i + 500]
        assert "Object.values(this._instances)" in blk

    def test_unknown_key_ignored(self):
        """未知 key 不应炸。"""
        s = _src()
        i = s.index("show(key) {")
        assert "if (!PAGES[key]" in s[i:i + 200]

    def test_starts_with_loading_placeholder(self):
        """加载期间显示占位，避免白屏。"""
        assert "正在加载" in _src()

    def test_replace_children(self):
        """切换用 replaceChildren（不是 append，避免堆叠）。"""
        assert "replaceChildren" in _src()


class TestKeyMapping:
    """node 真跑 `_keyOf` 的映射逻辑。"""

    def _fn(self) -> str:
        s = _src()
        i = s.index("_keyOf(path) {")
        j = s.index("\n  }", i) + 4
        body = s[i:j]
        # 替换 class 方法为独立函数
        body = body.replace("_keyOf(path) {", "function _keyOf(path) {")
        pages = s[s.index("const PAGES = {"):s.index("};", s.index("const PAGES = {")) + 2]
        return pages + "\n" + body

    def test_maps_full_paths(self):
        out = run_node(self._fn() + "\n" +
                       'console.log(["/lixiang/charge","/lixiang/app","/lixiang/task"]'
                       '.map(p=>_keyOf(p)).join(","));')
        assert out.strip() == "charge,app,task"

    def test_maps_bare_key(self):
        out = run_node(self._fn() + '\nconsole.log(_keyOf("seat"));')
        assert out.strip() == "seat"

    def test_unknown_returns_null(self):
        out = run_node(self._fn() + '\nconsole.log(String(_keyOf("/lovelace/0")));')
        assert out.strip() == "null", "HA 自己的路径不能被误拦"

    def test_empty_safe(self):
        out = run_node(self._fn() +
                       '\nconsole.log([null,undefined,""].map(v=>String(_keyOf(v))).join(","));')
        assert out.strip() == "null,null,null"


class TestBackwardCompatible:
    def test_children_still_fallback_to_ha_route(self):
        """★ 向后兼容：子卡片未被拦截时仍走 HA 路由（多视图用法照常可用）。

        这是一个**约定测试** —— 只要子卡片保留 pushState，多视图就还能用；
        总卡片只是"优先级更高"的拦截者。
        """
        sample = CARDS / "lixiang-charge-page.js"
        s = sample.read_text(encoding="utf-8")
        assert "history.pushState" in s, \
            "子卡片必须保留 pushState 回退（否则多视图用法会失效）"