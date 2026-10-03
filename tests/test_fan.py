"""fan.py 测试：座椅加热/通风实体

★ 背景（2026-09-24 用户报告"加热出错"）：
  HA 的 FanEntity 内部调用约定是【位置参数】：
    homeassistant/components/fan/__init__.py:315
      await self.async_turn_on(percentage, preset_mode, **kwargs)

  原实现只有 (percentage, **kwargs) → TypeError:
    "LiCarSeatFan.async_turn_on() takes from 1 to 2 positional
     arguments but 3 were given"

  本测试确保签名与 HA 基类一致，避免再次踩坑。
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import types
from pathlib import Path

import pytest

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src(filename: str) -> str:
    return (INTEG / filename).read_text(encoding="utf-8")


class TestFanSignatures:
    """★ fan 实体的方法签名必须与 HA 基类兼容"""

    def test_async_turn_on_has_preset_mode_positional(self):
        """★ async_turn_on 必须有 preset_mode 位置参数

        HA 内部调用：async_turn_on(percentage, preset_mode, **kwargs)
        缺少 preset_mode → TypeError（线上踩过的坑）
        """
        src = _src("fan.py")
        m = re.search(
            r"async def async_turn_on\s*\((.*?)\)\s*->", src, re.S)
        assert m, "未找到 async_turn_on"
        params = m.group(1)
        assert "percentage" in params, "缺少 percentage 参数"
        assert "preset_mode" in params, (
            "★ async_turn_on 缺少 preset_mode 位置参数 —— "
            "HA 会传 (percentage, preset_mode) 两个位置参数，会 TypeError！")

    def test_async_turn_off_accepts_kwargs(self):
        """async_turn_off 必须接受 **kwargs"""
        src = _src("fan.py")
        m = re.search(r"async def async_turn_off\s*\((.*?)\)\s*->", src, re.S)
        assert m, "未找到 async_turn_off"
        assert "kwargs" in m.group(1), "async_turn_off 应接受 **kwargs"

    def test_async_set_percentage_exists(self):
        """set_percentage 必须存在（HA 依赖它）"""
        src = _src("fan.py")
        assert re.search(r"async def async_set_percentage\s*\(", src), \
            "缺少 async_set_percentage"

    def test_signature_matches_ha_base(self):
        """★ 与 HA 基类签名对比（模拟 HA 的调用方式）

        HA 基类（fan/__init__.py:318）：
          async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs)
        """
        src = _src("fan.py")
        m = re.search(
            r"async def async_turn_on\s*\((.*?)\)\s*->", src, re.S)
        params = m.group(1)
        # 模拟 HA 调用：func(self, 100, "high")
        # 两个位置参数必须都能接收
        positional = [
            p.strip().split(":")[0].split("=")[0].strip()
            for p in params.split(",")
            if p.strip() and "**" not in p
        ]
        assert len(positional) >= 3, (
            f"async_turn_on 至少需要 3 个位置参数（self + 2），实际 {positional}")


class TestFanEntityTable:
    """SEAT_FANS 表完整性"""

    @staticmethod
    def _fans() -> list[tuple]:
        """解析 SEAT_FANS 表。

        ★ 2026-09-26：表从 5 列扩展为 7 列
          (suffix, name, icon, state_key, control_type, feat, ability_tag)
          这里只取前 5 列以保持既有断言语义。
        """
        src = _src("fan.py")
        m = re.search(r"SEAT_FANS = \((.*?)\n\)", src, re.S)
        assert m, "未找到 SEAT_FANS"
        return re.findall(
            r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"',
            m.group(1))

    @staticmethod
    def _all_specs() -> list[tuple]:
        """解析全部 7 列（含 feat / ability_tag）。"""
        src = _src("fan.py")
        m = re.search(r"SEAT_FANS = \((.*?)\n\)", src, re.S)
        assert m, "未找到 SEAT_FANS"
        return re.findall(
            r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",'
            r'\s*"([^"]+)",\s*"([^"]+)"(?:,\s*"([^"]+)")?\)',
            m.group(1))

    def test_table_has_twelve_definitions(self):
        """★ 2026-09-26：表里有 12 个座椅定义（含三排 3 个）。

        实际生成几个由【车型能力表】决定：
          L6/L7（五座）→ 9 个（无三排）
          L8/L9（六座）→ 10 个（有三排左/右，无二排中）

        ★ 2026-09-28：13 → 12。方向盘加热已从 fan 平台移除
          （用户反馈「实际只有开关功能，没有三档」；协议层
          strgWhlHeatSw 在 _AC_ONOFF_TYPES 白名单里，只发 ON/OFF），
          现由 switch 平台提供，见 switch.py 的 SWITCHES。
        """
        fans = self._fans()
        assert len(fans) == 12, f"应有 12 个座椅定义，实际 {len(fans)}"
        assert not any(s[0] == "wheel_heat" for s in fans), \
            "方向盘加热不应再出现在 fan 表里（应改为 switch）"

    def test_l6_generates_nine_seats(self):
        """★ L6（五座）按能力表应生成 9 个座椅 fan。"""
        specs = self._all_specs()
        # 模拟 L6 的能力表：三排=1（无）
        l6_absent = {"thirdLSeatSw", "thirdMSeatHeatSw", "thirdRSeatSw"}
        generated = [sp for sp in specs
                     if not (len(sp) > 6 and sp[6] and sp[6] in l6_absent)]
        assert len(generated) == 9, f"L6 应生成 9 个，实际 {len(generated)}"

    def test_second_row_has_middle_heat(self):
        """★ 二排中座椅加热（用户实测确认存在）"""
        keys = {f[0] for f in self._fans()}
        assert "seat_sm_heat" in keys, "缺少二排中座椅加热"

    def test_no_second_row_middle_vent(self):
        """★ 二排中【无】通风（SMSeatVentilationState 信号不存在）"""
        keys = {f[0] for f in self._fans()}
        assert "seat_sm_vent" not in keys, (
            "不该有 SMSeatVentilationState —— 该信号不存在")

    def test_all_nine_seats_user_verified(self):
        """★ 2026-09-26 用户实测：「座椅加热都正常」

        9 个座椅实体（主/副 × 加热通风 + 二排左中右）全部可用。
        其中 3 个用推测 controlType（App 里找不到），实测被服务端接受。
        """
        fans = self._fans()
        keys = {f[0] for f in fans}
        # ★ 2026-09-26：表已扩展为 12 个（含三排），
        #   这里断言 L6 实际生成的 9 个都在表里
        expected_l6 = {
            "seat_fl_heat", "seat_fr_heat", "seat_fl_vent", "seat_fr_vent",
            "seat_sl_heat", "seat_sr_heat", "seat_sm_heat",
            "seat_sl_vent", "seat_sr_vent",
        }
        assert expected_l6 <= keys, f"缺少 L6 的座椅: {expected_l6 - keys}"

    def test_third_row_defined_for_l8_l9(self):
        """★ 三排座椅已定义（供 L8/L9 自动生成）。"""
        keys = {f[0] for f in self._fans()}
        for k in ("seat_tl_heat", "seat_tm_heat", "seat_tr_heat"):
            assert k in keys, f"缺少三排定义: {k}"

    def test_ability_tags_present(self):
        """★ 每个座椅定义都带能力表 tag（第 7 列）。"""
        specs = self._all_specs()
        for sp in specs:
            assert len(sp) > 6 and sp[6], f"{sp[0]} 缺少 ability_tag"

    def test_second_row_control_types_match_app_jobtypes(self):
        """★ 二排 5 个 controlType 都来自 App 的 jobTypes（JS bundle）。

        ⚠️ 2026-09-26 更正：这些**不是**推测命名，App 里就有。

        权威来源：assets/index.vehicle.js 的 jobTypes 对象
          secLSeatHeatSw / secLSeatVentSw / secMSeatHeatSw
          secRSeatHeatSw / secRSeatVentSw
          （另有 thirdL/M/RSeatHeatSw —— 三排，L6 五座车无）

        ⚠️ 陷阱：smali 的 MVehicleControlManager 里只有 6 个
                （fl/fr 加热通风 + secL/secR 加热），
                那是【子集白名单】，不是完整定义。
                只查 smali 会误判为"App 没有"。
        """
        by_key = {f[0]: f[4] for f in self._fans()}
        second_row = {
            "seat_sl_heat": "secLSeatHeatSw",
            "seat_sl_vent": "secLSeatVentSw",
            "seat_sm_heat": "secMSeatHeatSw",
            "seat_sr_heat": "secRSeatHeatSw",
            "seat_sr_vent": "secRSeatVentSw",
        }
        for key, ctrl in second_row.items():
            assert by_key.get(key) == ctrl, (
                f"{key} 应为 {ctrl}，实际 {by_key.get(key)}")

        # 源码里应明确这些来自 App 的 jobTypes（防止后人又误判）
        src = (Path(__file__).resolve().parent.parent
               / "custom_components" / "lixiang_auto" / "fan.py").read_text()
        assert "jobTypes" in src, (
            "fan.py 应注明二排 controlType 来自 App 的 jobTypes")


    def test_control_types_match_app(self):
        """controlType 命名规则"""
        fans = self._fans()
        known = {
            "seat_fl_heat": "flSeatHeatSw",
            "seat_fr_heat": "frSeatHeatSw",
            "seat_fl_vent": "flSeatVentSw",
            "seat_fr_vent": "frSeatVentSw",
            "seat_sl_heat": "secLSeatHeatSw",
            "seat_sr_heat": "secRSeatHeatSw",
        }
        by_key = {f[0]: f[4] for f in fans}
        for key, ctrl in known.items():
            assert by_key.get(key) == ctrl, (
                f"{key} 的 controlType 应为 {ctrl}，实际 {by_key.get(key)}")
