"""实体共用工具（route_id 解析、设备信息、控制开关）

★ 2026-09-23 重构：合并原先散落的 3 套 route_id 实现
  （route_id_of / route_id_of_vin，以及已删除的旧 derive_route_id 变体）
  统一到这里，避免「改一处忘一处 → unique_id 分裂」。

算法（必须保持不变，否则现有实体的 unique_id 会变）：
  · 有 VIN      → "v" + sha256(vin)[:12]        例: v7162cef49ddb
  · 有多车列表   → 取列表中第一辆的 route_id
  · 无 VIN      → "e" + sha256(entry_id:0)[:12]
  · 都没有       → "default"

⚠️ 修改 route_id 算法会破坏所有已注册实体，务必谨慎。
"""

from __future__ import annotations

import hashlib
from typing import Any

from .const import CONF_VIN, DOMAIN


def route_id_of_vin(vin: str | None) -> str:
    """从 VIN 派生 route_id（各平台实体 __init__ 里统一调用）。

    用法：
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_{description.key}"
    """
    v = str(vin or "")
    if v:
        return "v" + hashlib.sha256(v.encode()).hexdigest()[:12]
    return "default"


def route_id_of(entry: Any = None, config_entry: Any = None) -> str:
    """从 ConfigEntry 取 route_id（多车时取该 entry 对应车辆的）。

    优先级：
      ① data['routes'] 是列表（多车，新格式）→ 取第一辆的 route_id
      ② data['vin'] 存在（单车）→ 用 VIN 派生
      ③ 都没有 → 用 entry_id 派生（保持历史输出格式一致，勿改）
    """
    e = config_entry or entry
    if e is None:
        return "default"

    data = getattr(e, "data", None) or {}

    # ① 多车列表
    raw = data.get("routes")
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        rid = raw[0].get("route_id")
        if rid:
            return str(rid)

    # ② 单车：VIN
    vin = str(data.get(CONF_VIN) or "")
    if vin:
        return "v" + hashlib.sha256(vin.encode()).hexdigest()[:12]

    # ③ 回退：entry_id（保持历史输出格式一致，勿改）
    eid = str(getattr(e, "entry_id", "") or data.get("entry_id") or "")
    if eid:
        return "e" + hashlib.sha256(f"{eid}:0".encode()).hexdigest()[:12]

    return "default"


def device_info_for(entry: Any, vin: str, model: str = "理想汽车") -> dict:
    """车辆设备的 device_info（可被各平台直接用作 _attr_device_info）。

    ★ identifiers 用 route_id 而非 VIN 明文：
      与 unique_id 保持同一主键，VIN 修正时不会重建设备。
    """
    rid = route_id_of_vin(vin)
    return {
        "identifiers": {(DOMAIN, rid)},
        "manufacturer": "理想汽车",
        "model": model,
        "name": _device_name(model, vin),
        "serial_number": vin or None,
    }


def account_device_info(entry: Any) -> dict:
    """账号级虚拟设备的 device_info（车辆设备 via_device 指向它）。"""
    data = getattr(entry, "data", None) or {}
    phone = str(data.get("phone") or "")
    tail = phone[-4:] if len(phone) >= 4 else ""
    return {
        "identifiers": {(DOMAIN, f"account_{tail or 'default'}")},
        "manufacturer": "理想汽车",
        "model": "理想账号",
        "name": f"理想账号 ****{tail}" if tail else "理想账号",
        "entry_type": "service",
    }


def control_enabled(entry: Any) -> bool:
    """是否允许车控（enable_control 选项，默认开启）。"""
    opts = getattr(entry, "options", None) or {}
    return bool(opts.get("enable_control", True))


def _device_name(model: str, vin: str) -> str:
    """设备显示名：车型 + VIN 后 4 位（无 VIN 时只用车型）。"""
    if vin:
        return f"{model} {vin[-4:]}"
    return model


__all__ = [
    "route_id_of",
    "route_id_of_vin",
    "device_info_for",
    "account_device_info",
    "control_enabled",
]
