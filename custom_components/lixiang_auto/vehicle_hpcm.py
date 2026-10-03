"""整车配置表（`Vehicle.HU.Diag.Hpcm`）解析 —— 2026-09-27 新增

★ 来源
----
App 的 `LXLiMeshStateDelegate.getHmiPlatform()`：
    raw = cache.getString(vin, "Vehicle.HU.Diag.Hpcm")
    map = LXJsonUtil.fromJson(raw, Map<String,String>)
    hmiPlatform = map.get("hmi_platform") ?: "0"

这是一个 **120+ 字段的整车配置 JSON**，比车型能力表（`vehicle_configs/*.json`）
更【精确到具体车辆】—— 因为同款车型选装不同，配置也不同。

★ 用途
----
1. **精确功能判断**：`hc_frunk`（前备箱）、`hc_car_refrigeratory`（冰箱）等
2. **协议版本判断**：`hmi_platform`（"1" → SS4，其他 → SS3）
3. **硬件规格**：`hc_hud_size`、`speaker_options`、`hc_front_camera` 等

★ 用法
----
    hpcm = parse_hpcm(coordinator)
    if hpcm.has("hc_frunk"):
        ...创建前备箱实体...

    if hpcm.is_ss4():
        ...用 SS4 协议...
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .const import LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)

#: VSS 信号路径
HPCM_PATH = "Vehicle.HU.Diag.Hpcm"

#: ★ 表示"有该硬件"的字段（值为非 "0" / 非空）
#: 来源：实测 L6 Pro 的 Hpcm 数据 + App 代码交叉验证
FEATURE_FIELDS: dict[str, str] = {
    # 车身硬件
    "hc_frunk": "前备箱",
    "soft_close_frunk": "电吸前备箱",
    "hc_car_refrigeratory": "冰箱",
    "hc_rear_display_screen": "后排屏",
    "hc_empress_seat": "皇后座",
    "hc_swivel_seats": "旋转座椅",
    "hc_automatic_door": "电动门",
    "hc_psd": "电动侧门",
    "hc_soft_close_automatic_door": "电吸门",
    "hc_sunroof_sunshade": "遮阳帘",
    "hc_220V_outlet": "220V 插座",
    "hc_tow_hitch": "拖车钩",
    # 座椅
    "hc_rear_seat_ven": "二排通风",
    "hc_rear_l_seat_leg_rest": "二排左腿托",
    "hc_rear_r_seat_leg_rest": "二排右腿托",
    "hc_seat_boss_key": "老板键",
    "hc_reading_light_3rd_seats": "三排阅读灯",
    "hc_rear_seat_back_folding": "二排靠背折叠",
    # 智驾/感知
    "hc_lidar": "激光雷达",
    "hc_dms_camera": "DMS 摄像头",
    "hc_front_camera": "前视摄像头",
    "hc_rear_camera": "后视摄像头",
    "hc_hud_size": "HUD",
    # 舒适
    "hc_multi_zone_ac": "多区空调",
    "hc_rear_ac_panel": "后排空调面板",
    "hc_front_wireless_charging": "前排无线充",
    "hc_rear_wireless_charging": "后排无线充",
    "fragrance_system": "香氛",
    "hc_touchbar": "触控条",
    "hc_co2_sensor": "CO₂ 传感器",
    # 底盘
    "rear_steering": "后轮转向",
    "cdc_solenoid_valve": "CDC 减振",
}


class VehicleHpcm:
    """整车配置表（解析后的便捷访问器）。"""

    def __init__(self, raw: dict[str, Any] | None = None,
                 parse_ok: bool = False) -> None:
        self._raw: dict[str, Any] = raw or {}
        #: 是否成功解析到（用于判断"不支持" vs "未获取"）
        self.available = parse_ok

    # ---- 原始访问 ----

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    @property
    def raw(self) -> dict[str, Any]:
        return dict(self._raw)

    def __bool__(self) -> bool:
        return bool(self._raw)

    # ---- 功能判断 ----

    def has(self, field: str) -> bool:
        """★ 是否有该硬件（值为非 "0" / 非空字符串）。"""
        if not self.available:
            return False
        v = self._raw.get(field)
        if v is None:
            return False
        return str(v) not in ("", "0")

    def value_of(self, feature_name: str) -> Any:
        """按【中文功能名】取值（如 "前备箱"）。"""
        for field, name in FEATURE_FIELDS.items():
            if name == feature_name:
                return self._raw.get(field)
        return None

    def supported_features(self) -> list[str]:
        """全部支持的硬件（中文名列表）。"""
        return [name for field, name in FEATURE_FIELDS.items()
                if self.has(field)]

    def unsupported_features(self) -> list[str]:
        """明确不支持（字段存在但值为 0）。"""
        if not self.available:
            return []
        return [name for field, name in FEATURE_FIELDS.items()
                if field in self._raw and not self.has(field)]

    # ---- 协议版本 ----

    @property
    def hmi_platform(self) -> str:
        """★ HMI 平台代号。

        ★★ 关键：App 的 SS3/SS4 判定就是比较它！
            hmi_platform == "1"  → SS4（需要服务证书签名）
            其他                  → SS3（只需 IDaaS token）
        """
        return str(self._raw.get("hmi_platform") or "0")

    def is_ss4(self) -> bool:
        """是否走 SS4 安全协议（= App 的 shouldUseSS4）。"""
        return self.hmi_platform == "1"

    @property
    def eea(self) -> str:
        """电子电气架构版本（如 "2.0"）。"""
        return str(self._raw.get("eea") or "")

    @property
    def car_of_year(self) -> str:
        """年款代码。"""
        return str(self._raw.get("hc_year") or self._raw.get("car_of_year") or "")

    # ---- 诊断 ----

    def dump(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "hmi_platform": self.hmi_platform,
            "is_ss4": self.is_ss4(),
            "eea": self.eea,
            "car_of_year": self.car_of_year,
            "supported": self.supported_features(),
            "unsupported": self.unsupported_features(),
            "raw": self._raw,
        }


def parse_hpcm_value(raw: Any) -> VehicleHpcm:
    """解析 Hpcm 的原始值（JSON 字符串 或 已解析的 dict）。"""
    if raw is None:
        return VehicleHpcm()
    if isinstance(raw, dict):
        return VehicleHpcm(raw, parse_ok=bool(raw))
    if not isinstance(raw, str) or not raw.strip():
        return VehicleHpcm()
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        _LOGGER.debug("Hpcm JSON 解析失败")
        return VehicleHpcm()
    if not isinstance(d, dict):
        return VehicleHpcm()
    return VehicleHpcm(d, parse_ok=True)


def get_hpcm(coordinator: Any) -> VehicleHpcm:
    """从 coordinator 的 VSS 缓存里取 Hpcm（供实体 setup 用）。"""
    try:
        vss = (coordinator.data or {}).get("vss") or {}
    except AttributeError:
        return VehicleHpcm()

    # 尝试多个可能的 key（VSS 路径 / 我们的信号 key）
    # ★ 优先用信号表里的 key（hu_diag），再试 VSS 原始路径
    for k in ("hu_diag", HPCM_PATH, "/" + HPCM_PATH, "hpcm"):
        sig = vss.get(k)
        if sig is None:
            continue
        val = sig.get("value") if isinstance(sig, dict) else sig
        hpcm = parse_hpcm_value(val)
        if hpcm:
            return hpcm
    return VehicleHpcm()
