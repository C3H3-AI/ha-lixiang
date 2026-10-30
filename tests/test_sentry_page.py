"""哨兵视频页（UI）—— 服务/注册/接线 的静态契约。

★ 2026-10-28 新增：车主要求「哨兵卡点进去」查看视频。
链路：
  首页「哨兵模式」卡 → /lixiang/sentry
  → lixiang_auto.get_sentinel_videos（列表）
  → lixiang_auto.get_file_urls（filekey → 有时效签名 URL）
  → 封面缩略图 + 点播（H.265 不支持时降级为下载）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "lixiang_auto"
CARDS = PKG / "www" / "lixiang-cards"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestSentryServices:
    def test_services_registered(self):
        import yaml
        d = yaml.safe_load(_read(PKG / "services.yaml"))
        assert "get_sentinel_videos" in d
        assert "get_file_urls" in d
        f = d["get_file_urls"]["fields"]
        assert "file_keys" in f, "get_file_urls 必须接受 file_keys"

    def test_constants_and_handlers_exist(self):
        src = _read(PKG / "__init__.py")
        for frag in (
            'SERVICE_GET_SENTINEL_VIDEOS = "get_sentinel_videos"',
            'SERVICE_GET_FILE_URLS = "get_file_urls"',
            "async def _handle_get_sentinel_videos",
            "async def _handle_get_file_urls",
        ):
            assert frag in src, f"__init__.py 缺 {frag}"

    def test_handlers_support_response(self):
        """卡片要靠返回值渲染 → 两个服务都必须 supports_response。"""
        src = _read(PKG / "__init__.py")
        for const in ("SERVICE_GET_SENTINEL_VIDEOS", "SERVICE_GET_FILE_URLS"):
            i = src.index(f"async_register(DOMAIN, {const}")
            seg = src[i:i + 260]
            assert "supports_response=SupportsResponse.OPTIONAL" in seg, (
                f"{const} 未声明 supports_response，卡片拿不到数据")


class TestSentryPageCard:
    def test_page_file_exists_and_defines_element(self):
        f = CARDS / "lixiang-sentry-page.js"
        assert f.exists()
        s = _read(f)
        assert 'const CARD_TAG = "lixiang-sentry-page"' in s
        assert "customElements.define(CARD_TAG" in s

    def test_registered_in_page_map(self):
        """外壳 PAGES 必须能映射到该页面，否则导航过来是空白。"""
        s = _read(CARDS / "lixiang-app.js")
        assert re.search(r'sentry:\s*"lixiang-sentry-page"', s), (
            "lixiang-app.js 的 PAGES 未注册 sentry")

    def test_included_in_bundle_build_order(self):
        """构建清单漏了它 → bundle 里没有该元素 → 页面白屏（实测踩过）。"""
        s = _read(ROOT / "scripts" / "build-cards.mjs")
        assert '"lixiang-sentry-page.js"' in s, (
            "build-cards.mjs 的 ORDER 漏了哨兵页，单文件版会缺这个元素")

    def test_page_uses_services_with_return_response(self):
        """页面必须用 returnResponse 拿返回值（否则只能拿到 undefined）。"""
        s = _read(CARDS / "lixiang-sentry-page.js")
        assert s.count("true,") >= 0
        for svc in ("get_sentinel_videos", "get_file_urls"):
            assert svc in s, f"页面未调用 {svc}"
        assert "undefined, true, true," in s or ", true, true," in s, (
            "callService 需请求服务响应（notify=true, returnResponse=true）")

    def test_hevc_fallback_present(self):
        """H.265 兼容性必须探测并降级，不能只给黑屏 video。"""
        s = _read(CARDS / "lixiang-sentry-page.js")
        assert "_canHevc" in s
        assert "hvc1" in s and "hev1" in s
        assert "下载观看" in s, "不支持 H.265 时必须提供下载入口"


class TestSentryCardWiring:
    def test_home_sentry_card_navigates(self):
        """首页哨兵卡点击 → 导航到 /lixiang/sentry（不再是直接开关）。"""
        s = _read(CARDS / "lixiang-app-home.js")
        i = s.index('const senEl = this.querySelector("#c-sentry")')
        seg = s[i:i + 600]
        assert "/lixiang/sentry" in seg, "首页哨兵卡未导航到哨兵页"
        assert "查看哨兵视频" in seg, "无障碍标签应更新为「查看哨兵视频」"

    def test_page_keeps_sentry_switch(self):
        """开关挪到页内，不能丢失控制能力。"""
        s = _read(CARDS / "lixiang-sentry-page.js")
        assert "_toggleSentry" in s
        assert 'callService("switch"' in s


class TestServiceResponseContract:
    """卡片与后端之间的响应契约（这三处曾真出过 bug）。"""

    def test_page_unwraps_ha_service_response(self):
        """HA callService 把服务结果包在 {response: ...} 里 —— 必须解包。

        不解包 → 页面把 'response' 当成 VIN 键 → 列表永远空。
        """
        s = _read(CARDS / "lixiang-sentry-page.js")
        assert "res.response" in s, "页面未解 HA 的 {response:} 包装"

    def test_file_urls_handler_extracts_data_urls(self):
        """get_svm_photo_urls 返回的是原始 API 响应，handler 必须拆出 data.urls。

        直接透传 → 前端拿不到 filekey→URL 映射 → 封面全显示「无封面」。
        """
        src = _read(PKG / "__init__.py")
        i = src.index("async def _handle_get_file_urls")
        seg = src[i: i + 2600]
        assert 'raw.get("data")' in seg, "handler 未读取响应的 data 字段"
        assert 'urls = data_obj.get("urls")' in seg, "handler 未拆出 data.urls"
        assert '"urls": urls' in seg, "handler 未把 urls 映射返回给前端"

    def test_file_keys_is_text_selector(self):
        """file_keys 用 text 选择器（前端传逗号串）。

        用 object 选择器而前端传数组 → 服务参数校验可能拒绝。
        """
        import yaml
        d = yaml.safe_load(_read(PKG / "services.yaml"))
        sel = d["get_file_urls"]["fields"]["file_keys"]["selector"]
        assert "text" in sel, f"file_keys 选择器应为 text，实际 {sel}"

    def test_frontend_sends_comma_string(self):
        """前端按 text 选择器约定，传逗号分隔字符串而非数组。"""
        s = _read(CARDS / "lixiang-sentry-page.js")
        assert 'file_keys: need.join(",")' in s, "前端未按逗号串传 file_keys"

    def test_event_limit_applied_after_filtering(self):
        """limit 必须作用于「过滤后的有效事件」，与 App 列表语义一致。"""
        src = _read(PKG / "li_api.py")
        i = src.index("def _parse_sentinel_events")
        seg = src[i: i + 1800]
        # 过滤空视频的分支必须在 append 之前
        assert "if not vids:" in seg and "continue" in seg
        assert "len(events) >= max(0, limit)" in seg, "limit 未按过滤后计数"
