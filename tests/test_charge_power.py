"""充电功率（派生信号）测试。

★ 2026-10-14 车主："充电功率实体没有"。

官方充电页 4 项指标 = 充电效率 / 充电功率 / 输入电流 / 输入电压，
其 i18n 键名是 `power`（充电效率）与 **`av`**（充电功率）——
av = A × V，即 App 自己用"电流 × 电压"算的。车辆侧没有独立充电功率信号，
所以我们同样按电学定义派生：交流用 AC 一对、桩侧用 OGC 一对。
"""
from __future__ import annotations

import signals as sg

ACV = "Vehicle.Powertrain.Battery.ACChargeVoltage"
ACC = "Vehicle.Powertrain.Battery.ACChargeCurrent"
OGV = "Vehicle.Powertrain.Battery.OGCChargeVoltage"
OGC = "Vehicle.Powertrain.Battery.OGCChargeCurrent"


class TestChargePower:
    def test_ac_pair(self):
        """交流：232V × 16A = 3.712 kW。"""
        assert sg._charge_power({ACV: 232, ACC: 16}) == 3.71

    def test_ogc_pair(self):
        """桩侧/直流：400V × 150A = 60 kW。"""
        assert sg._charge_power({OGV: 400, OGC: 150}) == 60.0

    def test_prefers_ac_when_both_present(self):
        vss = {ACV: 230, ACC: 10, OGV: 400, OGC: 100}
        assert sg._charge_power(vss) == 2.3

    def test_idle_is_zero(self):
        """停车未充电：两项都在且为 0 → 0 kW（不是 unknown）。"""
        assert sg._charge_power({ACV: 0, ACC: 0}) == 0.0
        assert sg._charge_power({OGV: 0, OGC: 0}) == 0.0
        # 只有电压、没有电流 → 按电流 0 算 → 0 kW（停车时常见）
        assert sg._charge_power({ACV: 232}) == 0.0
        # 两项都完全没有 → unknown
        assert sg._charge_power({"Vehicle.Powertrain.Battery.EVESFltStopChrg": 0}) is None

    def test_missing_and_garbage(self):
        """全无数据 → None；非数值视为缺失（另一项有值则按 0 算）。"""
        assert sg._charge_power({}) is None
        assert sg._charge_power({ACV: "abc", ACC: 16}) == 0.0
        assert sg._charge_power({ACV: "abc", ACC: "xyz"}) is None

    def test_signal_declared(self):
        """信号必须声明为派生（path 为空）+ kW + POWER。"""
        spec = sg.SIGNALS["charge_power"]
        assert spec.path == "", "派生信号不该请求 VSS"
        assert spec.compute, "缺 compute"
        assert spec.unit == "kW"
        assert spec.device_class == "POWER"
