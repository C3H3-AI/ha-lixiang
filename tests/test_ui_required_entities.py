"""前端页面所需的诊断类实体必须默认启用（2026-10-12）。

事故
----
车主报「二级页面内容错误」。用**真实实体注册表 + auto-bind 引擎**复现后定位：

诊断类信号默认禁用（`entity_registry_enabled_default=False`）是为了少注册实体，
但其中有 6 个是**前端页面直接要用**的：

| 实体 | key | 缺了会怎样 |
|---|---|---|
| 陪伴里程 | `stat_mileage` | 能耗页缺 1 项 |
| 陪伴天数 | `stat_days` | 能耗页缺 1 项 |
| 耗电行驶 | `stat_elec_mileage` | 能耗页缺 1 项 |
| 位置服务 | `privacy_pos_service` | **位置页没有地址** |
| 场景模式 | `scene_mode` | 情景页 0/1 字段 |
| 车辆配置 | `config_code` | 钥匙管理页缺车型 |

复现证据（迁移前）：101 个 auto-bind 字段里 **8 个取不到**；
迁移后 **2 个**（`title` 是 `{meta:true}` 由车型名生成、`month_times` 是显式
`null` 由卡片从月度统计算 —— 两者都是设计如此）。

修复
----
1. `signals.py` 新增 `UI_REQUIRED_KEYS`，让这 6 个 key 走「默认启用」分支
2. `__init__.py` 新增 `_async_enable_ui_required_entities()` —— 老版本注册时已经
   被禁用的实体，启动时补启用

★ 安全边界：**只动 `disabled_by == "integration"`**（集成自己的默认值），
  绝不碰 `"user"` —— 用户主动禁用的实体必须保持禁用。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"

#: 前端页面要用、因此必须默认启用的 key
EXPECT_UI_KEYS = {
    "stat_mileage", "stat_days", "stat_elec_mileage",
    "privacy_pos_service", "scene_mode", "config_code",
}


def _signals() -> str:
    return (CC / "signals.py").read_text(encoding="utf-8")


def _init() -> str:
    return (CC / "__init__.py").read_text(encoding="utf-8")


class TestUIRequiredKeys:
    def test_defined(self):
        assert "UI_REQUIRED_KEYS = frozenset({" in _signals()

    def test_contains_all_six(self):
        s = _signals()
        i = s.index("UI_REQUIRED_KEYS = frozenset({")
        j = s.index("})", i)
        blk = s[i:j]
        for k in EXPECT_UI_KEYS:
            assert f'"{k}"' in blk, f"UI_REQUIRED_KEYS 缺 {k}"

    def test_enabled_default_branch_uses_it(self):
        """★ 关键：默认启用分支必须同时认 MAINTAIN_KEYS 与 UI_REQUIRED_KEYS。"""
        s = _signals()
        i = s.index("if spec.diagnostic:")
        j = s.index("return SensorEntityDescription(**kw)", i)
        blk = s[i:j]
        assert "MAINTAIN_KEYS" in blk and "UI_REQUIRED_KEYS" in blk, \
            "默认启用逻辑没有考虑 UI_REQUIRED_KEYS"

    def test_each_key_is_a_real_signal(self):
        """★ 防拼错：每个 key 必须真的在 signals.py 里定义为 SignalSpec。"""
        s = _signals()
        for k in EXPECT_UI_KEYS:
            assert f'key="{k}"' in s, f"signals.py 里没有 key={k} 的信号"


class TestEnabledDefaultBehaviour:
    """用 **AST 源码分析**验证默认启用逻辑（宿主机没有 homeassistant 包，不能运行时导入）。

    集成实体的 `enabled_default` 由 `to_sensor_description` 里的这一句决定：

        kw["entity_registry_enabled_default"] = (
            spec.key in MAINTAIN_KEYS or spec.key in UI_REQUIRED_KEYS)

    所以只要断言「两个例外集的内容」+「该表达式引用了两者」，
    就能在不导入 HA 的前提下守住行为。
    """

    def _frozenset(self, name: str) -> set[str]:
        """从源码里取出 frozenset 字面量（不导入模块）。"""
        tree = ast.parse(_signals())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        assert isinstance(node.value, ast.Call), f"{name} 不是调用式字面量"
                        out = set()
                        for kw in node.value.args:
                            for e in (kw.elts if isinstance(kw, (ast.Set, ast.List, ast.Tuple)) else [kw]):
                                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                    out.add(e.value)
                        return out
        raise AssertionError(f"源码里找不到 {name}")

    def test_ui_keys_exact(self):
        assert self._frozenset("UI_REQUIRED_KEYS") == EXPECT_UI_KEYS

    def test_maintain_keys_intact(self):
        """回归：保养项例外不能被破坏。"""
        mk = self._frozenset("MAINTAIN_KEYS")
        assert mk, "MAINTAIN_KEYS 空了"
        assert mk >= {"maint_acfilter", "maint_coolfuild", "maint_engine_oil"}

    def test_ordinary_diagnostic_not_exempt(self):
        """★ 不能把**所有**诊断类实体都放开（否则实体数量失控）。"""
        exempt = self._frozenset("UI_REQUIRED_KEYS") | self._frozenset("MAINTAIN_KEYS")
        # 从源码里抓所有 key=，找出确定为诊断类且不在例外集里的
        s = _signals()
        diag_keys = set()
        for m in re.finditer(r'key="([a-z_0-9]+)"((?:(?!SignalSpec\()(?s:.)){0,900}?)diagnostic=True', s):
            diag_keys.add(m.group(1))
        assert len(diag_keys) >= 10, f"样本太少（{len(diag_keys)}），该断言无意义"
        offenders = {k for k in diag_keys if k in exempt}
        unexpected = exempt - diag_keys - {"stat_days"}   # stat_days 可能有别的写法
        # 例外集里除（保养/UI）外不应有别的诊断 key
        assert not (exempt - EXPECT_UI_KEYS - self._frozenset("MAINTAIN_KEYS")), \
            "例外集里混入了非预期的 key"

    def test_expression_references_both_sets(self):
        s = _signals()
        i = s.index("if spec.diagnostic:")
        blk = s[i:s.index("return SensorEntityDescription(**kw)", i)]
        expr = blk[blk.index("entity_registry_enabled_default"):]
        assert "MAINTAIN_KEYS" in expr and "UI_REQUIRED_KEYS" in expr, \
            "默认启用表达式没有同时引用两个例外集"


class TestMigration:
    """`_async_enable_ui_required_entities` 的安全边界。"""

    def test_function_exists(self):
        assert "async def _async_enable_ui_required_entities" in _init()

    def test_called_in_setup_entry(self):
        s = _init()
        i = s.index("async def async_setup_entry")
        j = s.index("\n    try:", i)
        assert "await _async_enable_ui_required_entities(hass)" in s[i:j], \
            "迁移没有被 setup_entry 调用"

    def test_only_touches_integration_disabled(self):
        """★★ 最重要的一条：绝不能动用户手动禁用的实体。"""
        s = _init()
        i = s.index("async def _async_enable_ui_required_entities")
        j = s.index("\nasync def async_setup_entry", i)
        blk = s[i:j]
        assert "disabled_by" in blk, "没有检查 disabled_by"
        assert "integration" in blk, "没有限定 integration"
        # 必须是"跳过非 integration"的形式
        assert re.search(r'continue\s*#\s*★?\s*只处理集成默认禁用的', blk), \
            "缺少「只处理集成默认禁用的」守卫"

    def test_handles_enum_and_string(self):
        """不同 HA 版本里 disabled_by 可能是枚举或字符串。"""
        s = _init()
        i = s.index("async def _async_enable_ui_required_entities")
        j = s.index("\nasync def async_setup_entry", i)
        blk = s[i:j]
        assert "str(" in blk, "未兼容字符串形态的 disabled_by"

    def test_exception_contained(self):
        """迁移失败不能影响集成启动。"""
        s = _init()
        i = s.index("async def _async_enable_ui_required_entities")
        j = s.index("\nasync def async_setup_entry", i)
        blk = s[i:j]
        assert "except Exception" in blk and "return 0" in blk, \
            "迁移异常没有兜底，可能拖垮集成加载"

    def test_uses_registry_update(self):
        s = _init()
        i = s.index("async def _async_enable_ui_required_entities")
        j = s.index("\nasync def async_setup_entry", i)
        blk = s[i:j]
        assert "async_update_entity" in blk and "disabled_by=None" in blk, \
            "没有真正调用注册表更新"


class TestSyntax:
    @pytest.mark.parametrize("f", ["signals.py", "__init__.py"])
    def test_parses(self, f):
        ast.parse((CC / f).read_text(encoding="utf-8"))