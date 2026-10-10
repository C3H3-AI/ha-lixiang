"""车型资源层（www/lixiang-cards/lixiang-assets.js）—— 回归测试（2026-10-11）。

为什么需要它
-----------
UI 要适用所有车型，前提是**资源层**可靠：
  · 不按车型分支，而是「用户本地图 → 车系剪影 → 通用占位」三级回退
  · 车系能从三条线索之一派生（unityModel / 车型名 / 都没有 → generic）
  · 资源带版本号，HACS 更新后浏览器不会拿旧缓存

★ 关键：JS 行为用 **node 真跑**（不是子串断言）——
  子串断言挡不住「把 seriesOf 改成恒返回 L」这类退化。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
ASSETS = CC / "www" / "lixiang-cards" / "lixiang-assets.js"
PAGE = CC / "www" / "lixiang-cards" / "lixiang-vehicle-info-page.js"
INIT = CC / "__init__.py"

_NODE = None


def node_available() -> bool:
    global _NODE
    if _NODE is None:
        try:
            subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
            _NODE = True
        except Exception:  # noqa: BLE001
            _NODE = False
    return _NODE


def run_node(expr: str, prelude: str = "") -> str:
    """在 node 里加载模块并求值，返回 stdout 字符串。

    prelude 用于注入浏览器全局（node 里没有 window，必须显式 `globalThis.window = ...`）。
    """
    code = (prelude + f"const A = require('{ASSETS}'); process.stdout.write(String({expr}));")
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:400]
    return r.stdout.strip()


pytestmark = pytest.mark.skipif(not node_available(), reason="node 不可用（跳过 JS 行为测试）")


class TestSeriesDerivation:
    """★ 车系必须从任一线索派生；拿不到能力表时也不能白屏。"""

    def test_from_unity_model(self):
        assert run_node("A.seriesOf('L6','')") == "L"
        assert run_node("A.seriesOf('W02','')") == "W"
        assert run_node("A.seriesOf('M01B','')") == "M"

    def test_from_model_name_when_no_unity_model(self):
        """卡片手里往往只有设备注册表的 model（"理想L6"）。"""
        assert run_node("A.seriesOf('','理想L6')") == "L"
        assert run_node("A.seriesOf('','MEGA')") == "W"
        assert run_node("A.seriesOf('','理想ONE')") == "M"

    def test_unknown_falls_back_to_generic(self):
        assert run_node("A.seriesOf('','')") == "generic"
        assert run_node("A.seriesOf('','未来新车型')") == "generic"


class TestFallbackChain:
    def test_user_image_first(self):
        """用户本地图必须排在最前（才可能被用户覆盖）。"""
        cands = json.loads(run_node("JSON.stringify(A.carImageCandidates({modelName:'理想L6'}))"))
        assert cands[0].startswith("/local/lixiang-cars/L."), cands[0]
        assert any(".png" in c for c in cands[:4]), cands[:4]

    def test_model_id_key_wins_over_series(self):
        cands = json.loads(run_node(
            "JSON.stringify(A.carImageCandidates({modelId:'100123', modelName:'理想L6'}))"))
        assert cands[0].startswith("/local/lixiang-cars/100123."), cands[0]

    def test_builtin_silhouette_is_last_resort(self):
        """最后是内置剪影（data URI）—— 保证离线也不空屏。"""
        cands = json.loads(run_node("JSON.stringify(A.carImageCandidates({modelName:'理想L6'}))"))
        assert cands[-1].startswith("data:image/svg+xml"), cands[-1]
        assert cands[-2].startswith("data:image/svg+xml"), cands[-2]

    def test_every_series_has_a_silhouette(self):
        for s in ("L", "W", "M", "generic"):
            assert run_node(f"A.SILHOUETTE['{s}']").startswith("data:image/svg+xml")


class TestCacheBuster:
    def test_version_query_appended(self):
        assert run_node(
            "A.vurl('/x/y.js')",
            "globalThis.window = {__LX_ASSET_V__: '1.5.0'};") == "/x/y.js?v=1.5.0"

    def test_no_version_keeps_url(self):
        assert run_node("A.vurl('/x/y.js')") == "/x/y.js"


class TestWiring:
    def test_version_view_registered(self):
        src = INIT.read_text(encoding="utf-8")
        assert 'url = "/lixiang_auto/asset-version.js"' in src
        assert "LiXiangAssetVersionView())" in src, "版本视图未注册"
        assert "_integration_version()" in src

    def test_version_reads_manifest(self):
        """版本号必须来自 manifest（这样发版就自动变）。"""
        src = INIT.read_text(encoding="utf-8")
        assert "manifest.json" in src

    def test_page_uses_asset_layer_and_degrades(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "_ensureAssets" in src, "页面未接资源层"
        assert "lx-car-box" in src
        assert "catch (_)" in src, "资源层不可用时要能降级（不崩页面）"

    def test_module_exposes_globals_for_cards(self):
        src = ASSETS.read_text(encoding="utf-8")
        assert "window.LxAssets = api" in src
        assert "window.__lxCarFallback" in src
