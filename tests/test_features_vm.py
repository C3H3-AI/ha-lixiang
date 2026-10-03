"""variableModel 解析测试（2026-09-26 新增）

背景：GET /saos-vehicle-api/v2-0/vehicles/basics 的 vehicleInfo.variableModel
     返回【中文配置串】，比 App 的 ConfigCode（编码，需服务端字典）更易读。

实测我们的车（理想L6 Pro）：
  "AD PRO+无踏板+电池CATL+后驱汇川+伯特利后卡钳+天纳克减振器
   +西菱增压器+德赛XCU+威孚催化剂+斯泰必鲁斯背门撑杆+无冰箱+高级音响"
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_features():
    """加载 features.py（绕过 __init__.py 的 HA 依赖）。

    ★ 2026-09-26：features.py 现在 import 了 vehicle_ability，
      需要一并注入（先加载 vehicle_ability，再作为模块属性提供给 features）。
    """
    integ = (Path(__file__).resolve().parent.parent
             / "custom_components" / "lixiang_auto")

    # ① 先加载 vehicle_ability（注入到 sys.modules 的一个假包里）
    va_src = (integ / "vehicle_ability.py").read_text(encoding="utf-8")
    va_src = va_src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    va_src = va_src.replace(
        '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
        f'_CONFIG_DIR = Path({str(integ / "vehicle_configs")!r})')
    va_mod = types.ModuleType("va_for_features")
    exec(compile(va_src, "vehicle_ability.py", "exec"), va_mod.__dict__)

    # ② 加载 features.py，把 relative import 换成对 va_mod 的直接引用
    src = (integ / "features.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace(
        "from .vehicle_ability import VehicleAbility, get_ability",
        "VehicleAbility = _VA_MOD.VehicleAbility\nget_ability = _VA_MOD.get_ability")
    mod = types.ModuleType("feat_test")
    mod.__dict__["_VA_MOD"] = va_mod
    exec(compile(src, "features.py", "exec"), mod.__dict__)
    return mod


feat = _load_features()

# 实测样本
L6_PRO = ("AD PRO+无踏板+电池CATL+后驱汇川+伯特利后卡钳+天纳克减振器"
          "+西菱增压器+德赛XCU+威孚催化剂+斯泰必鲁斯背门撑杆+无冰箱+高级音响")


class TestParseVariableModel:
    def test_real_l6_sample(self):
        """实测样本：L6 Pro（无冰箱、无踏板）"""
        r = feat.parse_variable_model(L6_PRO)
        assert r["autopilot"] == "AD PRO"
        assert r["battery"] == "电池CATL"
        assert r["drive"] == "后驱汇川"
        assert r["factors"]["冰箱"] is False
        assert r["factors"]["电动踏板"] is False

    def test_empty_and_none(self):
        assert feat.parse_variable_model("")["factors"] == {}
        assert feat.parse_variable_model(None)["factors"] == {}

    def test_negative_wins_over_positive(self):
        """★ 关键：「无冰箱」必须优先于「冰箱」"""
        r = feat.parse_variable_model("AD MAX+无冰箱+电池宁德")
        assert r["factors"]["冰箱"] is False, "无冰箱 应覆盖 冰箱"

    def test_positive_fridge(self):
        r = feat.parse_variable_model("AD MAX+有冰箱+电池宁德")
        assert r["factors"]["冰箱"] is True

    def test_pedal_distinguished(self):
        """「无踏板」vs「踏板」"""
        assert feat.parse_variable_model("AD MAX+无踏板")["factors"]["电动踏板"] is False
        # 有踏板（不带"无"）
        r2 = feat.parse_variable_model("AD MAX+电动踏板+电池宁德")
        assert r2["factors"]["电动踏板"] is True

    def test_raw_parts(self):
        r = feat.parse_variable_model("A+B+C")
        assert r["raw"] == ["A", "B", "C"]

    def test_unknown_string_returns_empty_factors(self):
        r = feat.parse_variable_model("完全无关的配置串")
        assert r["factors"] == {}

    def test_air_suspension(self):
        r = feat.parse_variable_model("AD MAX+空气悬架")
        assert r["factors"]["空气悬架"] is True


class TestVariableModelFactors:
    def test_uses_get_vehicles(self):
        """_variable_model_factors 从 get_vehicles 拿数据。"""
        class FakeApi:
            def get_vehicles(self):
                return [{"vehicleInfo": {"variableModel": L6_PRO}}]
        f = feat._variable_model_factors(FakeApi())
        assert f["冰箱"] is False
        assert f["电动踏板"] is False

    def test_handles_empty(self):
        class EmptyApi:
            def get_vehicles(self):
                return []
        assert feat._variable_model_factors(EmptyApi()) == {}

    def test_handles_exception(self):
        class BadApi:
            def get_vehicles(self):
                raise RuntimeError("boom")
        assert feat._variable_model_factors(BadApi()) == {}

    def test_handles_missing_field(self):
        class NoVmApi:
            def get_vehicles(self):
                return [{"vehicleInfo": {}}]
        assert feat._variable_model_factors(NoVmApi()) == {}
