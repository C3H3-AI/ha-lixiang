"""Li Auto 传感器实体（110 个信号）.

- online_status: basics.vehicleStatus 在线标记
- 实时信号 (vss/get-batch): 电池/充电/续航/车门/空调/座椅/轮胎/位置...

VSS 路径全集见 docs/VSS路径全集_20260922.md
"""

from __future__ import annotations

import json
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNKNOWN,
    UnitOfTemperature,
    UnitOfPressure,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfPower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

# 单位名 → HA 常量
_UNITS = {
    "PERCENTAGE": PERCENTAGE, "°C": UnitOfTemperature.CELSIUS,
    "kPa": UnitOfPressure.KPA, "km": UnitOfLength.KILOMETERS,
    "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR, "kW": UnitOfPower.KILO_WATT,
    "V": UnitOfElectricPotential.VOLT, "A": UnitOfElectricCurrent.AMPERE,
    "min": UnitOfTime.MINUTES, "%": PERCENTAGE,
    "d": UnitOfTime.DAYS,   # ★ 2026-10-02：辅助驾驶天数
    "L": "L",           # 油量升

    "kWh": "kWh",   # ★ 2026-10-02：累计充电量（能源面板）
}
_DCLASS = {
    "BATTERY": SensorDeviceClass.BATTERY,
    "TEMPERATURE": SensorDeviceClass.TEMPERATURE,
    "PRESSURE": SensorDeviceClass.PRESSURE,
    "DISTANCE": SensorDeviceClass.DISTANCE,
    "SPEED": SensorDeviceClass.SPEED,
    "POWER": SensorDeviceClass.POWER,
    "VOLTAGE": SensorDeviceClass.VOLTAGE,
    "CURRENT": SensorDeviceClass.CURRENT,
    "DURATION": SensorDeviceClass.DURATION,
    "ENERGY": SensorDeviceClass.ENERGY,   # ★ 2026-10-02：累计充电量（能源面板）
}
_SCLASS = {
    "MEASUREMENT": SensorStateClass.MEASUREMENT,
    "TOTAL": SensorStateClass.TOTAL,
    "TOTAL_INCREASING": SensorStateClass.TOTAL_INCREASING,
}


# ★ 诊断类实体（借自 huawei-auto-cloud 的 EntityCategory 用法）
#   这些是"排查/元数据"类信息，不是日常关心的状态 →
#   归入 HA 的「诊断」分组，设备页面自动折叠，界面清爽。
_DIAGNOSTIC_CATS = frozenset({
    "OTA", "保养", "信息", "设置", "电源",
})
_DIAGNOSTIC_KEYS = frozenset({
    "config_code", "provision_auth", "hu_diag", "ota_version", "ota_short",
    "ota_state", "ota_status", "ota_progress",
    "low_vol_flag", "low_vol_mode", "battery_keep_warm",
})

# ⚠️ 注意：保养项「默认启用」的判定在 signals.py 的 to_sensor_description()，
#   不在这里 —— 实体描述表实际由 SIGNALS 动态生成（见 async_setup_entry）。

# ── 保养项字段 → 中文属性名（2026-10-03 按抓包实测重写）─────────────────
#   依据：vss_full_state.json 的 Vehicle.Carcenter.Maintain.* 每项含 33 字段。
#   旧实现查的 higherLevel/lowerLevel/percentage/remainMileage **不存在**，
#   导致属性长期为空。下面是实测存在的关键字段。
_MAINT_FIELDS: tuple[tuple[str, str], ...] = (
    ("maintainLeftMileage", "剩余里程"),
    ("maintainLeftDays", "剩余天数"),
    ("maintainDueDate", "到期日"),
    ("periodMileage", "保养周期里程"),
    ("periodMonth", "保养周期月数"),
    ("mileageSource", "计程来源"),
    ("engineMileage", "增程器里程"),
    ("mileage", "累计里程"),
    ("maintenanceMileage", "上次保养里程"),
    ("maintenanceEngineMileage", "上次保养增程器里程"),
    ("maintenanceValid", "是否显示"),
    ("rule", "提醒策略"),
)

# 说明：以下字段对用户可读性低或属于内部标记，不上抛为属性
#   iconUri / dateColor / higherLevelColor / mileageColor / timestamp /
#   payloadId / pushingStatusVssKey / subscribeRecordVssKey /
#   oilLife / saveCount / isMaintainIndeed / maintainIndeedReason /
#   isAgentMaintenance / timeValid / langName


def _maint_attrs(o: dict) -> dict:
    """把保养项 JSON 转成可读属性。

    ★ 关键换算（不做用户会看不懂）：

    - ``maintainLeftDays`` 单位是**毫秒**（实测 27388800000 ≈ 317 天），
      同时给一个人类可读的「剩余天数（可读）」。
    - ``maintainDueDate`` 是 ``YYYYMMDD`` 整数；``"--"``/0 表示无到期日
      （火花塞就是这种：只看里程不看时间），此时不输出。
    - ``maintenanceValid`` 0/1 → 中文「是/否」，因为它是「该项是否在
      App 里显示」的开关（如增程器大保养 valid=0 → App 不显示）。
    - ``mileageSource`` engine/total → 「增程器里程 / 总里程」。
    """
    out: dict = {}
    for src, label in _MAINT_FIELDS:
        v = o.get(src)
        if v in (None, ""):
            continue

        if src == "maintainLeftDays":
            # 毫秒 → 天（负数/极大值 = 无期限，不展示）
            try:
                days = float(v) / 86400000.0
            except (TypeError, ValueError):
                continue
            if days < 0 or days > 36500:        # 负数或 >100 年 → 视为无期限
                continue
            out["剩余天数"] = f"{days:.0f} 天"
            out["剩余天数(数值)"] = round(days)
            continue

        if src == "maintainDueDate":
            s = str(v).strip()
            if not s.isdigit() or len(s) != 8:
                continue                         # "--" 等 → 不输出
            out["到期日"] = f"{s[:4]}-{s[4:6]}-{s[6:]}"
            continue

        if src == "maintenanceValid":
            out["是否显示"] = "是" if str(v) in ("1", "True", "true") else "否"
            continue

        if src == "mileageSource":
            out["计程来源"] = {"engine": "增程器里程",
                              "total": "总里程"}.get(str(v), str(v))
            continue

        # 无时间项的保养（如火花塞只看里程）用哨兵值表示"无周期"，
        # 实测 periodMonth = -2147483647。原样上抛对用户是纯噪音。
        if src in ("periodMonth", "periodMileage"):
            try:
                if int(v) <= 0 or int(v) >= 2147483647:
                    continue
            except (TypeError, ValueError):
                continue

        out[label] = v
    return out


def _mk(key, spec):
    name, dclass, unit, sclass, icon, cat = spec
    kw = dict(key=key, name=name, icon=icon)
    if dclass in _DCLASS: kw["device_class"] = _DCLASS[dclass]
    if unit in _UNITS: kw["native_unit_of_measurement"] = _UNITS[unit]
    if sclass in _SCLASS: kw["state_class"] = _SCLASS[sclass]
    # ★ 诊断类实体归入 EntityCategory.DIAGNOSTIC（设备页面折叠显示）
    #   ⚠️ 保养项的「默认启用」例外在 signals.py（真正生效的路径）
    if cat in _DIAGNOSTIC_CATS or key in _DIAGNOSTIC_KEYS:
        kw["entity_category"] = EntityCategory.DIAGNOSTIC
        kw["entity_registry_enabled_default"] = False
    return SensorEntityDescription(**kw)


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="online_status", name="在线状态", icon="mdi:car-connected"),
    # ---- 电池 ----
    _mk("battery_level", ('电池电量', 'BATTERY', 'PERCENTAGE', 'MEASUREMENT', 'mdi:battery-high', '电池')),
    _mk("charge_status", ('充电状态', None, None, None, 'mdi:ev-station', '电池')),
    _mk("charge_power_cltc", ('充电功率(CLTC)', 'POWER', 'kW', 'MEASUREMENT', 'mdi:flash', '电池')),
    _mk("charge_power_wltc", ('充电功率(WLTC)', 'POWER', 'kW', 'MEASUREMENT', 'mdi:flash', '电池')),
    _mk("charge_voltage_ac", ('充电电压(AC)', 'VOLTAGE', 'V', 'MEASUREMENT', 'mdi:sine-wave', '电池')),
    _mk("charge_current_ac", ('充电电流(AC)', 'CURRENT', 'A', 'MEASUREMENT', 'mdi:current-ac', '电池')),
    _mk("battery_pack_voltage", ('电池包电压', 'VOLTAGE', 'V', 'MEASUREMENT', 'mdi:car-battery', '电池')),
    _mk("charge_remain_time", ('剩余充电时间', 'DURATION', 'min', 'MEASUREMENT', 'mdi:timer-sand', '电池')),
    _mk("charge_complete", ('充电完成状态', None, None, None, 'mdi:battery-check', '电池')),
    # ★ 2026-10-02：累计充电量（能源面板用）—— 值来自 coordinator 低频 HTTP
    _mk("charge_total_energy", ('累计充电量', 'ENERGY', 'kWh', 'TOTAL_INCREASING',
                                'mdi:battery-charging-100', '电池')),

    # ★ 2026-10-02：本月里程 / 充电量（与 App 首页、充电页同口径）
    _mk("month_km", ('本月里程', 'DISTANCE', 'km', 'MEASUREMENT',
                  'mdi:road-variant', '里程')),
    _mk("month_elec_km", ('本月纯电里程', 'DISTANCE', 'km', 'MEASUREMENT',
                  'mdi:road-variant', '里程')),
    _mk("month_elec_kwh", ('本月耗电量', 'ENERGY', 'kWh', 'TOTAL',
                  'mdi:lightning-bolt', '里程')),
    _mk("month_fuel_l", ('本月耗油量', None, 'L', 'TOTAL',
                  'mdi:gas-station', '里程')),
    _mk("month_charge_kwh", ('本月充电量', 'ENERGY', 'kWh', 'TOTAL',
                  'mdi:battery-charging', '里程')),
    _mk("discharge_status", ('放电状态', None, None, None, 'mdi:battery-minus', '电池')),
    # ---- 充电桩 ----
    _mk("charge_limit", ('充电上限', None, '%', None, 'mdi:battery-charging-80', '充电桩')),
    _mk("scheduled_charge_state", ('预约充电状态', None, None, None, 'mdi:calendar-check', '充电桩')),
    _mk("scheduled_charge_start", ('预约开始时间', None, None, None, 'mdi:clock-start', '充电桩')),
    _mk("scheduled_charge_end", ('预约结束时间', None, None, None, 'mdi:clock-end', '充电桩')),
    # ---- 续航 ----
    _mk("range_elec_cltc", ('纯电续航(CLTC)', 'DISTANCE', 'km', 'MEASUREMENT', 'mdi:map-marker-distance', '续航')),
    _mk("range_fuel_cltc", ('燃油续航(CLTC)', 'DISTANCE', 'km', 'MEASUREMENT', 'mdi:gas-station', '续航')),
    _mk("range_elec_wltc", ('纯电续航(WLTC)', 'DISTANCE', 'km', 'MEASUREMENT', 'mdi:map-marker-distance', '续航')),
    _mk("range_fuel_wltc", ('燃油续航(WLTC)', 'DISTANCE', 'km', 'MEASUREMENT', 'mdi:gas-station', '续航')),
    _mk("fuel_level", ('油量', None, 'L', 'MEASUREMENT', 'mdi:fuel', '续航')),
    # ---- 车门 ----
    # ---- 车窗 ----
    _mk("window_main", ('主驾车窗', None, '%', None, 'mdi:car-door', '车窗')),
    # ⚠️ window_skylight 移除了：L6 实测 SkylightWindow 返回 None
    #    （该车型可能无天窗，或信号名不同 —— 保留 VSS 路径供其他车型用）
    # ★ 2026-09-23 补充（task-14 高价值遗漏）
    _mk("low_vol_status", ('低压电源状态', None, None, None, 'mdi:car-battery', '电池')),
    # ⚠️ mileage_final 移除了：L6 实测 MileageFinalResult 返回 None
    _mk("battery_type", ('电池类型', None, None, None, 'mdi:battery-sync', '电池')),
    _mk("charge_order_mode", ('预约充电模式', None, None, None, 'mdi:calendar-clock', '充电桩')),
    _mk("window_copilot", ('副驾车窗', None, '%', None, 'mdi:car-door', '车窗')),
    _mk("window_back_left", ('左后车窗', None, '%', None, 'mdi:car-door', '车窗')),
    _mk("window_back_right", ('右后车窗', None, '%', None, 'mdi:car-door', '车窗')),
    _mk("sunshade", ('遮阳帘', None, None, None, 'mdi:window-shutter', '车窗')),
    # ---- 空调 ----
    _mk("inside_temp", ('车内温度', 'TEMPERATURE', '°C', 'MEASUREMENT', 'mdi:thermometer', '空调')),
    _mk("ac_set_temp", ('空调设定温度', 'TEMPERATURE', '°C', None, 'mdi:thermostat', '空调')),
    _mk("ac_wind_mode", ('风向模式', None, None, None, 'mdi:weather-windy', '空调')),
    _mk("ac_defrost", ('除霜模式', None, None, None, 'mdi:snowflake-melt', '空调')),
    _mk("ac_fan_speed", ('快冷快热', None, None, None, 'mdi:fan', '空调')),
    # ---- 座椅 ----
    _mk("seat_fl_heat", ('主驾座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_fl_vent", ('主驾座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_fr_heat", ('副驾座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_fr_vent", ('副驾座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_sl_heat", ('二排左座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_sr_heat", ('二排右座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_sm_heat", ('二排中座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_tl_heat", ('三排左座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    _mk("seat_tr_heat", ('三排右座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    # ★ 2026-09-23 补充（task-14 高价值遗漏）
    _mk("seat_sl_vent", ('二排左座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_sr_vent", ('二排右座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_tl_vent", ('三排左座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_tr_vent", ('三排右座椅通风', None, None, None, 'mdi:car-seat-cooler', '座椅')),
    _mk("seat_tm_heat", ('三排中座椅加热', None, None, None, 'mdi:car-seat-heater', '座椅')),
    # ---- 冰箱 ----
    _mk("fridge_status", ('冰箱工作状态', None, None, None, 'mdi:fridge', '冰箱')),
    _mk("fridge_mode", ('冰箱模式', None, None, None, 'mdi:fridge-outline', '冰箱')),
    _mk("fridge_cool_temp", ('冰箱制冷温度', None, None, None, 'mdi:snowflake', '冰箱')),
    _mk("fridge_remain_time", ('冰箱剩余时间', 'DURATION', 'min', None, 'mdi:timer', '冰箱')),
    # ---- 轮胎 ----
    _mk("tire_fl", ('胎压 左前', 'PRESSURE', 'kPa', 'MEASUREMENT', 'mdi:car-tire-alert', '轮胎')),
    _mk("tire_fr", ('胎压 右前', 'PRESSURE', 'kPa', 'MEASUREMENT', 'mdi:car-tire-alert', '轮胎')),
    _mk("tire_rl", ('胎压 左后', 'PRESSURE', 'kPa', 'MEASUREMENT', 'mdi:car-tire-alert', '轮胎')),
    _mk("tire_rr", ('胎压 右后', 'PRESSURE', 'kPa', 'MEASUREMENT', 'mdi:car-tire-alert', '轮胎')),
    _mk("tire_fl_temp", ('胎温 左前', 'TEMPERATURE', '°C', 'MEASUREMENT', 'mdi:thermometer-lines', '轮胎')),
    _mk("tire_fr_temp", ('胎温 右前', 'TEMPERATURE', '°C', 'MEASUREMENT', 'mdi:thermometer-lines', '轮胎')),
    _mk("tire_rl_temp", ('胎温 左后', 'TEMPERATURE', '°C', 'MEASUREMENT', 'mdi:thermometer-lines', '轮胎')),
    _mk("tire_rr_temp", ('胎温 右后', 'TEMPERATURE', '°C', 'MEASUREMENT', 'mdi:thermometer-lines', '轮胎')),
    # ---- 位置 ----
    _mk("speed", ('车速', 'SPEED', 'km/h', 'MEASUREMENT', 'mdi:speedometer', '位置')),
    # ---- 连接 ----
    # ---- OTA ----
    _mk("ota_version", ('车机版本', None, None, None, 'mdi:car-info', 'OTA')),
    _mk("ota_short", ('车机版本(短)', None, None, None, 'mdi:car-info', 'OTA')),
    _mk("ota_state", ('OTA 状态', None, None, None, 'mdi:download', 'OTA')),
    _mk("ota_status", ('OTA 结果', None, None, None, 'mdi:download-circle', 'OTA')),
    _mk("ota_progress", ('OTA 进度', None, '%', None, 'mdi:progress-download', 'OTA')),
    # ---- 哨兵 ----
    _mk("sentry_video_count", ('哨兵视频数', None, None, 'MEASUREMENT', 'mdi:video', '哨兵')),
    # ---- 保养 ----
    _mk("maint_acfilter", ('空调滤芯', None, None, None, 'mdi:air-filter', '保养')),
    _mk("maint_coolfuild", ('冷却液', None, None, None, 'mdi:coolant-temperature', '保养')),
    _mk("maint_engine_oil", ('机油', None, None, None, 'mdi:oil', '保养')),
    _mk("maint_brake_oil", ('刹车油', None, None, None, 'mdi:car-brake-fluid-level', '保养')),
    _mk("maint_sparkplug", ('火花塞', None, None, None, 'mdi:flash', '保养')),
    _mk("trip_total", ('行程总计', None, None, None, 'mdi:counter', '保养')),
    # ---- 里程统计（2026-09-28）----
    # ★ 与 trip_total 同一 VSS 路径，取不同字段（见 signals.py 与 rendering.py 注释）
    _mk("stat_days", ('陪伴天数', None, None, 'TOTAL_INCREASING', 'mdi:calendar-heart', '里程')),
    _mk("stat_mileage", ('陪伴里程', None, 'km', 'TOTAL_INCREASING', 'mdi:road-variant', '里程')),
    _mk("stat_elec_mileage", ('耗电行驶', None, 'km', 'TOTAL_INCREASING', 'mdi:ev-station', '里程')),
    # ★ 2026-10-02：Trip.Total 更多字段（App 显示、此前未暴露）
    _mk("stat_total_mileage", ('总里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                               'mdi:counter', '里程')),
    _mk("stat_engine_mileage", ('发动机里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                                'mdi:engine', '里程')),
    _mk("stat_ad_mileage", ('辅助驾驶里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                            'mdi:steering', '里程')),
    _mk("stat_noa_mileage", ('NOA 里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                             'mdi:highway', '里程')),
    _mk("stat_acc_mileage", ('ACC 里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                             'mdi:car-cruise-control', '里程')),
    _mk("stat_lcc_mileage", ('LCC 里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                             'mdi:highway', '里程')),
    _mk("stat_cd_mileage", ('纯电里程', 'DISTANCE', 'km', 'TOTAL_INCREASING',
                            'mdi:ev-station', '里程')),
    _mk("stat_ad_days", ('辅助驾驶天数', None, 'd', 'TOTAL_INCREASING',
                         'mdi:calendar-check', '里程')),
    # ---- 空气 ----
    _mk("air_pollution", ('空气污染指数', None, None, 'MEASUREMENT', 'mdi:air-filter', '空气')),
    _mk("low_battery_mode", ('低电量模式', None, None, None, 'mdi:battery-low', '空气')),
    _mk("travel_status", ('行驶状态', None, None, None, 'mdi:car-cruise-control', '空气')),
    # ---- 灯光 ----
    _mk("light_lic", ('牌照灯', None, None, None, 'mdi:lightbulb', '灯光')),
    _mk("mirror_left", ('左后视镜', None, None, None, 'mdi:mirror', '灯光')),
    _mk("mirror_right", ('右后视镜', None, None, None, 'mdi:mirror', '灯光')),
    # ---- 电源 ----
    _mk("low_vol_mode", ('低压电源模式', None, None, None, 'mdi:power-plug-battery', '电源')),
    # ---- 影像 ----
    _mk("svm_photo_state", ('360 拍照状态', None, None, None, 'mdi:camera', '影像')),
    _mk("svm_filekey", ('360 拍照信息', None, None, None, 'mdi:image', '影像')),
    # ---- 信息 ----
    _mk("config_code", ('车辆配置', None, None, None, 'mdi:car-cog', '信息')),
    _mk("hu_diag", ('车机诊断', None, None, None, 'mdi:stethoscope', '信息')),
    # ---- 设置 ----
    _mk("privacy_pos_service", ('位置服务', None, None, None, 'mdi:map-marker-radius', '设置')),
    _mk("scene_mode", ('场景模式', None, None, None, 'mdi:palette', '设置')),
    # ---- 电池 ----
    _mk("battery_keep_warm", ('电池预热', None, None, None, 'mdi:fire', '电池')),
    # ---- 泊车 ----
    _mk("park_status", ('泊车状态', None, None, None, 'mdi:parking', '泊车')),
    _mk("park_fsd_progress", ('泊车启动进度', None, None, None, 'mdi:progress-clock', '泊车')),
)


# vehicleInfo 中适合展示为属性的字段
_VEHICLE_INFO_ATTRS = (
    ("carSeries", "车系"), ("spu", "车型"), ("plateNumber", "车牌"),
    ("vehicleNickname", "昵称"), ("color", "颜色"), ("seat", "座椅"),
    ("wheelName", "轮毂"), ("interiorName", "内饰"), ("deviceId", "车机设备号"),
    ("materialNumber", "物料号"), ("modelNo", "型号"), ("variableModel", "配置"),
    ("isSupportBle", "支持蓝牙钥匙"), ("usageType", "用途类型"),
)


# ---------- 车型功能过滤 ----------
# ★ 2026-09-28：映射表与 feature_of 已提升到 features.py，供 sensor /
#   binary_sensor 两个平台共用（此前只在 sensor 生效，导致 binary_sensor
#   完全没有功能门控 —— L6 无前备箱却生成了前备箱二元传感器）。
from .features import feature_of as _feature_of  # noqa: E402


# ---------------------------------------------------------------------------
# 任务大师（2026-10-07，HTTP /ssp-task-master-service 抓包实证）
# ---------------------------------------------------------------------------

def _task_summary(task_value: dict) -> str:
    """taskValue → 一行摘要："当 已连接 且 … → 打开…"。

    paramDescs（列表响应）/ paramsDescs（save 请求体）两种拼写都兼容；
    无描述时回退 conditionType / actionType。
    """
    def _one(item: dict) -> str:
        descs = item.get("paramDescs") or item.get("paramsDescs")
        if descs:
            return "/".join(str(d) for d in descs)
        return str(item.get("conditionType") or item.get("actionType") or "?")

    conds = task_value.get("conditions") or []
    acts = task_value.get("actions") or []
    c = " 且 ".join(_one(x) for x in conds) or "（无条件）"
    a = "；".join(_one(x) for x in acts) or "（无动作）"
    return f"当{c} → {a}"


class LiTaskMasterSensor(CoordinatorEntity, SensorEntity):
    """任务大师列表汇总（state=任务总数，属性含每个任务的启停与摘要）。"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._attr_name = "任务大师"
        self._attr_icon = "mdi:clipboard-list"
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_task_master"
        self._attr_device_info = device_info

    def _tasks(self) -> list[dict]:
        t = (self.coordinator.data or {}).get("tasks")
        return t if isinstance(t, list) else []

    @property
    def native_value(self):
        return len(self._tasks())

    @property
    def extra_state_attributes(self) -> dict:
        tasks = self._tasks()
        items = [
            {
                "configId": t.get("configId"),
                "name": t.get("configName"),
                "enabled": bool(t.get("enabled")),
                "automate": bool(t.get("automate")),
                "summary": _task_summary(t.get("taskValue") or {}),
            }
            for t in tasks
        ]
        return {
            "任务数": len(tasks),
            "启用数": sum(1 for t in items if t["enabled"]),
            "任务": items,
            # ★ 拉取失败时这里会显示具体错误（HTTP 状态/服务端响应），
            #   成功后自动消失 —— 排查"任务数=0"先看这个属性
            "拉取错误": (self.coordinator.data or {}).get("task_error") or "无",
        }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器，并注册"理想L6"设备."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    vin = config_entry.data.get(CONF_VIN) or ""

    identifiers = {(DOMAIN, vin)} if vin else {(DOMAIN, config_entry.entry_id)}
    # ★ 2026-09-26：设备名统一由 build_device_info 生成（取自服务端，
    #   不再硬编码 "理想 L6"；L8/L9/MEGA 用户会看到自己的车型名）
    _d = hass.data[DOMAIN][config_entry.entry_id]
    device_info = build_device_info(
        coordinator, config_entry, _d.get("li_api"),
        ability=_d.get("ability"),
    )
    # 同步创建/更新设备注册项（用同一个 device_info，避免出现两个设备名）
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers=identifiers,
        name=device_info["name"],
        manufacturer=device_info["manufacturer"],
        model=device_info["model"],
        serial_number=vin or None,
    )

    # ★ 2026-09-24 接入 signals.py（架构方案 2.4）
    #   描述表改由 SIGNALS 生成 —— 新增信号只需在 signals.py 加一行。
    #
    #   等价性：已验证 signals.py 的 78 个 sensor 与旧 _mk 表
    #          在 name/icon/category/diagnostic 上完全一致
    #          （见 tests/test_signals.py::TestDescriptionEquivalence）
    # ★ 2026-09-28：改由 SignalSpec 自己的 requires/universal 声明判定
    #   （见 signals.SignalSpec 与 features.resolve_requirement）。
    #   旧的 FEATURE_BY_KEY_PREFIX 前缀表已不再用于此路径 ——
    #   它漏登记了 135/156，导致纯电车型拿到增程才有的实体。
    features = (hass.data[DOMAIN][config_entry.entry_id].get("features") or {})
    ability = hass.data[DOMAIN][config_entry.entry_id].get("ability")
    from .features import filter_specs
    from .signals import specs_for, to_sensor_description
    pairs = [(to_sensor_description(s), s) for s in specs_for("sensor")]
    keep, skipped = filter_specs(pairs, features, ability)
    if skipped:
        _LOGGER.info("车型不支持, 跳过传感器 %d 个: %s", len(skipped), skipped[:8])

    entities = [
        LiCarSensor(coordinator, desc, device_info, vin) for desc, _ in keep
    ]
    # ★ 任务大师列表汇总（2026-10-07）—— 有密码登录（li_api）才创建
    if hass.data[DOMAIN][config_entry.entry_id].get("li_api") is not None:
        entities.append(LiTaskMasterSensor(coordinator, device_info, vin))
    async_add_entities(entities)


def _vehicle_info(data: dict) -> dict:
    """从 coordinator.data 提取 vehicleInfo 字典."""
    basics = data.get("basics")
    if isinstance(basics, dict):
        vi = basics.get("vehicleInfo")
        if isinstance(vi, dict):
            return vi
    vehicles = data.get("vehicles") or []
    if vehicles and isinstance(vehicles[0], dict):
        vi = vehicles[0].get("vehicleInfo")
        if isinstance(vi, dict):
            return vi
    return {}


def _signal_age(ts: str | None) -> str | None:
    """把上报时间戳转成可读的年龄字符串（如 "5 分钟前" / "3 天前"）。

    ★ 2026-09-23：用于 extra_state_attributes —— 让用户能判断数据是否新鲜，
      而不改变实体状态（避免"实体突然变 unknown"的负面体验）。

    ts 格式："2026-09-23 20:15:32"（VSS 的 tsFormat）
    返回 None 表示 ts 无效（空/0/无法解析）。
    """
    if not ts:
        return None
    t = str(ts).strip()
    if t in ("", "0"):
        return None
    try:
        dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
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



class LiCarSensor(CoordinatorEntity, RestoreSensor):
    """理想车传感器 (在线状态 + 实时信号)"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_{description.key}"
        self._attr_device_info = device_info
        # ★ 断连保留最后有效值（借自 huawei-auto-cloud 的 sticky 设计）
        self._last_value: Any = None
        self._last_ts: str | None = None

    def _vss(self) -> dict | None:
        """当前 key 的 VSS 信号 {"value":..,"ts":..}, 无数据返回 None."""
        return (self.coordinator.data or {}).get("vss", {}).get(
            self.entity_description.key)

    def _compute_value(self):
        """计算实体值（★ 2026-09-23 已抽到 rendering.render_value，便于单测）。

        这里只负责取数，渲染逻辑全在 rendering.py（纯函数）。
        """
        from .rendering import render_value

        key = self.entity_description.key
        data = self.coordinator.data or {}
        sig = self._vss()
        val = sig.get("value") if isinstance(sig, dict) else None
        return render_value(key, val, sig, data)

    @property
    def native_value(self):
        """★ sticky 包装：优先当前值，无值时回退上次有效值。

        借自 huawei-auto-cloud 的 sticky 设计：
        车辆离线/信号缺失时保留最后一帧有效数据，
        避免 HA 界面出现大片 unknown。
        """
        v = self._compute_value()
        # ★ 数值型实体不能返回字符串（HA 会报 int()/float() 转换失败）
        #   因此把 STATE_UNKNOWN 哨兵统一转成 None
        if v == STATE_UNKNOWN or v == "unknown":
            v = None
        # ★ 2026-09-23 信号新鲜度（ROADMAP P1）：
        #   VSS 的 ts 能反映信号是否真的在上报：
        #     ts == "0"  → 从未上报（硬件不存在，如 L6 无冰箱）
        #     无 ts      → 同 ts==0
        #   → 这类实体的值即使非 None 也无意义（多为默认 0），
        #     标为 unavailable 而不是显示误导性的 0。
        #
        #   ⚠️ 保守策略：只处理 ts=="0"（确定的"从未上报"）。
        #      ts 陈旧但仍有效的信号（如 config_code 两年没变）
        #      不做判定 —— 那些值是真有效的，只是不常变。
        #      陈旧程度通过 extra_state_attributes 的「上报时间」暴露。
        # ★ 2026-09-29：数据驱动的「车型不支持」门控。
        #   协调器会统计「本批整体有数据、但该 key 连续 N 轮缺席」的信号，
        #   判定为该车型不上报 → 这里直接返回 None（HA 显示 unavailable），
        #   而不是显示一个容易误导的 unknown。
        #   实测场景：Vehicle.Cabin.CLTC.EnduranceMil（总续航）在 L6 上
        #   连续 112 轮缺席，而 App 在别的车型上会显示它。
        if self.entity_description.key in (
                (self.coordinator.data or {}).get("unsupported_keys") or set()):
            return None

        sig_now = self._vss()
        if sig_now is not None:
            ts = str(sig_now.get("ts") or "").strip()
            if ts in ("", "0"):
                # 从未上报：只有历史有效值时才回退（否则 unavailable）
                if self._last_value is None:
                    return None
        else:
            # ★ 2026-09-24 修复：非 VSS 信号（如 online_status）跳过此判定
            #   它的 _vss() 恒为 None → ts="" → 会被误判为"从未上报"
            #   → 永远显示 unknown（实测踩坑：在线状态一直 unknown）
            ts = ""

        if v is not None:
            self._last_value = v
            self._last_ts = ts
            return v
        # 无新值 → 回退最后有效值
        if self._last_value is not None:
            return self._last_value
        # ★ 无历史值：数值类实体返回 None（HA 显示 unknown）
        #   不能返回字符串 "unknown"，否则会被 HA 校验拒绝
        return None

    @property
    def available(self) -> bool:
        """★ 2026-09-29：把「该车型不上报这个信号」正确表达为 unavailable。

        修复一个语义 bug：原代码在「从未上报」时 `return None`，
        而 HA 把 None 显示为 **unknown** —— 注释却写着 unavailable。
        两者对用户含义完全不同：
            unknown     = 暂时没拿到（可能稍后就有）
            unavailable = 这个实体在此车上不存在/不可用

        实测案例：Vehicle.Cabin.CLTC.EnduranceMil（总续航）在 L6 上
        路径有效但【ts 恒为空】(服务端接受却从不上报)，
        原行为让用户看到一个永远 unknown 的实体。

        判定依据（两种都算「该车型不上报」）：
          ① 协调器的数据驱动门控：连续 N 轮不在响应里 → unsupported_keys
          ② 服务端返回了该路径但 ts 为空/0（从未上报）
        """
        if not super().available:
            return False
        key = self.entity_description.key
        data = self.coordinator.data or {}

        # ① 数据驱动门控判定为「该车型不支持」
        if key in (data.get("unsupported_keys") or set()):
            return False

        # ② 服务端返回了路径但从未上报（ts 为空/0）
        sig = self._vss()
        if sig is not None:
            ts = str(sig.get("ts") or "").strip()
            if ts in ("", "0") and self._last_value is None:
                return False

        return True

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        # ★ 2026-10-02：暴露「车型 + 能力」，供前端卡片按车型适配
        #   数据源：coordinator 探测到的 features（运行时真实能力，非静态表）
        try:
            from homeassistant.helpers import device_registry as _dr  # noqa: PLC0415

            _entry = self.coordinator.config_entry if hasattr(self.coordinator, "config_entry") else None
            _store = (self.hass.data.get(DOMAIN) or {})
            _d = _store.get(_entry.entry_id if _entry else "", {}) or {}
            # 车型名：优先本实体的设备（device_registry），其次 VSS 车辆信息
            _mdl = ""
            try:
                _dev = _dr.async_get(self.hass).async_get(
                    self.registry_entry.device_id
                ) if getattr(self, "registry_entry", None) else None
                if _dev is not None:
                    _mdl = _dev.model or _dev.name or ""
            except Exception:  # noqa: BLE001
                pass
            if not _mdl:
                _vi2 = _vehicle_info(self.coordinator.data or {})
                _mdl = (_vi2.get("车型") or _vi2.get("modelName")
                        or _vi2.get("model") or "")
            if _mdl:
                attrs["车型"] = _mdl
                # 车系代号（L6/L7/L8/L9/MEGA/i8）—— 前端据此适配布局
                import re as _re  # noqa: PLC0415
                _m = _re.search(r"(MEGA|L[6-9]|i[6-9]|ONE)", str(_mdl), _re.I)
                if _m:
                    attrs["车系"] = _m.group(1).upper()
            # 能力（coordinator 探测到的真实能力）
            _caps = _d.get("features") or {}
            if _caps:
                _b = {k: bool(v) for k, v in _caps.items()
                      if isinstance(v, (bool, int))}
                if _b:
                    attrs["车型能力"] = _b
        except Exception:  # noqa: BLE001
            pass
        vi = _vehicle_info(self.coordinator.data or {})
        for key, label in _VEHICLE_INFO_ATTRS:
            if key in vi and vi[key] not in (None, ""):
                attrs[label] = vi[key]
        sig = self._vss()
        if sig:
            ts = sig.get("ts")
            attrs["上报时间"] = ts
            # ★ 2026-09-23：暴露信号年龄（便于判断数据是否新鲜）
            age = _signal_age(ts)
            if age is not None:
                attrs["数据年龄"] = age
        polled = (self.coordinator.data or {}).get("vss_polled_at")
        if polled:
            attrs["轮询时间"] = polled
        key = self.entity_description.key
        if key == "location":
            loc_sig = (self.coordinator.data or {}).get("vss", {}).get("location")
            if loc_sig and isinstance(loc_sig.get("value"), str):
                try:
                    loc = json.loads(loc_sig["value"])
                    attrs.update({
                        "纬度": loc.get("lat"), "经度": loc.get("lon"),
                        "海拔": loc.get("alt"), "朝向": loc.get("dir"),
                        "速度": loc.get("spd"), "GPS时间": loc.get("utc"),
                    })
                except (ValueError, TypeError):
                    pass
        elif key in ("ota_state", "ota_status"):
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    for k2, label in (("currentVersion", "当前版本"), ("displayTargetVersion", "目标版本"),
                                      ("errorType", "错误类型"), ("status", "状态"),
                                      ("progress", "进度"), ("remainingSeconds", "剩余秒数"),
                                      ("addInfo", "附加信息")):
                        if o.get(k2) not in (None, ""):
                            attrs[label] = o[k2]
                except (ValueError, TypeError):
                    pass
        elif key in ("maint_acfilter", "maint_coolfuild", "maint_engine_oil",
                     "maint_brake_oil", "maint_sparkplug"):
            # ★ 2026-10-03：字段名按抓包实测重写。
            #
            #   此前查的是 higherLevel / lowerLevel / percentage / remainMileage
            #   —— 实测这 4 个字段【在服务端返回的 JSON 里根本不存在】，
            #   所以那几个属性一直是空的，只有状态文本「剩余 N km」能用
            #   （那是 render_value 正则从文本里提的，不是结构化数据）。
            #
            #   依据：vss_full_state.json 里 Vehicle.Carcenter.Maintain.*
            #        每个保养项返回 33 个字段，含：
            #          maintainLeftMileage / maintainLeftDays / maintainDueDate
            #          maintenanceValid / periodMileage / periodMonth
            #          mileageSource / engineMileage / mileage …
            #
            #   字段含义（对照 App 保养页）：
            #     maintainLeftMileage  剩余里程（km）—— App 主显示
            #     maintainLeftDays     剩余天数（**毫秒**，需换算）
            #     maintainDueDate      到期日 YYYYMMDD（"--" 表示无）
            #     maintenanceValid     1=显示 / 0=隐藏（如"增程器大保养"）
            #     periodMileage/Month  保养周期（里程 / 月数）
            #     mileageSource        计程来源 engine=增程器里程, total=总里程
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    attrs.update(_maint_attrs(o))
                except (ValueError, TypeError):
                    pass
        elif key == "trip_total":
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    for k2, label in (("accMileage", "辅助驾驶里程"), ("adMileage", "总里程"),
                                      ("totalMileage", "累计里程"), ("tripMileage", "本次里程")):
                        if o.get(k2) not in (None, ""):
                            attrs[label] = o[k2]
                except (ValueError, TypeError):
                    pass
        elif key == "sentry":
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    attrs["哨兵主状态"] = o.get("sentinelStatus")
                    attrs["哨兵子状态"] = o.get("sentinelSubStatus")
                except (ValueError, TypeError):
                    pass
        elif key == "battery_keep_warm":
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    attrs["开始时间"] = o.get("startTime")
                    attrs["结束时间"] = o.get("endTime")
                except (ValueError, TypeError):
                    pass
        elif key == "config_code":
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    for k2, label in (("autopilot", "辅助驾驶"), ("configLevel", "配置等级"),
                                      ("electricPackage", "电动包"), ("carSeries", "车系")):
                        if o.get(k2) not in (None, ""):
                            attrs[label] = o[k2]
                except (ValueError, TypeError):
                    pass
        elif key == "svm_filekey":
            sig2 = self._vss()
            if sig2 and isinstance(sig2.get("value"), str):
                try:
                    o = json.loads(sig2["value"])
                    for k2, label in (("picProduct", "图片类型"), ("picTime", "拍照时间")):
                        if o.get(k2) not in (None, ""):
                            attrs[label] = o[k2]
                except (ValueError, TypeError):
                    pass
        return attrs
