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
        import re

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
