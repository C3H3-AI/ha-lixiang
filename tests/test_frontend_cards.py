"""前端卡片测试（2026-10-02）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CARDS = CC / "www" / "lixiang-cards"

EXPECTED = {
    "lixiang-app-home.js": "lixiang-app-home",
    "lixiang-energy-page.js": "lixiang-energy-page",
    "lixiang-charge-page.js": "lixiang-charge-page",
    "lixiang-health-page.js": "lixiang-health-page",
    "lixiang-setting-page.js": "lixiang-setting-page",
    "lixiang-scene-page.js": "lixiang-scene-page",
    "lixiang-ad-page.js": "lixiang-ad-page",
    # ★ 2026-10-02 新增（按 App 截图逐页对齐）
    "lixiang-climate-page.js": "lixiang-climate-page",
    "lixiang-seat-page.js": "lixiang-seat-page",
    "lixiang-location-page.js": "lixiang-location-page",
    "lixiang-vehicle-info-page.js": "lixiang-vehicle-info-page",
    "lixiang-task-page.js": "lixiang-task-page",
    "lixiang-bindings-card.js": "lixiang-bindings-card",
}

# 自动发现引擎（不是卡片，不注册 customCards）
ENGINE = "lixiang-auto-bind.js"


def test_all_cards_present():
    """7 个卡片文件必须都在。"""
    missing = [f for f in EXPECTED if not (CARDS / f).exists()]
    assert not missing, f"缺卡片: {missing}"


def test_cards_define_custom_element():
    """每个卡片必须 define 自己的 tag 且注册到 window.customCards。"""
    for fname, tag in EXPECTED.items():
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert "customElements.define" in src, f"{fname} 未注册自定义元素"
        assert f'"{tag}"' in src or f"'{tag}'" in src, f"{fname} tag 不匹配"
        assert "window.customCards" in src, f"{fname} 未加入卡片选择器"


def test_cards_implement_ha_interface():
    """必须实现 HA 卡片接口。"""
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        for member in ("setConfig", "set hass", "getCardSize", "extends HTMLElement"):
            assert member in src, f"{fname} 缺 {member}"


def test_cards_no_global_dom_query():
    """不得用 document.querySelector（HA 卡片在 Shadow DOM 内，查不到）。"""
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        # 允许 document.createElement / document.addEventListener
        bad = re.findall(r"document\.(querySelector|getElementById|getElementsBy)", src)
        assert not bad, f"{fname} 用了全局选择器: {bad}"


def test_cards_have_a11y():
    """必须支持键盘与屏幕阅读器。"""
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert "aria-label" in src, f"{fname} 缺 aria-label"
        assert "focus-visible" in src, f"{fname} 缺 focus-visible 样式"
        assert "prefers-reduced-motion" in src, f"{fname} 未尊重动效偏好"


def test_cards_cleanup_resources():
    """必须实现 disconnectedCallback（防内存泄漏）。"""
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert "disconnectedCallback" in src, f"{fname} 缺资源清理"


def test_cards_resource_paths_configurable():
    """图标/字体路径必须可配置（资源可选）。"""
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert "DEFAULT_ICON_BASE" in src or "DEFAULT_FONT_BASE" in src, \
            f"{fname} 资源路径不可配置"


def test_static_path_registered():
    """集成必须注册 /lixiang_auto 静态路径（否则卡片 URL 404）。"""
    src = (CC / "__init__.py").read_text(encoding="utf-8")
    assert "async_register_static_paths" in src, "未注册静态路径"
    assert 'StaticPathConfig("/lixiang_auto"' in src, "路径不是 /lixiang_auto"
    # 必须在 async 函数内（否则 await 语法错）
    i = src.find("async_register_static_paths")
    fn = src.rfind("async def", 0, i)
    assert fn > 0, "静态路径注册不在 async 函数内"


def test_cards_no_sensitive_data():
    """卡片不得含敏感信息。"""
    # 排除脱敏占位符（全 X）
    # ★ 手机号规则加 \b 边界：否则长数字常量（如 GCJ-02 的偏心率常量）
    #   中间会命中 1[3-9]\d{9} 造成误报（实测会误报为手机号）。
    #   真实手机号单独成串，前后不会紧邻其他数字。
    pats = [r"HLX(?!32X{12})[A-Z0-9]{14}", r"\b1[3-9]\d{9}\b", r"nzy\d{6}"]
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        for p in pats:
            assert not re.search(p, src), f"{fname} 含敏感模式 {p}"


def test_readme_mentions_cards():
    """README 必须介绍卡片。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "前端卡片" in readme, "README 未介绍卡片"
    assert "docs/CARDS.md" in readme, "README 未链接卡片文档"


def test_cards_doc_exists():
    """卡片文档必须存在且被 git 跟踪（白名单）。"""
    doc = ROOT / "docs" / "CARDS.md"
    assert doc.exists(), "docs/CARDS.md 不存在"
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!docs/CARDS.md" in gi, "CARDS.md 未加 gitignore 白名单"

# ─────────────────────────── 新增（2026-10-02）───────────────────────────


def test_auto_bind_engine_exists():
    """自动发现引擎必须存在且导出 LixiangAutoBind。"""
    f = CARDS / ENGINE
    assert f.exists(), "缺自动发现引擎 lixiang-auto-bind.js"
    src = f.read_text(encoding="utf-8")
    assert "class LixiangAutoBind" in src, "引擎未定义 LixiangAutoBind"
    assert "window.LixiangAutoBind" in src, "引擎未挂到 window"
    # 必须有 resolve/diagnose/summary
    for m in ("resolve(", "diagnose(", "summary("):
        assert m in src, f"引擎缺 {m}"


def test_auto_bind_field_table():
    """引擎必须有足够多的字段映射（覆盖全部门）。"""
    src = (CARDS / ENGINE).read_text(encoding="utf-8")
    # 数一下 fields 里的条目（形如 `key:`）
    import re
    body = src[src.find("fields: {"):src.find("/* ─", src.find("fields: {"))]
    keys = re.findall(r"^\s{4}([a-z_][a-z0-9_]*):", body, re.M)
    assert len(keys) >= 70, f"字段映射只有 {len(keys)} 个，应 ≥ 70"


def test_cards_use_auto_bind():
    """除诊断卡外，所有卡片都应接入自动发现。"""
    for fname in EXPECTED:
        if fname in (ENGINE, "lixiang-bindings-card.js"):
            continue
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert "_autoBind()" in src, f"{fname} 未接入自动发现引擎"


def test_cards_cache_only_nonempty():
    """自动发现：空结果不得缓存（否则永久空绑定）。"""
    import re
    for fname in EXPECTED:
        if fname == ENGINE:
            continue
        src = (CARDS / fname).read_text(encoding="utf-8")
        if "_bindCache" not in src:
            continue
        # 不允许出现「无条件缓存」
        assert not re.search(r"^\s*this\._bindCache = out;\s*$", src, re.M), \
            f"{fname} 无条件缓存了自动发现结果（空值会永久生效）"


def test_cards_no_hardcoded_entity_ids():
    """卡片不得硬编码实体 ID（应由自动发现提供）。"""
    import re
    for fname in EXPECTED:
        if fname == ENGINE:
            continue
        src = (CARDS / fname).read_text(encoding="utf-8")
        # 允许注释与文档里的示例，但代码里不应出现 sensor./lock./switch. 字面量
        code = re.sub(r"//.*|/\*[\s\S]*?\*/", "", src)
        # 只认「实体 ID」：域名 + 点 + 拼音/下划线（≥6 字符且含下划线）
        # 排除服务名（如 climate.turn_on / switch.turn_off / cover.close_cover）
        hits = re.findall(
            r'"(?:sensor|binary_sensor|switch|lock|cover|fan|climate|number|select|button)'
            r'\.(?!turn_on|turn_off|toggle|close_cover|open_cover|lock|unlock|press|set_value|'
            r'select_option|set_percentage|set_temperature|set_hvac_mode|create|dismiss)'
            r'[a-z0-9]+_[a-z0-9_]+"',
            code,
        )
        assert not hits, f"{fname} 硬编码实体: {hits[:3]}"


def test_task_page_uses_automation_api():
    """任务大师卡应通过 HA 自动化 API 落地（而非云端）。"""
    src = (CARDS / "lixiang-task-page.js").read_text(encoding="utf-8")
    assert "/api/config/automation/config/" in src, "未使用 HA 自动化 API"
    assert "POST" in src, "未实现创建动作"


def test_capability_boundary_documented():
    """能力边界必须文档化（诚实标注）。"""
    doc = (ROOT / "docs" / "CARDS.md").read_text(encoding="utf-8")
    for kw in ("能力边界", "2009", "只读", "Shadow DOM", "returnResponse"):
        assert kw in doc, f"CARDS.md 缺「{kw}」说明"

def test_no_this_outside_class():
    """模块级代码不得引用 this（会在类外执行时崩溃）。

    真实踩过：task-page 的 PRESET_DEFS（模块级数组）里用了 this._eid("ac")，
    导致该卡片一加载就抛 TypeError，且污染同一页其他卡片。
    """
    import re
    for fname in EXPECTED:
        if fname == ENGINE:
            continue
        src = (CARDS / fname).read_text(encoding="utf-8")
        m = re.search(r"^class\s+\w+", src, re.M)
        if not m:
            continue
        head = src[: m.start()]
        # 去掉注释再检查
        code = re.sub(r"//.*|/\*[\s\S]*?\*/", "", head)
        assert "this." not in code, (
            f"{fname} 在类外引用了 this（模块级代码没有 this）："
            f"{[l.strip()[:60] for l in code.splitlines() if 'this.' in l][:2]}"
        )

def test_docs_no_real_vin():
    """文档（README/docs）不得出现真实 VIN。

    真实踩过：写示例配置时抄了真 VIN → CI `lint & security` 失败。
    CI 的敏感扫描用 GitHub Secret 的精确值，本地无法复现，
    所以这里用「16 位 HLX 开头且非全 X」做粗筛。
    """
    import re
    targets = [ROOT / "README.md", ROOT / "docs" / "CARDS.md"]
    pat = re.compile(r"HLX(?!32X{6,})[A-Z0-9]{12,}")
    for f in targets:
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        hits = pat.findall(txt)
        assert not hits, f"{f.name} 含疑似真实 VIN: {hits[:2]}"
