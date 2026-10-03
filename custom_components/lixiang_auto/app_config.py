"""App 配置表（从 APK 内置 assets/m01config.json 提取）

★ 2026-09-26 新增：这是【权威来源】，避免再瞎猜 audience/scope。

背景
----
我们之前自己拼 VAT scope（14 个，含 cpCtrl/ssCtrl/ChargingControl）——
实测服务端会【整批降级】，只授权 8 个（丢掉 fTkC/rmCtrl/ADCtrl/ADInit）。

而 App 的配置表（subTokenData）明确写了每个接口该用什么：
    type / client / audience / scope / responseType / urls

用法
----
    from .app_config import token_config, audience_for, scope_for

    cfg = token_config("VAT_1")
    # → {"client": "...", "audience": "5Tc7...", "scope": [...], "urls": [...]}

    aud = audience_for("/ssp-vehicle-control-service/...")   # 按端点反查
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from .const import LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)
_CONFIG_DIR = Path(__file__).parent / "app_config"


@lru_cache(maxsize=1)
def load_token_table() -> dict[str, dict[str, Any]]:
    """加载 token 配置表（40 项）。"""
    f = _CONFIG_DIR / "sub_token_data.json"
    if not f.exists():
        _LOGGER.debug("token 配置表不存在: %s", f.name)
        return {}
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("解析 token 配置表失败: %s", err)
        return {}
    toks = raw.get("tokens")
    return toks if isinstance(toks, dict) else {}


@lru_cache(maxsize=1)
def load_app_config() -> dict[str, Any]:
    """加载 app 配置（57 项，含 LiIDDomain / urlWhiteList 等）。"""
    f = _CONFIG_DIR / "app_config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def token_config(token_type: str) -> dict[str, Any]:
    """按 type 取 token 配置（如 "VAT_1" / "VSS" / "mms-api"）。"""
    return dict(load_token_table().get(token_type) or {})


def audience_for(path: str) -> str:
    """按端点路径反查 audience。

    ★ 长前缀优先（避免 /ssp-vehicle-control-service/... 匹配到更短的）。
    """
    best = ""
    best_len = 0
    for _t, cfg in load_token_table().items():
        for u in (cfg.get("urls") or []):
            if u.startswith("http"):
                continue
            if path.startswith(u) and len(u) > best_len:
                best = cfg.get("audience", "")
                best_len = len(u)
    return best


def type_for(path: str) -> str:
    """按端点路径反查 token type（如 "VAT_1" / "httpLiMeshServiceV2"）。"""
    best = ""
    best_len = 0
    for t, cfg in load_token_table().items():
        for u in (cfg.get("urls") or []):
            if u.startswith("http"):
                continue
            if path.startswith(u) and len(u) > best_len:
                best = t
                best_len = len(u)
    return best


def scope_for(path: str) -> list[str]:
    """按端点路径反查 scope 列表。"""
    t = type_for(path)
    return list((token_config(t).get("scope") or [])) if t else []


def all_types() -> list[str]:
    """全部 token type（诊断用）。"""
    return sorted(load_token_table().keys())


def dump_table() -> dict[str, Any]:
    """完整表（诊断服务用）。"""
    return {
        "token_types": all_types(),
        "tokens": load_token_table(),
        "app_keys": sorted(load_app_config().keys()),
    }
