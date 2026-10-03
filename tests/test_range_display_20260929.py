"""续航显示修正（2026-09-29）—— 车主反馈「i6 的续航数跟我们不一样」的根因回归测试。

背景
----
维护者反馈：理想 App 车控左上角的续航数，与集成显示的不一致。

根因（静态逆向，三条独立证据）
------------------------------
① 我们此前**没有总续航实体**，只有「纯电续航」「燃油续航」分项。
   而 App 车控头部（`headerControl.enduranceTag`）订阅的是
   `LXVehicleInfoKeyEndurance`，其 `subKeys`
   （`apk_latest/decompiled/assets/LXLiMeshPathConfig.json`）含：

       Vehicle.MSG.MSG_FuelLevelWrnng
       Vehicle.MSG.MSG_FuelLevelPos
       Vehicle.Cabin.LowBatteryMode
       Vehicle.Powertrain.Battery.RESSPowerBarCol
       Vehicle.Cabin.CLTC.PureElecEnduranceMileInd
       Vehicle.Cabin.CLTC.FuelEnduranceMileInd
       Vehicle.Cabin.WLTC.PureElecEnduranceMileInd
       Vehicle.Cabin.WLTC.FuelEnduranceMileInd
       Vehicle.Powertrain.Battery.ResidueBattery
       Vehicle.{{AccountId}}.CarSettings.Preference.CLTCWLTC   ← ★ 我们缺
       Vehicle.Cabin.CLTC.MileageFinalResult
       Vehicle.Cabin.CLTC.MileageFinalResultFuel

② 总续航的真实路径（`apk_decompile/ideal/assets/spec_X01-VSS-Path_148.json`）：

       Vehicle.Cabin.CLTC.EnduranceMil  = "CLTC总续航里程"
       Vehicle.Cabin.WLTC.EnduranceMil  = "WLTC总续航里程"

③ 显示工况开关（`LiAutoXSignal.json`）：

       /Vehicle/{{AccountId}}/CarSettings/Preference/CLTCWLTC
         datatype   = "string"
         default    = "1"
         type       = "actuator"
         description= "续航显示工况"

★ 我们曾经的错误判断
--------------------
`signals.py` 里原有一行备注称「CarSettings.Preference.CLTCWLTC ——
L6 增程版无 CLTC/WLTC 切换」并据此跳过。**那是错的**：真实原因是该路径带
`{{AccountId}}` 模板（App 用 `LXVssDelegate.resolveTemplateAccountId()` 替换成
车主账号，账号取自 `Vehicle.Account.Cloud.VehicleAccounts`），
不带模板去查自然无数据，于是被误判为「无此功能」。
"""
from __future__ import annotations

import pytest

import signals as sg


class TestRangeTotalSignals:
    """总续航必须存在 —— 它才是 App 车控左上角显示的那个数。

    ★ 2026-09-30 改成 compute —— App 反编译证实服务端不返回
      EnduranceMil 路径（LiMeshPathHelper.smali 里没有订阅），
      App 自己在 XEnduranceDataHandle 里把 PureElec + Fuel 加起来。
    """

    @pytest.mark.parametrize("key,compute,unit", [
        ("range_total_cltc", "lambda vss: _sum_range(vss, 'CLTC')", "km"),
        ("range_total_wltc", "lambda vss: _sum_range(vss, 'WLTC')", "km"),
    ])
    def test_total_range_exists(self, key, compute, unit):
        spec = sg.SIGNALS[key]
        # 虚拟信号：path="" + compute 算
        assert spec.path == "", f"{key} 是 compute 信号，path 应为空"
        assert spec.compute == compute, f"{key} 的 compute 应算总续航"
        assert spec.unit == unit

    @pytest.mark.parametrize("key", ["range_total_cltc", "range_total_wltc"])
    def test_total_range_is_not_a_fraction(self, key):
        """总续航不是分项 —— 用 compute 算（不是直接 VSS 分项）。"""
        spec = sg.SIGNALS[key]
        assert spec.path == "", f"{key} 是 compute 信号"
        assert spec.compute is not None, f"{key} 应有 compute 函数"

    def test_total_range_is_universal(self):
        """总续航对油车/电车都有意义（纯电车的总续航 = 纯电续航）。"""
        for key in ("range_total_cltc", "range_total_wltc"):
            assert sg.SIGNALS[key].universal is True, f"{key} 应为 universal"

    def test_total_range_freq_is_high(self):
        """续航随电量变化，必须高频轮询（与纯电/燃油分项同级）。"""
        for key in ("range_total_cltc", "range_total_wltc"):
            assert sg.SIGNALS[key].freq == sg.Freq.HIGH, f"{key} 应为 HIGH 频率"


class TestRangeDisplayMode:
    """「续航显示工况」决定 App 显示 CLTC 还是 WLTC。"""

    def test_exists_with_accountid_template(self):
        """★ 路径必须保留 {{AccountId}} 模板 —— 这是当初踩坑的地方。"""
        spec = sg.SIGNALS["range_display_mode"]
        assert spec.path == (
            "Vehicle.{{AccountId}}.CarSettings.Preference.CLTCWLTC"
        ), "路径必须带 {{AccountId}} 模板，否则读不到数据（曾因此误判为不存在）"

    def test_is_low_freq(self):
        """工况是用户偏好，不随车辆状态变化 → 低频。"""
        assert sg.SIGNALS["range_display_mode"].freq == sg.Freq.LOW

    def test_is_readable_as_sensor(self):
        """当前只读（可写是 actuator，但改它是用户设置层面的事，暂不提供控制）。

        用 specs_for() 而非 to_sensor_descriptions() —— 后者需要 homeassistant 包。
        """
        keys = {s.key for s in sg.specs_for("sensor")}
        assert "range_display_mode" in keys, "应能被 sensor 平台取到（只读展示）"
        sw_keys = {s.key for s in sg.specs_for("switch")}
        assert "range_display_mode" not in sw_keys, "暂不提供写入（改工况属账号设置）"

    def test_no_stale_claim_that_l6_lacks_cltcwltc(self):
        """★ 防止错误的旧结论回归：不得再出现「L6 无 CLTC/WLTC 切换」这类断言。"""
        import pathlib
        src = pathlib.Path(sg.__file__).read_text(encoding="utf-8")
        assert "L6 增程版无 CLTC/WLTC 切换" not in src, (
            "该备注已被证伪（真实原因：路径带 {{AccountId}} 模板），不应再出现"
        )


class TestNoRegressionOnExistingRangeSignals:
    """原有的 CLTC/WLTC 分项必须保留（只增不删）。"""

    @pytest.mark.parametrize("key,path", [
        ("range_elec_cltc", "Vehicle.Cabin.CLTC.PureElecEnduranceMileInd"),
        ("range_elec_wltc", "Vehicle.Cabin.WLTC.PureElecEnduranceMileInd"),
        ("range_fuel_cltc", "Vehicle.Cabin.CLTC.FuelEnduranceMileInd"),
        ("range_fuel_wltc", "Vehicle.Cabin.WLTC.FuelEnduranceMileInd"),
    ])
    def test_existing_range_signals_untouched(self, key, path):
        assert sg.SIGNALS[key].path == path
