"""前备箱方向 —— 回归测试（2026-10-14）。

背景
----
车主 **实车** 反馈：「前备箱的开和关好像又反了」→ 追问后确认：
**状态与操作方向两者都反了**。

集成原实现（自 v1.3.0 起）：
  · 命令：打开 → `fTkC {"lockSw":"1"}`；关闭 → `{"lockSw":"0"}`
    （依据反编译命令表 `LXVehicleControlTypeOpenFrontTrunk` = lockSw:"1"）
  · 状态：`DoorLockStatus.FrontTrunkDoor` 值 =1 判为「开」

实车结论（本文件钉住的方向）：
  · 命令：打开 → `{"lockSw":"0"}`；关闭 → `{"lockSw":"1"}`
  · 状态：1 = 上锁/关，0 = 解锁/开

⚠️ 反编译表与实车不一致时**以实车为准** —— 该差异已登记在
   `tests/test_command_table_consistency.py::_ACCEPTED_DIFFERENCES["fTkC","lockSw"]`，
   官方配置快照保持原样（provenance），不因本次修正而改写。

这个文件存在的原因：该方向历史上被翻过至少一次（2026-09-30 也"修过一次"），
光靠注释挡不住下一次改回去。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVER = ROOT / "custom_components" / "lixiang_auto" / "cover.py"


def _frunk_src() -> str:
    """只取 LiCarFrunkCover **类体**（到下一个顶层 class 为止）。

    ⚠️ 不能直接切到文件末尾：下一个类是本项目里同样用 `v != 1` 的**滑门**，
       会把它的正确写法误判成本测试要防的旧代码（第一次写就踩了）。
    """
    s = COVER.read_text(encoding="utf-8")
    i = s.find("class LiCarFrunkCover")
    assert i > 0, "未找到 LiCarFrunkCover"
    m = re.search(r"\nclass \w+\(", s[i + 10:])
    return s[i:i + 10 + m.start()] if m else s[i:]


def _sent_payload(method: str) -> str:
    seg = _frunk_src()
    j = seg.find(method)
    assert j > 0, f"未找到 {method}"
    m = re.search(r'_send\(\s*(\{[^}]*\})', seg[j:j + 500])
    assert m, f"{method} 里没有 _send({{...}})"
    return m.group(1)


class TestFrunkCommandDirection:
    def test_open_sends_lockSw_0(self):
        assert '"lockSw": "0"' in _sent_payload("async_open_cover"), (
            "打开前备箱必须发 lockSw=0（2026-10-14 车主实车实测；发 1 会变成关闭）")

    def test_close_sends_lockSw_1(self):
        assert '"lockSw": "1"' in _sent_payload("async_close_cover"), (
            "关闭前备箱必须发 lockSw=1（2026-10-14 车主实车实测）")

    def test_optimistic_direction_matches(self):
        """乐观状态方向必须与命令一致（open → closed=False）。"""
        seg = _frunk_src()
        j = seg.find("async_open_cover")
        assert "closed=False" in seg[j:j + 500], "打开命令的乐观状态应为「未关闭」"
        j2 = seg.find("async_close_cover")
        assert "closed=True" in seg[j2:j2 + 500], "关闭命令的乐观状态应为「已关闭」"


class TestFrunkStatePolarity:
    def test_one_means_closed(self):
        seg = _frunk_src()
        j = seg.find("def is_closed")
        assert j > 0, "未找到 is_closed"
        body = seg[j:j + 900]
        assert "elif v == 1:" in body and "vss_closed = True" in body, (
            "原始值 1 必须判为「关闭/上锁」（2026-10-14 车主实车实测）")
        assert "elif v == 0:" in body and "vss_closed = False" in body, (
            "原始值 0 必须判为「打开/解锁」")

    def test_unknown_values_are_not_guessed(self):
        seg = _frunk_src()
        j = seg.find("def is_closed")
        body = seg[j:j + 900]
        assert "vss_closed = None" in body, "非 0/1 的取值应判为未知，不得乱猜"

    def test_no_legacy_inverted_expression(self):
        """旧写法 `v != 1` 必须彻底消失（它就是"反了"的根源）。"""
        assert "v != 1" not in _frunk_src(), "仍残留旧的反向判定 v != 1"


class TestDiagnosticsExposed:
    def test_raw_value_exposed(self):
        """实体属性要暴露原始值，方便车主一眼判断方向。"""
        seg = _frunk_src()
        assert "原始锁定值" in seg, "缺少原始值诊断属性"

    def test_direction_recorded_in_attributes(self):
        seg = _frunk_src()
        assert '打开=lockSw:0' in seg, "属性里应写明当前命令方向（便于排查）"


class TestRecordedDifference:
    def test_difference_registered(self):
        t = (ROOT / "tests" / "test_command_table_consistency.py").read_text(encoding="utf-8")
        assert '("fTkC", "lockSw")' in t, (
            "与官方配置表的差异必须登记在 _ACCEPTED_DIFFERENCES，写明实车依据")
