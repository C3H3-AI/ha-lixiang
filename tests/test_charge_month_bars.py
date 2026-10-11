"""充电页历史 —— 月电量迷你条形图（2026-10-11）。

为什么加
--------
能量页的每日数据有迷你条形图（`.dbar`），而充电页的月度历史是**纯文字**
（`N 月 | X 次 | Y kWh`）—— 两处都是「历史数据」，一个可视化一个没有，
体验不一致。

本改动给充电页月行加条形（`.mbar`），**按当年最大月归一**
（跨年不可比，故按年算基准），并对最大月加 `.top` 高亮。

★ 用的是 node 真跑渲染逻辑（不是只用字符串断言）—— 沿用本仓库的教训：
  「断言落在注释/字符串上 → 测试永远不红」。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-charge-page.js"

#: 一个月的充电记录（服务端形态）
SAMPLE = [
    {"year": 2026, "month": 10, "chargingTimes": 5, "chargingCapacity": 80.0},
    {"year": 2026, "month": 9, "chargingTimes": 8, "chargingCapacity": 160.0},
    {"year": 2026, "month": 8, "chargingTimes": 2, "chargingCapacity": 20.0},
]


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:800]
    return r.stdout


def _render_fn() -> str:
    """从真实源码里抽出「月行渲染」那段（不复制逻辑，避免测副本）。

    抽的是 `_renderYears` 里构造 rows 的那一段 —— 用真实的 mvals/mmax/mtop
    计算与模板拼接，确保改坏了会被抓到。
    """
    src = PAGE.read_text(encoding="utf-8")
    i = src.index("const mvals = y.months.map")
    j = src.index("}).join(\"\");", i) + len("}).join(\"\");")
    return src[i:j]


HARNESS_HEAD = """
const I18N = { times: "\u6b21" };
const ctx = { _selMonth: null };
const render = function (y) {
"""
HARNESS_TAIL = """
  return rows;
};
console.log(render.call(ctx, DATA));
"""


def harness(rows: list[dict]) -> str:
    """拼出可执行的 node 脚本：真实源码片段 + 注入的月份数据。

    ★ 用 `render.call(ctx, ...)` 绑定 this —— 源码里用到了 `this._selMonth`
      （选中月高亮），不绑定会 ReferenceError。
    """
    # ★ 必须带 year —— 生产代码里 y 是 {year, months}（行内用 y.year 作 data-y）
    data = json.dumps({"year": 2026, "months": rows}, ensure_ascii=False)
    return HARNESS_HEAD + _render_fn() + HARNESS_TAIL.replace("DATA", data)


class TestBarsRendered:
    def test_every_month_has_bar(self):
        out = run_node(harness(SAMPLE))
        assert out.count('class="mbar"') == 3, "每个月都应有条形"

    def test_width_relative_to_year_max(self):
        """★ 最大月 100%，其余按比例（160 → 100%，80 → 50%，20 → 12.5%→13%）"""
        out = run_node(harness(SAMPLE))
        assert "width:100%" in out, "最大月应占满"
        assert "width:50%" in out, "80/160 = 50%"
        assert "width:13%" in out, "20/160 ≈ 13%"

    def test_small_value_still_visible(self):
        """极小值也要看得见（最小 3%）—— 否则条形宽度为 0 等于没画。"""
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 1, "chargingCapacity": 100.0},
            {"year": 2026, "month": 9, "chargingTimes": 1, "chargingCapacity": 0.5},
        ]
        out = run_node(harness(rows))
        assert "width:3%" in out, "0.5/100 应被抬到 3% 下限"

    def test_zero_capacity_gives_zero_width(self):
        """0 kWh 的月份不应有可见条形（但结构仍在）。"""
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 3, "chargingCapacity": 30.0},
        ]
        out = run_node(harness(rows))
        assert "width:0%" in out

    def test_all_zero_no_nan(self):
        """全 0 → 不能出现 NaN%（除数保护）。"""
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 0, "chargingCapacity": 0},
        ]
        out = run_node(harness(rows))
        assert "NaN" not in out, "全 0 时会出现 NaN% —— 必须有除数保护"
        assert "Infinity" not in out


class TestTopHighlight:
    def test_max_month_marked(self):
        out = run_node(harness(SAMPLE))
        assert out.count("m top") == 1, "应只有一个最大月被高亮"

    def test_top_is_the_largest(self):
        """★ 高亮的必须是 9 月（160 kWh），不是第一行。"""
        out = run_node(harness(SAMPLE))
        i = out.index("m top")
        seg = out[i:i + 160]
        assert 'data-m="9"' in seg, "高亮的应是 9 月（160 kWh）"

    def test_no_highlight_when_all_zero(self):
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 0, "chargingCapacity": 0},
        ]
        out = run_node(harness(rows))
        assert "m top" not in out, "全 0 时不该有高亮"


class TestExistingBehaviorPreserved:
    def test_month_label_and_values_kept(self):
        out = run_node(harness(SAMPLE))
        assert "10 月" in out and "9 月" in out
        assert "160.0" in out and "kWh" in out

    def test_charging_times_kept(self):
        out = run_node(harness(SAMPLE))
        assert "8 次" in out, "次数不能丢"

    def test_click_attrs_kept(self):
        """月行仍带 data-y/data-m（点击选月的依赖）。"""
        out = run_node(harness(SAMPLE))
        assert 'data-y="2026"' in out and 'data-m="9"' in out

    def test_aria_hidden_on_decorative_bar(self):
        """★ 条形是装饰，必须 aria-hidden —— 否则读屏会念出无意义的空元素。"""
        out = run_node(harness(SAMPLE))
        assert 'class="mbar" aria-hidden="true"' in out


class TestSourceGuards:
    def test_css_defined(self):
        s = PAGE.read_text(encoding="utf-8")
        assert ".m .mbar {" in s, "缺条形样式"
        assert ".m .mbar > i {" in s, "缺条形填充样式"
        assert ".m.top .mv" in s, "缺最大值高亮样式"

    def test_normalized_per_year_not_global(self):
        """★ 基准必须是「当年最大月」—— 跨年不可比（2024 的 100 与 2025 的 100 无关）。"""
        s = PAGE.read_text(encoding="utf-8")
        i = s.index("const mvals = y.months.map")
        blk = s[i:i + 400]
        assert "y.months" in blk, "应按年内的 months 计算基准"
        assert "this._years" not in blk, "不能用跨年的全局数据当基准"

    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(PAGE)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]