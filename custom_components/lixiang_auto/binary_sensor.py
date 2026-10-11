"""Li Auto 二元传感器（车门/车窗/充电枪/连接/告警类）— 数据源 vss/get-batch."""

from __future__ import annotations

import json
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

# kind 决定值的语义:
#   lock   : 0=已锁, 非0=未锁   → on = 未落锁
#   door   : 0=关闭, 非0=打开   → on = 打开
#   plug   : AC==2 / DC==1 = 已插（App 实证）   → on = 已连接
#   conn   : False=断, True=连  → on = 已连接
#   warn   : 0=正常, 非0=告警   → on = 告警
#   heat   : 0=关, 非0=开       → on = 开启
#   json   : 从 JSON 字段判读
# ★ 2026-09-24 新增：字符串 → HA 枚举的映射
#   供 signals.to_binary_description() 使用（架构方案 2.5）
_DCLASS_BS: dict[str, BinarySensorDeviceClass] = {
    "LOCK": BinarySensorDeviceClass.LOCK,
    "DOOR": BinarySensorDeviceClass.DOOR,
    "PLUG": BinarySensorDeviceClass.PLUG,
    "CONNECTIVITY": BinarySensorDeviceClass.CONNECTIVITY,
    "PROBLEM": BinarySensorDeviceClass.PROBLEM,
    "MOTION": BinarySensorDeviceClass.MOTION,
    "WINDOW": BinarySensorDeviceClass.WINDOW,
    "OPENING": BinarySensorDeviceClass.OPENING,
    "BATTERY_CHARGING": BinarySensorDeviceClass.BATTERY_CHARGING,
    "RUNNING": BinarySensorDeviceClass.RUNNING,
    "SAFETY": BinarySensorDeviceClass.SAFETY,
    "SOUND": BinarySensorDeviceClass.SOUND,
    "VIBRATION": BinarySensorDeviceClass.VIBRATION,
}


BINARY_DESCRIPTIONS: tuple[tuple[BinarySensorEntityDescription, str], ...] = (
    # ---- 车门锁（on = 未落锁）----
    (BinarySensorEntityDescription(key="lock_main", name="主驾门锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    (BinarySensorEntityDescription(key="lock_copilot", name="副驾门锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    (BinarySensorEntityDescription(key="lock_back_left", name="左后门锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    (BinarySensorEntityDescription(key="lock_back_right", name="右后门锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    (BinarySensorEntityDescription(key="lock_trunk", name="后备箱锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    (BinarySensorEntityDescription(key="lock_front_trunk", name="前备箱锁",
        device_class=BinarySensorDeviceClass.LOCK, icon="mdi:car-door-lock"), "lock"),
    # ---- 车门开关（on = 打开）----
    (BinarySensorEntityDescription(key="door_main", name="主驾车门",
        device_class=BinarySensorDeviceClass.DOOR, icon="mdi:car-door"), "door"),
    (BinarySensorEntityDescription(key="door_copilot", name="副驾车门",
        device_class=BinarySensorDeviceClass.DOOR, icon="mdi:car-door"), "door"),
    (BinarySensorEntityDescription(key="door_back_left", name="左后车门",
        device_class=BinarySensorDeviceClass.DOOR, icon="mdi:car-door"), "door"),
    (BinarySensorEntityDescription(key="door_back_right", name="右后车门",
        device_class=BinarySensorDeviceClass.DOOR, icon="mdi:car-door"), "door"),
    (BinarySensorEntityDescription(key="door_trunk", name="后备箱门",
        device_class=BinarySensorDeviceClass.DOOR, icon="mdi:car-door"), "trunk"),
    (BinarySensorEntityDescription(key="charge_port_lid", name="充电口盖",
        icon="mdi:ev-plug-type2"), "charge_lid"),
    (BinarySensorEntityDescription(key="tank_lock", name="油箱盖",
        icon="mdi:gas-station"), "door"),
    # ---- 充电枪（on = 已连接）----
    (BinarySensorEntityDescription(key="charge_gun_ac", name="交流充电枪",
        device_class=BinarySensorDeviceClass.PLUG, icon="mdi:power-plug"), "plug"),
    (BinarySensorEntityDescription(key="charge_gun_dc", name="直流充电枪",
        device_class=BinarySensorDeviceClass.PLUG, icon="mdi:power-plug-outline"), "plug"),
    # ---- 连接（on = 已连接）----
    (BinarySensorEntityDescription(key="online_5g", name="5G 连接",
        device_class=BinarySensorDeviceClass.CONNECTIVITY, icon="mdi:signal-5g"), "conn"),
    (BinarySensorEntityDescription(key="online_xcu", name="XCU 连接",
        device_class=BinarySensorDeviceClass.CONNECTIVITY, icon="mdi:chip"), "conn"),
    (BinarySensorEntityDescription(key="online_huf", name="车机连接",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:car-connected"), "conn"),
    # ---- 充电/车辆状态（★ 2026-09-23 补充）----
    (BinarySensorEntityDescription(key="eves_flt_stop_chrg", name="故障停止充电",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle"), "warn"),
    (BinarySensorEntityDescription(key="battery_insulation", name="电池保温",
        icon="mdi:thermometer-plus"), "door"),
    (BinarySensorEntityDescription(key="case_cover", name="钥匙保护套",
        icon="mdi:key-variant"), "door"),
    (BinarySensorEntityDescription(key="dcdc_fault_level", name="DCDC 故障",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-octagon"), "warn"),
    # ---- 告警（on = 告警）----
    (BinarySensorEntityDescription(key="tire_fl_warning", name="胎压告警 左前",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:car-tire-alert"), "warn"),
    (BinarySensorEntityDescription(key="tire_fr_warning", name="胎压告警 右前",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:car-tire-alert"), "warn"),
    (BinarySensorEntityDescription(key="tire_rl_warning", name="胎压告警 左后",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:car-tire-alert"), "warn"),
    (BinarySensorEntityDescription(key="tire_rr_warning", name="胎压告警 右后",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:car-tire-alert"), "warn"),
    (BinarySensorEntityDescription(key="tpms_status", name="TPMS 系统告警",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:car-tire-alert"), "warn"),
    (BinarySensorEntityDescription(key="charge_fault", name="充电故障",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:alert-circle"), "warn"),
    (BinarySensorEntityDescription(key="fuel_low_warning", name="油量低告警",
        device_class=BinarySensorDeviceClass.PROBLEM, icon="mdi:gas-station-off"), "warn"),
    (BinarySensorEntityDescription(key="low_vol_flag", name="低压电源标志",
        icon="mdi:flag"), "warn"),
    # ---- 功能开关（on = 开启）----
    (BinarySensorEntityDescription(key="scheduled_charge_switch", name="预约充电",
        icon="mdi:calendar-clock"), "heat"),
    (BinarySensorEntityDescription(key="provision_auth", name="车辆授权",
        icon="mdi:key-chain-variant"), "conn"),
    # ---- JSON 字段判读 ----
    (BinarySensorEntityDescription(key="sentry", name="哨兵模式",
        icon="mdi:shield-car"), "json:sentinelStatus"),
    (BinarySensorEntityDescription(key="sentry_switch", name="哨兵开关",
        icon="mdi:shield-check"), "json:sentinelSwitch"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    vin = config_entry.data.get(CONF_VIN) or ""
    identifiers = {(DOMAIN, vin)} if vin else {(DOMAIN, config_entry.entry_id)}
    # ★ 名字全取自服务端（vehicleNickname / spu），不硬编码车型
    _d = hass.data[DOMAIN][config_entry.entry_id]
    device_info = build_device_info(
        coordinator, config_entry, _d.get("li_api"),
        ability=_d.get("ability"),
    )
    if vin:
        device_info["serial_number"] = vin
    # ★ 2026-09-24 接入 signals.py（架构方案 2.5）
    # ★ 2026-09-28 补上【车型功能门控】——此前 binary_sensor 完全没有过滤：
    #     L6（Hpcm hc_frunk=0，无前备箱）上依然创建了
    #       binary_sensor.…_qian_bei_xiang_men / …_qian_bei_xiang_suo
    #     原因：FEATURE_BY_KEY_PREFIX 当时只定义在 sensor.py，
    #           只在 sensor 平台生效。现改为两平台共用 features.py 的表。
    # ★ 2026-09-28：统一由 SignalSpec 的 requires/universal 判定
    from .features import filter_specs
    from .signals import specs_for, to_binary_description
    features = (hass.data[DOMAIN][config_entry.entry_id].get("features") or {})
    ability = hass.data[DOMAIN][config_entry.entry_id].get("ability")
    pairs = [(to_binary_description(s), s) for s in specs_for("binary_sensor")]
    keep, skipped = filter_specs(pairs, features, ability)
    if skipped:
        _LOGGER.info("车型不支持, 跳过二元传感器 %d 个: %s",
                     len(skipped), skipped[:8])
    async_add_entities(
        LiCarBinarySensor(coordinator, desc, spec, vin, device_info)
        for desc, spec in keep
    )


class LiCarBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """理想车二元传感器（值来自 coordinator.data["vss"]）"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description, spec, vin: str,
                 device_info=None) -> None:
        """★ 2026-09-24（架构方案 2.5）：第三个参数从 kind 字符串改为 SignalSpec。

        kind 字符串分派（`if kind == "lock"` ...）已改为
        spec.semantics 枚举分派，语义更明确、可单测。
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._rid = route_id_of_vin(vin)
        self._spec = spec

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_{description.key}"
        if device_info is not None:
            self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """根据 spec.semantics 判定开关状态（★ 架构方案 2.5）。

        原实现用 kind 字符串分派（`if kind == "lock"` ...），
        现改为 Semantics 枚举 —— 语义在 signals.py 里声明，可单测。

        语义对照（详见 signals.Semantics 与各分支注释）：
          LOCKED     0=已落锁 → on=未落锁
          DOOR_OPEN  ==1 才开（XDoorDataHandle.smali:310）
          TRUNK      锁优先聚合（LXLiMeshStateDelegate.getTrunkState）
          PLUGGED    AC==2 / DC==1 才算已插入（App 四处反汇编实证，非「非0」）
          CHARGE_LID -1=无效(unknown)，0=关，非0=开
          CONNECTED  非0 = 已连接
          ALARM      非0 = 告警
          SWITCH_ON  非0 = 开启
        """
        from .signals import Semantics

        sig = (self.coordinator.data or {}).get("vss", {}).get(
            self.entity_description.key)
        if sig is None or sig.get("value") is None:
            return None
        val = sig.get("value")
        sem = getattr(self._spec, "semantics", Semantics.RAW)

        # JSON 字段（原 "json:xxx" 编码）
        if sem == Semantics.JSON_FIELD:
            field = getattr(self._spec, "json_field", "") or ""
            try:
                obj = json.loads(val) if isinstance(val, str) else val
                return int(obj.get(field, 0)) != 0
            except (TypeError, ValueError, AttributeError):
                return None

        # 布尔直读
        if isinstance(val, bool):
            return val

        try:
            n = int(val)
        except (TypeError, ValueError):
            try:
                return bool(val)
            except Exception:  # noqa: BLE001
                return None

        if sem == Semantics.LOCKED:
            return n != 0                     # 0=已落锁 → on=未落锁

        if sem == Semantics.DOOR_OPEN:
            # ★ 从 App 源码还原（XDoorDataHandle）：
            #     int v = toInt(doorValue);
            #     boolean open = (v == 1);      // 只有 1 → true
            #   ⚠️ 旧实现用 `n != 0` 会把尾门的 2 误判成「打开」。
            return n == 1

        if sem == Semantics.TRUNK:
            # ★ 尾门聚合（复刻 LXLiMeshStateDelegate.getTrunkState()
            #   smali:37730-37930）：
            #     if (lockVal != null) return convertAnyToInt(lockVal) == 0 ? 0 : 1;
            #     int v = convertAnyToInt(switchVal);
            #     return (v == 2 || v == 0 || v == 3) ? 0 : 1;
            lock_sig = (self.coordinator.data or {}).get("vss", {}).get(
                self.entity_description.key.replace("door_trunk", "lock_trunk"))
            if lock_sig and lock_sig.get("value") is not None:
                try:
                    return int(lock_sig["value"]) != 0
                except (TypeError, ValueError):
                    pass
            return n != 0 if n in (0, 1) else (n == 1)

        if sem == Semantics.PLUGGED:
            # ★ 2026-10-11 androguard 反汇编实证（LXLiMeshStateDelegate 四处一致：
            #   getChargeCurrent / getChargeVoltage / getChargingMode / getChargingStatus）：
            #     ACChgrActualConnSts == 2 → 交流枪已插
            #     DCChrgngGunActuSts  == 1 → 直流枪已插
            #   （XChargeDataHandle.smali:102 亦为 AC == 2）
            #   ⚠️ 旧规则 `n != 0` 会把 AC=1 / DC=2 等非插枪态误判为已插入
            #     —— 用户实测：未插枪却显示已插（2026-10-11 报告）
            key = self.entity_description.key
            if key == "charge_gun_dc":
                return n == 1
            if key == "charge_gun_ac":
                return n == 2
            return n != 0

        if sem == Semantics.CHARGE_LID:
            # ★ ChrgPorLidStsV2 用 -1 作【无效哨兵】
            #   （LXLiMeshStateDelegate.getChrgPorLidSts() smali:11921）
            if n == -1:
                return None
            return n != 0

        # CONNECTED / ALARM / SWITCH_ON / RAW 等：非 0 即真
        return n != 0
