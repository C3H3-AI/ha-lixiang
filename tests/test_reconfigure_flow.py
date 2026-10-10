"""重配置流程（HA reconfigure）回归测试（2026-10-10）。

背景
----
在这之前，「登录身份（理想汽车 / 理想同学）」与「VIN」都**改不了** ——
用户只能删除条目重新添加（HA 菜单里也没有「重配置」，因为集成没实现
`async_step_reconfigure`）。

设计要点（本文件守卫它们）
  ① 切换登录身份 → 必须重新 PAKE 登录 + **重新派生签名身份**
     （两个 App 的 KID 与 RSA 私钥都不同，沿用旧身份签名必被拒）
  ② 只改 VIN → 直接写回，**不触发登录**（VIN 与签名身份无关）
  ③ 切身份时必填密码；派生失败必须**中止**（不能把「新身份+旧签名」写进条目）
  ④ strings / 两份翻译都要有 reconfigure 步骤，否则 HA 界面上是空白表单
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CF = CC / "config_flow.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method(name: str) -> str:
    src = _src(CF)
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == "LiCarConfigFlow":
            for sub in node.body:
                if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and sub.name == name):
                    return ast.get_source_segment(src, sub) or ""
    raise AssertionError(f"找不到 LiCarConfigFlow.{name}")


# ── ① 纯函数：切身份才需要重登 ────────────────────────────────────────────
def _load_needs_relogin():
    src = _src(CF)
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef)
              and n.name == "_reconfigure_needs_relogin")
    ns = {"__name__": "cf", "APP_LIXIANG": "lixiang", "APP_LIVIS": "livis"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<f>", "exec"), ns)
    return ns["_reconfigure_needs_relogin"]


class TestNeedsRelogin:
    def test_switching_identity_needs_relogin(self):
        """★ 两个 App 的 KID/私钥不同 → 切身份必须重登重派生。"""
        fn = _load_needs_relogin()
        assert fn("lixiang", "livis") is True
        assert fn("livis", "lixiang") is True

    def test_same_identity_does_not(self):
        fn = _load_needs_relogin()
        assert fn("lixiang", "lixiang") is False
        assert fn("livis", "livis") is False

    def test_empty_values_default_to_lixiang(self):
        """历史条目可能没有 app_type → 视为理想汽车（与迁移逻辑一致）。"""
        fn = _load_needs_relogin()
        assert fn("", "") is False
        assert fn("", "lixiang") is False
        assert fn("", "livis") is True
        assert fn("lixiang", "") is False


# ── ② 步骤行为（源码级，环境没有 homeassistant）────────────────────────────
class TestReconfigureStep:
    def test_step_exists(self):
        assert "async def async_step_reconfigure" in _src(CF), (
            "未实现 async_step_reconfigure → HA 菜单里不会出现「重配置」")

    def test_vin_only_change_skips_login(self):
        """只改 VIN 不该触发登录（避免无谓的账号操作/风控）。"""
        body = _method("async_step_reconfigure")
        assert "_reconfigure_needs_relogin(cur_app, new_app)" in body
        # 不需要重登的分支里，必须直接更新条目
        head, _, tail = body.partition("if not _reconfigure_needs_relogin(cur_app, new_app):")
        assert "async_update_reload_and_abort" in tail, (
            "仅改 VIN 的分支没有直接写回条目")
        # 该分支内不得调用登录
        only_vin_branch = tail.split("password = ")[0]
        assert "_do_direct_login" not in only_vin_branch, (
            "仅改 VIN 的分支不该登录")

    def test_identity_switch_logs_in_with_new_app_type(self):
        """★ 切身份时用【新的】app_type 重新登录。"""
        body = _method("async_step_reconfigure")
        assert "_do_direct_login, phone, password, device_id, new_app" in body, (
            "切身份时未用新 app_type 登录（会拿旧身份的会话去签新身份）")

    def test_identity_switch_requires_password(self):
        body = _method("async_step_reconfigure")
        assert 'errors["password"] = "password_required"' in body, (
            "切身份未强制要求密码")

    def test_identity_rederived_and_aborts_on_failure(self):
        """★ 派生失败必须中止 —— 否则会把「新身份 + 旧签名」写进条目。"""
        body = _method("async_step_reconfigure")
        assert "await self._rederive_identity(data, cur_app)" in body
        seg = body.split("if not await self._rederive_identity")[1]
        assert 'errors["base"] = "identity_derive_failed"' in seg, (
            "派生失败未阻止保存")
        # 成功分支在 else 里 → 失败时不会走到 reload
        assert "else:" in seg
        assert seg.index("async_update_reload_and_abort") > seg.index("else:")

    def test_unknown_entry_aborts_cleanly(self):
        body = _method("async_step_reconfigure")
        assert 'reason="reconfigure_entry_not_found"' in body, (
            "找不到条目时应明确 abort，而不是抛异常")


# ── ③ 派生 helper 现在返回 bool（两个调用方语义不同）────────────────────────
class TestDeriveHelperContract:
    def test_helper_returns_bool(self):
        body = _method("_rederive_identity")
        assert "-> bool" in body, "helper 应返回是否成功（reconfigure 依赖它）"
        assert "return True" in body
        assert body.count("return False") >= 2, (
            "缺参数 / 派生异常两条失败路径都要返回 False")

    def test_reauth_still_tolerates_failure(self):
        """重新认证仍要「失败保留旧值」（不把能用的条目搞砖）。"""
        body = _method("async_step_reauth_confirm")
        assert "await self._rederive_identity(data, src)" in body
        assert "if not await self._rederive_identity" not in body, (
            "重新认证不该因派生失败而中止（失败保留旧身份即可）")

    def test_no_stale_helper_name(self):
        src = _src(CF)
        assert "_rederive_identity_on_reauth" not in src, (
            "旧名字应已全部改名（该方法现在被 reauth 与 reconfigure 共用）")


# ── ④ 文案与翻译 ─────────────────────────────────────────────────────────
class TestStrings:
    @pytest.mark.parametrize("rel", [
        "strings.json",
        "translations/en.json",
        "translations/zh-Hans.json",
    ])
    def test_reconfigure_step_declared(self, rel):
        d = json.loads(_src(CC / rel))
        step = d["config"]["step"].get("reconfigure")
        assert step, f"{rel} 缺 config.step.reconfigure（界面会是空白表单）"
        for field in ("app_type", "vin", "password"):
            assert field in step.get("data", {}), f"{rel} 缺字段说明 {field}"
        assert "current" in step.get("description", ""), (
            f"{rel} 的描述未用 {{current}} 占位（与代码的 placeholders 对不上）")

    @pytest.mark.parametrize("rel", [
        "strings.json",
        "translations/en.json",
        "translations/zh-Hans.json",
    ])
    def test_error_and_abort_keys(self, rel):
        d = json.loads(_src(CC / rel))
        assert "password_required" in d["config"]["error"]
        assert "identity_derive_failed" in d["config"]["error"]
        assert "reconfigure_successful" in d["config"]["abort"]
        assert "reconfigure_entry_not_found" in d["config"]["abort"]
