"""UI 主题变量一致性 —— 全页面守卫（2026-10-11）。

问题（实测扫描发现）
--------------------
同一套 UI 里，各页面**各自复制**了主题变量，导致取值漂移：

| 变量 | 修复前 | 影响 |
|---|---|---|
| `--lx-card`（亮）| `#F7F7F9` ×8 vs `#F5F5F7` ×6 | 卡片背景在页面切换时色值跳变 |
| `--lx-line`（亮）| `#F0F0F2` ×8 vs `#EDEDF0` ×5 vs `#ECECEF` ×1 | 分隔线 3 种值 |
| `--lx-green`（亮）| `#34C759` ×9 vs `#3CC75A` ×2 | 绿色不一致 |
| `--lx-t1/t2/t3`（暗）| **13 个页面**用 iOS 色板，**只有 `lixiang-base.js`** 用 `#FFF`/`#AAA`/`#777` | 唯一使用 base 的 info 页在暗色下文字过亮、对比度与其他页不一致 |

统到多数派（更接近 iOS 规范：`#34C759` 是 iOS systemGreen、`#F2F2F7` 是 systemGray6），
7 个文件被改。

本测试是**全页面守卫**：任何页面引入新的不一致值都会红。
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"

#: 必须全页面一致的「核心」变量（页面专用变量如 --lx-seat / --lx-tire 不在此列）
LIGHT_CORE = ("--lx-card", "--lx-line", "--lx-green", "--lx-blue", "--lx-bg")
DARK_CORE = ("--lx-bg", "--lx-card", "--lx-line", "--lx-t1", "--lx-t2",
             "--lx-t3", "--lx-blue")

#: 期望值（统一后的标准；改动时必须全页面一起改，否则本测试会红）
EXPECT_LIGHT = {
    "--lx-card": "#F7F7F9",
    "--lx-line": "#F0F0F2",
    "--lx-green": "#34C759",
}
EXPECT_DARK = {
    "--lx-bg": "#000",
    "--lx-card": "#1C1C1E",
    "--lx-line": "#2C2C2E",
    "--lx-t1": "#F2F2F7",
    "--lx-t2": "#AEAEB2",
    "--lx-t3": "#8E8E93",
    "--lx-blue": "#4C9AFF",
}


def _files() -> list[Path]:
    return sorted(p for p in CARDS.glob("*.js") if p.name != "lixiang-base.js")


def _light_vars(path: Path) -> dict[str, str]:
    """亮色变量 —— 取 `prefers-color-scheme` 块【之前】的定义。"""
    s = path.read_text(encoding="utf-8")
    head = s.split("prefers-color-scheme")[0]
    return {k: v.strip() for k, v in
            re.findall(r'(--lx-[\w-]+)\s*:\s*([^;]+);', head)}


def _dark_vars(path: Path) -> dict[str, str]:
    s = path.read_text(encoding="utf-8")
    m = re.search(r'prefers-color-scheme:\s*dark\)\s*\{\s*:host\s*\{([^}]*)\}', s)
    if not m:
        return {}
    return {k: v.strip() for k, v in
            re.findall(r'(--lx-[\w-]+)\s*:\s*([^;]+);', m.group(1))}


class TestLightConsistency:
    def test_card_line_green_are_uniform(self):
        """★ 核心守卫：这三个变量在全页面必须唯一。"""
        for var in ("--lx-card", "--lx-line", "--lx-green"):
            seen = collections.Counter()
            for f in _files():
                v = _light_vars(f).get(var)
                if v:
                    seen[v] += 1
            assert len(seen) <= 1, (
                f"{var} 在页面间不一致: {dict(seen)} —— "
                "颜色漂移会让页面切换时出现肉眼可见的色差")

    def test_expected_values(self):
        """锁定统一后的标准值（防止有人改回粗糙值）。"""
        for var, want in EXPECT_LIGHT.items():
            for f in _files():
                got = _light_vars(f).get(var)
                if got is None:
                    continue          # 该页面没定义此变量，不算错
                assert got == want, (
                    f"{f.name} 的 {var} = {got}，期望 {want}"
                    "（要改就全页面一起改，并同步本测试与 base）")


class TestDarkConsistency:
    def test_core_vars_uniform(self):
        for var in DARK_CORE:
            seen = collections.Counter()
            for f in _files():
                v = _dark_vars(f).get(var)
                if v:
                    seen[v] += 1
            assert len(seen) <= 1, f"暗色 {var} 不一致: {dict(seen)}"

    def test_expected_dark_values(self):
        """★ 这是本轮修的核心 bug：base 曾用 #FFF/#AAA/#777（过亮、对比度不一致）。"""
        for var, want in EXPECT_DARK.items():
            for f in _files():
                got = _dark_vars(f).get(var)
                if got is None:
                    continue
                assert got == want, f"{f.name} 暗色 {var} = {got}，期望 {want}"

    def test_base_matches_pages(self):
        """★ 共享基座必须与其他页面用**同一套**值 ——
        它曾经是唯一不同的那个（且反而是它在被使用）。"""
        base = CARDS / "lixiang-base.js"
        d = _dark_vars(base)
        for var, want in EXPECT_DARK.items():
            if var in d:
                assert d[var] == want, f"base 暗色 {var} = {d[var]}，期望 {want}"

    def test_t1_not_pure_white(self):
        """★ 纯白 #FFF 在暗色下过亮（刺眼）—— iOS 用 #F2F2F7。"""
        for f in list(_files()) + [CARDS / "lixiang-base.js"]:
            v = _dark_vars(f).get("--lx-t1")
            if v:
                assert v.upper() != "#FFF", (
                    f"{f.name} 暗色主文字用了纯白 #FFF（应为 #F2F2F7）")


class TestNoDriftRegression:
    def test_every_page_defining_card_uses_one_value(self):
        """通用守卫：任何页面新写一个不同的 card 值都会被抓到。"""
        vals = {f.name: _light_vars(f).get("--lx-card") for f in _files()}
        vals = {k: v for k, v in vals.items() if v}
        distinct = set(vals.values())
        assert len(distinct) == 1, f"card 有多个值: {vals}"

    def test_regex_would_catch_a_drift(self, tmp_path):
        """★ 自检：证明这套检测**真的能发现**不一致（否则守卫是装饰品）。

        构造一个写错值的文件，断言解析函数确实读出了不同的值。
        """
        bad = tmp_path / "lixiang-fake-page.js"
        bad.write_text(":host{--lx-card:#123456;--lx-line:#F0F0F2;}\n"
                       "@media (prefers-color-scheme: dark){:host{--lx-t1:#F2F2F7;}}",
                       encoding="utf-8")
        got = _light_vars(bad)
        assert got.get("--lx-card") == "#123456", "解析函数必须能读出真实值"
        assert got["--lx-card"] != EXPECT_LIGHT["--lx-card"], "自检：应判别为漂移"


class TestSyntaxAfterChange:
    def test_all_touched_files_parse(self):
        """被本轮改动过的 7 个文件语法必须正确（用 node --check）。"""
        import subprocess
        names = ["lixiang-base.js", "lixiang-charge-page.js", "lixiang-energy-page.js",
                 "lixiang-health-page.js", "lixiang-scene-page.js",
                 "lixiang-task-page.js", "lixiang-vehicle-info-page.js"]
        for n in names:
            r = subprocess.run(["node", "--check", str(CARDS / n)],
                               capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, f"{n} 语法错误: {r.stderr[:200]}"