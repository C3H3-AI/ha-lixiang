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


def test_cards_support_forced_theme():
    """★ 必须支持 theme: 配置强制指定明暗（2026-10-09 修复）。

    背景：此前 13 个有 UI 的卡片里只有 4 个支持 data-theme —— 用户在 YAML 里写
    `theme: dark` 时，多数卡片仍跟随系统，配置形同无效。
    统一要求：
      ① CSS 有 data-theme="dark"/"light" 两套令牌
      ② JS 在 setConfig 里把配置写到 dataset.theme（否则 CSS 永不生效）
    """
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        assert 'data-theme="dark"' in src, f"{fname} 缺强制 dark 主题样式"
        assert 'data-theme="light"' in src, f"{fname} 缺强制 light 主题样式"
        assert "dataset.theme" in src, (
            f"{fname} 未在 setConfig 写入 dataset.theme（theme 配置不会生效）")


def test_cards_theme_tokens_consistent():
    """★ 强制主题令牌须与卡片既有主题一致（避免切换主题时颜色跳变/视觉回归）。"""

    def _tokens(block: str) -> dict:
        found = re.findall(r'(--lx-[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', block)
        return {k: v.lower() for k, v in found}

    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        m_def = re.search(r':host\s*\{([^}]*)\}', src)
        m_light = re.search(r'\[data-theme="light"\][^{]*\{([^}]*)\}', src)
        m_dark = re.search(r'\[data-theme="dark"\][^{]*\{([^}]*)\}', src)
        m_media = re.search(
            r'@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:host[^{]*\{([^}]*)\}',
            src, re.S)
        assert m_light and m_dark, f"{fname} 缺强制主题令牌块"
        t_def = _tokens(m_def.group(1)) if m_def else {}
        t_light = _tokens(m_light.group(1))
        t_dark = _tokens(m_dark.group(1))
        t_media = _tokens(m_media.group(1)) if m_media else {}
        # 强制 light 的 card/line 沿用本卡片默认值（保留既有视觉，避免回归）
        for key in ("--lx-card", "--lx-line"):
            if key in t_def and key in t_light:
                assert t_def[key] == t_light[key], (
                    f"{fname} 强制 light 的 {key} 与默认值不一致（会改变原有视觉）")
        # 强制 dark 与"跟随系统 dark"的令牌必须一致
        for key, val in t_media.items():
            if key in t_dark:
                assert val == t_dark[key], (
                    f"{fname} 强制 dark 的 {key} 与系统 dark 不一致"
                    f"（{val} vs {t_dark[key]}）")


def test_theme_selector_matches_js_target():
    """★ 强制主题的 CSS 选择器必须与 JS 实际写入位置一致（2026-10-09 真 bug）。

    事故：CSS 写成 :host([data-theme=...])（期望属性在 host 上），
          但 JS 写的是 root.dataset.theme（属性在 .root 上）
          → 选择器永不命中，强制主题静默失效，且静态测试查子串仍会「通过」。
    因此必须显式断言二者一致：
      · 若 CSS 用 :host([data-theme=...]) → JS 必须写 host 属性（this.dataset.theme）
      · 若 CSS 用 .root[data-theme=...]   → JS 必须写 root.dataset.theme
    """
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        css_on_host = ':host([data-theme=' in src
        css_on_root = '.root[data-theme=' in src
        assert css_on_host or css_on_root, f"{fname} 无强制主题选择器"
        js_on_root = "root.dataset.theme" in src
        js_on_host = bool(re.search(r'this\.dataset\.theme', src))
        if css_on_root:
            assert js_on_root, (
                f"{fname} CSS 用 .root[data-theme] 但 JS 未写 root.dataset.theme —— 选择器永不命中")
        if css_on_host and not css_on_root:
            assert js_on_host, (
                f"{fname} CSS 用 :host([data-theme]) 但 JS 未写 host 属性 —— 选择器永不命中")


def test_theme_reads_persisted_config_not_param():
    """★ 主题赋值引用的 c 必须在同作用域内声明（2026-10-09 真事故）。

    事故：在某卡片 _build() 里写 `root.dataset.theme = c.theme || "light"`，
          而该 _build() 内并没有声明 c（c 只是 setConfig 的形参）
          → ReferenceError → setConfig/hass 抛错 → 卡片完全不渲染。
          静态测试只查"是否含 dataset.theme"子串会误判通过，
          浏览器实测（真实 setConfig→hass→_build 全链路）才暴露。

    合法两种写法：
      ① _build 内有 `const c = this._config;` 别名 → 可用 c.theme（4 个老卡片如此）
      ② 直接用 (this._config && this._config.theme) || "light"（本次 9 个卡片采用）
    """
    for fname in EXPECTED:
        src = (CARDS / fname).read_text(encoding="utf-8")
        for m in re.finditer(r'root\.dataset\.theme\s*=\s*([^;]+);', src):
            rhs = m.group(1)
            if "c.theme" not in rhs:
                continue
            # 找到该赋值所处方法（setConfig / _build ...）的起点
            starts = [(mm.start(), mm.group(0).strip()[:12]) for mm in
                      re.finditer(r'\n\s*(setConfig|_build)\s*\([^)]*\)\s*\{', src)]
            owner_start = None
            for st, _nm in starts:
                if st < m.start(): owner_start = st
            if owner_start is None:
                owner_start = 0
            body_start = src.find('{', owner_start) + 1
            # 花括号配对得到方法体
            depth, k = 1, body_start
            while k < len(src) and depth > 0:
                if src[k] == '{': depth += 1
                elif src[k] == '}': depth -= 1
                k += 1
            body = src[body_start:k]
            has_alias = re.search(r'(?:const|let|var)\s+c\s*=\s*this\._config', body) is not None
            assert has_alias, (
                f"{fname} 的主题赋值用了 c.theme，但所在方法内没有 `const c = this._config` 别名"
                f"（{rhs.strip()}）→ 会 ReferenceError、卡片不渲染；"
                f" 请改为 (this._config && this._config.theme) || \"light\"")



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


def test_home_card_header_is_sticky():
    """★ 2026-10-09（用户要求）：主界面抬头固定。

    要求：
      ① `.head` 粘顶（position:sticky + top:0，否则滚走了）
      ② 粘顶后收紧（.root.stuck …），否则固定的抬头会占掉半屏
      ③ 粘顶判定用真实滚动量（_scrollTopOf）——HA 的滚动常发生在外层容器里，
         window.scrollY 恒为 0，只看 window 会导致状态永远不切换
      ④ 监听器要在 disconnectedCallback 里清理（否则每次重渲染都叠加监听）
    """
    src = (CARDS / "lixiang-app-home.js").read_text(encoding="utf-8")
    assert "position:sticky" in src, "抬头未设置 position:sticky（不会固定）"
    assert "top:0" in src, "粘顶缺少 top:0"
    assert ".root.stuck .head" in src, "缺少粘顶后的收紧样式"
    assert 'classList.toggle("stuck"' in src, "未切换 .stuck 状态"
    assert "_scrollTopOf" in src, "粘顶判定未使用真实滚动量（外层容器滚动会失效）"
    assert "scrollTop" in src, "未读取滚动容器的 scrollTop"
    # 监听器清理
    assert "_scrollCleanups" in src and "removeEventListener" in src, "滚动监听未清理"


def test_home_card_header_avoids_ha_toolbar():
    """★ 2026-10-09 用户反馈「抬头还是会被遮挡」的回归守卫。

    HA 的顶栏是 position:fixed 覆盖层（高度 = --header-height，实测 56px）：
      · 覆盖式布局（窄屏）：滚动容器顶边在视口顶端 → 抬头必须下移一个顶栏高度
      · 预留式布局（宽屏）：滚动容器顶边已在顶栏之下 → 不能下移，否则露空白
    因此粘顶位置必须由 JS 按实测布局算，不能写死 top:0 / top:56px。
    """
    src = (CARDS / "lixiang-app-home.js").read_text(encoding="utf-8")
    assert "--header-height" in src, "未读取 HA 顶栏高度 --header-height"
    assert "_headTopOffset" in src, "缺少「避开 HA 顶栏」的粘顶位置计算"
    assert "--lx-head-top" in src, "粘顶位置未接到 CSS 变量 --lx-head-top"
    assert "top:var(--lx-head-top" in src.replace(" ", ""), "CSS 未使用 --lx-head-top 作为 top"
    assert "_scrollRoot" in src, "缺少滚动容器探测（决定是否覆盖式布局）"
