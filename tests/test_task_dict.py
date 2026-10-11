"""任务条件/动作字典 —— 规范化与持久化（2026-10-11）。

★ 夹具是**真实抓包响应**（`tests/fixtures/task_dict_real.json`，来自
  `lixiang-reverse/data/user_captures_20261008/情景模式任务大师.har`），
  不是手搓的假数据 —— 这样字段名/层级/空 params 才会真的对上。

实测要点（这些是本测试锁定的关键事实）
--------------------------------------
1. 字典**服务端下发** → APK 里搜不到路径字符串，运行时才调得到
2. 路径**必须带 `/v1/`** —— 漏掉返回 `100012`，与"无权限"无法区分（实测踩过）
3. 结构是**两层**：`classification`（分类）→ `functions[]`（条目）
4. ★ 早期注释写的「15 条件 / 17 动作」是**误读** —— 那是**分类数**；
   实测条目数远不止（见下方规模测试）
5. `params` 可能是 **`null`**（如 Time / Delay 无需参数）
6. `dataSource` 三态：`mob`（客户端提供）/ `clo`（车端）/ `veh`（车辆配置，
   我们通常无权创建 → UI 应标注）
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

import importlib.util

# ★ 直接按文件加载 task_dict 模块 —— 走 `custom_components.lixiang_auto` 包会触发
#   其 __init__（import homeassistant），本机无该模块。
#   task_dict 本身**零 HA 依赖**，所以可以独立加载与单测。
_SPEC = importlib.util.spec_from_file_location(
    "_lixiang_task_dict",
    Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "task_dict.py",
)
td = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(td)

FIXTURE = Path(__file__).parent / "fixtures" / "task_dict_real.json"


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def norm(raw: dict) -> dict:
    return td.normalize(raw)


class TestNormalizeRealPayload:
    def test_groups_preserved(self, norm):
        """分类必须原样保留（UI 按分类展示）。"""
        assert [g["classification"] for g in norm["conditions"]][:3] == [
            "ConditionTimes", "ConditionEnvironments", "ConditionLocations"]

    def test_items_flattened(self, norm):
        """两层 → 每组带 items 列表。"""
        first = norm["conditions"][0]
        assert "items" in first and isinstance(first["items"], list)
        assert [i["type"] for i in first["items"]][:2] == ["Time", "Sunrise"]

    def test_null_params_becomes_empty_list(self, norm):
        """★ params 可能是 null —— 必须归一成 []，否则 UI 会崩。"""
        t = next(i for g in norm["conditions"] for i in g["items"] if i["type"] == "Time")
        assert t["params"] == [], "params=null 应归一为空列表"

    def test_param_template_kept(self, norm):
        """★ 参数模板（key/type/label/可选值）必须保留 —— 这是不用手填 JSON 的关键。"""
        sunrise = next(i for g in norm["conditions"] for i in g["items"] if i["type"] == "Sunrise")
        keys = [p["key"] for p in sunrise["params"]]
        assert "op" in keys and "duration" in keys
        op = next(p for p in sunrise["params"] if p["key"] == "op")
        assert op["type"] == "singleChoiceList"
        assert op["value"] == ["before", "after"], "可选值应保留（UI 渲染成下拉）"

    def test_datasource_kept(self, norm):
        it = next(i for g in norm["conditions"] for i in g["items"] if i["type"] == "Sunrise")
        assert it["source"] == "clo"
        mob = next(i for g in norm["conditions"] for i in g["items"] if i["type"] == "Time")
        assert mob["source"] == "mob"

    def test_scale_is_not_15(self, norm):
        """★ 回归防护：早期把「15 分类」当成「15 条件」写进注释，实测条目数远多于此。"""
        c, a = td.count_items(norm)
        assert c > 15, f"条件条目应远多于分类数，实际 {c}"
        assert a > 15, f"动作条目应远多于分类数，实际 {a}"

    def test_missing_or_bad_payload(self):
        """坏数据不能抛异常，也不能造出假内容。"""
        assert td.normalize({}) == {"conditions": [], "actions": []}
        assert td.normalize({"conditions": [{"functions": None}]})["conditions"] == []
        assert td.normalize(None)["conditions"] == []
        # code != 0 的响应：normalize 不应凭空生成条目
        bad = td.normalize({"code": 100012, "msg": "没有接口访问权限", "data": {}})
        assert bad["conditions"] == []


class TestVehicleOnlyItems:
    """dataSource=veh 的条目我们通常无权创建 → UI 要能标出来。"""

    def test_extracts_veh_items(self, norm):
        v = td.requires_vehicle_data(norm)
        flat = [x for lst in v.values() for x in lst]
        assert flat, "真实字典里应有 veh 类条目"
        # 抽样：眼镜/语音命令属车辆配置
        assert any("Glasses" in x for x in flat) or any("VoiceCommand" in x for x in flat)


class TestPersistence:
    def test_roundtrip(self, tmp_path, norm):
        assert td.save(str(tmp_path), norm)
        back = td.load(str(tmp_path))
        assert back is not None
        assert td.count_items(back) == td.count_items(norm)

    def test_file_name_and_perms(self, tmp_path, norm):
        td.save(str(tmp_path), norm)
        p = tmp_path / "lixiang_task_dict.json"
        assert p.exists()
        assert oct(p.stat().st_mode)[-3:] == "600", "应仅属主可读（同 identity.py）"

    def test_saved_at_recorded(self, tmp_path, norm):
        td.save(str(tmp_path), norm)
        assert isinstance(td.load(str(tmp_path))["saved_at"], int)

    def test_atomic_write_leaves_no_tmp(self, tmp_path, norm):
        td.save(str(tmp_path), norm)
        assert not (tmp_path / "lixiang_task_dict.json.tmp").exists()

    def test_missing_file(self, tmp_path):
        assert td.load(str(tmp_path)) is None

    def test_corrupt_file_recovers(self, tmp_path):
        (tmp_path / "lixiang_task_dict.json").write_text("{ 这不是 json", encoding="utf-8")
        assert td.load(str(tmp_path)) is None, "损坏应返回 None（触发重拉），不能抛异常"

    def test_wrong_shape_rejected(self, tmp_path):
        (tmp_path / "lixiang_task_dict.json").write_text('{"foo":1}', encoding="utf-8")
        assert td.load(str(tmp_path)) is None


class TestFreshness:
    def test_fresh_not_stale(self, norm):
        assert td.is_stale(td.save and dict(norm, saved_at=int(time.time()))) is False

    def test_old_is_stale(self, norm):
        old = dict(norm, saved_at=int(time.time()) - 30 * 86400)
        assert td.is_stale(old) is True

    def test_missing_timestamp_is_stale(self, norm):
        """无时间戳 → 宁可多拉一次（宁可慢，不可陈旧）。"""
        assert td.is_stale(dict(norm)) is True


class TestDescribe:
    def test_describe_contains_counts(self, tmp_path, norm):
        td.save(str(tmp_path), norm)
        d = td.describe(td.load(str(tmp_path)))
        assert "条件" in d and "动作" in d
        c, a = td.count_items(norm)
        assert str(c) in d and str(a) in d

    def test_describe_none(self):
        assert td.describe(None) == "未获取"


class TestWiring:
    """守卫：防止"写了模块但没接上"。

    ★ 用 AST / 源码而非 import —— `li_api` 依赖 homeassistant，本机无该模块。
    """

    LI_API = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "li_api.py"
    COORD = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "coordinator.py"
    INIT = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "__init__.py"
    SENSOR = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto" / "sensor.py"

    def test_endpoint_has_v1(self):
        """★ 路径必须带 /v1/ —— 漏掉返回 100012，与无权限无法区分（实测踩过）。"""
        src = self.LI_API.read_text(encoding="utf-8")
        m = re.search(r'EP_TASK_DICT\s*=\s*"([^"]+)"', src)
        assert m, "找不到 EP_TASK_DICT 常量"
        assert "/v1/task-basic/mob/condition-and-action/" in m.group(1), (
            "字典端点必须带 /v1/，否则服务端返回 100012（与无权限无法区分）")

    def test_api_has_get_task_dict(self):
        src = self.LI_API.read_text(encoding="utf-8")
        assert re.search(r"def get_task_dict\(", src), "li_api 必须提供 get_task_dict()"

    def test_get_task_dict_returns_none_on_failure(self):
        """★ 取不到时返回 None（调用方保留旧缓存），不能抛异常也不能返回空字典冒充成功。"""
        src = self.LI_API.read_text(encoding="utf-8")
        i = src.index("def get_task_dict(")
        blk = src[i:i + 1200]
        assert "return None" in blk, "失败路径应返回 None"
        assert blk.index("return None") < blk.index("return r"), \
            "失败分支必须在成功返回之前"

    def test_coordinator_exposes_dict(self):
        s = self.COORD.read_text(encoding="utf-8")
        assert "def async_load_task_dict" in s
        assert "def async_refresh_task_dict" in s
        assert "task_dict_error" in s

    def test_startup_calls_load(self):
        assert "async_load_task_dict()" in self.INIT.read_text(encoding="utf-8"), \
            "启动时必须加载字典（否则新建任务表单永远空）"

    def test_sensor_exposes_dict_summary(self):
        assert '"字典"' in self.SENSOR.read_text(encoding="utf-8"), \
            "字典获取情况应出现在诊断属性里（取不到要可见，不静默）"

    def test_config_dir_handles_callable_path(self):
        """★ `hass.config.path` 在新版 HA 是**方法** —— 直接当属性取会拿到
        bound method，导致 os.path.join 抛 TypeError、字典永远不落盘（实测踩过）。
        """
        src = self.COORD.read_text(encoding="utf-8")
        assert "def _config_dir(" in src, "必须有统一的配置目录取法"
        i = src.index("def _config_dir(")
        blk = src[i:i + 700]
        assert "callable(" in blk, "必须处理 path 是方法的情况"
        assert 'getattr(cfg, "path", None)' in blk

    def test_failure_does_not_wipe_cache(self):
        """★ 拉取失败必须保留旧字典 —— 服务端临时不可用不该让 UI 空掉。"""
        s = self.COORD.read_text(encoding="utf-8")
        i = s.index("async def async_refresh_task_dict")
        blk = s[i:i + 1800]
        assert blk.count("self._task_dict = ") == 1, \
            "只能在成功路径赋值（多处赋值意味着某条失败路径会清空缓存）"
        assert 'if not norm.get("conditions")' in blk, "空字典应拒绝并保留缓存"
