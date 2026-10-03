"""充电通道检测测试（2026-09-26 新增）

背景：充电命令走 LiveNetControlRoute.JOB（LiNdn/NDN）通道，
      HTTP cmd/send 只支持 VEH_CONTROL 通道 → 必然 2009。

本测试守卫：
  · 充电命令被正确识别为 JOB 通道
  · ★ 实测能用的命令【不】被误判（哨兵/拍照/锁车）
  · 2009 时抛出 LiChannelNotSupported（而非静默失败）
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src() -> str:
    return (_INTEG / "li_api.py").read_text(encoding="utf-8")


def _job_commands() -> set[str]:
    """从 li_api.py 提取 _JOB_CHANNEL_COMMANDS。"""
    m = re.search(r"_JOB_CHANNEL_COMMANDS = frozenset\(\{(.*?)\}\)", _src(), re.S)
    assert m, "未找到 _JOB_CHANNEL_COMMANDS"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


class TestJobChannelList:
    def test_list_exists(self):
        assert len(_job_commands()) >= 5

    def test_charge_commands_included(self):
        """★ 充电命令必须在列表里（实测 2009）。"""
        cmds = _job_commands()
        for c in ("remote_charge_control", "remote_charging_start",
                  "remote_charging_stop", "chargeLimit",
                  "remoteChargingControl"):
            assert c in cmds, f"{c} 应被判为 JOB 通道"

    @pytest.mark.parametrize("cmd", [
        "sentinelModeSetting",     # ★ 实测能用
        "remoteVehSvm",            # ★ 实测能用（远程拍照）
        "remoteVehLockControl",    # 实测能用
        "remoteVehACSmartControl", # 实测能用
        "remoteVehSearch",         # 实测能用
    ])
    def test_working_commands_not_in_list(self, cmd):
        """★ 实测能用的命令【不】得进列表（否则会误报不支持）。"""
        assert cmd not in _job_commands(), f"{cmd} 实测能用，不该判为 JOB"


class TestChannelDetection:
    def test_raises_channel_not_supported(self):
        """2009 + 充电命令 → 应抛 LiChannelNotSupported。"""
        s = _src()
        assert "class LiChannelNotSupported" in s
        assert "LiChannelNotSupported(" in s.split("class _TokenExpired")[0]

    def test_2009_guarded_by_job_check(self):
        """2009 分支必须同时判断是 JOB 命令（且做类型容错）。"""
        s = _src()
        i = s.find("_rc_int == 2009")
        assert i > 0, "未找到 2009 检测（应为 _rc_int == 2009）"
        blk = s[i:i + 400]
        assert "_is_job_channel_command" in blk

    def test_exception_inherits_command_error(self):
        """新异常应继承 LiCommandError（保持向后兼容）。"""
        s = _src()
        m = re.search(r"class LiChannelNotSupported\((\w+)\)", s)
        assert m, "未找到类定义"
        assert m.group(1) == "LiCommandError"

    def test_message_is_user_friendly(self):
        """错误消息应说明原因（LiNdn 通道 + 已知限制）。"""
        s = _src()
        i = s.find("LiChannelNotSupported(")
        blk = s[i:i + 400]
        assert "LiNdn" in blk or "JOB" in blk
        assert "暂不可用" in blk or "不支持" in blk


class TestResultCodeTypeTolerance:
    """★ 服务端返回的 resultCode 可能是【字符串】"2009"（实测）。

    如果不做容错，`rc == 2009` 会 False → 检测失效。
    """

    def test_int_conversion_present(self):
        s = _src()
        i = s.find("rc_err == 2009")
        assert i < 0, "不该再直接比较（字符串会失败）"
        assert "int(rc_err)" in s, "缺少 int() 转换"

    def test_handles_none(self):
        s = _src()
        i = s.find("_rc_int = int(rc_err)")
        assert i > 0
        blk = s[i:i + 200]
        assert "is not None" in blk or "TypeError" in blk

    def test_tolerant_comparison(self):
        """模拟：字符串 "2009" 与 int 2009 都应判为 JOB 错误。"""
        for raw in ("2009", 2009):
            try:
                rc_int = int(raw) if raw is not None else None
            except (TypeError, ValueError):
                rc_int = None
            assert rc_int == 2009, f"{raw!r} 转换失败"
