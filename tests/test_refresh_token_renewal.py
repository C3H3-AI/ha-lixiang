"""refresh_token 免密续期主 Bearer —— 回归测试（2026-10-10）。

背景
----
`pake_login.refresh()` 存在但**全仓库无调用**（死代码，PR #38 提过、后来被放弃）。
于是会话失效只有一条路：**整段密码重登**（PAKE）—— 每次都要走一次密码登录，
有账号风控成本，也更慢。

本次接通，但**只接在主 Bearer 通道**（travel 陪伴里程 / 充电明细与月统计），
因为项目自己的实测结论是：

    裸 Bearer 换不了 scope token，必须带登录会话 cookie；
    refresh_token 续期**不会重新种 cookie** → 它救不了 VSS / 车控 / 任务大师。

★ 实现里最容易踩、也最危险的坑：
  **refresh_token 会轮换**。新值必须回写 config entry，否则「续期一次 →
  下次重启必须密码重登」—— 反而**制造**风控。本文件对此有专门用例。

测试环境没有 homeassistant → AST 抽真实方法 + 注入假依赖。
"""
from __future__ import annotations

import ast
import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
LI_API = CC / "li_api.py"

_METHODS = ("_refresh_main_bearer", "_travel_bearer", "_notify_token_update", "_login")


class _FakeLogin:
    """假 PAKE 客户端：refresh() 按脚本返回或抛错，并记录调用。"""

    calls: list = []
    result: dict | None = None
    error: Exception | None = None

    def __init__(self, device_id=None, debug=False, app_type=None):
        self.device_id = device_id
        self.app_type = app_type

    def refresh(self, refresh_token):
        _FakeLogin.calls.append(("refresh", refresh_token))
        if _FakeLogin.error is not None:
            raise _FakeLogin.error
        return dict(_FakeLogin.result or {})

    def login(self, phone, password):
        _FakeLogin.calls.append(("login", phone))
        return {"access_token": "APP-from-login", "refresh_token": "rt-from-login"}


def _load():
    src = LI_API.read_text(encoding="utf-8")
    tree = ast.parse(src)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in _METHODS:
                    nodes.append(sub)
    assert len(nodes) >= 3, "未抽到续期相关方法"

    ns = {
        "__name__": "lx", "__package__": "lx",
        "_LOGGER": logging.getLogger("refresh_test"),
        "LixiangDirectLogin": _FakeLogin,
        "LoginError": type("LoginError", (RuntimeError,), {}),
    }
    for n in nodes:
        exec(compile(ast.Module(body=[n], type_ignores=[]), f"<{n.name}>", "exec"), ns)
    cls = type("FakeClient", (), {n.name: ns[n.name] for n in nodes})
    return cls


def _client(refresh_token="rt-old", main_bearer="", cli=None, tokens=None, password="pw"):
    c = _load()()
    c._refresh_token = refresh_token
    c._main_bearer = main_bearer
    c._cli = cli
    c._tokens = tokens if tokens is not None else {"vss": ("t", 0.0)}
    c._password = password
    c._phone = "13800000000"
    c._xdev = "DEV"
    c._device_id = "DEV"
    c._app_type = "lixiang"
    c._app_token = "APP-static"
    # 真实 _notify_token_update 会读这个标记（身份迁移用）；本测试不涉及身份
    c._identity_dirty = False
    c.patches = []
    c._on_token_update = c.patches.append
    c.logins = []

    def _fake_login():
        """模拟真实 _login()：成功后写入新的主 Bearer/refresh_token。"""
        c.logins.append(1)
        c._main_bearer = "APP-from-login"
        c._refresh_token = "rt-from-login"

    c._login = _fake_login
    return c


class TestRefreshMainBearer:
    def setup_method(self):
        _FakeLogin.calls = []
        _FakeLogin.result = {"access_token": "APP-new", "refresh_token": "rt-new"}
        _FakeLogin.error = None

    def test_success_updates_bearer_and_rotated_token(self):
        c = _client()
        assert c._refresh_main_bearer() is True
        assert c._main_bearer == "APP-new"
        assert c._refresh_token == "rt-new"

    def test_rotated_refresh_token_is_persisted(self):
        """★★ 最关键的坑：轮换后的 refresh_token 必须回写。

        只存内存 → 下次重启读回旧值 → refresh 失败 → 必须密码重登
        → 反而制造风控（这正是当初「离线续期」没做好的地方）。
        """
        c = _client()
        c._refresh_main_bearer()
        assert c.patches, "未触发回写回调 —— 轮换后的 refresh_token 会丢"
        patch = c.patches[-1]
        assert patch.get("refresh_token") == "rt-new", patch
        assert patch.get("main_bearer") == "APP-new", patch

    def test_no_refresh_token_returns_false(self):
        c = _client(refresh_token="")
        assert c._refresh_main_bearer() is False
        assert _FakeLogin.calls == [], "无 refresh_token 时不该发起请求"

    def test_refresh_error_is_swallowed(self):
        _FakeLogin.error = RuntimeError("HTTP 400 invalid_grant")
        c = _client()
        assert c._refresh_main_bearer() is False, "续期失败必须返回 False（交给上层回退）"
        assert c._main_bearer == "", "失败不得污染主 Bearer"
        assert c._refresh_token == "rt-old", "失败不得改动 refresh_token"

    def test_missing_access_token_returns_false(self):
        _FakeLogin.result = {"refresh_token": "rt-x"}
        c = _client()
        assert c._refresh_main_bearer() is False
        assert c.patches == []

    def test_unchanged_token_not_logged_as_rotation(self):
        """服务端不轮换时也要正常工作并回写（幂等）。"""
        _FakeLogin.result = {"access_token": "APP-new", "refresh_token": "rt-old"}
        c = _client()
        assert c._refresh_main_bearer() is True
        assert c._refresh_token == "rt-old"


class TestTravelBearerFallback:
    def setup_method(self):
        _FakeLogin.calls = []
        _FakeLogin.result = {"access_token": "APP-new", "refresh_token": "rt-new"}
        _FakeLogin.error = None

    def test_force_login_prefers_refresh(self):
        """★ force_login 时先免密续期 —— 成功就不该走密码重登。"""
        c = _client()
        assert c._travel_bearer(force_login=True) == "APP-new"
        assert c.logins == [], "续期成功却仍然密码重登（白付一次风控）"

    def test_force_login_falls_back_to_password(self):
        """★ fail-safe：续期不可用时行为与改动前完全一致（走密码重登）。"""
        _FakeLogin.error = RuntimeError("no")
        c = _client()
        assert c._travel_bearer(force_login=True) == "APP-from-login"
        assert c.logins == [1], "续期失败必须回退密码重登"
        assert c._tokens == {}, "密码重登路径仍需清 scope token 缓存"

    def test_existing_bearer_not_renewed(self):
        """已有主 Bearer 且非 force → 不续期、不重登（保持原行为）。"""
        c = _client(main_bearer="APP-alive")
        assert c._travel_bearer() == "APP-alive"
        assert _FakeLogin.calls == []
        assert c.logins == []

    def test_falls_back_to_static_token_when_all_fail(self):
        """无密码、续期也失败 → 退回静态 app_token（不抛异常）。"""
        _FakeLogin.error = RuntimeError("no")
        c = _client(password="")
        c._login = lambda: None
        assert c._travel_bearer(force_login=True) == "APP-static"


class TestBoundaryGuard:
    """★ 技术边界：scope token 通道**不能**用 refresh（需要 cookie）。"""

    def _method_src(self, name: str) -> str:
        src = LI_API.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
                for sub in node.body:
                    if (isinstance(sub, ast.FunctionDef) and sub.name == name):
                        return ast.get_source_segment(src, sub) or ""
        raise AssertionError(f"找不到 {name}")

    def test_get_scoped_does_not_use_refresh(self):
        """换 scope token 必须带会话 cookie；refresh 不会重种 cookie。

        若有人「顺手」把续期也接到 _get_scoped，会得到「看起来成功、
        实际换不到 token」的假象 —— 这里挡住。
        """
        body = self._method_src("_get_scoped")
        assert "_refresh_main_bearer" not in body, (
            "scope token 通道不能靠 refresh 恢复（cookie 不会重种）")

    def test_get_scoped_still_relogins_with_password(self):
        body = self._method_src("_get_scoped")
        assert "_login()" in body, "scope 通道失效仍应密码重登"

    def test_docstring_states_cookie_constraint(self):
        """模块头部必须保留这条实测结论（否则后人会误以为 refresh 万能）。"""
        head = LI_API.read_text(encoding="utf-8")[:2000]
        assert "cookie" in head and "refresh_token" in head, (
            "模块头部应说明「refresh_token 续期不会重新种 cookie」")
