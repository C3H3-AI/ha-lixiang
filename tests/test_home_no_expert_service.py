"""首页移除「服务专家」卡（2026-10-12，车主指示）。

车主：**「专家服务模块不要了」**

移除内容（首页 `lixiang-app-home.js`）：
- `<div class="srvrow">…</div>` —— 服务专家 + 在线客服 + 电话客服两个圆按钮
- 紧邻的 `<div class="divider">`（上面没内容了，留着会是一条悬空分隔线）
- `wire("#btn-chat", nav.service)` 绑定
- `.srvrow` / `.cbtn` 两组 CSS（共 8 条规则）
- 卡片 `description` 里的"服务专家"字样

第二轮（同日）：车主追加「**学习平台也不要**」→ 连同 AD 学习平台一并移除。

★ 但 `.big` **样式必须保留** —— 它有 3 处使用（里程卡数值、电量卡数值、以及那个
  已被删掉的 AD 容器）。删 CSS 会连带破坏里程/电量卡版式。本测试守住这一点。
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


class TestAdPlatformRemoved:
    """第二轮：车主「学习平台也不要」→ AD 学习平台入口也移除。"""

    def test_ad_row_gone(self):
        s = _strip_comments(_src())
        assert 'class="adrow"' not in s, "AD 学习平台行还在"
        assert 'id="btn-ad"' not in s, "AD 入口按钮还在"

    def test_ad_binding_gone(self):
        s = _strip_comments(_src())
        assert 'wire("#btn-ad"' not in s, "还绑着已删除的 AD 入口"

    def test_ad_css_gone(self):
        s = _strip_comments(_src())
        assert not re.search(r'^\s*\.adrow\b', s, re.M), "残留 .adrow 样式"

    def test_no_ad_text(self):
        s = _src()
        m = re.search(r'description:\s*"([^"]*)"', s)
        assert m and "AD学习" not in m.group(1), "卡片描述还在提 AD 学习平台"


class TestBigContainerPreserved:
    """★★ 关键防误删：`.big` 是**共用样式**，删了会破坏里程/电量卡。

    `class="big"` 有 3 处使用：里程卡数值、电量卡数值、以及被删掉的 AD 容器。
    删掉 AD 容器后应剩 **2 处**，且 `.big { … }` 规则必须还在。
    """

    def test_big_css_kept(self):
        s = _strip_comments(_src())
        assert re.search(r'^\s*\.big\s*\{', s, re.M), \
            ".big 样式被误删 —— 里程/电量卡的数值容器会失去版式"

    def test_big_still_used_twice(self):
        s = _strip_comments(_src())
        assert s.count('class="big"') == 2, \
            "删掉 AD 容器后应剩 2 处 .big（里程卡 + 电量卡）"

    def test_big3d_untouched(self):
        """`.big3d`（3D 车模 iframe 容器）名字相近，不能被误伤。

        ★ 断言必须落在**具体规则**上 —— `.big3d` 在文件里出现 10 次，
          只查"字符串存在"的话，改坏其中一条规则测试照样绿（本测试初版就被骗过）。
        """
        s = _strip_comments(_src())
        assert re.search(r'^\s*\.big3d\s*\{', s, re.M), "缺 .big3d 主样式规则"
        assert ".big3d, .big3d iframe" in s, "big3d 的 touch-action 规则被改动"
        assert ".big3d iframe {" in s, "缺 big3d iframe 规则"
        assert 'class="big3d"' in s, "缺 big3d 容器"


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