# -*- coding: utf-8
"""任务大师（2026-10-07）结构性守卫 + payload 构造实测。

背景：任务大师走 HTTP /ssp-task-master-service（真机抓包实证，非 JOB 通道），
     本文件守卫：
       ① li_api 端点/令牌/方法不被误删或改错
       ② build_task_payload 与抓包 schema 逐字段一致（真实执行，不靠子串）
       ③ 实体与服务接线存在（LiTaskSwitch / LiTaskMasterSensor / create_task）
"""
from __future__ import annotations

import ast
import re
import time
from pathlib import Path

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (_INTEG / name).read_text(encoding="utf-8")


def _extract_function(source: str, name: str):
    """从源码中提取纯函数并 exec（只依赖 time/builtins 的函数可直接实测）。"""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            module = ast.Module(body=[node], type_ignores=[])
            code = compile(module, "<extracted>", "exec")
            ns: dict = {"time": time}
            exec(code, ns)  # noqa: S102 - 测试内提取自家纯函数
            return ns[name]
    raise AssertionError(f"未找到函数 {name}")


# ---------------------------------------------------------------------------
# ① 接口层
# ---------------------------------------------------------------------------

class TestLiApiTaskEndpoints:
    def test_scope_is_full_bundle(self):
        """★ 单换 task-master 被 SSO 拒（HTTP300 access_denied，2026-10-08 实测），
        必须固定使用 App 权威完整五件套。"""
        m = re.search(r'SCOPE_TASK_MASTER\s*=\s*\((.*?)\)', _src("li_api.py"), re.S)
        assert m, "未找到 SCOPE_TASK_MASTER"
        for need in ("task-master", "vss:get-batch", "veh-ctrl:cmd-send",
                     "veh-ctrl:cmd-result-get", "remote-wakeup:wakeup"):
            assert need in m.group(1), f"缺 {need}"
        # 不允许回退机制残留（主路径即完整包）
        assert "SCOPE_TASK_MASTER_FULL" not in _src("li_api.py")

    def test_endpoints_present(self):
        s = _src("li_api.py")
        for ep in ("/ssp-task-master-service/v1/task-config/mob/my-task-by-vin/{vin}",
                   "/ssp-task-master-service/v1/task-config/mob/save/{vin}",
                   "/ssp-task-master-service/v1/task-config/mob/update-task/{vin}",
                   "/ssp-task-master-service/v1/task-config/mob/delete/{vin}/{config_id}"):
            assert f'"{ep}"' in s, f"缺少端点 {ep}"

    def test_methods_exist(self):
        tree = ast.parse(_src("li_api.py"))
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for fn in ("get_tasks", "save_task", "update_task", "delete_task",
                   "_get_task_token", "_task_call", "_signed_call_task"):
            assert fn in names, f"缺少方法 {fn}"
        assert "_is_scope_denied" in names, "缺少 scope 拒绝判别函数"
        assert "_is_unauthorized" in names, "缺少 401 判别函数"

    def test_scope_denied_no_relogin(self):
        """★ scope 被拒 ≠ 会话失效：_get_scoped 不得对其触发重登。

        2026-10-08 真机教训：误判导致「每分钟 _login + _tokens.clear()」
        风暴（87 次/1.5h，账号风控风险）。
        """
        s = _src("li_api.py")
        i = s.find("def _get_scoped")
        # ★ 用「到下一个同类方法」的窗口，不用固定字符数 ——
        #   固定窗口会随合法改动（新增守卫、注释）而误报
        _next = s.find("\n    def ", i + 1)
        blk = s[i:_next if _next > 0 else i + 3000]
        pos_guard = blk.find("if _is_scope_denied(err)")
        pos_login = blk.find("self._login()")   # 真实调用（注释里的字样不算）
        assert pos_guard > 0, "_get_scoped 未使用 scope 拒绝判别"
        assert pos_login > 0 and pos_guard < pos_login, (
            "必须在重登分支之前拦截")
        i2 = s.find("def _is_scope_denied")
        helper = s[i2:i2 + 400]
        assert "access_denied" in helper and "HTTP 300" in helper

    def test_is_unauthorized(self):
        """★ 401 判别纯函数【真实执行】（不靠子串匹配源码）。"""
        fn = _extract_function(_src("li_api.py"), "_is_unauthorized")
        # 真机原文样例：HTTP 401 {"status":401,"error":"Unauthorized",...}
        assert fn(Exception('GET /x: HTTP 401 {"status":401,"error":"Unauthorized"}')) is True
        assert fn(Exception("Unauthorized")) is True
        # 不该误判的其它错误
        assert fn(Exception("HTTP 403 forbidden")) is False
        assert fn(Exception("任务列表响应异常: {'code': 100005}")) is False
        assert fn(Exception("HTTP 300 access_denied")) is False
        assert fn(Exception("HTTP 429 rate limited")) is False

    def test_is_scope_denied_distinguishes_login_required(self):
        """★ HTTP 300 有两种语义，不能一刀切（纯函数真实执行）。

        · 300 + access_denied  → scope 被策略拒绝 → 重登无用（True）
        · 300 + login_required → 会话失效         → **必须重登**（False）

        2026-10-08 真机故障实证：把 login_required 也判为 scope 拒绝
        → _get_scoped 永不重登 → 通知 / VSS / 任务大师三个模块全部持续
        失败且**无法自愈**（22:33 起每 30~60s 一次，十余分钟未恢复，
        只能手动重载集成）。
        """
        fn = _extract_function(_src("li_api.py"), "_is_scope_denied")

        # ① 会话失效 → 必须允许走重登分支
        assert fn(Exception(
            '换 token 失败 (ALL): HTTP 300 {"location":'
            '"https://account.lixiang.com/app-auth?error=login_required"}'
        )) is False, "login_required 被误判为 scope 拒绝 → 永不重登（严重）"

        # ② scope 被策略拒绝 → 不重登（避免重登风暴）
        assert fn(Exception(
            '换 token 失败 (task-master): HTTP 300 '
            '{"location":"https://id.lixiang.com/app-auth?error=access_denied"}'
        )) is True, "access_denied 未被识别为 scope 拒绝"

        # ③ 其它 300（无明确关键词）→ 保守按拒绝处理
        assert fn(Exception("HTTP 300 redirect without keyword")) is True

        # ④ 非 300 错误不属此列
        assert fn(Exception("HTTP 401 Unauthorized")) is False
        assert fn(Exception("HTTP 403 forbidden")) is False

    def test_task_call_401_selfheal(self):
        """★ 任务接口遇 401 必须【主动失效 token 缓存并重取】。

        2026-10-08 真机教训：401 连续 147 次、跨 10 小时才自愈 ——
        因为缓存 token（ttl=1800s）未失效，每 60s 重试都复用同一个
        被拒 token，必须等 ttl 到期才重新换取。
        """
        s = _src("li_api.py")
        i = s.find("def _task_call(")
        assert i > 0, "缺少 _task_call"
        j = s.find("def get_tasks(", i)
        blk = s[i:j] if j > i else s[i:i + 1400]

        pos_guard = blk.find("if not _is_unauthorized(err)")
        pos_inval = blk.find('_invalidate_token("taskmaster")')
        assert pos_guard > 0, "_task_call 未判别 401"
        assert pos_inval > 0, "遇 401 未失效 taskmaster 缓存"
        assert pos_guard < pos_inval, "必须先判别 401 再失效缓存"

        # ★ 只失效 taskmaster，不得触发重登（PR #11 修掉的重登风暴）
        assert "self._login()" not in blk, "401 自愈不得触发 _login()"
        assert "_tokens.clear()" not in blk, "401 自愈不得清空全部 token"

        # 失效缓存后必须重取 token 并重试一次
        assert blk.count("_signed_call_task(") >= 2, "401 后须重取 token 重试一次"
        assert blk.count("self._get_task_token()") >= 2, "重试须重新获取 token"

    def test_signed_call_used(self):
        """任务请求必须经 _task_call → _signed_call_task（App 实测头 + 重签）。"""
        s = _src("li_api.py")
        for fn in ("get_tasks", "save_task", "update_task"):
            i = s.find(f"def {fn}(")
            assert i > 0, fn
            blk = s[i:i + 900]
            assert "_task_call" in blk, f"{fn} 未走 _task_call"
        i = s.find("def _task_call(")
        assert i > 0, "缺少 _task_call"
        j = s.find("def get_tasks(", i)
        blk = s[i:j] if j > i else s[i:i + 1500]
        assert "_signed_call_task" in blk, "_task_call 未走 _signed_call_task"

    def test_task_headers_match_app_capture(self):
        """任务专用签名调用的头与抓包一致（403 排查：travel 同款教训）。"""
        s = _src("li_api.py")
        i = s.find("def _signed_call_task")
        assert i > 0, "缺少 _signed_call_task"
        blk = s[i:i + 2500]
        # 签名第 7 段与发送头都必须是 zh-CN（改语言必须同步重签）
        assert '"zh-CN", md5' in blk.replace("'", '"'), "签名语言段未用 zh-CN"
        assert '"Content-Language": "zh-CN"' in blk
        assert '"X-CHJ-ModelName": "ANDROID"' in blk
        assert "X-CHJ-Metadata" in blk and "Accept-Language" in blk
        # ★ 签名第 2 段必须等于请求头版本（不一致 → 100005，
        #   2026-10-08 维护者真机变体矩阵：8.25.4签名+8.27.0头=100005）
        m_data = re.search(r'data = "\\n"\.join\(\[(.*?)\]\)', blk, re.S)
        assert m_data, "未找到签名 data 串"
        assert "TASK_APP_VERSION" in m_data.group(1), "签名第2段必须用 TASK_APP_VERSION"
        assert "SIGN_APP_VERSION" not in m_data.group(1), (
            "签名第2段不得用 SIGN_APP_VERSION（与头不一致 → 100005）")
        # 版本/UA 常量存在
        s2 = _src("li_api.py")
        assert 'TASK_APP_VERSION = "8.27.0"' in s2
        assert "M01/8.27.0" in s2


# ---------------------------------------------------------------------------
# ② build_task_payload：与抓包 schema 逐字段一致（真实执行）
# ---------------------------------------------------------------------------

CAPTURED_KEYS = {
    "configName", "configId", "automate", "voiceExecute",
    "runOnceFrequency", "runOnce", "taskValue", "enabled",
}


class TestBuildTaskPayload:
    def test_schema_matches_capture(self):
        fn = _extract_function(_src("li_api.py"), "build_task_payload")
        p = fn("测试任务",
               [{"conditionType": "Microphone",
                 "params": [{"key": "state", "value": "connected"}]}],
               [{"actionType": "PowerOutlet",
                 "params": [{"key": "operation", "value": "open"}]}])
        assert set(p.keys()) == CAPTURED_KEYS, p.keys()
        assert p["configId"].startswith("mob_")
        assert p["configId"][4:].isdigit() and len(p["configId"]) == 17  # mob_+13位毫秒
        assert p["runOnceFrequency"] == "2"
        assert set(p["taskValue"].keys()) == {"conditions", "actions"}
        assert p["enabled"] is True and p["automate"] is True
        assert p["voiceExecute"] is False and p["runOnce"] is False

    def test_config_id_is_millis_epoch(self):
        fn = _extract_function(_src("li_api.py"), "build_task_payload")
        t0 = int(time.time() * 1000)
        cid = fn("x", [], [{"actionType": "A"}])["configId"]
        assert cid.startswith("mob_")
        assert int(cid.split("_")[1]) >= t0

    def test_validation(self):
        fn = _extract_function(_src("li_api.py"), "build_task_payload")
        import pytest
        with pytest.raises(ValueError):
            fn("", [], [{"actionType": "A"}])          # 空名称
        with pytest.raises(ValueError):
            fn("名字", [], [])                          # 空动作
        with pytest.raises(ValueError):
            fn("名字", "not-a-list", [{"actionType": "A"}])  # conditions 类型错


# ---------------------------------------------------------------------------
# ③ 实体与服务接线
# ---------------------------------------------------------------------------

class TestEntitiesAndService:
    def test_task_switch_class_and_dynamic_registration(self):
        s = _src("switch.py")
        tree = ast.parse(s)
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        assert "LiTaskSwitch" in names
        assert "async_add_listener" in s, "缺少动态注册监听"
        assert "invalidate_task_cache" in s, "启停后未失效任务缓存"
        assert "update_task" in s, "开关未走 update_task"

    def test_task_sensor_class(self):
        s = _src("sensor.py")
        tree = ast.parse(s)
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        assert "LiTaskMasterSensor" in names
        assert '_task_summary' in s
        assert "拉取错误" in s, "传感器需暴露拉取错误属性（排障入口）"

    def test_task_summary_rendering(self):
        fn = _extract_function(_src("sensor.py"), "_task_summary")
        out = fn({"conditions": [{"paramDescs": ["已连接"]}],
                  "actions": [{"paramDescs": ["打开"]}]})
        assert "已连接" in out and "打开" in out and "→" in out
        # save 请求体的另一种拼写 paramsDescs
        out2 = fn({"conditions": [], "actions": [{"paramsDescs": ["关窗"]}]})
        assert "关窗" in out2 and "无条件" in out2

    def test_coordinator_fetch_and_invalidate(self):
        s = _src("coordinator.py")
        assert 'get_tasks' in s and '"tasks"' in s
        assert "def invalidate_task_cache" in s
        # 两个 return 路径都要带上 tasks + 错误上浮
        assert s.count('data["tasks"] = _tasks') == 2, "离线/在线两个出口都要挂 tasks"
        assert s.count('data["task_error"]') == 2, "两个出口都要挂 task_error"
        assert "_task_error" in s, "coordinator 需记录拉取错误"

    def test_create_task_service_wired(self):
        s = _src("__init__.py")
        assert 'SERVICE_CREATE_TASK = "create_task"' in s
        assert "SERVICE_CREATE_TASK, _handle_create_task" in s
        assert "SupportsResponse.OPTIONAL" in s
        assert "build_task_payload" in s
        yaml_src = _src("services.yaml")
        assert "create_task:" in yaml_src
        assert re.search(r"create_task:.*?name:.*?required: true", yaml_src, re.S)
        assert re.search(r"create_task:.*?actions:.*?required: true", yaml_src, re.S)

    def test_task_service_suite_wired(self):
        """CRUD 服务套件（查询/更新/删除）接线完整。"""
        s = _src("__init__.py")
        for const, handler in (("SERVICE_GET_TASKS", "_handle_get_tasks"),
                               ("SERVICE_UPDATE_TASK", "_handle_update_task"),
                               ("SERVICE_DELETE_TASK", "_handle_delete_task")):
            assert f'{const} =' in s, f"缺少常量 {const}"
            assert f"{const}, {handler}" in s, f"未注册 {handler}"
        assert "invalidate_task_cache" in s, "写服务后需失效任务缓存"
        yaml_src = _src("services.yaml")
        for svc in ("get_tasks:", "update_task:", "delete_task:"):
            assert svc in yaml_src, f"services.yaml 缺 {svc}"
        # update/delete 的 config_id 必填
        assert re.search(r"update_task:.*?config_id:.*?required: true", yaml_src, re.S)
        assert re.search(r"delete_task:.*?config_id:.*?required: true", yaml_src, re.S)
