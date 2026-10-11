"""充电页月度列表 —— 条形图 + 扁平结构（2026-10-11）。

两轮改动叠加
------------
1. **加条形图**：能量页有 `.dbar`，充电页原本是纯文字 → 补上月电量迷你条形
2. **改扁平结构**：车主反馈「点击10月，明细在下面，根本看不到」
   → 从「按年折叠 + 明细渲染在页面底部」改为「**扁平列表 + 内联展开**」（照 App）

★ 本测试用 **node 真跑** `_renderYears()` 的真实源码（方法体是抽取的，不是副本），
  注入 `_years` 结构 + `box` 桩来取回渲染出的 HTML。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "custom_components" / "lixiang_auto" / "www"
        / "lixiang-cards" / "lixiang-charge-page.js")

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


def _render_years_body() -> str:
    """抽取真实的 `_renderYears` **方法体**（不含签名与结尾闭合括号）。

    ★ 必须剥掉签名 —— harness 已经用 `const fn = function () { ... }` 包了一层，
      再带 `_renderYears() {` 会变成嵌套方法定义 → node 报语法错误。
    """
    src = PAGE.read_text(encoding="utf-8")
    sig = src.index("_renderYears() {")
    start = src.index("{", sig) + 1                      # 跳过 `) {`
    nxt = src.index("_renderList() {", sig)              # 下一个方法的起点
    end = src.rindex("}", start, nxt)                    # _renderYears 的闭合括号
    return src[start:end]


HARNESS_HEAD = """
const I18N = { times: "\u6b21", chargePrefix: "\u5145\u7535", loading: "..", noData: "-" };
// ★ box 桩要提供 querySelector/querySelectorAll —— _renderYears 末尾会绑定
//   月份行事件（.mh），缺这些方法会 TypeError。
const BOX = {
  innerHTML: "",
  querySelector: () => null,
  querySelectorAll: () => [],
};
const ctx = {
  _years: DATA,
  _selMonth: null,
  _error: null,
  _fetching: false,
  _a11y: () => {},
  querySelector: () => BOX,
  querySelectorAll: () => [],
};
const fn = function () {
"""
HARNESS_TAIL = """
  return BOX.innerHTML;
};
console.log(fn.call(ctx));
"""


def harness(rows: list[dict], year: int = 2026,
            extra_years: list[dict] | None = None) -> str:
    years = [{"year": year, "months": rows}]
    if extra_years:
        years += extra_years
    data = json.dumps(years, ensure_ascii=False)
    return HARNESS_HEAD.replace("DATA", data) + _render_years_body() + HARNESS_TAIL


class TestBarsRendered:
    def test_every_month_has_bar(self):
        out = run_node(harness(SAMPLE))
        assert out.count('class="mbar"') == 3, "每个月都应有条形"

    def test_width_relative_to_year_max(self):
        """最大月 100%，其余按比例（160 → 100%，80 → 50%，20 → 13%）。"""
        out = run_node(harness(SAMPLE))
        assert "width:100%" in out, "最大月应占满"
        assert "width:50%" in out, "80/160 = 50%"
        assert "width:13%" in out, "20/160 ≈ 13%"

    def test_small_value_still_visible(self):
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 1, "chargingCapacity": 100.0},
            {"year": 2026, "month": 9, "chargingTimes": 1, "chargingCapacity": 0.5},
        ]
        out = run_node(harness(rows))
        assert "width:3%" in out, "0.5/100 应被抬到 3% 下限"

    def test_zero_capacity_gives_zero_width(self):
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 3, "chargingCapacity": 30.0},
        ]
        out = run_node(harness(rows))
        assert "width:0%" in out

    def test_all_zero_no_nan(self):
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 0, "chargingCapacity": 0},
        ]
        out = run_node(harness(rows))
        assert "NaN" not in out, "全 0 时会出现 NaN% —— 必须有除数保护"
        assert "Infinity" not in out

    def test_normalized_per_year_not_global(self):
        """★ 按【所在年】归一 —— 跨年不可比。"""
        rows = [{"year": 2026, "month": 10, "chargingTimes": 1, "chargingCapacity": 100.0}]
        older = [{"year": 2025, "months": [
            {"year": 2025, "month": 8, "chargingTimes": 1, "chargingCapacity": 10.0}]}]
        out = run_node(harness(rows, extra_years=older))
        assert out.count("width:100%") == 2, \
            "每年应各自按该年最大值归一（跨年不共用基准）"


class TestTopHighlight:
    def test_max_month_marked(self):
        out = run_node(harness(SAMPLE))
        assert out.count("month top") == 1, "应只有一个最大月被高亮"

    def test_top_is_the_largest(self):
        out = run_node(harness(SAMPLE))
        i = out.index("month top")
        assert 'data-m="9"' in out[i:i + 200], "高亮的应是 9 月（160 kWh）"

    def test_no_highlight_when_all_zero(self):
        rows = [
            {"year": 2026, "month": 10, "chargingTimes": 0, "chargingCapacity": 0},
            {"year": 2026, "month": 9, "chargingTimes": 0, "chargingCapacity": 0},
        ]
        out = run_node(harness(rows))
        assert "month top" not in out, "全 0 时不该有高亮"


class TestExistingBehaviorPreserved:
    def test_month_label_and_values_kept(self):
        out = run_node(harness(SAMPLE))
        assert "10 月" in out and "9 月" in out
        assert "160.00" in out and "kW·h" in out, "单位应与 App 一致（kW·h）"

    def test_charging_times_kept(self):
        out = run_node(harness(SAMPLE))
        assert "8" in out and "次" in out, "次数不能丢"

    def test_click_attrs_kept(self):
        out = run_node(harness(SAMPLE))
        assert 'data-y="2026"' in out and 'data-m="9"' in out

    def test_aria_hidden_on_decorative_bar(self):
        out = run_node(harness(SAMPLE))
        assert 'class="mbar" aria-hidden="true"' in out


class TestYearFolding:
    """★ 年份折叠 + 月份内联明细（车主："充电明细建议按年也折叠"）。

    演进：按年折叠（明细在底部看不到）→ 扁平+内联 → **年份折叠+内联**（兼顾）。
    """

    def test_year_group_present(self):
        out = run_node(harness(SAMPLE))
        assert 'class="year' in out and 'data-year="2026"' in out, "应有年份分组"

    def test_year_header_summary(self):
        """年份头应带汇总（月数 / 次数 / 总电量）。"""
        out = run_node(harness(SAMPLE))
        assert "3 个月" in out, "年份头应显示月数"
        assert "15" in out, "年份头应显示总次数（5+8+2）"
        assert "260.0" in out, "年份头应显示总电量（80+160+20）"

    def test_month_rows_inside_year(self):
        out = run_node(harness(SAMPLE))
        assert out.count("class=\"month") == 3 or out.count('class="month') == 3

    def test_inline_detail_container_kept(self):
        """★ 月份内联明细必须保留（车主认可的交互，不要在重构中丢掉）。"""
        out = run_node(harness(SAMPLE))
        assert out.count('class="md" id="md-2026-') == 3, "每个月都要有内联明细容器"

    def test_latest_year_expanded_by_default(self):
        """有数据时默认展开最新年份（否则用户先看到全收起）。"""
        s = PAGE.read_text(encoding="utf-8")
        i = s.index("_renderYears() {")
        blk = s[i:s.index("_renderList() {", i)]
        assert "!this._openYears.size" in blk, "应有默认展开最新年的逻辑"

    def test_multiple_years_both_have_headers(self):
        rows = [{"year": 2026, "month": 10, "chargingTimes": 1, "chargingCapacity": 10.0}]
        older = [{"year": 2025, "months": [
            {"year": 2025, "month": 8, "chargingTimes": 2, "chargingCapacity": 53.88}]}]
        out = run_node(harness(rows, extra_years=older))
        assert 'data-year="2026"' in out and 'data-year="2025"' in out, "每年一个分组"


class TestSourceGuards:
    def test_css_defined(self):
        s = PAGE.read_text(encoding="utf-8")
        assert ".month .mbar {" in s, "缺条形样式"
        assert ".month .mbar > i {" in s, "缺条形填充样式"
        assert ".month.top .mv" in s, "缺最大值高亮样式"
        assert ".month.open .md { display:block; }" in s, "缺内联展开样式"

    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(PAGE)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]