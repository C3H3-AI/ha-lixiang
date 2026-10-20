"""SessionGuard 的离线单测 —— 不 import HA。

职责：把"账号/token 变了就拒发"钉死。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "custom_components" / "lixiang_auto" / "session_guard.py"


def _load():
    """按文件路径加载模块。

    ★ 必须同时注册进 sys.modules —— dataclass 处理
       这类注解时会查 sys.modules[cls.__module__]，
      不注册就 AttributeError。
    """
    import sys
    name = "lixiang_session_guard"
    spec = importlib.util.spec_from_file_location(name, MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sg = _load()


class TestHappyPath:
    def test_snapshot_is_current(self):
        g = sg.SessionGuard(vin="LW433B111M1027177")
        t = g.snapshot()
        ok, why = g.is_current(t)
        assert ok is True and why == ""
        g.assert_current(t)          # 不抛

    def test_initial_generations_are_zero(self):
        g = sg.SessionGuard()
        t = g.snapshot()
        assert t.account_generation == 0
        assert t.token_generation == 0


class TestTokenBump:
    def test_token_refresh_invalidates(self):
        g = sg.SessionGuard()
        t = g.snapshot()
        g.bump_token()
        ok, why = g.is_current(t)
        assert ok is False
        assert "token" in why
        with pytest.raises(sg.StaleSession):
            g.assert_current(t)

    def test_token_bump_count(self):
        g = sg.SessionGuard()
        assert g.bump_token() == 1
        assert g.bump_token() == 2
        assert g.snapshot().token_generation == 2


class TestAccountBump:
    def test_relogin_invalidates(self):
        g = sg.SessionGuard(vin="AAA")
        t = g.snapshot()
        g.bump_account()
        ok, why = g.is_current(t)
        assert ok is False
        assert "账号" in why

    def test_account_bump_also_bumps_token(self):
        """★ 换账号 ⇒ 旧 token 必然作废 ⇒ token 代际也要 +1。"""
        g = sg.SessionGuard()
        t0 = g.snapshot()
        g.bump_account()
        t1 = g.snapshot()
        assert t1.account_generation == t0.account_generation + 1
        assert t1.token_generation == t0.token_generation + 1

    def test_account_bump_can_change_vin(self):
        g = sg.SessionGuard(vin="OLD")
        g.bump_account(vin="NEW")
        assert g.snapshot().vin == "NEW"

    def test_vin_change_invalidates(self):
        """★ 单独验证 VIN 判据 —— 用 set_vin（不推账号代际）。"""
        g = sg.SessionGuard(vin="OLD")
        t = g.snapshot()
        g.set_vin("NEW")                    # 只改 VIN，不动代际
        ok, why = g.is_current(t)
        assert ok is False
        assert "VIN" in why

    def test_account_bump_reports_account_first(self):
        """★ 优先级：bump_account 同时推两个代际 ⇒ 报「账号已更换」（更根本）。"""
        g = sg.SessionGuard(vin="OLD")
        t = g.snapshot()
        g.bump_account(vin="NEW")
        ok, why = g.is_current(t)
        assert ok is False
        assert why == "账号已更换"


class TestErrorMessage:
    def test_error_carries_both_snapshots(self):
        g = sg.SessionGuard()
        t = g.snapshot()
        g.bump_token()
        try:
            g.assert_current(t)
            raise AssertionError("应当抛 StaleSession")
        except sg.StaleSession as e:
            assert e.expected is t
            assert e.current.token_generation == 1
            assert "token" in str(e)
            # 消息里必须有两边的代际号（排障要靠）
            assert "account_gen=0" in str(e)
            assert "token_gen=1" in str(e)

    def test_reason_prefers_account_over_token(self):
        """账号和 token 都变时，报更根本的那个（账号）。"""
        g = sg.SessionGuard()
        t = g.snapshot()
        g.bump_account()                     # 两个代际都 +1
        ok, why = g.is_current(t)
        assert why == "账号已更换"

    def test_is_stale_session_runtime_error(self):
        assert issubclass(sg.StaleSession, RuntimeError)


class TestRealisticScenario:
    def test_polling_window_relogin(self):
        """★ 典型危险窗口：命令已发，轮询结果期间用户重登。"""
        g = sg.SessionGuard(vin="LW433B111M1027177")
        ticket = g.snapshot()                 # 命令入口
        # ... 命令已下发，正在轮询 ...
        g.bump_account()                      # 用户在这期间重登了
        # 轮询到结果后、做下一步动作前必须校验
        with pytest.raises(sg.StaleSession):
            g.assert_current(ticket)

    def test_token_refresh_mid_command(self):
        """token 在命令执行期间被刷新 —— 同样要拒。"""
        g = sg.SessionGuard()
        ticket = g.snapshot()
        g.bump_token()
        ok, why = g.is_current(ticket)
        assert ok is False and why == "token 已刷新/重新获取"

    def test_no_bump_stays_valid(self):
        """没有任何变更 ⇒ 一直有效（不能误报）。"""
        g = sg.SessionGuard(vin="V")
        t = g.snapshot()
        for _ in range(10):
            g.assert_current(t)               # 都不抛
        assert g.is_current(t)[0] is True
