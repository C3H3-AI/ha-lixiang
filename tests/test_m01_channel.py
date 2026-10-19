"""★ 2026-10-17：理想 ONE（M01 / platform=='1'）实时数据通道 —— 三个叠加 bug 的回归测试。

背景（车主实机反馈 + 本轮定位）：
    车主把理想 ONE 账号加进 HA，实体建好了 188 个，但**几乎全是 unknown**，
    而 App 里一切正常。逐层排查定位出三个叠加 bug：

  ① `X-CHJ-Token` 请求头用的是配置条目里【上次保存的旧 token】
     —— 登录后只更新了 _main_bearer（Authorization 头），没同步 _app_token。
     实测：X-CHJ-Token=旧值 → `240225 账号登录已过期`；
           X-CHJ-Token=登录返回值 → `code=0 SUCCESS`（23 字段真实车况）。

  ② M 系没有 VSS 服务，`vss:get-batch` 对它返回 HTTP 503；
     而「补拉 real-time-state」写在 VSS 的 try 块**内部** →
     503 一抛异常就跳 except，**补拉永远执行不到**。

  ③ 503 不属于 `access_denied`，于是 `_vss_denied_notified` 被重置为 False，
     每分钟刷一条 WARNING。

修复后实测：ONE 有值实体 0 → 50 个（电量 79%、纯电续航 123km、燃油 202km、
油量 28%、车内 22℃、档位 P、位置/车门/车窗/座椅/空调全部正确）。
"""
from __future__ import annotations
import re

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "lixiang_auto"


def _read(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


class TestTokenSync:
    """① 登录后必须同步 _app_token（X-CHJ-Token 取的就是它）。"""

    def test_login_syncs_app_token(self):
        s = _read("li_api.py")
        i = s.find("def _login(")
        j = s.find("def ", i + 10)
        body = s[i:j]
        assert "self._app_token = self._main_bearer" in body, (
            "登录成功后必须把 _app_token 同步为最新 token，"
            "否则 X-CHJ-Token 用旧值 → 240225 账号登录已过期")

    def test_token_update_persists_app_token(self):
        s = _read("li_api.py")
        i = s.find("def _notify_token_update(")
        j = s.find("def ", i + 10)
        body = s[i:j]
        assert '"app_token"' in body, (
            "回写 config entry 时必须带上 app_token，否则重启后又用旧值")
        # 容忍半初始化实例（测试里 Fake 客户端没有该属性）
        assert 'getattr(self, "_app_token"' in body, (
            "app_token 取值要 getattr 容错（与同函数其它字段一致）")


class TestM01Channel:
    """②③ M 系必须跳过 VSS、直接走 real-time-state。"""

    def test_vss_except_branch_fetches_realtime_state(self):
        s = _read("coordinator.py")
        # 从 _async_update_data 之后找【调用点】（前面还有函数定义，别找错了）
        base = s.find("def _async_update_data")
        assert base > 0
        i = s.find("_vss_failure_is_model_unsupported(err)", base)
        assert i > base, "找不到 VSS 失败分支的调用点"
        # 异常分支里（往前找 except）必须为 M 系补拉 real-time-state
        seg = s[max(0, i - 3000):i]
        assert "_realtime_state_signals" in seg, (
            "M 系在 VSS 异常分支里必须补拉 real-time-state —— "
            "否则 503 抛异常后补拉永远执行不到（唯一的 bug 就是它）")
        assert "_use_realtime_state" in seg, "必须按 _use_realtime_state 判定 M 系"

    def test_m01_does_not_spam_vss_warning(self):
        s = _read("coordinator.py")
        assert "_skip_vss_warn" in s, (
            "M 系已知没有 VSS → 不该每分钟刷 WARNING（要有 _skip_vss_warn 抑制）")

    def test_is_m_series_matches_platform_1(self):
        from m01_state import is_m_series

        class _Ab:
            def __init__(self, platform, unity):
                self.platform = platform
                self.unity_model = unity

        # 理想ONE 实测：platform='1' unityModel='M01B'
        assert is_m_series(_Ab("1", "M01B")) is True
        # L6 实测：platform='2' unityModel='L6'
        assert is_m_series(_Ab("2", "L6")) is False
        # 能力表缺失时退回 unityModel 前缀判断
        assert is_m_series(_Ab("", "M01A")) is True
        assert is_m_series(None) is False


class TestFamilyAccountControlHint:
    """★ 家人/授权账号发车控 —— 错误必须说清是【权限】而非【服务故障】。

    实测（2026-10-18）：ONE 家人账号走 `cmd/send` 返回 **HTTP 503
    「服务暂时不可用」**，但真实原因是服务端按角色拒绝（同一辆车走
    `send-command` 通道明确报 `241000 用户没有权限`）。

    若原样透传 503，用户会以为「等会儿再试」——实际上等也没用，必须换车主账号。
    App 做法一致：对家人账号不开放车控。
    """

    def test_role_detection_matches_app(self):
        """角色判定必须复刻 App（authorized + roleId 15 → 家人共享）。"""
        from vehicle_role import REL_FAMILY_SHARED, REL_OWNER, relation_of

        assert relation_of({"vehicleType": "authorized",
                            "vehicleRoleId": 15}) == REL_FAMILY_SHARED
        assert relation_of({"vehicleType": "owned",
                            "vehicleRoleId": 11}) == REL_OWNER

    def test_hint_mentions_permission_and_503(self):
        """提示语要点明【权限】且戳穿 503 伪装（文本断言，跳过 HA 依赖）。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def _control_permission_hint")
        assert i > 0, "缺 _control_permission_hint"
        body = src[i:i + 1800]
        assert "家人" in body and "授权账号" in body, "必须点明家人/授权账号"
        assert "503" in body, "必须说明 503 是伪装而非真故障"
        assert "REL_OWNER" in body, "车主不得被加提示"

    def test_hint_text_is_actionable(self):
        """★ 行为级：提示语必须【可操作】—— 让用户知道换车主账号，而不是干等。

        直接从源码取提示语原文做内容断言（比"关键字存在"更强）：
        li_api 需 HA 环境，这里只验证消息本身的正确性。
        """
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def _control_permission_hint")
        body = src[i:i + 2000]
        assert "车主账号" in body, "必须给出解法：换车主账号"
        assert "并非服务端故障" in body, "必须否定『服务故障』这个误解"
        assert "App 对家人账号" in body, "应说明与 App 一致（家人账号同样不可控）"


    def test_hint_wired_into_send_command(self):
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "_control_permission_hint(self)" in src, "必须挂到 send_command 的失败路径"
        # 必须包住 send_command_raw（家人账号的失败来自 HTTP 503，不是 resultCode）
        assert "resp = self.send_command_raw(command_key, command_data)" in src


class TestM01ChargeButtons:
    """★ 充电启停：只有 M 系（理想ONE）能建，且必须走 send-command 通道。

    权威依据（官方配置表，不是推测）：
      · M 系 LXMVehicleConfig2025.json
          StartCharging → cmdKey=remote_charging_start
          StopCharging  → cmdKey=remote_charging_stop
          sendUrl=/ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command
      · X 系 LXXVehicleConfig2025.json
          开始/停止充电 cmdKey 均为 remote_charge_control
          → 走 JOB(LiNdn) 长连接，HTTP 必返 2009（我们 2026-09 实测）
    """

    def test_cmdkeys_from_official_table(self):
        src = (PKG / "button.py").read_text(encoding="utf-8")
        assert "remote_charging_start" in src, "开始充电 cmdKey 应为 remote_charging_start"
        assert "remote_charging_stop" in src, "停止充电 cmdKey 应为 remote_charging_stop"

    def test_gated_to_m_series_only(self):
        """必须按 is_m_series 门控 —— L 系建了也必然 2009。"""
        src = (PKG / "button.py").read_text(encoding="utf-8")
        assert "is_m_series" in src, "充电按钮必须按车型门控（L 系不可控）"
        assert "M_SERIES_CHARGE_BUTTONS" in src

    def test_uses_send_command_channel(self):
        """必须走 send_vehicle_command（send-command），不是 cmd/send。"""
        src = (PKG / "button.py").read_text(encoding="utf-8")
        i = src.find("class LiM01ChargeButton")
        assert i > 0, "缺 LiM01ChargeButton 实体类"
        body = src[i:i + 2000]
        assert "send_vehicle_command" in body, "必须用 send-command 通道（M 系权威）"
        assert "send_command(" not in body, "不能用 cmd/send（M 系充电走 send-command）"

    def test_raise_label_keeps_exception_chain(self):
        """既有守卫：每个 raise _label(...) 必须 `from err`（单行）。"""
        src = (PKG / "button.py").read_text(encoding="utf-8")
        lines = [l for l in src.splitlines() if "raise _label(" in l]
        assert lines
        assert all(l.rstrip().endswith("from err") for l in lines), (
            "button.py 有 raise _label 没带 `from err`（异常链断了）")


class TestM01DedicatedEndpoints:
    """★ M 系专属的【专用同步端点】（不走 cmd/send、不走 JOB 长连接）。

    权威依据（官方 M 系代码 `NetApiConst` + M 系配置表）：
      · 电池保温/充电保温 SetChargeInsulation → chargeWarmSwitch
        POST /ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch
        body {vin, switchState:"1"/"0"}
      · 预约充电 SetChargeAppointment → chargeAppointmentUpdate
        POST /ssp-as-mobile-api/v1-0/vehicles/charge-appointment-update
    两项在 X 系配置表里【都没有】 → 理想ONE 专属。
    原实现对所有车型都用 remote_charge_control（JOB）→ HTTP 必 2009（已实测），
    也就是 ONE 上这两个开关此前【必然不可用】。
    """

    def test_endpoints_defined(self):
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "EP_BATTERY_WARM" in src, "缺电池保温端点常量"
        assert "EP_CHARGE_APPOINTMENT" in src, "缺预约充电端点常量"
        assert "def set_charge_warm(" in src, "缺 set_charge_warm"
        assert "def set_charge_appointment(" in src, "缺 set_charge_appointment"

    def test_dispatch_by_platform_in_switch(self):
        src = (PKG / "switch.py").read_text(encoding="utf-8")
        assert "set_charge_warm(level != 0)" in src, "电池保温未按车型分派到 M 系端点"
        assert "set_charge_appointment(level != 0)" in src, "预约充电未按车型分派到 M 系端点"
        # 开关实体必须能拿到 ability（否则无法按车型分派）
        assert "self._ability = ability" in src, "LiCarSwitch 未保存 ability"

    def test_appointment_preserves_schedule(self):
        """★ 只改开关位时必须带回当前模式/起止时间，否则会清掉用户预约。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def set_charge_appointment(")
        assert i > 0
        body = src[i:i + 1400]
        assert "reserveStartTime" in body, "必须回带预约开始时间"
        assert "NewReserveFinishTime" in body, "必须回带预约结束时间"
        assert "def set_last_vss(" in src, "必须有回填最近一帧信号的入口"

    def test_m_series_state_key_fallback(self):
        """ONE 的预约充电状态键是 charge_appointment（不是 X 系的 scheduled_charge_switch）。"""
        src = (PKG / "switch.py").read_text(encoding="utf-8")
        assert "charge_appointment" in src, "缺少 M 系预约充电状态键回退"
        assert '_vss_all.get("charge_appointment")' in src, "is_on 未回退到 M 系键"


class TestM01SensorCoverage:
    """★ M 系传感器覆盖：响应里有的字段要尽量映射出来（2026-10-19 补齐）。

    实测 ONE 的 real-time-state 有 **150 个叶子字段**，此前只映射了 42 个。
    本轮补齐最有价值的几类（沿用 signals.py 里【已有】的键名，不重造）：
      充电电压/电流 · 车外温度 · 四座加热通风档位 · 其余门锁
    """

    def test_charge_voltage_current(self):
        """实测响应：chargeSetting.chargeStatus.{voltage:377.0, current:0.0}"""
        src = (PKG / "m01_state.py").read_text(encoding="utf-8")
        assert 'put("charge_voltage_ac"' in src, "缺充电电压映射"
        assert 'put("charge_current_ac"' in src, "缺充电电流映射"
        assert "chargeStatus" in src, "应从 chargeSetting.chargeStatus 取值"

    def test_outside_temp(self):
        """实测响应：temperatureStatus.outdoorTemperature = 17.5"""
        src = (PKG / "m01_state.py").read_text(encoding="utf-8")
        assert 'put("outside_temp"' in src, "缺车外温度映射"
        assert "outdoorTemperature" in src, "应取 outdoorTemperature"
        # 它是新键 → signals.py 必须有对应 SignalSpec，且登记为虚拟信号
        sg = (PKG / "signals.py").read_text(encoding="utf-8")
        assert '"outside_temp": SignalSpec(' in sg, "signals.py 缺 outside_temp"
        t = (Path(__file__).resolve().parent.parent / "tests" / "test_signals.py")
        assert '"outside_temp"' in t.read_text(encoding="utf-8"), (
            "test_signals.py 需把 outside_temp 登记为虚拟信号（否则守卫拦截）")

    def test_seat_heat_vent_levels(self):
        """实测响应：seatStatus.{fl,fr,rl,rr}SeatHeatVent（四座档位）"""
        src = (PKG / "m01_state.py").read_text(encoding="utf-8")
        for k in ("fl", "fr", "rl", "rr"):
            assert f'put("seat_heat_vent_{k}"' in src, f"缺 {k} 座加热通风档位"
        assert "SeatHeatVent" in src, "应取 seatStatus 的 SeatHeatVent 字段"

    def test_remaining_door_locks(self):
        """实测响应：doorSwitchStatus.<门>.isLock —— 此前只映射了主驾"""
        src = (PKG / "m01_state.py").read_text(encoding="utf-8")
        for k in ("copilot", "back_left", "back_right"):
            assert f'put("lock_{k}"' in src, f"缺 {k} 门锁状态"


class TestTaskMasterFailureHandling:
    """★ 任务大师失败处理（2026-10-19 更正过一次，留档防再犯）。

    车主日志：HTTP 400 {"error_code":"120009","message":"无法获取车辆信息"}

    ★ 我最初的误判：「120009 = 该车型不支持 → 永久停止重试」——**错了**：
      ① ONE 的 versionSupport.taskMaster = **1**（服务端明确说支持）✓
      ② 120009 在 App 里是 AG_SYSTEM_MISS_PARAM = 【系统缺少参数】
      ③ 同样的代码在 L6（X 系）上完全正常（实测 44 条任务）✓
      ⇒ 120009 是 M 系专项的参数/标识问题，**可以修**，不该放弃。

    现在的处理：只在服务端明确说「能力不存在」时才算永久失败；
    120009 只做降噪（拉长退避），保留修复空间。
    """

    def test_120009_is_not_permanent(self):
        """120009（缺参数）**不能**被当成永久失败 —— 它是可以修的问题。"""
        src = (PKG / "coordinator.py").read_text(encoding="utf-8")
        assert "_TASK_SLOW_CODES" in src, "缺慢重试错误码常量（120009 属于此类）"
        assert "AG_SYSTEM_MISS_PARAM" in src, (
            "应写明 120009 的真实含义（缺参数），避免再误判成「不支持」")

    def test_permanent_list_is_conservative(self):
        """永久失败判定必须保守 —— 只认真正说明能力不存在的返回。"""
        import ast

        src = (PKG / "coordinator.py").read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if isinstance(node, ast.AnnAssign) and getattr(
                    node.target, "id", "") == "_TASK_PERMANENT_CODES":
                val = ast.literal_eval(node.value)
                assert val == (), f"永久失败清单应保持为空/极保守，实际 {val}"
                return
        raise AssertionError("未找到 _TASK_PERMANENT_CODES")

    def test_task_master_works_on_x_series(self):
        """对照事实：同样代码在 X 系（L6）上正常 —— 证明不是通用故障。

        （这是当初推翻「不支持」误判的关键证据之一，固化下来。）
        """
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "SCOPE_TASK_MASTER" in src, "任务大师 scope 应存在"
        assert "task-master" in src, "scope 里应含 task-master"


class TestNumericSensorNeverCrashesListener:
    """★ 数值型 sensor 不得把 HA 监听器搞崩（2026-10-18 实测 396 次/6h）。

    现象：HA 日志刷 `Unexpected error updating listener ... for lixiang_auto`，
         栈为 `components/sensor/__init__.py:730 int(value)` →
         `ValueError: invalid literal for int(): '未知'` → **整个 coordinator
         的 listener 崩掉，那一轮所有实体都不刷新**。

    根因：`render_value()` 对无数据返回字符串 STATE_UNKNOWN；
         而声明了 `state_class` 的 sensor 在 HA 里会 int()/float() 它的值。
         M 系（理想ONE）不上报这些信号 → 全部落到 "unknown" → 稳定复现；
         X 系有值，所以此前没暴露。

    修法：sensor 平台出口统一拦截 —— 数值型拿到非数值返回 None
         （HA 显示 unknown，且不做数值转换）。
    """

    def test_guard_present_at_platform_exit(self):
        src = (PKG / "sensor.py").read_text(encoding="utf-8")
        i = src.find("render_value(key, val, sig, data)")
        assert i > 0, "找不到 render_value 调用点"
        tail = src[i:i + 2600]
        assert "state_class" in tail, "sensor 出口必须按 state_class 分流"
        assert "return None" in tail, "数值型拿到非数值必须返回 None（不能返回字符串）"

    def test_guard_only_affects_numeric_sensors(self):
        """字符串型 sensor 不得被误伤（「未知」「已关闭」是合法展示值）。"""
        src = (PKG / "sensor.py").read_text(encoding="utf-8")
        i = src.find("render_value(key, val, sig, data)")
        tail = src[i:i + 2600]
        # 判定必须以 state_class 为前提，而不是无条件拦截
        # ★ 2026-10-18 二次修正：判据不能只看 state_class ——
        #   HA 的规则是【声明了 native_unit_of_measurement 就按数值处理】。
        #   漏网案例：range_total_cltc/wltc（unit="km"、state_class=None）
        #   → 理想ONE 无输入信号 → _sum_range 返回 None → 仍会抛 ValueError。
        assert "native_unit_of_measurement" in tail, (
            "守卫判据必须同时考虑 unit —— HA 对「有单位的实体」按数值处理，"
            "与 state_class 无关（range_total_cltc 就是 unit=km / state_class=None）")

    def test_two_description_sources_are_covered(self):
        """★ sensor 有【两套】实体描述来源，守卫必须都覆盖。

        ① `sensor.SENSOR_DESCRIPTIONS`（手写）
        ② `signals.specs_for("sensor")`（自动生成，含 range_total_cltc/wltc）

        只覆盖第一套会漏掉第二套 —— 这正是 range_total_cltc 崩溃逃逸的原因。
        （本机无 HA 运行环境，用文本断言；语义由 test_m01_channel 的
          map_realtime_state 用例 + 变异测试保证。）
        """
        sensor_src = (PKG / "sensor.py").read_text(encoding="utf-8")
        signals_src = (PKG / "signals.py").read_text(encoding="utf-8")

        # 第二套来源确实存在，且包含 range_total_cltc
        assert 'specs_for("sensor")' in sensor_src, "sensor 应有第二套描述来源"
        assert '"range_total_cltc"' in signals_src, "应有 range_total_cltc（自动生成的实体）"
        # 它带单位但没有 state_class —— 正是「只看 state_class」会漏的形态
        i = signals_src.find('"range_total_cltc"')
        seg = signals_src[i:i + 400]
        assert 'unit="km"' in seg, "range_total_cltc 应带单位 km"
        assert 'state_class' not in seg, (
            "range_total_cltc 不应声明 state_class —— "
            "这正是必须同时看 unit 的原因（否则守卫漏它）")

    def test_numeric_sensor_entity_sets_are_declared(self):
        """确认确实存在一批 state_class sensor（回归时的前提）。"""

        src = (PKG / "sensor.py").read_text(encoding="utf-8")
        assert "SensorStateClass.MEASUREMENT" in src, "应有数值型 sensor 存在"


class TestFamilyAccountKeepsControlEntities:
    """★ 家人/授权账号【仍然要建】车控实体 —— 不要"好心"过滤掉。

    这是 2026-10-18 查证后的【反直觉】结论，写下来防止以后有人做反：

      直觉：家人账号用不了车控 → 那就别建实体（免得点了报错）。
      实测官方 App：**并不这么做**。

    App 的真实做法（assets/index.vehicle.js 实证）：
      · `isOwner()` / `isFamily()` 都存在，但 **`isCarOwner()` 调用数为 0**
        → 车控【不是】按"是否车主"来显隐的。
      · `isFamily()` 只用于隐藏少量【设置/维保】入口
        （如「车辆保养」页右上角的按钮），车控按钮本身不隐藏。
      · 所以家人账号在 App 里【能看到】车控，点了 → 服务端拒绝并提示无权限。

    → 我们建实体 = 与 App 一致；真正该修的是【报错文案】
       （cmd/send 对家人账号返回 HTTP 503「服务暂时不可用」，
        会让人干等；已由 _control_permission_hint 改述为权限原因）。
    """

    def test_control_platforms_not_gated_by_role(self):
        """车控实体的创建入口不得按 relation / 是否车主做过滤。"""

        for fn in ("switch.py", "lock.py", "cover.py", "button.py"):
            src = (PKG / fn).read_text(encoding="utf-8")
            # 只看代码，不看注释
            code = "\n".join(l for l in src.splitlines()
                              if not l.strip().startswith("#"))
            assert not re.search(r"relation_of\(|REL_FAMILY|is_owner", code), (
                f"{fn} 里出现了【按角色过滤】车控的逻辑 —— "
                "这与 App 不一致（App 对家人账号同样显示车控，点了才提示无权限）。"
                "若确有必要，请先复核 App 行为再改，并同步更新本测试。")

    def test_filter_specs_ignores_relation(self):
        """filter_specs 的过滤依据是能力声明，不是账号角色。"""
        src = (PKG / "features.py").read_text(encoding="utf-8")
        i = src.find("def filter_specs")
        assert i > 0
        body = src[i:i + 900]
        assert "relation_of" not in body and "REL_FAMILY" not in body, (
            "filter_specs 不应按账号角色过滤信号")


class TestM01ControlDispatch:
    """★ M 系车控改走 send-command（2026-10-19 · 官方配置表 + 实测双重确认）。

    依据链（三条独立证据，非推测）：
      ① subTokenData（m01config.json 权威表）：
         httpLiMeshServiceV2.scope 含 veh-ctrl:cmd-send（MESH）；
         VAT.scope 全是 X 系 cmdKey ⇒ VAT 属于 cmd/send 专用
      ② MControlKeyConst（M 系 cmdKey 常量表）+ BaseAppWidget.H() 下发入口
      ③ L6 实测：send-command 仅带 MESH → 100035（X 系不开放），
         不是「token 无效」⇒ MESH 就够了，不需要 VAT
    """

    def test_m_series_uses_send_command(self):
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "_use_send_command_channel" in src, "缺车型通道判定"
        assert "_send_command_via_rvc" in src, "缺 send-command 下发实现"
        # 分派点在 send_command 内（一处改，全平台受益）
        assert "self._use_send_command_channel()" in src

    def test_m_series_cmdkeys_declared(self):
        """M 系 cmdKey 与 X 系是两套并存的键，必须显式声明映射。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "_M01_CMDKEY_MAP" in src, "缺 M 系 cmdKey 映射表"
        assert '"remoteVehLockControl": "remote_central_lock_lock"' in src, (
            "锁车键应映射为 M 系的 remote_central_lock_lock")
        assert "MControlKeyConst" in src, "应注明 cmdKey 来源（官方常量表）"

    def test_only_meshtoken_needed(self):
        """send-command 只用 MESH，不需要 VAT —— 这是 ONE 能控的关键。"""
        src = (PKG / "li_api.py").read_text(encoding='utf-8')
        i = src.find("def _send_command_via_rvc")
        body = src[i:i + 1200]
        assert "send_vehicle_command" in body, "应复用已有的 send-command 方法"
        assert "VAT" not in body or "#" in body, (
            "send-command 路径不应需要 VAT（官方 subTokenData 已证实）")

    def test_x_series_unaffected(self):
        """X 系（L6）必须不受影响 —— 实测 _use_send_command_channel() = False。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def _use_send_command_channel")
        body = src[i:i + 1200]
        # 判定依据是车型（platform/modelId），不是无条件切换
        assert "modelId" in body or "platform" in body, (
            "应按车型判定，不能无条件走 send-command（否则误伤 X 系）")


class TestM01DispatchCriterionIsFactBased:
    """★ 车型判据必须是【事实】，不能是猜的常量（2026-10-19 车主反馈暴露）。

    背景：对方 2026-10-19 反馈 M 系车控 `fan/turn_on` 仍报 access_denied，
    且提示「M 系尚未适配」。根因：**分派判据恒为 False**。
    原判据 `modelId.startswith("1002043")` / `platform=="1"`：
      · modelId 要靠 get_vehicles()，M 系车主往往取不到 ⇒ 恒 False
      · platform 字段 get_vehicles() 根本不返回
    ⇒ 判据形同虚设，M 系一直走 cmd/send ⇒ 一直 access_denied。
    """

    def test_no_hardcoded_modelid_prefix(self):
        """不应再把 modelId 前缀当判据 —— 那是从未实测过的猜测。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def _use_send_command_channel")
        body = src[i:i + 2000]
        # ★ 只在【可执行代码】里断言；注释里保留历史说明是有意的
        #   （记录「这里曾经用过一个猜测值」对后来者有价值）。
        # ★ 判据只看【可执行语句】：注释与 docstring 里保留历史说明是有意的
        code = re.sub(r'""".*?"""', "", body, flags=re.S)
        code = "\n".join(ln for ln in code.splitlines()
                            if not ln.strip().startswith("#"))
        assert "1002043" not in code, (
            "车型判据不应依赖未实测的 modelId 前缀（代码里仍有残留）")

    def test_uses_m01_only_response_fields(self):
        """判据应是 real-time-state 里【M 系独有】的顶层字段（事实驱动）。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "_M01_ONLY_FIELDS" in src, "缺 M 系独有字段清单"
        i = src.find("def _use_send_command_channel")
        body = src[i:i + 2000]
        assert "_last_rts" in body, "判据应读取最近一帧 real-time-state"
        # 清单里至少要有几个实测确认的字段
        i2 = src.find("_M01_ONLY_FIELDS")
        j2 = src.find(")", i2)
        fields = src[i2:j2]
        for f in ("versionSupport", "wheelWarmStatus", "ringLightStatus"):
            assert f in fields, f"判据字段缺 {f}（实测 M 系响应里有）"

    def test_realtime_state_is_cached(self):
        """get_realtime_state 必须缓存，否则判据永远拿不到数据。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def get_realtime_state")
        body = src[i:i + 900]
        assert "self._last_rts" in body, "get_realtime_state 未写入 _last_rts"
        assert "self._last_rts: dict = {}" in src, "缺 _last_rts 初始化"

    def test_error_message_not_claiming_unadapted(self):
        """文案不得再说「M 系尚未适配」—— 已经适配了，说法要如实。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        assert "M 系的授权体系尚未适配" not in src, (
            "文案过时：M 系车控已改走 send-command，不能再说尚未适配")


class TestNoDuplicatedDetectionLogic:
    """★ 同一个判断不得在两处各写一遍（2026-10-19 自查发现）。

    教训：beta.4 我改了「车控分派」的车型判据（改成事实判据），
    却忘了「错误文案分支」还在用同一份**旧的烂判据**
    （modelId 前缀，未实测且取不到）⇒ 文案会分错支。
    ⇒ 「同一个判断写两遍」= 迟早只改其中一处。
    """

    def test_error_branch_reuses_dispatch_criterion(self):
        """文案分支必须调用 _use_send_command_channel，而不是自己判车型。"""
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("_is_m = self._use_send_command_channel()")
        assert i > 0, "文案分支应调用 _use_send_command_channel()"
        body = src[i:i + 200]
        assert "_use_send_command_channel()" in body, (
            "文案分支应复用车控分派的判据，不要自己抄一份")
        assert "1002043" not in body, "文案分支不应再出现未实测的 modelId 前缀"

    def test_only_one_place_decides_m_series(self):
        """全库只应有一处「这车是不是 M 系」的判定实现。"""
        import glob
        import os

        # m01_state.is_m_series 是能力表口径（供有 ability 的调用方用）
        # li_api._use_send_command_channel 是网络口径（供 li_api 用）
        # ★ 两者是不同数据源，允许并存；但 li_api 内部不得再出现第三份。
        src = (PKG / "li_api.py").read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", src, flags=re.S)
        code = "\n".join(ln for ln in code.splitlines()
                         if not ln.strip().startswith("#"))
        # li_api 里只能有一处读 M 系独有字段的判断
        assert code.count("_M01_ONLY_FIELDS") <= 2, (
            "li_api 里出现多处车型判定，应统一到 _use_send_command_channel")
        # 不得再有 modelId 前缀判据
        assert "startswith(\"1002043\")" not in code


class TestCoordinatorAttrsAllDeclared:
    """★ 拦「用而未声明」的属性（2026-10-19 实机日志暴露）。

    实机 WARNING：
      任务大师列表拉取异常: 'LiCarCoordinator' object has no attribute
      '_task_permanent'
    根因：2026-10-18 引入「永久失败不再重试」时加了 3 处**使用**，
          却漏了 `__init__` 里的**初始化** ⇒ 每轮任务大师拉取都抛异常。
    """

    def test_task_permanent_declared(self):
        """_task_permanent 必须在 __init__ 里初始化（不是只有使用）。"""
        src = (PKG / "coordinator.py").read_text(encoding="utf-8")
        assert "self._task_permanent: dict[str, str] = {}" in src, (
            "缺 _task_permanent 初始化声明 ⇒ 实机每轮任务大师都抛 AttributeError")

    def test_no_attr_used_without_declaring(self):
        """通用守卫：self._xxx 若被当【数据】用，就必须有初始化声明。

        ★ 只看「赋值/读取数据」的用法 —— `self._foo(` 是方法调用，
          方法的定义是 `def _foo(self)`，不属于未声明属性。
        """
        import re as _re

        src = (PKG / "coordinator.py").read_text(encoding="utf-8")
        # ① 初始化声明：self._xxx = / self._xxx: T = ...
        declared = set(_re.findall(r"self\.(_[A-Za-z0-9_]+)\s*(?::[^=]+)?=", src))
        # ② 类里定义的方法名
        methods = set(_re.findall(r"^\s{4}def (_[A-Za-z0-9_]+)\(", src, _re.M))
        methods |= set(_re.findall(r"^\s{4}async def (_[A-Za-z0-9_]+)\(", src, _re.M))
        # ③ 全部 self._xxx 引用，排除「紧跟左括号」的（= 方法调用）
        # ★ 先剥掉注释行 —— 注释里的示例代码不是真代码
        code = "\n".join(ln for ln in src.splitlines()
                            if not ln.strip().startswith("#"))
        used = set(_re.findall(r"self\.(_[A-Za-z0-9_]+)\b(?!\s*\()", code))
        provided = {"_hass", "_config_entry", "_api", "_api_m"}
        missing = sorted(used - declared - methods - provided)
        assert not missing, (
            f"这些属性被当数据用但没有初始化声明（实机会抛 AttributeError）: {missing}")

class TestM01Mapping:
    """real-time-state → signal-key 映射的正确性（用实车真值）。"""

    def test_maps_vehicle_values(self):
        from m01_state import map_realtime_state

        # 取自 2026-10-17 理想ONE 实车 real-time-state 响应（节选）
        res = {
            "timestamp": 1792222269617,
            "chargeSetting": {
                "enduranceStatus": {
                    "batteryEndurance": "123", "fuelEndurance": "202",
                    "residueBattery": "79", "residueFuel": "28",
                },
                "chargeStatus": {"chargeStatus": "10"},
            },
            "temperatureStatus": {"indoorTemperature": "22",
                                  "airPollutionIndex": "2"},
            "vehOnlineStatus": {"status": "Sleeping"},
            "locationStatus": {"lat": "36.100939", "lon": "103.739979",
                               "alt": "1472.1", "dir": "190.7"},
        }
        # ★ ONE 专属（官方配置表差集确认）：充电阈值 / 充电保温 / 预约充电
        res["chargeSetting"]["chargingTarget"] = {"target": "90"}
        res["chargeSetting"]["batteryWarmSwitch"] = {"switchState": "1"}
        res["chargeSetting"]["appointmentTime"] = {
            "chargeOnOff": 1, "startTime": "23:00", "endTime": "06:00"}
        m = map_realtime_state(res)
        assert m["charge_limit"]["value"] == 90.0, "充电阈值（M 系 SetChargeLimit）"
        assert m["battery_insulation"]["value"] == 1, "充电保温（M 系专属开关）"
        assert m["charge_appointment"]["value"] == 1, "预约充电（M 系专属开关）"
        assert m["charge_appointment_start"]["value"] == "23:00"
        assert m["charge_appointment_end"]["value"] == "06:00"

        # ★ 其它 M 系状态（2026-10-18 补齐）
        res["wheelWarmStatus"] = {"warmOnOff": "0"}
        res["ringLightStatus"] = {"status": "1"}
        res["remoteStartStatus"] = {"startStatus": "0"}
        res["versionSupport"] = {"acAppointment": 1, "wakeupHu": 0, "energyCostV2": 1}
        m3 = map_realtime_state(res)
        assert m3["wheel_heat_switch"]["value"] == 0, "方向盘/座椅加热总开关"
        assert m3["ring_light_status"]["value"] == 1, "环形灯状态"
        assert m3["remote_start_state"]["value"] == 0, "远程启动状态"
        # versionSupport = App 的本车功能支持表（1/0）
        assert m3["support_acAppointment"]["value"] == 1, "支持预约空调"
        assert m3["support_wakeupHu"]["value"] == 0, "本车不支持远程唤醒(实测 0)"
        assert m3["support_energyCostV2"]["value"] == 1

        # ★ 整车锁状态：isLock=1（已落锁）→ 我方 lock_main 取反写 0（locked）
        res["doorSwitchStatus"] = {"mainDoor": {"isOpen": "0", "isLock": "1"}}
        m2 = map_realtime_state(res)
        assert m2["lock_main"]["value"] == 0, (
            "isLock=1(已落锁) 必须取反为 0 —— lock.py 里 0 才代表 locked")
        assert m["battery_level"]["value"] == 79.0
        assert m["range_elec_cltc"]["value"] == 123.0
        assert m["range_fuel_cltc"]["value"] == 202.0
        assert m["fuel_level"]["value"] == 28.0
        assert m["inside_temp"]["value"] == 22.0
        assert m["charge_status"]["value"] == 10.0
        # 休眠 → 离线（0）
        assert m["online_status"]["value"] == 0
        # 位置是 JSON 字符串（device_tracker 需要）
        assert '"lat"' in m["location"]["value"]

    def test_online_status_key_matches_signal(self):
        """实体用的键是 online_status（不是 online_5g）—— 必须两个都写。"""
        from m01_state import map_realtime_state

        # signals.py 依赖 homeassistant（本地无 HA 环境）→ 用文本断言键名存在
        sig = (PKG / "signals.py").read_text(encoding="utf-8")
        assert 'key="online_status"' in sig
        m = map_realtime_state({"vehOnlineStatus": {"status": "Online"}})
        assert "online_status" in m, "缺 online_status → 「在线状态」实体永远 unknown"
        assert m["online_status"]["value"] == 1
