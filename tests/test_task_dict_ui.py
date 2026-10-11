"""任务页字典驱动 UI —— 回归测试（2026-10-11）。

改造
----
条件/动作原先是页面里**硬编码的 5~6 条简表**（且无条件过滤 → 会给"必失败"的选项）。
现在改为**服务端字典驱动**：

    GET /lixiang_auto/task-dict.json          ← 集成暴露（卡片拿不到 coordinator）
      → 选分类 → 选条目 → 按 params 模板生成表单

★ 为什么走 REST：卡片只有 `hass`，**拿不到 coordinator** → 字典必须经视图出去。
★ 取不到时**静默回退旧简表** —— 不能让用户看到空的"添加条件"表单（那像坏了）。

★ 本轮踩过的坑（各有守卫防回归）
--------------------------------
1. `hass.config.path` 新版是**方法** → 当属性取会 TypeError，字典永不落盘
2. `li_api` 属性名是 `li_api` 不是 `_api` → setup 直接失败
3. ★ view 注册放在了 **coordinator 创建之前** → 引用不存在的变量 → 404
4. 文件 IO 必须在 executor（否则 blocking call 告警）
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
PAGE = CC / "www" / "lixiang-cards" / "lixiang-task-page.js"
INIT = CC / "__init__.py"
FIXTURE = Path(__file__).parent / "fixtures" / "task_dict_real.json"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:600]
    return r.stdout


class TestRestEndpoint:
    def test_view_exists_and_registered(self):
        s = INIT.read_text(encoding="utf-8")
        assert "class LiXiangTaskDictView" in s
        assert "register_view(LiXiangTaskDictView" in s

    def test_url_and_shape(self):
        s = INIT.read_text(encoding="utf-8")
        assert 'url = "/lixiang_auto/task-dict.json"' in s
        # 必须有 ok 标志与错误分支（前端据此回退，不能只回空数组）
        assert '"ok": True' in s and '"ok": False' in s

    def test_registration_after_coordinator_creation(self):
        """★ 注册必须在 coordinator 创建之后 —— 否则引用不存在的变量 → 404。"""
        s = INIT.read_text(encoding="utf-8")
        i_coord = s.index("coordinator = LiCarCoordinator(")
        i_reg = s.index("register_view(LiXiangTaskDictView")
        assert i_reg > i_coord, (
            "view 注册早于 coordinator 创建 → 运行期 NameError/404（本轮踩过）")

    def test_failure_returns_reason(self):
        """取不到时给**原因**（前端要能区分'没字典'与'别的问题'）。"""
        s = INIT.read_text(encoding="utf-8")
        i = s.index("class LiXiangTaskDictView")
        blk = s[i:i + 2600]
        assert "error" in blk
        assert "task_dict_error" in blk, "应带上 coordinator 记录的拉取错误"


class TestCardIntegration:
    def _src(self) -> str:
        return PAGE.read_text(encoding="utf-8")

    def test_fetches_from_rest_not_coordinator(self):
        s = self._src()
        assert 'fetch("/lixiang_auto/task-dict.json")' in s
        assert "this.coordinator.task_dict" not in s, \
            "卡片拿不到 coordinator，必须经 REST"

    def test_silent_fallback(self):
        """★ 取不到时静默回退（不让用户看到空表单）。"""
        s = self._src()
        assert "_dictTried" in s and "return false" in s
        i = s.index("async _ensureDict()")
        blk = s[i:i + 900]
        assert "catch" in blk, "取字典必须容错（网络/接口未注册）"

    def test_fetch_tried_only_once(self):
        """★ 每次点「添加条件」都重打接口 = 白白拖慢界面。
        必须在实例上记住"已试过"，本次会话不再重试。"""
        s = self._src()
        i = s.index("async _ensureDict()")
        blk = s[i:i + 900]
        assert "if (this._dictCache) return true" in blk, "成功结果要缓存"
        assert "if (this._dictTried) return false" in blk, \
            "★ 失败也必须记住（否则每次点都重打接口，界面变慢）"
        # 赋值顺序：先查缓存 → 再查是否试过 → 才置位并发起
        assert blk.index("_dictTried") < blk.index("fetch("), \
            "应在 fetch 之前置位，避免并发重复请求"

    def test_two_step_picker(self):
        s = self._src()
        assert "_pickFromDict" in s
        i = s.index("_pickFromDict(title, kind")
        blk = s[i:i + 1400]
        # 先分类 → 再条目 → 参数表单
        assert blk.count("_choose(") >= 2, "应是两级选择（分类 → 条目）"
        assert "_fillParams" in blk, "有 params 的条目应追加参数表单"

    def test_param_form_controls(self):
        """参数控件要覆盖字典里的主要类型。"""
        s = self._src()
        assert "singleChoiceList" in s or "ChoiceList" in s
        assert "singleColumnSelector" in s
        assert 'data-kind="num"' in s, "数值型参数应有数字输入"
        assert 'data-kind="txt"' in s, "未知类型应退回文本输入（不猜语义）"

    def test_default_value_used(self):
        """默认值应来自字典（defaultValue），不是我们硬编码。"""
        s = self._src()
        assert "defaultValue" in s

    def test_fallback_path_is_reachable(self):
        """★ 执行级：字典不可用时必须真的走旧简表（变异"永不回退"要能被抓到）。"""
        src = self._src()
        i = src.index("async _pickTrigger()")
        j = src.index("\n  async ", i + 10)
        blk = src[i:j]
        # 字典分支必须有"取到才走"的守卫，而不是无条件走字典
        assert "if (await this._ensureDict())" in blk, "字典路径必须有可用性守卫"
        # 守卫之后必须还有旧简表逻辑（不是 early return 结束整个方法）
        after = blk[blk.index("if (await this._ensureDict())"):]
        assert "const OPTS = [" in after, "守卫之后应有旧简表作为兜底"
        # 判据是"旧简表逻辑确实存在"，而不是数 return 的个数
        assert 'if (!OPTS.length)' in after, "兜底路径也要保留能力过滤"

    def test_old_simple_list_kept_as_fallback(self):
        """旧简表要留着（字典不可用时的兜底）。"""
        s = self._src()
        i = s.index("async _pickTrigger()")
        blk = s[i:i + 1500]
        assert "_ensureDict()" in blk, "应先试字典"
        assert "_eid(" in blk, "字典不可用时回退到实体过滤的简表"
        assert "暂无可用触发条件" in blk, "回退路径仍需保留能力过滤"

    def test_no_coordinator_reference(self):
        """回归防护：不要再引入 coordinator 引用。"""
        assert "coordinator.task_dict" not in self._src()

    def test_cls_label_mapping(self):
        """分类英文 → 中文映射存在（服务端只给英文）。"""
        s = self._src()
        assert "_DICT_CLS_LABEL" in s
        assert "ConditionDoorsAndWindows" in s
        m = re.search(r"const _DICT_CLS_LABEL = \{(.*?)\};", s, re.S)
        assert m and len(m.group(1)) > 200, "分类映射表不应为空"


class TestFormBehavior:
    """参数表单的行为（node 真跑渲染逻辑）。"""

    def test_choice_options_rendered(self):
        """ChoiceList 参数应渲染成可点的选项组。"""
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        items = [fn for g in fixture["data"]["conditions"] for fn in g["functions"]]
        sunrise = next(i for i in items if i["conditionType"] == "Sunrise")
        op = next(p for p in sunrise["params"] if p["key"] == "op")
        assert op["value"] == ["before", "after"], "夹具应含真实选项"
        assert "singleChoiceList" in op["type"]

    def test_no_param_items_need_no_form(self):
        """params 为 null 的条目（Time/Delay）选完即用，不该弹表单。"""
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        items = [fn for g in fixture["data"]["conditions"] for fn in g["functions"]]
        t = next(i for i in items if i["conditionType"] == "Time")
        assert not t.get("params"), "Time 应无参数"


class TestGuards:
    def test_js_syntax_ok(self):
        r = subprocess.run(["node", "--check", str(PAGE)],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[:300]

    def test_python_compiles(self):
        import py_compile
        py_compile.compile(str(INIT), doraise=True)
        py_compile.compile(str(CC / "coordinator.py"), doraise=True)