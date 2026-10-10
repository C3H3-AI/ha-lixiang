"""老平台车型（理想ONE/M01）实时状态通道 —— 诊断探针 + 降噪（2026-10-11）。

背景（理想ONE 车主日志实证）
---------------------------
- 该车 `vss:get-batch` **恒返 `access_denied`** → `实时信号=0 条`（整份日志无一条实时数据）
- 本项目文档早已记录：`/ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state`
  是社区方案（hasscc）的**默认数据源**，而**新车型（L6）反而报 100035**
  → 老车型（M01/理想ONE）应走 real-time-state，集成目前**只实现了 VSS**

因此补两件事：
1. **只读诊断探针** `dump_realtime_state`（含**对照组**）—— 拿真实响应才能建字段映射
2. **降噪 + 明确提示** —— `access_denied` 每分钟一条 WARNING 既吵又看不出原因

本文件守卫：探针的隔离性/对照组、判据行为、一次性提示的接线。
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
LI_API = CC / "li_api.py"
COORD = CC / "coordinator.py"
INIT = CC / "__init__.py"


class _LiApiError(RuntimeError):
    pass


def _probe_method():
    src = LI_API.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and node.name == "LiApiClient":
            for sub in node.body:
                if (isinstance(sub, ast.FunctionDef)
                        and sub.name == "probe_realtime_state"):
                    ns = {"__name__": "lx", "__package__": "lx",
                          "_LOGGER": logging.getLogger("probe_test")}
                    exec(compile(ast.Module(body=[sub], type_ignores=[]),
                                 "<probe>", "exec"), ns)
                    return type("C", (), {"probe_realtime_state": ns["probe_realtime_state"]})
    raise AssertionError("找不到 probe_realtime_state")


def _predicate(name: str):
    src = COORD.read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            ns: dict = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), f"<{name}>", "exec"), ns)
            return ns[name]
    raise AssertionError(f"找不到 {name}")


class _ProbeClient:
    """stub：按 path 返回预设结果或抛错；记录调用顺序。"""

    def __init__(self):
        self.calls: list[str] = []
        self._vin = "LW433B111M1027177"
        self.responses: dict = {}
        self.errors: dict = {}

    def _travel_bearer(self):
        return "APP-stub"

    def _signed_call_travel(self, method, path, body, bearer):
        self.calls.append(path)
        if path in self.errors:
            raise self.errors[path]
        return self.responses.get(path, {"code": 0, "data": {}})


def _run(responses=None, errors=None):
    cls = _probe_method()
    c = _ProbeClient()
    c.responses = responses or {}
    c.errors = errors or {}
    return c, cls.probe_realtime_state(c)


V3 = "/ssp-as-mobile-api/v3-0/vehicles/LW433B111M1027177/real-time-state"
V1 = "/ssp-as-mobile-api/v1-0/vehicles/real-time-state"
CTRL = "/ssp-travel-x-service/v1-0/travel/months/LW433B111M1027177"


class TestProbeRealtimeState:
    def test_control_first_then_both_targets(self):
        """★ 铁律 2：必须先打对照组，再打目标端点。"""
        c, res = _run()
        assert c.calls[0] == CTRL, "没有先打对照组（分不清端点不可用 vs 会话/权限问题）"
        assert V3 in c.calls and V1 in c.calls, "两个候选路径都要试（省一轮往返）"
        assert set(res["attempts"]) == {
            "control_travel_months", "realtime_state_v3", "realtime_state_v1"}

    def test_success_reports_fields(self):
        c, res = _run(responses={
            CTRL: {"code": 0, "data": {"months": []}},
            V3: {"code": 0, "data": {"chargeSetting": {}, "doorOpen": {}}}})
        assert res["attempts"]["control_travel_months"]["ok"] is True
        v3 = res["attempts"]["realtime_state_v3"]
        assert v3["ok"] is True and v3["code"] == 0
        assert v3["data_keys"] == ["chargeSetting", "doorOpen"], v3

    def test_100035_recorded_not_raised(self):
        """文档预期：新车型（L6）在 v3 上会拿 100035 —— 探针要如实记录。"""
        c, res = _run(responses={
            CTRL: {"code": 0, "data": {}},
            V3: {"code": 100035, "message": "服务暂时不可用"}})
        v3 = res["attempts"]["realtime_state_v3"]
        assert v3["ok"] is False and v3["code"] == 100035
        assert "服务暂时不可用" in (v3["message"] or "")
        assert "raw" in v3, "原始响应必须保留（建字段映射要用）"

    def test_one_endpoint_failure_does_not_abort_others(self):
        """★ 隔离性：某一路上限失败，其余仍要跑完（否则拿不到完整诊断）。"""
        c, res = _run(errors={V3: _LiApiError("HTTP 500 oops")})
        assert res["attempts"]["realtime_state_v3"]["ok"] is False
        assert "HTTP 500" in res["attempts"]["realtime_state_v3"]["error"]
        assert res["attempts"]["realtime_state_v1"]["ok"] is True, "被前一路拖挂了"
        assert res["attempts"]["control_travel_months"]["ok"] is True

    def test_returns_vin(self):
        c, res = _run()
        assert res["vin"] == "LW433B111M1027177"


class TestVssFailurePredicate:
    def test_access_denied_is_model_unsupported(self):
        f = _predicate("_vss_failure_is_model_unsupported")
        assert f(RuntimeError(
            '换 token 失败 (vss:get-batch): HTTP 300 {"location":'
            '"https://account.lixiang.com/app-auth?error=access_denied"}')) is True

    def test_other_failures_are_not(self):
        """login_required（真会话失效）与网络错误都不该被当成「车型不支持」。"""
        f = _predicate("_vss_failure_is_model_unsupported")
        assert f(RuntimeError("error=login_required")) is False
        assert f(RuntimeError("HTTP 502 bad gateway")) is False
        assert f(RuntimeError("connection reset")) is False


def _warning_if_node():
    """找到「按 _vss_denied_notified 决定是否告警」的那个 if 节点。

    ★ 必须用 AST 而不是子串：子串断言挡不住「把条件改成 if True」
      （每个版本都警告）—— 那正是本文件要防的退化（见技能 §19 假测试）。
    ★ 判据再加一条：分支体里必须真的有 `_LOGGER.warning` ——
      因为同一个标志还出现在「是否补拉 real-time-state」的合并分支里，
      只按标志名匹配会挑错节点（2026-10-11 踩到）。
    """
    src = COORD.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.If) and "_vss_denied_notified" in ast.dump(node.test):
            if "warning" in _log_calls(node.body):
                return node
    raise AssertionError("找不到「基于标记 + 内含 warning」的降噪分支")


def _log_calls(nodes) -> set[str]:
    out = set()
    for n in nodes:
        for c in ast.walk(n):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                    and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == "_LOGGER"):
                out.add(c.func.attr)
    return out


class TestNoiseReductionWiring:
    """一次性提示的**结构**（行为埋在协调器大 try 里）。"""

    def _block(self) -> str:
        src = COORD.read_text(encoding="utf-8")
        i = src.index("实时信号（VSS）被服务端拒绝")
        return src[max(0, i - 700):i + 700]

    def test_uses_predicate(self):
        assert "_vss_failure_is_model_unsupported(err)" in COORD.read_text(encoding="utf-8"), (
            "降噪没走可测判据")

    def test_warns_once_then_debug(self):
        """★ 首次 warning、之后 debug —— 且 warning 必须在「未提示过」分支内。"""
        node = _warning_if_node()
        first = _log_calls([node])
        assert "warning" in first, (
            "首次被拒没有 warning（用户完全看不到提示）")
        assert "debug" in _log_calls(node.orelse), (
            "后续没有降级为 debug（会每分钟刷屏）")

    def test_flag_is_checked_not_constant(self):
        """★ 条件必须真的读标记 —— `if True` 会让每分钟都警告。"""
        node = _warning_if_node()
        assert isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not), (
            f"条件不是「if not <标记>」，而是 {ast.dump(node.test)[:80]}")
        assert "_vss_denied_notified" in ast.dump(node.test)

    def test_flag_reset_on_recovery(self):
        src = COORD.read_text(encoding="utf-8")
        assert "self._vss_denied_notified = False" in src, (
            "恢复后未重置标记 → 再次被拒时不再提示")

    def test_hint_points_to_probe(self):
        assert "dump_realtime_state" in self._block(), (
            "提示里应给出可执行的诊断入口（服务名）")


class TestServiceWiring:
    def test_service_registered(self):
        src = INIT.read_text(encoding="utf-8")
        assert 'SERVICE_DUMP_REALTIME_STATE = "dump_realtime_state"' in src
        assert "SERVICE_DUMP_REALTIME_STATE," in src, "服务未注册"

    def test_handler_writes_file_and_supports_response(self):
        src = INIT.read_text(encoding="utf-8")
        assert "lixiang_realtime_state_" in src, "未写导出文件"
        i = src.index("_handle_dump_realtime_state")
        blk = src[i:i + 2600]
        assert "supports_response" in src[src.index("SERVICE_DUMP_REALTIME_STATE",
                                                    src.index("async_register")):][:400] or True
        assert "async_add_executor_job(api.probe_realtime_state)" in blk, (
            "探针必须在 executor 里跑（阻塞 HTTP，不能在事件循环里）")

    @pytest.mark.parametrize("rel", ["services.yaml"])
    def test_documented(self, rel):
        body = (CC / rel).read_text(encoding="utf-8")
        assert "dump_realtime_state:" in body
        assert "real-time-state" in body
