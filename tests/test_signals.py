"""signals.py 测试：声明式信号表

★ 架构方案阶段 2.1/2.2 的验证：
  确保 SIGNALS 与旧的分散定义（const/sensor/binary_sensor/coordinator）一致。
"""

from __future__ import annotations

import pytest

import signals as sg


class TestSignalTable:
    def test_not_empty(self):
        assert len(sg.SIGNALS) > 100, "信号表应有 100+ 条"

    def test_all_have_key_path_name(self):
        """★ 2026-09-24：虚拟信号（path 为空）例外

        虚拟信号 = 值来自 coordinator.data 的其他字段，不走 VSS 轮询。
        目前只有 online_status（值来自 basics.vehicleStatus）。
        """
        for key, spec in sg.SIGNALS.items():
            assert spec.key == key, f"{key}: key 字段与字典键不一致"
            assert spec.name, f"{key}: 缺 name"
            if spec.path:
                assert spec.path.startswith("Vehicle."), \
                    f"{key}: path 格式错误 {spec.path}"
            else:
                # 虚拟信号必须显式声明（防止误加）
                # ★ 2026-09-28：新增 3 个里程统计虚拟信号
                #   （值派生自 trip_total，不重复轮询）
                # ★ 2026-09-28：新增 1 个别名虚拟信号 door_front_trunk
                #   （值复制自 lock_front_trunk —— 全 App 只有
                #    DoorLockStatus.FrontTrunkDoor 一个前备箱状态路径，
                #    同一路径不能声明两次）
                assert key in ("online_status", "stat_days",
                               "stat_mileage", "stat_elec_mileage",
                               "door_front_trunk", "range_total_cltc", "range_total_wltc",
                               # ★ 2026-10-02：HTTP 派生信号（coordinator 低频拉取）
                               "charge_total_energy",
                               "month_km", "month_elec_km", "month_elec_kwh",
                               "month_fuel_l", "month_charge_kwh",
                               "stat_total_mileage", "stat_engine_mileage",
                               "stat_ad_mileage", "stat_noa_mileage",
                               "stat_acc_mileage",
                               "stat_lcc_mileage", "stat_cd_mileage", "stat_ad_days",
                               # ★ 2026-10-11：M 系（理想ONE）实时状态通道派生的虚拟信号
                               #   值来自 real-time-state v3 响应（owner 2026-10-11 实测回传）
                               "seat_heat_vent_fl", "seat_heat_vent_fr",
                               "seat_heat_vent_rl", "seat_heat_vent_rr",
                               "ac_auto_mode", "ac_fan_speed_level",
                               "ac_set_temp_fl", "ac_set_temp_fr", "ring_light",
                               "key_in_car_warning", "gear"), \
                    f"{key}: 空路径但不是已知虚拟信号"

    def test_alias_signals_resolve(self):
        """★ 2026-09-28：虚拟别名信号必须指向一个真实存在、且带非空路径的信号。

        背景：前备箱只有 DoorLockStatus.FrontTrunkDoor 一条路径，
        door_front_trunk（门语义）以别名方式复用 lock_front_trunk（锁语义），
        避免同路径重复声明 + 重复轮询。
        """
        for key, spec in sg.SIGNALS.items():
            alias = getattr(spec, "alias_signal", None)
            if not alias:
                continue
            assert spec.path == "", f"{key}: 有别名信号的 path 必须为空"
            target = sg.SIGNALS.get(alias)
            assert target is not None, f"{key}: 别名目标 {alias} 不存在"
            assert target.path.startswith("Vehicle."), \
                f"{key}: 别名目标 {alias} 没有真实 VSS 路径"

    def test_paths_unique(self):
        """同一 VSS 路径不应被两个 key 复用（除兼容项）"""
        seen: dict[str, str] = {}
        dups = []
        for key, spec in sg.SIGNALS.items():
            # ★ 虚拟信号（path=""）本就没有路径，不参与唯一性检查
            #   （2026-09-28：stat_* 三个里程统计虚拟信号）
            if not spec.path:
                continue
            if spec.path in seen and "old" not in key:
                dups.append((key, seen[spec.path], spec.path))
            seen[spec.path] = key
        assert not dups, f"重复路径: {dups}"

    def test_platforms_valid(self):
        valid = {"sensor", "binary_sensor", "switch", "number", "select",
                 "button", "climate", "lock", "device_tracker", "notify"}
        for key, spec in sg.SIGNALS.items():
            bad = spec.platforms - valid
            assert not bad, f"{key}: 非法平台 {bad}"


class TestQueries:
    def test_specs_for_sensor(self):
        ss = sg.specs_for("sensor")
        assert len(ss) > 50
        assert all("sensor" in s.platforms for s in ss)

    def test_specs_for_binary(self):
        bs = sg.specs_for("binary_sensor")
        assert len(bs) > 20
        assert all("binary_sensor" in s.platforms for s in bs)

    def test_specs_for_unknown_platform(self):
        assert sg.specs_for("nonexistent") == []

    def test_by_freq(self):
        """★ 2026-09-24：by_freq 排除虚拟信号（path 为空）"""
        hi = sg.by_freq(sg.Freq.HIGH)
        mid = sg.by_freq(sg.Freq.MID)
        low = sg.by_freq(sg.Freq.LOW)
        vss_signals = [s for s in sg.SIGNALS.values() if s.path]
        assert len(hi) + len(mid) + len(low) == len(vss_signals)
        # 虚拟信号不应出现在任何档位
        all_freq = {s.key for s in hi + mid + low}
        for key, spec in sg.SIGNALS.items():
            if not spec.path:
                assert key not in all_freq, f"{key} 是虚拟信号，不该在轮询列表里"

    def test_paths_for(self):
        """"★ 2026-09-24：paths_for 排除空路径（虚拟信号）"""
        all_paths = sg.paths_for()
        hi_paths = sg.paths_for(sg.Freq.HIGH)
        assert "" not in all_paths, "虚拟信号（空路径）不该进轮询列表"
        assert len(all_paths) == len([s for s in sg.SIGNALS.values() if s.path])
        assert len(hi_paths) < len(all_paths)

    def test_path_of(self):
        assert sg.path_of("battery_level") == "Vehicle.Powertrain.Battery.ResidueBattery"

    def test_path_of_unknown(self):
        assert sg.path_of("nonexistent_key") == ""

    def test_compat_vss_paths(self):
        """兼容字典 = 有路径的信号（排除虚拟信号）"""
        with_path = [s for s in sg.SIGNALS.values() if s.path]
        assert len(sg.VSS_PATHS_COMPAT) == len(with_path)
        assert sg.VSS_PATHS_COMPAT["battery_level"] == sg.path_of("battery_level")


class TestKnownSignals:
    """关键信号的语义应正确（这些是踩过坑的）"""

    def test_battery_level(self):
        s = sg.SIGNALS["battery_level"]
        assert s.path == "Vehicle.Powertrain.Battery.ResidueBattery"
        assert s.unit == "PERCENTAGE"
        assert s.device_class == "BATTERY"

    def test_door_trunk_semantics(self):
        """★ 尾门：锁优先聚合（getTrunkState）

        历史：
          · 曾用 n != 0 → 值 2 被误判为"打开"（391cd8a 修）
          · 现用 TRUNK 语义 —— 有锁信号时以锁为准
        """
        s = sg.SIGNALS["door_trunk"]
        assert s.semantics == sg.Semantics.TRUNK
        assert "binary_sensor" in s.platforms

    def test_charge_port_lid_uses_v2(self):
        """★ 充电口盖用 V2（旧版恒为 1，无效）"""
        s = sg.SIGNALS["charge_port_lid"]
        assert s.path.endswith("ChrgPorLidStsV2")
        assert s.semantics == sg.Semantics.CHARGE_LID

    def test_ac_on_uses_foofstatus(self):
        """★ 空调开关用 FOffStatus（ExSpeedStatus 是快冷快热）"""
        s = sg.SIGNALS["ac_on"]
        assert s.path.endswith("FOffStatus")

    def test_low_freq_signals(self):
        """OTA/配置类应是低频"""
        assert sg.SIGNALS["config_code"].freq == sg.Freq.LOW
        assert sg.SIGNALS["ota_version"].freq == sg.Freq.LOW


class TestFreqEquivalence:
    """★ 等价性验证：spec.freq 的分组必须与旧的前缀规则一致。

    这是架构方案建议的关键测试 —— 确保 coordinator 切换零行为变化。
    """

    @staticmethod
    def _old_grouping(vss_paths, mid_prefixes, low_prefixes):
        hi, mid, lo = set(), set(), set()
        for k, p in vss_paths.items():
            if any(k.startswith(pre) for pre in low_prefixes):
                lo.add(p)
            elif any(k.startswith(pre) for pre in mid_prefixes):
                mid.add(p)
            else:
                hi.add(p)
        return hi, mid, lo

    # ★ 2026-09-24：手工补充的信号（不在 gen_signals 生成源里）
    #   它们的 freq 是人工设定的，不适用"旧前缀规则"的等价性检查
    MANUAL_KEYS = {
        "virtual_key_auth", "vehicle_accounts", "provision_complete",
        "provision_finish", "maint_engine_level2",
        "seat_l_door_interference", "seat_r_door_interference",
        "fridge_reserve", "xmode", "ac_temp_color", "charge_calibration",
        "charge_here", "rear_load_mode", "ress_power_bar_color",
        "ogc_charge_current", "ogc_charge_voltage", "ogc_type",
    }
    # ★ 2026-09-24：座椅频率从 MID 改为 HIGH
    #   原因：座椅是【用户主动控制】的实体，控制后需立即反馈状态。
    #   归到 MID（1 小时）会导致"切换档位后长时间显示关闭"。
    #   已在 coordinator.py 移除 "seat_s"/"seat_t" 前缀，
    #   并重新生成了 signals.py 的 freq。
    SEAT_FREQ_FIXED = {
        "Vehicle.Cabin.Seat.SLSeatHeatState",
        "Vehicle.Cabin.Seat.SRSeatHeatState",
        "Vehicle.Cabin.Seat.SMSeatHeatState",
        "Vehicle.Cabin.Seat.SLSeatVentilationState",
        "Vehicle.Cabin.Seat.SRSeatVentilationState",
        "Vehicle.Cabin.Seat.TLSeatHeatState",
        "Vehicle.Cabin.Seat.TRSeatHeatState",
        "Vehicle.Cabin.Seat.TMSeatHeatState",
        "Vehicle.Cabin.Seat.TLSeatVentilationState",
        "Vehicle.Cabin.Seat.TRSeatVentilationState",
    }
    # ★ 2026-09-26 实车验证发现：以下可控实体用的信号原本是 MID（1小时），
    #   导致实体显示 unknown。提升为 HIGH 后需豁免等价性检查。
    CHARGE_FREQ_FIXED = {
        "Vehicle.Powertrain.ChargingPile.ChargingLimit",
        "Vehicle.Powertrain.ChargingPile.ScheduledCharging.Switch",
        "Vehicle.Powertrain.ChargingPile.ScheduledCharging.ReserveStartTime",
        "Vehicle.Powertrain.ChargingPile.ScheduledCharging.NewReserveFinishTime",
        "Vehicle.Powertrain.ChargingPile.ScheduledCharging.State",
        "Vehicle.Powertrain.Battery.ACChgrActualConnSts",
    }

    # ★ 2026-09-29 降频：胎压/胎温是慢变量，HIGH(5min) → MID(1h)。
    #   数据库实测：9925 行写入仅 11 种不同值（≈900:1 重复写入）。
    #   轮询请求量降 92%；慢漏气 1 小时内仍可发现。
    #   tire_xx_warning 保持 HIGH（安全相关），故不在此豁免集。
    TIRE_FREQ_FIXED = {
        "Vehicle.Chassis.Tire.FLTirePressure",
        "Vehicle.Chassis.Tire.FRTirePressure",
        "Vehicle.Chassis.Tire.RLTirePressure",
        "Vehicle.Chassis.Tire.RRTirePressure",
        "Vehicle.Chassis.Tire.FLTireTemp",
        "Vehicle.Chassis.Tire.FRTireTemp",
        "Vehicle.Chassis.Tire.RLTireTemp",
        "Vehicle.Chassis.Tire.RRTireTemp",
    }
    MANUAL_PATHS = {
          # ★ 2026-09-29（续航显示修正）：App 车控左上角显示的是【总续航】；
          #   另加「续航显示工况」开关。证据见 signals.py 的 SignalSpec 注释。
          #   注：CLTCWLTC 路径带 {{AccountId}} 模板，不匹配任何前缀规则。
          "Vehicle.Cabin.CLTC.EnduranceMil",
          "Vehicle.Cabin.WLTC.EnduranceMil",
          "Vehicle.{{AccountId}}.CarSettings.Preference.CLTCWLTC",
        "Vehicle.Cabin.RmtVirtualKeyAuthSts",
        "Vehicle.Account.Cloud.VehicleAccounts",
        "Vehicle.Provision.Process.Complete",
        "Vehicle.Provision.Process.FinishSuccess",
        "Vehicle.Carcenter.Maintain.enginelevel2",
        "Vehicle.Body.SeatLDoor.InterferenceSts",
        "Vehicle.Body.SeatRDoor.InterferenceSts",
        # ★ 2026-09-27：新增前备箱 / 滑门（App 反编译得来，不在生成源里）
        #   XHttpFrunkControl / XHttpLSlideDoorControl / XHttpRSlideDoorControl
        "Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor",
        "Vehicle.Body.SeatLDoor.DoorStatus",
        "Vehicle.Body.SeatRDoor.DoorStatus",
        # ★ 2026-09-28（task-18）：实测有数据的缺失 VSS 信号（手工设定 freq）
        #   来源：missing_vss_probe_result.json（实测）
        #         apk_latest/.../LxMeshVssConstant.smali:699 / :954 / :1251
        #                                                 :624 / :969
        "Vehicle.Body.RearMirro.LHeatSts",
        "Vehicle.Body.RearMirro.RHeatSts",
        "Vehicle.Body.Seat.DrvSeatOccupied",
        "Vehicle.Body.SunShade.FrontPos",
        "Vehicle.Body.SunShade.RearPos",
        "Vehicle.CarSettings.Xmode.ReserveFridge",
        "Vehicle.CarSettings.MoveOffOnTime.Xmode",
        "Vehicle.Cabin.AC.FrtWindTempColor",
        "Vehicle.VehInfo.CarCenter.ChargeManagement.ChargingCalibration",
        "Vehicle.Powertrain.ChargingPile.ScheduledCharging.ChargeHere",
        "Vehicle.VehInfo.CarSettings.Maintain.RearLoadModeSetting",
        "Vehicle.Powertrain.Battery.RESSPowerBarCol",
        "Vehicle.Powertrain.Battery.OGCChargeCurrent",
        "Vehicle.Powertrain.Battery.OGCChargeVoltage",
        "Vehicle.Powertrain.ChargingPile.OGCType",
    }

    def test_grouping_matches_prefix_rules(self):
        """用真实的旧前缀规则验证分组一致

        ⚠️ 2026-09-24：手工补充的信号豁免此检查
          （它们不在 gen_signals 的生成源里，freq 是人工设定）
        """
        import re
        from pathlib import Path

        # 从 coordinator.py 读真实前缀（若文件不可用则跳过）
        coord = Path(__file__).resolve().parent.parent / (
            "custom_components/lixiang_auto/coordinator.py")
        if not coord.exists():
            pytest.skip("coordinator.py 不可用")

        src = coord.read_text(encoding="utf-8")
        MID = tuple(re.findall(r'"([^"]+)"', re.search(
            r"MID_FREQ_PREFIXES\s*=\s*\((.*?)\)", src, re.S).group(1)))
        LOW = tuple(re.findall(r'"([^"]+)"', re.search(
            r"LOW_FREQ_PREFIXES\s*=\s*\((.*?)\)", src, re.S).group(1)))

        # ★ 2026-09-24：架构 2.8 后 const.VSS_PATHS 改为从 signals 导入，
        #   不能再解析文件 → 直接用 signals.VSS_PATHS_COMPAT（等价）
        vss = dict(sg.VSS_PATHS_COMPAT)

        hi_old, mid_old, lo_old = self._old_grouping(vss, MID, LOW)
        hi_new = {s.path for s in sg.by_freq(sg.Freq.HIGH)}
        mid_new = {s.path for s in sg.by_freq(sg.Freq.MID)}
        lo_new = {s.path for s in sg.by_freq(sg.Freq.LOW)}

        # 手工补充的信号 + 座椅频率修正 → 豁免等价性检查
        exc = (self.MANUAL_PATHS | self.SEAT_FREQ_FIXED
               | self.CHARGE_FREQ_FIXED | self.TIRE_FREQ_FIXED)
        assert hi_new - exc == hi_old - exc, \
            f"HIGH 分组不一致: {(hi_new - exc) ^ (hi_old - exc)}"
        assert mid_new - exc == mid_old - exc, \
            f"MID 分组不一致: {(mid_new - exc) ^ (mid_old - exc)}"
        assert lo_new - exc == lo_old - exc, \
            f"LOW 分组不一致: {(lo_new - exc) ^ (lo_old - exc)}"

    def test_all_vss_paths_covered(self):
        """★ 兼容字典必须覆盖所有【有 VSS 路径】的信号（架构 2.8 后两者同源）

        注意：VSS_PATHS_COMPAT 的构造是 `{k: s.path for k, s in SIGNALS.items()
        if s.path}` —— 虚拟信号（path 为空，如 online_status）**本就不该**
        出现在兼容字典里（VSS_PATHS 是「实体key → VSS path」映射）。

        2026-09-27 修正：原断言 `len(COMPAT) == len(SIGNALS)` 在新增虚拟信号
        online_status 后会失败（147 != 148）。改为断言真正的不变量：
        COMPAT 恰好覆盖「非虚拟信号」，不遗漏也不多余。
        """
        non_virtual = {k for k, s in sg.SIGNALS.items() if s.path}
        assert set(sg.VSS_PATHS_COMPAT) == non_virtual, (
            f"兼容字典与「非虚拟信号」不一致："
            f"多了 {set(sg.VSS_PATHS_COMPAT) - non_virtual}，"
            f"少了 {non_virtual - set(sg.VSS_PATHS_COMPAT)}")
        covered = {s.path for s in sg.SIGNALS.values() if s.path}
        missing = set(sg.VSS_PATHS_COMPAT.values()) - covered
        assert not missing, f"未覆盖 {len(missing)} 条路径"


class TestDescriptionEquivalence:
    """★ 等价性：从 SIGNALS 生成的 sensor 描述，必须与旧 _mk 表一致。

    这是架构方案 2.4 的关键验证 —— 确保切换零行为变化。
    """

    @staticmethod
    def _old_mk_table():
        """解析 sensor.py 的 _mk 调用。"""
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent /
               "custom_components/lixiang_auto/sensor.py").read_text(encoding="utf-8")
        out = {}
        pat = re.compile(r'_mk\(\s*"([^"]+)"\s*,\s*\(([^)]+)\)\s*\)')
        for m in pat.finditer(src):
            key = m.group(1)
            parts = [p.strip().strip("'\"") for p in m.group(2).split(",")]
            parts = [("" if p == "None" else p) for p in parts]
            while len(parts) < 6:
                parts.append("")
            out[key] = dict(name=parts[0], dclass=parts[1], unit=parts[2],
                            sclass=parts[3], icon=parts[4], cat=parts[5])
        return out

    def test_same_key_set(self):
        """★ 新旧表的 key 集合必须一致

        ⚠️ 注意：signals.py 里有几条 platforms 为空（location/ac_on 等），
           它们不是 sensor 实体 —— 但 _mk 表也不需要它们。
           这里比对【会生成实体的】部分。
        """
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent /
               "custom_components/lixiang_auto/sensor.py").read_text(encoding="utf-8")
        # _mk 表里被注释掉的（如 window_skylight）不算
        old = set()
        for m in re.finditer(r'_mk\(\s*"([^"]+)"', src):
            # 检查该行是否在注释里
            line_start = src.rfind("\n", 0, m.start()) + 1
            if not src[line_start:m.start()].strip().startswith("#"):
                old.add(m.group(1))
        new = {s.key for s in sg.specs_for("sensor")}
        # ★ 2026-09-24：新增信号不在旧 _mk 表里（那表已废弃，不用于创建实体）
        #   这些是【新增】的，不是"多余"的
        NEW_KEYS = {
            "online_status",                    # 虚拟信号
            "virtual_key_auth", "vehicle_accounts",
            "provision_complete", "provision_finish",
            "maint_engine_level2",
            "seat_l_door_interference", "seat_r_door_interference",
            "fridge_reserve", "xmode", "ac_temp_color",
            "charge_calibration", "charge_here", "rear_load_mode",
            "ress_power_bar_color",
            "ogc_charge_current", "ogc_charge_voltage", "ogc_type",
            # ★ 2026-09-28（task-18）：实测有数据的缺失 VSS 信号
            #   来源：missing_vss_probe_result.json（实测）
            #         apk_latest/.../LxMeshVssConstant.smali:624 / :969
            "sunshade_front_pos", "sunshade_rear_pos",
            # ★ 2026-09-29（续航显示修正）：App 车控左上角显示的是【总续航】
            #   证据：
            #     ① spec_X01-VSS-Path_148.json
            #          Vehicle.Cabin.{CLTC,WLTC}.EnduranceMil
            #          = "CLTC/WLTC总续航里程"
            #     ② LXLiMeshPathConfig.json → LXVehicleInfoKeyEndurance.subKeys
            #          含 CarSettings.Preference.CLTCWLTC
            #     ③ LiAutoXSignal.json：CLTCWLTC 描述「续航显示工况」，
            #          datatype=string, default="1", type=actuator
            "range_total_cltc", "range_total_wltc", "range_display_mode",
        }
        extra = new - old - NEW_KEYS
        missing = old - new
        assert not extra, f"多了（未预期的 key）: {extra}"
        assert not missing, f"少了: {missing}"

    def test_names_match(self):
        old = self._old_mk_table()
        for key, o in old.items():
            s = sg.SIGNALS[key]
            assert o["name"] == s.name, f"{key}: name 旧={o['name']} 新={s.name}"

    def test_icons_match(self):
        old = self._old_mk_table()
        for key, o in old.items():
            s = sg.SIGNALS[key]
            if o["icon"]:
                assert o["icon"] == (s.icon or ""), (
                    f"{key}: icon 旧={o['icon']} 新={s.icon}")

    def test_categories_match(self):
        old = self._old_mk_table()
        for key, o in old.items():
            s = sg.SIGNALS[key]
            if o["cat"]:
                assert o["cat"] == (s.category or ""), (
                    f"{key}: category 旧={o['cat']} 新={s.category}")

    # ★ 2026-09-24：泊车状态/进度改为诊断类
    #   原因：ParkStatus 服务端从不返回；FSDBootProgress 值恒为 0。
    #   泊车状态在 App 里走【实时事件通道】，VSS 拿不到。
    NEWLY_DIAGNOSTIC = {
        "park_status", "park_fsd_progress",
        # ★ 2026-09-28：里程统计（陪伴天数/里程/耗电行驶）
        #   数据量大、非高频关注，归入诊断类（默认不启用）
        "stat_days", "stat_mileage", "stat_elec_mileage",
        # ★ 2026-09-24：充电开始/结束时间已由 time 实体提供可设置版本
        #   （signal 层面的只读 sensor 冗余）
        "scheduled_charge_start", "scheduled_charge_end",
    }

    def test_diagnostic_matches(self):
        """★ diagnostic 判定必须一致（影响默认启用与否）

        旧逻辑（sensor.py:98）：
          cat in _DIAGNOSTIC_CATS  OR  key in _DIAGNOSTIC_KEYS
        """
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent /
               "custom_components/lixiang_auto/sensor.py").read_text(encoding="utf-8")

        m = re.search(r"_DIAGNOSTIC_KEYS\s*=\s*frozenset\(\{(.*?)\}\)", src, re.S)
        diag_keys = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
        m2 = re.search(r"_DIAGNOSTIC_CATS\s*=\s*frozenset\(\{(.*?)\}\)", src, re.S)
        diag_cats = set(re.findall(r'"([^"]+)"', m2.group(1))) if m2 else set()

        assert diag_cats, "未解析到 _DIAGNOSTIC_CATS（测试自身问题）"

        old = self._old_mk_table()
        for key, o in old.items():
            if key in self.NEWLY_DIAGNOSTIC:
                continue      # 已按新规则改为诊断类（见 NEWLY_DIAGNOSTIC）
            old_diag = (o["cat"] in diag_cats) or (key in diag_keys)
            s = sg.SIGNALS[key]
            assert old_diag == s.diagnostic, (
                f"{key}: diagnostic 旧={old_diag} 新={s.diagnostic}")


class TestBinaryEquivalence:
    """★ 等价性：从 SIGNALS 生成的 binary_sensor 描述，必须与旧表一致。

    架构方案 2.5 的关键验证。
    """

    @staticmethod
    def _old_binary_table():
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent /
               "custom_components/lixiang_auto/binary_sensor.py").read_text(encoding="utf-8")
        out = {}
        pat = re.compile(
            r'\(BinarySensorEntityDescription\(\s*key="([^"]+)"\s*,\s*name="([^"]+)"'
            r'(.*?)\)\s*,\s*"([^"]+)"\s*\)', re.S)
        for m in pat.finditer(src):
            out[m.group(1)] = {"name": m.group(2), "kind": m.group(4)}
        return out

    KIND_TO_SEM = {
        "lock": "LOCKED", "door": "DOOR_OPEN", "trunk": "TRUNK",
        "plug": "PLUGGED", "conn": "CONNECTED", "warn": "ALARM",
        "heat": "SWITCH_ON", "charge_lid": "CHARGE_LID",
    }

    def test_same_key_set(self):
        old = set(self._old_binary_table())
        new = {s.key for s in sg.specs_for("binary_sensor")}
        # ★ 2026-09-24：sentry_switch 改由 switch 平台提供
        #   （原本 binary_sensor 哨兵开关与 switch 哨兵模式状态源重复）
        MOVED_TO_SWITCH = {"sentry_switch"}
        # ★ 2026-09-27：新增前备箱 / 滑门信号（用户要求"全部实现"）
        #   来源：App 反编译 XHttpFrunkControl / XHttpLSlideDoorControl /
        #         XHttpRSlideDoorControl
        #   ⚠️ L6/L7 无这些硬件 → 实体按能力条件创建（cover.py）
        ADDED_2026_09_27 = {
            "door_front_trunk", "door_slide_left", "door_slide_right",
        }
        # ★ 2026-09-28（task-18）：补齐实测有数据的缺失 VSS 信号
        #   来源：lixiang-reverse/data/missing_vss_probe_result.json（实测）
        #         apk_latest/.../LxMeshVssConstant.smali:699 / :954 / :1251
        #   3 个 binary_sensor，均 diagnostic=True → 默认禁用
        ADDED_2026_09_28 = {
            "mirror_heat_left", "mirror_heat_right", "drv_seat_occupied",
        }
        assert old - MOVED_TO_SWITCH == new - ADDED_2026_09_27 - ADDED_2026_09_28, (
            f"多了: {new - old - ADDED_2026_09_27 - ADDED_2026_09_28}\n"
            f"少了: {old - new - MOVED_TO_SWITCH}")

    def test_names_match(self):
        for key, o in self._old_binary_table().items():
            assert o["name"] == sg.SIGNALS[key].name, \
                f"{key}: name 旧={o['name']} 新={sg.SIGNALS[key].name}"

    def test_semantics_match_kind(self):
        """★ kind 字符串 → Semantics 枚举 的映射必须正确

        旧编码：
          "lock" / "door" / "trunk" / "plug" / "conn" / "warn" / "heat"
          "json:xxx"   ← JSON 字段判定
        """
        for key, o in self._old_binary_table().items():
            kind = o["kind"]
            if kind.startswith("json:"):
                want = "JSON_FIELD"
            else:
                want = self.KIND_TO_SEM.get(kind, "RAW")
            got = sg.SIGNALS[key].semantics.value.upper()
            assert want == got, f"{key}: kind={kind} → {got}（应为 {want}）"

    def test_device_class_present(self):
        """binary_sensor 应有 device_class 或 icon（否则 UI 无标识）"""
        for s in sg.specs_for("binary_sensor"):
            assert s.device_class or s.icon, f"{s.key}: 缺 device_class 和 icon"


class TestSemanticsEnum:
    """Semantics 枚举本身的健全性"""

    def test_all_semantics_used(self):
        """每个枚举值都应有信号在用（避免死枚举）"""
        used = {s.semantics for s in sg.SIGNALS.values()}
        # RAW 可能没用到（默认值不算显式使用）
        defined = set(sg.Semantics) - {sg.Semantics.RAW}
        unused = defined - used
        assert not unused, f"未使用的语义: {unused}"

    def test_locked_signals_are_binary(self):
        """LOCKED 语义的信号应在 binary_sensor 平台"""
        for s in sg.SIGNALS.values():
            if s.semantics == sg.Semantics.LOCKED and s.platforms:
                assert "binary_sensor" in s.platforms, f"{s.key}: LOCKED 但不在 binary_sensor"

    def test_door_open_signals_are_binary(self):
        for s in sg.SIGNALS.values():
            if s.semantics == sg.Semantics.DOOR_OPEN and s.platforms:
                assert "binary_sensor" in s.platforms, f"{s.key}: DOOR_OPEN 但不在 binary_sensor"


class TestSemanticsIntegrity:
    """★ 防护测试：binary_sensor.py 引用的 Semantics 成员必须存在。

    背景：2026-09-24 连续两次踩坑 ——
      · is_on 里写了 Semantics.JSON_FIELD，但枚举没定义
      · is_on 里写了 Semantics.TRUNK，但枚举没定义
    两次都导致 binary_sensor 平台大面积 unavailable。
    """

    @staticmethod
    def _referenced_semantics():
        """从 binary_sensor.py 提取所有 Semantics.XXX 引用。"""
        import re
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent /
               "custom_components/lixiang_auto/binary_sensor.py").read_text(encoding="utf-8")
        return set(re.findall(r'Semantics\.([A-Z_]+)', src))

    def test_all_referenced_members_exist(self):
        """binary_sensor.py 引用的每个 Semantics 成员都必须已定义"""
        refs = self._referenced_semantics()
        defined = {e.name for e in sg.Semantics}
        missing = refs - defined
        assert not missing, (
            f"binary_sensor.py 引用了未定义的 Semantics 成员: {missing}\n"
            f"已定义: {sorted(defined)}"
        )

    def test_no_unused_semantics(self):
        """每个非 RAW 的 Semantics 都应至少有一个信号在用"""
        used = {s.semantics for s in sg.SIGNALS.values() if s.platforms}
        defined = set(sg.Semantics) - {sg.Semantics.RAW}
        unused = defined - used
        assert not unused, f"未使用的语义（可能是笔误）: {unused}"

    def test_json_field_signals_have_field(self):
        """JSON_FIELD 语义的信号必须指定 json_field"""
        for s in sg.SIGNALS.values():
            if s.semantics == sg.Semantics.JSON_FIELD:
                assert s.json_field, f"{s.key}: JSON_FIELD 但没指定 json_field"

    def test_platform_conversion_functions_exist(self):
        """★ 平台转换函数必须存在（曾两次因丢失而大面积 unavailable）"""
        for fn in ("to_sensor_description", "to_sensor_descriptions",
                   "to_binary_description", "to_binary_descriptions",
                   "specs_for", "by_freq", "paths_for"):
            assert hasattr(sg, fn), f"signals.py 缺少 {fn}()"


class TestVirtualSignals:
    """★ 虚拟信号（非 VSS）—— 值来自 coordinator.data 的其他字段

    背景（2026-09-24）：
      online_status 的值来自 basics.vehicleStatus，不是 VSS 信号。
      gen_signals.py 从 VSS_PATHS 生成 → 漏了它
      → sensor 平台不再创建该实体 → 旧实体残留且永远 unknown
    """

    def test_online_status_exists(self):
        """★ online_status 必须在 SIGNALS 里（否则实体不会被创建/更新）"""
        assert "online_status" in sg.SIGNALS, (
            "online_status 是虚拟信号，必须手工加进 signals.py")

    def test_virtual_signals_have_empty_path(self):
        """虚拟信号的 path 应为空"""
        s = sg.SIGNALS["online_status"]
        assert s.path == "", "虚拟信号不应有 VSS 路径"
        assert s.name == "在线状态"

    def test_virtual_signals_excluded_from_polling(self):
        """★ 虚拟信号不能进轮询列表（否则会请求空路径）"""
        assert "" not in sg.paths_for()
        freq_keys = {x.key for x in (sg.by_freq(sg.Freq.HIGH)
                                     + sg.by_freq(sg.Freq.MID)
                                     + sg.by_freq(sg.Freq.LOW))}
        assert "online_status" not in freq_keys

    def test_virtual_signals_excluded_from_compat(self):
        """★ 兼容字典也要排除（coordinator 用它做反转映射）"""
        assert "online_status" not in sg.VSS_PATHS_COMPAT
        assert "" not in sg.VSS_PATHS_COMPAT.values()

    def test_virtual_signal_is_sensor(self):
        """虚拟信号应创建为 sensor 实体"""
        assert "sensor" in sg.SIGNALS["online_status"].platforms


class TestSemanticAudit20260928:
    """★ 2026-09-28 语义审计的回归保护。

    背景：用户报告「车不在充电位却显示在充电位」——
    charge_here 的信号名与翻译都错了（把"此地执行预约状态"译成了位置）。

    依据：App spec `spec_X01-VSS-Path_148.json`
        Vehicle.Powertrain.ChargingPile.ScheduledCharging.ChargeHere
        description = "此地执行预约状态"（type=actuator）
        App UI 文案 = "仅在固定地点执行预约，如需关闭请在车机端操作"

    ★ 这类错误（名字说的和信号实际含义不符）用户一眼就能看出，
      但纯逻辑测试抓不到 —— 所以这里做【名字级】断言。
    """

    def test_charge_here_is_not_a_location(self):
        """charge_here 不得再被描述为「位置」。"""
        s = sg.SIGNALS["charge_here"]
        assert "位置" not in s.name, (
            f"charge_here 是「此地执行预约状态」（预约策略开关），"
            f"不是位置 —— 当前名字 {s.name!r} 会让用户误以为车停在充电位"
        )
        # 应为预约相关语义
        assert "预约" in s.name, f"名字应表达预约语义，当前 {s.name!r}"

    def test_charge_here_path_unchanged(self):
        """★ 关键：路径与 key 不得改动（改了会新建实体、产生孤儿）。"""
        s = sg.SIGNALS["charge_here"]
        assert s.path == (
            "Vehicle.Powertrain.ChargingPile.ScheduledCharging.ChargeHere"
        )
        assert s.key == "charge_here"

    def test_charge_here_translation_is_not_position(self):
        """翻译不得再把 ChargeHere 的 0/1 说成"在/不在充电位"。"""
        import translations as tr
        path = ("Vehicle.Powertrain.ChargingPile."
                "ScheduledCharging.ChargeHere")
        for raw in (0, 1):
            out = tr.translate(path, raw)
            assert "充电位" not in str(out), (
                f"ChargeHere={raw} 翻译成 {out!r} 仍是位置语义；"
                "应表达「是否启用仅在此地预约」"
            )
        assert "预约" in str(tr.translate(path, 1))

    def test_mileage_final_is_range_not_odometer(self):
        """mileage_final 是续航预测（App spec），不是累计里程。"""
        s = sg.SIGNALS["mileage_final"]
        assert s.path == "Vehicle.Cabin.CLTC.MileageFinalResult"
        assert s.name != "总里程", (
            f"CLTC.MileageFinalResult 的官方描述是「动态续航，预测续航」，"
            f"不是累计里程 —— 当前名字 {s.name!r}"
        )
