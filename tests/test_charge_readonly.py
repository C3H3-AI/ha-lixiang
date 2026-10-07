"""充电实体「只读标注 + 明确失败」测试（2026-09-28 新增）

★ 背景（用户视角）：

  6 个充电实体在 HA 里是【可写平台】：
      number.充电上限 / select.充电模式 / switch.预约充电 /
      switch.电池保温 / time.充电开始时间 / time.充电结束时间

  用户能点，但命令 cmdKey=remote_charge_control 走理想 App 的
  LiNdn（JOB）长连接，HTTP cmd/send 不支持 → 必然 resultCode=2009。
  旧行为：点了 → 等一次网络往返 → HA 报「执行失败」，
  用户以为集成坏了。

★ 本测试守卫的四个不变量：

  ① 实体【仍存在】（不删除 —— 用户可能已用其状态做自动化）
  ② 实体状态属性里有「只读原因」，写明为什么不能控制
  ③ 写入时【在发送前】就抛出 LiChannelNotSupported（明确原因），
     而不是静默消耗一次车控请求后再抛含混的「执行失败」
  ④ 只读原因文案在「属性」与「异常」两处【逐字一致】

★ 同时守卫【反向】不变量（防误伤）：

  ⑤ 实测可用的命令（寻车/锁车/空调/哨兵/拍照）不得被标注或拦截

★ 为什么用「真实执行」而不是「读源码字符串」：

  test_charge_channel.py 已有源码级守卫（检查 2009 分支）。
  但源码里有 `LiChannelNotSupported(` 不代表运行时真会抛。
  本文件通过桩掉 homeassistant，把 li_api.py 与 4 个平台模块
  【真正 import 进来执行】，断言真实的对象行为。

  代价：需要在 import 前构造一个最小的 homeassistant 桩。
  这是刻意的取舍 —— 行为断言比字符串断言更能防回归。
"""
from __future__ import annotations

import ast
import asyncio
import datetime
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"

# JOB 通道命令（必然 2009）——与 li_api._JOB_CHANNEL_COMMANDS 保持一致
_JOB_CMDS = [
    "remote_charge_control",
    "remote_charging_start",
    "remote_charging_stop",
    "remoteChargingControl",
    "chargeLimit",
    # ★ 2026-10-07 真机实测 2009（destParams=metaJobService.*，APK 实证）
    "sentinelModeSetting",
    "mobileVehSvm",
]

# 反向：HTTP 可用的命令【不得】被拦截
_WORKING_CMDS = [
    "remoteVehSearch",
    "remoteVehLockControl",
    "remoteVehACSmartControl",
]


# ---------------------------------------------------------------------------
# 最小 homeassistant 桩 + 隔离加载
# ---------------------------------------------------------------------------

def _install_ha_stubs() -> None:
    """构造最小 homeassistant 包，使 li_api/number/select/switch/time 可 import。

    ★ 只桩掉 import 期真正会被求值的东西（类/base/常量）。
      事件循环、真实 HA 运行时都不需要。
    """
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    def _sub(name: str, **attrs):
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    class _Base:
        def __init__(self, *a, **k):
            pass

    class _CoordinatorEntity:
        def __init__(self, coordinator=None, *a, **k):
            self.coordinator = coordinator

        @property
        def available(self):
            return True

    class _Entity:
        _attr_has_entity_name = False

        def async_write_ha_state(self):
            pass

    _sub("homeassistant.core", HomeAssistant=_Base, callback=lambda f: f)
    _sub(
        "homeassistant.const",
        PERCENTAGE="%",
        UnitOfTemperature=types.SimpleNamespace(CELSIUS="CELSIUS"),
    )
    _sub("homeassistant.config_entries", ConfigEntry=_Base)
    _sub("homeassistant.exceptions", HomeAssistantError=Exception)
    for extra in ("homeassistant.helpers", "homeassistant.util", "homeassistant.util.dt"):
        _sub(extra)
    _sub("homeassistant.helpers.device_registry", DeviceInfo=_Base, async_get=lambda *a, **k: None)
    _sub("homeassistant.helpers.entity_platform", AddEntitiesCallback=_Base)
    _sub(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=_CoordinatorEntity,
        CoordinatorUpdateFailed=Exception,
    )
    _sub("homeassistant.helpers.entity", Entity=_Entity)
    _sub(
        "homeassistant.components.number",
        NumberEntity=_Entity,
        NumberDeviceClass=types.SimpleNamespace(TEMPERATURE="TEMPERATURE"),
        NumberMode=types.SimpleNamespace(BOX="BOX"),
    )
    _sub("homeassistant.components.select", SelectEntity=_Entity)
    _sub("homeassistant.components.switch", SwitchEntity=_Entity)
    _sub("homeassistant.components.time", TimeEntity=_Entity)


def _load(mod_name: str):
    """按包内路径加载 lixiang_auto.<mod_name>（绕开会 import 全部平台的 __init__）。"""
    spec = importlib.util.spec_from_file_location(
        f"lixiang_auto.{mod_name}", _INTEG / f"{mod_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"lixiang_auto.{mod_name}"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mods():
    """一次性加载 li_api + 4 个平台模块。"""
    _install_ha_stubs()
    # lixiang_auto 注册成指向真实目录的包，但不执行 __init__
    pkg = types.ModuleType("lixiang_auto")
    pkg.__path__ = [str(_INTEG)]
    sys.modules["lixiang_auto"] = pkg

    li_api = _load("li_api")
    gate = _load("gate")
    # require_control 会检查 HA 运行时开关；测试里放行，才能测到通道守卫
    gate.require_control = lambda f: f

    out = {"li_api": li_api}
    for name in ("number", "select", "switch", "time"):
        m = _load(name)
        # 平台模块在 import 时已绑定 require_control，需同步替换
        if hasattr(m, "require_control"):
            m.require_control = lambda f: f
        out[name] = m
    return out


# ---------------------------------------------------------------------------
# 测试用桩
# ---------------------------------------------------------------------------

class _FakeHass:
    """hass 桩：executor job 直接同步调用。"""

    async def async_add_executor_job(self, fn, *a):
        return fn(*a)


class _FakeCoordinator:
    def __init__(self, vss=None):
        self.data = {"vss": vss or {}}

    async def async_request_refresh(self):
        pass


class _GuardedApi:
    """模拟 li_api 的真实行为：发送时先过通道守卫。

    ★ 这正是我们要守的不变量：
      「守卫失败发生在 send_command 内部 ⇒ 调用方不必各自重复判断」。
    """

    def __init__(self, li_api):
        self._li_api = li_api
        self.calls: list[tuple[str, dict]] = []

    def send_command(self, key, data=None, **kw):
        self.calls.append((key, data))
        self._li_api.ensure_job_channel_supported(key)
        return {"pushState": 5, "resultCode": 0}


VIN = "TESTVIN0000000000"


def _make_number(mods, cmd_key, **over):
    """构造一个 LiCarNumber（默认是充电上限）。"""
    kw = dict(
        suffix="charge_limit", name="充电上限", icon="mdi:battery-charging-80",
        state_key="charge_limit", cmd_key=cmd_key,
        data_builder=mods["number"]._charge_limit_payload,
        minimum=80, maximum=100, step=1, unit="%", device_class=None,
    )
    kw.update(over)
    ent = mods["number"].LiCarNumber(_FakeCoordinator(), None, None, VIN, **kw)
    ent.hass = _FakeHass()
    return ent


def _make_switch(mods, control_type, name):
    ent = mods["switch"].LiCarSwitch(
        _FakeCoordinator(), None, None, VIN,
        suffix="s", name=name, icon="mdi:x",
        state_key="k", control_type=control_type,
    )
    ent.hass = _FakeHass()
    ent._optimistic_on = None
    ent._optimistic_until = 0.0
    return ent


# ---------------------------------------------------------------------------
# ① 通道判定
# ---------------------------------------------------------------------------

class TestChannelDetection:
    @pytest.mark.parametrize("cmd", _JOB_CMDS)
    def test_job_commands_are_rejected_immediately(self, mods, cmd):
        """★ JOB 通道命令必须在【发送前】抛 LiChannelNotSupported。"""
        with pytest.raises(mods["li_api"].LiChannelNotSupported) as ei:
            mods["li_api"].ensure_job_channel_supported(cmd)
        err = ei.value
        assert err.result_code == 2009, "应带 resultCode=2009，便于日志对照"
        assert err.push_state == 7, "应带 pushState=7"

    @pytest.mark.parametrize("cmd", _WORKING_CMDS)
    def test_working_commands_pass(self, mods, cmd):
        """★ 反向守卫：实测可用的命令不得被拦（否则真功能被误杀）。"""
        mods["li_api"].ensure_job_channel_supported(cmd)   # 不抛即通过

    def test_exception_type_is_command_error(self, mods):
        """保持向后兼容：仍是 LiCommandError 子类。"""
        assert issubclass(
            mods["li_api"].LiChannelNotSupported, mods["li_api"].LiCommandError
        )

    def test_message_names_channel_and_is_actionable(self, mods):
        """错误消息要说清「走什么通道」+「不支持」，不能只说"失败"。"""
        with pytest.raises(mods["li_api"].LiChannelNotSupported) as ei:
            mods["li_api"].ensure_job_channel_supported("remote_charge_control")
        msg = str(ei.value)
        assert "LiNdn" in msg
        assert "不支持" in msg
        assert "remote_charge_control" in msg


# ---------------------------------------------------------------------------
# ② 只读标注（extra_state_attributes）
# ---------------------------------------------------------------------------

class TestReadonlyAttributes:
    def test_number_charge_limit_annotated(self, mods):
        ent = _make_number(mods, mods["number"].CMD_CHARGE)
        attrs = ent.extra_state_attributes
        assert attrs[mods["li_api"].JOB_CHANNEL_REASON_ATTR] == mods["li_api"].JOB_CHANNEL_NOTICE

    def test_select_charging_mode_annotated(self, mods):
        ent = mods["select"].LiCarChargingModeSelect(_FakeCoordinator(), None, None, VIN)
        attrs = ent.extra_state_attributes
        assert attrs[mods["li_api"].JOB_CHANNEL_REASON_ATTR] == mods["li_api"].JOB_CHANNEL_NOTICE

    @pytest.mark.parametrize("ct,name", [
        ("__SCHEDULED__", "预约充电"),
        ("__INSULATION__", "电池保温"),
        ("__SENTRY__", "哨兵模式"),
    ])
    def test_switch_charge_entities_annotated(self, mods, ct, name):
        ent = _make_switch(mods, ct, name)
        attrs = ent.extra_state_attributes
        assert attrs[mods["li_api"].JOB_CHANNEL_REASON_ATTR] == mods["li_api"].JOB_CHANNEL_NOTICE

    def test_time_entities_annotated(self, mods):
        for spec in mods["time"].TIME_ENTITIES:
            ent = mods["time"].LiCarTime(_FakeCoordinator(), None, None, VIN, *spec)
            attrs = ent.extra_state_attributes
            assert attrs[mods["li_api"].JOB_CHANNEL_REASON_ATTR] == mods["li_api"].JOB_CHANNEL_NOTICE

    def test_wording_is_about_lin_dn_channel(self, mods):
        """文案必须点明 LiNdn 通道（用户能据此搜到已知限制）。"""
        notice = mods["li_api"].JOB_CHANNEL_NOTICE
        assert "LiNdn" in notice
        assert "不支持" in notice

    # ---- 反向：非充电实体不得被标注 ----

    def test_ac_temp_number_not_annotated(self, mods):
        """空调设定温度（实测可用）不得被标为只读。"""
        ent = _make_number(
            mods, mods["number"].CMD_AC,
            suffix="ac_set_temp", name="空调设定温度", state_key="ac_set_temp",
            data_builder=mods["number"]._ac_temp_payload,
            minimum=16, maximum=30, unit="CELSIUS",
        )
        assert mods["li_api"].JOB_CHANNEL_REASON_ATTR not in ent.extra_state_attributes

    def test_sentry_switch_annotated(self, mods):
        """★ 哨兵（2026-10-07 实证 destParams=metaJobService → 2009）应标只读。"""
        ent = _make_switch(mods, "__SENTRY__", "哨兵模式")
        attrs = ent.extra_state_attributes
        assert attrs[mods["li_api"].JOB_CHANNEL_REASON_ATTR] == mods["li_api"].JOB_CHANNEL_NOTICE


# ---------------------------------------------------------------------------
# ③ 写入抛明确异常（真实调用，不是读源码）
# ---------------------------------------------------------------------------

class TestWriteRaisesClearError:
    def test_number_write_raises(self, mods):
        ent = _make_number(mods, mods["number"].CMD_CHARGE)
        ent._api = _GuardedApi(mods["li_api"])
        with pytest.raises(mods["li_api"].LiChannelNotSupported):
            asyncio.run(ent.async_set_native_value(90))

    def test_select_write_raises(self, mods):
        ent = mods["select"].LiCarChargingModeSelect(_FakeCoordinator(), None, None, VIN)
        ent.hass = _FakeHass()
        ent._api = _GuardedApi(mods["li_api"])
        with pytest.raises(mods["li_api"].LiChannelNotSupported):
            asyncio.run(ent.async_select_option("低价充电"))

    @pytest.mark.parametrize("ct,name", [
        ("__SCHEDULED__", "预约充电"),
        ("__INSULATION__", "电池保温"),
        ("__SENTRY__", "哨兵模式"),
    ])
    def test_switch_write_raises(self, mods, ct, name):
        ent = _make_switch(mods, ct, name)
        ent._api = _GuardedApi(mods["li_api"])
        with pytest.raises(mods["li_api"].LiChannelNotSupported):
            asyncio.run(ent.async_turn_on())

    def test_time_write_raises(self, mods):
        ent = mods["time"].LiCarTime(
            _FakeCoordinator(), None, None, VIN, *mods["time"].TIME_ENTITIES[0]
        )
        ent.hass = _FakeHass()
        ent._api = _GuardedApi(mods["li_api"])
        with pytest.raises(mods["li_api"].LiChannelNotSupported):
            asyncio.run(ent.async_set_value(datetime.time(22, 30)))

    def test_error_message_matches_attribute_wording(self, mods):
        """★ ④ 用户在属性里看到的原因，与写入报错的原因必须【逐字一致】。

        否则会出现「属性说是 A，报错说是 B」的困惑。
        """
        li_api = mods["li_api"]
        ent = _make_number(mods, mods["number"].CMD_CHARGE)
        notice = ent.extra_state_attributes[li_api.JOB_CHANNEL_REASON_ATTR]
        ent._api = _GuardedApi(li_api)
        with pytest.raises(li_api.LiChannelNotSupported) as ei:
            asyncio.run(ent.async_set_native_value(90))
        assert notice in str(ei.value), "异常消息必须包含属性里的「只读原因」原文"

    def test_no_command_actually_sent(self, mods):
        """★ 关键：失败必须发生在【发出请求之前】。

        用 _GuardedApi 记录调用：守卫在 send_command 内抛出，
        所以 API 对象被调用了，但【真实 HTTP 请求没发出去】是 li_api 的责任 ——
        这里断言「抛错类型正确」，配合 li_api 源码守卫一起保证。
        """
        api = _GuardedApi(mods["li_api"])
        ent = _make_number(mods, mods["number"].CMD_CHARGE)
        ent._api = api
        with pytest.raises(mods["li_api"].LiChannelNotSupported):
            asyncio.run(ent.async_set_native_value(90))
        assert api.calls and api.calls[0][0] == "remote_charge_control"


# ---------------------------------------------------------------------------
# ④ 实体仍然存在（「只增不删」）
# ---------------------------------------------------------------------------

class TestPreSendGuardWiredIntoApi:
    """★ 守卫必须真的接在 li_api 的发命令路径上，而不是只定义了一个函数。

    ★ 为什么单独守这一条（2026-09-28 变异测试发现）：

      最初我只测了 ensure_job_channel_supported() 本身 +
      用 _GuardedApi 桩模拟"li_api 会调守卫"。
      结果：把 li_api.send_command_raw 里那行守卫删掉，
            **全部 572 个测试依然通过** —— 桩把真实缺陷掩盖了。

      这正是本项目最该防的失效模式：测试通过但功能是坏的。
      所以这里必须【不靠桩】，直接从源码断言守卫被调用。

    ★★ 第一个版本仍然漏检，原因值得记下来：

      我一开始写成 `"ensure_job_channel_supported(" in body`。
      但 body 里那段【注释】正好写着
          「理由见 ensure_job_channel_supported() 的 docstring」
      → 注释里带括号的函数名让子串检查【永远为真】，
        把真正的调用删掉后测试照样通过（实测确认）。

      教训：对代码做子串断言前必须【先剥掉注释】，
            否则注释会替代码"背书"。
            这里改用 AST，只认真正的函数调用。
    """

    @staticmethod
    def _body_node(src: str):
        """用 AST 取 send_command_raw 的函数节点（注释天然被忽略）。"""
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "send_command_raw":
                return node
        return None

    @staticmethod
    def _called_names(node) -> set[str]:
        """函数体内【真正被调用】的函数名集合（不含注释/docstring）。"""
        names: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name):
                    names.add(f.id)
                elif isinstance(f, ast.Attribute):
                    names.add(f.attr)
        return names

    def test_guard_called_in_send_command_raw(self, mods):
        """send_command_raw 必须【真正调用】守卫（AST 级，注释不算）。"""
        src = (_INTEG / "li_api.py").read_text(encoding="utf-8")
        node = self._body_node(src)
        assert node is not None, "未找到 send_command_raw 函数"
        called = self._called_names(node)
        assert "ensure_job_channel_supported" in called, (
            "★ send_command_raw 里缺少 ensure_job_channel_supported 调用 —— "
            "充电命令会重新变成『静默 2009』"
        )

    def test_guard_runs_before_body_construction(self, mods):
        """守卫要在构造请求体（now_ms = ...）之前执行。"""
        src = (_INTEG / "li_api.py").read_text(encoding="utf-8")
        node = self._body_node(src)
        assert node is not None
        i_guard = i_now = -1
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "ensure_job_channel_supported"):
                i_guard = sub.lineno
            if (isinstance(sub, ast.Assign) and sub.targets
                    and getattr(sub.targets[0], "id", "") == "now_ms"):
                i_now = sub.lineno
        assert i_guard > 0, "缺少守卫调用"
        assert i_now > 0, "未找到请求体构造起点（now_ms 赋值）"
        assert i_guard < i_now, (
            f"守卫应在构造请求体之前执行 (守卫 L{i_guard}, 请求体 L{i_now})"
        )

    def test_no_duplicate_guard_logic_in_platforms(self, mods):
        """平台层不应各自复制一份判断（否则改一处忘一处）。

        统一走 li_api。平台侧只要"标注 + 让它抛"即可。
        """
        for name in ("number", "select", "switch", "time"):
            src = (_INTEG / f"{name}.py").read_text(encoding="utf-8")
            assert "_JOB_CHANNEL_COMMANDS" not in src, (
                f"{name}.py 复制了 JOB 命令表 —— 应统一用 li_api 的常量/函数"
            )


class TestEntitiesStillExist:
    def test_number_setup_still_creates_charge_limit(self, mods):
        """充电上限必须仍在 number 平台的实体列表里。"""
        src = (_INTEG / "number.py").read_text(encoding="utf-8")
        assert 'suffix="charge_limit"' in src, "充电上限被删除了！用户自动化会断"
        assert "CMD_CHARGE" in src

    def test_select_setup_still_creates_charging_mode(self, mods):
        src = (_INTEG / "select.py").read_text(encoding="utf-8")
        assert "LiCarChargingModeSelect(" in src.split("async_setup_entry")[1]

    def test_switch_list_still_has_charge_switches(self, mods):
        names = {s[1] for s in mods["switch"].SWITCHES}
        assert "预约充电" in names
        assert "电池保温" in names

    def test_time_list_still_has_both(self, mods):
        suffixes = {t[0] for t in mods["time"].TIME_ENTITIES}
        assert suffixes == {"charge_start_time", "charge_end_time"}

    def test_charge_params_unchanged(self, mods):
        """★ 不得改 remote_charge_control 的【参数】（参数是对的，障碍是通道）。"""
        payload = mods["number"]._charge_limit_payload(90)
        assert payload == {
            "statusControlRequest": 255,
            "controlType": "1",
            "chargingLimit": "90",
        }
