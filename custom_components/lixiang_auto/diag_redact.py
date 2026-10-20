"""诊断导出的**脱敏** —— 纯函数，不 import HA（便于离线单测）。

## 为什么单独一个模块

诊断文件是**要发给别人**的东西（排查 / 多车型对比 / 提 Issue），
而原始响应里存着：

  · 车辆经纬度 —— **住址级**信息
  · VIN —— 可定位到具体车辆
  · 可能的 token / 会话凭据

**脱敏一旦漏掉，就是"用户点一下就把住址和车控凭据发出去"。**

## 设计原则（学自两个同类项目）

1. **问界 huawei-auto-cloud**：诊断只导「代际号 + ID + 错误码」，
   **零车辆数据**。最彻底，但排障时信息量偏少。
2. **零跑 ha-leapmotor-cn**：**白名单** —— 只放行明确安全的键，
   其余一律丢弃；「将来新增敏感字段时，默认行为是不导出，而不是泄露」；
   VIN 只留 sha256 前 12 位**指纹**（能把多份诊断归到同一辆车，但不可还原）。

本模块取二者之长：
  · **结构白名单**（哪些键允许导出）+ **值分级**（有的掩码、有的留指纹）
  · 位置类信号**一律掩码**
  · VIN 只留指纹
"""

from __future__ import annotations

import hashlib
from typing import Any

__all__ = [
    "LOCATION_SIGNAL_IDS",
    "SENSITIVE_KEY_HINTS",
    "redact_entry_data",
    "redact_realtime_state",
    "redact_ability",
    "mask_value",
    "vin_fingerprint",
    "safe_filename_token",
]

# ── 位置类信号 ──────────────────────────────────────────────
#   原始响应里含经纬度的键名/路径片段。这些是**住址级**信息，一律掩码。
LOCATION_SIGNAL_IDS = (
    "longitude", "latitude", "lng", "lat",
    "gps_longitude", "gps_latitude",
    "coord", "coordinates", "position", "location",
    "gpsInfo", "gps_info",
)

# ── 敏感键名提示 ────────────────────────────────────────────
#   命中任一（大小写不敏感、子串匹配）⇒ 值掩码，连键名也可能不保留。
SENSITIVE_KEY_HINTS = (
    "token", "jwt", "bearer", "authorization", "auth",
    "password", "passwd", "pwd", "secret", "credential",
    "cookie", "session", "refresh", "hac_key", "hackey",
    "xdev", "device_id", "deviceid", "imei", "sn", "serial",
    "phone", "mobile", "tel", "email", "id_card", "idcard",
    # ★ VIN 及其变体：可定位到具体车辆（后 6 位常被车友当标识用）
    "vin", "vehicle_id", "vehicleid", "frame_no", "frameno",
)

# ── 条目数据白名单（只放行明确安全的）────────────────────────
#   其余一律丢弃 —— 包括 token / 密钥 / 手机号。
ENTRY_DATA_ALLOWLIST = (
    "vin_fingerprint",     # 指纹，不是 VIN 本身
    "car_type",            # 车型（诊断核心）
    "car_nickname",        # 车名（排查需要）
    "model_code",          # 官方车型码
    "spu",                 # 车型 SPU
    "version",             # 会话结构版本
    "platform",            # M 系 / X 系判据（排障关键）
)


def mask_value(value: Any) -> str:
    """把值替换成「类型 + 长度」指纹 —— 保留"有没有值/多长"，不保留内容。"""
    if value is None or value == "":
        return ""
    s = str(value)
    return f"<{type(value).__name__}:len{len(s)}>"


def vin_fingerprint(vin: Any) -> str:
    """VIN 只留**稳定指纹**（用于把多份诊断归类到同一辆车）。

    为什么用哈希而不是"留后 6 位"：后 6 位足以在公开场合定位到具体车辆
    （且常被用作车友间的标识）。指纹只需要"同一辆车得到同一个值"。
    """
    s = str(vin or "")
    if not s:
        return ""
    return "vin-" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def safe_filename_token(value: Any) -> str:
    """文件名用的安全片段 —— 只留指纹，避免 VIN/手机号进文件名。"""
    s = str(value or "")
    if not s:
        return "unknown"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def _is_sensitive_key(key: str) -> bool:
    k = str(key).lower()
    return any(h in k for h in SENSITIVE_KEY_HINTS)


def _is_location_key(key: str) -> bool:
    """是否是「位置类」键。

    ⚠️ 只对**标量值**生效 —— 若值是 dict/list（容器），说明它只是
    "装着位置信息的组"（如 vehiclePosition / gpsInfo），应该**继续往下递归**，
    而不是把整棵树掩成一个字符串（否则连组里其它非位置字段也丢了）。
    """
    k = str(key).lower()
    return any(h in k for h in LOCATION_SIGNAL_IDS)


def _redact_tree(node: Any, *, keep_location_shape: bool = True) -> Any:
    """递归脱敏一棵 JSON 树。

    · 键名敏感        ⇒ 值掩码
    · 键名是位置类    ⇒ 值掩码（但保留键，让排障者知道有这字段）
    · 其它            ⇒ 原样保留（信号号/值是协议层公共信息，
                         是"某车型上报哪些信号"的唯一证据）
    """
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            if _is_sensitive_key(k):
                out[str(k)] = mask_value(v)
            elif _is_location_key(k) and not isinstance(v, (dict, list)):
                # 位置标量：保留键名与"有值"这个事实，值掩码
                out[str(k)] = "<masked-location>" if v not in (None, "") else v
            else:
                out[str(k)] = _redact_tree(v, keep_location_shape=keep_location_shape)
        return out
    if isinstance(node, list):
        return [_redact_tree(x, keep_location_shape=keep_location_shape) for x in node]
    return node


def redact_realtime_state(raw: Any) -> dict:
    """`real-time-state` 原始响应 → 脱敏版。

    刻意**不**脱敏普通信号值：信号号/值是协议层公共信息，
    是"某车型上报哪些信号"的唯一证据；真正需要保护的是位置与账号凭据。
    """
    if not isinstance(raw, dict):
        return {"_redacted": True, "_type": type(raw).__name__}
    out = _redact_tree(raw)
    out["_redacted"] = True
    return out


def redact_ability(raw: Any) -> dict:
    """能力表导出 → 脱敏版（能力表一般不含敏感值，仍过一遍以防将来新增）。"""
    if not isinstance(raw, dict):
        return {"_redacted": True, "_type": type(raw).__name__}
    out = _redact_tree(raw)
    out["_redacted"] = True
    return out


def redact_entry_data(data: dict | None) -> dict:
    """配置条目 → **只保留白名单键**（其余丢弃，连键名都不保留）。

    这样即使将来新增敏感字段，默认行为也是"不导出"而不是"泄露"。
    """
    out: dict[str, Any] = {}
    for k in ENTRY_DATA_ALLOWLIST:
        if data and k in data:
            out[k] = data[k]
    return out


def summarize_for_log(raw: Any, *, max_keys: int = 12) -> dict:
    """给日志用的极简摘要（只报"有哪些顶层组/多少个叶子"）。

    ★ 日志同样可能被转发 ⇒ 不放任何值。
    """
    if not isinstance(raw, dict):
        return {"_type": type(raw).__name__}
    groups = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            groups[str(k)] = len(v)
        else:
            groups[str(k)] = 1
    keys = list(groups)
    return {
        "top_level_count": len(keys),
        "groups": {k: groups[k] for k in keys[:max_keys]},
        "truncated": len(keys) > max_keys,
    }
