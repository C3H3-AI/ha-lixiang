"""信号声明表（自动生成，需人工校对）

来源: /media/duola/devdata/AI-workspace/home-assistant-nas/ha-test/config/custom_components/lixiang_auto
生成: tools/gen_signals.py

⚠️ 这是【机械合并】的结果，语义需人工校对：
  · kind → semantics 的映射需逐条确认
  · 分频是根据前缀猜的，可能不准
  · 翻译需与 translations.py 对齐
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


def _sum_range(vss: dict, std: str) -> float | None:
    """总续航 = 纯电续航 + 燃油续航（App 也这么算）。

    纯电车型没有 FuelEndurance → 只取 PureElecEnduranceMileInd。
    增程版两者都有 → 相加。
    两个都是 None → 返回 None（实体显示 unknown）。

    Why not Vehicle.Cabin.{std}.EnduranceMil?
      App smali (LiMeshPathHelper.smali) 证实它**不订阅这个路径** ——
      XEnduranceDataHandle 只用 PureElecEnduranceMileInd 和
      FuelEnduranceMileInd。服务端可能对部分车型（如纯电 i6）不返回。
    """
    def _val(k: str):
        sig = vss.get(k) or {}
        raw = sig.get("value")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    elec = _val(f"range_elec_{std.lower()}")
    fuel = _val(f"range_fuel_{std.lower()}")

    if elec is None and fuel is None:
        return None
    return (elec or 0.0) + (fuel or 0.0)


class Freq(StrEnum):
    """轮询频率档位。"""
    HIGH = "high"
    MID = "mid"
    LOW = "low"


class Semantics(StrEnum):
    """值语义（决定实体平台与判定）。"""
    RAW = "raw"                # 原样输出
    LOCKED = "locked"          # 0=已锁 → on = 未落锁
    DOOR_OPEN = "door_open"    # ==1 才开（XDoorDataHandle）
    TRUNK = "trunk"            # 尾门：锁优先聚合（getTrunkState）
    PLUGGED = "plugged"        # AC==2 / DC==1 = 已连接（App 实证；非「非0」）
    CONNECTED = "connected"    # 非0 = 已连接
    ALARM = "alarm"            # 非0 = 告警
    SWITCH_ON = "switch_on"    # 非0 = 开启
    CHARGE_LID = "charge_lid"  # -1=无效(unknown)，0=关，非0=开
    JSON_FIELD = "json_field"  # 值是 JSON，取 json_field 指定的字段判 0/1


@dataclass(frozen=True, slots=True)
class SignalSpec:
    """一个 VSS 信号的完整声明。"""
    key: str
    path: str
    name: str
    freq: Freq = Freq.HIGH
    semantics: Semantics = Semantics.RAW
    json_field: str | None = None
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    icon: str | None = None
    category: str = ''
    platforms: frozenset[str] = field(default_factory=lambda: frozenset({'sensor'}))
    diagnostic: bool = False
    value_map: dict | None = None      # 值翻译（0/1 → 中文）
    # ★ 2026-09-28 新增：别名信号。
    #   用于「同一个 VSS 路径、两种消费者语义」的场景 ——
    #   避免同一路径被两个 key 各轮询一次（test_paths_unique 会失败）。
    #   使用时 path 必须为 ""（虚拟），值由 coordinator 从 alias_signal 复制。
    #   首个用例：door_front_trunk（门开/关）别名 lock_front_trunk（锁）——
    #   全 App 只有 DoorLockStatus.FrontTrunkDoor 一个前备箱状态路径。
    alias_signal: str | None = None
    # ★ 2026-09-30 新增：派生信号 —— 不从 VSS 直接取，而是由其他信号计算。
    #   compute 是一个函数字符串（延迟 import 用），在 coordinator poll 完后执行。
    #   fn(vss) -> value，vss 是整批轮询结果 dict。
    #   path 必须为 ""（不请求 VSS）。
    #   首个用例：总续航 = 纯电续航 + 燃油续航（App 真正也这么算）。
    compute: str | None = None
    # ══════════════════════════════════════════════════════════════════════
    #  ★★★ 车型能力声明（2026-09-28）—— 决定「哪些车型创建这个实体」
    # ══════════════════════════════════════════════════════════════════════
    #
    #  背景：用户问「app 都能区分，我们为什么不能？不是直接有清单吗？」
    #  答：App 有【数据清单】(assets/{modelId}.json，54 个能力标签)，
    #      但「标签 → 界面元素」的映射它也是逐句写死的
    #      （getAbilityLeven 35 处 + isSupportCheck 6 处）。
    #      我们此前只有一张【独立】的映射表且不完整（156 个信号里只覆盖 21 个），
    #      没登记的默认「所有车型都建」→ 于是 i6（纯电）拿到了 L 系才有的燃油实体。
    #
    #  现在把声明【挪到信号旁边】，并由测试强制【每个信号都必须表态】，
    #  「忘记分类」在结构上不再可能。
    #
    #  requires 取值（DSL，二选一）：
    #    "version:<tag>"    App version 标签 → ability.is_supported(tag)
    #                       例：version:fridge / version:sentry / version:sideDoor
    #    "ability:<tag>"    App temp.config 硬件能力 → ability_level(tag) >= 2
    #                       例：ability:strgWhlHeatSw / ability:thirdLSeatSw
    #    "feature:<名称>"   我们自己的 VSS 探测功能（App 配置里无对应标签）
    #                       例：feature:前备箱 / feature:冰箱
    #    "combustion"       增程专属 → not ability.is_bev
    #    "bev"              纯电专属 → ability.is_bev
    #
    #  无法归入任何能力、所有车型都有的信号：显式写 universal=True
    #  （这也是一种【表态】，且必须写出来 —— 不允许留空默认）。
    # ══════════════════════════════════════════════════════════════════════
    requires: str | None = None
    universal: bool = False


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ⚠️ 关于「本表由 tools/gen_signals.py 生成」的说法（2026-09-28 更正）  ║
# ║                                                                      ║
# ║  gen_signals.py 是【一次性迁移脚本】，其输入是改造前的分散定义：      ║
# ║    const.py 的 VSS_PATHS（现已移除）                                 ║
# ║    sensor.py 的 _mk(...) 调用                                        ║
# ║    binary_sensor.py 的 Description 表                                ║
# ║  实测重跑：const.py 里 VSS_PATHS 已为 0 处 → 生成结果里               ║
# ║  **0 个 SignalSpec**（与现有 156 个对比）→ 脚本已失效。              ║
# ║                                                                      ║
# ║  ⇒ 因此【直接编辑本表是安全的】，不存在「被覆盖」的风险。             ║
# ║    原横幅的警告已过期，保留以免后人误以为不能改。                     ║
# ╚══════════════════════════════════════════════════════════════════════╝
SIGNALS: dict[str, SignalSpec] = {
    "ac_defrost": SignalSpec(
        key="ac_defrost",
        path="Vehicle.Cabin.AC.DefrostModeStatus",
        name="除霜模式",
        freq=Freq.HIGH,
        icon="mdi:snowflake-melt",
        category="空调",
        universal=True,
    ),  # 有翻译映射
    # ★ 2026-09-24 修正：ExSpeedStatus 的真实语义是【快冷快热】
    #   依据：App 的 LXLiMeshStateDelegate.getNeedRapidCoolheat()
    #        读的就是 LxMeshVssConstant.getExSpeedStatus()
    #
    #   ⚠️ key 保留 ac_fan_speed（避免 unique_id 变化、打断用户自动化），
    #      只把显示名改为"快冷快热"（实体 ID 不变）
    "ac_fan_speed": SignalSpec(
        key="ac_fan_speed",
        path="Vehicle.Cabin.AC.ExSpeedStatus",
        name="快冷快热",
        freq=Freq.HIGH,
        icon="mdi:fan",
        category="空调",
        universal=True,
    ),
    "ac_on": SignalSpec(
        key="ac_on",
        path="Vehicle.Cabin.AC.FOffStatus",
        name="空调开关",
        freq=Freq.HIGH,
        icon="mdi:air-conditioner",
        platforms=frozenset(),  # ★ 空调开关信号（climate 平台用，不建实体）
        universal=True,
    ),
    "ac_set_temp": SignalSpec(
        key="ac_set_temp",
        path="Vehicle.Cabin.AC.SetTemp",
        name="空调设定温度",
        freq=Freq.HIGH,
        device_class="TEMPERATURE",
        unit="°C",
        icon="mdi:thermostat",
        category="空调",
        universal=True,
    ),
    "ac_wind_mode": SignalSpec(
        key="ac_wind_mode",
        path="Vehicle.Cabin.AC.WindMode",
        name="风向模式",
        freq=Freq.HIGH,
        icon="mdi:weather-windy",
        category="空调",
        universal=True,
    ),  # 有翻译映射
    # ═══ 2026-10-11 按车主回传的【实测响应】新增（理想ONE real-time-state v3）═══
    # 依据：realtime_state_v3 原始响应 ok=true/code=0，实测字段名与形态如下：
    #   seatStatus.<座>SeatHeatVentState = {"value":"0","timestamp":...}
    #   airConditioningStatus.<X>        = {"value":..,"timestamp":...}
    #   chargeSetting.enduranceStatus.residueFuel / travelStatus.gear
    #   ringLightStatus.status / keyInCarWarning.warning
    # ⚠️ 座椅加热/通风的 1/2/3 各档含义**未实测**（只覆盖"关=0"）→ 与旧表一致，属 [推断]

    "seat_heat_vent_fl": SignalSpec(
        key="seat_heat_vent_fl", path="", name="主驾座椅加热通风",
        icon="mdi:car-seat-heater", category="座椅", universal=True,
    ),
    "seat_heat_vent_fr": SignalSpec(
        key="seat_heat_vent_fr", path="", name="副驾座椅加热通风",
        icon="mdi:car-seat-heater", category="座椅", universal=True,
    ),
    "seat_heat_vent_rl": SignalSpec(
        key="seat_heat_vent_rl", path="", name="左后座椅加热通风",
        icon="mdi:car-seat-heater", category="座椅", universal=True,
    ),
    "seat_heat_vent_rr": SignalSpec(
        key="seat_heat_vent_rr", path="", name="右后座椅加热通风",
        icon="mdi:car-seat-heater", category="座椅", universal=True,
    ),
    # ── M 系（理想ONE）空调：与 L 系共用实体，但 L 系无对应 VSS 路径的细分项 ──
    # ⚠️ 档位/模式语义未实测（仅"关=0"有样本）→ 属 [推断]
    "ac_auto_mode": SignalSpec(
        key="ac_auto_mode", path="", freq=Freq.HIGH, name="空调自动模式",
        icon="mdi:air-conditioner", category="空调", universal=True,
    ),
    "ac_fan_speed_level": SignalSpec(
        key="ac_fan_speed_level", path="", freq=Freq.HIGH, name="空调风量档位",
        icon="mdi:fan", category="空调", universal=True,
    ),
    "ac_set_temp_fl": SignalSpec(
        key="ac_set_temp_fl", path="", freq=Freq.HIGH, name="主驾设定温度",
        state_class="MEASUREMENT", unit="°C",
        icon="mdi:thermometer", category="空调", universal=True,
    ),
    "ac_set_temp_fr": SignalSpec(
        key="ac_set_temp_fr", path="", freq=Freq.HIGH, name="副驾设定温度",
        state_class="MEASUREMENT", unit="°C",
        icon="mdi:thermometer", category="空调", universal=True,
    ),
    "gear": SignalSpec(
        key="gear", path="", freq=Freq.HIGH, name="挡位",
        icon="mdi:car-shift-pattern", category="其他", universal=True,
    ),
    "ring_light": SignalSpec(
        key="ring_light", path="", name="环形灯",
        icon="mdi:lightbulb", category="灯光", universal=True,
    ),
    "key_in_car_warning": SignalSpec(
        key="key_in_car_warning", path="", name="车内有钥匙提醒",
        icon="mdi:key", category="其他", universal=True,
    ),
    "air_pollution": SignalSpec(
        key="air_pollution",
        path="Vehicle.Cabin.AirPollutionIndex",
        name="空气污染指数",
        freq=Freq.HIGH,
        state_class="MEASUREMENT",
        icon="mdi:air-filter",
        category="空气",
        universal=True,
    ),
    "battery_insulation": SignalSpec(
        key="battery_insulation",
        path="Vehicle.Powertrain.ChargingPile.BatteryInsulation",
        name="电池保温",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        icon="mdi:thermometer-plus",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "battery_keep_warm": SignalSpec(
        key="battery_keep_warm",
        path="Vehicle.APP.BMS.KeepWarm",
        name="电池预热",
        freq=Freq.LOW,
        icon="mdi:fire",
        category="电池",
        diagnostic=True,
        universal=True,
    ),
    "battery_level": SignalSpec(
        key="battery_level",
        path="Vehicle.Powertrain.Battery.ResidueBattery",
        name="电池电量",
        freq=Freq.HIGH,
        device_class="BATTERY",
        unit="PERCENTAGE",
        state_class="MEASUREMENT",
        icon="mdi:battery-high",
        category="电池",
        universal=True,
    ),
    "battery_pack_voltage": SignalSpec(
        key="battery_pack_voltage",
        path="Vehicle.Powertrain.Battery.MSG_RESSInterVolt",
        name="电池包电压",
        freq=Freq.HIGH,
        device_class="VOLTAGE",
        unit="V",
        state_class="MEASUREMENT",
        icon="mdi:car-battery",
        category="电池",
        universal=True,
    ),
    "battery_type": SignalSpec(
        key="battery_type",
        path="Vehicle.Powertrain.Battery.PowerBatteryType",
        name="电池类型",
        freq=Freq.HIGH,
        icon="mdi:battery-sync",
        category="电池",
        universal=True,
    ),  # 有翻译映射
    "case_cover": SignalSpec(
        key="case_cover",
        path="Vehicle.Body.DoorSwitchStatus.CaseCoverStatus",
        name="钥匙保护套",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        icon="mdi:key-variant",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "charge_complete": SignalSpec(
        key="charge_complete",
        path="Vehicle.Powertrain.Battery.VehicleChrgComplete",
        name="充电完成状态",
        freq=Freq.HIGH,
        icon="mdi:battery-check",
        category="电池",
        universal=True,
    ),  # 有翻译映射
    "charge_current_ac": SignalSpec(
        key="charge_current_ac",
        path="Vehicle.Powertrain.Battery.ACChargeCurrent",
        name="交流充电电流",
        unit="A",
        freq=Freq.HIGH,
        icon="mdi:current-ac",
        category="充电",
        universal=True,
    ),
    "charge_fault": SignalSpec(
        key="charge_fault",
        path="Vehicle.Powertrain.Battery.ChargeFaults",
        name="充电故障",
        freq=Freq.MID,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:alert-circle",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "charge_gun_ac": SignalSpec(
        key="charge_gun_ac",
        path="Vehicle.Powertrain.Battery.ACChgrActualConnSts",
        name="交流充电枪",
        freq=Freq.HIGH,
        semantics=Semantics.PLUGGED,
        device_class="PLUG",
        icon="mdi:power-plug",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "charge_gun_dc": SignalSpec(
        key="charge_gun_dc",
        path="Vehicle.Powertrain.Battery.DCChrgngGunActuSts",
        name="直流充电枪",
        freq=Freq.MID,
        semantics=Semantics.PLUGGED,
        device_class="PLUG",
        icon="mdi:power-plug-outline",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "charge_limit": SignalSpec(
        key="charge_limit",
        path="Vehicle.Powertrain.ChargingPile.ChargingLimit",
        name="充电上限",
        freq=Freq.HIGH,
        unit="%",
        icon="mdi:battery-charging-80",
        category="充电桩",
        universal=True,
    ),
    "charge_order_mode": SignalSpec(
        key="charge_order_mode",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.OrderChargingMode",
        name="预约充电模式",
        freq=Freq.HIGH,
        icon="mdi:calendar-clock",
        category="充电桩",
        requires="version:multiSlotChargingReservation",
    ),  # 有翻译映射
    "charge_port_lid": SignalSpec(
        key="charge_port_lid",
        path="Vehicle.Body.DoorSwitchStatus.ChrgPorLidStsV2",
        name="充电口盖",
        freq=Freq.HIGH,
        semantics=Semantics.CHARGE_LID,
        icon="mdi:ev-plug-type2",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),
    "charge_port_lid_old": SignalSpec(
        key="charge_port_lid_old",
        path="Vehicle.Body.DoorSwitchStatus.ChrgPorLidSts",
        name="充电口盖(旧信号)",
        freq=Freq.HIGH,
        icon="mdi:ev-plug-type2",
        platforms=frozenset(),  # ★ 旧版充电口盖路径（仅保留供参考）
        category="充电",
        universal=True,
    ),
    "charge_power_cltc": SignalSpec(
        key="charge_power_cltc",
        path="Vehicle.Powertrain.Battery.CLTCChargePower",
        name="充电功率(CLTC)",
        unit="kW",
        freq=Freq.HIGH,
        icon="mdi:lightning-bolt",
        category="充电",
        universal=True,
    ),
    "charge_power_wltc": SignalSpec(
        key="charge_power_wltc",
        path="Vehicle.Powertrain.Battery.WLTCChargePower",
        name="充电功率(WLTC)",
        unit="kW",
        freq=Freq.HIGH,
        icon="mdi:lightning-bolt",
        category="充电",
        universal=True,
    ),
    "charge_remain_time": SignalSpec(
        key="charge_remain_time",
        path="Vehicle.Powertrain.Battery.ChargeSurplusTime",
        name="剩余充电时间",
        freq=Freq.MID,
        device_class="DURATION",
        unit="min",
        state_class="MEASUREMENT",
        icon="mdi:timer-sand",
        category="电池",
        universal=True,
    ),
    "charge_status": SignalSpec(
        key="charge_status",
        path="Vehicle.Powertrain.Battery.ChargeStatus",
        name="充电状态",
        freq=Freq.HIGH,
        icon="mdi:ev-station",
        category="电池",
        universal=True,
    ),  # 有翻译映射
    "charge_voltage_ac": SignalSpec(
        key="charge_voltage_ac",
        path="Vehicle.Powertrain.Battery.ACChargeVoltage",
        name="交流充电电压",
        unit="V",
        freq=Freq.HIGH,
        icon="mdi:sine-wave",
        category="充电",
        universal=True,
    ),
    "config_code": SignalSpec(
        key="config_code",
        path="Vehicle.Information.ConfigCode",
        name="车辆配置",
        freq=Freq.LOW,
        icon="mdi:car-cog",
        category="信息",
        diagnostic=True,
        universal=True,
    ),
    "dcdc_fault_level": SignalSpec(
        key="dcdc_fault_level",
        path="Vehicle.MSG.MSG_DCDCFltLvl",
        name="DCDC 故障",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:alert-octagon",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "discharge_status": SignalSpec(
        key="discharge_status",
        path="Vehicle.Powertrain.Battery.DischargeStatus",
        name="放电状态",
        freq=Freq.HIGH,
        icon="mdi:battery-minus",
        category="电池",
        universal=True,
    ),
    "door_back_left": SignalSpec(
        key="door_back_left",
        path="Vehicle.Body.DoorSwitchStatus.BackLeftDoor",
        name="左后车门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "door_back_right": SignalSpec(
        key="door_back_right",
        path="Vehicle.Body.DoorSwitchStatus.BackRightDoor",
        name="右后车门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "door_copilot": SignalSpec(
        key="door_copilot",
        path="Vehicle.Body.DoorSwitchStatus.CopilotDoor",
        name="副驾车门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "door_main": SignalSpec(
        key="door_main",
        path="Vehicle.Body.DoorSwitchStatus.MainDoor",
        name="主驾车门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "door_trunk": SignalSpec(
        key="door_trunk",
        path="Vehicle.Body.DoorSwitchStatus.TrunkDoor",
        name="后备箱门",
        freq=Freq.HIGH,
        semantics=Semantics.TRUNK,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    # ★ 2026-09-27 新增：前备箱 / 滑门状态
    #   ⚠️ 这些信号在 L6/L7 上不存在（无对应硬件）
    #      → 服务端不会返回 → 实体状态 unknown（可接受）
    #      ★ 实体本身按能力条件创建（见 cover.py）
    "door_front_trunk": SignalSpec(
        key="door_front_trunk",
        # ★★ 2026-09-28 修正路径（用户反馈「i6 前备箱状态错误」）
        #
        #   原路径 Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor 【不存在】：
        #     · 实测服务端直接拒绝：
        #         HTTP 400 invalid_path|desc:Vehicle.Body.DoorSwitchStatus.FrontTrunkDoor
        #       ⚠️ 且无效路径会让【整批】VSS 失败 → 触发二分重试，白耗请求
        #     · LxMeshVssConstant.smali 中该字符串出现 0 次
        #     · VSS spec 的 DoorSwitchStatus 分支下【没有】FrontTrunkDoor
        #
        #   全 App 唯一的前备箱状态路径是：
        #     Vehicle.Body.DoorLockStatus.FrontTrunkDoor（smali 出现 1 次，desc=「前备箱锁」）
        #   它属 DoorLockStatus 分支，实测编码与 DoorSwitchStatus 一致：
        #   0=上锁/关（车门正常锁着 MainDoor=0）, 1=解锁/开（FrontTrunkDoor 实测为 1）。
        #   2026-09-30 修正：lockSw 实际 "1"=开, "0"=关（用户实测方向反了）。
        #
        #   ⚠️ 该路径已由 lock_front_trunk 声明 —— 同一路径不能声明两次
        #      （tests/test_signals.py::test_paths_unique 会失败，且会重复轮询）。
        #      故本信号改为【虚拟别名】：值直接从 lock_front_trunk 复制，
        #      既保留「前备箱门」实体（不产生孤儿），又不重复请求。
        #
        #   ⚠️ 不可用此路径做「有无前备箱」判定 —— 实测 L6（无前备箱）也返回 1。
        #      存在性判定仍由 cover.py 的能力表 / Hpcm 负责。
        path="",                              # 虚拟信号（见 alias_signal）
        alias_signal="lock_front_trunk",
        name="前备箱门",
        freq=Freq.HIGH,
        semantics=Semantics.TRUNK,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        requires="feature:前备箱",
    ),
    "door_slide_left": SignalSpec(
        key="door_slide_left",
        # ★★ 2026-09-28 修正路径（全量审计发现，同类于前备箱）
        #
        #   原路径 Vehicle.Body.SeatLDoor.DoorStatus 服务端【直接拒绝】：
        #       HTTP 400 invalid_path|desc:Vehicle.Body.SeatLDoor.DoorStatus
        #     ⚠️ 危害不止于实体显示：轮询路径来自 signals（不按车型过滤），
        #        所以这个无效路径【每一轮】都让整批 VSS 失败 →
        #        触发二分重试，长期白白多花请求。
        #
        #   SeatLDoor 分支的真实内容（spec desc =「座椅左侧滑门」）：
        #       SeatLDoor.InterferenceSts   ← 唯一在 smali 里出现的键（已用作
        #                                     seat_l_door_interference）
        #     并没有 DoorStatus。
        #
        #   正确的滑门状态路径（spec desc =「W二排左侧侧滑门开度值」）：
        #       Vehicle.Body.DoorPosition.BackLeftDoor
        #   实测：路径有效；本车 L6（无滑门）返回 value=None → 实体 unknown
        #         （正是无此硬件时该有的表现，且另外还有 sideDoor 门控兜底）
        path="Vehicle.Body.DoorPosition.BackLeftDoor",
        name="左滑门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        requires="version:sideDoor",
    ),
    "door_slide_right": SignalSpec(
        key="door_slide_right",
        # ★★ 同上：原 SeatRDoor.DoorStatus 无效，改用 DoorPosition.BackRightDoor
        #   依据见 door_slide_left 的注释。
        path="Vehicle.Body.DoorPosition.BackRightDoor",
        name="右滑门",
        freq=Freq.HIGH,
        semantics=Semantics.DOOR_OPEN,
        device_class="DOOR",
        icon="mdi:car-door",
        platforms=frozenset({'binary_sensor'}),
        requires="version:sideDoor",
    ),  # 有翻译映射
    "eves_flt_stop_chrg": SignalSpec(
        key="eves_flt_stop_chrg",
        path="Vehicle.Powertrain.Battery.EVESFltStopChrg",
        name="故障停止充电",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:alert-circle",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "fridge_cool_temp": SignalSpec(
        key="fridge_cool_temp",
        path="Vehicle.Cabin.Fridge.CoolTempSt",
        name="冰箱制冷温度",
        freq=Freq.MID,
        icon="mdi:snowflake",
        category="冰箱",
        requires="feature:冰箱",
    ),
    "fridge_mode": SignalSpec(
        key="fridge_mode",
        path="Vehicle.Cabin.Fridge.ModeState",
        name="冰箱模式",
        freq=Freq.MID,
        icon="mdi:fridge-outline",
        category="冰箱",
        requires="feature:冰箱",
    ),  # 有翻译映射
    "fridge_remain_time": SignalSpec(
        key="fridge_remain_time",
        path="Vehicle.Cabin.Fridge.DlyTmRemain",
        name="冰箱剩余时间",
        freq=Freq.MID,
        device_class="DURATION",
        unit="min",
        icon="mdi:timer",
        category="冰箱",
        requires="feature:冰箱",
    ),
    "fridge_status": SignalSpec(
        key="fridge_status",
        path="Vehicle.Cabin.Fridge.ActWorkSts",
        name="冰箱工作状态",
        freq=Freq.MID,
        icon="mdi:fridge",
        category="冰箱",
        requires="feature:冰箱",
    ),  # 有翻译映射
    "fuel_level": SignalSpec(
        key="fuel_level",
        path="Vehicle.MSG.MSG_FuelLevelPos",
        name="油量",
        freq=Freq.HIGH,
        unit="L",
        state_class="MEASUREMENT",
        icon="mdi:fuel",
        category="续航",
        requires="combustion",
    ),
    "fuel_low_warning": SignalSpec(
        key="fuel_low_warning",
        path="Vehicle.MSG.MSG_FuelLevelWrnng",
        name="油量低告警",
        freq=Freq.MID,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:gas-station-off",
        platforms=frozenset({'binary_sensor'}),
        requires="combustion",
    ),
    # ★★ 2026-09-27：这个信号不只是"车机诊断"——
    #   它其实是【整车配置表】（120+ 字段的 JSON）：
    #     {"hmi_platform":"6", "hc_frunk":"0", "hc_car_refrigeratory":"0", ...}
    #
    #   用途（见 vehicle_hpcm.py）：
    #     1. 精确功能判断（hc_frunk 前备箱 / hc_psd 滑门 / …）
    #     2. ★ SS3/SS4 协议判定（hmi_platform == "1" → SS4）
    #
    #   ⚠️ freq 保持 HIGH 不变（信号表等价性守卫要求）
    #      实际它几乎不变 —— 由 vehicle_hpcm 模块按需解析
    "hu_diag": SignalSpec(
        key="hu_diag",
        path="Vehicle.HU.Diag.Hpcm",
        name="车机诊断",
        freq=Freq.HIGH,
        icon="mdi:stethoscope",
        category="信息",
        diagnostic=True,
        universal=True,
    ),
    "inside_temp": SignalSpec(
        key="inside_temp",
        path="Vehicle.Cabin.AC.FrtACIncarTemp",
        name="车内温度",
        freq=Freq.HIGH,
        device_class="TEMPERATURE",
        unit="°C",
        state_class="MEASUREMENT",
        icon="mdi:thermometer",
        category="空调",
        universal=True,
    ),
    "light_lic": SignalSpec(
        key="light_lic",
        path="Vehicle.Body.Light.LicLghtSts",
        name="牌照灯",
        freq=Freq.HIGH,
        icon="mdi:lightbulb",
        category="灯光",
        universal=True,
    ),  # 有翻译映射
    "location": SignalSpec(
        key="location",
        path="Vehicle.Location.CurrentLocationInfo",
        name="location",
        freq=Freq.HIGH,
        platforms=frozenset(),  # ★ 车辆位置（device_tracker 平台用，不建 sensor）
        universal=True,
    ),
    "lock_back_left": SignalSpec(
        key="lock_back_left",
        path="Vehicle.Body.DoorLockStatus.BackLeftDoor",
        name="左后门锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "lock_back_right": SignalSpec(
        key="lock_back_right",
        path="Vehicle.Body.DoorLockStatus.BackRightDoor",
        name="右后门锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "lock_copilot": SignalSpec(
        key="lock_copilot",
        path="Vehicle.Body.DoorLockStatus.CopilotDoor",
        name="副驾门锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "lock_front_trunk": SignalSpec(
        key="lock_front_trunk",
        path="Vehicle.Body.DoorLockStatus.FrontTrunkDoor",
        name="前备箱锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        requires="feature:前备箱",
    ),  # 有翻译映射
    "lock_main": SignalSpec(
        key="lock_main",
        path="Vehicle.Body.DoorLockStatus.MainDoor",
        name="主驾门锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "lock_trunk": SignalSpec(
        key="lock_trunk",
        path="Vehicle.Body.DoorLockStatus.TrunkDoor",
        name="后备箱锁",
        freq=Freq.HIGH,
        semantics=Semantics.LOCKED,
        device_class="LOCK",
        icon="mdi:car-door-lock",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "low_battery_mode": SignalSpec(
        key="low_battery_mode",
        path="Vehicle.Cabin.LowBatteryMode",
        name="低电量模式",
        freq=Freq.MID,
        icon="mdi:battery-low",
        category="空气",
        universal=True,
    ),  # 有翻译映射
    "low_vol_flag": SignalSpec(
        key="low_vol_flag",
        path="Vehicle.Body.Power.LowVolPwrMdFlag",
        name="低压电源标志",
        freq=Freq.MID,
        semantics=Semantics.ALARM,
        icon="mdi:flag",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "low_vol_mode": SignalSpec(
        key="low_vol_mode",
        path="Vehicle.Body.Power.LowVolEngyMngtMd",
        name="低压电源模式",
        freq=Freq.MID,
        icon="mdi:power-plug-battery",
        category="电源",
        diagnostic=True,
        universal=True,
    ),  # 有翻译映射
    "low_vol_status": SignalSpec(
        key="low_vol_status",
        path="Vehicle.Body.Power.LowVolPwrMdSts",
        name="低压电源状态",
        freq=Freq.HIGH,
        icon="mdi:car-battery",
        category="电池",
        universal=True,
    ),  # 有翻译映射
    "maint_acfilter": SignalSpec(
        key="maint_acfilter",
        path="Vehicle.Carcenter.Maintain.acfilter",
        name="空调滤芯",
        freq=Freq.LOW,
        icon="mdi:air-filter",
        category="保养",
        diagnostic=True,
        requires="version:maintainConfig",
    ),
    "maint_brake_oil": SignalSpec(
        key="maint_brake_oil",
        path="Vehicle.Carcenter.Maintain.gearbrakeoil",
        name="刹车油",
        freq=Freq.LOW,
        icon="mdi:car-brake-fluid-level",
        category="保养",
        diagnostic=True,
        requires="version:maintainConfig",
    ),
    "maint_coolfuild": SignalSpec(
        key="maint_coolfuild",
        path="Vehicle.Carcenter.Maintain.coolfuild",
        name="冷却液",
        freq=Freq.LOW,
        icon="mdi:coolant-temperature",
        category="保养",
        diagnostic=True,
        requires="version:coolingLiquid",
    ),
    "maint_engine_oil": SignalSpec(
        key="maint_engine_oil",
        path="Vehicle.Carcenter.Maintain.enginelevel1",
        name="机油",
        freq=Freq.LOW,
        icon="mdi:oil",
        category="保养",
        diagnostic=True,
        requires="combustion",
    ),
    "maint_sparkplug": SignalSpec(
        key="maint_sparkplug",
        path="Vehicle.Carcenter.Maintain.sparkplug",
        name="火花塞",
        freq=Freq.LOW,
        icon="mdi:flash",
        category="保养",
        diagnostic=True,
        requires="combustion",
    ),
    "mileage_final": SignalSpec(
        key="mileage_final",
        path="Vehicle.Cabin.CLTC.MileageFinalResult",
        # ★ 2026-09-28 语义修正：App spec = "动态续航，预测续航"
        #   → 这是【续航预测结果】，不是累计里程。旧名「总里程」有误。
        name="续航预测",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:map-marker-distance",
        platforms=frozenset(),  # ★ L6 实测无数据（MileageFinalResult 返回 None）
        universal=True,
    ),
    "mirror_left": SignalSpec(
        key="mirror_left",
        path="Vehicle.Body.RearMirro.LRearMirro",
        name="左后视镜",
        freq=Freq.HIGH,
        icon="mdi:mirror",
        category="灯光",
        universal=True,
    ),  # 有翻译映射
    "mirror_right": SignalSpec(
        key="mirror_right",
        path="Vehicle.Body.RearMirro.RRearMirro",
        name="右后视镜",
        freq=Freq.HIGH,
        icon="mdi:mirror",
        category="灯光",
        universal=True,
    ),  # 有翻译映射
    "online_5g": SignalSpec(
        key="online_5g",
        path="Vehicle.ConnectManager.ConnectStatus.5G",
        name="5G 连接",
        freq=Freq.HIGH,
        semantics=Semantics.CONNECTED,
        device_class="CONNECTIVITY",
        icon="mdi:signal-5g",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),
    "online_huf": SignalSpec(
        key="online_huf",
        path="Vehicle.ConnectManager.ConnectStatus.hu-f",
        name="车机连接",
        freq=Freq.HIGH,
        semantics=Semantics.CONNECTED,
        device_class="CONNECTIVITY",
        icon="mdi:car-connected",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),
    "online_xcu": SignalSpec(
        key="online_xcu",
        path="Vehicle.ConnectManager.ConnectStatus.xcu",
        name="XCU 连接",
        freq=Freq.HIGH,
        semantics=Semantics.CONNECTED,
        device_class="CONNECTIVITY",
        icon="mdi:chip",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),
    "ota_progress": SignalSpec(
        key="ota_progress",
        path="Vehicle.OTA.Upgrade.UpgradeProgress",
        name="OTA 进度",
        freq=Freq.LOW,
        unit="%",
        icon="mdi:progress-download",
        category="OTA",
        diagnostic=True,
        universal=True,
    ),
    "ota_short": SignalSpec(
        key="ota_short",
        path="Vehicle.Version.OTA.displayedBaseline",
        name="OTA 版本(简)",
        freq=Freq.LOW,
        icon="mdi:cellphone-arrow-down",
        diagnostic=True,
        universal=True,
    ),
    "ota_state": SignalSpec(
        key="ota_state",
        path="Vehicle.OTA.Upgrade.UpgradeState",
        name="OTA 状态",
        freq=Freq.LOW,
        icon="mdi:download",
        category="OTA",
        diagnostic=True,
        universal=True,
    ),
    "ota_status": SignalSpec(
        key="ota_status",
        path="Vehicle.OTA.Upgrade.UpgradeStatus",
        name="OTA 结果",
        freq=Freq.LOW,
        icon="mdi:download-circle",
        category="OTA",
        diagnostic=True,
        universal=True,
    ),
    "ota_version": SignalSpec(
        key="ota_version",
        path="Vehicle.Version.OTA.Baseline",
        name="车机版本",
        freq=Freq.LOW,
        icon="mdi:car-info",
        category="OTA",
        diagnostic=True,
        universal=True,
    ),
    "park_fsd_progress": SignalSpec(
        key="park_fsd_progress",
        path="Vehicle.ParkMeshAgent.Park.FSDBootProgress",
        name="泊车启动进度",
        freq=Freq.MID,
        icon="mdi:progress-clock",
        category="泊车",
        # ★ 2026-09-24 改诊断类：值恒为 0 且时间戳停留在 2026-09-21，实际无变化
        #   （泊车状态在 App 里走【实时事件通道】，VSS 拿不到）
        diagnostic=True,
        requires="version:remoteParkingOut",
    ),
    "park_status": SignalSpec(
        key="park_status",
        path="Vehicle.ParkMeshAgent.Park.ParkStatus",
        name="泊车状态",
        freq=Freq.LOW,
        icon="mdi:parking",
        category="泊车",
        # ★ 2026-09-24 改诊断类：服务端从不返回该信号（value 恒为 None），实体永远是 unknown
        #   （泊车状态在 App 里走【实时事件通道】，VSS 拿不到）
        diagnostic=True,
        requires="version:remoteParkingOut",
    ),
    "privacy_pos_service": SignalSpec(
        key="privacy_pos_service",
        path="Vehicle.CarSettings.Privacy.PosService",
        name="位置服务",
        freq=Freq.HIGH,
        icon="mdi:map-marker-radius",
        category="设置",
        diagnostic=True,
        universal=True,
    ),  # 有翻译映射
    "provision_auth": SignalSpec(
        key="provision_auth",
        path="Vehicle.Provision.Authorize.State",
        name="车辆授权",
        freq=Freq.LOW,
        semantics=Semantics.CONNECTED,
        icon="mdi:key-chain-variant",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),
    "range_elec_cltc": SignalSpec(
        key="range_elec_cltc",
        path="Vehicle.Cabin.CLTC.PureElecEnduranceMileInd",
        name="纯电续航(CLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:ev-station",
        universal=True,
    ),
    "range_elec_wltc": SignalSpec(
        key="range_elec_wltc",
        path="Vehicle.Cabin.WLTC.PureElecEnduranceMileInd",
        name="纯电续航(WLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:ev-station",
        universal=True,
    ),
    "range_fuel_cltc": SignalSpec(
        key="range_fuel_cltc",
        path="Vehicle.Cabin.CLTC.FuelEnduranceMileInd",
        name="燃油续航(CLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:gas-station",
        requires="combustion",
    ),
    "range_fuel_wltc": SignalSpec(
        key="range_fuel_wltc",
        path="Vehicle.Cabin.WLTC.FuelEnduranceMileInd",
        name="燃油续航(WLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:gas-station",
        requires="combustion",
    ),
    # ★★★ 2026-09-29 新增：总续航 + 续航显示工况
    #   静态逆向的三条独立证据：
    #     ① spec_X01-VSS-Path_148.json：
    #          Vehicle.Cabin.CLTC.EnduranceMil = "CLTC总续航里程"
    #          Vehicle.Cabin.WLTC.EnduranceMil = "WLTC总续航里程"
    #     ② LXLiMeshPathConfig.json → LXVehicleInfoKeyEndurance.subKeys 含
    #          CarSettings.Preference.CLTCWLTC
    #          信号定义：datatype=string, default="1", type=actuator,
    #          description="续航显示工况"
    #     ③ App 车控头部（headerControl.enduranceTag）订阅 LXVehicleInfoKeyEndurance
    #   ★ 关键：App 车控左上角显示的是【总续航】，不是纯电/燃油分项。
    #     但 App 反编译证实：**服务端不返回 EnduranceMil 路径** ——
    #     App 自己在 XEnduranceDataHandle 里把 PureElec + Fuel 加起来。
    #     所以我们也改成 compute，确保所有车型都有总续航。
    "range_total_cltc": SignalSpec(
        key="range_total_cltc",
        path="",           # 不请求 VSS —— compute 算
        name="总续航(CLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:map-marker-distance",
        universal=True,
        compute="lambda vss: _sum_range(vss, 'CLTC')",
    ),
    "range_total_wltc": SignalSpec(
        key="range_total_wltc",
        path="",           # 不请求 VSS —— compute 算
        name="总续航(WLTC)",
        unit="km",
        freq=Freq.HIGH,
        icon="mdi:map-marker-distance",
        universal=True,
        compute="lambda vss: _sum_range(vss, 'WLTC')",
    ),
    "range_display_mode": SignalSpec(
        key="range_display_mode",
        # ★ 带 {{AccountId}} 模板：App 用 LXVssDelegate.resolveTemplateAccountId()
        #   替换成车主账号（账号来自 VSS 的 Vehicle.Account.Cloud.VehicleAccounts）
        path="Vehicle.{{AccountId}}.CarSettings.Preference.CLTCWLTC",
        name="续航显示工况",
        freq=Freq.LOW,
        icon="mdi:gauge",
        universal=True,
    ),
    "scene_mode": SignalSpec(
        key="scene_mode",
        path="Vehicle.CarSettings.SceneMode.ModeState",
        name="场景模式",
        freq=Freq.HIGH,
        icon="mdi:palette",
        category="设置",
        diagnostic=True,
        requires="version:scene",
    ),  # 有翻译映射
    "scheduled_charge_end": SignalSpec(
        key="scheduled_charge_end",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.NewReserveFinishTime",
        name="预约结束时间",
        freq=Freq.HIGH,
        icon="mdi:clock-end",
        category="充电桩",
        # ★ 2026-09-24 改诊断类：已由 time 实体提供可设置的
        #   「充电开始/结束时间」，此只读 sensor 冗余
        diagnostic=True,
        requires="version:multiSlotChargingReservation",
    ),
    "scheduled_charge_start": SignalSpec(
        key="scheduled_charge_start",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.ReserveStartTime",
        name="预约开始时间",
        freq=Freq.HIGH,
        icon="mdi:clock-start",
        category="充电桩",
        # ★ 2026-09-24 改诊断类：已由 time 实体提供可设置的
        #   「充电开始/结束时间」，此只读 sensor 冗余
        diagnostic=True,
        requires="version:multiSlotChargingReservation",
    ),
    "scheduled_charge_state": SignalSpec(
        key="scheduled_charge_state",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.State",
        name="预约充电状态",
        freq=Freq.HIGH,
        icon="mdi:calendar-check",
        category="充电桩",
        requires="version:multiSlotChargingReservation",
    ),  # 有翻译映射
    "scheduled_charge_switch": SignalSpec(
        key="scheduled_charge_switch",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.Switch",
        name="预约充电",
        freq=Freq.HIGH,
        semantics=Semantics.SWITCH_ON,
        icon="mdi:calendar-clock",
        platforms=frozenset({'binary_sensor'}),
        requires="version:multiSlotChargingReservation",
    ),  # 有翻译映射
    "seat_fl_heat": SignalSpec(
        key="seat_fl_heat",
        path="Vehicle.Cabin.Seat.FLSeatHeatState",
        name="主驾座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:flSeatSw",
    ),  # 有翻译映射
    "seat_fl_vent": SignalSpec(
        key="seat_fl_vent",
        path="Vehicle.Cabin.Seat.FLSeatVentilationState",
        name="主驾座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:flSeatSw",
    ),  # 有翻译映射
    "seat_fr_heat": SignalSpec(
        key="seat_fr_heat",
        path="Vehicle.Cabin.Seat.FRSeatHeatState",
        name="副驾座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:frSeatSw",
    ),  # 有翻译映射
    "seat_fr_vent": SignalSpec(
        key="seat_fr_vent",
        path="Vehicle.Cabin.Seat.FRSeatVentilationState",
        name="副驾座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:frSeatSw",
    ),  # 有翻译映射
    "seat_sl_heat": SignalSpec(
        key="seat_sl_heat",
        path="Vehicle.Cabin.Seat.SLSeatHeatState",
        name="二排左座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:secLSeatSw",
    ),  # 有翻译映射
    "seat_sl_vent": SignalSpec(
        key="seat_sl_vent",
        path="Vehicle.Cabin.Seat.SLSeatVentilationState",
        name="二排左座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:secLSeatSw",
    ),  # 有翻译映射
    "seat_sm_heat": SignalSpec(
        key="seat_sm_heat",
        path="Vehicle.Cabin.Seat.SMSeatHeatState",
        name="二排中座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:secMSeatSw",
    ),  # 有翻译映射
    "seat_sr_heat": SignalSpec(
        key="seat_sr_heat",
        path="Vehicle.Cabin.Seat.SRSeatHeatState",
        name="二排右座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:secRSeatSw",
    ),  # 有翻译映射
    "seat_sr_vent": SignalSpec(
        key="seat_sr_vent",
        path="Vehicle.Cabin.Seat.SRSeatVentilationState",
        name="二排右座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:secRSeatSw",
    ),  # 有翻译映射
    "seat_tl_heat": SignalSpec(
        key="seat_tl_heat",
        path="Vehicle.Cabin.Seat.TLSeatHeatState",
        name="三排左座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:thirdLSeatSw",
    ),  # 有翻译映射
    "seat_tl_vent": SignalSpec(
        key="seat_tl_vent",
        path="Vehicle.Cabin.Seat.TLSeatVentilationState",
        name="三排左座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:thirdLSeatSw",
    ),  # 有翻译映射
    "seat_tm_heat": SignalSpec(
        key="seat_tm_heat",
        path="Vehicle.Cabin.Seat.TMSeatHeatState",
        name="三排中座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:thirdMSeatHeatSw",
    ),  # 有翻译映射
    "seat_tr_heat": SignalSpec(
        key="seat_tr_heat",
        path="Vehicle.Cabin.Seat.TRSeatHeatState",
        name="三排右座椅加热",
        freq=Freq.HIGH,
        icon="mdi:car-seat-heater",
        category="座椅",
        requires="ability:thirdRSeatSw",
    ),  # 有翻译映射
    "seat_tr_vent": SignalSpec(
        key="seat_tr_vent",
        path="Vehicle.Cabin.Seat.TRSeatVentilationState",
        name="三排右座椅通风",
        freq=Freq.HIGH,
        icon="mdi:car-seat-cooler",
        category="座椅",
        requires="ability:thirdRSeatSw",
    ),  # 有翻译映射
    "sentry": SignalSpec(
        key="sentry",
        path="Vehicle.Sentry.SentinelStatus",
        name="哨兵模式",
        freq=Freq.HIGH,
        icon="mdi:shield-car",
        platforms=frozenset({'binary_sensor'}),
        semantics=Semantics.JSON_FIELD,
        json_field="sentinelStatus",
        requires="feature:哨兵模式",
    ),  # 有翻译映射
    "sentry_switch": SignalSpec(
        key="sentry_switch",
        path="Vehicle.Sentry.SettingsStatus",
        name="哨兵开关",
        freq=Freq.HIGH,
        icon="mdi:shield-check",
        platforms=frozenset(),  # ★ 2026-09-24：改由 switch 平台提供
        semantics=Semantics.JSON_FIELD,
        json_field="sentinelSwitch",
        requires="feature:哨兵模式",
    ),
    "sentry_video_count": SignalSpec(
        key="sentry_video_count",
        path="Vehicle.Sentry.Video.Count",
        name="哨兵视频数",
        freq=Freq.HIGH,
        state_class="MEASUREMENT",
        icon="mdi:video",
        category="哨兵",
        requires="feature:哨兵模式",
    ),
    "speed": SignalSpec(
        key="speed",
        path="Vehicle.XCU.VehSpd",
        name="车速",
        freq=Freq.HIGH,
        device_class="SPEED",
        unit="km/h",
        state_class="MEASUREMENT",
        icon="mdi:speedometer",
        category="位置",
        universal=True,
    ),
    "sunshade": SignalSpec(
        key="sunshade",
        path="Vehicle.Body.SunshadeStatus.FrtSunshdSwSts",
        name="遮阳帘",
        freq=Freq.MID,
        icon="mdi:window-shutter",
        category="车窗",
        requires="feature:遮阳帘",
    ),  # 有翻译映射
    "svm_filekey": SignalSpec(
        key="svm_filekey",
        path="Vehicle.360Svm.Park.Filekey",
        name="360 拍照信息",
        freq=Freq.HIGH,
        icon="mdi:image",
        category="影像",
        requires="feature:远程拍照",
    ),
    "svm_photo_state": SignalSpec(
        key="svm_photo_state",
        path="Vehicle.360Svm.ParkPhoto.State",
        name="360 拍照状态",
        freq=Freq.HIGH,
        icon="mdi:camera",
        category="影像",
        requires="feature:远程拍照",
    ),  # 有翻译映射
    "tank_lock": SignalSpec(
        key="tank_lock",
        path="Vehicle.Body.DoorSwitchStatus.TankLockDrvSts",
        name="油箱盖",
        freq=Freq.MID,
        semantics=Semantics.DOOR_OPEN,
        icon="mdi:gas-station",
        platforms=frozenset({'binary_sensor'}),
        requires="combustion",
    ),
    "tire_fl": SignalSpec(
        key="tire_fl",
        path="Vehicle.Chassis.Tire.FLTirePressure",
        name="胎压 左前",
        freq=Freq.MID,
        device_class="PRESSURE",
        unit="kPa",
        state_class="MEASUREMENT",
        icon="mdi:car-tire-alert",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_fl_temp": SignalSpec(
        key="tire_fl_temp",
        path="Vehicle.Chassis.Tire.FLTireTemp",
        name="胎温 左前",
        freq=Freq.MID,
        device_class="TEMPERATURE",
        unit="°C",
        state_class="MEASUREMENT",
        icon="mdi:thermometer-lines",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_fl_warning": SignalSpec(
        key="tire_fl_warning",
        path="Vehicle.Chassis.Tire.FLTireWarning",
        name="胎压告警 左前",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:car-tire-alert",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "tire_fr": SignalSpec(
        key="tire_fr",
        path="Vehicle.Chassis.Tire.FRTirePressure",
        name="胎压 右前",
        freq=Freq.MID,
        device_class="PRESSURE",
        unit="kPa",
        state_class="MEASUREMENT",
        icon="mdi:car-tire-alert",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_fr_temp": SignalSpec(
        key="tire_fr_temp",
        path="Vehicle.Chassis.Tire.FRTireTemp",
        name="胎温 右前",
        freq=Freq.MID,
        device_class="TEMPERATURE",
        unit="°C",
        state_class="MEASUREMENT",
        icon="mdi:thermometer-lines",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_fr_warning": SignalSpec(
        key="tire_fr_warning",
        path="Vehicle.Chassis.Tire.FRTireWarning",
        name="胎压告警 右前",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:car-tire-alert",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "tire_rl": SignalSpec(
        key="tire_rl",
        path="Vehicle.Chassis.Tire.RLTirePressure",
        name="胎压 左后",
        freq=Freq.MID,
        device_class="PRESSURE",
        unit="kPa",
        state_class="MEASUREMENT",
        icon="mdi:car-tire-alert",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_rl_temp": SignalSpec(
        key="tire_rl_temp",
        path="Vehicle.Chassis.Tire.RLTireTemp",
        name="胎温 左后",
        freq=Freq.MID,
        device_class="TEMPERATURE",
        unit="°C",
        state_class="MEASUREMENT",
        icon="mdi:thermometer-lines",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_rl_warning": SignalSpec(
        key="tire_rl_warning",
        path="Vehicle.Chassis.Tire.RLTireWarning",
        name="胎压告警 左后",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:car-tire-alert",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "tire_rr": SignalSpec(
        key="tire_rr",
        path="Vehicle.Chassis.Tire.RRTirePressure",
        name="胎压 右后",
        freq=Freq.MID,
        device_class="PRESSURE",
        unit="kPa",
        state_class="MEASUREMENT",
        icon="mdi:car-tire-alert",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_rr_temp": SignalSpec(
        key="tire_rr_temp",
        path="Vehicle.Chassis.Tire.RRTireTemp",
        name="胎温 右后",
        freq=Freq.MID,
        device_class="TEMPERATURE",
        unit="°C",
        state_class="MEASUREMENT",
        icon="mdi:thermometer-lines",
        category="轮胎",
          # ★ 2026-09-29 降频：胎压/胎温是慢变量 —— 数据库实测
          #   9925 行写入仅 11 种不同值（≈900:1），HIGH(5min)→MID(1h)
          #   使轮询请求量降 92%；慢漏气 1 小时内仍可发现。
          #   胎压【告警】tire_xx_warning 保持 HIGH（安全相关）。
        universal=True,
    ),
    "tire_rr_warning": SignalSpec(
        key="tire_rr_warning",
        path="Vehicle.Chassis.Tire.RRTireWarning",
        name="胎压告警 右后",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:car-tire-alert",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "tpms_status": SignalSpec(
        key="tpms_status",
        path="Vehicle.Chassis.Tire.TPMSSysSts",
        name="TPMS 系统告警",
        freq=Freq.HIGH,
        semantics=Semantics.ALARM,
        device_class="PROBLEM",
        icon="mdi:car-tire-alert",
        platforms=frozenset({'binary_sensor'}),
        universal=True,
    ),  # 有翻译映射
    "travel_status": SignalSpec(
        key="travel_status",
        path="Vehicle.Cabin.TravelStatus",
        name="行驶状态",
        freq=Freq.HIGH,
        icon="mdi:car-cruise-control",
        category="空气",
        universal=True,
    ),
    "trip_total": SignalSpec(
        key="trip_total",
        path="Vehicle.Carcenter.Trip.Total",
        name="行程总计",
        freq=Freq.HIGH,
        icon="mdi:counter",
        category="保养",
        diagnostic=True,
        universal=True,
    ),
    # ★ 2026-10-02：充电累计量（虚拟信号；path="" 不参与 VSS 轮询）
    #   值来自 coordinator 低频 HTTP（官方按月充电统计求和，天然递增）
    #   用途：HA 能源面板「总充电量」（energy / kWh / total_increasing）
    "charge_total_energy": SignalSpec(
        key="charge_total_energy",
        path="",
        name="累计充电量",
        freq=Freq.LOW,
        semantics=Semantics.RAW,
        device_class="ENERGY",
        unit="kWh",
        state_class="TOTAL_INCREASING",
        icon="mdi:battery-charging-100",
        category="电池",
        universal=True,
    ),

    # ★ 2026-10-02 补：LCC 里程 / 纯电里程 / 辅助驾驶天数
    "stat_lcc_mileage": SignalSpec(
        key="stat_lcc_mileage", path="", name="LCC 里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="lccMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:highway", category="里程", universal=True,
    ),
    "stat_cd_mileage": SignalSpec(
        key="stat_cd_mileage", path="", name="纯电里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="cdMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:ev-station", category="里程", universal=True,
    ),
    "stat_ad_days": SignalSpec(
        key="stat_ad_days", path="", name="辅助驾驶天数", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="adMileageDate",
        unit="d", state_class="TOTAL_INCREASING",
        icon="mdi:calendar-check", category="里程", universal=True,
    ),

    # ★ 2026-10-02：Trip.Total 的更多字段（App 显示、此前只暴露 4 个）
    #   虚拟信号（值派生自 trip_total 的 JSON），单位米 → 渲染转 km
    "stat_total_mileage": SignalSpec(
        key="stat_total_mileage", path="", name="总里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="mileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:counter", category="里程", universal=True,
    ),
    "stat_engine_mileage": SignalSpec(
        key="stat_engine_mileage", path="", name="发动机里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="engineMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:engine", category="里程", universal=True,
    ),
    "stat_ad_mileage": SignalSpec(
        key="stat_ad_mileage", path="", name="辅助驾驶里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="adMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:steering", category="里程", universal=True,
    ),
    "stat_noa_mileage": SignalSpec(
        key="stat_noa_mileage", path="", name="NOA 里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="noaMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:highway", category="里程", universal=True,
    ),
    "stat_acc_mileage": SignalSpec(
        key="stat_acc_mileage", path="", name="ACC 里程", freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD, json_field="accMileage",
        device_class="DISTANCE", unit="km", state_class="TOTAL_INCREASING",
        icon="mdi:car-cruise-control", category="里程", universal=True,
    ),

    # ★ 2026-10-02：本月里程 / 本月充电量（与 App 首页、充电页同口径）
    #   虚拟信号（path=""），值来自 coordinator 低频 HTTP（1h）
    "month_km": SignalSpec(
        key="month_km", path="", name="本月里程", freq=Freq.LOW,
        semantics=Semantics.RAW, device_class="DISTANCE", unit="km",
        state_class="MEASUREMENT", icon="mdi:road-variant",
        category="里程", universal=True,
    ),
    "month_elec_km": SignalSpec(
        key="month_elec_km", path="", name="本月纯电里程", freq=Freq.LOW,
        semantics=Semantics.RAW, device_class="DISTANCE", unit="km",
        state_class="MEASUREMENT", icon="mdi:road-variant",
        category="里程", universal=True,
    ),
    "month_elec_kwh": SignalSpec(
        key="month_elec_kwh", path="", name="本月耗电量", freq=Freq.LOW,
        semantics=Semantics.RAW, device_class="ENERGY", unit="kWh",
        state_class="TOTAL", icon="mdi:lightning-bolt",
        category="里程", universal=True,
    ),
    "month_fuel_l": SignalSpec(
        key="month_fuel_l", path="", name="本月耗油量", freq=Freq.LOW,
        semantics=Semantics.RAW, unit="L",
        state_class="TOTAL", icon="mdi:gas-station",
        category="里程", universal=True,
    ),
    "month_charge_kwh": SignalSpec(
        key="month_charge_kwh", path="", name="本月充电量", freq=Freq.LOW,
        semantics=Semantics.RAW, device_class="ENERGY", unit="kWh",
        state_class="TOTAL", icon="mdi:battery-charging",
        category="里程", universal=True,
    ),

    # ---- 里程统计（2026-09-28）----
    # ★ 数据来源：Vehicle.Carcenter.Trip.Total（与 trip_total 同一路径）
    #   该路径是一个 36 字段的 JSON，trip_total 只暴露了其中 4 个。
    #   以下 3 个字段来自 JS bundle 的 aggregate 映射（权威）：
    #     X.ownerTransferDate      = day            陪伴天数
    #     X.ownerTransferMileage   = 1e3*travelMileage  陪伴里程(m)
    #     X.ownerTransferCdMileage = 1e3*elecMileage    耗电行驶(m)
    #   ⚠️ 值单位是【米】，渲染时转 km。
    "stat_days": SignalSpec(
        key="stat_days",
        path="",          # ★ 虚拟信号：值派生自 trip_total 的 JSON（不重复轮询）
        name="陪伴天数",
        freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD,
        json_field="ownerTransferDate",
        unit=None,
        state_class="total_increasing",
        icon="mdi:calendar-heart",
        category="里程",
        diagnostic=True,
        universal=True,
    ),
    "stat_mileage": SignalSpec(
        key="stat_mileage",
        device_class="DISTANCE",
        path="",          # ★ 虚拟信号（同上）
        name="陪伴里程",
        freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD,
        json_field="ownerTransferMileage",
        unit="km",
        state_class="total_increasing",
        icon="mdi:road-variant",
        category="里程",
        diagnostic=True,
        universal=True,
    ),
    "stat_elec_mileage": SignalSpec(
        key="stat_elec_mileage",
        device_class="DISTANCE",
        path="",          # ★ 虚拟信号（同上）
        name="耗电行驶",
        freq=Freq.HIGH,
        semantics=Semantics.JSON_FIELD,
        json_field="ownerTransferCdMileage",
        unit="km",
        state_class="total_increasing",
        icon="mdi:ev-station",
        category="里程",
        diagnostic=True,
        universal=True,
    ),
    "wheel_heat": SignalSpec(
        key="wheel_heat",
        path="Vehicle.Cabin.WheelWarmStatus.WarmOnOff",
        name="方向盘加热",
        freq=Freq.HIGH,
        icon="mdi:steering",
        platforms=frozenset(),  # ★ 由 switch 平台提供【开/关】，不自动建实体
        requires="feature:方向盘加热",
    ),  # 有翻译映射
    "window_back_left": SignalSpec(
        key="window_back_left",
        path="Vehicle.Body.WindowPosition.BackLeftWindow",
        name="左后车窗",
        freq=Freq.HIGH,
        unit="%",
        icon="mdi:car-door",
        category="车窗",
        universal=True,
    ),  # 有翻译映射
    "window_back_right": SignalSpec(
        key="window_back_right",
        path="Vehicle.Body.WindowPosition.BackRightWindow",
        name="右后车窗",
        freq=Freq.HIGH,
        unit="%",
        icon="mdi:car-door",
        category="车窗",
        universal=True,
    ),  # 有翻译映射
    "window_copilot": SignalSpec(
        key="window_copilot",
        path="Vehicle.Body.WindowPosition.CopilotWindow",
        name="副驾车窗",
        freq=Freq.HIGH,
        unit="%",
        icon="mdi:car-door",
        category="车窗",
        universal=True,
    ),  # 有翻译映射
    "window_main": SignalSpec(
        key="window_main",
        path="Vehicle.Body.WindowPosition.MainWindow",
        name="主驾车窗",
        freq=Freq.HIGH,
        unit="%",
        icon="mdi:car-door",
        category="车窗",
        universal=True,
    ),  # 有翻译映射
    "window_skylight": SignalSpec(
        key="window_skylight",
        path="Vehicle.Body.WindowPosition.SkylightWindow",
        name="天窗位置",
        unit="%",
        freq=Freq.HIGH,
        icon="mdi:window-closed-variant",
        platforms=frozenset(),  # ★ L6 实测无数据（SkylightWindow 返回 None）
        universal=True,
    ),
    # ★ 虚拟信号（非 VSS）—— 值来自 coordinator.data 的其他字段
    # ⚠️ gen_signals.py 从 VSS_PATHS 生成，不会包含它们 —— 需手工维护
    "online_status": SignalSpec(
        key="online_status",
        path="",                      # 无 VSS 路径（虚拟信号）
        name="在线状态",
        freq=Freq.HIGH,
        icon="mdi:car-connected",
        category="状态",
        universal=True,
    ),
    # ═══════════════════════════════════════════════════════════════════
    #  ★ 2026-09-24 手工补充的信号（task-14 报告，已实测有数据）
    #  ⚠️ 这些不在 gen_signals.py 的生成源里，需手工维护
    # ═══════════════════════════════════════════════════════════════════
    # ---- 授权 / 账号 ----
    "virtual_key_auth": SignalSpec(
        key="virtual_key_auth",
        path="Vehicle.Cabin.RmtVirtualKeyAuthSts",
        name="远程虚拟钥匙授权",
        freq=Freq.LOW,
        icon="mdi:key-variant",
        category="状态",
        diagnostic=True,
        universal=True,
    ),
    "vehicle_accounts": SignalSpec(
        key="vehicle_accounts",
        path="Vehicle.Account.Cloud.VehicleAccounts",
        name="车辆账号",
        freq=Freq.LOW,
        icon="mdi:account-multiple",
        category="信息",
        diagnostic=True,
        universal=True,
    ),
    # ---- 激活流程 ----
    "provision_complete": SignalSpec(
        key="provision_complete",
        path="Vehicle.Provision.Process.Complete",
        name="激活完成",
        freq=Freq.LOW,
        icon="mdi:check-circle",
        category="信息",
        diagnostic=True,
        universal=True,
    ),
    "provision_finish": SignalSpec(
        key="provision_finish",
        path="Vehicle.Provision.Process.FinishSuccess",
        name="激活成功信息",
        freq=Freq.LOW,
        icon="mdi:clipboard-check",
        category="信息",
        diagnostic=True,
        universal=True,
    ),
    # ---- 保养二级 ----
    "maint_engine_level2": SignalSpec(
        key="maint_engine_level2",
        path="Vehicle.Carcenter.Maintain.enginelevel2",
        name="保养二级",
        freq=Freq.LOW,
        icon="mdi:oil-level",
        category="保养",
        diagnostic=True,
        requires="version:maintainConfig",
    ),
    # ---- 座椅门干涉 ----
    "seat_l_door_interference": SignalSpec(
        key="seat_l_door_interference",
        path="Vehicle.Body.SeatLDoor.InterferenceSts",
        name="左座椅门干涉",
        freq=Freq.MID,
        icon="mdi:alert",
        category="座椅",
        diagnostic=True,
        universal=True,
    ),
    "seat_r_door_interference": SignalSpec(
        key="seat_r_door_interference",
        path="Vehicle.Body.SeatRDoor.InterferenceSts",
        name="右座椅门干涉",
        freq=Freq.MID,
        icon="mdi:alert",
        category="座椅",
        diagnostic=True,
        universal=True,
    ),
    # ---- 冰箱预约 / 离车模式 ----
    "fridge_reserve": SignalSpec(
        key="fridge_reserve",
        path="Vehicle.CarSettings.Xmode.ReserveFridge",
        name="冰箱预约",
        freq=Freq.MID,
        icon="mdi:fridge-outline",
        category="冰箱",
        requires="feature:冰箱",
    ),
    "xmode": SignalSpec(
        key="xmode",
        path="Vehicle.CarSettings.MoveOffOnTime.Xmode",
        name="按时出发",
        freq=Freq.MID,
        icon="mdi:clock-start",
        category="设置",
        # ★ 2026-09-28 形态决策（用户明确）：保持【只读 sensor】展示开启状态与设置内容。
        #
        #   不做成可控开关，原因：
        #     · 按时出发本质是"自定义模式"，HA 的自动化完全能实现同等效果
        #     · 写命令 MoveOffAdd / MoveOffModify 在 _JOB_CHANNEL_COMMANDS 里
        #       → 走 LiNdn（JOB）通道，HTTP 不支持，与充电同一门槛
        #     · 一个只能读的开关没有价值
        #
        #   显示内容（rendering.py 的 xmode 分支）：
        #     "已关闭"                              无生效计划
        #     "已开启 · 07:00 空调22°C 法定工作日"   有生效计划（+N 提示多条）
        requires="version:departOnTime",
    ),
    # ---- 空调温度色 ----
    "ac_temp_color": SignalSpec(
        key="ac_temp_color",
        path="Vehicle.Cabin.AC.FrtWindTempColor",
        name="空调温度色",
        freq=Freq.MID,
        icon="mdi:palette",
        category="空调",
        diagnostic=True,
        universal=True,
    ),
    # ---- 充电校准 / 位置 / 后负载 ----
    "charge_calibration": SignalSpec(
        key="charge_calibration",
        path="Vehicle.VehInfo.CarCenter.ChargeManagement.ChargingCalibration",
        name="充电校准",
        freq=Freq.LOW,
        icon="mdi:tune",
        category="充电桩",
        diagnostic=True,
        universal=True,
    ),
    "charge_here": SignalSpec(
        key="charge_here",
        path="Vehicle.Powertrain.ChargingPile.ScheduledCharging.ChargeHere",
        # ★ 2026-09-28 语义修正（用户报告"车不在充电位却显示在充电位"）：
        #   App spec description = "此地执行预约状态"（type=actuator，可写设置项）
        #   App UI 文案          = "仅在固定地点执行预约，如需关闭请在车机端操作"
        #   → 该信号表示【是否启用"仅在此固定地点执行预约充电"】这个开关，
        #     与"车此刻在哪"无关。
        #   旧名「充电位置」+ 旧翻译 {0:不在充电位, 1:在充电位} 是语义错误。
        name="仅在此地预约",
        freq=Freq.LOW,
        icon="mdi:map-marker-check",
        category="充电",
        diagnostic=True,   # 设置项，默认禁用避免干扰
        universal=True,
    ),
    "rear_load_mode": SignalSpec(
        key="rear_load_mode",
        path="Vehicle.VehInfo.CarSettings.Maintain.RearLoadModeSetting",
        name="后负载模式",
        freq=Freq.LOW,
        icon="mdi:weight",
        category="设置",
        diagnostic=True,
        universal=True,
    ),
    # ---- 电池功率条 ----
    "ress_power_bar_color": SignalSpec(
        key="ress_power_bar_color",
        path="Vehicle.Powertrain.Battery.RESSPowerBarCol",
        name="电池功率条颜色",
        freq=Freq.MID,
        icon="mdi:palette-outline",
        category="电池",
        diagnostic=True,
        universal=True,
    ),
    # ---- OGC（第三方充电桩）----
    "ogc_charge_current": SignalSpec(
        key="ogc_charge_current",
        path="Vehicle.Powertrain.Battery.OGCChargeCurrent",
        name="OGC 充电电流",
        freq=Freq.MID,
        unit="A",
        icon="mdi:current-ac",
        category="充电桩",
        universal=True,
    ),
    "ogc_charge_voltage": SignalSpec(
        key="ogc_charge_voltage",
        path="Vehicle.Powertrain.Battery.OGCChargeVoltage",
        name="OGC 充电电压",
        freq=Freq.MID,
        unit="V",
        icon="mdi:sine-wave",
        category="充电桩",
        universal=True,
    ),
    "ogc_type": SignalSpec(
        key="ogc_type",
        path="Vehicle.Powertrain.ChargingPile.OGCType",
        name="OGC 类型",
        freq=Freq.LOW,
        icon="mdi:ev-station",
        category="充电桩",
        diagnostic=True,
        requires="version:ogcType",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    #  ★ 2026-09-28 补齐实测【有数据】的缺失 VSS 信号（task-18）
    #
    #  依据（★ 必须用 apk_latest，不是 apk_decompile/ideal 的 8.27.0 旧版）：
    #    apk_latest/decompiled/smali_classes11/com/chehejia/lib/vehicle/
    #        limesh/x/sdk/constant/LxMeshVssConstant.smali
    #
    #  实测来源：docs/缺失信号实测_20260928.md
    #            lixiang-reverse/data/missing_vss_probe_result.json
    #  30 条缺失信号中仅 11 条有数据；本段只声明其中【5 条裸标量】——
    #  其余 5 条 envelope 信号值恒为常数/含义不明，暂不建实体；
    #  19 条无数据（L6 无此硬件），见本段末尾注释。
    #
    #  ★ 全部 diagnostic=True → EntityCategory.DIAGNOSTIC + 默认禁用，
    #    避免污染用户界面（验收要求）。
    # ═══════════════════════════════════════════════════════════════════════

    # ── 后视镜加热（实测值 0 = 未加热）────────────────────────────────
    #  App: LxMeshVssConstant.smali:699
    #       .field public static final LRearMirroHeatSts = "Vehicle.Body.RearMirro.LHeatSts"
    "mirror_heat_left": SignalSpec(
        key="mirror_heat_left",
        path="Vehicle.Body.RearMirro.LHeatSts",
        name="左后视镜加热",
        freq=Freq.MID,
        semantics=Semantics.SWITCH_ON,   # 非 0 = 加热中
        icon="mdi:mirror",
        category="灯光",
        platforms=frozenset({"binary_sensor"}),
        diagnostic=True,
        universal=True,
    ),
    #  App: LxMeshVssConstant.smali:954
    #       .field public static final RRearMirroHeatSts = "Vehicle.Body.RearMirro.RHeatSts"
    "mirror_heat_right": SignalSpec(
        key="mirror_heat_right",
        path="Vehicle.Body.RearMirro.RHeatSts",
        name="右后视镜加热",
        freq=Freq.MID,
        semantics=Semantics.SWITCH_ON,
        icon="mdi:mirror",
        category="灯光",
        platforms=frozenset({"binary_sensor"}),
        diagnostic=True,
        universal=True,
    ),

    # ── 主驾座椅占用（★ 隐私敏感，务必默认禁用）──────────────────────
    #  App: LxMeshVssConstant.smali:1251
    #       .field public static final drvSeatOccupied = "Vehicle.Body.Seat.DrvSeatOccupied"
    #  ⚠️ 这是"车内是否有人"的隐私信号 —— diagnostic=True 使其默认禁用，
    #     用户主动启用后才会出现在设备页面。
    "drv_seat_occupied": SignalSpec(
        key="drv_seat_occupied",
        path="Vehicle.Body.Seat.DrvSeatOccupied",
        name="主驾有人",
        freq=Freq.MID,
        semantics=Semantics.SWITCH_ON,   # 非 0 = 有人
        icon="mdi:account-multiple",
        category="座椅",
        platforms=frozenset({"binary_sensor"}),
        diagnostic=True,
        universal=True,
    ),

    # ── 遮阳帘位置（实测值 0；0-100 位置值）──────────────────────────
    #  App: LxMeshVssConstant.smali:624
    #       .field public static final FrontPos = "Vehicle.Body.SunShade.FrontPos"
    "sunshade_front_pos": SignalSpec(
        key="sunshade_front_pos",
        path="Vehicle.Body.SunShade.FrontPos",
        name="前遮阳帘位置",
        freq=Freq.MID,
        unit="%",
        state_class="MEASUREMENT",
        icon="mdi:window-shutter",
        category="车窗",
        diagnostic=True,
        requires="feature:遮阳帘",
    ),
    #  App: LxMeshVssConstant.smali:969
    #       .field public static final RearPos = "Vehicle.Body.SunShade.RearPos"
    "sunshade_rear_pos": SignalSpec(
        key="sunshade_rear_pos",
        path="Vehicle.Body.SunShade.RearPos",
        name="后遮阳帘位置",
        freq=Freq.MID,
        unit="%",
        state_class="MEASUREMENT",
        icon="mdi:window-shutter",
        category="车窗",
        diagnostic=True,
        requires="feature:遮阳帘",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    #  ★ 以下 5 条实测【有数据】但【不建实体】—— 保留声明与依据备查
    #
    #  ⚠️ 关键：这 5 条的 VSS 返回值是【包装 JSON】而非裸标量：
    #       {"id":"...","value":"0","support":1,"protocolVersion":1,...}
    #     真实值在 .value；且 .support 需为 1 才有效。
    #     （实测原始返回见 missing_vss_probe_result.json）
    #     与上面 5 条裸标量的形状【不同】，不是同一个渲染路径。
    #
    #  不建的原因（逐条）：
    #    · PreHeatAndPreCoolSts (smali:879) 预热/预冷 → 实测恒 0，无变化价值
    #    · PreBTCTime           (smali:874) 电池预热时间 → 实测 65535 = uint16 无效哨兵
    #    · ManuTempAdjStatus    (smali:759) 手动调温 → 实测恒 0，含义未确证
    #    · RemoteCabinRearview  (smali:1266) 远程座舱后视 → 实测恒 0，仅实验室开关
    #    · CampMode.SupportTime 无 smali 行号（不在 LxMeshVssConstant 中）
    #        实测 value=24（小时）→ 露营模式支持时长，纯诊断信息，价值低
    #      ⚠️ CampMode 无 App 源码行号，故【不能】按 CONTRIBUTING 要求附依据
    #         → 不建（宁缺毋滥）。
    #
    #  ⚠️ Carcenter.Maintain.Config (smali:1261) 保养配置：
    #     返回完整保养计划 JSON（含中文名/周期里程/周期月数/阈值等级），
    #     是【嵌套 JSON 里的又一层 JSON】，不适合做实体。
    #     可用于补全既有保养实体的周期属性（本任务未做，留作后续）。
    #
    #  ═══ 19 条实测无数据（L6 无此硬件）—— 均不建实体 ═══
    #    · Body.SunShade.RearLeftPos / RearRightPos      L6 只有前排遮阳帘
    #    · Body.RingLightColor.{Blue,White,Yellow}Sts    氛围灯，L6 无
    #    · Body.ElectrochromicMirror.{RLDoorOne,RRDoorOne,ThirdLeft,ThirdRight}Sts
    #                                                    流媒体后视镜 ×4，L6 无
    #    · APP.Setting.{Baffle,ControlSort,ParkConfig}   非车端信号（App 本地配置）
    #    · Carcenter.Maintain.{engine,airfilter}         已由 Maintain.Config 覆盖
    #    · Powertrain.ChargingPile.ScheduledCharging.
    #        {NewReserveFinishTime26,ReserveStartTime26,ReserveTimeStatus}
    #                                                    充电通道受限（LiNdn）
    #    · Cabin.CLTC.MileageFinalResultFuel / CarSettings.Preference.CLTCWLTC
      #  ★ 更正（2026-09-29）：上面两行「无 CLTC/WLTC 切换」是【错的】。
      #    CarSettings.Preference.CLTCWLTC 的真实路径带 {{AccountId}} 模板：
      #      Vehicle.{{AccountId}}.CarSettings.Preference.CLTCWLTC
      #    当初用不带模板的路径去查 → 无数据 → 误判为「无此功能」。
      #    它已正确实现为 range_display_mode（续航显示工况，决定 CLTC/WLTC）。
    # ═══════════════════════════════════════════════════════════════════════
}

# ═══════════════════════════════════════════════════════════════════════════
#  查询辅助
# ═══════════════════════════════════════════════════════════════════════════
# ★ 2026-10-02：保养项白名单 —— 这些虽标 diagnostic，但默认启用。
#   App 把「车辆保养」放在车辆健康页显眼位置（5 项），是用户可见的主要功能。
#   依据：抓包 vss_full_state.json 的 Vehicle.Carcenter.Maintain.* 含 33 字段/项。
MAINTAIN_KEYS = frozenset({
    "maint_acfilter",       # 空调滤芯保养
    "maint_coolfuild",      # 冷却液保养
    "maint_engine_oil",     # 机油 / 增程器小保养
    "maint_brake_oil",      # 油液 / 刹车油保养
    "maint_sparkplug",      # 火花塞保养
    "maint_engine_level2",  # 增程器大保养（保养二级）
})


def to_sensor_description(spec: SignalSpec):
    """把 SignalSpec 转成 HA 的 SensorEntityDescription。

    ★ 需要 homeassistant 包 → 仅在 HA 运行时调用。
    """
    from homeassistant.components.sensor import SensorEntityDescription
    from homeassistant.const import EntityCategory

    from .sensor import _DCLASS, _SCLASS, _UNITS

    kw: dict = {"key": spec.key, "name": spec.name}
    if spec.icon:
        kw["icon"] = spec.icon
    if spec.device_class and spec.device_class in _DCLASS:
        kw["device_class"] = _DCLASS[spec.device_class]
    if spec.unit and spec.unit in _UNITS:
        kw["native_unit_of_measurement"] = _UNITS[spec.unit]
    if spec.state_class and spec.state_class in _SCLASS:
        kw["state_class"] = _SCLASS[spec.state_class]
    # ★ 2026-10-02：保养项例外 —— 归诊断类（设备页折叠）但【默认启用】。
    #   理由：App 把「车辆保养」放在车辆健康页的显眼位置（5 项），
    #   是用户可见的主要功能，不该默认禁用让用户自己去开。
    #   依据：抓包 vss_full_state.json 里 Vehicle.Carcenter.Maintain.*
    #        每项含 33 字段（剩余里程/到期日/周期…），启用后能拿到真实数据，
    #        与 App 截图逐项吻合。
    if spec.diagnostic:
        kw["entity_category"] = EntityCategory.DIAGNOSTIC
        kw["entity_registry_enabled_default"] = (
            spec.key in MAINTAIN_KEYS        # 保养项默认启用
        )
    return SensorEntityDescription(**kw)


def to_sensor_descriptions(specs=None):
    """批量转换。specs 为 None 时按 platform 取全部（不过滤车型能力）。"""
    return [to_sensor_description(s) for s in (specs if specs is not None else specs_for("sensor"))]



def to_binary_description(spec: SignalSpec):
    """把 SignalSpec 转成 BinarySensorEntityDescription。

    ★ 架构方案 2.5：替代 binary_sensor.py 的 (Description, kind) 元组。
      语义由 spec.semantics 表达（枚举），不再是字符串分派。

    ★ 2026-09-28 修复（task-18）：补上 diagnostic 支持。
      此前只有 to_sensor_description() 处理 spec.diagnostic，
      binary_sensor 走本函数 → diagnostic=True 被【静默忽略】，
      导致诊断/隐私类二元传感器无法默认禁用、直接污染设备页面。
      （例：主驾有人 = 隐私信号，必须默认禁用。）
    """
    from homeassistant.components.binary_sensor import BinarySensorEntityDescription
    from homeassistant.const import EntityCategory

    from .binary_sensor import _DCLASS_BS

    kw: dict = {"key": spec.key, "name": spec.name}
    if spec.icon:
        kw["icon"] = spec.icon
    if spec.device_class and spec.device_class in _DCLASS_BS:
        kw["device_class"] = _DCLASS_BS[spec.device_class]
    # ★ 与 to_sensor_description 对齐：诊断类 → DIAGNOSTIC 分组 + 默认禁用
    if spec.diagnostic:
        kw["entity_category"] = EntityCategory.DIAGNOSTIC
        kw["entity_registry_enabled_default"] = False
    return BinarySensorEntityDescription(**kw)


def to_binary_descriptions(specs=None):
    """批量转换（返回 (desc, spec) 元组）。specs 为 None 时取全部二元信号。"""
    return [
        (to_binary_description(s), s)
        for s in (specs if specs is not None else specs_for("binary_sensor"))
    ]



def specs_for(platform: str, features: dict | None = None,
              ability=None) -> list[SignalSpec]:
    """按平台 + 车型能力过滤信号。

    ★ 2026-09-28：改由每个 SignalSpec 自己的 requires/universal 声明判定
      （见 SignalSpec 文档）。features/ability 为 None 时【不过滤】
      （保持旧调用点行为；平台应按需传入以获得车型区分）。

    参数
    ----
    platform : "sensor" / "binary_sensor" / ...
    features : features.detect_features() 的结果
    ability  : vehicle_ability.VehicleAbility 实例
    """
    out = [s for s in SIGNALS.values() if platform in s.platforms]
    if features is None and ability is None:
        return out
    from .features import filter_specs
    keep, _ = filter_specs(out, features or {}, ability)
    return keep


def by_freq(freq: Freq) -> list[SignalSpec]:
    """按频率档位筛选（coordinator 用）。

    ★ 2026-09-24：排除虚拟信号（path 为空）—— 它们不走 VSS 轮询。
    """
    return [s for s in SIGNALS.values() if s.freq == freq and s.path]


def paths_for(freq: Freq | None = None) -> list[str]:
    """返回 VSS 路径列表（coordinator 轮询用）。

    freq=None 表示全部。

    ★ 2026-09-24：排除【虚拟信号】（path 为空）——
      它们的值来自 coordinator.data 的其他字段，不通过 VSS 轮询。
    """
    items = [s for s in SIGNALS.values() if s.path]
    if freq is not None:
        items = [s for s in items if s.freq == freq]
    return [s.path for s in items]


def path_of(key: str) -> str:
    """按 key 取 VSS 路径（兼容旧代码的 VSS_PATHS 用法）。"""
    spec = SIGNALS.get(key)
    return spec.path if spec else ""


def value_map_of(key: str) -> dict | None:
    """按 key 取值翻译表。"""
    spec = SIGNALS.get(key)
    return spec.value_map if spec else None


# 兼容：把 SIGNALS 转成旧的 {key: path} 形式
VSS_PATHS_COMPAT: dict[str, str] = {
    k: s.path for k, s in SIGNALS.items() if s.path
}


__all__ = [
    "Freq", "Semantics", "SignalSpec", "SIGNALS",
    "specs_for", "by_freq", "paths_for", "path_of", "value_map_of",
    "to_sensor_description", "to_sensor_descriptions",
    "to_binary_description", "to_binary_descriptions",
    "VSS_PATHS_COMPAT",
]
