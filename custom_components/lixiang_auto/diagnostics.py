"""理想汽车集成 · 诊断导出（脱敏）

用途
----
用户遇到问题时，可在 HA 里「设备 → 下载诊断」，导出 JSON 便于排查。
参考 huawei-auto-cloud 的 diagnostics 设计。

★ 安全要求（关键）
------------------
本文件导出的内容**绝不能**包含：
  · hac_key / key_id / app_token / password / device_id（完整）
  · 完整 VIN（只留后 6 位）
  · 完整手机号（只留后 4 位）
  · 车辆位置坐标（lat / lon）
  · MESH / VAT / MMS token

所有字段都要经过 _redact() 或显式裁剪。
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_VIN, DOMAIN

# 敏感键名（出现在任何层级都要打码）
_SENSITIVE_KEYS = frozenset({
    "hac_key", "key_id", "app_token", "password", "device_id",
    "x_chj_deviceid", "main_bearer", "mesh_token", "vat_token",
    "mms_token", "token", "access_token", "refresh_token",
    "lat", "lon", "latitude", "longitude", "phone", "vin",
})


def _redact(obj: Any, depth: int = 0) -> Any:
    """递归打码：敏感键的值替换为 ***，深度限制 4 层。"""
    if depth > 4:
        return "..."
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEYS:
                out[k] = "***"
            else:
                out[k] = _redact(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [_redact(x, depth + 1) for x in obj[:20]]
    if isinstance(obj, str) and len(obj) > 120:
        return obj[:120] + f"...(len={len(obj)})"
    return obj


def _mask_phone(p: Any) -> str | None:
    """手机号只留后 4 位。"""
    s = str(p or "")
    if len(s) < 4:
        return None
    return "****" + s[-4:]


def _mask_vin(v: Any) -> str | None:
    """VIN 只留后 6 位。"""
    s = str(v or "")
    if len(s) < 6:
        return None
    return "***" + s[-6:]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """导出配置条目诊断（已脱敏）。"""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    coordinator = data.get("coordinator")
    client = data.get("client")
    li_api = data.get("li_api")

    vin = entry.data.get(CONF_VIN) or ""
    coord_data = (coordinator.data if coordinator else None) or {}
    vss = coord_data.get("vss") or {}

    # ---- 集成版本 ----
    manifest: dict[str, Any] = {}
    try:
        import json as _json
        import os as _os
        mp = _os.path.join(_os.path.dirname(__file__), "manifest.json")
        with open(mp, encoding="utf-8") as fh:
            manifest = _json.load(fh)
    except Exception:  # noqa: BLE001
        pass

    # ---- coordinator 状态 ----
    coord_info: dict[str, Any] = {
        "signal_count": len(vss),
        "has_data": bool(coord_data),
        "vss_polled_at": coord_data.get("vss_polled_at"),
        "vss_skipped": coord_data.get("vss_skipped"),
        "vehicle_status": coord_data.get("vehicle_status"),
    }
    if coordinator is not None:
        coord_info.update({
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "online": getattr(coordinator, "_online", None),
            "update_interval_s": (
                coordinator.update_interval.total_seconds()
                if getattr(coordinator, "update_interval", None) else None
            ),
            "mid_freq_cached": len(getattr(coordinator, "_mid_freq_cache", {}) or {}),
            "low_freq_cached": len(getattr(coordinator, "_low_freq_cache", {}) or {}),
        })

    # ---- 信号抽样（避开位置类）----
    sample = {}
    for k, v in list(vss.items())[:25]:
        if k == "location":          # ★ 位置信号跳过（含坐标）
            sample[k] = {"value": "<redacted>", "ts": v.get("ts")}
            continue
        val = v.get("value")
        if isinstance(val, str) and len(val) > 80:
            val = val[:80] + "..."
        sample[k] = {"value": val, "ts": v.get("ts")}

    # ---- token 状态（只报有无）----
    token_state: dict[str, Any] = {"app_token": bool(entry.data.get("app_token"))}
    if li_api is not None:
        cache = getattr(li_api, "_token_cache", None)
        if isinstance(cache, dict):
            token_state["cached_scopes"] = sorted(cache.keys())
        else:
            token_state["cached_scopes"] = []

    # ---- 车辆/账号（脱敏）----
    vehicle: dict[str, Any] = {
        "vin_tail": _mask_vin(vin),
        "route_id": entry.data.get("route_id"),
        "model": entry.data.get("model"),
        "alias": entry.data.get("alias"),
    }
    if client is not None:
        vehicle["has_client"] = True
        vlist = getattr(client, "_vehicles", None)
        if isinstance(vlist, list):
            vehicle["vehicle_count"] = len(vlist)

    return {


        # ★ 2026-09-24：集成健康状态（失败计数 / 在线状态）


        "health": (coordinator.health if coordinator is not None else None),

        "manifest": {
            "version": manifest.get("version"),
            "domain": manifest.get("domain"),
            "iot_class": manifest.get("iot_class"),
        },
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "state": str(entry.state),
            "data_keys": sorted(entry.data.keys()),      # ★ 只列键名
            "options": dict(entry.options or {}),
            "unique_id": entry.unique_id,
        },
        "account": {
            "phone_tail": _mask_phone(entry.data.get("phone")),
        },
        "vehicle": vehicle,
        "features": _redact(data.get("features") or {}),
        "vehicle_config": _redact(data.get("vehicle_config") or {}),
        "coordinator": _redact(coord_info),
        "signal_sample": sample,
        "signal_all_keys": sorted(vss.keys())[:200],
        "token_state": token_state,
    }
