"""车控门禁（enable_control 安全开关）

背景
----
远程控制车辆是**高风险操作**（锁车/解锁/开窗/空调）。
用户在 OptionsFlow 里可关闭 `enable_control`，
关闭后所有写操作应被拒绝（只读模式），防止误操作或自动化失控。

用法
----
在实体的写方法前加装饰器：

    from .gate import require_control

    class LiCarDoorLock(...):
        @require_control
        async def async_lock(self, **kwargs):
            ...
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from homeassistant.exceptions import HomeAssistantError

from .const import CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL, LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)


class ControlDisabledError(HomeAssistantError):
    """控制被禁用（enable_control=False）。"""

    def __init__(self) -> None:
        super().__init__(
            "远程控制已被禁用（集成选项 → 允许远程控制）。"
            "如需控制请先在 HA 中开启该选项。"
        )


def _enabled(entity: Any) -> bool:
    """检查该实体所属条目是否允许控制。"""
    try:
        # 优先从 coordinator/entry 的 options 读
        coord = getattr(entity, "coordinator", None)
        entry = getattr(coord, "_entry", None) if coord is not None else None
        if entry is None:
            # 回退：从 hass.data 找
            hass = getattr(entity, "hass", None)
            if hass is None:
                return True
            for d in (getattr(hass, "data", {}) or {}).get("lixiang_auto", {}).values():
                if isinstance(d, dict) and d.get("coordinator") is coord:
                    entry = d.get("entry")
                    break
        if entry is None:
            return True          # 找不到条目 → 不阻止（保守放行）
        return bool(entry.options.get(CONF_ENABLE_CONTROL, DEFAULT_ENABLE_CONTROL))
    except Exception:  # noqa: BLE001
        return True


def require_control(func: Callable) -> Callable:
    """装饰器：enable_control 关闭时拒绝写操作。"""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not _enabled(self):
            _LOGGER.warning(
                "拒绝控制操作 %s（enable_control=False）", func.__name__)
            raise ControlDisabledError()
        return await func(self, *args, **kwargs)

    return wrapper
