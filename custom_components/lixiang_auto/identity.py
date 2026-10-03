"""理想汽车集成 · 设备身份持久化（device_id）

为什么需要
----------
理想的登录风控（顶象/PAKE）会检查 device_id：
  · **受信任**的 device_id → 密码登录直接通过
  · **新设备**的 device_id  → 返回 require=SMS_CODE（需要短信验证）

实测（2026-09-23）：
    受信任设备 <设备ID>... → ✅ 登录成功
    随机新设备 <随机ID>... → ⚠️ 风控要求短信验证

因此 device_id 必须**跨 ConfigEntry 持久化**：
  · 用户删除集成再重新添加时，不应失去设备信任
  · 同一账号在 HA 里重装集成后应能直接密码登录

存储位置
--------
    custom_components/lixiang_auto/.identity.json
    {
      "accounts": {
        "<手机号sha256前16位>": {"device_id": "...", "phone_tail": "6363"}
      },
      "fallback_device_id": "..."     # 首个账号之前用
    }

参考：huawei-auto-cloud 的 storage.py（PhoneAssetStore）
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from .const import DEFAULT_DEVICE_ID, LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)

_STORE_FILE = os.path.join(os.path.dirname(__file__), ".identity.json")


def normalize_phone(phone: Any) -> str:
    """归一化手机号（去空格/横杠/括号/`+86` 前缀）。

    ★ 关键：unique_id 必须用归一化值，否则
      "+86 138-0013-8000" 与 "13800138000" 会被当成两个账号
      → 重复添加 → 双倍轮询 → 触发风控
    """
    s = str(phone or "").strip()
    for ch in (" ", "-", "(", ")", "_"):
        s = s.replace(ch, "")
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) > 11:
        s = s[2:]
    return s


def _account_key(phone: str) -> str:
    """账号存储键（手机号 hash，避免明文落盘）。"""
    norm = normalize_phone(phone)
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


class IdentityStore:
    """device_id 持久化（跨 ConfigEntry 保活）。"""

    def __init__(self, path: str = _STORE_FILE, *, autoload: bool = True) -> None:
        self._path = path
        self._data: dict[str, Any] = {"accounts": {}}
        self._loaded = False
        if autoload:
            # ★ 仅在非事件循环场景自动加载；
            #   事件循环里请用 await load_async(hass)
            self._load()
            self._loaded = True

    async def load_async(self, hass) -> None:
        """在线程池里加载（避免阻塞事件循环）。"""
        if self._loaded:
            return
        await hass.async_add_executor_job(self._load)
        self._loaded = True

    def ensure_loaded_sync(self) -> None:
        """同步加载（调用方需确保不在事件循环里）。"""
        if not self._loaded:
            self._load()
            self._loaded = True

    # ---------- 读写 ----------
    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, encoding="utf-8") as fh:
                    d = json.load(fh)
                if isinstance(d, dict):
                    self._data = d
                    self._data.setdefault("accounts", {})
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("读取设备身份存储失败（将重建）: %s", err)
            self._data = {"accounts": {}}

    def _save(self) -> None:
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
            try:
                os.chmod(self._path, 0o600)      # 仅属主可读
            except OSError:
                pass
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("保存设备身份失败: %s", err)

    # ---------- 公开 API ----------
    def get_device_id(self, phone: str) -> str | None:
        """取该账号已保存的 device_id（没有则返回 None）。"""
        rec = (self._data.get("accounts") or {}).get(_account_key(phone))
        if isinstance(rec, dict):
            did = rec.get("device_id")
            if did:
                return str(did)
        return None

    def set_device_id(self, phone: str, device_id: str, *, save: bool = True) -> None:
        """保存该账号的 device_id。

        ★ 注意（2026-09-23 修复阻塞 IO）：
          _save() 是同步文件写。若在事件循环里调用会触发 HA 的
          "Detected blocking call" 警告。
          因此：
            · 事件循环中 → 传 save=False，然后 await save_async()
            · 线程/executor → 直接 save=True
        """
        if not phone or not device_id:
            return
        accounts = self._data.setdefault("accounts", {})
        accounts[_account_key(phone)] = {
            "device_id": str(device_id),
            "phone_tail": str(normalize_phone(phone))[-4:],
        }
        if save:
            self._save()
        _LOGGER.debug("已保存设备身份: ...%s", str(device_id)[-8:])

    async def save_async(self, hass) -> None:
        """在线程池里落盘（避免阻塞事件循环）。"""
        await hass.async_add_executor_job(self._save)

    def ensure_device_id(self, phone: str, *, bootstrap: str | None = None) -> str:
        """取或创建 device_id。

        bootstrap: 首次安装时可传入一个已知受信任的值（如 DEFAULT_DEVICE_ID），
                   这样首个账号也能免短信。建议只在**用户明确选择**时使用。
        """
        did = self.get_device_id(phone)
        if did:
            return did
        if bootstrap:
            self.set_device_id(phone, bootstrap, save=False)
            return bootstrap
        import uuid
        did = uuid.uuid4().hex
        self.set_device_id(phone, did, save=False)
        return did

    @property
    def known_accounts(self) -> int:
        return len(self._data.get("accounts") or {})


# 模块级单例（进程内共享，避免重复读写）
_store: IdentityStore | None = None


def get_store() -> IdentityStore:
    """获取（或惰性创建）身份存储单例。

    ★ 注意：首次创建时【不】自动读盘（避免事件循环阻塞 IO）。
      事件循环里请先 await get_store_async(hass)。
    """
    global _store
    if _store is None:
        _store = IdentityStore(autoload=False)
    return _store


async def get_store_async(hass) -> IdentityStore:
    """获取单例并确保已读盘（在线程池里做 IO）。"""
    store = get_store()
    await store.load_async(hass)
    return store


__all__ = [
    "IdentityStore", "get_store", "get_store_async", "normalize_phone",
    "DEFAULT_DEVICE_ID",
]
