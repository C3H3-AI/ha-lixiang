"""首页移除「服务专家」卡（2026-10-12，车主指示）。

车主：**「专家服务模块不要了」**

移除内容（首页 `lixiang-app-home.js`）：
- `<div class="srvrow">…</div>` —— 服务专家 + 在线客服 + 电话客服两个圆按钮
- 紧邻的 `<div class="divider">`（上面没内容了，留着会是一条悬空分隔线）
- `wire("#btn-chat", nav.service)` 绑定
- `.srvrow` / `.cbtn` 两组 CSS（共 8 条规则）
- 卡片 `description` 里的"服务专家"字样

★ **保留**「理想AD学习平台」入口（`.adrow` / `btn-ad`）—— 车主只说了"专家服务模块"，
  没有让删 AD 学习平台。本测试专门守住这一点，防止后人顺手把整块 `.big` 删掉。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = (ROOT / "custom_components" / "lixiang_auto" / "www"
        / "lixiang-cards" / "lixiang-app-home.js")


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


def _strip_comments(s: str) -> str:
    """去掉注释 —— 否则断言会命中「已移除服务专家」这类说明文字而恒为真。"""
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'^\s*//.*$', '', s, flags=re.M)
    s = re.sub(r'^\s*\*.*$', '', s, flags=re.M)
    return s


class TestExpertServiceRemoved:
    def test_no_srvrow_markup(self):
        s = _strip_comments(_src())
        assert 'class="srvrow"' not in s, "「服务专家」行还在"

    def test_no_customer_service_buttons(self):
        s = _strip_comments(_src())
        assert 'id="btn-chat"' not in s, "在线客服按钮还在"
        assert 'id="btn-call"' not in s, "电话客服按钮还在"

    def test_no_binding(self):
        s = _strip_comments(_src())
        assert 'wire("#btn-chat"' not in s, "还绑着已删除的按钮"

    def test_no_css_rules(self):
        s = _strip_comments(_src())
        assert not re.search(r'^\s*\.srvrow\b', s, re.M), "残留 .srvrow 样式"
        assert not re.search(r'^\s*\.cbtn\b', s, re.M), "残留 .cbtn 样式"

    def test_no_consultant_icon_reference(self):
        s = _strip_comments(_src())
        assert "icon_car_owner_consultant" not in s, "还引用服务专家图标"

    def test_no_dangling_divider(self):
        """分隔线是给"服务专家"和"AD学习平台"分的 —— 上面没了就是悬空的。"""
        s = _strip_comments(_src())
        assert 'class="divider"' not in s, "残留悬空分隔线"

    def test_description_updated(self):
        s = _src()
        m = re.search(r'description:\s*"([^"]*)"', s)
        assert m, "找不到卡片 description"
        assert "服务专家" not in m.group(1), "卡片描述还在提服务专家"


class TestAdPlatformKept:
    """★ 防误删：车主只让删服务专家，AD 学习平台应保留。"""

    def test_ad_row_still_present(self):
        s = _strip_comments(_src())
        assert 'class="adrow" id="btn-ad"' in s, "「理想AD学习平台」入口被误删"
        assert "理想AD学习平台" in s

    def test_ad_binding_kept(self):
        s = _strip_comments(_src())
        assert 'wire("#btn-ad", nav.ad)' in s, "AD 入口绑定丢了"

    def test_ad_css_kept(self):
        s = _strip_comments(_src())
        assert re.search(r'^\s*\.adrow\b', s, re.M), "缺失 .adrow 样式"

    def test_big_container_kept(self):
        """`.big` 是卡片外壳（背景/圆角/内边距），去掉会破坏版式。"""
        s = _strip_comments(_src())
        assert re.search(r'^\s*\.big\s*\{', s, re.M), "缺 .big 样式"
        assert '<div class="big">' in s, "缺 .big 容器"


class TestSyntax:
    def test_js_syntax(self):
        import subprocess
        r = subprocess.run(["node", "--check", str(HOME)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]

    def test_plan_placeholder_untouched(self):
        """这次改动不该碰其他入口（情景模式/车辆设置/车辆健康等）。"""
        s = _strip_comments(_src())
        for sel in ('id="e-scene"', 'id="e-setting"', 'id="e-health"',
                    'id="e-task"', 'id="e-key"'):
            assert sel in s, f"{sel} 被误删"