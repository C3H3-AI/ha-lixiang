"""登录会话 cookie 持久化 —— 回归测试（2026-10-10）。

为什么要它
----------
用户实测：**手机上的「理想汽车」App 被顶下线**。

取证发现：会话对象 `_cli` 只在内存里，**cookie 从不落盘** ——
于是「每次 HA 启动 / 每次会话丢失」都要重做一次 **PAKE 密码登录**
（日志实证：重启后 1 秒出现 `li_api PAKE 登录成功 (app_type=livis)`）。
每次密码登录都是一次可能顶掉手机 App 的事件。

而会话 cookie 本身有 **13 天**有效期 —— 存下来复用即可完全跳过登录。

改动（fail-safe）
----------------
1. `_login()` 成功后导出 cookie → 经 `_notify_token_update` 回写 config entry
2. `_ensure_session()` 先装载持久化的 cookie 复用会话；装不到（过期/为空）
   才走 `_login()`
3. 服务端若已不认这份会话 → 换取失败 → 既有「会话失效 → 密码重登」路径兜底
   （最坏情况与改动前完全一致）

本文件既测**真实类的 cookie 往返**，也用 AST 抽真实方法测复用决策。
"""
from __future__ import annotations

import ast
import logging
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
LI_API = CC / "li_api.py"
INIT = CC / "__init__.py"

sys.path.insert(0, str(CC))
import pake_login  # noqa: E402


# ── ① 真实类的 cookie 往返 ───────────────────────────────────────────────
class TestCookieRoundTrip:
    def _client(self):
        return pake_login.LixiangDirectLogin(device_id="DEVID", app_type="livis")

    def _add(self, cli, name, value, domain=".lixiang.com", path="/", expires=None):
        kw = {"domain": domain, "path": path}
        if expires is not None:
            kw["expires"] = expires
        cli._sess.cookies.set(name, value, **kw)

    def test_export_import_roundtrip(self):
        a = self._client()
        self._add(a, "sso_token", "SSO-VALUE")
        self._add(a, "authli_device_id", "DEVID", domain="account.lixiang.com")
        exported = a.export_session_cookies()
        assert any(c["name"] == "sso_token" and c["value"] == "SSO-VALUE"
                   for c in exported)

        b = self._client()
        assert b.import_session_cookies(exported) >= 2
        got = {c.name: c.value for c in b._sess.cookies}
        assert got.get("sso_token") == "SSO-VALUE", "登录态 cookie 没被装载"
        assert got.get("authli_device_id") == "DEVID"

    def test_domain_preserved(self):
        a = self._client()
        self._add(a, "sso_token", "V", domain=".lixiang.com")
        b = self._client()
        b.import_session_cookies(a.export_session_cookies())
        doms = {c.domain for c in b._sess.cookies if c.name == "sso_token"}
        assert doms == {".lixiang.com"}, f"域丢失 → H5 会跳登录: {doms}"

    def test_expired_cookie_not_imported(self):
        """★ 过期 cookie 必须丢 —— 否则拿着死会话去换 token 白折腾一轮。"""
        a = self._client()
        self._add(a, "sso_token", "FRESH")
        self._add(a, "dead_cookie", "OLD", expires=int(time.time()) - 3600)
        exported = a.export_session_cookies()
        b = self._client()
        b.import_session_cookies(exported)
        got = {c.name for c in b._sess.cookies}
        assert "dead_cookie" not in got, "过期 cookie 被装进来了"
        assert "sso_token" in got

    def test_import_is_idempotent(self):
        a = self._client()
        self._add(a, "sso_token", "V1")
        b = self._client()
        n1 = b.import_session_cookies(a.export_session_cookies())
        n2 = b.import_session_cookies(a.export_session_cookies())
        assert n1 == n2, "重复装载应当幂等"

    def test_garbage_tolerated(self):
        """脏数据不能打断启动（最坏退化为重新登录）。"""
        b = self._client()
        assert b.import_session_cookies(None) == 0
        assert b.import_session_cookies([None, {}, {"name": ""}, "junk", 42]) == 0
        assert b.import_session_cookies([{"name": "ok", "value": "1",
                                          "expires": "not-a-number"}]) == 1

    def test_export_skips_empty_values(self):
        a = self._client()
        self._add(a, "empty", "")
        assert all(c["value"] for c in a.export_session_cookies())


# ── ② 复用决策（AST 抽真实方法）─────────────────────────────────────────
class _FakeLoginClient:
    calls: list = []
    imported: list = []
    import_returns: int = 2

    def __init__(self, device_id=None, debug=False, app_type=None, **kw):
        self.device_id = device_id
        self.app_type = app_type
        self._sess = type("S", (), {"cookies": []})()

    def import_session_cookies(self, cookies):
        _FakeLoginClient.imported.append(list(cookies or []))
        return _FakeLoginClient.import_returns

    def export_session_cookies(self):
        return [{"name": "sso_token", "value": "NEW", "domain": ".lixiang.com",
                 "path": "/", "expires": 0}]

    def login(self, phone, password):
        _FakeLoginClient.calls.append(("login", phone))
        return {"access_token": "APP-x", "refresh_token": "rt-x"}


def _extract(*names):
    src = LI_API.read_text(encoding="utf-8")
    nodes = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in names:
                    nodes.append(sub)
    assert len(nodes) == len(names), f"未抽到: {names}"
    ns = {
        "__name__": "lx", "__package__": "lx",
        "_LOGGER": logging.getLogger("cookie_test"),
        "LixiangDirectLogin": _FakeLoginClient,
        "CONF_SESSION_COOKIES": "session_cookies",
        "CONF_HAC_KEY": "hac_key", "CONF_KEY_ID": "key_id",
        "CONF_XDEV": "x_chj_deviceid", "CONF_IDENTITY_SOURCE": "identity_source",
        "LiApiError": type("LiApiError", (RuntimeError,), {}),
        "CredentialRejected": type("CredentialRejected", (RuntimeError,), {}),
        "is_credential_rejection": lambda e: False,
        "APP_LIXIANG": "lixiang", "APP_LIVIS": "livis",
    }
    for n in nodes:
        exec(compile(ast.Module(body=[n], type_ignores=[]), f"<{n.name}>", "exec"), ns)
    return type("FakeClient", (), {n.name: ns[n.name] for n in nodes})


def _client(session_cookies=None, cli=None, stub_login=True):
    c = _extract("_ensure_session", "_login", "_notify_token_update")()
    c._session_cookies = list(session_cookies or [])
    c._cookies_dirty = False
    c._cli = cli
    c._xdev = "DEVID"
    c._device_id = "DEVID"
    c._app_type = "livis"
    c._phone = "13800000000"
    c._password = "pw"
    c._main_bearer = ""
    c._refresh_token = ""
    c._tokens = {}
    c._app_token = "APP-static"
    c._identity_dirty = False
    c.patches = []
    c._on_token_update = c.patches.append
    c.logins = []
    if stub_login:
        # _ensure_session 用例只需要知道「有没有走登录」→ 用桩
        c._login = lambda: c.logins.append(1)
    else:
        # 持久化用例要真实 _login（它才会 export cookie）
        c.logins = _FakeLoginClient.calls
    c._migrate_identity_if_needed = lambda *a, **k: None
    return c


class TestEnsureSessionReuse:
    def setup_method(self):
        _FakeLoginClient.calls = []
        _FakeLoginClient.imported = []
        _FakeLoginClient.import_returns = 2

    def test_reuses_persisted_session_without_login(self):
        """★★ 核心：有持久化 cookie 时**不得**做密码登录。"""
        c = _client(session_cookies=[{"name": "sso_token", "value": "V"}])
        cli = c._ensure_session()
        assert c.logins == [], "有持久化会话却仍然密码登录（每次重启都会顶号）"
        assert cli is not None and _FakeLoginClient.imported, "未装载 cookie"

    def test_logs_in_when_no_cookies(self):
        c = _client(session_cookies=None)
        c._ensure_session()
        assert c.logins == [1], "无会话可用时应回退密码登录"
        assert _FakeLoginClient.imported == []

    def test_logs_in_when_all_cookies_expired(self):
        """★ 过期（import 装入 0 条）→ 必须回退登录，不能拿着空会话硬跑。"""
        _FakeLoginClient.import_returns = 0
        c = _client(session_cookies=[{"name": "sso_token", "value": "V"}])
        c._ensure_session()
        assert c.logins == [1]

    def test_existing_client_wins(self):
        sentinel = object()
        c = _client(session_cookies=[{"name": "sso_token", "value": "V"}], cli=sentinel)
        assert c._ensure_session() is sentinel
        assert c.logins == [] and _FakeLoginClient.imported == []


class TestLoginPersistsCookies:
    def setup_method(self):
        _FakeLoginClient.calls = []
        _FakeLoginClient.imported = []
        _FakeLoginClient.import_returns = 2

    def test_login_exports_and_persists_cookies(self):
        """★ 登录后必须把 cookie 交给回写回调 —— 否则下次重启又要登录。"""
        c = _client(stub_login=False)
        c._login()
        assert _FakeLoginClient.calls, "未执行登录"
        assert c.patches, "登录后没有任何回写"
        patch = c.patches[-1]
        assert "session_cookies" in patch, "登录后未持久化会话 cookie"
        assert any(x["name"] == "sso_token" for x in patch["session_cookies"])

    def test_persist_is_conditional(self):
        """cookie 没变化时不必重复回写（避免每次都写 entry）。"""
        c = _client(stub_login=False)
        c._login()
        first = [p for p in c.patches if "session_cookies" in p]
        assert len(first) == 1
        c._notify_token_update()          # 再触发一次回写
        both = [p for p in c.patches if "session_cookies" in p]
        assert len(both) == 1, "cookie 未变化却重复写 entry"


# ── ③ 接线守卫 ──────────────────────────────────────────────────────────
class TestWiring:
    def test_init_passes_session_cookies(self):
        body = INIT.read_text(encoding="utf-8")
        assert "session_cookies=entry.data.get(CONF_SESSION_COOKIES)" in body, (
            "集成侧未把持久化的 session_cookies 传给客户端 → 复用永远不会发生")

    def test_const_defined(self):
        body = (CC / "const.py").read_text(encoding="utf-8")
        assert 'CONF_SESSION_COOKIES = "session_cookies"' in body

    def test_ensure_session_reuse_before_login(self):
        """顺序必须「先复用、后登录」；写反就等于没修。"""
        src = ast.get_source_segment(
            LI_API.read_text(encoding="utf-8"),
            next(n for n in ast.walk(ast.parse(LI_API.read_text(encoding="utf-8")))
                 if isinstance(n, ast.FunctionDef) and n.name == "_ensure_session"))
        assert src.index("import_session_cookies") < src.index("self._login()"), (
            "_ensure_session 里 _login() 出现在复用之前 → 复用被跳过")
