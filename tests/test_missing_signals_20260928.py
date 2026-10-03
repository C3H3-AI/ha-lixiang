"""task-18 回归测试：补齐实测【有数据】的缺失 VSS 信号

背景（docs/缺失信号实测_20260928.md）
----------------------------------
从 App 的 `LxMeshVssConstant.smali` 提取全量路径，与本项目对比得 30 条缺失，
用真实会话逐条探测 → **仅 11 条有数据**，19 条无数据（L6 无此硬件）。

本任务只建 **5 条裸标量**信号对应的实体；其余不建（见 signals.py 注释）。

★ 依据版本（重要）
-----------------
必须用 `apk_latest/decompiled/`（smali_classes11），**不是**
`apk_decompile/ideal/`（smali_classes9，8.27.0 旧版）。
旧版 2119 行、**不含**这些字段；新版 2405 行、含。
本文件把行号一并断言，防止将来又读错版本。

这些测试是【防回归】的 —— 每条都对应一个具体的验收要求：
  1. 5 个信号已声明，且 path/name/行号依据正确
  2. 全部 diagnostic=True（→ 默认禁用，不污染界面）
  3. ★ binary_sensor 的 diagnostic 必须生效（本次修的 bug）
  4. 19 条无数据的【不得】声明（避免误建实体）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import signals as sg

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"

# ── App 源码依据（apk_latest，smali_classes11）──────────────────────────────
# (key, path, name, app 行号)
_NEW_BARE_SCALAR = (
    ("mirror_heat_left",
     "Vehicle.Body.RearMirro.LHeatSts", "左后视镜加热", 699),
    ("mirror_heat_right",
     "Vehicle.Body.RearMirro.RHeatSts", "右后视镜加热", 954),
    ("drv_seat_occupied",
     "Vehicle.Body.Seat.DrvSeatOccupied", "主驾有人", 1251),
    ("sunshade_front_pos",
     "Vehicle.Body.SunShade.FrontPos", "前遮阳帘位置", 624),
    ("sunshade_rear_pos",
     "Vehicle.Body.SunShade.RearPos", "后遮阳帘位置", 969),
)

# 19 条实测【无数据】→ 不得出现在 SIGNALS 里
_NO_DATA_PATHS = (
    "Vehicle.Body.SunShade.RearLeftPos",
    "Vehicle.Body.SunShade.RearRightPos",
    "Vehicle.Body.RingLightColor.BlueSts",
    "Vehicle.Body.RingLightColor.WhiteSts",
    "Vehicle.Body.RingLightColor.YellowSts",
    "Vehicle.Body.ElectrochromicMirror.RLDoorOneSts",
    "Vehicle.Body.ElectrochromicMirror.RRDoorOneSts",
    "Vehicle.Body.ElectrochromicMirror.ThirdLeftSts",
    "Vehicle.Body.ElectrochromicMirror.ThirdRightSts",
    "Vehicle.APP.Setting.Baffle",
    "Vehicle.APP.Setting.ControlSort",
    "Vehicle.APP.Setting.ParkConfig",
    "Vehicle.Carcenter.Maintain.engine",
    "Vehicle.Carcenter.Maintain.airfilter",
    "Vehicle.Powertrain.ChargingPile.ScheduledCharging.NewReserveFinishTime26",
    "Vehicle.Powertrain.ChargingPile.ScheduledCharging.ReserveStartTime26",
    "Vehicle.Powertrain.ChargingPile.ScheduledCharging.ReserveTimeStatus",
    "Vehicle.Cabin.CLTC.MileageFinalResultFuel",
    "Vehicle.CarSettings.Preference.CLTCWLTC",
)


class TestDeclaredSignals:
    """5 个新信号必须正确声明。"""

    @pytest.mark.parametrize("key,path,name,_line", _NEW_BARE_SCALAR)
    def test_declared_with_correct_path_and_name(self, key, path, name, _line):
        assert key in sg.SIGNALS, f"{key} 未声明"
        spec = sg.SIGNALS[key]
        assert spec.path == path, f"{key}: path 不符"
        assert spec.name == name, f"{key}: name 不符（应与 App 文案对齐）"

    @pytest.mark.parametrize("key,path,name,_line", _NEW_BARE_SCALAR)
    def test_is_diagnostic(self, key, path, name, _line):
        """★ 全部默认禁用 —— 验收硬要求，避免污染用户界面。"""
        assert sg.SIGNALS[key].diagnostic is True, \
            f"{key}: 必须 diagnostic=True（否则默认启用，污染界面）"

    @pytest.mark.parametrize("key,_path,_name,line", _NEW_BARE_SCALAR)
    def test_source_line_cited_in_comment(self, key, _path, _name, line):
        """★ CONTRIBUTING 硬要求：涉及信号语义必须附 App 源码依据（行号）。

        同时锁定【版本】—— 行号来自 apk_latest/smali_classes11。
        """
        src = (_INTEG / "signals.py").read_text(encoding="utf-8")
        idx = src.find(f'"{key}": SignalSpec(')
        assert idx != -1, f"{key}: 未找到声明"
        # 取该声明之前的一段注释作为依据区
        block = src[max(0, idx - 700):idx]
        assert f":{line}" in block, (
            f"{key}: 缺少 App 行号依据 :{line}\n"
            f"（依据应为 apk_latest/.../LxMeshVssConstant.smali:{line}）")

    def test_platforms_are_correct(self):
        """3 个 binary_sensor + 2 个 sensor。"""
        bs = {s.key for s in sg.specs_for("binary_sensor")}
        sn = {s.key for s in sg.specs_for("sensor")}
        for key in ("mirror_heat_left", "mirror_heat_right", "drv_seat_occupied"):
            assert key in bs, f"{key} 应为 binary_sensor"
            assert key not in sn
        for key in ("sunshade_front_pos", "sunshade_rear_pos"):
            assert key in sn, f"{key} 应为 sensor"
            assert key not in bs

    def test_privacy_signal_is_binary_and_disabled(self):
        """★ 主驾有人 = 隐私信号 → binary_sensor + 默认禁用（双重保险）。"""
        spec = sg.SIGNALS["drv_seat_occupied"]
        assert spec.diagnostic is True
        assert "binary_sensor" in spec.platforms

    def test_semantics_are_switch_on_for_booleans(self):
        """后视镜加热 / 主驾有人：非 0 = 开启。"""
        for key in ("mirror_heat_left", "mirror_heat_right", "drv_seat_occupied"):
            assert sg.SIGNALS[key].semantics == sg.Semantics.SWITCH_ON, \
                f"{key}: 语义应为 SWITCH_ON"


class TestNoDataSignalsNotDeclared:
    """19 条实测无数据的信号【不得】声明 —— 避免误建实体。"""

    @pytest.mark.parametrize("path", _NO_DATA_PATHS)
    def test_path_not_in_signals(self, path):
        declared = {s.path for s in sg.SIGNALS.values()}
        assert path not in declared, (
            f"{path} 实测【无数据】（L6 无此硬件），不应声明！\n"
            f"见 docs/缺失信号实测_20260928.md 第三节")

    def test_no_data_paths_annotated_in_source(self):
        """无数据的清单必须写在 signals.py 注释里（可追溯）。"""
        src = (_INTEG / "signals.py").read_text(encoding="utf-8")
        assert "L6 无此硬件" in src or "L6 无" in src, \
            "signals.py 应注释标注无数据信号（L6 无此硬件）"


class TestBinaryDiagnosticSupport:
    """★ 本次修的 bug：binary_sensor 此前忽略 spec.diagnostic。

    to_sensor_description() 处理了 diagnostic，
    但 to_binary_description() 没处理 → 诊断/隐私类二元传感器无法默认禁用。
    """

    def test_to_binary_description_source_handles_diagnostic(self):
        """源码级断言：防止有人回退掉这段逻辑。"""
        src = (_INTEG / "signals.py").read_text(encoding="utf-8")
        m = re.search(
            r"def to_binary_description\(.*?\n(.*?)\n(?=def )", src, re.S)
        assert m, "未找到 to_binary_description"
        body = m.group(1)
        assert "spec.diagnostic" in body, \
            "to_binary_description 必须处理 spec.diagnostic"
        assert "entity_registry_enabled_default" in body, \
            "diagnostic 信号必须设置 entity_registry_enabled_default = False"
        assert "EntityCategory.DIAGNOSTIC" in body, \
            "diagnostic 信号应归入 EntityCategory.DIAGNOSTIC"

    def test_two_converters_are_consistent(self):
        """两个转换函数对 diagnostic 的处理必须一致（防再次漏改）。"""
        src = (_INTEG / "signals.py").read_text(encoding="utf-8")

        def _body(fn: str) -> str:
            m = re.search(rf"def {fn}\(.*?\n(.*?)\n(?=def )", src, re.S)
            assert m, f"未找到 {fn}"
            return m.group(1)

        for fn in ("to_sensor_description", "to_binary_description"):
            body = _body(fn)
            assert "spec.diagnostic" in body, f"{fn} 未处理 diagnostic"
            assert "entity_registry_enabled_default" in body, \
                f"{fn} 未设置 entity_registry_enabled_default"
