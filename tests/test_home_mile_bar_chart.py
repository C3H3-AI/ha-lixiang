"""首页里程卡 —— 本月每日里程图（2026-10-12）。

车主发来 App 首页截图（充满电状态），逐块对比后发现唯一明显差异：

    App：柱状图（多根等宽柱子 + 网格线 + 01/08/15/22/29 轴）
    我们：**折线图**（`polyline`）

本文件守住「改成柱状图」这件事，并把关键算法（等宽、归一、0 值处理）用
node 真跑一遍 —— 而不是只查字符串存在。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOME = (ROOT / "custom_components" / "lixiang_auto" / "www"
        / "lixiang-cards" / "lixiang-app-home.js")


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:700]
    return r.stdout


def _method(name: str) -> str:
    """从源码按花括号配平抽出方法体（不抄副本）。"""
    s = _src()
    i = s.index(f"  {name}(")
    j = s.index("{", i)
    depth, k = 0, j
    while k < len(s):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    sig = s[i:j]
    return f"{sig}{{{s[j + 1:k]}}},"


def harness(vals_js: str) -> str:
    """最小宿主：只需 querySelector / _st / _dailyCache。"""
    return (
        "let RECTS = '';\n"
        f"const VALS = {vals_js};\n"
        "const box = { set innerHTML(v) { RECTS = v; }, get innerHTML() { return RECTS; } };\n"
        "const G = {\n"
        "  _dailyCache: VALS.map(v => ({ mileage: v })),\n"
        "  _config: {},\n"
        "  _st() { return null; },\n"
        "  querySelector(sel) { return sel === '#sparkbars' ? box : null; },\n"
        f"{_method('_spark')}\n"
        "};\n"
        "G._spark();\n"
        "process.stdout.write(RECTS);\n"
    )


def rects(html: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" '
                         r'height="([\d.]+)"( data-zero="1")?>', html):
        out.append({"x": float(m.group(1)), "y": float(m.group(2)),
                    "w": float(m.group(3)), "h": float(m.group(4)),
                    "zero": bool(m.group(5))})
    return out


SAMPLE = [0, 40, 120, 300, 0, 80, 10]


class TestMarkup:
    def test_uses_rect_group_not_polyline(self):
        s = _src()
        assert 'id="sparkbars"' in s, "缺柱状图容器"
        assert "<polyline" not in s, "还在用折线（polyline）"

    def test_grid_lines_present(self):
        """App 的柱状图带网格线。"""
        s = _src()
        assert 'id="sparkgrid"' in s, "缺网格线组"
        assert s.count('<line x1="0"') >= 3, "网格线少于 3 条"

    def test_axis_labels_kept(self):
        s = _src()
        i = s.index('class="axis"')
        for lab in ("01", "08", "15", "22", "29"):
            assert f">{lab}<" in s[i:i + 260], f"缺坐标轴标签 {lab}"

    def test_css_for_bars(self):
        s = _src()
        assert "#sparkbars rect {" in s, "缺柱子填充样式"
        assert "#sparkbars rect[data-zero]" in s, "0 值柱子没有特殊处理"
        assert "#sparkgrid line" in s, "缺网格线样式"


class TestBarGeometry:
    """node 真跑 `_spark`，检查生成的柱子几何。"""

    def test_one_rect_per_value(self):
        out = run_node(harness(json.dumps(SAMPLE)))
        assert len(rects(out)) == len(SAMPLE), "柱子数应与数据点数一致"

    def test_bars_are_equal_width(self):
        """★ App 的柱子是**等宽**的。"""
        out = run_node(harness(json.dumps(SAMPLE)))
        ws = {r["w"] for r in rects(out)}
        assert len(ws) == 1, f"柱宽不一致: {ws}"

    def test_bars_ordered_left_to_right(self):
        out = run_node(harness(json.dumps(SAMPLE)))
        xs = [r["x"] for r in rects(out)]
        assert xs == sorted(xs), "柱子未按数据顺序排列"

    def test_height_normalized_to_max(self):
        """最高值应占满可用高度（34），其余按比例。"""
        out = run_node(harness(json.dumps(SAMPLE)))
        rs = rects(out)
        hmax = max(r["h"] for r in rs)
        assert abs(hmax - 34) < 0.01, f"最高柱高度应为 34，实际 {hmax}"
        # 300 是最大值 → 其高度为 34；120 应为 34*120/300=13.6
        h120 = rs[2]["h"]
        assert abs(h120 - 13.6) < 0.05, f"300→120 的比例不对: {h120}"

    def test_zero_values_not_drawn(self):
        """0 值不能画成实心柱（否则会出现假的"有里程"）。"""
        out = run_node(harness(json.dumps(SAMPLE)))
        zs = [r for r in rects(out) if r["zero"]]
        assert len(zs) == 2, f"SAMPLE 里有 2 个 0，实际标记 {len(zs)} 个"
        for r in zs:
            assert r["h"] <= 0.61, f"0 值柱高应为最小值，实际 {r['h']}"

    def test_no_negative_or_over_height(self):
        out = run_node(harness(json.dumps(SAMPLE)))
        for r in rects(out):
            assert 0 < r["h"] <= 34.01, f"柱高越界: {r['h']}"
            assert 0 <= r["x"] and r["x"] + r["w"] <= 100.01, "柱子横向越界"

    def test_single_value_works(self):
        """只有一天数据时不该除以 0 或越界。"""
        out = run_node(harness(json.dumps([120])))
        rs = rects(out)
        assert len(rs) == 1
        assert rs[0]["w"] > 0 and 0 < rs[0]["h"] <= 34.01

    def test_all_zero_does_not_crash(self):
        """全是 0 —— max 会被兜底为 1，不能出现 NaN。"""
        out = run_node(harness(json.dumps([0, 0, 0])))
        rs = rects(out)
        assert len(rs) == 3
        assert all(r["zero"] for r in rs)
        assert "NaN" not in out and "Infinity" not in out

    def test_empty_clears(self):
        out = run_node(harness("[]"))
        assert out.strip() == "", "无数据时应清空容器"

    def test_nan_input_tolerated(self):
        """接口偶尔给 null/字符串 —— 必须退化为 0 而不是 NaN。"""
        out = run_node(harness('[null, "x", 120]'))
        assert "NaN" not in out, "出现了 NaN"
        rs = rects(out)
        assert len(rs) == 3


class TestSource:
    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(HOME)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]

    def test_no_leftover_sparkline_id(self):
        s = _src()
        assert "sparkline" not in s, "残留旧的折线元素 id"