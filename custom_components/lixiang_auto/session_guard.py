"""命令下发的**代际守卫** —— 防止"账号/token 已变，命令还按旧的发出去"。

## 为什么需要（学自问界 huawei-auto-cloud 的 generation 机制）

问界的 `RouteRegistry.is_current()` 在下发前比对四样东西：
账号代际 / 会话 ID / 会话代际 / 合同 ID，任一不符就拒绝下发。

我们场景更简单（单车单账号），但**风险同源**：

  · 用户在 HA 里重新登录（换账号 / 重新授权）
  · token 被刷新或重新获取
  · 用户改了配置条目的账号

**若不校验**：命令可能带着**已失效的 token** 发出去 ——
轻则失败（`access_denied`），重则落到一个"你以为还是原来那个"的会话上。

## 我们的两层代际（砍到最小，不过度设计）

| 代际 | 何时 +1 | 防什么 |
|---|---|---|
| `account_generation` | 重新登录 / 换账号 | 发错账号 |
| `token_generation` | token 刷新 / 重新获取 | 带旧 token 下发 |

VIN 在 `LiApiClient` 构造时定死（`self._vin`，运行期不改），
所以**不需要 VIN 代际** —— 这是有依据的简化，不是遗漏。

## 用法

```python
guard = SessionGuard()

# 命令入口：抓当前代际
ticket = guard.snapshot()

# ... 中间可能发生重登 / token 刷新（异步等待、轮询结果时尤其容易）...

# 下发前：校验代际未变
guard.assert_current(ticket)      # 变了就抛 StaleSession
```

★ **关键设计**：ticket 在命令**入口**取，在校验点比 ——
中间隔着的正是"轮询等待"这段最危险的窗口。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StaleSession", "SessionGuard", "SessionTicket"]


class StaleSession(RuntimeError):
    """账号或 token 在命令执行期间被更换 —— 拒绝继续下发。

    宁可明确失败，也不要带着失效凭据发出去。
    """

    def __init__(self, reason: str, *, expected: "SessionTicket",
                 current: "SessionTicket") -> None:
        self.reason = reason
        self.expected = expected
        self.current = current
        super().__init__(
            f"会话已变更（{reason}）：命令被拒绝下发。"
            f" expected(account_gen={expected.account_generation},"
            f"token_gen={expected.token_generation})"
            f" current(account_gen={current.account_generation},"
            f"token_gen={current.token_generation})")


@dataclass(frozen=True)
class SessionTicket:
    """命令入口处的会话快照。"""

    account_generation: int
    token_generation: int
    vin: str = ""

    def describe(self) -> str:
        return (f"account_gen={self.account_generation},"
                f"token_gen={self.token_generation}")


@dataclass(frozen=True)
class _Snapshot:
    account: int
    token: int
    vin: str


class SessionGuard:
    """代际守卫。

    · `bump_account()` —— 重新登录 / 换账号时调用
    · `bump_token()`   —— token 刷新 / 重新获取时调用
    · `snapshot()`     —— 命令入口取快照
    · `assert_current(ticket)` —— 下发前校验
    """

    __slots__ = ("_account", "_token", "_vin")

    def __init__(self, *, vin: str = "") -> None:
        self._account = 0
        self._token = 0
        self._vin = str(vin or "")

    # ── 代际推进 ────────────────────────────────────────────
    def bump_account(self, *, vin: str | None = None) -> int:
        """账号代际 +1（重新登录 / 换账号 / 改配置）。"""
        self._account += 1
        # token 必然也变了（换账号 ⇒ 旧 token 作废）
        self._token += 1
        if vin is not None:
            self._vin = str(vin or "")
        return self._account

    def set_vin(self, vin: str) -> None:
        """只改 VIN，不动代际（用于单独验证 VIN 判据）。"""
        self._vin = str(vin or "")

    def bump_token(self) -> int:
        """token 代际 +1（刷新 / 重新获取）。"""
        self._token += 1
        return self._token

    # ── 快照与校验 ──────────────────────────────────────────
    def snapshot(self) -> SessionTicket:
        return SessionTicket(self._account, self._token, self._vin)

    def is_current(self, ticket: SessionTicket) -> tuple[bool, str]:
        """返回 (是否仍然有效, 原因)。"""
        cur = self.snapshot()
        if ticket.account_generation != cur.account_generation:
            return False, "账号已更换"
        if ticket.token_generation != cur.token_generation:
            return False, "token 已刷新/重新获取"
        if ticket.vin and cur.vin and ticket.vin != cur.vin:
            return False, "VIN 已变更"
        return True, ""

    def assert_current(self, ticket: SessionTicket) -> None:
        """代际不符就抛 `StaleSession`。"""
        ok, reason = self.is_current(ticket)
        if not ok:
            raise StaleSession(reason, expected=ticket, current=self.snapshot())

    def current(self) -> SessionTicket:
        return self.snapshot()
