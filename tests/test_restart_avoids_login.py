"""重启后不再密码登录 —— 回归测试（2026-10-10）。

真机取证发现的两个根因
----------------------
① **`refresh_token` / `main_bearer` 只写不读**：集成把这两个 token 回写进
   config entry，但启动构造客户端时**从不传回** → `self._refresh_token` 与
   `self._main_bearer` 都是空 → travel / 充电累计量首次调用必然走 `_login()`
   （密码登录 = 可能顶掉手机 App），且 v1.4.10 的「refresh_token 免密续期」
   **在启动路径上永远不会生效**（实测日志：复用会话成功后 0.7s 又登录一次）。

② **`_get_scoped` 把任何换取失败都当「会话失效」**：5xx / 空响应 / 解析异常
   都会白白触发一次密码登录。只有 `login_required` / `100105` / HTTP 401
   这类才是真的会话失效，其余应原样抛出交给上层重试。

本文件还锁住一个**关键前提**：失败原因常在 `location` 的 query/fragment
（如 `error=login_required`），正文里可能什么都没有 —— 若不把它带进异常，
新的收窄判据会把「真会话失效」误判成「与会话无关」→ **永久不自愈**。
"""
from __future__ import annotations

import ast
import logging
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
LI_API = CC / "li_api.py"
INIT = CC / "__init__.py"


class _LiApiError(RuntimeError):
    pass


def _ns():
    return {
        "__name__": "lx", "__package__": "lx",
        "_LOGGER": logging.getLogger("restart_test"),
        "LiApiError": _LiApiError,
        "time": time,
        # 代码里用的是 `urllib.parse.urlparse(...)` → 这里要给【包】而非子模块
        "urllib": sys.modules["urllib"],
        "BASE_ID": "https://account.lixiang.com",
        "LOGIN_APP_VERSION": "8.25.4-10463",
        "SDK_VERSION": "1.0",
        "APP_LOGIN_PARAMS": {"lixiang": ("CID", "SCOPE", "https://cb")},
    }


def _top(name):
    src = LI_API.read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns = _ns()
            exec(compile(ast.Module(body=[node], type_ignores=[]), f"<{name}>", "exec"), ns)
            return ns[name]
    raise AssertionError(f"找不到顶层函数 {name}")


def _method(name, extra=None):
    src = LI_API.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    ns = _ns()
                    ns.update(extra or {})
                    exec(compile(ast.Module(body=[sub], type_ignores=[]),
                                 f"<{name}>", "exec"), ns)
                    cls = type("C", (), {name: ns[name]})
                    return cls
    raise AssertionError(f"找不到 LiApiClient.{name}")


# ── ① 会话失效判据 ───────────────────────────────────────────────────────
class TestSessionLossPredicate:
    def test_recognizes_real_session_loss(self):
        f = _top("_is_session_loss")
        assert f(_LiApiError("换 token 失败 (vss): HTTP 300 error=login_required")) is True
        assert f(_LiApiError("HTTP 401 unauthorized")) is True
        assert f(_LiApiError("100105 用户未登录")) is True

    def test_ignores_non_session_failures(self):
        """★ 与会话无关的失败不该重登（每次重登都可能顶掉手机 App）。"""
        f = _top("_is_session_loss")
        for msg in ("换 token 失败 (vss): HTTP 500 ",
                    "换 token 失败 (mms): HTTP 200 error=access_denied",
                    "换 token 失败 (vss): HTTP 0 ",
                    "connection reset by peer",
                    ""):
            assert f(_LiApiError(msg)) is False, msg

    def test_scope_denied_is_not_session_loss(self):
        """access_denied 走 _is_scope_denied 分支，不能被判成会话失效。"""
        assert _top("_is_session_loss")(_LiApiError("HTTP 300 access_denied")) is False


# ── ② _get_scoped：只有真会话失效才重登 ─────────────────────────────────
class _Scoped:
    def __init__(self, errors):
        self._errors = list(errors)     # 每次 exchange 抛的错（None = 成功）
        self._tokens = {}
        self._password = "pw"
        self._cli = object()
        self.logins = []
        self.exchanges = []
        self._login = lambda: self.logins.append(1)

    def _exchange(self, scope, audience):
        self.exchanges.append((scope, audience))
        err = self._errors.pop(0) if self._errors else None
        if err is not None:
            raise err
        return "TOK-" + str(len(self.exchanges))


class TestGetScopedRelogin:
    def _run(self, errors, ttl=780):
        cls = _method("_get_scoped", extra={
            "_is_scope_denied": _top("_is_scope_denied"),
            "_is_session_loss": _top("_is_session_loss"),
        })
        c = cls()
        inst = _Scoped(errors)
        return inst, cls._get_scoped(inst, "vss", "AUD", ttl)

    def test_relogins_on_login_required(self):
        inst, tok = self._run([_LiApiError("HTTP 300 error=login_required")])
        assert inst.logins == [1], "真会话失效却没重登（会永久失效）"
        assert tok == "TOK-2"

    def test_does_not_relogin_on_server_error(self):
        """★ 核心：5xx 不该重登 —— 每次重登都可能顶掉手机 App。"""
        try:
            self._run([_LiApiError("换 token 失败 (vss): HTTP 500 ")])
        except _LiApiError as err:
            assert "HTTP 500" in str(err)
        else:
            raise AssertionError("5xx 时应当原样抛出")
        # 重新跑一次以检查 login 未被调用
        cls = _method("_get_scoped", extra={
            "_is_scope_denied": _top("_is_scope_denied"),
            "_is_session_loss": _top("_is_session_loss")})
        inst = _Scoped([_LiApiError("HTTP 502 bad gateway")])
        try:
            cls._get_scoped(inst, "vss", "AUD", 780)
        except _LiApiError:
            pass
        assert inst.logins == [], "服务端 5xx 竟然触发了密码重登"

    def test_no_relogin_without_password(self):
        cls = _method("_get_scoped", extra={
            "_is_scope_denied": _top("_is_scope_denied"),
            "_is_session_loss": _top("_is_session_loss")})
        inst = _Scoped([_LiApiError("HTTP 300 error=login_required")])
        inst._password = ""
        try:
            cls._get_scoped(inst, "vss", "AUD", 780)
        except _LiApiError:
            pass
        assert inst.logins == []

    def test_caches_success(self):
        cls = _method("_get_scoped", extra={
            "_is_scope_denied": _top("_is_scope_denied"),
            "_is_session_loss": _top("_is_session_loss")})
        inst = _Scoped([])
        a = cls._get_scoped(inst, "vss", "AUD", 780)
        b = cls._get_scoped(inst, "vss", "AUD", 780)
        assert a == b and len(inst.exchanges) == 1, "成功结果没被缓存"


# ── ③ 失败原因必须能被判据看到（否则收窄 = 永久不自愈）──────────────────
class _Resp:
    def __init__(self, status=302, location="", text=""):
        self.status_code = status
        self.headers = {"location": location}
        self.text = text


class _Sess:
    def __init__(self, resp):
        self._resp = resp

    def post(self, *a, **kw):
        return self._resp


class _Cli:
    def __init__(self, resp):
        self._sess = _Sess(resp)


class TestExchangeErrorHint:
    def _call(self, resp):
        cls = _method("_do_exchange")
        inst = type("I", (), {})()
        inst._sess = None
        inst._device_id = "DEVID"      # _do_exchange 组请求头/表单要用
        try:
            cls._do_exchange(inst, _Cli(resp), "livis", "vss", "AUD")
        except _LiApiError as err:
            return str(err)
        raise AssertionError("应当抛出 LiApiError")

    def test_error_marker_from_location_is_carried(self):
        """★ location 里的 error=login_required 必须出现在异常里。"""
        resp = _Resp(location="https://x/#error=login_required&error_description=expired")
        msg = self._call(resp)
        assert "login_required" in msg, f"失败原因丢失 → 无法判定会话失效: {msg}"
        assert _top("_is_session_loss")(_LiApiError(msg)) is True

    def test_no_token_leaked_into_message(self):
        """只带诊断键：location 别处的 token 不能被写进日志。

        注：fragment 里若有 access_token 就是**成功**（不会抛错），
        所以要构造「token 在 query、error 在 fragment」这种真实失败形态。
        """
        resp = _Resp(location="https://x/?access_token=SECRET-TOKEN#error=access_denied")
        msg = self._call(resp)
        assert "access_denied" in msg, "诊断键丢了"
        assert "SECRET-TOKEN" not in msg, f"把 token 写进日志了: {msg}"

    def test_plain_failure_still_raises(self):
        msg = self._call(_Resp(status=500, location="", text="oops"))
        assert "HTTP 500" in msg


# ── ④ 启动接线守卫（本次 bug 的形态：只写不读）──────────────────────────
class TestStartupTokenWiring:
    def test_init_passes_refresh_token_and_main_bearer(self):
        body = INIT.read_text(encoding="utf-8")
        assert "refresh_token=entry.data.get(CONF_REFRESH_TOKEN)" in body, (
            "未把 entry 里的 refresh_token 传回客户端 → 每次重启必然密码登录")
        assert "CONF_MAIN_BEARER" in body and "main_bearer=(" in body, (
            "未把 entry 里的 main_bearer 传回客户端")

    def test_client_accepts_and_stores_main_bearer(self):
        src = LI_API.read_text(encoding="utf-8")
        assert "main_bearer: str = \"\"," in src, "LiApiClient 未接受 main_bearer 参数"
        assert "self._main_bearer: str = str(main_bearer)" in src, (
            "main_bearer 参数没被赋给 self._main_bearer")

    def test_missing_refresh_token_is_visible(self):
        """刷新续期拿不到 refresh_token 时必须留痕（此前静默，排查极难）。"""
        assert "无 refresh_token 可续期" in LI_API.read_text(encoding="utf-8")
