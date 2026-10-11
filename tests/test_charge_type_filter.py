"""充电记录：类型筛选 + 按月统计聚合修复（2026-10-11）。

★★ 修复的用户可见 BUG
---------------------
前端充电页的"按月统计"走的是 `get_charge_monthly_stats()`（默认
`charging_type=1` = **仅 DC 直流快充**），而服务端该接口**每个类型只返回
该类型的统计、且没有"全部"取值**。

后果：充电页月电量**只有实际的约 1/3**。用户截图对照（2026-10-11）：

| 月 | 我们显示（旧）| App 显示 | 实际 |
|---|---|---|---|
| 10月 | 6 次 / 78.65 | 13 次 / **223.32** | 只有 35% |
|  9月 | 1 次 / 12.93 | 28 次 / **529.18** | 只有 2% |

修复后按 (year, month) **求和 4 种类型**，与 App 8 个月全部吻合。

同时补上 App 有的**类型筛选**（全部/交流慢充/直流快充/理想超充）。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
LI_API = CC / "li_api.py"
INIT = CC / "__init__.py"
PAGE = CC / "www" / "lixiang-cards" / "lixiang-charge-page.js"

#: 真机实测对照（按 (year, month) 分类型的原始统计）
REAL = {
    (2026, 10): {1: (6, 78.65), 2: (5, 91.48), 3: (1, 29.43), 4: (1, 23.76)},
    (2026, 9):  {1: (1, 12.93), 2: (27, 516.25)},
    (2026, 8):  {1: (12, 151.3), 2: (27, 446.88), 3: (1, 12.82)},
    (2026, 7):  {1: (6, 120.92), 2: (27, 417.82), 3: (1, 21.48)},
    (2026, 6):  {1: (1, 21.74), 2: (28, 444.18)},
}
#: 车主 App 截图显示的「全部」合计
APP_ALL = {(2026, 10): (13, 223.32), (2026, 9): (28, 529.18),
           (2026, 8): (40, 611.0), (2026, 7): (34, 560.22),
           (2026, 6): (29, 465.92)}


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:700]
    return r.stdout


class TestAggregationFormula:
    """★ 用真机对照数据验证聚合公式（App 的「全部」= 4 类型求和）。"""

    def _aggregate(self, months: dict) -> dict:
        """复刻聚合规则：按 (year, month) 求和（不是简单 extend）。"""
        out: dict[tuple, list] = {}
        for (y, m), types in months.items():
            times = sum(v[0] for v in types.values())
            cap = round(sum(v[1] for v in types.values()), 2)
            out[(y, m)] = (times, cap)
        return out

    def test_sum_matches_app(self):
        got = self._aggregate(REAL)
        for key, want in APP_ALL.items():
            assert got[key] == want, f"{key} 聚合 {got[key]} != App {want}"

    def test_single_type_is_much_smaller(self):
        """★ 证明单类型（旧行为）远小于真实值 —— 这是那个 bug 的量化证据。"""
        only_dc = {k: v[1][1] for k, v in REAL.items()}
        assert only_dc[(2026, 10)] == 78.65
        assert only_dc[(2026, 10)] < APP_ALL[(2026, 10)][1] * 0.4, \
            "旧行为只有真实值的不到 40% —— 用户会以为数据不准"

    def test_ideal_supercharge_is_3_plus_4(self):
        """★ App 的「理想超充」= 5C(3) + 4C/5C(4)。"""
        oct_types = REAL[(2026, 10)]
        hpc = round(oct_types[3][1] + oct_types[4][1], 2)
        assert hpc == 53.19, "理想超充应为 29.43 + 23.76 = 53.19"


class TestBackendSource:
    def test_all_method_exists(self):
        s = LI_API.read_text(encoding="utf-8")
        assert "def get_charge_monthly_stats_all(" in s, "缺聚合方法"

    def test_aggregates_by_year_month_key(self):
        """★★ 核心：必须按 (year, month) 求和 —— 只按 month 会把不同年份的混在一起。"""
        s = LI_API.read_text(encoding="utf-8")
        i = s.index("def get_charge_monthly_stats_all(")
        blk = s[i:i + 3200]
        assert 'key = (x.get("year"), x.get("month"))' in blk, \
            "聚合键必须含年份（否则 2024/2026 的同月会被错误相加）"
        assert 'cur["chargingTimes"] +=' in blk and 'cur["chargingCapacity"] +=' in blk, \
            "必须是累加而非覆盖"

    def test_supports_type_subset(self):
        s = LI_API.read_text(encoding="utf-8")
        i = s.index("def get_charge_monthly_stats_all(")
        blk = s[i:i + 3200]
        assert "types" in blk and "wanted" in blk, "应支持只聚合指定类型组合"

    def test_default_path_uses_aggregate(self):
        """★★ 回归防护：默认（不传 charging_type）必须走聚合，不能回到 type=1。"""
        s = INIT.read_text(encoding="utf-8")
        i = s.index('_raw2 = str(ctype)')
        blk = s[i:i + 1200]
        assert "get_charge_monthly_stats_all)" in blk, \
            "默认分支必须调用聚合方法"
        # 默认分支里不能再出现无参的 get_charge_monthly_stats
        first_branch = blk[:blk.index("elif _raw2")]
        assert "api.get_charge_monthly_stats)" not in first_branch, \
            "默认分支又回到了「只查一种类型」"

    def test_hpc_maps_to_3_and_4(self):
        s = INIT.read_text(encoding="utf-8")
        i = s.index('_raw2 = str(ctype)')
        blk = s[i:i + 1400]
        assert '"hpc"' in blk and "(3, 4)" in blk, \
            "「理想超充」应聚合类型 3 和 4"


class TestFrontend:
    def _src(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_tabs_defined(self):
        s = self._src()
        assert "_CTYPES" in s
        for label in ("全部", "交流慢充", "直流快充", "理想超充"):
            assert label in s, f"缺筛选项 {label}"

    def test_mapping_correct(self):
        """★ 映射必须与 App 一致：全部=聚合 / 交流=2 / 直流=1 / 理想超充=hpc。"""
        s = self._src()
        i = s.index("const _CTYPES = [")
        blk = s[i:s.index("];", i)]
        assert re.search(r'value:\s*0,\s*label:\s*"全部"', blk)
        assert re.search(r'value:\s*2,\s*label:\s*"交流慢充"', blk)
        assert re.search(r'value:\s*1,\s*label:\s*"直流快充"', blk)
        assert re.search(r'value:\s*"hpc",\s*label:\s*"理想超充"', blk)

    def test_request_passes_type(self):
        """★ 切换筛选必须把 charging_type 传出去（否则 UI 变了但数据不变）。"""
        s = self._src()
        i = s.index('callService("lixiang_auto", "get_charge"')
        blk = s[i:i + 260]
        assert "charging_type" in blk and "this._ctype" in blk

    def test_switch_clears_cache_and_refetches(self):
        s = self._src()
        i = s.index("_switchCType(i) {")
        blk = s[i:i + 1200]
        assert "this._years = null" in blk, "必须清缓存，否则守卫会直接 return"
        assert "_fetchStats()" in blk, "必须重新拉取"

    def test_bind_is_called(self):
        """★ 防「定义了但没调用」（本仓库踩过：`_st()` 未定义那次）。"""
        s = self._src()
        assert s.count("_bindCTypes") >= 2, "_bindCTypes 定义了但没被调用"
        # 调用点在 _build 里（文件位置早于定义 —— 所以不能比较索引大小）
        assert "this._bindCTypes();" in s, "必须真的调用（不是只有定义）"
        i = s.index("this._bindCTypes();")
        # 调用点应落在 _build 方法体内（其后不远出现 #refresh 的绑定）
        seg = s[i:i + 400]
        assert 'querySelector("#refresh")' in seg or "appendChild(root)" in s[:i], \
            "调用应出现在 _build 的绑定流程里"

    def test_accessibility(self):
        """tab 需要 role/aria-selected + 键盘可达（本仓库的 a11y 基线）。"""
        s = self._src()
        assert 'role="tablist"' in s and 'role="tab"' in s
        assert "aria-selected" in s
        assert 'e.key === "Enter"' in s or "keydown" in s

    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(PAGE)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]


class TestTabsRender:
    """node 真跑：tabs 渲染出 4 项、首项默认选中。"""

    @pytest.mark.skipif(not _node_ok(), reason="node 不可用")
    def test_render_four_tabs(self):
        s = PAGE.read_text(encoding="utf-8")
        i = s.index("const _CTYPES = [")
        j = s.index("];", i) + 2
        code = (s[i:j] + "\n" +
                'const html = _CTYPES.map((c,i)=>`<span class="ctab${i===0?" on":""}"'
                ' data-ct="${i}">${c.label}</span>`).join("");\n'
                'console.log(html);\n')
        out = run_node(code)
        assert out.count('class="ctab') == 4, "应渲染 4 个筛选项"
        assert out.count('class="ctab on"') == 1, "只应有一个默认选中"
        for label in ("全部", "交流慢充", "直流快充", "理想超充"):
            assert label in out

class TestDetailListIncludesSupercharge:
    """★★ 同类第二个 bug：**明细**（点开某月）也只拉 AC/DC，漏 5C/4C 超充。

    原实现手写两次请求 `charging_type: 2` + `charging_type: 1` ——
    既漏超充，又不跟随筛选。App 明细显示 `5C超充 29.43 / 4C超充 23.76`。
    """

    def _src(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_no_hardcoded_type_pair(self):
        """★ 回归防护：不能再硬编码只拉 1 和 2。"""
        s = self._src()
        i = s.index("async _fetchMonth(")
        j = s.index("_renderYears()", i)
        blk = s[i:j]
        assert "charging_type: this._ctype" in blk, \
            "明细请求必须跟随当前筛选（this._ctype）"
        assert "charging_type: 2 }" not in blk and "charging_type: 1 }" not in blk, \
            "还有硬编码的单类型请求（只拉 AC/DC，漏超充）"

    def test_single_request(self):
        """一次请求即可（服务端 0/hpc 会聚合），不该再手写两次。"""
        s = self._src()
        i = s.index("async _fetchMonth(")
        j = s.index("_renderYears()", i)
        assert s[i:j].count('callService("lixiang_auto", "get_charge"') == 1, \
            "明细应一次请求（此前两次分别拉 AC/DC）"

    def test_detail_labels_four_types(self):
        """★ 标签必须区分 4 种 —— 此前只有「直流/交流」，5C/4C 被误标成交流。"""
        s = self._src()
        i = s.index("_renderList() {")
        blk = s[i:i + 1600]
        assert "ct5c" in blk and "ct4c" in blk, "明细标签缺 5C/4C 超充"
        assert "I18N.ctAc" in blk and "I18N.ctDc" in blk

    def test_i18n_has_four_names(self):
        s = self._src()
        for k in ("ctDc", "ctAc", "ct5c", "ct4c"):
            assert f'{k}:' in s, f"I18N 缺 {k}"
        assert "5C超充" in s and "4C超充" in s, "类型名应与 App 用词一致"

    def test_backend_detail_supports_subset(self):
        """★ 断言必须用**完整表达式** —— 只查 "types"/"wanted" 关键词存在，
        `wanted = None` 这种"过滤失效"的写法照样能骗过测试（本测试初版就被骗过一次）。
        """
        s = LI_API.read_text(encoding="utf-8")
        i = s.index("def get_charge_records_monthly_all(")
        blk = s[i:i + 1800]
        assert "types: tuple[int, ...] | None = None" in blk, "签名应接受 types 参数"
        assert "wanted = set(types) if types else None" in blk, \
            "必须真的把 types 转成过滤集合（写成 wanted = None 会让过滤失效）"
        assert "if wanted is not None and ct not in wanted:" in blk, \
            "必须真的用它跳过不需要的类型"

    def test_backend_dt_branch_handles_hpc(self):
        """★ 防 `int("hpc")` 崩溃：dt 分支也要识别"理想超充"。"""
        s = INIT.read_text(encoding="utf-8")
        i = s.index('_raw = str(ctype)')
        blk = s[i:i + 1600]
        assert '"hpc"' in blk, "dt 分支应识别 hpc"
        # hpc 分支必须出现在 int(ctype) 之前
        assert blk.index('"hpc"') < blk.index("ct = int(ctype)"), \
            'int("hpc") 会抛异常 —— hpc 必须在前面的分支里处理'


class TestFlatListInlineDetail:
    """★★ 结构重构（车主反馈：「点击10月，明细在下面，根本看不到」）。

    原结构：按年折叠 + 明细渲染在页面底部的 #list → 点完要滚到下方才看得见。
    现结构（照 App）：**扁平月度列表 + 点击月份内联展开**。
    """

    def _src(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_no_bottom_list_container(self):
        """★ 底部 #list 容器必须移除（明细不再渲染到那里）。"""
        s = self._src()
        assert 'id="list"' not in s, "底部明细容器还在 —— 明细会被渲染到看不见的地方"

    def test_detail_container_is_inline(self):
        """明细容器必须在月行**内部**（id=md-{年}-{月}）。"""
        s = self._src()
        assert 'class="md" id="md-${y.year}-${m.month}"' in s, "缺内联明细容器"
        # 容器应在 .month 卡片内（模板里 mh 之后）
        i = s.index('class="md" id="md-')
        seg = s[max(0, i - 1400):i]
        assert 'class="mh"' in seg, "内联容器应紧跟月份行（同属 .month 卡片）"

    def test_render_list_targets_inline(self):
        """★ 明细渲染必须定位到内联容器，不是 #list。"""
        s = self._src()
        i = s.index("_renderList() {")
        blk = s[i:i + 500]
        assert "#md-${this._selMonth.year}" in blk, "应渲染到内联容器"
        assert 'querySelector("#list")' not in blk, "又渲染回底部容器了"

    def test_year_folding_present(self):
        """★ 车主拍板：**年份折叠 + 月份内联明细**（兼顾列表短与点开即见）。"""
        s = self._src()
        i = s.index("_renderYears() {")
        blk = s[i:s.index("_renderList() {", i)]
        assert 'class="year' in blk, "应有年份折叠分组"
        assert "this._openYears" in blk, "年份展开状态应可切换"

    def test_year_shown_once_in_group_header(self):
        """★ 年份只在分组头出现一次（不再是每月标签的前缀）——
        这样列表更短，且不会重复。"""
        s = self._src()
        i = s.index("_renderYears() {")
        blk = s[i:s.index("_renderList() {", i)]
        assert '${y.year} 年' in blk, "年份应在分组头"
        assert '${y} 年 ${m.month} 月' not in blk, "月份标签不应再带年份前缀"

    def test_click_toggles_inline(self):
        """点击展开/收起（App 的箭头行为）。"""
        s = self._src()
        i = s.index("_renderYears() {")
        # ★ 用下一个方法名做终点 —— 固定窗口（3000 字符）会截断长方法，
        #   导致断言假失败/假通过（本测试初版就栽在这）
        blk = s[i:s.index("_renderList() {", i)]
        assert "classList.add(\"open\")" in blk or "classList.add('open')" in blk
        assert "classList.remove(\"open\")" in blk, "应支持收起"
        assert 'aria-expanded' in blk, "展开状态需 aria-expanded"

    def test_dead_css_removed(self):
        """旧类 CSS 应清理（避免死代码）。"""
        s = self._src()
        for cls in (".yhead {", ".ymonths {"):
            assert cls not in s, f"残留死 CSS: {cls}"

    def test_js_syntax(self):
        r = subprocess.run(["node", "--check", str(PAGE)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]
