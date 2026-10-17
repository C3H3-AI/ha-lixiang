"""卡片源文件语法检查 —— 防止「改一行注释就整卡白屏」。

★ 2026-10-16 真实事故
---------------------
改 `lixiang-app-home.js` 时在 **CSS 注释里用了反引号**：

    /* 原来是 `.big3d, .root.expanded3d .big3d { height:188px }` —— 裸 .big3d */

但整个 CSS 是写在 JS **模板字符串**（反引号）里的 → 注释里的反引号**提前终结了模板字符串**
→ 整个文件语法错误 → 卡片在浏览器里直接白屏（`SyntaxError: Unexpected token '.'`）。

更糟的是当时用的是：

    node --check file.js 2>/dev/null && echo "✅ 语法通过"

`2>/dev/null` 把错误吞了、`&&` 的行为又被误读成"通过" → **差点把坏文件部署上去**。

所以这里补一条兜底：**每个卡片源文件都必须能被 JS 引擎解析**。
比"断言某个字符串存在"强得多 —— 它拦的是整类事故，而不是某一个写法。

为什么是 node --check 而不是自己写正则
--------------------------------------
模板字符串 / 正则字面量 / 嵌套引号的组合太多，正则根本判不准；
交给真正的解析器（node 已在 CI 里用于 TestRuntime 的 node 真跑测试）。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"

# node 是 TestRuntime 那批测试的前置依赖；缺失则跳过而不是误报
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 做语法检查")


def _card_files() -> list[Path]:
    # lixiang-all.js 是构建产物（拼接结果），源文件才是要检查的对象
    return sorted(p for p in CARDS.glob("lixiang-*.js") if p.name != "lixiang-all.js")


def test_card_files_exist():
    files = _card_files()
    assert len(files) >= 15, f"卡片源文件数量异常：{len(files)}"


@pytest.mark.parametrize("path", _card_files(), ids=lambda p: p.name)
def test_card_syntax_ok(path: Path):
    """每个卡片源文件都必须通过 JS 语法检查（失败时把引擎原话贴出来）。"""
    r = subprocess.run(["node", "--check", str(path)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (
        f"{path.name} 语法错误（卡片会白屏）：\n{r.stderr.strip()[:1200]}")


def test_bundle_exists_and_parses():
    """构建产物也要能解析 —— 单文件是真正下发到 HA 的东西。"""
    bundle = CARDS / "lixiang-all.js"
    assert bundle.is_file(), "缺少构建产物 lixiang-all.js，请先 node scripts/build-cards.mjs"
    r = subprocess.run(["node", "--check", str(bundle)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"lixiang-all.js 语法错误：\n{r.stderr.strip()[:1200]}"


def test_no_backtick_inside_css_comment():
    """★ 钉住本次事故的具体形态：CSS 模板字符串里的**注释块**不得含反引号。

    比语法检查更直白（语法检查只会说 "Unexpected token '.'"）。

    注意要按【注释块】而不是按行扫 —— 事故里的反引号在注释的第二行，
    按行判断（要求同一行同时有 /* 和 `）会漏掉。
    """
    import re
    bad: list[str] = []
    for f in _card_files():
        src = f.read_text(encoding="utf-8")
        # 抓 CSS 模板字符串：const STYLE = `...`  或  CSS: `...`
        for m in re.finditer(r"(?:const\s+[A-Za-z_$][\w$]*\s*=\s*|[\w$]+\s*:\s*)`", src):
            start = m.end()
            end = src.find("`", start)          # 这段模板字符串的结束位置
            if end < 0:
                continue
            body = src[start:end]
            # ① 反引号若落在**未闭合的注释块**里 → 它就是那个"提前终结模板字符串"的凶手
            #    （事故形态：/* 开了头，反引号在注释里，注释还没闭合就被它终结）
            if body.rfind("/*") > body.rfind("*/"):
                snippet = " ".join(body[body.rfind("/*"):].split())[:110]
                bad.append(f"{f.name}: 终止反引号落在未闭合注释里 -> {snippet}")
            # ② 已闭合的注释块内部也不得含反引号
            for c in re.finditer(r"/\*.*?\*/", body, re.S):
                if "`" in c.group(0):
                    bad.append(f"{f.name}: {' '.join(c.group(0).split())[:110]}")
    assert not bad, ("CSS 注释块里出现反引号（会提前终结模板字符串，导致整卡白屏）：\n"
                     + "\n".join(bad))
