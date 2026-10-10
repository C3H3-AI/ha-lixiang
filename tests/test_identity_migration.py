"""签名身份迁移 / 签名错误自愈 的回归测试（2026-10-10）。

背景（两个真实缺陷）
--------------------
① **老条目永远用「内置抓包身份」**
   v1.4.7 之前建条目时，config_flow 会把内置的 `DEFAULT_HAC_KEY/KEY_ID/XDEV`
   写进 `entry.data`；这些常量被删除后（去 iPad 化），运行期只从 entry 读，
   而 `derive_identity` 只在「添加集成」时发生、重新认证又会沿用旧值、
   没有任何迁移代码 → 老用户会**永远**用那套「所有人共用」的 iPad 身份
   （服务端一失效就是这批用户一起挂），唯一出路是删条目重加。

② **「重新认证」看着成功却没修好**
   它只做 PAKE 登录，然后沿用旧的 `hac_key/key_id`。签名身份失效时，
   用户看到「成功」但功能照旧全挂 —— 最糟的失败形态。

测试环境没有 `homeassistant`，所以这里用仓库既有范式：
**用 AST 抽出真实方法 + 注入假依赖**来跑真实代码。
"""
from __future__ import annotations

import ast
import json
import logging
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"


class _LiApiError(Exception):
    pass


# ── 载入 li_api 的真实方法（不 import homeassistant）─────────────────────────
_IDENTITY_METHODS = (
    "_identity_needs_migration",
    "_migrate_identity_if_needed",
    "_recover_signature_error",
    "_notify_token_update",
    "_login",
)


def _load_li_api(derive_impl):
    """返回一个带真实迁移/自愈方法的假 LiApiClient 类。

    derive_impl(xdev, bearer) 之外，测试还会 `verify` derive 的入参，
    所以这里把 app_type 一起透传：fake 形如 derive_identity(app_type, xdev, bearer)。
    """
    src = (CC / "li_api.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    nodes, consts = [], {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name in _IDENTITY_METHODS:
                    nodes.append(sub)
                elif isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Name) and t.id == "SIG_RECOVER_COOLDOWN":
                            consts[t.id] = ast.literal_eval(sub.value)
    assert nodes, "未从 li_api.py 抽到迁移相关方法"

    class _FakeLogin:
        """假 PAKE 登录：固定返回新鲜 Bearer（模拟登录成功）。"""

        def __init__(self, device_id=None, debug=False, app_type=None):
            self.device_id = device_id
            self.app_type = app_type
            self.logins = 0

        def login(self, phone, password):
            self.logins += 1
            return {"access_token": "APP-fresh", "refresh_token": "rt-fresh"}

    # 假 key_suite，让方法里的 `from .key_suite import derive_identity` 生效
    pkg = types.ModuleType("lx_li")
    pkg.__path__ = []
    ks = types.ModuleType("lx_li.key_suite")
    ks.derive_identity = lambda app_type, xdev, bearer, timeout=20: derive_impl(
        app_type, xdev, bearer)
    pkg.key_suite = ks
    sys.modules["lx_li"] = pkg
    sys.modules["lx_li.key_suite"] = ks

    ns = {
        "__name__": "lx_li", "__package__": "lx_li",
        "_LOGGER": logging.getLogger("lixiang_auto_identity_test"),
        "time": time, "json": json,
        "CONF_HAC_KEY": "hac_key",
        "CONF_KEY_ID": "key_id",
        "CONF_XDEV": "x_chj_deviceid",
        "CONF_IDENTITY_SOURCE": "identity_source",
        "IDENTITY_SOURCE_DERIVED": "derived",
        "IDENTITY_SOURCE_MANUAL": "manual",
        "LiApiError": _LiApiError,
        "LixiangDirectLogin": _FakeLogin,
        "_hac_key_bytes": lambda v: (v if isinstance(v, bytes)
                                     else bytes.fromhex(str(v))),
    }
    for node in nodes:
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     f"<li_api.{node.name}>", "exec"), ns)

    cls = type("FakeLiApiClient", (),
               {n.name: ns[n.name] for n in nodes})
    for k, v in consts.items():
        setattr(cls, k, v)
    return cls


def _client(cls, **kw):
    c = cls()
    c._identity_source = kw.get("identity_source", "")      # 默认=老条目
    c._main_bearer = kw.get("bearer", "")
    c._device_id = kw.get("device_id", "dev-new-1234")
    c._xdev = kw.get("xdev", "DEVICE-OF-THE-IPAD")
    c._hac = b"old-hac-bytes"
    c._key_id = "OLD-KEY-ID"
    c._app_type = kw.get("app_type", "lixiang")
    c._phone = "13800000000"
    c._password = kw.get("password", "pw")
    c._refresh_token = "rt-old"
    c._cli = object()                    # 已有会话
    c._tokens = {"vss": ("tok", 0.0)}
    c._sig_recover_ts = 0.0
    c._identity_dirty = False
    c.patches = []
    c._on_token_update = c.patches.append
    return c


# ── ① 签名错误判定 ──────────────────────────────────────────────────────────
def _load_signature_error_fn():
    src = (CC / "li_api.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "is_signature_error")
    ns = {"__name__": "lx_li", "json": json}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<x>", "exec"), ns)
    return ns["is_signature_error"]


class TestSignatureErrorDetection:
    def test_detects_both_shapes(self):
        """★ 两种形态都要认：异常文本（非 2xx）与 body 里的业务码（200）。"""
        fn = _load_signature_error_fn()
        # HTTP 非 2xx 抛出的异常文本
        assert fn(_LiApiError("POST /x: HTTP 403 {\"code\":100005}"))
        # HTTP 200 但 body 是业务码（不会抛异常，调用方只拿到空 items）
        assert fn({"code": 100005, "message": "签名错误"})
        assert fn({"code": "100005"})
        assert fn({"message": "请求签名错误"})

    def test_ignores_unrelated_errors(self):
        fn = _load_signature_error_fn()
        assert not fn({"code": 0, "data": []})
        assert not fn(_LiApiError("HTTP 401 240225 账号登录已过期"))
        assert not fn({"code": 100105, "message": "用户未登录"})


# ── ② 身份迁移（老条目 → 本设备派生身份）────────────────────────────────────
class TestIdentityMigration:
    @staticmethod
    def _mk(derive_impl=None, **kw):
        calls = []

        def default_derive(app_type, xdev, bearer):
            calls.append((app_type, xdev, bearer))
            return ("ab" * 32, "NEW-KEY-ID")

        cls = _load_li_api(derive_impl or default_derive)
        c = _client(cls, **kw)
        c.derive_calls = calls
        return c

    def test_legacy_entry_migrates_on_login(self):
        """★ 核心：标记缺失（老条目）+ 登录成功 → 迁移成本设备派生身份。"""
        c = self._mk(bearer="APP-fresh", device_id="dev-new-1234")
        assert c._identity_needs_migration() is True
        assert c._migrate_identity_if_needed("login") is True

        # ① 身份换成派生值
        assert c._key_id == "NEW-KEY-ID"
        assert c._hac == bytes.fromhex("ab" * 32)
        # ② xdev 与登录设备对齐（v1.4.7 规则：PAKE/签名/exchange 三者一致）
        assert c._xdev == "dev-new-1234"
        # ③ 来源标记置为 derived（下次不再迁移，也不重复请求）
        assert c._identity_source == "derived"
        # ④ derive 用了新鲜的 Bearer 与登录设备号
        assert c.derive_calls == [("lixiang", "dev-new-1234", "APP-fresh")]
        # ⑤ scope token 缓存清空（旧身份换来的 token 不能再用）
        assert c._tokens == {}

    def test_migration_persists_identity_to_entry(self):
        """迁移必须回写 entry（否则重启又变回旧身份）。"""
        c = self._mk(bearer="APP-fresh")
        c._migrate_identity_if_needed("login")
        assert c.patches, "未触发回写回调"
        patch = c.patches[-1]
        assert patch["hac_key"] == "ab" * 32
        assert patch["key_id"] == "NEW-KEY-ID"
        assert patch["x_chj_deviceid"] == "dev-new-1234"
        assert patch["identity_source"] == "derived"

    def test_already_derived_entry_does_not_migrate(self):
        """已派生条目：不重复请求（每次登录都派生会造成无谓的 keySuite 调用）。"""
        c = self._mk(identity_source="derived", bearer="APP-fresh")
        assert c._identity_needs_migration() is False
        assert c._migrate_identity_if_needed("login") is False
        assert c.derive_calls == []
        assert c.patches == []
        assert c._key_id == "OLD-KEY-ID"

    def test_manual_entry_does_not_migrate(self):
        """手动流程用户自填四件套 → 尊重用户选择，不动。"""
        c = self._mk(identity_source="manual", bearer="APP-fresh")
        assert c._identity_needs_migration() is False
        assert c._migrate_identity_if_needed("login") is False
        assert c.derive_calls == []
        assert c._hac == b"old-hac-bytes"

    def test_derive_failure_keeps_old_identity(self):
        """★★ 派生失败绝不破坏现状：保留旧身份、不写回、不置标记。"""

        def boom(app_type, xdev, bearer):
            raise RuntimeError("keySuite HTTP 500")

        c = self._mk(derive_impl=boom, bearer="APP-fresh")
        assert c._migrate_identity_if_needed("login") is False
        assert c._key_id == "OLD-KEY-ID"          # 旧身份保留
        assert c._hac == b"old-hac-bytes"
        assert c._identity_source == ""            # 标记未置 → 下次登录重试
        assert c.patches == []                     # 没有回写
        assert c._tokens != {}                     # 缓存未被破坏

    def test_skips_without_bearer_or_device(self):
        """缺 Bearer / 设备号 → 明确跳过（keySuite 需要有效 Bearer）。"""
        c1 = self._mk(bearer="")
        assert c1._migrate_identity_if_needed("login") is False
        assert c1.derive_calls == []

        c2 = self._mk(bearer="APP-fresh", device_id="")
        c2._xdev = ""
        assert c2._migrate_identity_if_needed("login") is False
        assert c2.derive_calls == []

    def test_login_triggers_migration_end_to_end(self):
        """真实 `_login()` 跑通：登录成功后自动迁移（老条目场景）。"""
        c = self._mk(bearer="", device_id="dev-e2e")
        assert c._main_bearer == ""
        c._login()
        assert c._main_bearer == "APP-fresh"
        assert c._identity_source == "derived"
        assert c._key_id == "NEW-KEY-ID"
        assert c.derive_calls == [("lixiang", "dev-e2e", "APP-fresh")]


# ── ③ 签名错误自愈（带冷却，防重登风暴）─────────────────────────────────────
class TestSignatureRecovery:
    def test_recovers_by_migrating_legacy_identity(self):
        calls = []

        def derive(app_type, xdev, bearer):
            calls.append(xdev)
            return ("cd" * 32, "FIXED-KEY")

        cls = _load_li_api(derive)
        c = _client(cls, bearer="APP-fresh", device_id="dev-1")
        assert c._recover_signature_error() is True
        assert c._key_id == "FIXED-KEY"

    def test_throttled_after_first_attempt(self):
        """★★ 冷却：同一客户端短时间内只自愈一次。

        历史教训：无守卫的重登/重试会变成每分钟风暴（实测 87 次/1.5h）。
        """
        calls = []

        def derive(app_type, xdev, bearer):
            calls.append(1)
            return ("cd" * 32, "FIXED-KEY")

        cls = _load_li_api(derive)
        c = _client(cls, bearer="APP-fresh")
        assert c._recover_signature_error() is True
        # 第二次（冷却期内）：直接放弃，不再触发任何派生/重登
        assert c._recover_signature_error() is False
        assert len(calls) == 1

    def test_falls_back_to_relogin_when_nothing_to_migrate(self):
        """身份已是派生值（标记 derived）→ 自愈走「重登」而不是迁移。"""
        cls = _load_li_api(lambda a, x, b: ("ee" * 32, "K"))
        c = _client(cls, identity_source="derived", bearer="")
        c._password = "pw"
        relogins = []

        def fake_login():
            relogins.append(1)

        c._login = fake_login
        assert c._recover_signature_error() is True
        assert relogins == [1]

    def test_no_password_no_recovery(self):
        """既无可迁移身份、又没有密码（仅静态信息条目）→ 不假装成功。"""
        cls = _load_li_api(lambda a, x, b: ("ee" * 32, "K"))
        c = _client(cls, identity_source="derived", bearer="")
        c._password = ""
        assert c._recover_signature_error() is False


# ── ④ 签名器身份热更新（迁移后必须立即生效）────────────────────────────────
def _load_signer():
    pkg = types.ModuleType("lx_sig")
    pkg.__path__ = [str(CC)]
    sys.modules["lx_sig"] = pkg
    for name in ("const", "signer"):
        mod = types.ModuleType(f"lx_sig.{name}")
        mod.__package__ = "lx_sig"
        sys.modules[f"lx_sig.{name}"] = mod
        exec(compile((CC / f"{name}.py").read_text(encoding="utf-8"),
                     f"<{name}>", "exec"), mod.__dict__)
    return sys.modules["lx_sig.signer"].LiCarSigner


class TestSignerIdentityUpdate:
    def test_update_identity_changes_headers_and_signature(self):
        """★ 迁移后签名器必须换身份，否则 coordinator 的 client.update()
        会继续用旧的（抓包）身份签名。"""
        Signer = _load_signer()
        s = Signer(hac_key="0" * 64, key_id="OLD-KID", device_id="OLD-DEV")
        before = s.build_headers("POST", "")
        assert before["X-CHJ-Key"] == "OLD-KID"
        assert before["X-CHJ-Deviceid"] == "OLD-DEV"

        s.update_identity("f" * 64, "NEW-KID", "NEW-DEV")
        after = s.build_headers("POST", "")
        assert after["X-CHJ-Key"] == "NEW-KID"
        assert after["X-CHJ-Deviceid"] == "NEW-DEV"
        assert after["X-CHJ-Sign"] != before["X-CHJ-Sign"], "签名未随身份变化"


# ── ⑤ 接线守卫（源码级：确保三条路径都接上了）──────────────────────────────
def _src(name: str) -> str:
    return (CC / name).read_text(encoding="utf-8")


def _method_src(src: str, cls_name: str, fn_name: str) -> str:
    """取某个类方法的源码。

    ★ 必须同时认 FunctionDef 与 AsyncFunctionDef —— config_flow 里这几个
      都是 `async def`，只认前者会导致测试「找不到方法」而非真正失败。
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and sub.name == fn_name):
                    return ast.get_source_segment(src, sub) or ""
    raise AssertionError(f"找不到 {cls_name}.{fn_name}")


class TestWiring:
    def test_finish_login_marks_identity_source(self):
        src = _src("config_flow.py")
        body = _method_src(src, "LiCarConfigFlow", "_finish_login")
        assert "data[CONF_IDENTITY_SOURCE] = IDENTITY_SOURCE_DERIVED" in body, (
            "添加集成时未标记身份来源 → 新条目会被当成老条目重复迁移")

    def test_manual_flow_marks_manual(self):
        src = _src("config_flow.py")
        body = _method_src(src, "LiCarConfigFlow", "async_step_manual")
        assert "IDENTITY_SOURCE_MANUAL" in body, "手动流程未标记 manual"

    def test_reauth_rederives_identity(self):
        """★ 重新认证必须重派生 —— 否则「成功」了但功能照旧全挂。"""
        src = _src("config_flow.py")
        body = _method_src(src, "LiCarConfigFlow", "async_step_reauth_confirm")
        assert "_rederive_identity(data, src)" in body
        assert "src != IDENTITY_SOURCE_MANUAL" in body, (
            "重新认证未排除 manual 条目（会覆盖用户自填身份）")

    def test_reauth_helper_never_bricks_entry_on_failure(self):
        """★ 派生失败只告警 + 保留旧值：不得把能用的条目改成无凭据状态。

        （本方法现被 reauth 与 reconfigure 共用；reconfigure 会额外要求 True，
          见 tests/test_reconfigure_flow.py。）
        """
        src = _src("config_flow.py")
        body = _method_src(src, "LiCarConfigFlow", "_rederive_identity")
        exc_i = body.find("except Exception as err")
        assert exc_i > 0, "未捕获派生异常"
        after_exc = body[exc_i:]
        assert "保留原身份" in after_exc, "失败分支未说明保留原身份"
        # except 分支里不得写 data[...]（写就意味着覆盖旧身份）
        head = after_exc.split("return")[0]
        assert "data[CONF_HAC_KEY] = " not in head
        # 成功赋值必须在 except 块之后
        assert body.find("data[CONF_HAC_KEY] = hac_key") > exc_i

    def test_init_passes_identity_source(self):
        src = _src("__init__.py")
        assert "identity_source=entry.data.get(CONF_IDENTITY_SOURCE)" in src, (
            "未把身份来源标记传给 LiApiClient → 运行期无法判断是否迁移")

    def test_apply_patch_really_calls_signer_update_identity(self):
        """★ 用 AST 只认真实调用节点。

        为什么不用 `"signer.update_identity(" in src`：那是子串断言，
        注释里出现同样文字、或把调用改名成 `x.update_identity(` 都能骗过它
        （本文件初版就踩过：变异体 `pass or signer.update_identity(` 仍绿）。
        """
        tree = ast.parse(_src("__init__.py"))
        target = None
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "_apply_patch"):
                target = node
        assert target is not None, "找不到 _apply_patch（身份回写入口）"

        calls = [
            n for n in ast.walk(target)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "update_identity"
        ]
        assert calls, (
            "身份回写到 entry 时没有真正调用 signer.update_identity() → "
            "coordinator 的 client.update() 会继续用旧身份签名")
        # 必须挂在 signer 上（不能是别处对象的同名方法）
        assert any(isinstance(c.func.value, ast.Name)
                   and c.func.value.id == "signer" for c in calls), (
            "update_identity 必须调用在 signer 上")
