"""真实快照一致性测试 —— 充电状态显示（task-19）

背景（docs/充电数据显示错误_20260928.md）
----------------------------------------
用户实测报告「车没在充电，数据错误」。抓取到的**同一时刻**真实 VSS 值：

    Vehicle.Powertrain.Battery.ChargeStatus        = 15     → 应显示「未充电」
    Vehicle.Powertrain.Battery.ACChgrActualConnSts = 0      → 充电枪未插入
    Vehicle.Powertrain.Battery.DCChrgngGunActuSts  = 0      → 充电枪未插入
    Vehicle.Powertrain.Battery.ACChargeVoltage     = 231.6  （见文末说明）
    Vehicle.Powertrain.Battery.ACChargeCurrent     = 0

**当时的实际显示是「—」**，因为 rendering.py 里复刻 App 的分支对
`chargeStatus=15`（App 未定义）直接 `return "—"`，把 translations.py 的
映射表完全遮住了。

这个文件的价值：**它是「真实数据一致性测试」，不是「函数单测」**。
旧测试只验证"给定输入输出什么"，所以用户一眼能看出的错误，测试抓不到。
这里用真实快照做夹具，断言用户最终看到的文案。

★ 防回归边界（本文件最重要的部分）
---------------------------------
修复只允许改【未匹配时的兜底】。下面两组必须同时成立：

  · 映射表里的值（15 等）→ 中文文案        ← 本次修复的收益
  · App 已定义的 8 个状态  → 行为一字不变   ← 不许改坏
  · 两边都没有的码        → 仍是 "—"       ← 不许瞎猜/不许漏出裸数字
"""

from __future__ import annotations

import pytest

from rendering import render_value


def _snapshot(**vss):
    """构造 coordinator.data（含 vss 子树），模拟真实轮询结果。"""
    return {"vss": {k: {"value": v} for k, v in vss.items()}}


# ── 用户报告那一刻的完整真实快照 ──────────────────────────────────────────
# 值全部来自 docs/充电数据显示错误_20260928.md 第一节的实测表格
REAL_SNAPSHOT_IDLE = dict(
    charge_status=15,        # 未充电
    charge_gun_ac=0,         # 枪未插
    charge_gun_dc=0,         # 枪未插
    charge_complete=0,
    charge_fault=0,
    scheduled_charge_switch=0,
    scheduled_charge_state=0,
)


class TestRealSnapshotIdle:
    """车没在充电（用户报告的现场）—— 这是本次修复要守住的核心场景。"""

    def test_charge_status_shows_not_charging(self):
        """★ 核心断言：raw=15 → 「未充电」，绝不能是「—」。

        这条就是用户报的那句「车没在充电，数据错误」。
        """
        d = _snapshot(**REAL_SNAPSHOT_IDLE)
        assert render_value("charge_status", 15, {"value": 15}, d) == "未充电"

    def test_not_dash(self):
        """把"不是 —"单独断言一次：修复前就是死在这里。"""
        d = _snapshot(**REAL_SNAPSHOT_IDLE)
        assert render_value("charge_status", 15, {"value": 15}, d) != "—"

    def test_gun_conn_sts_semantics(self):
        """枪未插：ACChgrActualConnSts=0 → 「充电枪未插入」。"""
        d = _snapshot(**REAL_SNAPSHOT_IDLE)
        assert render_value("charge_gun_ac", 0, {"value": 0}, d) == "充电枪未插入"

    def test_snapshot_is_self_consistent(self):
        """快照自洽性：枪未插 + 未充电 + 无故障，不应出现"充电中/充电告警"。"""
        d = _snapshot(**REAL_SNAPSHOT_IDLE)
        got = render_value("charge_status", 15, {"value": 15}, d)
        assert got not in ("充电中", "充电告警", "充电完成")
        assert got == "未充电"


class TestAppDefinedStatesRegression:
    """★ 回归保护：复刻 App XChargeDataHandle.getChargeState() 的 8 个状态。

    修复只碰"兜底"，这些分支的行为必须一字不变。
    任何一条挂了 = 修复改坏了 App 复刻逻辑。
    """

    @pytest.mark.parametrize("cs,expected", [
        (3, "充电中"),      # CHARGING=50
        (2, "电池加热"),    # BATTERY_HEAT=40
        (4, "电池保温"),    # BATTERY_INSULATION=80
        (7, "充电告警"),    # CHARGE_ALARM=111
    ])
    def test_single_condition_states(self, cs, expected):
        d = _snapshot(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == expected

    def test_complete(self):
        """chargeStatus==5 && chrgComplete==1 → 已完成"""
        d = _snapshot(charge_status=5, charge_complete=1)
        assert render_value("charge_status", 5, {"value": 5}, d) == "充电完成"

    def test_stopped(self):
        """chargeStatus==5 && !complete && !eveFlt → 已停止"""
        d = _snapshot(charge_status=5, charge_complete=0, charge_fault=0)
        assert render_value("charge_status", 5, {"value": 5}, d) == "已停止"

    def test_alarm(self):
        """chargeStatus==5 && !complete && eveFlt==1 → 告警"""
        d = _snapshot(charge_status=5, charge_complete=0, charge_fault=1)
        assert render_value("charge_status", 5, {"value": 5}, d) == "充电告警"

    def test_appointed(self):
        """预约充电三条件：开关==1 && AC枪==2 && state==1"""
        d = _snapshot(scheduled_charge_switch=1, charge_gun_ac=2,
                      scheduled_charge_state=1, charge_status=0)
        assert render_value("charge_status", 0, {"value": 0}, d) == "预约充电"

    def test_appointed_takes_priority(self):
        """★ 预约判定在 chargeStatus 分支【之前】—— 优先级不能被修复打乱。

        即使 chargeStatus=3（本会返回"充电中"），三条件满足时仍是"预约充电"。
        """
        d = _snapshot(scheduled_charge_switch=1, charge_gun_ac=2,
                      scheduled_charge_state=1, charge_status=3)
        assert render_value("charge_status", 3, {"value": 3}, d) == "预约充电"


class TestFallbackBoundary:
    """兜底边界：映射表命中用文案；两边都没有的码仍 "—"。"""

    @pytest.mark.parametrize("cs,expected", [
        (0, "未充电"),
        (10, "已插枪"),
        (15, "未充电"),
        (70, "充电中"),
        (130, "充电完成"),
    ])
    def test_mapped_codes(self, cs, expected):
        d = _snapshot(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == expected

    @pytest.mark.parametrize("cs", [1, 9, 42, 99, 255])
    def test_unmapped_codes_stay_dash(self, cs):
        """没证据的码不许猜，也不许把裸数字 1/42 当文案透出去。"""
        d = _snapshot(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == "—"

    def test_none_is_none(self):
        assert render_value("charge_status", None, None, _snapshot()) is None


# ───────────────────────────────────────────────────────────────────────────
# ⚠️ 缺陷 2（ACChargeVoltage=231.6）—— 故意【不】加断言
# ───────────────────────────────────────────────────────────────────────────
#
# 实测：车未插枪（ACChgrActualConnSts=0）时，ACChargeVoltage 仍返回 231.6，
# 且 ACChargeCurrent=0。这不像实时读数，但**语义未能确认**：
#   ① 电网参考电压（未插枪时报市电额定值）  → 保留 231.6 是对的
#   ② 服务器残留/上次充电缓存              → 未插枪时应 unknown
#   ③ 信号含义被误解                        → 需重新映射
#
# 三种解释会导致**互相矛盾**的正确行为，没有证据就选任何一种都是猜。
# 因此本次【不改代码】，按 task-19 要求只在文档记录。
# 一旦拿到 App 同刻显示/协议文档，在此补断言即可。
