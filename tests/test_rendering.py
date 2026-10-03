"""render_value() 纯函数测试

★ 这是架构方案 T0 的核心：
  把 sensor.py 的 29 处 `if key ==` 分支变成可验证的纯函数。

覆盖：
  1. 无数据场景（None / 缺失）
  2. 各特殊信号的渲染
  3. 门/窗/锁的语义（历史踩坑点）
  4. 通用兜底（长 JSON 截断 / 类型直返）
"""

from __future__ import annotations

import json

import pytest

from rendering import STATE_UNKNOWN, render_value


# ───────────────────────────────────────────────────────────────────────────
# 1. 基础：无数据
# ───────────────────────────────────────────────────────────────────────────
class TestEmpty:
    @pytest.mark.parametrize("key", [
        "battery_level", "charge_status", "door_main", "window_main",
        "ac_set_temp", "tire_fl_pressure", "location", "sentry",
    ])
    def test_none_value_returns_none(self, key):
        """值为 None → 返回 None（让 sticky 包装器回退上次有效值）"""
        assert render_value(key, None, None, {}) is None

    def test_missing_sig_returns_none(self):
        assert render_value("battery_level", None, None, None) is None


# ───────────────────────────────────────────────────────────────────────────
# 2. online_status（非 VSS 来源，读 data["vehicle_status"]）
# ───────────────────────────────────────────────────────────────────────────
class TestOnlineStatus:
    def test_online(self):
        assert render_value("online_status", None, None, {"vehicle_status": 1}) == "在线"

    def test_offline(self):
        assert render_value("online_status", None, None, {"vehicle_status": 0}) == "离线"

    def test_missing(self):
        assert render_value("online_status", None, None, {}) == STATE_UNKNOWN


# ───────────────────────────────────────────────────────────────────────────
# 3. location（JSON → "lat,lon"）
# ───────────────────────────────────────────────────────────────────────────
class TestLocation:
    def test_valid_json(self):
        raw = json.dumps({"lat": 28.014583, "lon": 120.678253})
        assert render_value("location", raw, {"value": raw}, {}) == "28.01458,120.67825"

    def test_invalid_json(self):
        assert render_value("location", "not-json", {"value": "not-json"}, {}) == STATE_UNKNOWN


# ───────────────────────────────────────────────────────────────────────────
# 4. 空调设定温度（数值直返）
# ───────────────────────────────────────────────────────────────────────────
class TestAcSetTemp:
    @pytest.mark.parametrize("val,expected", [
        (22.5, 22.5),
        (26, 26),
        (0, 0),          # 0 是合法温度下限边界（不过滤）
    ])
    def test_numeric(self, val, expected):
        assert render_value("ac_set_temp", val, {"value": val}, {}) == expected


# ───────────────────────────────────────────────────────────────────────────
# 5. 通用兜底
# ───────────────────────────────────────────────────────────────────────────
class TestGeneric:
    def test_short_string_passthrough(self):
        assert render_value("some_key", "abc", {"value": "abc"}, {}) == "abc"

    def test_long_string_truncated(self):
        long = "x" * 300
        r = render_value("some_key", long, {"value": long}, {})
        assert len(r) == 250
        assert r.endswith("...")

    def test_dict_serialized(self):
        v = {"a": 1, "b": 2}
        r = render_value("some_key", v, {"value": v}, {})
        assert json.loads(r) == v

    def test_int_passthrough(self):
        assert render_value("some_key", 42, {"value": 42}, {}) == 42

    def test_zero_not_treated_as_none(self):
        """★ 0 是合法值，不能被当成缺失"""
        assert render_value("some_key", 0, {"value": 0}, {}) == 0


# ───────────────────────────────────────────────────────────────────────────
# 6. ChargeStatus（复刻 App 归一化函数）
# ───────────────────────────────────────────────────────────────────────────
class TestChargeStatus:
    def _data(self, **kw):
        """构造带 vss 的 coordinator.data。"""
        return {"vss": {k: {"value": v} for k, v in kw.items()}}

    @pytest.mark.parametrize("cs,expected", [
        (3, "充电中"),
        (2, "电池加热"),
        (4, "电池保温"),
        (7, "充电告警"),
    ])
    def test_simple_states(self, cs, expected):
        d = self._data(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == expected

    def test_charge_complete(self):
        d = self._data(charge_status=5, charge_complete=1)
        assert render_value("charge_status", 5, {"value": 5}, d) == "充电完成"

    def test_charge_stopped(self):
        d = self._data(charge_status=5, charge_complete=0)
        assert render_value("charge_status", 5, {"value": 5}, d) == "已停止"

    def test_charge_alarm(self):
        d = self._data(charge_status=5, charge_complete=0, charge_fault=1)
        assert render_value("charge_status", 5, {"value": 5}, d) == "充电告警"

    def test_appointed_charge(self):
        """预约充电：三条件同时满足"""
        d = self._data(scheduled_charge_switch=1,
                       charge_gun_ac=2,
                       scheduled_charge_state=1,
                       charge_status=0)
        assert render_value("charge_status", 0, {"value": 0}, d) == "预约充电"

    # ── ★ 2026-09-28 修复：兜底改为「先查 translations 映射」 ──────────
    #
    # 旧行为：App 分支外的值一律 "—"（含 15），
    #   导致车未充电时用户看到 "—" 而非「未充电」（用户实测报告）。
    # 新行为：先查 translations.py 的 ChargeStatus 映射表，命中则用文案，
    #   未命中才退回 "—"（不猜、不显示裸数字）。

    @pytest.mark.parametrize("cs,expected", [
        (0, "未充电"),      # 映射表条目
        (10, "已插枪"),     # 映射表条目
        (15, "未充电"),     # ★ 用户实测的那个值
        (70, "充电中"),     # 映射表条目
        (130, "充电完成"),  # 映射表条目
    ])
    def test_mapped_code_uses_translation(self, cs, expected):
        """映射表里的值 → 显示中文文案（修复前这些全是 "—"）。"""
        d = self._data(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == expected

    @pytest.mark.parametrize("cs", [1, 9, 42, 99, 255])
    def test_unmapped_code_falls_back(self, cs):
        """★ 既不在 App 分支、也不在映射表的码 → 仍是 "—"。

        这条守住修复的边界：没证据的码【不能猜】，
        更不能把裸数字 1/42 直接透出去当文案。
        """
        d = self._data(charge_status=cs)
        assert render_value("charge_status", cs, {"value": cs}, d) == "—"

    def test_none_stays_none(self):
        """无值时不编造文案。"""
        assert render_value("charge_status", None, None, self._data()) is None


# ───────────────────────────────────────────────────────────────────────────
# 7. 回归测试：记录已知的语义决定
# ───────────────────────────────────────────────────────────────────────────
class TestRegressions:
    def test_door_semantics_documented(self):
        """★ 门语义：1=打开（源码依据 XDoorDataHandle.smali:310）

        这个测试不测 render_value（门由 binary_sensor 处理），
        而是作为【文档化断言】提醒后来者：
          - DoorSwitchStatus.*  用 == 1 判打开
          - DoorLockStatus.*    用 != 0 判未落锁
        """
        opened, closed = 1, 2
        assert (opened == 1) is True, "1 表示打开"
        assert (closed == 1) is False, "2 表示关闭（历史 bug：曾用 n != 0）"

    def test_zero_is_valid_value(self):
        """★ 0 不等于缺失（历史 bug：曾把 0 当 None）"""
        assert render_value("charge_limit", 0, {"value": 0}, {}) == 0


# ───────────────────────────────────────────────────────────────────────────
# 8. 回归：确保 translate() 被真正调用
# ───────────────────────────────────────────────────────────────────────────
class TestTranslateWired:
    """★ 2026-09-23 bug：抽 rendering.py 时漏了 import，
    导致 translate() 从未被调用，值永远是裸数字。

    这组测试确保「翻译管线是接通的」。
    """

    def test_path_lookup_available(self):
        """★ 2026-09-24：rendering 改用 signals.path_of()

        原先直接 import VSS_PATHS，架构 2.8 后改为经 signals 查询（消除重复）。
        """
        import rendering
        assert hasattr(rendering, "path_of"), "rendering 应导入 signals.path_of"
        # 能查到路径 → 翻译才可能生效
        assert rendering.path_of("battery_level") == "Vehicle.Powertrain.Battery.ResidueBattery"

    def test_translate_imported(self):
        import rendering
        assert hasattr(rendering, "translate")
        assert callable(rendering.translate)

    def test_raw_number_is_translated(self):
        """有翻译映射的信号，裸数字应变成中文"""
        # LowVolPwrMdSts: {0: "正常", 1: "低压模式"}
        d = {}
        r = render_value("low_vol_status", 0, {"value": 0}, d)
        assert r == "正常", f"应翻译为「正常」，实际 {r!r}"

    def test_untranslated_passthrough(self):
        """无翻译映射的信号，原值透传"""
        r = render_value("battery_level", 55, {"value": 55}, {})
        assert r == 55


# ───────────────────────────────────────────────────────────────────────────
# 9. 信号新鲜度（_signal_age）
# ───────────────────────────────────────────────────────────────────────────
class TestSignalAge:
    """★ 2026-09-23 新增：把上报时间转成可读年龄。

    用于 extra_state_attributes，让用户判断数据是否新鲜，
    而不改变实体状态（避免"实体突然变 unknown"）。
    """

    @staticmethod
    def _age(ts):
        # sensor.py 需要 HA 依赖，这里复制一份纯逻辑做单测
        from datetime import datetime
        if not ts:
            return None
        t = str(ts).strip()
        if t in ("", "0"):
            return None
        try:
            dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None
        secs = int((datetime.now() - dt).total_seconds())
        if secs < 0:
            return "刚刚"
        if secs < 60:
            return f"{secs} 秒前"
        if secs < 3600:
            return f"{secs // 60} 分钟前"
        if secs < 86400:
            return f"{secs // 3600} 小时前"
        days = secs // 86400
        if days < 30:
            return f"{days} 天前"
        if days < 365:
            return f"{days // 30} 个月前"
        return f"{days // 365} 年前"

    def test_invalid_returns_none(self):
        assert self._age(None) is None
        assert self._age("") is None
        assert self._age("0") is None
        assert self._age("not-a-date") is None

    def test_old_date(self):
        assert self._age("2024-07-22 15:57:18") == "2 年前"

    def test_recent(self):
        from datetime import datetime, timedelta
        t = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        assert self._age(t) == "30 分钟前"


class TestJsonSignalRendering:
    """★ 2026-09-24 新增：复杂 JSON 信号 → 可读值

    用户反馈："离车模式好像有问题"（显示一坨 JSON）
    """

    def test_xmode_on(self):
        val = json.dumps({
            "mainSwitch": True,
            "moveOffDatas": {
                "1721880052498": {
                    "acSwitch": True, "startTime": "07:00",
                    "temp": 22.0, "dayDesc": "法定工作日",
                }
            },
        })
        r = render_value("xmode", val, {"value": val, "ts": "1"}, {})
        assert "已开启" in str(r)
        assert "07:00" in str(r)
        assert "22" in str(r)

    def test_xmode_off(self):
        val = json.dumps({"mainSwitch": False, "moveOffDatas": {}})
        r = render_value("xmode", val, {"value": val, "ts": "1"}, {})
        assert r == "已关闭"

    def test_xmode_none(self):
        assert render_value("xmode", None, {"value": None, "ts": "1"}, {}) is None

    def test_xmode_bad_json(self):
        r = render_value("xmode", "not json", {"value": "not json", "ts": "1"}, {})
        assert r == STATE_UNKNOWN

    def test_fridge_reserve_off(self):
        val = json.dumps({"reserveSwitch": False, "startTime": "05:00"})
        r = render_value("fridge_reserve", val, {"value": val, "ts": "1"}, {})
        assert r == "已关闭"

    def test_fridge_reserve_on(self):
        val = json.dumps({
            "reserveSwitch": True, "startTime": "05:00",
            "temp": 5, "dayDesc": "每天",
        })
        r = render_value("fridge_reserve", val, {"value": val, "ts": "1"}, {})
        assert "已开启" in str(r)
        assert "05:00" in str(r)

    def test_vehicle_accounts_count(self):
        val = json.dumps({"acc1": {"role": "owner"}, "acc2": {"role": "family"}})
        r = render_value("vehicle_accounts", val, {"value": val, "ts": "1"}, {})
        assert r == "2 个账号"

    def test_provision_finish(self):
        val = json.dumps({"accountId": "123"})
        r = render_value("provision_finish", val, {"value": val, "ts": "1"}, {})
        assert r == "已激活"

    def test_charge_calibration(self):
        val = json.dumps({"id": "Vehicle.VehInfo"})
        r = render_value("charge_calibration", val, {"value": val, "ts": "1"}, {})
        assert r == "已启用"

    def test_no_raw_json_leak(self):
        """★ 关键：这些信号不应把原始 JSON 泄漏到 state"""
        cases = [
            ("xmode", {"mainSwitch": True, "moveOffDatas": {}}),
            ("fridge_reserve", {"reserveSwitch": True}),
            ("vehicle_accounts", {"a": {}}),
            ("provision_finish", {"accountId": "x"}),
        ]
        for key, obj in cases:
            val = json.dumps(obj)
            r = render_value(key, val, {"value": val, "ts": "1"}, {})
            assert not str(r).startswith("{"), (
                f"{key} 仍返回原始 JSON: {str(r)[:60]}")


class TestMaintenanceSignals:
    """★ 保养类信号渲染（2026-09-24 发现 maint_engine_level2 误判）"""

    def test_engine_level2_full(self):
        """保养二级：应显示名称+剩余里程+到期日"""
        val = json.dumps({
            "name": "增程器大保养",
            "maintainLeftMileage": 1234.5,
            "maintainDueDate": "20300115",
            "periodMileage": 10000,
        })
        r = render_value("maint_engine_level2", val, {"value": val, "ts": "1"}, {})
        assert "增程器大保养" in str(r)
        assert "1234" in str(r)
        assert "2030-01-15" in str(r)

    def test_engine_level2_not_wrongly_normal(self):
        """★ 关键的防回归：不能因为 maint_ 前缀误返回「正常」"""
        val = json.dumps({
            "name": "增程器大保养",
            "maintainLeftMileage": 1234.5,
            "maintainDueDate": "20300115",
        })
        r = render_value("maint_engine_level2", val, {"value": val, "ts": "1"}, {})
        assert r != "正常", (
            "maint_engine_level2 被 maint_ 前缀逻辑误伤了 —— "
            "它的字段结构与普通保养项不同")

    def test_engine_level2_no_mileage(self):
        """只有名称时也能显示"""
        val = json.dumps({"name": "增程器大保养"})
        r = render_value("maint_engine_level2", val, {"value": val, "ts": "1"}, {})
        assert r == "增程器大保养"

    def test_engine_level2_bad_json(self):
        r = render_value("maint_engine_level2", "bad", {"value": "bad", "ts": "1"}, {})
        assert r == "未知"

    def test_normal_maint_still_works(self):
        """普通保养项（maint_engine_oil）逻辑不受影响"""
        val = json.dumps({"maintainLeftMileage": 3000})
        r = render_value("maint_engine_oil", val, {"value": val, "ts": "1"}, {})
        assert "剩余 3000 km" in str(r)


class TestTravelStatus:
    """★ 行驶状态/驻车（2026-09-24 从 App parseTravelStatus 破解）

    源码逻辑（VehicleBaseState.smali:716）：
      gear == "P" → vehicleGearStatus = 4
      else        → vehicleGearStatus = 1

    实测：Vehicle.Cabin.TravelStatus = 4（P 档，驻车）
    这是 App 首页「已驻车 / 行驶中」的数据源。
    """

    def test_park_p(self):
        """★ 4 = P 档 = 已驻车"""
        r = render_value("travel_status", 4, {"value": 4}, {})
        assert "驻车" in str(r), f"值 4 应渲染为已驻车，实际 {r}"

    def test_driving(self):
        """★ 1 = 其他档 = 行驶中"""
        r = render_value("travel_status", 1, {"value": 1}, {})
        assert "行驶" in str(r), f"值 1 应渲染为行驶中，实际 {r}"

    def test_unknown_zero(self):
        """0 = 未知"""
        r = render_value("travel_status", 0, {"value": 0}, {})
        assert "未知" in str(r)

    def test_string_value(self):
        """字符串值也能处理（VSS 有时返回 str）"""
        r = render_value("travel_status", "4", {"value": "4"}, {})
        assert "驻车" in str(r), f"字符串 '4' 也应识别，实际 {r}"

    def test_bad_value(self):
        """异常值不应抛错"""
        r = render_value("travel_status", "bad", {"value": "bad"}, {})
        assert r is not None


# ───────────────────────────────────────────────────────────────────────────
# 里程统计（2026-09-28 新增）
# ───────────────────────────────────────────────────────────────────────────
class TestMileageStats:
    """陪伴天数 / 陪伴里程 / 耗电行驶（虚拟信号）。

    ★ 三者 signals.py 里 path=""，值【派生自 trip_total】
      （Vehicle.Carcenter.Trip.Total）的 JSON —— 不重复轮询。
    ★ 字段名与语义来自 App JS bundle 的 aggregate 映射（权威）：
        X.ownerTransferDate      = day               → 陪伴天数
        X.ownerTransferMileage   = 1e3*travelMileage → 陪伴里程
        X.ownerTransferCdMileage = 1e3*elecMileage   → 耗电行驶
    ★ 里程原始单位是【米】，渲染需 /1000 转 km。
    """

    #: 取自实车快照 lixiang-reverse/data/vss_full_state.json
    REAL = json.dumps({
        "ownerTransferDate": 774,
        "ownerTransferMileage": 61246200,
        "ownerTransferCdMileage": 53389000,
        "adMileage": 8582300,
        "mileage": 61284100,
    })

    @staticmethod
    def _data(payload=None):
        """构造 coordinator data（上游 trip_total 在里面）"""
        return {"vss": {"trip_total": {"value": payload if payload is not None else
                                       TestMileageStats.REAL, "ts": "1757000000"}}}

    def test_days_from_real_data(self):
        """陪伴天数 = ownerTransferDate（单位：天，不换算）"""
        assert render_value("stat_days", None, None, self._data()) == 774

    def test_mileage_meters_to_km(self):
        """陪伴里程：米 → 公里（实车 61246200 m = 61246.2 km）"""
        assert render_value("stat_mileage", None, None, self._data()) == 61246.2

    def test_elec_mileage_meters_to_km(self):
        """耗电行驶：米 → 公里（实车 53389000 m = 53389.0 km）"""
        assert render_value("stat_elec_mileage", None, None, self._data()) == 53389.0

    def test_trip_total_still_works(self):
        """回归：trip_total 行为不被本次改动影响"""
        sig = {"value": self.REAL, "ts": "1757000000"}
        assert render_value("trip_total", self.REAL, sig, {}) == 8582.3

    @pytest.mark.parametrize("key", ["stat_days", "stat_mileage", "stat_elec_mileage"])
    @pytest.mark.parametrize("bad", ["", "{}", "not json", "[1,2]", json.dumps({"other": 1})])
    def test_missing_or_bad_field_is_unknown(self, key, bad):
        """上游字段缺失 / JSON 非法 → unknown（不抛异常）"""
        assert render_value(key, None, None, self._data(bad)) == STATE_UNKNOWN

    @pytest.mark.parametrize("key", ["stat_days", "stat_mileage", "stat_elec_mileage"])
    def test_no_upstream_signal_is_unknown(self, key):
        """上游 trip_total 完全没数据 → unknown"""
        assert render_value(key, None, None, {"vss": {}}) == STATE_UNKNOWN

    def test_zero_days_is_zero_not_unknown(self):
        """★ 0 天是合法值（新车），不能当成 unknown"""
        d = self._data(json.dumps({"ownerTransferDate": 0}))
        assert render_value("stat_days", None, None, d) == 0

    def test_float_mileage_rounds_to_one_decimal(self):
        """米 → km 保留 1 位小数"""
        d = self._data(json.dumps({"ownerTransferMileage": 1234567}))
        assert render_value("stat_mileage", None, None, d) == 1234.6


class TestXmodeSubSwitch:
    """★ 2026-09-28：按时出发（xmode）必须看【单条计划的开关】，不能只看 mainSwitch。

    用户报告：「我们按时出发是没有打开的」，但我们显示「已开启」。
    实测真实数据：
        mainSwitch = True                 ← 只是功能模板层总开关（旧逻辑据此误判）
        moveOffDatas[0].subSwitch = False ← ★ 该条计划自身是关的
        weekOfDayStates 全 DISABLE        ← ★ 七天全不生效
    """

    @staticmethod
    def _data(sub_switch, days=None, ac=True):
        d = {
            "startTime": "07:00", "acSwitch": ac, "temp": 22.0,
            "dayDesc": "法定工作日", "subSwitch": sub_switch,
        }
        if days is not None:
            d["weekOfDayStates"] = days
        return json.dumps({
            "mainSwitch": True, "maxItemCount": 6,
            "moveOffDatas": {"1721880052498": d},
        })

    def test_main_switch_true_but_sub_off_is_closed(self):
        """★ 核心回归：mainSwitch=True 但 subSwitch=False → 必须显示「已关闭」。"""
        raw = self._data(False)
        sig = {"value": raw}
        out = render_value("xmode", raw, sig, {"vss": {"xmode": sig}})
        assert out == "已关闭", (
            f"mainSwitch=True 只是模板层开关；subSwitch=False 表示该条计划是关的，"
            f"应显示「已关闭」而非 {out!r}"
        )

    def test_all_days_disabled_is_closed(self):
        """七天全 DISABLE → 不生效 → 已关闭。"""
        raw = self._data(True, {"1": "DISABLE", "2": "DISABLE", "3": "DISABLE",
                                "4": "DISABLE", "5": "DISABLE", "6": "DISABLE",
                                "7": "DISABLE"})
        sig = {"value": raw}
        out = render_value("xmode", raw, sig, {"vss": {"xmode": sig}})
        assert out == "已关闭", f"七天全禁用应显示「已关闭」，实得 {out!r}"

    def test_sub_on_and_weekday_enabled_is_open(self):
        """subSwitch=True 且工作日启用 → 已开启 + 摘要。"""
        raw = self._data(True, {"1": "ENABLE", "2": "ENABLE", "3": "ENABLE",
                                "4": "ENABLE", "5": "ENABLE", "6": "DISABLE",
                                "7": "DISABLE"})
        sig = {"value": raw}
        out = render_value("xmode", raw, sig, {"vss": {"xmode": sig}})
        assert out.startswith("已开启"), f"应显示已开启，实得 {out!r}"
        assert "07:00" in out

    def test_missing_week_field_is_backward_compatible(self):
        """无 weekOfDayStates 字段（旧数据）→ 视为启用，只看 subSwitch。"""
        raw = self._data(True, None)
        sig = {"value": raw}
        out = render_value("xmode", raw, sig, {"vss": {"xmode": sig}})
        assert out.startswith("已开启"), f"无星期字段时应按启用处理，实得 {out!r}"

    def test_no_plans_at_all_is_closed(self):
        raw = json.dumps({"mainSwitch": True, "moveOffDatas": {}})
        sig = {"value": raw}
        out = render_value("xmode", raw, sig, {"vss": {"xmode": sig}})
        assert out == "已关闭"
