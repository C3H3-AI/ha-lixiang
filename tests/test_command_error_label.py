"""车控失败的「部件名 + 原因」提示（2026-10-12）。

车主实测
--------
点「充电盖」开关，HA 只显示：

    「命令执行失败 (cpCtrl): pushState=7 resultCode=-2 msg=执行失败（set signal err!）」

看不出**是哪个功能**、**为什么**。车主追问：

> app提示是充电口盖已开启，请前往手动关闭。这些存在提示app里面应该有对照表的。

**查证结论（车主是对的）**：App 那句话是**两段拼出来的**，不是单条文案 ——

| 拼图 | 位置 | 实测内容 |
|---|---|---|
| 部件中文名 | **VSS 路径表** `spec_X01-VSS-Path_148.json` | `Vehicle.Body.DoorSwitchStatus.ChrgPorLidStsV2.description` = "充电口盖开启状态新信号" |
| 提示模板 | **RN bundle** 的 Hermes 字符串表 | `"请前往手动关闭"` |
| 完整句 | **任何地方都没有** | → 拼接生成 |

★ 关键教训：Hermes 字节码的字符串是 **UTF-16** 存储的。
  只用 UTF-8 搜「充电口盖」会 0 命中，从而误判成"App 自己生成的"。
  换 UTF-16 搜才有 —— 这条测试把教训固化成断言。

实现上**不引入**那张 541 KB 的 VSS 表（只为几个名字不划算）——
实体名本身就是中文，直接拼。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "lixiang_auto"
LI_API = PKG / "li_api.py"

#: 所有会下发车控命令的平台（都要给用户报出"是哪个部件"）
PLATFORMS = ("switch.py", "lock.py", "cover.py", "climate.py", "fan.py",
             "button.py", "number.py", "select.py", "time.py")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _label_module():
    """导入 li_api —— 但先 stub 掉 homeassistant。

    `li_api.py` 顶层 `from homeassistant.exceptions import HomeAssistantError`，
    测试环境没有 HA 包 → 直接用 `unittest.mock` 造个壳，
    这样就能**真实调用** label_command_error（而不是测一份复制品）。
    """
    import sys
    import types
    from unittest.mock import MagicMock

    if "homeassistant" not in sys.modules:
        ha = types.ModuleType("homeassistant")
        ha_exc = types.ModuleType("homeassistant.exceptions")

        class HomeAssistantError(Exception):
            pass

        ha_exc.HomeAssistantError = HomeAssistantError
        # 其他可能被顶层引用的子模块，统一给 MagicMock
        for name in ("homeassistant.core", "homeassistant.helpers",
                     "homeassistant.helpers.storage", "homeassistant.util",
                     "homeassistant.config_entries", "homeassistant.const"):
            sys.modules.setdefault(name, MagicMock())
        sys.modules["homeassistant"] = ha
        sys.modules["homeassistant.exceptions"] = ha_exc

    # li_api.py 里有相对导入（from .const import ...）→ 必须让它作为**包内模块**加载。
    # 直接 import 包又会执行 lixiang_auto/__init__.py（依赖大量 HA API），
    # 所以造一个只带 __path__ 的假包，跳过 __init__。
    if "lixiang_auto" not in sys.modules:
        pkg = types.ModuleType("lixiang_auto")
        pkg.__path__ = [str(PKG)]
        sys.modules["lixiang_auto"] = pkg

    import importlib
    return importlib.import_module("lixiang_auto.li_api")


class TestLabelCommandError:
    def test_message_contains_label(self):
        m = _label_module()
        err = m.LiCommandError("命令执行失败 (cpCtrl): resultCode=-2",
                               request_id="r1", result_code=-2, push_state=7)
        out = m.label_command_error("充电盖", err)
        assert "充电盖" in str(out), "部件名没进消息"
        assert "resultCode=-2" in str(out), "原始错误信息丢了"

    def test_preserves_result_code_and_push_state(self):
        """★ 必须保留结构化字段 —— 自动化里靠它们判断，不能只换个消息。"""
        m = _label_module()
        err = m.LiCommandError("x", request_id="rid", result_code=-2, push_state=7)
        out = m.label_command_error("车锁", err)
        assert isinstance(out, m.LiCommandError)
        assert out.result_code == -2
        assert out.push_state == 7
        assert out.request_id == "rid"

    def test_subclass_preserved(self):
        """LiChannelNotSupported 这类子类要尽量保持类型。"""
        m = _label_module()
        err = m.LiChannelNotSupported("走高通道", result_code=2009, push_state=7)
        out = m.label_command_error("充电", err)
        assert isinstance(out, m.LiCommandError)
        assert out.result_code == 2009

    def test_empty_label_returns_original(self):
        m = _label_module()
        err = m.LiCommandError("x", result_code=-2)
        assert m.label_command_error("", err) is err

    def test_non_command_error_untouched(self):
        """非车控错误（如网络异常）原样返回，不包装。"""
        m = _label_module()
        err = ValueError("boom")
        assert m.label_command_error("车锁", err) is err

    def test_original_not_mutated(self):
        m = _label_module()
        err = m.LiCommandError("原始", result_code=-2)
        m.label_command_error("充电盖", err)
        assert str(err) == "原始", "原错误对象被改坏了"


class TestAllPlatformsLabelTheirErrors:
    """每个下发车控的平台都要在 except 里补部件名。"""

    @pytest.mark.parametrize("fn", PLATFORMS)
    def test_platform_imports_label(self, fn):
        s = _read(PKG / fn)
        assert "label_command_error" in s, f"{fn} 没补部件名（用户看不到是哪个功能失败）"

    @pytest.mark.parametrize("fn", PLATFORMS)
    def test_uses_getattr_for_name(self, fn):
        """★ 用 getattr 兜底 —— 不是所有实体类都一定定义了 `_attr_name`，
        直接 `self._attr_name` 会抛 AttributeError **掩盖真正的错误**。"""
        s = _read(PKG / fn)
        assert 'getattr(self, "_attr_name", None)' in s, \
            f"{fn} 直接访问 _attr_name（可能抛 AttributeError 掩盖原错误）"

    @pytest.mark.parametrize("fn", PLATFORMS)
    def test_raises_from_original(self, fn):
        """`raise ... from err` 保留因果链，便于排查。"""
        s = _read(PKG / fn)
        # `_label(...)` 内含嵌套括号 → 不能用 [^)]* ；逐行判断
        lines = [l for l in s.splitlines() if "raise _label(" in l]
        assert lines, f"{fn} 没有 raise _label(...)"
        assert all(l.rstrip().endswith("from err") for l in lines), \
            f"{fn} 丢了 `from err`（异常链断了）: {lines}"


    @pytest.mark.parametrize("fn", PLATFORMS)
    def test_file_assigns_attr_name(self, fn):
        """文件里必须给实体设过 `_attr_name`（值可能是构造参数，不一定是字面量）。"""
        s = _read(PKG / fn)
        assert "_attr_name" in s, f"{fn} 没有 _attr_name"

    def test_fallback_names_are_chinese(self):
        """★ 兜底值不能是**英文字面量**（用户会看到 remoteVehPlgControl 这种东西）。

        允许 `CMD_*` / `self.xxx` 这类内部值 —— 它们只在 `_attr_name` 为空时
        才会用到，而各实体类都定义了中文 `_attr_name`（见下面的测试）。
        """
        bad = []
        for fn in PLATFORMS:
            s = _read(PKG / fn)
            for m in re.finditer(
                    r'_label\(getattr\(self, "_attr_name", None\) or ([^,]+), err\)', s):
                val = m.group(1).strip()
                if val[:1] in ('"', "'") and not re.search(r'[\u4e00-\u9fff]', val):
                    bad.append(f"{fn}:{val}")
        assert not bad, f"这些兜底名是英文字面量（用户看不懂）: {bad}"


class TestHermesEncodingLesson:
    """★ 教训固化：Hermes 字节码字符串是 UTF-16 的。

    这条防止以后有人再次用「UTF-8 搜不到」得出"App 没有这个文案"的错误结论。
    """

    def test_doc_records_the_encoding_trap(self):
        s = _read(LI_API)
        assert "UTF-16" in s or "utf-16" in s, \
            "没记录 Hermes 字符串是 UTF-16 的关键教训"

    def test_doc_records_two_piece_origin(self):
        """要写明文案是「VSS 表中文名 + bundle 模板」两段拼的。"""
        s = _read(LI_API)
        assert "VSS" in s, "没说明部件名来自 VSS 路径表"
        assert "Hermes" in s or "RN bundle" in s, "没说明模板来自 RN bundle"

    def test_doc_explains_why_not_import_vss_table(self):
        """说明为什么**不**引入那张 541KB 的表（否则后人会想"为什么不直接用"）。"""
        s = _read(LI_API)
        assert "541" in s or "KB" in s, "没说明不引入 VSS 表的原因"
