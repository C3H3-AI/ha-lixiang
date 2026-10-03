"""API 错误类型与重试策略（统一收敛）

★ 2026-09-23 从 li_api.py 抽出（架构优化方案 阶段 2.6）

问题
----
原先 401 重试逻辑散落 3 处，且都用【字符串匹配】判断：
```python
if "401" in str(err):          # ← 脆弱：错误消息格式一变就失效
    self.invalidate_tokens()
    return _do()
```
3 处分别在 `li_api.py:326`（VSS 轮询）、`:532`（车控命令）、`:547`（命令结果查询）。

解决
----
① 结构化异常 `TokenExpired`：401 不再靠字符串，靠类型
② `ResultPolicy`：把「清 token → 重试一次」收敛成一处

用法
----
```python
from .policy import POLICY_VSS, run_with_retry, TokenExpired

def _do():
    return self._signed_call(...)

return run_with_retry(
    _do,
    on_token_expired=self.invalidate_tokens,
    policy=POLICY_VSS,
)
```

设计取舍
--------
· **不做**通用重试框架（指数退避/熔断）—— 这是个人项目，够用即可
· 只处理「token 失效重试一次」这一个真实存在的场景
· 保留 `LiApiError` 名字作为基类别名，避免一次性大改
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

_LOGGER = logging.getLogger("lixiang_auto")

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════
#  异常层次
# ═══════════════════════════════════════════════════════════════════════════
class ApiError(RuntimeError):
    """所有 API 错误的基类。

    ★ 统一原先混用的 LiApiError / LiCarApiError / LiAuthError。
      旧名字保留为别名（见文件末尾），避免一次性大改。
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        path: str = "",
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.path = path
        self.request_id = request_id


class TokenExpired(ApiError):
    """Token 失效（HTTP 401）。

    ★ 结构化异常 —— 替代 `if "401" in str(err)` 的字符串匹配。
      构造时自动从消息里提取状态码，兼容旧的调用点。
    """

    def __init__(self, message: str = "token expired", **kw: Any) -> None:
        super().__init__(message, status=401, **kw)


class CommandError(ApiError):
    """车控命令失败（业务层）。"""


class AuthError(ApiError):
    """登录/认证失败。"""


# ═══════════════════════════════════════════════════════════════════════════
#  重试策略
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True, slots=True)
class ResultPolicy:
    """一次 API 调用的容错策略。"""

    name: str = "default"
    retry_on_token_expired: bool = True
    max_retries: int = 1
    """401 后最多重试几次（0 = 不重试）。"""

    log_level: str = "info"
    """重试时的日志级别。"""

    def log(self, msg: str) -> None:
        getattr(_LOGGER, self.log_level, _LOGGER.info)(msg)


# 预置策略（调用点一眼看懂意图）
POLICY_VSS = ResultPolicy(name="vss", retry_on_token_expired=True, max_retries=1)
POLICY_COMMAND = ResultPolicy(name="command", retry_on_token_expired=True, max_retries=1)
POLICY_RESULT = ResultPolicy(name="cmd-result", retry_on_token_expired=True, max_retries=1)
POLICY_LOGIN = ResultPolicy(name="login", retry_on_token_expired=False, max_retries=0)


# ═══════════════════════════════════════════════════════════════════════════
#  执行器
# ═══════════════════════════════════════════════════════════════════════════
def run_with_retry(
    call: Callable[[], T],
    *,
    on_token_expired: Callable[[], None] | None = None,
    policy: ResultPolicy = POLICY_VSS,
    before_retry: Callable[[], None] | None = None,
) -> T:
    """执行 call，遇到 TokenExpired 时清 token 并重试。

    参数
    ----
    call              : 实际发请求的零参函数
    on_token_expired  : 清 token 缓存的回调（通常是 self.invalidate_tokens）
    policy            : 重试策略
    before_retry      : 重试前的额外处理（如重算 expireAt）

    返回
    ----
    call() 的结果；重试用尽后抛出最后一次的 TokenExpired。

    行为
    ----
    · 非 TokenExpired 的异常直接透传（不吞异常）
    · max_retries=0 时不重试，直接抛
    · 每次重试都调 on_token_expired（清缓存）+ before_retry
    """
    attempts = 0
    while True:
        try:
            return call()
        except TokenExpired as err:
            if not policy.retry_on_token_expired or attempts >= policy.max_retries:
                raise
            attempts += 1
            policy.log(
                f"[{policy.name}] token 失效（第 {attempts} 次重试）: {err}"
            )
            if on_token_expired is not None:
                on_token_expired()
            if before_retry is not None:
                before_retry()


def is_token_expired(err: BaseException) -> bool:
    """判断异常是否为 token 失效。

    ★ 兼容层：旧代码抛的是普通 LiApiError 且消息里含 "401"，
      这个函数让两者都能被识别。新代码应直接抛 TokenExpired。
    """
    if isinstance(err, TokenExpired):
        return True
    if isinstance(err, ApiError) and err.status == 401:
        return True
    # 兼容：旧调用点把 401 塞在消息里
    return "401" in str(err) and "Unauthorized" in str(err)


# ═══════════════════════════════════════════════════════════════════════════
#  向后兼容别名（阶段 2 完成后可删）
# ═══════════════════════════════════════════════════════════════════════════
LiApiError = ApiError
LiCommandError = CommandError
LiAuthError = AuthError


__all__ = [
    "ApiError", "TokenExpired", "CommandError", "AuthError",
    "ResultPolicy", "run_with_retry", "is_token_expired",
    "POLICY_VSS", "POLICY_COMMAND", "POLICY_RESULT", "POLICY_LOGIN",
    # 兼容别名
    "LiApiError", "LiCommandError", "LiAuthError",
]
