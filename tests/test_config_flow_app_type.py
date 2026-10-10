"""config_flow 登录身份选择 + 「去 iPad 化」源码级守卫（2026-10-10）

项目惯例：config_flow 依赖 homeassistant，测试只读源码文本（不 import）。

锁定：
  1. 登录表单含「理想汽车/理想同学」二选一下拉（默认理想汽车）
  2. _finish_login 用登录 device_id 作 xdev + keySuite 派生 + 失败 abort
  3. 代码中 iPad 四件套残留为零（DEFAULT_HAC_KEY/KEY_ID/XDEV 及字面量）
"""

from __future__ import annotations

from pathlib import Path

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (_INTEG / name).read_text(encoding="utf-8")


class TestAppTypeSelector:
    """登录表单身份二选一。"""

    @staticmethod
    def _schema_block() -> str:
        s = _src("config_flow.py")
        i = s.find("PASSWORD_SCHEMA = vol.Schema")
        assert i > 0, "未找到 PASSWORD_SCHEMA"
        return s[i:i + 1600]

    def test_schema_has_app_type(self):
        blk = self._schema_block()
        assert "CONF_APP_TYPE" in blk, "登录表单缺少身份选择字段"
        assert "default=APP_LIXIANG" in blk, "默认必须是理想汽车（保持现状）"

    def test_schema_has_both_options(self):
        blk = self._schema_block()
        assert "APP_LIXIANG" in blk and "APP_LIVIS" in blk
        assert "SelectSelector" in blk, "身份选择应使用下拉 selector"

    def test_pending_carries_app_type(self):
        s = _src("config_flow.py")
        assert '"app_type": user_input.get(CONF_APP_TYPE)' in s, (
            "_pending 必须携带 app_type（供浏览器/SMS 后续步骤使用）")

    def test_finish_login_sets_app_type(self):
        s = _src("config_flow.py")
        i = s.find("async def _finish_login")
        assert i > 0
        blk = s[i:i + 6000]
        assert "data[CONF_APP_TYPE]" in blk, "_finish_login 必须写入 app_type"


class TestDeriveInsteadOfBuiltin:
    """_finish_login：xdev = 登录 device_id + keySuite 派生 + abort 文案。"""

    @staticmethod
    def _blk() -> str:
        s = _src("config_flow.py")
        i = s.find("async def _finish_login")
        return s[i:i + 6000]

    def test_xdev_is_login_device_id(self):
        blk = self._blk()
        assert "data[CONF_XDEV] = data.get(CONF_DEVICE_ID)" in blk, (
            "新条目 xdev 必须用登录 device_id（V4c 实测定案）")

    def test_derive_identity_called(self):
        blk = self._blk()
        assert "derive_identity" in blk, "必须走 keySuite 派生"
        assert "functools.partial" in blk, "executor 调用需 functools.partial"
        assert "async_add_executor_job" in blk, "派生必须在 executor 中执行"

    def test_abort_on_derive_failure(self):
        blk = self._blk()
        assert 'reason="identity_derive_failed"' in blk, (
            "派生失败必须 abort（不静默回退）")

    def test_app_token_default_kept(self):
        blk = self._blk()
        assert "DEFAULT_APP_TOKEN" in blk, (
            "APP token 是唯一保留的内置常量（V2 实测不绑设备）")

    def test_reauth_preserves_app_type(self):
        s = _src("config_flow.py")
        i = s.find("async_step_reauth_confirm")
        assert i > 0
        blk = s[i:i + 4000]
        assert "CONF_APP_TYPE" in blk, "reauth 必须保留 app_type"


class TestNoIpadResidue:
    """★ 验收标准 3/4：iPad 四件套在代码中零残留。"""

    REMOVED_PREFIXES = (
        "13BFCE38",      # DEFAULT_XDEV 字面量
        "2020a7738b35",  # DEFAULT_HAC_KEY 字面量
        "22004e67c0f7",  # DEFAULT_KEY_ID 字面量
    )

    def test_no_removed_literals_in_integration(self):
        for path in sorted(_INTEG.rglob("*")):
            if path.suffix.lower() not in (".py", ".json", ".yaml"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for bad in self.REMOVED_PREFIXES:
                assert bad.lower() not in text.lower(), (
                    f"{path.name} 残留 iPad 身份字面量 {bad}")

    def test_no_default_identity_constants(self):
        for name in ("DEFAULT_HAC_KEY", "DEFAULT_KEY_ID", "DEFAULT_XDEV"):
            for fname in ("const.py", "secrets.py", "__init__.py",
                          "config_flow.py", "li_api.py", "auth.py"):
                assert name not in _src(fname), (
                    f"{fname} 仍引用已删除的 {name}")

    def test_auth_py_no_hardcoded_device(self):
        """auth.py 的字面量设备号回退必须删除。"""
        assert "13BFCE" not in _src("auth.py")

    def test_app_type_plumbed_to_client(self):
        s = _src("__init__.py")
        assert "CONF_APP_TYPE" in s and "app_type=app_type" in s, (
            "__init__ 必须把 app_type 传给 LiApiClient")
        s2 = _src("li_api.py")
        assert "app_type: str = APP_LIXIANG" in s2, (
            "LiApiClient 缺少 app_type 参数")


class TestLivisLoginClient:
    """★ 2026-10-10 追加逆向：理想同学独立 OAuth client 参数化。

    静态来源（理想同学 APK smali）+ V5/V6 实测：
      client_id = 40amUDKOdqQTaGDONZC1oY
      scope     = iam:client:type:lisa
      redirect  = https://account.lixiang.com/app-auth/livis
    """

    def test_pake_login_has_livis_params(self):
        s = _src("pake_login.py")
        assert 'LIVIS_LOGIN_CLIENT_ID = "40amUDKOdqQTaGDONZC1oY"' in s, (
            "pake_login 缺少理想同学 client_id（smali ApiConfig.smali:37）")
        assert 'LIVIS_LOGIN_SCOPE = "iam:client:type:lisa"' in s
        assert "APP_LOGIN_PARAMS" in s
        assert '"livis": (LIVIS_LOGIN_CLIENT_ID' in s

    def test_login_client_takes_app_type(self):
        s = _src("pake_login.py")
        i = s.find("class LixiangDirectLogin")
        assert i > 0
        blk = s[i:i + 1200]
        assert "app_type" in blk, "LixiangDirectLogin 必须接受 app_type"
        assert "APP_LOGIN_PARAMS" in blk, "必须按 app_type 取登录参数"

    def test_login_flow_uses_instance_params(self):
        """login()/refresh() 中 client_id/scope/redirect 必须用实例属性。"""
        s = _src("pake_login.py")
        i = s.find("def login(self")
        j = s.find("def _query_param")
        blk = s[i:j]
        assert "self.client_id" in blk, "login() 必须用 self.client_id"
        assert "self.redirect_uri" in blk
        assert "self.login_scope" in blk
        # 模块级常量不得再出现在登录流程体中（定义处除外）
        assert '"client_id": CLIENT_ID' not in blk
        assert '"redirect_uri": REDIRECT_URI' not in blk

    def test_do_direct_login_passes_app_type(self):
        s = _src("config_flow.py")
        i = s.find("def _do_direct_login")
        blk = s[i:i + 900]
        assert "app_type" in blk and "app_type=app_type" in blk, (
            "_do_direct_login 必须把 app_type 传给 LixiangDirectLogin")
        # 三个调用点都必须传 app_type
        assert s.count("_do_direct_login, phone") >= 3, (
            "password_login/browser/reauth 三处调用点都要传 app_type")

    def test_li_api_exchanges_with_app_type_params(self):
        s = _src("li_api.py")
        assert "APP_LOGIN_PARAMS" in s, "_exchange 必须按 app_type 取 client 参数"
        assert "app_type=self._app_type" in s, (
            "_login 构造 LixiangDirectLogin 必须传 app_type")

    def test_auth_web_session_carries_app_type(self):
        s = _src("auth_web.py")
        assert "app_type" in s, "create_session/try_login 必须参数化 app_type"
        assert '"app_type": app_type' in s, "会话需持久化 app_type（辅助页链接用）"

    def test_const_old_livis_constants_removed(self):
        """旧「设备码侧门」常量与新逆向结论冲突且无调用方 → 必须删除。"""
        s = _src("const.py")
        for name in ("LIVIS_CLIENT_ID", "LIVIS_AUDIENCE", "LIVIS_SCOPE"):
            assert f"{name} =" not in s, f"const.py 残留旧常量 {name}"
        # 冲突字面量全仓清零
        for path in sorted(_INTEG.rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "6qxd1MLZhAtdWipnmXe1dd" not in text, (
                f"{path.name} 残留旧 livis client 字面量")

    def test_trust_link_fixed_to_main_app(self):
        """★ 2026-10-10：信任链接固定主 App 参数。

        背景：链接唯一用途是建立 device_id 信任（信任按 device_id 全局
        生效，与 client 无关）。按 app_type 切 livis 参数会跳到理想同学
        「绑定特斯拉」页 → 无法完成信任建立。
        """
        s = _src("config_flow.py")
        i = s.find("def _browser_ph")
        assert i > 0
        blk = s[i:i + 3500]
        assert 'APP_LOGIN_PARAMS["lixiang"]' in blk, (
            "_browser_ph 必须固定主 App 信任参数")
        assert "APP_LOGIN_PARAMS.get(app_type" not in blk, (
            "_browser_ph 不得按 app_type 切参（livis H5 跳特斯拉绑定页）")
        # 调用点不再传 app_type
        assert "_browser_ph(tok, device_id, app_type)" not in s

        # auth_web 辅助页同规则
        s2 = _src("auth_web.py")
        assert 'APP_LOGIN_PARAMS["lixiang"]' in s2, (
            "auth_web 辅助页信任链接必须固定主 App 参数")
        assert "APP_LOGIN_PARAMS.get(s.get(" not in s2

    def test_browser_poll_fast_probing(self):
        """信任检测轮询前密后疏（原固定 5 秒盲等）。"""
        s = _src("config_flow.py")
        assert "_RETRY_GAPS = [1, 2, 3, 5, 5, 8, 10]" in s, (
            "轮询应为快探测序列（信任同步 1~3 秒生效）")
