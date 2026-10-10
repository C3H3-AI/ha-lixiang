"""凭据失效 → HA 标准「重新认证」 的回归测试（2026-10-10）。

背景（真缺陷）
--------------
用户改了理想账号密码后：

1. 会话 cookie（13 天）与 refresh token 还能撑一段 → **不会立刻坏**；
2. 需要重登时（cookie 过期 / 401 / 重启后首次签名调用），`_login()` 用
   存着的旧密码 PAKE → 服务端 401「密码错误或账号不存在」；
3. 这个错误在协调器里被**分段 try/except 吞掉**（那些分段本来是为了
   网络抖动降级）→ 用户只看到「实体不可用 + 一条『网络中断 / 车辆离线 /
   凭据失效』的含糊通知」，**永远等不到** HA 的「需要重新认证」入口。

修法：把「凭据被拒」与网络错误区分开，让它一路冒到最外层 →
`ConfigEntryAuthFailed` → HA 自动弹出重新认证。

本文件既测分类/行为，也用 AST 守卫「不许再新增吞掉凭据失效的分段」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"

# conftest 已把集成目录加进 sys.path → 可直接导入无 HA 依赖的模块
sys.path.insert(0, str(CC)) if str(CC) not in sys.path else None  # noqa: B018

from pake_login import (  # noqa: E402
    CredentialRejected,
    LoginError,
    is_credential_rejection,
)

COORD = CC / "coordinator.py"


def _src(name: str) -> str:
    return (CC / name).read_text(encoding="utf-8")


# ── ① 分类器：只认「账号/密码被拒」，不认网络与风控 ────────────────────────
class TestCredentialClassification:
    def test_401_is_credential_rejection(self):
        """实测：401 空体 = 密码错误。"""
        assert is_credential_rejection(LoginError("login", 401, "密码错误或账号不存在"))
        assert is_credential_rejection(CredentialRejected("login", 401, "x"))

    def test_plain_detail_also_counts(self):
        assert is_credential_rejection(LoginError("login", 0, "密码错误"))

    def test_network_error_is_not(self):
        """★ 网络抖动绝不能转成「去改密码」——否则用户被误导。"""
        assert not is_credential_rejection(ConnectionError("connection reset"))
        assert not is_credential_rejection(TimeoutError("timeout"))

    def test_sms_risk_control_is_not(self):
        """风控（设备未受信任）不是密码问题，走浏览器辅助登录，不弹改密码。"""
        assert not is_credential_rejection(
            LoginError("login", 300, "密码正确但风控要求短信验证"))
        assert not is_credential_rejection(LoginError("login", 500, "服务端错误"))


# ── ② _login 把凭据被拒转成结构化异常 ─────────────────────────────────────
class _FakeLogin:
    """假 PAKE 客户端：按需抛出指定异常。"""

    def __init__(self, raise_exc=None, device_id=None, debug=False, app_type=None):
        self._exc = raise_exc
        self.device_id = device_id

    def login(self, phone, password):
        if self._exc is not None:
            raise self._exc
        return {"access_token": "APP-x", "refresh_token": "rt"}


def _load_login(raise_exc):
    """AST 抽出真实 `LiApiClient._login`，注入假依赖后调用。"""
    src = _src("li_api.py")
    tree = ast.parse(src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == "_login":
                    fn = sub
    assert fn is not None, "找不到 LiApiClient._login"

    ns = {
        "__name__": "lx", "__package__": "lx",
        "LiApiError": type("LiApiError", (Exception,), {}),
        "LoginError": LoginError,
        "CredentialRejected": CredentialRejected,
        "is_credential_rejection": is_credential_rejection,
        "LixiangDirectLogin": lambda **kw: _FakeLogin(raise_exc, **kw),
        "_LOGGER": __import__("logging").getLogger("t"),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<_login>", "exec"), ns)

    class C:
        pass

    C._login = ns["_login"]
    c = C()
    c._xdev = "DEV"
    c._device_id = "DEV"
    c._app_type = "lixiang"
    c._phone = "13800000000"
    c._password = "old-pw"
    c._main_bearer = ""
    c._refresh_token = ""
    c._tokens = {}
    c._notify_token_update = lambda: None
    c._migrate_identity_if_needed = lambda reason: False
    return c


class TestLoginConvertsCredentialError:
    def test_wrong_password_becomes_credential_rejected(self):
        """★ 401 → CredentialRejected（供上层转 ConfigEntryAuthFailed）。"""
        c = _load_login(LoginError("login", 401, "密码错误或账号不存在"))
        with pytest.raises(CredentialRejected) as ei:
            c._login()
        assert ei.value.status == 401

    def test_network_error_passes_through_unchanged(self):
        """网络错误必须原样抛出（不能变成「要改密码」）。"""
        c = _load_login(ConnectionError("reset by peer"))
        with pytest.raises(ConnectionError):
            c._login()

    def test_sms_risk_control_passes_through_unchanged(self):
        c = _load_login(LoginError("login", 300, "密码正确但风控要求短信验证"))
        with pytest.raises(LoginError) as ei:
            c._login()
        assert not isinstance(ei.value, CredentialRejected)


# ── ③ coordinator：_fail_if_credential 只在凭据失效时抛 ───────────────────
def _load_fail_helper():
    src = COORD.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_fail_if_credential")

    class _AuthFailed(Exception):
        pass

    ns = {
        "__name__": "cx",
        "is_credential_rejection": is_credential_rejection,
        "ConfigEntryAuthFailed": _AuthFailed,
        "_LOGGER": __import__("logging").getLogger("t"),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<h>", "exec"), ns)
    return ns["_fail_if_credential"], _AuthFailed


class TestFailIfCredential:
    def test_raises_for_credential_rejection(self):
        fn, AuthFailed = _load_fail_helper()
        with pytest.raises(AuthFailed):
            fn(CredentialRejected("login", 401, "密码错误"))

    def test_silent_for_other_errors(self):
        """网络/其它错误必须放行原逻辑（否则会误导用户去改密码）。"""
        fn, AuthFailed = _load_fail_helper()
        for err in (ConnectionError("reset"), TimeoutError("t"),
                    LoginError("login", 300, "风控要求短信验证"),
                    LoginError("login", 500, "服务端 500")):
            assert fn(err) is None
        # 且不应抛
        fn(ValueError("boom"))


# ── ④ AST 守卫：不许再新增「吞掉凭据失效」的分段 ──────────────────────────
class TestNoSwallowingHandlers:
    def test_coordinator_imports_config_entry_auth_failed(self):
        src = COORD.read_text(encoding="utf-8")
        assert "ConfigEntryAuthFailed" in src, "未使用 HA 标准的重新认证信号"

    def test_every_update_handler_checks_credential(self):
        """★ 更新流程里每个「吞异常继续」的分段都必须先做凭据判定。

        这条守卫的价值：将来有人新增一个 `except Exception: log` 分段时，
        凭据失效会再次被静默吞掉（本次修的就是这个问题）→ 测试必须红。
        """
        src = COORD.read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = None
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "_async_update_data"):
                fn = node
        assert fn is not None, "找不到 _async_update_data"

        # 只要求「包住网络调用」的分段做凭据判定 —— 纯本地计算（如派生信号
        # 的 eval）不可能产出凭据错误，无谓加检查是噪声。
        NET_MARKERS = ("li_api", "self.client", "async_add_executor_job",
                       "_signed_call", "get_tasks")

        bad = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.Try):
                continue
            body_src = " ".join(
                ast.get_source_segment(src, st) or "" for st in node.body)
            if not any(m in body_src for m in NET_MARKERS):
                continue
            for handler in node.handlers:
                seg = ast.get_source_segment(src, handler) or ""
                if "_fail_if_credential(" in seg:
                    continue
                bad.append(f"line {handler.lineno}: {seg.splitlines()[0]}")
        assert not bad, (
            "以下「包住网络调用」的分段会静默吞掉凭据失效，"
            "导致用户等不到重新认证提示：\n  " + "\n  ".join(bad))

    def test_helper_raises_only_for_credential(self):
        """_fail_if_credential 的 raise 必须在 is_credential_rejection 判定之内。"""
        src = COORD.read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(src).body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_fail_if_credential")
        ifs = [n for n in ast.walk(fn) if isinstance(n, ast.If)]
        assert ifs, "_fail_if_credential 缺少条件判断（会无差别抛 AuthFailed）"
        cond = ast.get_source_segment(src, ifs[0].test) or ""
        assert "is_credential_rejection" in cond, (
            "必须以 is_credential_rejection 作为前置条件")
        raises = [n for n in ast.walk(ifs[0]) if isinstance(n, ast.Raise)]
        assert raises, "条件成立时未抛 ConfigEntryAuthFailed"
