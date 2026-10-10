"""2026-10-10 三个修复的回归守卫。

① 派生信号 NameError：compute 字符串 eval 时必须带 signals 的 globals
   （实测 range_total_cltc/wltc 一直 unknown：`name '_sum_range' is not defined`）
② 服务 handler 里的角色探测必须走 executor
   （实测：事件循环里同步 HTTP 被 HA 拦截 → get_charge/get_travel/get_tasks
    全部静默返回空 []，且异常被吞掉）
③ diagnostics 不得在事件循环里 open(manifest.json)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (CC / name).read_text(encoding="utf-8")


class TestDerivedSignalGlobals:
    def test_eval_uses_signals_globals(self):
        src = _src("coordinator.py")
        assert "_signals_mod.__dict__" in src, (
            "eval(compute) 未带 signals 模块 globals —— _sum_range 会 NameError")
        assert 'eval(_compute, _eval_globals)' in src, "eval 未传入 globals"

    def test_sum_range_importable_from_signals_namespace(self):
        """compute 串里引用的名字必须在 signals 命名空间内。"""
        import ast
        tree = ast.parse(_src("signals.py"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
        for want in ("_sum_range",):
            assert want in names, f"signals.py 缺 {want}（compute 引用它）"

    def test_compute_strings_reference_defined_names(self):
        """所有 compute 串引用的顶层名字都必须在 signals.py 里定义。"""
        import ast
        sig_src = _src("signals.py")
        tree = ast.parse(sig_src)
        defined = set(dir(ast))  # 占位，真正集合在下面
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        defined.add(t.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    defined.add((a.asname or a.name).split(".")[0])
        import ast as _ast
        for m in re.finditer(r'compute="(.*?)"', sig_src, re.S):
            expr = m.group(1)
            try:
                tree2 = _ast.parse(expr, mode="eval")
            except SyntaxError:
                continue
            for node in _ast.walk(tree2):
                if isinstance(node, _ast.Name) and isinstance(node.ctx, _ast.Load):
                    name = node.id
                    if name in ("lambda", "vss"):
                        continue
                    assert name in defined, (
                        f"compute 串引用了 signals.py 未定义的名字 {name!r} —— "
                        "运行时 eval 会 NameError（range_total 事故）")


class TestRoleProbeGoesToExecutor:
    def test_coordinator_owner_check_is_async_with_executor(self):
        src = _src("coordinator.py")
        assert "async def _is_owner_account(" in src, "角色判定应为 async"
        assert "_is_owner_account_sync" in src, "同步核心应拆出"
        assert "async_add_executor_job(\n                self._is_owner_account_sync)" in src \
            or "async_add_executor_job(" in src, "角色探测必须走 executor"
        assert "_owner_cache" in src, "角色结果必须缓存（不能每轮询都打一次 HTTP）"
        assert "await self._owner_only_skip(" in src, "调用点未 await（改动后必须同步更新）"

    def test_service_handlers_use_async_role_probe(self):
        src = _src("__init__.py")
        assert "async def _is_non_owner_async(" in src, "缺异步角色探测 helper"
        assert "async_add_executor_job(_is_non_owner, api)" in src, (
            "角色探测必须经 executor")
        assert "await _is_non_owner_async(hass, api)" in src, "服务 handler 未使用异步探测"
        assert "await _li_task_entries(target_vin)" in src, "_li_task_entries 未改 async"
        assert "await _owner_only_hint(hass, result)" in src, "_owner_only_hint 未改 async"


class TestDiagnosticsNoBlockingOpen:
    def test_manifest_read_is_cached(self):
        src = _src("diagnostics.py")
        assert "_MANIFEST_CACHE" in src, "manifest 读取未做模块级缓存"
        assert "_MANIFEST_CACHE.update(manifest)" in src


class TestRoleCacheIsolation:
    """角色缓存不得写进 hass.data[DOMAIN] 本体。

    实测 500：handler 遍历 `hass.data[DOMAIN].items()` 期间，
    `_is_non_owner_async` 往同一个 dict 塞缓存键 →
    "dictionary changed size during iteration"。
    """
    def test_cache_key_not_in_domain_dict(self):
        src = _src("__init__.py")
        assert 'hass.data.setdefault(DOMAIN, {}).setdefault("__owner_role"' not in src, (
            "角色缓存放在 DOMAIN 容器里（遍历期间加键 → RuntimeError）")
        assert 'f"{DOMAIN}__owner_role"' in src, "应使用独立命名空间存角色缓存"
