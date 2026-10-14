"""图标回退 / 图标基址自动降级 —— 回归测试（2026-10-14）。

背景：车主实测「别人家的车看不到图标」
--------------------------------------
截图显示理想 L8 的 8 个快捷按钮全是破图。根因有两层：

① **JS 赋值的图标没有 onerror 可挂**
   v1.5.6 的图标回退是靠正则往 HTML 模板里注入
   `onerror="__lxIconFallback(this)"` —— 只能覆盖模板里写死的 `<img src="${__iconBase}/x">`。
   但快捷按钮的图标是 **JS 赋值**的：

       d.innerHTML = `<img src="${this._img(it.off)}" alt="">`   // 模板插值，正则匹配不到
       img.src = this._img(active ? it.on : it.off);             // 纯 JS 赋值

   用户机器上没有 `/config/www/lixiang-icons/` 时，`/local/lixiang-icons/...` 全部 404
   → **永久破图**。实测：7 个快捷按钮 7 个全破。

② 只靠 onerror 也不够 —— 必须在渲染前就把基址切对
   新增「整页只探一次 /local/lixiang-icons」：不存在 → 把各卡的 `__iconBase`
   切到集成内置路径，并就地改写已渲染的 /local 图标。

★ 踩过的坑（本测试专门钉住）
   首版把探测块插在 `__lxIconFallback` 定义之后，但它引用的
   `DEFAULT_ICON_BASE` / `__iconBase` / `__iconFallback` 声明在文件更下面
   → **TDZ ReferenceError**，探测根本没跑起来（`node --check` 只查语法，查不出）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
APP_HOME = CARDS / "lixiang-app-home.js"

MARK = "// —— 图标基址自动降级（★ 2026-10-14）——"


def _cards_with_icons() -> list[Path]:
    out = []
    for f in sorted(CARDS.glob("*.js")):
        s = f.read_text(encoding="utf-8")
        if "__iconBase" in s:
            out.append(f)
    return out



def _strip_comments(s: str) -> str:
    """去 JS 注释 —— 注释里可能出现被断言的词（如本文件说明中的 document.querySelector）。"""
    out, i, n = [], 0, len(s)
    while i < n:
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i)
            i = n if j < 0 else j + 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _snippet(f: Path) -> str:
    s = f.read_text(encoding="utf-8")
    i = s.find(MARK)
    if i < 0:
        return ""
    j = s.find("\n}\n", i)
    return s[i:j + 3]


class TestDowngradeBlockPresent:
    def test_there_are_cards_to_check(self):
        assert len(_cards_with_icons()) >= 10, "用图标的卡片太少，断言可能空转"

    @pytest.mark.parametrize("f", _cards_with_icons(), ids=lambda p: p.name)
    def test_every_icon_card_has_downgrade(self, f: Path):
        """所有用 ${__iconBase} 的卡片都要有自动降级块。"""
        assert MARK in f.read_text(encoding="utf-8"), (
            f"{f.name}: 缺图标基址自动降级块 —— 没有 /local 目录的用户会破图")

    @pytest.mark.parametrize("f", _cards_with_icons(), ids=lambda p: p.name)
    def test_downgrade_placed_after_declarations(self, f: Path):
        """★ 防 TDZ：探测块必须在 `__iconFallback` 声明**之后**。

        首版插在 __lxIconFallback 之后（文件更上面）→ 运行时 ReferenceError，
        探测静默失效。`node --check` 查不出这类错误。
        """
        s = f.read_text(encoding="utf-8")
        i_decl = s.find("const __iconFallback")
        i_mark = s.find(MARK)
        assert i_decl > 0 and i_mark > 0, f"{f.name}: 缺少声明或探测块"
        assert i_mark > i_decl, (
            f"{f.name}: 探测块在 __iconFallback 声明之前 —— 会因 TDZ 抛错而失效")

    @pytest.mark.parametrize("f", _cards_with_icons(), ids=lambda p: p.name)
    def test_downgrade_declares_globals_once(self, f: Path):
        """整页只探一次：用 window.__lxIconProbing 做锁，回调列表共享。"""
        code = _snippet(f)
        assert "window.__lxIconProbing" in code, f"{f.name}: 缺探测锁"
        assert "window.__lxIconCbs" in code, f"{f.name}: 缺回调列表（多卡片共享探测结果）"


class TestJsAssignedIconsHaveFallback:
    """JS 赋值图标（无模板 onerror）必须有 other 兜底。"""

    def test_quick_button_has_onerror(self):
        s = APP_HOME.read_text(encoding="utf-8")
        m = re.search(r'd\.innerHTML = `<div class="c"><img[^>]*>', s)
        assert m, "未找到快捷按钮模板"
        assert 'onerror="__lxIconFallback(this)"' in m.group(0), (
            "快捷按钮 img 缺 onerror 兜底（/local 存在但个别图标缺失时会破图）")


class TestDowngradeBehavior:
    """node 真跑注入的探测块，验证两条分支。"""

    def _run(self, probe_fails: bool) -> str:
        snip = _snippet(APP_HOME)
        assert snip, "未提取到探测块"
        code = f"""
        let __iconBase = "/local/lixiang-icons";
        const __iconFallback = "/lixiang_auto/lixiang-icons";
        const DEFAULT_ICON_BASE = "/local/lixiang-icons";
        const rewritten = [];
        globalThis.window = {{}};
        globalThis.document = {{ querySelectorAll: () => [] }};
        globalThis.Image = class {{
          set src(v) {{ queueMicrotask(() => {{ if (this.{'onerror' if probe_fails else 'onload'}) this.{'onerror' if probe_fails else 'onload'}(); }}); }}
        }};
        {snip}
        await new Promise(r => setTimeout(r, 20));
        process.stdout.write(__iconBase + "|" + (window.__lxIconBaseMissing ? "1" : "0"));
        """
        r = subprocess.run(["node", "--input-type=module", "-e", code],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:600]
        return r.stdout.strip()

    def test_switches_to_builtin_when_local_missing(self):
        base, missing = self._run(probe_fails=True).split("|")
        assert base == "/lixiang_auto/lixiang-icons", f"探测失败时未切内置：{base}"
        assert missing == "1", "未记录 window.__lxIconBaseMissing"

    def test_keeps_local_when_present(self):
        base, missing = self._run(probe_fails=False).split("|")
        assert base == "/local/lixiang-icons", f"探测成功时不应改基址：{base}"
        assert missing == "0", "不应记录为缺失"

class TestSnippetCompliance:
    """探测块必须遵守卡片通用约定（见 tests/test_frontend_cards.py）。"""

    @pytest.mark.parametrize("f", _cards_with_icons(), ids=lambda p: p.name)
    def test_no_global_dom_query(self, f: Path):
        """★ 不得用 document.querySelector —— HA 卡片在 Shadow DOM 内，查不到。

        首版实现用 `document.querySelectorAll('img[src^="/local/..."]')` 做改写：
        既违反约定，又在真实 HA 里**完全无效**（我的 light DOM 测试环境掩盖了这点）。
        """
        code = _strip_comments(_snippet(f))
        assert code, f"{f.name}: 未提取到探测块"
        assert not re.search(r"document\.(querySelector|getElementById|getElementsBy)", code), (
            f"{f.name}: 探测块用了全局选择器（Shadow DOM 内查不到，等于无效代码）")


class TestQuickIconReassignment:
    """JS 重新赋值图标时的守卫（否则回退救回来的图标会被再次写坏）。"""

    def test_clears_fallback_guard_before_reassign(self):
        s = APP_HOME.read_text(encoding="utf-8")
        i = s.find("_applyQuick()")
        seg = s[i:i + 3000]
        assert "delete img.dataset.lxFb" in seg, (
            "重新赋值图标前必须清掉 dataset.lxFb（__lxIconFallback 是一次性保护，"
            "否则第二次赋值后不再回退 → 永久破图）")

    def test_only_assigns_when_changed(self):
        s = APP_HOME.read_text(encoding="utf-8")
        i = s.find("_applyQuick()")
        seg = s[i:i + 3000]
        assert 'img.getAttribute("src") !== want' in seg, (
            "应只在目标变化时赋值，避免把已回退成功的内置图标再写回 /local")
