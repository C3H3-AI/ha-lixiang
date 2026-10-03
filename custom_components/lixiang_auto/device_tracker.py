"""Li Auto 车辆位置 device_tracker — 数据源 VSS Vehicle.Location.CurrentLocationInfo.

位置为 WGS84 坐标 (车机 GPS 原始坐标, 未经国测局偏移); GPS 无效 (v=false) 时
实体置 unknown.
"""

from __future__ import annotations

import json
import logging

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin

_LOGGER = logging.getLogger(LOGGER_NAME)

# ---------- 漂移防护配置 ----------
# 服务端不提供 sat/hdop，无法判断精度，因此默认【关闭】跳变过滤。
# 若你的车常在地下车库等弱信号环境，出现明显漂移，可改为 True。
DRIFT_GUARD = False
MAX_JUMP_M = 500.0        # 单次跳变超过此距离(m)视为异常


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """两点球面距离（米）。"""
    import math
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(h))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    vin = config_entry.data.get(CONF_VIN) or ""
    async_add_entities([LiCarTracker(coordinator, vin)])


class LiCarTracker(CoordinatorEntity, TrackerEntity):
    """理想 L6 位置追踪"""

    _attr_has_entity_name = True
    _attr_name = "车辆位置"
    _attr_icon = "mdi:navigation-variant"

    def __init__(self, coordinator, vin: str) -> None:
        super().__init__(coordinator)
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_location"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, vin or "default")},
        }
        self._last_ll: tuple[float, float] | None = None
        self._invalid_count = 0

    def _loc(self) -> dict | None:
        """解析 VSS 定位数据。

        ★ 数据质量说明（2026-09-23 实测）
        ----------------------------------
        服务端返回的 JSON:
            {"alt":32.0, "dir":85.4, "hdop":0, "lat":28.014, "lon":120.678,
             "sat":0, "spd":0.0, "utc":..., "v":true}

        质量字段:
          · v    有效性标志（true/false）★ 主要判据
          · sat  卫星数（服务端恒为 0，不上报）
          · hdop 水平精度因子（服务端恒为 0，不上报）

        因此无法判断实时精度，只能靠 v 字段。
        GPS 丢失（地下车库/隧道）时服务端应返回 v=false → 我们显示 unknown。

        ★ 漂移防护（DRIFT_GUARD）
        --------------------------
        可选：丢弃与上一位置距离突变过大的点（默认关闭）。
        原因：本车数据实测坐标稳定（车停 20 分钟坐标一致），
              且服务端已做有效性过滤，额外过滤可能误伤正常跳变。
              如需开启，把 DRIFT_GUARD 设为 True 并调 MAX_JUMP_M。
        """
        sig = (self.coordinator.data or {}).get("vss", {}).get("location")
        if not sig or not isinstance(sig.get("value"), str):
            return None
        try:
            loc = json.loads(sig["value"])
        except ValueError:
            return None
        # ① 有效性检查（主要防护）
        if not loc.get("v") or loc.get("lat") is None or loc.get("lon") is None:
            _LOGGER.debug("定位无效 (v=%s)", loc.get("v"))
            self._invalid_count += 1
            return None
        # ② 坐标合法性
        lat, lon = float(loc["lat"]), float(loc["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            _LOGGER.warning("定位坐标越界: %s,%s", lat, lon)
            return None
        # ③ 可选：漂移过滤
        if DRIFT_GUARD and self._last_ll:
            if _haversine_m(self._last_ll, (lat, lon)) > MAX_JUMP_M:
                _LOGGER.warning(
                    "定位跳变过大 (>%dm)，可能漂移，本次忽略: %s,%s",
                    MAX_JUMP_M, lat, lon)
                return None
        self._last_ll = (lat, lon)
        self._invalid_count = 0
        return loc

    @property
    def source_type(self) -> str:
        return "gps"

    @property
    def latitude(self) -> float | None:
        loc = self._loc()
        return loc.get("lat") if loc else None

    @property
    def longitude(self) -> float | None:
        loc = self._loc()
        return loc.get("lon") if loc else None

    @property
    def extra_state_attributes(self) -> dict:
        loc = self._loc()
        if not loc:
            return {}
        sig = (self.coordinator.data or {}).get("vss", {}).get("location") or {}
        return {
            "海拔": loc.get("alt"),
            "朝向": loc.get("dir"),
            "速度": loc.get("spd"),
            "卫星数": loc.get("sat"),      # 服务端恒为 0（不上报）
            "GPS时间": loc.get("utc"),
            "上报时间": sig.get("ts"),
            "定位有效": loc.get("v"),
            "连续无效次数": self._invalid_count,
            "漂移过滤": "已开启" if DRIFT_GUARD else "未开启",
        }
