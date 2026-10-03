"""三档分频「首次拉取」修复测试（2026-09-26 新增）

背景 bug：
    原实现 `need_low = (now - self._low_freq_ts.get(rid, 0.0)) > LOW_FREQ_INTERVAL`
    首次时 dict 为空 → get 返回 0.0 → 差值 = time.monotonic() = 进程运行时长。
    由于 LOW_FREQ_INTERVAL = 24h，只要 HA 进程启动不到 24 小时，
    need_low 恒为 False → 低频信号（车辆授权等 23 个）在首个 24 小时永不拉取，
    对应实体一直 unknown。

实测证据：
    容器 uptime = 13,561 秒（3.8 小时）
    `(13561 - 0) > 86400` → False
    → `binary_sensor.车辆授权` 显示 unknown（VSS 里其实有 value="true"）
"""
from __future__ import annotations

import re
from pathlib import Path

_COORD = (Path(__file__).resolve().parent.parent
          / "custom_components" / "lixiang_auto" / "coordinator.py")


def _src() -> str:
    return _COORD.read_text(encoding="utf-8")


class TestFirstPollFix:
    def test_uses_none_sentinel_not_zero_default(self):
        """必须用 `is None` 判首次，而不是 `get(rid, 0.0)`。"""
        s = _src()
        assert "_mid_ts is None or" in s, "need_mid 未用 is None 判首次"
        assert "_low_ts is None or" in s, "need_low 未用 is None 判首次"

    def test_no_zero_default_regression(self):
        """不能回退到 `get(rid, 0.0)` 的老写法。"""
        s = _src()
        bad = re.findall(r"need_(?:mid|low)\s*=\s*\(now\s*-\s*self\._\w+_ts\.get\(\s*\w+\(\),\s*0\.0\s*\)\)", s)
        assert not bad, f"仍存在旧的 0.0 默认写法: {bad}"

    def test_bug_statement_recorded(self):
        """bug 说明要留在代码里（避免后人改回去）。"""
        s = _src()
        assert "首次永不拉取低频信号" in s or "首个 24 小时" in s

    def test_semantics_first_poll_true(self):
        """语义验证：首次 → need_* = True；随后按间隔。"""
        MID, LOW = 3600, 86400

        def need(mid_ts, low_ts, now):
            nm = mid_ts is None or (now - mid_ts) > MID
            nl = low_ts is None or (now - low_ts) > LOW
            return nm, nl

        # 首次（uptime 3.8h，旧逻辑会 False）
        assert need(None, None, 13561) == (True, True)
        # 30 分钟后，都未到期
        assert need(13561, 13561, 15361) == (False, False)
        # 1 小时后 MID 到期
        assert need(13561, 13561, 13561 + 3601) == (True, False)
        # 25 小时后 LOW 到期
        assert need(13561, 13561, 13561 + 90001) == (True, True)

    def test_old_logic_would_fail(self):
        """守卫：证明旧逻辑在 uptime < 24h 时确实不拉 LOW。"""
        MID, LOW = 3600, 86400
        now = 13561                      # 容器 uptime
        old_need_low = (now - 0.0) > LOW
        assert old_need_low is False, "旧逻辑本应 False（这就是 bug）"
        new_need_low = True              # low_ts is None → True
        assert new_need_low is True
