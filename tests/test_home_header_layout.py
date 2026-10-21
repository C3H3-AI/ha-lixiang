"""首页「抬头固定」与「卡片布局」的守卫（2026-10-12）。

车主反馈两件事：

1. **「标题抬头固定做的不是很好」**
   → 根因：两条规则**打架**且优先级更低的那个才是我想要的效果：

     ```css
     .root.stuck .head .mini { display:none; }   /* 粘顶隐藏小图 (0,3,0) */
     .root.collapsed3d .mini { display:flex; }   /* 收起显示小图 (0,2,0) */
     ```

     结果是**一滚动小图就消失** —— 而「上滑小图」正是车主确认过的行为
     （「先大图。上滑小图」）。已删除前者。

2. **「首页卡片大小布局还需优化」**
   → 从车主 App 截图量得比例（逻辑像素）：

     | 卡片 | App |
     |---|---|
     | 温度卡 / 位置卡 | 宽≈180 × 高≈183（**近正方形**）|
     | 里程卡 | 高≈213 |

     而此前写死 `min-height:150px` → 卡片比 App 矮约 20%，视觉上偏扁。
     已改为 `clamp(...)` 随视口缩放。

★★ 附带：本文件还守住一个**踩过两次**的坑 ——
   卡片 CSS 写在 **JS 模板字符串**里（``const STYLE = `...` ``），
   所以在 CSS 注释里写**反引号**会把字符串提前终止：

   - 第一次：注释里写 `` `1fr` `` → 整个文件语法错误
   - 第二次：注释里写 `` `.mini { … }` `` → 再次语法错误

   直接后果是**集成的前端全挂**（所有卡片加载失败）。本文件做**全仓库扫描**。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
HOME = CARDS / "lixiang-app-home.js"


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


def _style_segments(src: str) -> list[str]:
    """取出 **CSS 常量** 模板字符串的内容。

    ★ 只认名字含 `STYLE`/`CSS` 的常量 —— 其它模板字符串里出现嵌套反引号是**合法**的
      （例如 ``const url = `https://a` + `?x=1` `` 或 `` `${sub ? `<b>` : ""}` ``）。
      初版把所有模板字符串都当 CSS 检查 → 对这两个文件误报。
    """
    out = []
    for m in re.finditer(
            r'(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*`', src):
        name = m.group(1)
        if not re.search(r'STYLE|CSS', name, re.I):
            continue
        i = m.end() - 1
        j = src.find("`;", i + 1)
        if j != -1:
            out.append(src[i + 1:j])
    return out


class TestNoBacktickInStyle:
    """★ 踩过两次的坑：CSS 注释里写反引号 → 模板字符串提前终止 → 前端全挂。"""

    def test_home_clean(self):
        for seg in _style_segments(_src()):
            assert "`" not in seg, "STYLE 段内出现反引号（会终止模板字符串）"

    @pytest.mark.parametrize("f", sorted(p.name for p in CARDS.glob("*.js")))
    def test_every_card_clean(self, f):
        src = (CARDS / f).read_text(encoding="utf-8")
        for seg in _style_segments(src):
            assert "`" not in seg, f"{f}: STYLE 段内有反引号"

    def test_detector_catches_the_bug(self):
        """自检：证明这个检测真能发现问题（否则只是装饰）。"""
        fake = "const STYLE = `\n  /* 注释里写了 `反引号` */\n  .a{}\n`;"
        segs = _style_segments(fake)
        assert segs and "`" in segs[0], "检测器抓不到问题"


class TestHeaderSticky:
    def _css_only(self) -> str:
        """去掉 JS 注释后再断言 —— 否则会命中说明文字（本会话已多次被骗）。"""
        s = _src()
        return re.sub(r'/\*.*?\*/', '', s, flags=re.S)

    def test_mini_not_hidden_when_stuck(self):
        """★★ 核心回归：粘顶时**不得**隐藏小图（否则「上滑小图」失效）。"""
        css = self._css_only()
        # 只认真正的规则（选择器后跟 {），注释里的提及不算
        assert not re.search(r'\.root\.stuck\s+\.head\s+\.mini\s*\{', css), \
            "又出现了「粘顶隐藏小图」的规则 —— 它优先级更高，会压过 .collapsed3d .mini"
        assert not re.search(r'\.root\.stuck[^{}]*\.mini[^{}]*\{', css), \
            "粘顶态不得再对 .mini 做任何隐藏"

    def test_mini_shown_when_collapsed(self):
        s = _src()
        assert re.search(r'\.root\.collapsed3d\s+\.mini\s*\{[^}]*display\s*:\s*flex',
                         s), "收起态必须显示小图"

    def test_head_is_sticky(self):
        s = _src()
        i = s.index(".head {")
        assert "position:sticky" in s[i:i + 200], "抬头不是 sticky"
        assert "--lx-head-top" in s[i:i + 260], "缺避让 HA 顶栏的偏移变量"

    def test_stuck_tightens_header(self):
        """粘顶后要收紧（标题字号变小、间距归零）——否则固定头部占掉半屏。"""
        s = _src()
        assert ".root.stuck .head .title" in s, "粘顶时标题未收紧"
        assert re.search(r'\.root\.stuck \.head \.title\s*\{[^}]*font-size\s*:\s*18px', s), \
            "粘顶标题字号应为 18px"


class TestCardLayout:
    """卡片高度对齐 App 截图比例。"""

    def _min_height(self, sel: str) -> str:
        s = _src()
        i = s.index(sel + " {")
        blk = s[i:s.index("}", i)]
        m = re.search(r'min-height\s*:\s*([^;]+);', blk)
        assert m, f"{sel} 没有 min-height"
        return m.group(1).strip()

    def test_cards_no_longer_hardcoded_150(self):
        """★ 以前写死 150px（比 App 矮约 20%）—— 必须改成随视口缩放。

        ★ 2026-10-21 变更：`.mile` 不再自带 min-height。
           原因：车主反馈「里程卡太高、电量卡应该跟哨兵一样大」。
           实测（420 宽）右列 = 电量 259 + gap 12 + 哨兵 108 = 379，
           而 .mile 作为 grid 项目被 align-items:stretch 拉到 379 ——
           **里程卡的高度是被右列撑出来的，不是自己的 min-height**。
           现改为右列 `.row2-stack` 两行等高，里程卡高度由右列总高
           自然决定（真浏览器实测 245px > 上排 225px，视觉意图不变）。
        """
        for sel in (".ac", ".loc"):
            mh = self._min_height(sel)
            assert "clamp(" in mh, f"{sel} 仍是固定高度 {mh}"
            assert "150px" != mh, f"{sel} 又回到 150px"
        # .mile 不得再写死固定高度（允许没有 min-height）
        s = _src()
        i = s.index(".mile {")
        blk = s[i:s.index("}", i)]
        assert "150px" not in blk, "里程卡又回到写死 150px"

    def test_row2_stack_is_two_equal_rows(self):
        """★ 右列「电量 + 哨兵」必须等高（车主明确要求）。

        电量与哨兵在同一列堆叠；.row2-stack 带 .row2 类是为复用拖拽能力，
        但 .row2 的 grid-template-columns:repeat(2,1fr) 会把它变成两列并排
        —— 必须显式覆盖回单列两行，否则会出现「挤成一行、文字竖排被裁」。
        """
        s = _src()
        assert ".row2.row2-stack" in s, "缺右列布局规则"
        assert re.search(
            r'\.row2\.row2-stack\s*\{[^}]*grid-template-columns\s*:\s*minmax\(0,\s*1fr\)',
            s), "右列必须覆盖成单列（否则 .row2 会把它变成两列并排）"
        assert re.search(
            r'\.row2\.row2-stack\s*\{[^}]*grid-template-rows\s*:\s*repeat\(2',
            s), "右列必须是两行等高（电量与哨兵一样大）"

    def test_ac_and_loc_equal(self):
        """上排两张卡必须等高（App 里就是等高的近正方形）。"""
        assert self._min_height(".ac") == self._min_height(".loc")

    def test_mile_taller_than_top_row(self):
        """里程卡比上排高（App ≈213 vs ≈183）——右列是「电量+哨兵」堆叠。

        ★ 2026-10-21：改为断言「右列两行等高」这一新机制（见上）。
          .mile 已无 clamp，故不再比较 clamp 下限。
        """
        s = _src()
        assert "grid-template-rows:repeat(2" in s.replace(" ", ""), \
            "右列应为两行等高 —— 里程卡随之自然高于上排（实测 245 vs 225）"

    def test_clamp_is_bounded(self):
        """clamp 必须三参齐全（否则窄屏/宽屏行为失控）。

        ★ 2026-10-21：.mile 已不再用 clamp（高度由右列等高决定），故只查上排两卡。
        """
        for sel in (".ac", ".loc"):
            mh = self._min_height(sel)
            assert len(mh.split(",")) == 3, f"{sel} 的 clamp 参数不全: {mh}"

    def test_wrap_gap_kept(self):
        s = _src()
        assert re.search(r'\.wrap\s*\{[^}]*gap', s), "缺卡片间距"
        assert re.search(r'\.row2\s*\{[^}]*gap', s), "row2 缺间距"


class TestSyntax:
    def test_js_syntax(self):
        import subprocess
        r = subprocess.run(["node", "--check", str(HOME)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]