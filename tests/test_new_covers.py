"""新增 cover 实体测试（前备箱 / 左右滑门）—— 2026-09-27

来源：App 反编译 XHttp*Control.getParams()
  XHttpFrunkControl       cmdKey="fTkC",             cmdData={"lockSw":"0"/"1"}
  XHttpLSlideDoorControl  cmdKey="remoteVehPlgControl", cmdData={"lSlidingDoor":"100"/"0"}
  XHttpRSlideDoorControl  cmdKey="remoteVehPlgControl", cmdData={"rSlidingDoor":"100"/"0"}

★ 关键守卫：
  · 前备箱的 cmdKey 必须是 "fTkC"（不是 remoteVehXxx）
  · 滑门的开值必须是 "100"（不是 "1"）—— App 源码实测
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src() -> str:
    return (_INTEG / "cover.py").read_text(encoding="utf-8")


class TestFrunkCommand:
    """前备箱命令格式（App 源码）。"""

    def test_cmd_key_is_ftkc(self):
        """★ cmdKey 必须是 fTkC（前备箱专用，不是 remoteVehXxx）。"""
        s = _src()
        assert 'CMD_FRUNK = "fTkC"' in s, "前备箱 cmdKey 定义不对"

    def test_open_uses_lock_sw_0(self):
        """★ 开前备箱：lockSw = "0"（App 源码）。"""
        s = _src()
        i = s.find("async def async_open_cover")
        assert i > 0
        # 在前备箱类里找
        j = s.find("class LiCarFrunkCover")
        assert j > 0
        blk = s[j:s.find("class LiCarSlideDoorCover")]
        assert '{"lockSw": "0"}' in blk, "开前备箱参数应为 lockSw=0"

    def test_close_uses_lock_sw_1(self):
        """★ 关前备箱：lockSw = "1"。"""
        j = _src().find("class LiCarFrunkCover")
        blk = _src()[j:_src().find("class LiCarSlideDoorCover")]
        assert '{"lockSw": "1"}' in blk, "关前备箱参数应为 lockSw=1"

    def test_class_exists(self):
        assert "class LiCarFrunkCover" in _src()


class TestSlideDoorCommand:
    """滑门命令格式（App 源码）。"""

    def test_left_uses_lslidingdoor(self):
        j = _src().find("class LiCarSlideDoorCover")
        blk = _src()[j:]
        assert '"lSlidingDoor"' in blk

    def test_right_uses_rslidingdoor(self):
        j = _src().find("class LiCarSlideDoorCover")
        blk = _src()[j:]
        assert '"rSlidingDoor"' in blk

    def test_open_value_is_100(self):
        """★★ 滑门开值是 "100"（不是 "1"）—— App 源码实测。"""
        j = _src().find("class LiCarSlideDoorCover")
        blk = _src()[j:]
        i = blk.find("async def async_open_cover")
        assert i > 0
        seg = blk[i:i + 400]
        assert '"100"' in seg, "滑门开值必须是 100"
        assert '"1"' not in seg, "滑门开值不能是 1"

    def test_close_value_is_0(self):
        j = _src().find("class LiCarSlideDoorCover")
        blk = _src()[j:]
        i = blk.find("async def async_close_cover")
        assert i > 0
        seg = blk[i:i + 400]
        assert '"0"' in seg

    def test_uses_plg_cmd_key(self):
        """滑门与尾门共用 remoteVehPlgControl。"""
        j = _src().find("class LiCarSlideDoorCover")
        blk = _src()[j:]
        assert "CMD_PLG" in blk


class TestConditionalCreation:
    """按车型能力条件创建（L6 不该有滑门）。

    ★★ 2026-09-28 重要更正（用户报告「L6 没有滑门」）

    本类的两个测试【把缺陷固化成了期望】，是这个 bug 能活下来的直接原因：

        test_seat_count_gate_for_slide
            assert "seat_count" in blk or ">= 6" in blk
            → 断言"socket 按 6 座判定"，而 L8/L9 正是 6 座【但没有滑门】
              （App 里 sideDoor 只在 W01/W01B/W10B 为真）

        test_vss_fallback
            assert "door_slide_left" in blk or "SeatLDoor" in blk
            → 断言"VSS 有信号就算支持"，而 vss 的键是信号 key、
              轮询又不按车型过滤，该条件恒真 → 每辆车都建滑门

    教训：**测试写的是"当前实现"，而不是"正确行为"时，
    它就从守卫变成了共犯。** 现在改为断言行为（见
    tests/test_bugfixes_20260928.py::TestSlideDoorDetection），
    这里只保留"确实调用了判定函数"的结构性检查。
    """

    @staticmethod
    def _setup_body() -> str:
        """取 async_setup_entry 的函数体（按下一个顶层定义切，不用固定窗口）。

        ★ 原先用 s[i:i+4000] 这种固定窗口 —— 注释一长就被截断，
          于是"断言失败"其实只是窗口太小（本次就是这么暴露的）。
        """
        s = _src()
        i = s.find("async def async_setup_entry")
        assert i > 0
        rest = s[i:]
        j = len(rest)
        for marker in ("\nclass ", "\nasync def ", "\ndef "):
            k = rest.find(marker, 1)
            if k != -1:
                j = min(j, k)
        return rest[:j]

    def test_setup_checks_capability(self):
        blk = self._setup_body()
        assert "frunk_ok" in blk, "前备箱必须有能力判定"
        assert "detect_slide_door(features, hpcm)" in blk, \
            "滑门判定必须走 detect_slide_door()（而不是内联的 vss 推断）"

    def test_slide_gate_is_not_seat_count(self):
        """★ 滑门不得再按座位数判定 —— L8/L9 是 6 座但没有滑门。"""
        blk = self._setup_body()
        # 只看代码（剥掉注释），否则注释里提到 seat_count 会误判
        code = "\n".join(
            ln for ln in blk.splitlines() if not ln.lstrip().startswith("#"))
        assert "seat_count" not in code and ">= 6" not in code, (
            "滑门判定不得再用 seat_count >= 6 —— L8/L9（6座）没有滑门，"
            "App 里 sideDoor 只在 W01/W01B/W10B 为真"
        )

    def test_slide_has_no_vss_presence_fallback(self):
        """★ 滑门不得再用「信号在 vss 里」推断硬件（该条件恒真）。"""
        blk = self._setup_body()
        code = "\n".join(
            ln for ln in blk.splitlines() if not ln.lstrip().startswith("#"))
        assert "in vss" not in code, (
            "滑门/前备箱不得用 `in vss` 推断硬件 —— vss 的键是信号 key，"
            "而轮询不按车型过滤，该条件恒真（曾导致每辆车都建滑门）"
        )


class TestCoverCount:
    """实体数量与 platform 注册。"""

    def test_two_base_covers_always(self):
        """尾门 + 车窗 总是创建。"""
        s = _src()
        i = s.find("entities = [")
        blk = s[i:i + 400]
        assert "LiCarTrunkCover" in blk
        assert "LiCarWindowCover" in blk

    def test_all_cover_classes_exist(self):
        s = _src()
        for cls in ("LiCarTrunkCover", "LiCarWindowCover",
                    "LiCarFrunkCover", "LiCarSlideDoorCover"):
            assert f"class {cls}" in s, f"{cls} 缺失"


class TestSignalsAdded:
    """新增信号定义。"""

    @staticmethod
    def _signals() -> str:
        return (_INTEG / "signals.py").read_text(encoding="utf-8")

    def test_front_trunk_signal(self):
        assert '"door_front_trunk"' in self._signals()

    def test_slide_signals(self):
        s = self._signals()
        assert '"door_slide_left"' in s
        assert '"door_slide_right"' in s

    def test_semantics_valid(self):
        """★ 必须用 Semantics 枚举里存在的值（DOOR 不存在！）。"""
        s = self._signals()
        # 提取 Semantics 枚举成员
        m = re.search(r"class Semantics.*?(?=\nclass |\Z)", s, re.S)
        assert m
        members = set(re.findall(r"^\s+([A-Z_]+) = ", m.group(0), re.M))
        # 找新增信号的 semantics
        for key in ("door_front_trunk", "door_slide_left", "door_slide_right"):
            i = s.find(f'"{key}"')
            assert i > 0
            # ★ 2026-09-28：窗口从固定 600 字符改为「到该 SignalSpec 块结束」。
            #   原实现是脆弱的：给 door_front_trunk 补了一段路径修正的注释
            #   （说明为什么要改成 DoorLockStatus / 为什么走别名），
            #   注释长度一超 600 就找不到 semantics，测试误报失败。
            #   注释越长越失败 —— 这等于惩罚写清楚原因，必须修。
            end = s.find("\n    ),", i)
            blk = s[i:end if end > 0 else i + 2000]
            sm = re.search(r"semantics=Semantics\.([A-Z_]+)", blk)
            assert sm, f"{key} 无 semantics"
            assert sm.group(1) in members, \
                f"{key} 用了不存在的 Semantics.{sm.group(1)}"
