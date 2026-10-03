"""policy.py 测试：异常层次 + 重试策略

★ 覆盖架构方案阶段 2.6 的核心行为：
  · TokenExpired 结构化（不再靠字符串匹配）
  · run_with_retry 的重试次数/回调顺序
  · 非 401 异常不被吞
"""

from __future__ import annotations

import pytest

from policy import (
    POLICY_LOGIN,
    POLICY_VSS,
    ApiError,
    AuthError,
    CommandError,
    ResultPolicy,
    TokenExpired,
    is_token_expired,
    run_with_retry,
)


# ───────────────────────────────────────────────────────────────────────────
# 1. 异常层次
# ───────────────────────────────────────────────────────────────────────────
class TestExceptions:
    def test_token_expired_has_status_401(self):
        e = TokenExpired("HTTP 401 Unauthorized")
        assert e.status == 401
        assert isinstance(e, ApiError)

    def test_command_error_is_api_error(self):
        assert issubclass(CommandError, ApiError)

    def test_auth_error_is_api_error(self):
        assert issubclass(AuthError, ApiError)

    def test_all_exceptions_carry_context(self):
        e = ApiError("boom", status=500, path="/x", request_id="r1")
        assert (e.status, e.path, e.request_id) == (500, "/x", "r1")


# ───────────────────────────────────────────────────────────────────────────
# 2. is_token_expired（兼容层）
# ───────────────────────────────────────────────────────────────────────────
class TestIsTokenExpired:
    def test_structured_token_expired(self):
        assert is_token_expired(TokenExpired()) is True

    def test_api_error_with_401_status(self):
        assert is_token_expired(ApiError("x", status=401)) is True

    def test_legacy_string_match(self):
        """旧代码把 401 塞在消息里 —— 兼容层要能识别"""
        e = ApiError("POST /x: HTTP 401 Unauthorized")
        assert is_token_expired(e) is True

    def test_other_errors_not_matched(self):
        assert is_token_expired(ApiError("HTTP 500")) is False
        assert is_token_expired(ValueError("401")) is False

    def test_bare_401_without_unauthorized(self):
        """只有 '401' 但没有 'Unauthorized' → 不算（避免误判）"""
        assert is_token_expired(ApiError("grep 4010 lines")) is False


# ───────────────────────────────────────────────────────────────────────────
# 3. run_with_retry
# ───────────────────────────────────────────────────────────────────────────
class TestRunWithRetry:
    def test_success_first_try(self):
        calls = []

        def call():
            calls.append(1)
            return "ok"

        assert run_with_retry(call, policy=POLICY_VSS) == "ok"
        assert len(calls) == 1

    def test_retry_once_on_token_expired(self):
        """第一次 401，第二次成功"""
        calls = []
        cleared = []

        def call():
            calls.append(1)
            if len(calls) == 1:
                raise TokenExpired("401")
            return "ok"

        r = run_with_retry(call, on_token_expired=lambda: cleared.append(1),
                           policy=POLICY_VSS)
        assert r == "ok"
        assert len(calls) == 2
        assert len(cleared) == 1

    def test_raises_after_retries_exhausted(self):
        """持续 401 → 重试用尽后抛出"""
        calls = []

        def call():
            calls.append(1)
            raise TokenExpired("401")

        with pytest.raises(TokenExpired):
            run_with_retry(call, on_token_expired=lambda: None, policy=POLICY_VSS)
        assert len(calls) == 2          # 首次 + 1 次重试

    def test_no_retry_policy(self):
        """POLICY_LOGIN 不重试"""
        calls = []

        def call():
            calls.append(1)
            raise TokenExpired("401")

        with pytest.raises(TokenExpired):
            run_with_retry(call, policy=POLICY_LOGIN)
        assert len(calls) == 1

    def test_non_401_error_propagates(self):
        """★ 非 401 异常必须透传，不能吞"""
        def call():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            run_with_retry(call, policy=POLICY_VSS)

    def test_before_retry_called(self):
        """before_retry 在重试前调用（用于重算 expireAt）"""
        seq = []

        def call():
            seq.append("call")
            if len(seq) == 1:
                raise TokenExpired("401")
            return "ok"

        run_with_retry(
            call,
            on_token_expired=lambda: seq.append("clear"),
            before_retry=lambda: seq.append("before"),
            policy=POLICY_VSS,
        )
        assert seq == ["call", "clear", "before", "call"]

    def test_custom_max_retries(self):
        calls = []

        def call():
            calls.append(1)
            raise TokenExpired("401")

        p = ResultPolicy(name="t", max_retries=3)
        with pytest.raises(TokenExpired):
            run_with_retry(call, on_token_expired=lambda: None, policy=p)
        assert len(calls) == 4          # 首次 + 3 次重试


# ───────────────────────────────────────────────────────────────────────────
# 4. 策略预置
# ───────────────────────────────────────────────────────────────────────────
class TestPolicies:
    def test_vss_retries_once(self):
        assert POLICY_VSS.retry_on_token_expired is True
        assert POLICY_VSS.max_retries == 1

    def test_login_never_retries(self):
        assert POLICY_LOGIN.retry_on_token_expired is False
        assert POLICY_LOGIN.max_retries == 0
