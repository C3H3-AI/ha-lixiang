"""首页充电卡显示「剩余充电时间」（2026-10-11）。

背景
----
车主发来的 App 首页截图里，充电卡显示：

```
54%  剩余2小时25分钟
```

而我们的首页 `c-batt` **只显示电量百分比**。数据其实早就有
（`charge_remain_time` → VSS `Vehicle.Powertrain.Battery.ChargeSurplusTime`，
单位 min），只是没展示。

做法
----
- `auto-bind.js` 加 `remain_time` 规则（按中文名「剩余充电时间」匹配）
- 首页 `c-batt` 加一行（默认隐藏），充电中才显示
- 判据：值 > 0 → 充电中（无需额外依赖充电状态实体）；否则整行隐藏不留空位
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
HOME = CARDS / "lixiang-app-home.js"
BIND = CARDS / "lixiang-auto-bind.js"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (r.stderr or "")[:600]
    return r.stdout


class TestAutoBindRule:
    def test_remain_time_rule_exists(self):
        s = BIND.read_text(encoding="utf-8")
        assert "remain_time:" in s, "自动绑定缺 remain_time 规则"
        assert "剩余充电时间" in s, "应按实体中文名匹配"

    def test_rule_is_array_of_keywords(self):
        s = BIND.read_text(encoding="utf-8")
        m = re.search(r'remain_time:\s*\[([^\]]*)\]', s)
        assert m, "规则应是关键字数组"
        kws = [k.strip().strip('"') for k in m.group(1).split(",") if k.strip()]
        assert "剩余充电时间" in kws


class TestHomeMarkup:
    def _src(self) -> str:
        return HOME.read_text(encoding="utf-8")

    def test_remain_row_present_and_hidden_by_default(self):
        s = self._src()
        assert 'id="batt-remain"' in s, "缺剩余时间行"
        assert 'id="v-remain"' in s, "缺数值占位"
        # 默认隐藏（非充电态不该占位）
        i = s.index('id="batt-remain"')
        assert "display:none" in s[max(0, i - 80):i + 80], "默认应隐藏"

    def test_inside_battery_card(self):
        """★ 必须落在 c-batt 卡片内（App 就是放在充电卡里）。"""
        s = self._src()
        i_batt = s.index('id="c-batt"')
        i_rm = s.index('id="batt-remain"')
        assert i_rm > i_batt, "剩余时间行应在 c-batt 之后"
        # 且不应超出该卡片的闭合（下一个 card 之前）
        i_next = s.find('<div class="card', i_batt + 10)
        assert i_next == -1 or i_rm < i_next, "不应跑到下一张卡片里"

    def test_uses_remain_time_entity(self):
        s = self._src()
        assert '_eid("remain_time")' in s, "应绑定 remain_time 实体"


class TestDisplayLogic:
    def _blk(self) -> str:
        s = HOME.read_text(encoding="utf-8")
        i = s.index("const rmEl = q(\"#batt-remain\")")
        j = s.index("}", s.index("rmEl.style.display = \"none\"", i)) + 1
        return s[i:j]

    def test_hides_when_zero_or_missing(self):
        blk = self._blk()
        assert "rmMin > 0" in blk, "应以 > 0 作为「充电中」判据"
        assert 'rmEl.style.display = "none"' in blk, "否则必须隐藏"

    def test_formats_hours_and_minutes(self):
        """145 分钟 → 「2小时25分钟」（App 的写法）。"""
        # 等价执行源码里的算式（源码是多行拼接，这里直接跑同一套公式）
        out = run_node("""
const rmMin = 145;
const _h = Math.floor(rmMin / 60), _m = Math.round(rmMin % 60);
console.log((_h ? _h + "小时" : "") + (_m ? _m + "分钟" : (_h ? "整" : "—")));
""")
        assert out.strip() == "2小时25分钟"

    def test_exact_hour(self):
        out = run_node("""
const rmMin = 60;
const _h = Math.floor(rmMin / 60), _m = Math.round(rmMin % 60);
console.log((_h ? _h + "小时" : "") + (_m ? _m + "分钟" : (_h ? "整" : "—")));
""")
        assert out.strip() == "1小时整", "整点不应显示「0分钟」"

    def test_under_one_hour(self):
        out = run_node("""
const rmMin = 25;
const _h = Math.floor(rmMin / 60), _m = Math.round(rmMin % 60);
console.log((_h ? _h + "小时" : "") + (_m ? _m + "分钟" : (_h ? "整" : "—")));
""")
        assert out.strip() == "25分钟", "不足一小时不该显示「0小时」"

    def test_matches_source_formula(self):
        """★ 防源码与测试各写一套：断言源码里确实是这个算式。"""
        s = HOME.read_text(encoding="utf-8")
        assert "Math.floor(rmMin / 60)" in s
        assert "Math.round(rmMin % 60)" in s
        assert '_h ? "整" : "—"' in s, "整点/异常值的兜底"


class TestGuards:
    def test_js_syntax_home(self):
        r = subprocess.run(["node", "--check", str(HOME)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]

    def test_js_syntax_bind(self):
        r = subprocess.run(["node", "--check", str(BIND)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]

    def test_no_fake_stop_button(self):
        """★ 「停止充电」走 LiNdn，HTTP 不可达 —— 不应放一个点了必失败的按钮。"""
        s = HOME.read_text(encoding="utf-8")
        assert "停止充电" not in s, \
            "不该加「停止充电」按钮（充电命令走 JOB/LiNdn，HTTP 不可达）"