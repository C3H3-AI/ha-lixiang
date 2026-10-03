"""保养项属性提取测试（2026-10-03）。

## 背景

旧实现查的 4 个字段 **在服务端返回的 JSON 里根本不存在**：

    higherLevel / lowerLevel / percentage / remainMileage

所以那些属性长期为空 —— 卡片上只有状态文本「剩余 N km」能用
（那是 render_value 用正则从文本里提的，不是结构化数据）。

依据抓包 `vss_full_state.json`：`Vehicle.Carcenter.Maintain.*` 每项
返回 **33 个字段**，本文件钉住其中对用户有意义的那些。

## 关键换算（不做用户会看不懂）

- `maintainLeftDays` 单位是**毫秒**（实测 27388800000 ≈ 317 天）
- `maintainDueDate` 是 `YYYYMMDD`；`"--"`/缺省表示**无到期日**
  （火花塞就是只看里程不看时间）→ 必须跳过而不是显示 `--`
- `maintenanceValid` 0/1 → 「是/否」（该项在 App 里是否显示）
- `periodMonth` 对无时间项的保养是**哨兵值** `-2147483647`
  → 现状：会原样上抛（见 test_known_sentinel_leak 记录这一事实）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SENSOR = ROOT / "custom_components" / "lixiang_auto" / "sensor.py"


def _load_maint_attrs():
    """从 sensor.py 提取 _MAINT_FIELDS + _maint_attrs（避免 HA 依赖链）。"""
    src = SENSOR.read_text(encoding="utf-8")
    start = src.index("_MAINT_FIELDS: tuple")
    end = src.index("def _mk(key, spec):")
    ns: dict = {}
    exec(src[start:end], ns)  # noqa: S102
    return ns["_maint_attrs"]


MAINT = _load_maint_attrs()


# 真实字段样本（值用构造数，结构照抓包）
FULL = {
    "name": "增程器小保养",
    "langName": {"CN": "增程器小保养", "US": "Range Extender Minor"},
    "maintainLeftMileage": 12345.6,
    "maintainLeftDays": 27388800000,      # 毫秒 → 317 天
    "maintainDueDate": 20270719,
    "maintenanceValid": 1,
    "periodMileage": 10000,
    "periodMonth": 12,
    "mileageSource": "engine",
    "engineMileage": 6536.2,
    "mileage": 61277.8,
    "maintenanceMileage": 56539.0,
    "rule": "noRemind",
    # 下面这些属于内部标记，不应上抛
    "iconUri": "android.resource://x/y",
    "dateColor": "#66FFFFFF",
    "payloadId": 1,
    "timestamp": 1788606125462,
}


class TestFieldExtraction:
    def test_core_fields(self):
        a = MAINT(FULL)
        assert a["剩余里程"] == 12345.6
        assert a["到期日"] == "2027-07-19"
        assert a["保养周期里程"] == 10000
        assert a["保养周期月数"] == 12
        assert a["计程来源"] == "增程器里程"
        assert a["累计里程"] == 61277.8

    def test_days_converted_from_ms(self):
        """毫秒必须换算成「天」—— 直接显示 27388800000 用户看不懂。"""
        a = MAINT(FULL)
        assert a["剩余天数"] == "317 天"
        assert a["剩余天数(数值)"] == 317

    def test_valid_to_chinese(self):
        assert MAINT({**FULL, "maintenanceValid": 1})["是否显示"] == "是"
        assert MAINT({**FULL, "maintenanceValid": 0})["是否显示"] == "否"

    def test_mileage_source_mapped(self):
        assert MAINT({**FULL, "mileageSource": "total"})["计程来源"] == "总里程"
        assert MAINT({**FULL, "mileageSource": "engine"})["计程来源"] == "增程器里程"

    def test_internal_fields_not_exposed(self):
        """内部标记不上抛（否则实体属性会被 33 个字段淹没）。"""
        a = MAINT(FULL)
        for k in ("iconUri", "dateColor", "payloadId", "timestamp", "langName"):
            assert k not in a, f"{k} 不应上抛"


class TestEdgeCases:
    def test_no_due_date_skipped(self):
        """火花塞的 maintainDueDate 是 "--" —— 必须跳过，不能显示 "--"。"""
        a = MAINT({**FULL, "maintainDueDate": "--"})
        assert "到期日" not in a

    def test_no_days_skipped(self):
        """无期限项（负/哨兵值）不显示天数。"""
        a = MAINT({**FULL, "maintainLeftDays": -9223372036854775807})
        assert "剩余天数" not in a
        assert "剩余天数(数值)" not in a

    def test_missing_fields_ok(self):
        """字段缺失不应崩 —— 只输出存在的。"""
        a = MAINT({"name": "x"})
        assert a == {}

    def test_non_numeric_days_ok(self):
        assert "剩余天数" not in MAINT({**FULL, "maintainLeftDays": "abc"})

    def test_seven_digit_date_rejected(self):
        assert "到期日" not in MAINT({**FULL, "maintainDueDate": 2027071})

    def test_sentinel_period_filtered(self):
        """无时间项的保养用哨兵值表示「无周期」，实测 periodMonth = -2147483647。

        原样上抛会让卡片显示「保养周期月数: -2147483647」—— 纯噪音，必须过滤。
        （这条曾是 xfail，修掉哨兵后转为正常断言。）
        """
        a = MAINT({**FULL, "periodMonth": -2147483647})
        assert "保养周期月数" not in a, "哨兵值不应上抛"

    def test_sentinel_period_mileage_filtered(self):
        assert "保养周期里程" not in MAINT({**FULL, "periodMileage": -1})
        assert "保养周期里程" not in MAINT({**FULL, "periodMileage": 2147483647})

    def test_normal_period_kept(self):
        a = MAINT({**FULL, "periodMonth": 12, "periodMileage": 10000})
        assert a["保养周期月数"] == 12
        assert a["保养周期里程"] == 10000


class TestOldFieldsGone:
    def _code_only(self) -> str:
        """只取代码行（去掉注释）。

        ★ 必须这样：注释里**故意**写了那 4 个旧字段名来说明「它们不存在」，
          直接子串匹配会命中注释，导致断言恒真/恒假。
          （这正是 skill 里记过的「注释里的字符串让子串断言失效」陷阱。）
        """
        src = SENSOR.read_text(encoding="utf-8")
        seg = src[src.index("_MAINT_FIELDS: tuple"):src.index("def _mk(key, spec):")]
        return "\n".join(
            ln for ln in seg.splitlines()
            if not ln.lstrip().startswith("#")
        )

    def test_old_bogus_fields_dropped(self):
        """旧实现查的 4 个字段不存在 —— 确认新代码不再引用它们。"""
        code = self._code_only()
        for bogus in ("higherLevel", "lowerLevel", "percentage", "remainMileage"):
            assert bogus not in code, f"代码仍在引用不存在的字段 {bogus}"

    def test_real_fields_present(self):
        src = SENSOR.read_text(encoding="utf-8")
        seg = src[src.index("_MAINT_FIELDS: tuple"):src.index("def _mk(key, spec):")]
        for real in ("maintainLeftMileage", "maintainLeftDays", "maintainDueDate",
                     "maintenanceValid", "periodMileage", "mileageSource"):
            assert real in seg, f"缺真实字段 {real}"
