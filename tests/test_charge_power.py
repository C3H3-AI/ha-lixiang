"""充电功率（派生信号）测试。

★ 2026-10-14 车主："充电功率实体没有"；2026-10-15 日检用实车充电数据修好。

官方充电页 4 项指标 = 充电效率 / 充电功率 / 输入电流 / 输入电压，
其 i18n 键名是 `power`（充电效率）与 **`av`**（充电功率）——av = A × V，
即 App 自己用「电流 × 电压」算的。

⚠️ 契约（与 _sum_range 一致）：
  · `vss` 的键是**信号 key**（charge_voltage_ac），不是 VSS 路径；
  · `vss[key]` 是 {"value": raw} 字典，要先取 ["value"]。
"""
from __future__ import annotations

import signals as sg


def _v(x):
    """构造 coordinator 里的 {value: ...} 包装。"""
    return {"value": x}


class TestChargePower:
    def test_ac_pair_real_session(self):
        """★ 实车数据：2026-10-15 00:04 交流充电中 219V × 30A = 6.57 kW。"""
        assert sg._charge_power({"charge_voltage_ac": _v(219),
                                 "charge_current_ac": _v(30)}) == 6.57

    def test_ogc_pair(self):
        """桩侧/直流：400V × 150A = 60 kW。"""
        assert sg._charge_power({"ogc_charge_voltage": _v(400),
                                 "ogc_charge_current": _v(150)}) == 60.0

    def test_prefers_ac_when_both_present(self):
        """交流数据有效时优先用交流（直流那对此时为 0）。"""
        vss = {"charge_voltage_ac": _v(219), "charge_current_ac": _v(30),
               "ogc_charge_voltage": _v(367), "ogc_charge_current": _v(0)}
        assert sg._charge_power(vss) == 6.57

    def test_idle_is_zero(self):
        """停车未充电：两项都在且为 0 → 0 kW（不是 unknown）。"""
        assert sg._charge_power({"charge_voltage_ac": _v(0),
                                 "charge_current_ac": _v(0)}) == 0.0
        # 只有电压、没有电流 → 按电流 0 算
        assert sg._charge_power({"charge_voltage_ac": _v(232)}) == 0.0

    def test_missing_and_garbage(self):
        assert sg._charge_power({}) is None
        assert sg._charge_power({"charge_voltage_ac": _v("abc"),
                                 "charge_current_ac": _v(16)}) == 0.0
        assert sg._charge_power({"charge_voltage_ac": _v("abc"),
                                 "charge_current_ac": _v("xyz")}) is None

    def test_old_vss_path_keys_do_not_resolve(self):
        """★ 回归：用 VSS 路径当键（曾经的 bug）必须取不到值。

        日检实测：写成 `Vehicle.Powertrain.Battery.ACChargeVoltage` 时恒为 unknown。
        """
        assert sg._charge_power({"Vehicle.Powertrain.Battery.ACChargeVoltage": _v(219),
                                 "Vehicle.Powertrain.Battery.ACChargeCurrent": _v(30)}) is None

    def test_signal_declared(self):
        """信号必须声明为派生（path 为空）+ kW + POWER。"""
        spec = sg.SIGNALS["charge_power"]
        assert spec.path == "", "派生信号不该请求 VSS"
        assert spec.compute, "缺 compute"
        assert spec.unit == "kW"
        assert spec.device_class == "POWER"
