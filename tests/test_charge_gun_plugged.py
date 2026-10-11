"""充电枪插枪判定守卫测试（2026-10-11 新增）

背景（用户实测报告）
-------------------
「没有插入充电枪也会判断插上」——交流/直流枪 binary_sensor 频繁误报已插入。
根因：`Semantics.PLUGGED` 分支用宽松规则 `n != 0`，而真实信号存在
非插枪的非零态（AC=1 / DC=2 / -1 …），全部被误判为 on。

证据（App 反汇编实证，非推断）
------------------------------
用 androguard 反汇编理想汽车 APK（com.chehejia.oc.m01），
`LXLiMeshStateDelegate` 四个方法交叉一致：

    getChargeCurrent    AC == 2 → 取交流电流；DC == 1 → 取 OGC 电流
    getChargeVoltage    AC == 2 / DC == 1（同构）
    getChargingMode     DC == 1 → 直流模式；AC == 2 → 交流模式
    getChargingStatus   v3(AC) vs 2、v5(DC) vs 1（含预约 state==1）

即：**ACChgrActualConnSts==2 才算交流插枪，DCChrgngGunActuSts==1 才算直流插枪**
（XChargeDataHandle.smali:102 的 AC==2 引用与此一致）。
translations 旧表把 1、2 双双标成「已插入」是误报的第二来源。

本文件守卫的不变量
------------------
① AC：0/1/3/-1 → False（1 是旧误报源），2 → True，缺值 → None
② DC：0/2/3/-1 → False（2 是旧误报源），1 → True
③ 字符串数字按数值判定（服务端偶发 "2" 形态）
④ 门/锁语义回归不受影响（DOOR_OPEN==1、LOCKED 非0）
⑤ translations 两表与判定逐字段一致（防两处再分叉）

变异验收（已执行）
------------------
删掉 binary_sensor PLUGGED 分支的精确匹配（还原为 return n != 0）
→ 本文件 6 条断言失败；恢复后全绿。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


# ---------------------------------------------------------------------------
# 最小 HA 桩 + 隔离加载（与 test_charge_readonly 同模式，按需增补 binary_sensor）
# ---------------------------------------------------------------------------

class _Meta(type):
    def __getattr__(cls, n):
        return n


def _install_ha_stubs() -> None:
    def _mod(name: str, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    class _Base:
        def __init__(self, *a, **k):
            pass

    class _CoordinatorEntity:
        def __init__(self, coordinator=None, *a, **k):
            self.coordinator = coordinator

        @property
        def available(self):
            return True

    class _Entity:
        _attr_has_entity_name = False

        def async_write_ha_state(self):
            pass

    class BinarySensorDeviceClass(metaclass=_Meta):
        pass

    class BinarySensorEntity:
        pass

    class BinarySensorEntityDescription:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class EntityCategory(metaclass=_Meta):
        pass

    ha = _mod("homeassistant")
    ha.__path__ = []
    _mod("homeassistant.const", EntityCategory=EntityCategory)
    _mod("homeassistant.core", HomeAssistant=_Base, callback=lambda f: f)
    _mod("homeassistant.exceptions", HomeAssistantError=Exception)
    _mod("homeassistant.config_entries", ConfigEntry=_Base)
    for extra in ("homeassistant.helpers", "homeassistant.util",
                  "homeassistant.util.dt", "homeassistant.components"):
        m = _mod(extra)
        m.__path__ = []
    _mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=_Base)
    _mod("homeassistant.helpers.update_coordinator", CoordinatorEntity=_CoordinatorEntity,
         CoordinatorUpdateFailed=Exception)
    _mod("homeassistant.helpers.device_registry", DeviceInfo=dict,
         async_get=lambda *a, **k: None)
    _mod("homeassistant.components.binary_sensor",
         BinarySensorDeviceClass=BinarySensorDeviceClass,
         BinarySensorEntity=BinarySensorEntity,
         BinarySensorEntityDescription=BinarySensorEntityDescription)


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(
        f"lixiang_auto.{mod_name}", _INTEG / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"lixiang_auto.{mod_name}"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mods():
    _install_ha_stubs()
    pkg = types.ModuleType("lixiang_auto")
    pkg.__path__ = [str(_INTEG)]
    sys.modules["lixiang_auto"] = pkg
    out = {}
    for name in ("const", "signals", "entity_helper", "binary_sensor", "translations"):
        try:
            out[name] = _load(name)
        except Exception as e:  # noqa: BLE001 — device 等重依赖模块可缺席
            print(f"load {name} failed: {e}")
    assert "binary_sensor" in out and "signals" in out
    return out


def _gun(mods, key: str, value) -> bool | None:
    """真实构造实体并执行 is_on（不打桩行为，只桩 import 面）。"""
    signals = mods["signals"]
    spec = signals.SIGNALS[key]
    desc = signals.to_binary_description(spec)
    vss = {key: {"value": value}}
    coord = types.SimpleNamespace(data={"vss": vss})
    ent = mods["binary_sensor"].LiCarBinarySensor(coord, desc, spec, "TESTVIN0000000001")
    return ent.is_on


class TestACGunPlugged:
    """交流枪：App 实证 ACChgrActualConnSts == 2 才是插枪。"""

    @pytest.mark.parametrize("value,expected", [
        (0, False),      # 未插（真实快照实测值）
        (1, False),      # ★ 旧 n!=0 规则的误报源
        (2, True),       # App 判定的插枪态
        (3, False),      # 其他非插枪态
        (-1, False),     # 负值哨兵（旧规则会误报）
        ("1", False),    # 字符串形态
        ("2", True),
    ])
    def test_ac_values(self, mods, value, expected):
        assert _gun(mods, "charge_gun_ac", value) is expected

    def test_ac_missing_is_none(self, mods):
        assert _gun(mods, "charge_gun_ac", None) is None


class TestDCGunPlugged:
    """直流枪：App 实证 DCChrgngGunActuSts == 1 才是插枪。"""

    @pytest.mark.parametrize("value,expected", [
        (0, False),      # 未插（真实快照实测值）
        (1, True),       # App 判定的插枪态
        (2, False),      # ★ 旧 n!=0 规则的误报源
        (3, False),
        (-1, False),
        ("1", True),
        ("2", False),
    ])
    def test_dc_values(self, mods, value, expected):
        assert _gun(mods, "charge_gun_dc", value) is expected


class TestRegression:
    """相邻语义不得被波及（同一 is_on 函数的其他分支）。"""

    def test_door_open_semantics(self, mods):
        assert _gun(mods, "door_main", 1) is True
        assert _gun(mods, "door_main", 2) is False   # ==1 才开（尾门 2 陷阱）

    def test_lock_semantics(self, mods):
        assert _gun(mods, "lock_main", 0) is False   # 已落锁
        assert _gun(mods, "lock_main", 1) is True    # 未落锁


class TestTranslationsConsistent:
    """翻译表必须与判定同口径（误报的第二来源就是旧表 1/2 双「已插入」）。"""

    def test_tables_match_app_evidence(self, mods):
        tr = mods["translations"]
        tbl = None
        for attr in dir(tr):
            v = getattr(tr, attr)
            if isinstance(v, dict) and "ACChgrActualConnSts" in v:
                tbl = v
                break
        assert tbl is not None, "未找到翻译表"
        assert tbl["ACChgrActualConnSts"] == {0: "充电枪未插入", 2: "充电枪已插入"}
        assert tbl["DCChrgngGunActuSts"] == {0: "充电枪未插入", 1: "充电枪已插入"}
