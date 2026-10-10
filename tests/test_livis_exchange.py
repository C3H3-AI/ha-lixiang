# -*- coding: utf-8
"""livis 换取回退（2026-10-10 实测对照矩阵驱动）。

背景
----
app_type=livis 时按 app_type 取 client 参数换 saos_vehicle(7gbe) scope token
被服务端 access_denied（audience↔client 白名单配对，只认主 App client）
→ get_vehicles 失败 → modelId 缺失 → 车型能力表不可用 → 实体误建
（L6 滑门 / L8 二排中 / 显示名空 / 车主角色失效）。

实测（同一 livis 登录会话，仅换 client 参数）：
    A: livis client + app-auth/livis         ❌ access_denied（集成现状）
    B: 主 App client + app-auth              ✅ token → 车辆列表 → modelId
    C: livis client + subidaas/callback      ❌ access_denied（App 原生参数）
    D: 主 App client + subidaas/callback      ✅

故修复 = 被拒回退（非一刀切：VSS 等 audience 在 livis client 下已通），
并去掉 offline_access（实测不带照样成功，且不签发无人使用的 refresh_token）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (_INTEG / name).read_text(encoding="utf-8")


def _extract_pure(source: str, name: str):
    """提取模块级纯函数并 exec（不依赖实例状态的可直接实测）。"""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            module = ast.Module(body=[node], type_ignores=[])
            ns: dict = {}
            exec(compile(module, "<extracted>", "exec"), ns)  # noqa: S102
            return ns[name]
    raise AssertionError(f"未找到函数 {name}")


class TestExchangeClientOrder:
    """_exchange_client_order：尝试顺序纯函数实测。"""

    def _order(self):
        # 需要 APP_LOGIN_PARAMS / APP_LIXIANG 常量，从源码注入
        src = _src("li_api.py")
        fn = _extract_pure(src, "_exchange_client_order")
        # 从 pake_login 提取 APP_LOGIN_PARAMS 键
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "pake_login_t", _INTEG / "pake_login.py")
        pl = _ilu.module_from_spec(spec)
        spec.loader.exec_module(pl)

        def wrapped(app_type, win):
            import types
            mod = types.SimpleNamespace(
                APP_LOGIN_PARAMS=pl.APP_LOGIN_PARAMS,
                APP_LIXIANG=pl.APP_LOGIN_PARAMS and "lixiang")
            # 以函数 globals 注入常量执行
            g = {"APP_LOGIN_PARAMS": pl.APP_LOGIN_PARAMS,
                 "APP_LIXIANG": "lixiang"}
            return types.FunctionType(fn.__code__, g)(app_type, win)
        return wrapped

    def test_livis_falls_back_to_main(self):
        """livis → [livis, lixiang]：先登录身份，被拒回退主 App。"""
        assert self._order()("livis", None) == ["livis", "lixiang"]

    def test_lixiang_no_redundant(self):
        """app_type=lixiang → 仅 [lixiang]，不重复不回退。"""
        assert self._order()("lixiang", None) == ["lixiang"]

    def test_winner_pinned(self):
        """胜出参数置顶：livis 账号回退主 client 成功后，下次直接用主 client。"""
        assert self._order()("livis", "lixiang") == ["lixiang", "livis"]

    def test_unknown_app_type_defaults_main(self):
        """未知 app_type 兜底主 App（不抛错）。"""
        assert self._order()("", None) == ["lixiang"]

    def test_win_invalid_ignored(self):
        """win 是非法值（如空串/未知 key）时忽略，回退常规顺序。"""
        assert self._order()("livis", "bogus") == ["livis", "lixiang"]
        assert self._order()("livis", None) == ["livis", "lixiang"]


class TestExchangeSourceGuards:
    """结构性守卫：回退与去 offline_access 不被误删。"""

    def test_fallback_loop_exists(self):
        s = _src("li_api.py")
        assert "_exchange_client_order(" in s, "_exchange 必须用顺序函数"
        assert "_do_exchange(cli, key" in s, "必须按顺序逐个尝试 client 参数"
        assert '"access_denied" in str(err)' in s, (
            "仅 access_denied 才回退换 client（网络错换也没用）")

    def test_offline_access_removed(self):
        s = _src("li_api.py")
        assert '"offline_access"' not in s, (
            "换取不得再带 offline_access —— 会签发无人使用的 refresh_token"
            "（2026-10-10 实测：不带照样换到 token）")

    def test_winner_memory_fields(self):
        s = _src("li_api.py")
        assert "self._exchange_client_win" in s, "需实例字段记忆胜出参数"
        assert "_exchange_client_win = key" in s, "回退成功后必须记忆"

    def test_app_type_params_still_primary(self):
        """按 app_type 取参仍是第一选择（VSS 等 audience 依赖它）。"""
        s = _src("li_api.py")
        i = s.find("def _do_exchange")
        blk = s[i:i + 800]
        assert "APP_LOGIN_PARAMS.get(client_key)" in blk, (
            "_do_exchange 必须按 client_key 取参（而非硬编码）")

    def test_scope_denied_still_no_relogin(self):
        """回归：_get_scoped 的 scope 拒绝仍不得触发重登（风暴教训）。"""
        s = _src("li_api.py")
        assert "if _is_scope_denied(err):" in s
        m = re.search(r"def _get_scoped.*?(?=\n    def )", s, re.S)
        assert m and "_is_scope_denied(err)" in m.group(0)
        # 回退后仍 access_denied → 抛给 _get_scoped → 不重登
        assert "raise last_err if last_err" in _src("li_api.py") or \
            "raise last_err" in _src("li_api.py")
