"""官方静态车模图（2026-10-12）。

背景：为什么放弃 3D
------------------
我们曾把 App 的 Unity AssetBundle（133 MB/车）转成 GLB 内嵌展示，实测**行不通**：

1. **素材本身不含车门外覆件** —— 逐个核对 92 个网格，只有
   ``Door_*``（材质是"车门内_金属""内饰底绒_侧面"= 内衬），
   **没有前/后保险杠、车门外壳**。这是官方包的内容，不是导出错误
   （下载的官方包与本地 ``carmodel.bundle`` md5 完全一致：
   （下载包哈希与本地一致））。
2. **成本极高** —— 61 MB 的 GLB，手机每次清缓存都要重下；
   而官方静态图仅 ~230 KB/张。
3. **颜色要靠猜** —— 7 个 ``CarPaint_*`` 材质共用同一张贴图、
   ``_BaseColor`` 全是 ``[1,1,1]``，车漆颜色**不在模型里**。

所以改用**官方渲染好的竖版整车图**，颜色/车型全自动对上。

数据来源（实测打通）
--------------------
① ``GET /saos-vehicle-api/v2-0/vehicles/basics?vehicleInfo=true``
   → ``modelId`` / ``colorCode`` / ``interiorCode`` / ``wheelCode``
   实测：``color = "珠光漆 - 新白色-EA05"``、``colorCode = "FA9"``

② 本地 ``vehicle_configs/{modelId}.json``（从官方 APK 提取，72 个车型）
   → ``config.vertical[] = [{"key":"FA9","value":"https://…png"}, …]``
   ★ ``colorCode`` 与 ``vertical[].key`` **是同一套 key** → 可精确匹配

③ 图是 ``p.ampmake.com`` 上的**明文直链**，无需鉴权（已实测下载成功）

设计要点
--------
* **零人工配置**：颜色由服务器返回，用户什么都不用填
* **懒下载**：只在卡片真的要用时才下，不预置进git（69 MB 全量太重）
* **并发去重**：同一张图被多处请求时只会下一次
* **不阻塞事件循环**：全程 ``aiohttp`` 异步
* **失败不缓存**：下次请求自动重试
* **降级**：本地缓存 → CDN 直连 → 占位图标
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

# ★ 2026-10-12：aiohttp / vehicle_ability 都**延迟导入**。
#   原因：本模块的 list_images / pick_key 是**纯函数**（选图逻辑），
#   应能在没有 HA / aiohttp 的环境里直接单测 —— 顶层 import aiohttp
#   会让整个模块导入失败，纯函数也没法验证（实测踩过）。
_LOGGER = logging.getLogger(__name__)

# 图片类型（都来自 config 的同名字段）
KIND_VERTICAL = "vertical"    # 竖版整车图（主力）
KIND_MINICON = "minIcon"      # 小图标版
_KIND_FIELD = {KIND_VERTICAL: "vertical", KIND_MINICON: "minIcon"}

# 允许的 CDN 主机（白名单：配置来自本地 json，但仍不外发到任意主机）
_ALLOWED_HOSTS = ("p.ampmake.com",)

_MAX_BYTES = 4 * 1024 * 1024      # 单图上限 4 MB
_TIMEOUT = 30


def list_images(config: dict[str, Any] | None, kind: str = KIND_VERTICAL) -> dict[str, str]:
    """从车型配置里取 ``{key: url}``。

    ``config`` 形如 ``{"config": {"vertical": [{"key": "FA9", "value": "https://…"}]}}``
    """
    if not config:
        return {}
    field = _KIND_FIELD.get(kind)
    if not field:
        return {}
    items = (config.get("config") or {}).get(field) or []
    out: dict[str, str] = {}
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                key, val = it.get("key"), it.get("value")
            elif isinstance(it, (list, tuple)) and len(it) == 2:
                key, val = it[0], it[1]
            else:
                continue
            # value 可能是 URL，也可能是资源 key（如 ex_color_0_LXVR_L7）→ 只收 URL
            if key and isinstance(val, str) and val.startswith(("http://", "https://")):
                out[str(key)] = val
    return out


def pick_key(images: dict[str, str], want: str | None, fallback: str | None = None) -> str | None:
    """按服务器给的色码选 key；选不中则退回调用方指定的兜底。"""
    if want and want in images:
        return want
    if fallback and fallback in images:
        return fallback
    # 最后兜底：取第一张（保证有图可显示）
    return next(iter(images), None)


def _safe_host(url: str) -> bool:
    return any(h in url for h in _ALLOWED_HOSTS)


class CarImageManager:
    """按需下载并缓存官方车模图。"""

    def __init__(self, hass, cache_dir: Path) -> None:
        self.hass = hass
        self.cache_dir = Path(cache_dir)
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("车模图缓存目录创建失败（将退化为CDN 直连）: %s", err)

    # ---------- 路径 ----------
    def _dir(self, model_id: str) -> Path:
        return self.cache_dir / str(model_id)

    def local_path(self, model_id: str, key: str, kind: str = KIND_VERTICAL) -> Path:
        safe = "".join(ch for ch in str(key) if ch.isalnum() or ch in "-_")
        return self._dir(model_id) / f"{kind}_{safe or 'default'}.png"

    # ---------- 取URL ----------
    def resolve(self, model_id: str | None, kind: str = KIND_VERTICAL,
                color_code: str | None = None) -> dict[str, Any] | None:
        """返回 ``{model_id, key, url, kind, cached}``；拿不到返回 None。"""
        if not model_id:
            return None
        from .vehicle_ability import load_vehicle_config

        cfg = load_vehicle_config(str(model_id))
        images = list_images(cfg, kind)
        if not images:
            return None
        key = pick_key(images, color_code)
        if not key:
            return None
        return {
            "model_id": str(model_id),
            "key": key,
            "url": images[key],
            "kind": kind,
            "cached": self.local_path(model_id, key, kind).is_file(),
        }

    # ---------- 下载 ----------
    async def async_ensure(self, model_id: str | None, kind: str = KIND_VERTICAL,
                           color_code: str | None = None) -> dict[str, Any] | None:
        """确保图在本地，返回同 ``resolve``（``cached`` 反映最终状态）。"""
        info = self.resolve(model_id, kind, color_code)
        if not info:
            return None
        path = self.local_path(info["model_id"], info["key"], info["kind"])
        if path.is_file() and path.stat().st_size > 0:
            info["cached"] = True
            info["path"] = str(path)
            return info
        lock = self._locks.setdefault(f"{info['model_id']}_{info['kind']}_{info['key']}",
                                      asyncio.Lock())
        async with lock:
            # 双检：可能已被并发请求下好
            if path.is_file() and path.stat().st_size > 0:
                info["cached"] = True
                info["path"] = str(path)
                return info
            ok = await self._async_download(info["url"], path)
            info["cached"] = bool(ok)
            if ok:
                info["path"] = str(path)
        return info

    async def _async_download(self, url: str, dest: Path) -> bool:
        if not _safe_host(url):
            _LOGGER.warning("车模图 URL 主机不在白名单内，已拒绝: %s", url[:80])
            return False
        tmp = dest.with_suffix(".part")
        try:
            import aiohttp
            from homeassistant.helpers import aiohttp_client

            session = aiohttp_client.async_get_clientsession(self.hass)
            timeout = aiohttp.ClientTimeout(total=_TIMEOUT)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.debug("车模图下载 HTTP %s: %s", resp.status, url[:80])
                    return False
                dest.parent.mkdir(parents=True, exist_ok=True)
                # ★ 必须流式分块读：aiohttp 的 `read(n)` 在部分版本/响应头下
                #   会返回不足 n 的数据（实测 231KB 的 PNG 只拿到 16384 字节），
                #   一次性 read 不可靠。分块累加并自行判上限。
                buf = bytearray()
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    buf.extend(chunk)
                    if len(buf) > _MAX_BYTES:
                        break
                data = bytes(buf)
            if len(data) > _MAX_BYTES:
                _LOGGER.warning("车模图超过 %d 字节上限，已丢弃: %s", _MAX_BYTES, url[:60])
                return False
            if not data or data[:4] not in (b"\x89PNG", b"\xff\xd8\xff\xe0"):
                _LOGGER.debug("车模图不是 PNG/JPEG，已丢弃: %s", url[:60])
                return False
            # ★ 文件 IO 走 executor —— HA 会把事件循环里的阻塞调用记成告警
            def _write(d=dest, b=data):
                tmp = d.with_suffix(".part")
                tmp.write_bytes(b)
                tmp.replace(d)

            await self.hass.async_add_executor_job(_write)
            _LOGGER.info("已缓存车模图 %s (%d 字节)", dest.name, len(data))
            return True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("车模图下载失败 %s: %s", url[:70], err)
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:  # noqa: BLE001
                pass
            return False

    # ---------- 预热 ----------
    async def async_prefetch(self, model_id: str | None,
                             color_code: str | None = None) -> None:
        """启动时把当前车型需要的图下好（失败静默）。"""
        for kind in (KIND_VERTICAL, KIND_MINICON):
            try:
                await self.async_ensure(model_id, kind, color_code)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("预取车模图失败(%s): %s", kind, err)


def read_meta(hass) -> dict[str, Any]:
    """诊断用：返回缓存概况。"""
    try:
        mgr: CarImageManager | None = hass.data.get("lixiang_auto__car_image")
    except Exception:  # noqa: BLE001
        mgr = None
    if not mgr:
        return {}
    out: dict[str, Any] = {"dir": str(mgr.cache_dir), "models": []}
    try:
        for d in sorted(mgr.cache_dir.iterdir()):
            if d.is_dir():
                files = [f.name for f in d.iterdir() if f.is_file()]
                out["models"].append({"model_id": d.name, "files": files})
    except Exception:  # noqa: BLE001
        pass
    return out


def sha256_of(path: Path) -> str:
    """给缓存文件算摘要（诊断/测试用）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
