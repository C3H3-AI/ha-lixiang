"""卡片基座 / 通用信息页 —— 回归测试（2026-10-11）。

背景
----
13/14 个卡片文件各自抄一遍 `@font-face` + 图标/字体 base（实测重复 13 处），
且「信息型页面」的「卡片 + 行」HTML 也是各写一份 → 改样式要改十几次。

本轮改造：
- `lixiang-base.js`     共享基座（主题 / 字体 / 图标 / 工具）
- `lixiang-info-page.js`通用信息页：`renderCards()` 只渲染卡片区（**行由数据定义**），
  `buildInfoPage()` 整页渲染（新页面直接复用，不必再写 HTML）
- `lixiang-vehicle-info-page.js` 首个改造对象：保留自己的 topbar/返回/toast 外壳，
  只把三段手写卡片换成 `renderCards(...)` —— **渐进改造，不丢导航**。

★ JS 行为用 **node 真跑**（子串断言挡不住「忽略 when 门控」这类退化）。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CARDS = CC / "www" / "lixiang-cards"
BASE = CARDS / "lixiang-base.js"
INFO = CARDS / "lixiang-info-page.js"
VEH = CARDS / "lixiang-vehicle-info-page.js"


def node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_node(code: str) -> str:
    """以 **ES module** 方式执行（两个模块都是 ESM，用 -e 的 CommonJS 会报错）。"""
    r = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:600]
    return r.stdout


pytestmark = pytest.mark.skipif(not node_ok(), reason="node 不可用")


class TestSharedBase:
    def test_theme_and_fonts(self):
        out = run_node(
            f"import * as B from '{BASE.as_uri()}';"
            "process.stdout.write([B.BASE_CSS.includes('--lx-card'),"
            "B.fontFaceCss('/f').includes('/f/licium_regular.ttf'),"
            "B.ICON_BASE_DEFAULT, B.FONT_BASE_DEFAULT].join('|'));"
        )
        a, b, icon, font = out.split("|")
        assert a == "true" and b == "true"
        assert icon == "/local/lixiang-icons" and font == "/local/lixiang-fonts"

    def test_icon_url_has_cache_buster(self):
        out = run_node(
            "globalThis.window={__LX_ASSET_V__:'1.5.0'};"
            f"import * as B from '{BASE.as_uri()}';"
            "process.stdout.write(B.iconUrl('/i','a.webp'));"
        )
        assert out == "/i/a.webp?v=1.5.0"


class TestRenderCards:
    def test_rows_from_data(self):
        js = f"""
        import {{ renderCards }} from '{INFO.as_uri()}';
        const html = renderCards({{cards:[{{rows:[
            {{icon:'a.webp', k:'车辆昵称', id:'v-name'}},
            {{icon:'b.webp', k:'车牌号', id:'v-plate', na:'暂不可用', rowId:'r-plate', click:true}},
        ]}}]}});
        process.stdout.write(JSON.stringify({{
            hasId: html.includes('id="v-name"'),
            na: html.includes('暂不可用'),
            click: html.includes('class="row click"'),
            rowId: html.includes('id="r-plate"'),
        }}));
        """
        got = json.loads(run_node(js))
        assert got["hasId"] and got["na"] and got["click"] and got["rowId"]

    def test_capability_gate_hides_rows(self):
        """★ `when:false` 的行必须不渲染 —— 这是「按能力/车型显隐」的基础。"""
        js = f"""
        import {{ renderCards }} from '{INFO.as_uri()}';
        const html = renderCards({{cards:[{{rows:[
            {{k:'燃油续航', id:'v-fuel', when:false}},
            {{k:'电量', id:'v-bat', when:true}},
        ]}}]}});
        process.stdout.write(JSON.stringify({{
            fuel: html.includes('v-fuel'), bat: html.includes('v-bat'),
        }}));
        """
        got = json.loads(run_node(js))
        assert got["bat"] is True
        assert got["fuel"] is False, "when=false 的行不该出现（否则纯电车会显示燃油续航）"

    def test_missing_icon_is_tolerated(self):
        js = f"""
        import {{ renderCards }} from '{INFO.as_uri()}';
        const html = renderCards({{cards:[{{rows:[{{k:'无图标项', id:'x'}}]}}]}});
        process.stdout.write(String(html.includes('x')));
        """
        assert run_node(js) == "true"


class TestVehicleInfoPageRefactor:
    def test_uses_render_cards(self):
        src = VEH.read_text(encoding="utf-8")
        assert "renderCards(" in src, "未改用通用渲染"
        assert "lixiang-info-page.js" in src

    def test_keeps_shell(self):
        """★ 改造不能丢外壳：topbar / 返回 / toast 必须还在。"""
        src = VEH.read_text(encoding="utf-8")
        assert "topbar" in src and "#back" in src and "toast" in src

    def test_no_handwritten_card_blocks_left(self):
        """行标记不应该再手写（否则改造没落地）。"""
        src = VEH.read_text(encoding="utf-8")
        assert 'class="k">车辆昵称</span>' not in src, "仍有手写的行标记"


class TestWiring:
    def test_base_and_info_exist(self):
        assert BASE.exists() and INFO.exists()

    def test_base_exposes_globals(self):
        assert "window.LxBase = api" in BASE.read_text(encoding="utf-8")
