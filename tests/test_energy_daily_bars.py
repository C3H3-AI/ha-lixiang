"""能量页每日行 —— 迷你条 + 排序（2026-10-11）。

背景
----
改造前每日数据只有「日期 + 数值」两列，**要逐行对比数字才能看出哪天跑得多**。
现在每行加一条**迷你条形**（以当月最大值为 100% 基准）+ 可切换排序。

为什么这个基准重要
------------------
条形宽度必须相对**当月最大值**，而不是绝对值 —— 否则
「月内最高那天」永远是满格、「有数据的日子」都差不多长，等于没信息。
另外 `v > 0` 时给 **3% 下限**：小数值也要看得见（否则 1km 和 0km 长得一样）。

★ 测试从源文件抽取 `_renderDaily` 与样式常量执行，不在测试里抄副本。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-energy-page.js"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:700]
    return r.stdout


def extract_method(src: str, name: str) -> str:
    i = src.index(f"\n  {name}(")
    j = src.index("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError(f"{name} 大括号不配平")


def _as_member(code: str) -> str:
    """方法定义 → 对象字面量成员（去外层花括号 + 补逗号）。"""
    code = code.strip()
    sig = code.split("{", 1)[0]
    body = code[code.index("{") + 1: code.rindex("}")]
    return f"{sig}{{{body}}},"


def harness(rows_js: str, tab: str, sort: bool) -> str:
    """最小宿主：只需 _selMonth / _monthDaily / _tab / _sort / querySelector / _a11y。"""
    src = PAGE.read_text(encoding="utf-8")
    members = "\n".join(_as_member(extract_method(src, n))
                        for n in ("_renderDaily", "_bindSort"))
    return (
        "const I18N = { noData:'\u6682\u65e0\u6570\u636e' };\n"
        f"const ROWS = {rows_js};\n"
        f"const TAB = {json.dumps(tab, ensure_ascii=False)};\n"
        f"let SORT = {str(sort).lower()};\n"
        "let CAPTURED = '';\n"
        "const dailyBox = {\n"
        "  set innerHTML(v) { CAPTURED = v; }, get innerHTML() { return CAPTURED; },\n"
        "  style: {},\n"
        # ★ 真实 DOM 元素有 querySelector/querySelectorAll；绑定排序/标签时需要
        "  querySelector() { return null; },\n"
        "  querySelectorAll() { return []; },\n"
        "};\n"
        "const G = {\n"
        "  _selMonth: { year: 2026, month: 10 },\n"
        "  _monthDaily: ROWS,\n"
        "  _tab: TAB,\n"
        "  get _sort() { return SORT; },\n"
        "  set _sort(v) { SORT = v; },\n"
        "  _a11y() {}, _bindTabs() {}, _bindSort() {},\n"
        # ★ 2026-10-12：明细改为内联到月份下方（参考充电页），
        #   选择器从 #daily 变为 #md-{year}-{month}；排序按钮去掉重复 id 改用 .sortbtn
        "  querySelector(sel) { return (sel === '#daily' || sel === '.sortbtn'"
        " || String(sel).indexOf('#md-') === 0) ? dailyBox : null; },\n"
        f"{members}\n"
        "};\n"
        "G._renderDaily();\n"
        "process.stdout.write(CAPTURED);\n"
    )


SAMPLE = [
    {"dayOfMonth": 1, "mileage": 0, "elecEnergy": 0, "fuelConsumption": 0},
    {"dayOfMonth": 2, "mileage": 120, "elecEnergy": 18.5, "fuelConsumption": 0},
    {"dayOfMonth": 3, "mileage": 40, "elecEnergy": 6.2, "fuelConsumption": 1.1},
    {"dayOfMonth": 4, "mileage": 300, "elecEnergy": 44.0, "fuelConsumption": 0},
]


def widths(html: str) -> list[int]:
    return [int(x) for x in re.findall(r'class="dbar"><i style="width:(\d+)%', html)]


def order(html: str) -> list[int]:
    return [int(x) for x in re.findall(r'class="dd">(\d+) 日', html)]


class TestMiniBars:
    def test_bar_relative_to_month_max(self):
        """★ 条形以【当月最大值】为 100%（不是绝对值）。"""
        html = run_node(harness(json.dumps(SAMPLE), "mileage", False))
        w = widths(html)
        assert w, "没有渲染迷你条"
        assert max(w) == 100, f"最大值那天应为满格，实际 {w}"
        # 120/300 = 40%；40/300 ≈ 13%；0 → 0%
        assert w[1] == 40, f"120/300 应为 40%，实际 {w[1]}"
        assert w[2] == 13, f"40/300 应为 13%，实际 {w[2]}"
        assert w[0] == 0, "零值不应有宽度"

    def test_small_values_still_visible(self):
        """★ 非零但很小的值也要看得见（下限 3%）—— 否则 1km 和 0km 一样。"""
        rows = [{"dayOfMonth": 1, "mileage": 1000, "elecEnergy": 0, "fuelConsumption": 0},
                {"dayOfMonth": 2, "mileage": 1, "elecEnergy": 0, "fuelConsumption": 0}]
        html = run_node(harness(json.dumps(rows), "mileage", False))
        w = widths(html)
        assert w[1] == 3, f"极小非零值应给 3% 下限，实际 {w[1]}"

    def test_top_day_highlighted(self):
        html = run_node(harness(json.dumps(SAMPLE), "mileage", False))
        assert 'class="drow top"' in html, "当月最高那天应高亮"
        assert html.count('class="drow top"') == 1, "只该高亮一天"

    def test_zero_max_no_nan(self):
        """全月都是 0 → 不能出现 NaN/undefined 宽度。"""
        rows = [{"dayOfMonth": i, "mileage": 0, "elecEnergy": 0, "fuelConsumption": 0}
                for i in (1, 2, 3)]
        html = run_node(harness(json.dumps(rows), "mileage", False))
        assert "NaN" not in html and "undefined" not in html
        assert set(widths(html)) <= {0}

    @pytest.mark.parametrize("tab,field", [
        ("mileage", "mileage"), ("elec", "elecEnergy"), ("fuel", "fuelConsumption"),
    ])
    def test_each_tab_uses_its_field(self, tab, field):
        html = run_node(harness(json.dumps(SAMPLE), tab, False))
        assert "NaN" not in html
        # 该 tab 的最大值那天应满格
        expect_max = max(r[field] for r in SAMPLE)
        if expect_max > 0:
            assert max(widths(html)) == 100, f"{tab} tab 应按 {field} 计算基准"


class TestSorting:
    def test_default_sorted_by_date(self):
        html = run_node(harness(json.dumps(SAMPLE), "mileage", False))
        assert order(html) == [1, 2, 3, 4], "默认按日期升序"

    def test_sort_by_value_desc(self):
        html = run_node(harness(json.dumps(SAMPLE), "mileage", True))
        assert order(html) == [4, 2, 3, 1], "按数值降序（300/120/40/0）"

    def test_sort_button_present(self):
        html = run_node(harness(json.dumps(SAMPLE), "mileage", False))
        assert 'class="sortbtn"' in html
        assert "按日期" in html
        html2 = run_node(harness(json.dumps(SAMPLE), "mileage", True))
        assert "按数值" in html2, "排序开启时按钮文案要变"

    def test_sort_binding_exists(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "  _bindSort(scope) {" in src, "必须有 _bindSort（否则按钮点了没反应）"
        assert "this._bindSort(box);" in src, "_renderDaily 末尾必须绑定排序按钮（带作用域）"


class TestPreserved:
    def test_tabs_still_work(self):
        """★ 改造不能破坏原有 tab 切换。"""
        html = run_node(harness(json.dumps(SAMPLE), "mileage", False))
        for t in ("每日里程", "每日耗电", "每日耗油"):
            assert t in html, f"tab {t} 丢了"

    def test_empty_state_kept(self):
        html = run_node(harness("[]", "mileage", False))
        assert "暂无数据" in html, "空数据要显示空态"

    def test_styles_present(self):
        src = PAGE.read_text(encoding="utf-8")
        assert ".dbar" in src and ".sortbtn" in src, "迷你条/排序按钮样式缺失"
        assert "min-width:44px" in src, "日期列需固定宽度，否则条形长度会跳"


class TestGuardSelfCheck:
    def test_harness_uses_real_source(self):
        h = harness(json.dumps(SAMPLE), "mileage", False)
        assert "_renderDaily" in h and "_bindSort" in h

class TestEnergyOptimizedLikeCharge:
    """★★ 2026-10-12：里程耗能页按「充电页」的模式优化（车主：「参考充电」）。

    充电页经过三轮迭代后的形态：
      · 年份折叠，**年份头带汇总**
      · 月份行带**条形图**（按所在年归一）
      · ★ **明细内联**在月份下方（不再渲染到页面底部 —— 那是充电页踩过的坑：
        车主原话「点击10月，明细在下面，根本看不到」）

    能耗页此前：年份折叠 ✓ 但月份行**没有条形图**、明细渲染到页面底部 `#daily` ✗
    """

    def _src(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_year_header_has_summary(self):
        """年份头要有「N 个月 · X km」汇总。"""
        s = self._src()
        i = s.index('box.innerHTML = yl.map((y) => {')
        blk = s[i:s.index('box.querySelectorAll(".yhead")', i)]
        assert 'class="ys"' in blk, "年份头缺汇总元素"
        assert "tot.toFixed(1)" in blk and "个月" in blk, "年份头缺汇总内容"

    def test_month_row_has_bar(self):
        """月份行要有条形图（对齐充电页）。"""
        s = self._src()
        i = s.index('box.innerHTML = yl.map((y) => {')
        blk = s[i:s.index('box.querySelectorAll(".yhead")', i)]
        assert 'class="mbar"' in blk, "月份行缺条形图"
        assert "const w = v > 0 ? Math.max(3" in blk, "条形宽度算法缺失"
        assert "const mx = Math.max(1," in blk, "缺按年归一的最大值"

    def test_month_has_inline_detail_container(self):
        """★ 每个月都要有内联明细容器（点开即在该月下方）。"""
        s = self._src()
        i = s.index('box.innerHTML = yl.map((y) => {')
        blk = s[i:s.index('box.querySelectorAll(".yhead")', i)]
        assert 'class="md" id="md-${y.year}-${m.month}"' in blk, "缺内联明细容器"

    def test_no_bottom_daily_container(self):
        """★ 页面底部的 `#daily` 必须删掉（否则又变成"明细在下面"）。"""
        s = self._src()
        assert 'id="daily"' not in s, "底部 #daily 容器还在"

    def test_render_daily_auto_locates_container(self):
        """未传容器时应自动定位到当前选中月份的内联容器。"""
        s = self._src()
        i = s.index("  _renderDaily(box) {")
        blk = s[i:i + 700]
        assert "#md-${this._selMonth.year}-${this._selMonth.month}" in blk, \
            "没有按选中月份自动定位容器"

    def test_month_click_toggles_inline(self):
        """点月份应切换内联展开（再点一次收起），而不是跳到别处。"""
        s = self._src()
        i = s.index('box.querySelectorAll(".m").forEach')
        blk = s[i:i + 1400]
        assert "classList.add(\"sel\")" in blk, "没有标记选中态"
        assert "classList.remove(\"sel\")" in blk, "再点一次没有收起"
        assert "target.innerHTML" in blk, "没有往内联容器渲染"

    def test_only_one_month_expanded(self):
        """展开新月份时应收起其它月份（避免列表被撑开）。"""
        s = self._src()
        i = s.index('box.querySelectorAll(".m").forEach')
        blk = s[i:i + 1400]
        assert 'box.querySelectorAll(".m.sel")' in blk, "没有收起其它已展开月份"

    def test_tabs_and_sort_are_scoped(self):
        """★ tabs/排序必须限定在**当前容器**内 —— 否则会绑到其它月份的按钮上。"""
        s = self._src()
        assert "  _bindTabs(scope) {" in s and "  _bindSort(scope) {" in s, \
            "tabs/排序未做作用域限定"
        assert "(scope || this).querySelectorAll(\".tab\")" in s
        assert '(scope || this).querySelector(".sortbtn")' in s

    def test_no_duplicate_dsort_id(self):
        """多个月份展开时 `#dsort` id 会重复 → 必须改用 class。"""
        s = self._src()
        assert 'id="dsort"' not in s, "重复 id 未清理"
        assert 'class="sortbtn' in s

    def test_css_rules_present(self):
        s = self._src()
        for rule in (".yhead .ys", ".m .mbar", ".m .md", ".m.sel .md"):
            assert rule in s, f"缺样式 {rule}"

    def test_month_row_is_block_not_flex(self):
        """`.m` 现在包着 `.mh` + `.md`，必须是 block（否则明细挤在同一行）。"""
        s = self._src()
        i = s.index("  .m { display:")
        seg = s[i:i + 60]
        assert "block" in seg, f".m 仍是 {seg.split(';')[0]}"
