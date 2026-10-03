"""理想汽车门锁（lock 平台）— 车控 cmd/send 已实测打通.

命令（2026-09-22 实测 pushState=5 / resultCode=0）:
  remoteVehLockControl  cmdData={"lockSw":"0"}   落锁
  remoteVehLockControl  cmdData={"lockSw":"1"}   解锁

★ 旧的 remote_central_lock_lock / unlock 是错的（APK 字符串枚举值，非真实 cmdKey），
  已按实测结果修正为同一个 cmdKey + lockSw 区分。

状态: VSS Vehicle.Body.DoorLockStatus.MainDoor（0=落锁, 非0=解锁）

⚠️ 车控会真实作用于车辆。lock 实体是显式操作（UI 点击）。
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .gate import require_control
from .entity_helper import route_id_of_vin
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

LOCK_STATE_KEY = "lock_main"
CMD_LOCK = "remoteVehLockControl"
# ★ lockSw: "1"=解锁, "0"=落锁（实测）
DATA_LOCK = {"lockSw": "0"}
DATA_UNLOCK = {"lockSw": "1"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator, li_api = data["coordinator"], data.get("li_api")
    vin = config_entry.data.get(CONF_VIN) or ""
    identifiers = {(DOMAIN, vin)} if vin else {(DOMAIN, config_entry.entry_id)}
    # ★ 名字全取自服务端（vehicleNickname / spu），不硬编码车型
    _d = hass.data[DOMAIN][config_entry.entry_id]
    device_info = build_device_info(
        _d.get("coordinator"), config_entry, _d.get("li_api"),
        ability=_d.get("ability"),
    )
    if li_api is None:
        _LOGGER.warning("无密码登录凭据，跳过 lock 实体")
        return
    async_add_entities([LiCarDoorLock(coordinator, li_api, device_info, vin)])


class LiCarDoorLock(CoordinatorEntity, LockEntity):
    """理想车门锁（真车控）."""

    _attr_has_entity_name = True
    # ★ 2026-09-26：名字对齐 App（App 叫「车锁」，见 vehicle_control_car_lock）
    #   ⚠️ 名字在 __init__ 里预取（app_name 会读 JSON 文件，
    #      放在 name 属性里会在事件循环中阻塞 → HA 告警）
    _attr_icon = "mdi:car-door-lock"

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        # ★ 名字对齐 App（在 __init__ 预取，避免事件循环里读文件）
        try:
            from .vehicle_ability import app_name
            self._attr_name = app_name("lock", default="车锁")
        except Exception:  # noqa: BLE001
            self._attr_name = "车锁"
        self._api = li_api
        self._rid = route_id_of_vin(vin)

        self._attr_unique_id = f"{DOMAIN}_{self._rid}_lock_central"
        self._attr_device_info = device_info
        self._last_result: dict | None = None

    @property
    def is_locked(self) -> bool | None:
        """0 = 已落锁 → True."""
        sig = (self.coordinator.data or {}).get("vss", {}).get(LOCK_STATE_KEY)
        if not sig or sig.get("value") is None:
            return None
        try:
            return int(sig["value"]) == 0
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_lock(self, **kwargs: Any) -> None:
        await self._send(DATA_LOCK)

    @require_control
    async def async_unlock(self, **kwargs: Any) -> None:
        await self._send(DATA_UNLOCK)

    async def _send(self, cmd_data: dict) -> None:
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_LOCK, cmd_data)
            self._last_result = res
            _LOGGER.info("车控 %s %s 已执行: %s", CMD_LOCK, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", CMD_LOCK, cmd_data, err)
            raise
        await self.coordinator.async_request_refresh()
