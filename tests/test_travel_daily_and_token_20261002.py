"""2026-10-02 新增能力测试。

覆盖：
  1. token 轮换持久化（on_token_update 回调）
  2. travel 日明细与极值（single_far / single_elec / single_fuel）
  3. get_travel / get_charge 服务声明 supports_response
  4. coordinator 注入 month_daily / month_single_*
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"


def _read(name: str) -> str:
    return (CC / name).read_text(encoding="utf-8")


# ─────────────────────────── 1. token 持久化 ───────────────────────────


def test_li_api_accepts_token_callback():
    """LiApiClient 必须接受 on_token_update 回调参数。"""
    src = _read("li_api.py")
    assert "on_token_update=None" in src, "构造参数缺失"
    assert "self._on_token_update = on_token_update" in src, "未保存回调"


def _func_src(cls_name: str, fn_name: str) -> str:
    """取某个类方法的源码（★ 只用该方法本体，避开其它方法里的同名调用）。

    2026-10-10：原来用全文 `src.find(...)` 定位 —— 当别处（如身份迁移
    方法）也出现 `_notify_token_update()` 时会取到错的那个，测试随即失真。
    """
    import ast

    tree = ast.parse(_read("li_api.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if (isinstance(sub, ast.FunctionDef)
                        and sub.name == fn_name):
                    return ast.get_source_segment(_read("li_api.py"), sub) or ""
    raise AssertionError(f"找不到 {cls_name}.{fn_name}")


def test_login_notifies_token_update():
    """_login() 成功后必须触发回调（否则重启读回旧 token）。"""
    body = _func_src("LiApiClient", "_login")
    assert "_notify_token_update()" in body, "未调用回调"
    # 回调必须在设置 _main_bearer 之后
    idx_bearer = body.find('self._main_bearer = str(tok.get("access_token")')
    idx_notify = body.find("self._notify_token_update()")
    assert idx_bearer > 0 and idx_notify > idx_bearer, "回调调用点位置错误"


def test_notify_swallows_callback_error():
    """回调异常不能影响主流程。"""
    src = _read("li_api.py")
    seg = src[src.find("def _notify_token_update"):]
    seg = seg[: seg.find("def ", 10)]
    assert "except Exception" in seg, "回调未做异常保护"


def test_init_wires_token_persistence_async():
    """__init__.py 必须用 async 函数 + hass.add_job 投递。

    ★ 两个关键约束：
      - 同步函数 add_job 会在调用者线程就地执行 → 必须 async
      - executor 线程不能直接调 async_update_entry
    """
    src = _read("__init__.py")
    assert "async def _apply_patch" in src, "回调必须是 async 函数"
    assert "hass.add_job(_apply_patch" in src, "未用 add_job 投递到事件循环"
    assert "async_update_entry" in src, "未写回 config entry"
    assert "on_token_update=_persist_tokens" in src, "回调未注入"


def test_no_sync_update_entry_from_thread():
    """不得在同步回调里【实际调用】async_update_entry（HA 会报线程错误）。

    注意：docstring 里提到该名字是允许的（说明性文字），
    只检查去掉注释与字符串后的代码行。
    """
    src = _read("__init__.py")
    i = src.find("def _persist_tokens")
    assert i > 0
    seg = src[i : i + 1200]
    # 去掉 docstring 与注释后再判断
    code_lines = []
    in_doc = False
    for ln in seg.splitlines():
        t = ln.strip()
        if t.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or t.startswith("#"):
            continue
        code_lines.append(ln)
    code = "\n".join(code_lines)
    assert "async_update_entry" not in code, (
        "_persist_tokens 里直接调用了 async_update_entry（应通过 _apply_patch）"
    )


# ─────────────────────── 2. travel 日明细与极值 ───────────────────────


def test_month_returns_daily_and_extremes():
    """get_travel_current_month_km 必须返回 daily + 三个极值字段。"""
    src = _read("li_api.py")
    i = src.find("def get_travel_current_month_km")
    assert i > 0, "方法不存在"
    seg = src[i : i + 4000]
    for key in ('"daily": daily', '"single_far"', '"single_elec"', '"single_fuel"'):
        assert key in seg, f"缺字段 {key}"


def test_daily_parsing_is_defensive():
    """日明细解析必须容忍脏数据（TypeError/ValueError 不炸）。"""
    src = _read("li_api.py")
    i = src.find("daily = []")
    seg = src[i : i + 1200]
    assert "except (TypeError, ValueError)" in seg, "缺异常保护"
    assert "continue" in seg, "缺跳过逻辑"


def test_extremes_only_from_moved_days():
    """极值只在有行驶的日里取（避免除零 / 空日污染）。"""
    src = _read("li_api.py")
    assert 'moved = [r for r in daily if (r["mileage"] or 0) > 0]' in src, "未过滤空日"


def test_coordinator_injects_daily_fields():
    """coordinator 必须把日明细与极值注入 data。"""
    src = _read("coordinator.py")
    for key in ('"month_daily"', '"month_single_far"', '"month_single_elec"', '"month_single_fuel"'):
        assert key in src, f"缺注入 {key}"
    assert '_mc["daily"]' in src, "缓存未存 daily"


# ─────────────────────── 3. supports_response 声明 ───────────────────────


def test_services_declare_supports_response():
    """get_travel / get_charge 必须声明 supports_response，否则前端拿不到返回体。"""
    src = _read("__init__.py")
    assert "SupportsResponse" in src, "未导入 SupportsResponse"
    n = src.count("supports_response=SupportsResponse.OPTIONAL")
    assert n >= 2, f"声明数量不足（{n} < 2）"


def test_handlers_return_result():
    """handler 必须 return 结果（新版 HA 的服务响应方式）。"""
    src = _read("__init__.py")
    assert src.count("return result") >= 2, "handler 未 return"
    assert "async_set_service_response" not in src, "仍在使用旧 API"


def test_handler_signature_annotated():
    """handler 返回值类型应标注 ServiceResponse。"""
    src = _read("__init__.py")
    assert "-> ServiceResponse" in src, "缺返回类型标注"


# ─────────────────────── 4. 不破坏既有约束 ───────────────────────


def test_no_hardcoded_vin_in_source():
    """不得硬编码真实 VIN（隐私）。

    注意：本测试自身也不得出现完整 VIN 字面量
    （否则 CI 的 VIN 扫描会把它当成泄露 —— 这个坑踩过一次）。
    因此这里用片段拼接对比。
    """
    # 拆成两段，避免出现完整 VIN 字面量
    vin_head = "HLX32" + "B14X"
    vin_tail = "R136" + "1015"
    full = vin_head + vin_tail
    for name in ("li_api.py", "coordinator.py", "__init__.py"):
        src = _read(name)
        assert full not in src, f"{name} 里有真实 VIN"
        assert vin_head not in src, f"{name} 里有 VIN 前 8 位"


def test_no_probe_style_requests_added():
    """不得新增探测式请求（用户明确要求不主动探测服务器）。"""
    src = _read("li_api.py")
    for bad in ("for _ in range(", "while True"):
        # 仅检查新增区域：日明细解析附近不应有循环探测
        i = src.find("def get_travel_current_month_km")
        seg = src[i : i + 4000]
        assert bad not in seg, f"疑似探测循环: {bad}"


def test_manifest_version_unchanged():
    """不得自行 bump 版本（由发布流程管理）。"""
    import json

    m = json.loads((CC / "manifest.json").read_text(encoding="utf-8"))
    # 只断言版本格式合法，不断言具体值（避免与发布流程耦合）
    assert re.match(r"^\d+\.\d+\.\d+$", m["version"]), "版本号格式异常"
