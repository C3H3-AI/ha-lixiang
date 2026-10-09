"""刷新渠道（refresh_channel）守卫测试（2026-10-09 新增）

★ 背景（用户视角）：

  登录会话过期后，集成此前只有一条恢复路径：密码重登。1.5.0 起，
  集成选项提供「刷新渠道」：自动回退 / 主渠道 / 理想同学渠道 / 仅密码重登。
  任何渠道失败都会回退到密码重登 —— 最坏情况必须等于原行为。

★ 本测试守卫的不变量：

  ① 渠道序列映射正确（auto/primary/livis/password + callable 注入）
  ② 回退顺序正确，且【探测是硬门槛】：
     渠道"受理"了但探测换 token 失败 → 必须继续回退，不得当作成功
  ③ 「仅密码重登」与引入本选项前的行为等价（不碰任何渠道）
  ④ 三条恢复路径都经 _obtain_session，没有人绕过渠道直接 _login：
     _ensure_session / _get_scoped / _travel_bearer
  ⑤ 权威表（sub_token_data.json 的 livis_login_refresh）与 const 常量一致
  ⑥ 选项对用户可见且三语翻译同步（strings.json == zh-Hans.json 字节一致）

★ 为什么行为断言 + AST 断言【两者都要有】（CONTRIBUTING 教训）：

  - 只有行为断言：接线可以被"换一种写法"绕过而不易察觉；
  - 只有 AST/子串断言：注释会替代码背书、桩会掩盖真实缺陷。
  所以 ④ 同时用真实调用（monkeypatch 记录）与 AST 调用节点断言。

★ 变异测试（验收时已执行）：
  - 删掉 _get_scoped 里的 _obtain_session 调用 → 行为与 AST 断言均失败
  - 删掉 config_flow 的 refresh_channel 字段 → AST 断言失败
  - 改掉权威表 aud → 一致性断言失败
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


# ---------------------------------------------------------------------------
# 最小依赖桩 + 隔离加载（沿用 test_charge_readonly 的模式）
# ---------------------------------------------------------------------------

def _install_stubs() -> None:
    """桩掉 homeassistant（li_api import 期需要）与缺失的 requests。"""
    if importlib.util.find_spec("requests") is None:
        # pake_login 顶层 `import requests`；行为测试不触网，桩足够
        sys.modules.setdefault("requests", types.ModuleType("requests"))

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    def _sub(name: str, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    class _Base:
        def __init__(self, *a, **k):
            pass

    _sub("homeassistant.core", HomeAssistant=_Base, callback=lambda f: f)
    _sub("homeassistant.exceptions", HomeAssistantError=Exception)
    for extra in ("homeassistant.helpers", "homeassistant.const",
                  "homeassistant.config_entries"):
        _sub(extra)


def _load(mod_name: str):
    """按包内路径加载 lixiang_auto.<mod_name>（不触发包 __init__）。"""
    spec = importlib.util.spec_from_file_location(
        f"lixiang_auto.{mod_name}", _INTEG / f"{mod_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"lixiang_auto.{mod_name}"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mods():
    _install_stubs()
    if "lixiang_auto" not in sys.modules or not getattr(
            sys.modules["lixiang_auto"], "__path__", None):
        pkg = types.ModuleType("lixiang_auto")
        pkg.__path__ = [str(_INTEG)]
        sys.modules["lixiang_auto"] = pkg
    out = {}
    for name in ("const", "li_api"):
        out[name] = _load(name)
    return out


def _client(li_api, channel):
    # ★ 必须传 device_id：conftest 把集成目录插到了 sys.path[0]，
    #   不传会走 `import secrets` 分支并命中包内的 secrets.py（遮蔽标准库）。
    return li_api.LiApiClient(
        phone="13800138000", password="pw", vin="",
        hac_key="00", key_id="00", xdev="00", app_token="APP-x",
        device_id="dev00", refresh_token="rt-1", refresh_channel=channel,
    )


# ---------------------------------------------------------------------------
# ① 渠道序列映射
# ---------------------------------------------------------------------------

class TestChannelSteps:
    @pytest.mark.parametrize("channel,want", [
        ("auto", ["primary", "livis"]),
        ("primary", ["primary"]),
        ("livis", ["livis"]),
        ("password", []),
        (None, ["primary", "livis"]),          # None → 默认 auto
        (lambda: "primary", ["primary"]),      # callable 注入（__init__ 的用法）
    ], ids=lambda v: v if isinstance(v, str) else type(v).__name__)
    def test_steps(self, mods, channel, want):
        got = _client(mods["li_api"], channel)._channel_steps()
        assert got == want

    def test_broken_provider_falls_back_to_default(self, mods):
        def boom():
            raise RuntimeError("options read failed")
        got = _client(mods["li_api"], boom)._channel_steps()
        assert got == ["primary", "livis"]

    def test_labels_cover_all_channels(self, mods):
        const = mods["const"]
        assert set(const.REFRESH_CHANNEL_LABELS) == {
            "auto", "primary", "livis", "password"}
        assert const.DEFAULT_REFRESH_CHANNEL == "auto"
        # 序列里只允许出现 4 个渠道名（密码兜底不在序列内）
        for ch in const.REFRESH_CHANNEL_LABELS:
            steps = _client(mods["li_api"], ch)._channel_steps()
            assert set(steps) <= {"primary", "livis"}


# ---------------------------------------------------------------------------
# ②③ 回退顺序 / 探测硬门槛 / 仅密码等价
# ---------------------------------------------------------------------------

class TestFallbackOrder:
    def test_auto_falls_back_primary_livis_login(self, mods):
        c = _client(mods["li_api"], "auto")
        calls: list[str] = []

        def fail_primary():
            calls.append("primary")
            raise RuntimeError("primary fail")

        def fail_livis():
            calls.append("livis")
            raise RuntimeError("livis fail")

        c._attempt_primary = fail_primary
        c._attempt_livis = fail_livis
        c._probe_session = lambda: calls.append("probe")
        c._login = lambda: (calls.append("login"), setattr(c, "_cli", object()))
        c._obtain_session()
        assert calls == ["primary", "livis", "login"]

    def test_probe_success_short_circuits(self, mods):
        c = _client(mods["li_api"], "auto")
        calls: list[str] = []

        def ok_primary():
            calls.append("primary")
            c._cli = object()

        c._attempt_primary = ok_primary
        c._attempt_livis = lambda: calls.append("livis")
        c._probe_session = lambda: calls.append("probe")
        c._login = lambda: calls.append("login")
        c._obtain_session()
        assert calls == ["primary", "probe"]   # 未走到 livis / login

    def test_probe_is_hard_gate(self, mods):
        """渠道受理但探测失败 → 不算成功，必须继续回退。"""
        c = _client(mods["li_api"], "auto")
        calls: list[str] = []

        def primary_ok():
            calls.append("primary")
            c._cli = object()

        def probe_fail():
            calls.append("probe")
            raise RuntimeError("session still dead")

        c._attempt_primary = primary_ok
        c._attempt_livis = lambda: calls.append("livis")
        c._probe_session = probe_fail
        c._login = lambda: (calls.append("login"), setattr(c, "_cli", object()))
        c._obtain_session()
        assert calls == ["primary", "probe", "livis", "probe", "login"]

    def test_password_only_equals_original_behaviour(self, mods):
        """仅密码重登：不碰任何渠道，直接 _login（= 引入本选项前的行为）。"""
        c = _client(mods["li_api"], "password")
        calls: list[str] = []
        c._attempt_primary = lambda: calls.append("primary")
        c._attempt_livis = lambda: calls.append("livis")
        c._probe_session = lambda: calls.append("probe")
        c._login = lambda: (calls.append("login"), setattr(c, "_cli", object()))
        c._obtain_session()
        assert calls == ["login"]

    def test_obtain_without_password_raises(self, mods):
        c = _client(mods["li_api"], "auto")
        c._password = ""
        c._refresh_token = ""
        c._attempt_primary = lambda: (_ for _ in ()).throw(RuntimeError("x"))
        c._attempt_livis = lambda: (_ for _ in ()).throw(RuntimeError("y"))
        with pytest.raises(mods["li_api"].LiApiError, match="密码"):
            c._obtain_session()


# ---------------------------------------------------------------------------
# ④ 接线：行为断言（真实调用记录）
# ---------------------------------------------------------------------------

class TestWiringBehaviour:
    def test_ensure_session_routes_through_obtain(self, mods):
        c = _client(mods["li_api"], "auto")
        assert c._cli is None
        calls: list[str] = []

        def fake_obtain():
            calls.append("obtain")
            c._cli = object()

        c._obtain_session = fake_obtain
        cli = c._ensure_session()
        assert calls == ["obtain"]
        assert cli is c._cli

    def test_get_scoped_recovery_routes_through_obtain(self, mods):
        c = _client(mods["li_api"], "auto")
        calls: list[str] = []
        attempts = {"n": 0}

        def fake_exchange(scope, audience):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise mods["li_api"].LiApiError("session dead")
            return "tok-ok"

        def fake_obtain():
            calls.append("obtain")

        c._exchange = fake_exchange
        c._obtain_session = fake_obtain
        c._login = lambda: (_ for _ in ()).throw(
            AssertionError("恢复路径不得绕过 _obtain_session 直接 _login"))
        tok = c._get_scoped("vss", "vss:get-batch", "aud")
        assert tok == "tok-ok"
        assert calls == ["obtain"]

    def test_get_scoped_without_credentials_raises_original_error(self, mods):
        c = _client(mods["li_api"], "auto")
        c._password = ""
        c._refresh_token = ""

        def boom(scope, audience):
            raise mods["li_api"].LiApiError("boom-original")

        c._exchange = boom
        with pytest.raises(mods["li_api"].LiApiError, match="boom-original"):
            c._get_scoped("vss", "vss:get-batch", "aud")

    def test_travel_bearer_routes_through_obtain(self, mods):
        """100105 强制换 Bearer 的路径也必须走渠道序列。"""
        c = _client(mods["li_api"], "auto")
        c._main_bearer = "stale"
        calls: list[str] = []

        def fake_obtain():
            calls.append("obtain")
            c._main_bearer = "fresh"

        c._obtain_session = fake_obtain
        c._login = lambda: (_ for _ in ()).throw(
            AssertionError("_travel_bearer 不得绕过渠道直接 _login"))
        bearer = c._travel_bearer(force_login=True)
        assert calls == ["obtain"]
        assert bearer == "fresh"


# ---------------------------------------------------------------------------
# ④ 接线：AST 断言（桩测不到的"调用真的存在"）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def li_api_tree():
    return ast.parse((_INTEG / "li_api.py").read_text(encoding="utf-8"))


def _func(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name == name:
                    return sub
    raise AssertionError(f"未找到函数 {name}")


def _calls_named(node: ast.AST, method: str) -> list[ast.Call]:
    return [
        n for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == method
    ]


class TestWiringAst:
    @pytest.mark.parametrize("func_name", [
        "_ensure_session", "_get_scoped", "_travel_bearer",
    ])
    def test_recovery_paths_call_obtain_session(self, li_api_tree, func_name):
        fn = _func(li_api_tree, func_name)
        assert _calls_named(fn, "_obtain_session"), (
            f"{func_name} 必须经 _obtain_session（渠道序列入口）")

    def test_travel_bearer_does_not_call_login_directly(self, li_api_tree):
        fn = _func(li_api_tree, "_travel_bearer")
        assert not _calls_named(fn, "_login"), (
            "_travel_bearer 直接调 _login = 绕过渠道")

    def test_obtain_session_probes(self, li_api_tree):
        fn = _func(li_api_tree, "_obtain_session")
        assert _calls_named(fn, "_probe_session"), (
            "_obtain_session 必须在渠道尝试后探测（硬门槛）")

    def test_get_scoped_recovery_guard_kept(self, li_api_tree):
        """无密码且无 refresh_token 时必须直接抛出（不静默吞错）。"""
        fn = _func(li_api_tree, "_get_scoped")
        src = ast.unparse(fn)
        assert "_refresh_token" in src and "_obtain_session" in src

    def test_init_injects_refresh_channel(self):
        tree = ast.parse((_INTEG / "__init__.py").read_text(encoding="utf-8"))
        kws = [
            kw.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "LiApiClient"
            for kw in node.keywords
        ]
        assert "refresh_channel" in kws, (
            "__init__ 必须把 refresh_channel 注入 LiApiClient")

    def test_config_flow_exposes_option(self):
        tree = ast.parse((_INTEG / "config_flow.py").read_text(encoding="utf-8"))
        fn = _func(tree, "async_step_init")
        required_args = [
            ast.unparse(node.args[0])
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Required"
            and node.args
        ]
        assert "CONF_REFRESH_CHANNEL" in required_args, (
            "选项表单必须包含 CONF_REFRESH_CHANNEL")


# ---------------------------------------------------------------------------
# ⑤ 权威表与 const 一致性
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def livis_entry():
    data = json.loads(
        (_INTEG / "app_config/sub_token_data.json").read_text(encoding="utf-8"))
    return data["tokens"]["livis_login_refresh"]


class TestAuthoritativeTable:
    def test_entry_fields_match_app_config(self, livis_entry):
        """逐字段对齐理想同学 APK assets/m01config.json 的原始条目。"""
        entry = livis_entry
        assert entry["audience"] == "5KLfKAqTUjRFNVjPVAWpKJ"
        assert entry["scope"] == ["login"]
        assert entry["client"] == ""
        assert entry["disableIAM"] == 1
        assert entry["responseType"] == ["token"]
        assert entry["urls"] == [
            "https://app.lixiang.com/login/subidaas/livis/login/refresh"]

    def test_const_matches_entry(self, mods, livis_entry):
        const = mods["const"]
        assert const.AUD_LIVIS_LOGIN_REFRESH == livis_entry["audience"]
        assert const.SCOPE_LIVIS_LOGIN_REFRESH == livis_entry["scope"][0]
        assert const.URL_LIVIS_LOGIN_REFRESH == livis_entry["urls"][0]

    def test_table_documented_source(self):
        data = json.loads(
            (_INTEG / "app_config/sub_token_data.json").read_text(encoding="utf-8"))
        assert "livis_login_refresh" in data.get("_extra", ""), (
            "_extra 必须注明该条目来自理想同学 APK")


# ---------------------------------------------------------------------------
# ⑥ 用户可见性与翻译同步
# ---------------------------------------------------------------------------

class TestUserFacingTranslations:
    def test_strings_and_zh_hans_byte_identical(self):
        s = (_INTEG / "strings.json").read_bytes()
        z = (_INTEG / "translations/zh-Hans.json").read_bytes()
        assert s == z, "CI 要求 strings.json 与 zh-Hans.json 同步（cp 即可）"

    @pytest.mark.parametrize("rel", [
        "strings.json", "translations/zh-Hans.json", "translations/en.json",
    ])
    def test_option_label_present(self, rel):
        data = json.loads((_INTEG / rel).read_text(encoding="utf-8"))
        field = data["options"]["step"]["init"]["data"]
        assert "refresh_channel" in field, f"{rel} 缺 refresh_channel 标签"

    def test_option_description_mentions_fallback(self):
        data = json.loads((_INTEG / "strings.json").read_text(encoding="utf-8"))
        desc = data["options"]["step"]["init"]["description"]
        assert "刷新渠道" in desc and "回退" in desc
