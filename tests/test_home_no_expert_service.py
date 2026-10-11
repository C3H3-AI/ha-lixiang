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
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)      # ★ HTML 注释也要删（模板字符串里）
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

class TestSecondaryNavDefaults:
    """★★ 修复（车主："车辆设置二级页面错误"）。

    `e-health` / `e-setting` 此前**没有默认路径**：

    ```js
    wire("#e-health",  nav.health);     // nav.health 未配置 → undefined
    wire("#e-setting", nav.setting);    // → go(undefined) → if (!p) return（点击无反应）
    ```

    其他入口都有 `nav.x || "/lixiang/x"` 兜底，唯独这两个漏了。
    """

    def test_health_has_default(self):
        s = _strip_comments(_src())
        assert 'wire("#e-health", nav.health || "/lixiang/health")' in s, \
            "车辆健康缺默认路径 → 点击无反应"

    def test_setting_has_default(self):
        s = _strip_comments(_src())
        assert 'wire("#e-setting", nav.setting || "/lixiang/setting")' in s, \
            "车辆设置缺默认路径 → 点击无反应"

    def test_all_entry_wires_have_fallback(self):
        """★ 通用守卫：所有 wire("#e-xxx", …) 都必须有 `|| "/lixiang/…"` 兜底。"""
        s = _strip_comments(_src())
        bad = []
        for m in re.finditer(r'wire\(\s*"(#e-[a-z]+)"\s*,\s*([^)]*)\)', s):
            sel, arg = m.group(1), m.group(2)
            if "||" not in arg:
                bad.append(f"{sel} → {arg.strip()}")
        assert not bad, f"这些入口缺默认路径（未配置就点不动）：{bad}"

    def test_vinfo_entry_present(self):
        """「钥匙管理」入口走 vinfo。"""
        s = _strip_comments(_src())
        assert 'wire("#e-key", nav.vinfo || "/lixiang/vinfo")' in s


class TestNoHorizontalOverflow:
    """★★ 修复（车主："手机上右边溢出"）。

    根因：grid 用 `1fr` —— 其默认 `min-width:auto` 会让**长内容撑破容器**
    （地址/数值等），在窄屏上表现为右侧溢出。标准修复是 `minmax(0,1fr)`。
    """

    def test_grids_use_minmax(self):
        s = _strip_comments(_src())
        offenders = []
        for m in re.finditer(r'grid-template-columns:\s*([^;]+);', s):
            val = m.group(1)
            if re.search(r'(?<![\w(])1fr(?![\w)])', val) and "minmax" not in val:
                offenders.append(val.strip())
        assert not offenders, f"这些 grid 仍用裸 1fr（长内容会撑破容器）：{offenders}"

    def test_root_hidden_overflow(self):
        """兜底：根节点不得横向溢出。"""
        s = _strip_comments(_src())
        assert "overflow-x:hidden" in s, "缺横向溢出兜底"

    def test_children_can_shrink(self):
        """grid/flex 子项要允许收缩（min-width:0）。"""
        s = _strip_comments(_src())
        assert "min-width:0" in s, "缺 min-width:0 —— 子项无法收缩"

    def test_quick_grid_fixed(self):
        s = _strip_comments(_src())
        assert "repeat(4,minmax(0,1fr))" in s, "8 圆按钮的 grid 未修复"

    def test_row2_and_entries_fixed(self):
        s = _strip_comments(_src())
        assert "repeat(2,minmax(0,1fr))" in s, "row2/entries 的 grid 未修复"


class TestKeyManagementNamingFix:
    """★★ 车主反馈：「钥匙管理显示的设置的内容」（2026-10-12）。

    根因是**三处名称不一致**：

    | 位置 | 原名 | 实际内容 |
    |---|---|---|
    | 首页入口 | 钥匙管理 | — |
    | 页面标题 | 车辆设置 | 车辆昵称/车牌/型号/车架号 |
    | 卡片名   | 车辆信息 | 同上 |

    且首页副标题的「未连接」来自 `_eid("key_connected")` —— 这个绑定键
    **在 auto-bind 里根本不存在**，所以永远显示**假状态**。

    现统一为「车辆信息」，并去掉假状态。
    """

    def test_vehicle_page_title_is_vehicle_info(self):
        s = (ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-vehicle-info-page.js").read_text(encoding="utf-8")
        assert "<h1>车辆信息</h1>" in s, "页面标题不是「车辆信息」"
        assert "<h1>车辆设置</h1>" not in s, "页面标题仍是「车辆设置」（与内容不符）"

    def test_home_entry_renamed(self):
        s = _strip_comments(_src())
        assert "<div class=\"nm\">车辆信息</div>" in s, "首页入口未改名"
        assert "钥匙管理" not in s, "首页入口仍叫「钥匙管理」"

    def test_no_fake_key_connected(self):
        """★ `key_connected` 在 auto-bind 里不存在 → 不能拿它显示状态。"""
        s = _strip_comments(_src())
        assert "key_connected" not in s, "仍在使用不存在的 key_connected 绑定"

    def test_key_connected_is_truly_absent_from_autobind(self):
        """坐实前提：auto-bind 里确实没有这个键。"""
        ab = (ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-auto-bind.js").read_text(encoding="utf-8")
        assert "key_connected" not in ab, \
            "auto-bind 里居然有了 key_connected —— 那这条测试的前提要重估"

    def test_subtitle_uses_real_data(self):
        s = _strip_comments(_src())
        assert 'this._eid("vehicle_cfg")' in s, "副标题未改用真实车型数据"
