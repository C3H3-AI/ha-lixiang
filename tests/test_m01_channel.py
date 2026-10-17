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
        m = map_realtime_state(res)
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
