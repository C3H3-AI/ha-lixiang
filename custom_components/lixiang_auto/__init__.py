"""Li Auto (Ideal Car) Home Assistant integration.

认证链 (2026-09-06 端到端验证): PAKE 密码登录 → 会话 cookie 换 vss scope token
→ x-chj 签名调 vss/get-batch 读实时信号. 见 docs/实时状态打通_20260906.md.

车控 (2026-09-22 实测打通): 同一登录会话换【双 token】——
  MESH token (Authorization 头) + VAT token (body.token 字段)
→ x-chj 签名 POST cmd/send → 轮询 cmd-result 至 pushState=5.
见 docs/车控Token突破_20260922.md / docs/HA集成车控实现_20260922.md.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    aiohttp_client,
    entity_registry as er,
)

from .client import LiCarClient
from .const import (
    APP_LIVIS,
    APP_LIXIANG,
    CONF_APP_TOKEN,
    CONF_APP_TYPE,
    CONF_DEVICE_ID,
    CONF_HAC_KEY,
    CONF_KEY_ID,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_VIN,
    CONF_XDEV,
    DEFAULT_APP_TOKEN,
    CONF_IDENTITY_SOURCE,
    CONF_MAIN_BEARER,
    CONF_REFRESH_TOKEN,
    CONF_SESSION_COOKIES,
    DEFAULT_DEVICE_ID,
    DOMAIN,
    LOGGER_NAME,
)
from .coordinator import LiCarCoordinator
from .signer import LiCarSigner

# ★ 2026-10-09：服务端按【账号角色】限制的功能（实测：家人账号拿不到）
#   · 任务大师（task-master）
#   · 充电记录 / 充电量（chargeRecords / monthlyStatistics）
#   非车主调用时返回可读原因，而不是让服务端回 401/100105 ——
#   那是服务端限制、用户改不了，不该伪装成可修复的故障。
_OWNER_ONLY_NOTICE = "仅车主账号可用（服务端按账号角色限制）"


# ★ 2026-10-14：随集成自动注入的前端卡片模块清单。
#
# 为什么全部注入（而不只注入外壳）：
#   · 外壳（lixiang-app.js）**一张卡就含全部 13 个页面**，是推荐用法；
#   · 但历史文档教用户"每个页面各建一个视图"，那 13 个视图各自的卡片
#     （custom:lixiang-charge-page 等）也必须被定义，否则视图一片空白。
#     HACS 不会替集成注册 Lovelace 资源 → 用户漏加就"下面的都无法操作"。
#   · 这些模块只在被用到的页面实例化（外壳内部也按需 import），
#     静态文件由浏览器缓存，代价可控。
_CARD_MODULES = (
    "lixiang-app.js",              # 总卡片（内部含全部页面 + 导航）
    "lixiang-app-home.js",
    "lixiang-charge-page.js",
    "lixiang-energy-page.js",
    "lixiang-health-page.js",
    "lixiang-setting-page.js",
    "lixiang-scene-page.js",
    "lixiang-climate-page.js",
    "lixiang-seat-page.js",
    "lixiang-location-page.js",
    "lixiang-vehicle-info-page.js",
    "lixiang-task-page.js",
    "lixiang-ad-page.js",
    "lixiang-bindings-card.js",
    "lixiang-overview-card.js",    # 车辆总览（可单独使用）
)


async def _owner_only_hint(hass, result) -> str:
    """任务/充电服务在「结果为空」时给出准确原因。

    ★ 2026-10-09：空结果有两种成因，对用户是完全不同的指引 ——
      · 非车主账号 → 服务端按角色限制，用户改不了（不该让他去查配置）
      · 真的没配置 / vin 不匹配 → 集成侧问题
    ★ 2026-10-10：角色探测走 executor（见 _is_non_owner_async）。
    """
    if result:
        return ""
    try:
        for d in (hass.data.get(DOMAIN) or {}).values():
            if isinstance(d, dict) and await _is_non_owner_async(
                    hass, d.get("li_api")):
                return _OWNER_ONLY_NOTICE
    except Exception:  # noqa: BLE001
        pass
    return "未找到 lixiang_auto 配置项（或 vin 不匹配）"


def _is_non_owner(api, config_dir: str = "") -> bool:
    """当前 API 所属账号是否【确定不是车主】。

    角色探测失败一律返回 False（按"可试"处理），
    避免因车辆列表读取失败而误伤车主账号。

    ★ 2026-10-11：传 config_dir 走落盘缓存 —— get_vehicles 的
      saos_vehicle token 必须回退主 App client 换取，会顶掉用户手机 App。
    """
    try:
        from . import vehicle_role as _vr
        veh = _vr.current_vehicle(api, config_dir)
        if not veh:
            return False
        rel = _vr.relation_of(veh)
        # ★ 只有【明确是】家人/试驾/邀请中等才拦截。
        #   REL_NONE = 关系未确定（如车主车辆尚在 Registered 未完成）
        #   → 必须放行，否则新车车主会被误判成"非车主"而看不到任务大师。
        if rel in (None, _vr.REL_NONE, _vr.REL_OWNER):
            return False
        return True
    except Exception:  # noqa: BLE001
        return False

_OWNER_ROLE_TTL = 6 * 3600.0     # 角色缓存 6 小时（与 coordinator 侧一致）


async def _is_non_owner_async(hass, api) -> bool:
    """_is_non_owner 的异步包装：探测走 executor + 模块级缓存。

    ★ 2026-10-10 修：服务 handler 里此前直接调同步 `_is_non_owner`，
      内部 `get_vehicles()` 是同步 HTTP —— 在事件循环里执行会触发
      HA blocking-call 告警，且**抛出的异常会中断服务 handler 的
      条目遍历**（实测：get_charge/get_travel/get_tasks 全部返回空 `[]`）。
    """
    if api is None:
        return False
    import time as _time
    # ★ 缓存必须放独立 dict：DOMAIN 容器会被各服务 handler 遍历，
    #   遍历期间加键会抛 "dictionary changed size during iteration"（实测 500）
    cache = hass.data.setdefault(f"{DOMAIN}__owner_role", {})
    key = getattr(api, "_phone", "") or "default"
    now = _time.monotonic()
    ent = cache.get(key)
    if ent is not None:
        value, ts = ent
        if value is not None and (now - ts) < _OWNER_ROLE_TTL:
            return bool(value)
    value = await hass.async_add_executor_job(_is_non_owner, api)
    cache[key] = (value, now)
    return bool(value)


PLATFORMS: list[Platform] = [
    Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER,
    Platform.LOCK, Platform.SWITCH, Platform.BUTTON, Platform.NUMBER,
    Platform.CLIMATE, Platform.SELECT, Platform.NOTIFY,
    # ★ 2026-09-24 整合 shinnaluo 的 PR：
    Platform.COVER,   # 尾门/车窗（HA 标准做法，替代 button）
    Platform.FAN,     # 座椅加热/通风（档位 UI，替代 switch+number）
    # ★ 2026-09-24 新增（用户反馈"开始充电时间应该是时间设置"）：
    Platform.TIME,    # 充电开始/结束时间（可设置的区间）
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(LOGGER_NAME)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """集成加载时执行（早于 config_entry）。

    ★ 在这里注册登录辅助页面 —— 因为用户【还没有配置条目】时
      就可能需要访问 /lixiang-login（首次登录场景）。
    """
    hass.data.setdefault(DOMAIN, {})
    try:
        from .auth_web import async_register_login_views
        await async_register_login_views(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册登录辅助页面失败: %s", err)
    return True


def _integration_version() -> str:
    """集成版本号（读 manifest.json）—— 给前端资源做 cache-buster。"""
    try:
        from pathlib import Path as _P  # noqa: PLC0415

        import json as _json  # noqa: PLC0415

        m = _json.loads((_P(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
        return str(m.get("version") or "0")
    except Exception:  # noqa: BLE001
        return "0"


class LiXiangAssetVersionView(HomeAssistantView):
    """给前端卡片用的资源版本号。

    ★ 为什么需要它：卡片资源（JS / 图标 / 车型剪影）走静态路径 `/lixiang_auto`，
      **没有版本号**时浏览器会沿用旧缓存 —— HACS 更新后用户可能仍在跑旧卡片。
      卡片拿到 `window.__LX_ASSET_V__` 后给资源 URL 追加 `?v=`，版本一变必然重新拉取。
    """

    url = "/lixiang_auto/asset-version.js"
    name = "api:lixiang_auto:asset_version"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return web.Response(
            text=f'window.__LX_ASSET_V__="{_integration_version()}";\n',
            content_type="application/javascript")



class LiXiangTaskDictView(HomeAssistantView):
    """把任务条件/动作字典暴露给前端卡片。

    ★ 卡片只能访问 `hass`（拿不到 coordinator），所以字典必须经 REST 出去。
      路径：/lixiang_auto/task-dict.json
      返回：{ok:true, saved_at, conditions:[...], actions:[...], summary}
            {ok:false, error:"..."} —— 取不到时**如实报错**，前端据此回退旧简表
    """

    url = "/lixiang_auto/task-dict.json"
    name = "api:lixiang_auto:task_dict"
    requires_auth = False      # 与 asset-version 一致：不含敏感信息

    def __init__(self, hass: HomeAssistant, coordinator=None) -> None:
        self.hass = hass
        self._coordinator = coordinator

    async def get(self, request: web.Request) -> web.Response:
        """返回字典；未获取到时给 ok=false + 原因（前端据此回退，不显示空表单）。"""
        try:
            from . import task_dict as _td
        except Exception as err:  # noqa: BLE001
            return web.json_response({"ok": False, "error": f"模块不可用：{err}"[:160]})
        coord = self._coordinator
        data = getattr(coord, "task_dict", None) if coord else None
        if not data:
            err = (getattr(coord, "task_dict_error", "") if coord else "") \
                or "字典尚未获取（可能首次启动未联网，或服务端未返回）"
            return web.json_response({"ok": False, "error": err})
        payload = {
            "ok": True,
            "saved_at": data.get("saved_at"),
            "summary": _td.describe(data),
            "conditions": data.get("conditions") or [],
            "actions": data.get("actions") or [],
        }
        return web.json_response(payload)

async def _car_identity(hass, coordinator=None, li_api=None) -> tuple[str, str]:
    """取 (modelId, colorCode) —— 车模图匹配用。

    ★ 2026-10-12：优先从车辆信息的**落盘缓存**读（7 天有效），
      避免每次刷新卡片都联网 —— 联网会走 saos_vehicle token 回退，
      **顶掉用户手机 App**（单设备登录），代价太大。
    实测返回里这两个字段是平级的：
        modelId=100167931652606785、colorCode=FA9
    """
    info = (getattr(coordinator, "data", None) or {}) if coordinator else {}
    mid = info.get("car_model_id") or ""
    col = info.get("car_color_code") or ""
    if mid and col:
        return str(mid), str(col)
    # 回退：读车辆信息缓存（同步 IO → 丢executor）
    try:
        from .vehicle_role import current_vehicle as _cv

        def _read() -> tuple[str, str]:
            cd = getattr(getattr(hass, "config", None), "path", "")
            cd = cd() if callable(cd) else (cd or "")
            v = _cv(li_api, cd) or {}
            vi = v.get("vehicleInfo") or {}
            return str(v.get("modelId") or vi.get("modelId") or ""), \
                   str(vi.get("colorCode") or "")

        if li_api is not None:
            m, c = await hass.async_add_executor_job(_read)
            if m:
                return m, c
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("读取车型/色码失败（首页将无车模图）: %s", err)
    return str(mid or ""), str(col or "")


class LiXiangCarImageView(HomeAssistantView):
    """车模图信息（★ 2026-10-12）。

    卡片只能访问 hass（拿不到 coordinator），所以车型/车漆信息必须经 REST 出去。
    路径：/lixiang_auto/car-image.json
      返回 {ok:true, model_id, color_code, vertical:{key,url,cached,path}, minicon:{…}}
            {ok:false, error:"..."}

    ★ 图片本身走静态目录 /lixiang_car/<modelId>/<file>，由卡片直接 <img> 引用。
    ★ 未缓存时这里会顺带触发一次异步下载（首次可能有几百毫秒延迟）。
    """

    url = "/lixiang_auto/car-image.json"
    name = "api:lixiang_auto:car_image"
    requires_auth = False      # 与 asset-version 一致：不含敏感信息

    def __init__(self, hass: HomeAssistant, coordinator=None, li_api=None) -> None:
        self.hass = hass
        self._coordinator = coordinator
        self._li_api = li_api

    async def get(self, request: web.Request) -> web.Response:
        try:
            from . import car_image as _ci
        except Exception as err:  # noqa: BLE001
            return web.json_response({"ok": False, "error": f"模块不可用：{err}"[:160]})
        mgr: _ci.CarImageManager | None = self.hass.data.get("lixiang_auto__car_image")
        if mgr is None:
            return web.json_response({"ok": False, "error": "车模图管理器未就绪"})
        model_id, color = await _car_identity(self.hass, self._coordinator, self._li_api)
        if not model_id:
            return web.json_response({"ok": False, "error": "未取到车型信息"})
        out: dict[str, Any] = {"ok": True, "model_id": model_id, "color_code": color}
        try:
            for kind in (_ci.KIND_VERTICAL, _ci.KIND_MINICON):
                got = await mgr.async_ensure(model_id, kind, color or None)
                if got:
                    got = dict(got)
                    got.pop("url", None)          # 不外传CDN 地址（无必要）
                    got["static"] = (
                        f"/lixiang_car/{got['model_id']}/"
                        f"{got['kind']}_{got['key']}.png"
                    ) if got.get("cached") else ""
                    out[kind] = got
                # ★ 横版（由竖图逆时针旋转 90° 派生，车头朝左）—— 卡片横容器优先用
                if kind == _ci.KIND_VERTICAL and got and got.get("cached"):
                    hpath = mgr.local_horizontal_path(model_id, got["key"])
                    if hpath.is_file():
                        out["horizontal"] = {
                            "model_id": str(model_id), "key": got["key"],
                            "kind": "horizontal", "cached": True, "path": str(hpath),
                            "static": f"/lixiang_car/{model_id}/horizontal_{got['key']}.png",
                        }
        except Exception as err:  # noqa: BLE001
            return web.json_response({"ok": False, "error": str(err)[:160]})
        return web.json_response(out)


async def _async_enable_ui_required_entities(hass: HomeAssistant) -> int:
    """启用「前端页面需要、但被诊断类规则默认禁用」的实体（2026-10-12）。

    背景
    ----
    诊断类信号默认禁用（`entity_registry_enabled_default=False`）是为了减少实体数量，
    但其中 6 个是**前端页面直接要用**的：

        陪伴里程 / 陪伴天数 / 耗电行驶 → 能耗页缺 3 项
        位置服务（地址）              → 位置页无地址
        场景模式                      → 情景页 0/1 字段
        车辆配置（车型）              → 钥匙管理页缺车型

    车主报「二级页面内容错误」，实测根因就是这个（实体存在但前端 `hass.states`
    里没有 → auto-bind 取不到 → 页面显示「—」）。

    ★ 安全边界：**只动 `disabled_by == "integration"`**（集成自己的默认值），
      绝不碰 `"user"` —— 用户主动禁用的实体必须保持禁用。
    """
    try:
        from .signals import UI_REQUIRED_KEYS

        reg = er.async_get(hass)
        enabled = 0
        for entry_obj in list(reg.entities.values()):
            if entry_obj.platform != DOMAIN:
                continue
            # ★ 兼容枚举与字符串两种形态（不同 HA 版本/存储反序列化结果不同）
            _dis = entry_obj.disabled_by
            if _dis != er.RegistryEntryDisabler.INTEGRATION and str(_dis) not in (
                    "integration", "RegistryEntryDisabler.INTEGRATION"):
                continue          # ★ 只处理集成默认禁用的（不碰用户手动禁用的）
            uid = entry_obj.unique_id or ""
            if not any(k in uid for k in UI_REQUIRED_KEYS):
                continue
            reg.async_update_entity(entry_obj.entity_id, disabled_by=None)
            enabled += 1
        if enabled:
            _LOGGER.info("已启用 %d 个前端页面所需的诊断类实体", enabled)
        return enabled
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("启用 UI 所需实体失败: %s", err, exc_info=True)
        return 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ★ 前端卡片静态资源（7 个自定义卡片随集成发布）
    #   URL: /lixiang_auto/lixiang-cards/<name>.js
    #   放在 entry 开头：只注册一次，且卡片不可用不应影响集成
    # ★ 2026-10-12：启用前端页面需要的诊断类实体（老版本注册时被禁用，
    #   导致二级页面拿不到数据）。只动集成自己禁用的，不动用户禁用的。
    await _async_enable_ui_required_entities(hass)
    try:
        from pathlib import Path as _Path

        from homeassistant.components.http import StaticPathConfig

        _cards_dir = _Path(__file__).parent / "www"
        if _cards_dir.is_dir():
            await hass.http.async_register_static_paths([
                StaticPathConfig("/lixiang_auto", str(_cards_dir), False),
            ])
            _LOGGER.debug("已注册前端卡片静态路径: /lixiang_auto → %s", _cards_dir)

            # ★ 2026-10-14：**自动注入前端卡片资源**，用户无需手工注册 Lovelace 资源。
            #
            # 背景：HACS 不会替自定义集成注册前端资源，用户必须自己到
            # 「设置 → 仪表盘 → 资源」里逐条添加；漏加就只显示第一个界面、
            # 其余页面点不动（车主反馈"其他用户只能用第一个界面"）。
            # 这里用 HA 官方 frontend.add_extra_js_url 注入：
            #   · 只注入「总卡片外壳」——它内部按需 import 全部子页面，
            #     所以一个资源即可覆盖 13 个页面（已实测：单资源 → 13/13 加载成功）
            #   · 另注入「车辆总览卡」（独立单卡，用户可能单独使用）
            # 手工注册过也没关系：HA 对重复 URL 去重，卡片列表也做了去重。
            try:
                if "frontend" in hass.config.components:
                    from homeassistant.components.frontend import add_extra_js_url

                    # ★ 2026-10-14：优先注入**单文件版**（scripts/build-cards.mjs 生成）
                    #   —— 1 个资源即含全部卡片，没有相对路径依赖（车主："不能合成一个？"）。
                    #   单文件不存在时（老部署）回退为逐个模块注入。
                    _bundle = _cards_dir / "lixiang-cards" / "lixiang-all.js"
                    # ★ 2026-10-14：必须带 cache-buster。
                    #   HA 的静态文件只给 Etag/Last-Modified、**没有 Cache-Control**，
                    #   浏览器会走启发式缓存（甚至不校验），升级后用户仍拿到旧模块 ——
                    #   车主的"我看到的没变化"就是这个原因（服务端已经是新文件）。
                    #   用文件 mtime 当令牌：每次部署 URL 都变 → 必然重新拉取。
                    try:
                        _tok = str(int(_bundle.stat().st_mtime))
                    except OSError:
                        _tok = "0"
                    _names = (
                        [_bundle.name] if _bundle.is_file() else list(_CARD_MODULES)
                    )
                    _urls = [
                        f"/lixiang_auto/lixiang-cards/{n}?v={_tok}" for n in _names
                    ]
                    for _url in _urls:
                        add_extra_js_url(hass, _url)
                    _LOGGER.debug("已自动注入前端卡片资源 %d 个（%s）",
                                  len(_urls), "单文件" if _bundle.is_file() else "多文件")
            except Exception as _ferr:  # noqa: BLE001
                _LOGGER.debug("自动注入前端资源失败（用户可手工注册）: %s", _ferr)

            # ★ 2026-10-12：官方静态车模图缓存目录（按需下载，见 car_image.py）。
            #   挂在 /lixiang_car 下，卡片直接 <img src="/lixiang_car/…"> 引用。
            try:
                from .car_image import CarImageManager as _CIM

                _car_dir = _Path(hass.config.config_dir) / "lixiang-car"
                _mgr = _CIM(hass, _car_dir)
                hass.data["lixiang_auto__car_image"] = _mgr
                # ★ 2026-10-16 修（车主："车辆图片经常显示不出来，有时候显示了过会儿又没了"）：
                #   ① 原来只在目录已存在时才注册 → 首次安装/清缓存后目录还没建，
                #      `/lixiang_car/...` 会 404 **直到下次 HA 重启**（时有时无的根因之一）。
                #      改为先建目录、**无条件注册**。
                #   ② `cache_headers=False` → 响应不带缓存头（实测只有 ETag/Last-Modified），
                #      手机每次渲染都要重拉 224KB 大图，网络一抖就"显示不出来"。
                #      改为 True：静态图按 URL（含车型+色码）长缓存，命中后秒出。
                try:
                    _car_dir.mkdir(parents=True, exist_ok=True)
                except Exception:  # noqa: BLE001
                    pass
                await hass.http.async_register_static_paths([
                    StaticPathConfig("/lixiang_car", str(_car_dir), True),
                ])
                _LOGGER.debug("已注册车模图静态路径: /lixiang_car → %s（长缓存）", _car_dir)
            except Exception as _cerr:  # noqa: BLE001
                _LOGGER.debug("注册车模图静态路径失败（首页将无车模图）: %s", _cerr)
            # ★ 资源版本号（cache-buster）：卡片据此给静态资源加 ?v=
            try:
                hass.http.register_view(LiXiangAssetVersionView())
            except Exception as _verr:  # noqa: BLE001
                _LOGGER.debug("注册资源版本视图失败（卡片缓存可能不刷新）: %s", _verr)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册前端卡片静态路径失败（不影响集成功能）: %s", err)

    """从配置条目设置理想汽车集成."""
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)

    # ★ 2026-10-10「去 iPad 化」：不再回填内置 DEFAULT_*（已删除）；
    #   条目自带签名身份，缺失=数据损坏 → 告警（不静默回填他人身份）。
    hac_key = entry.data.get(CONF_HAC_KEY) or ""
    key_id = entry.data.get(CONF_KEY_ID) or ""
    xdev = entry.data.get(CONF_XDEV) or ""
    app_token = entry.data.get(CONF_APP_TOKEN) or DEFAULT_APP_TOKEN
    device_id = entry.data.get(CONF_DEVICE_ID) or DEFAULT_DEVICE_ID
    vin = entry.data.get(CONF_VIN)
    if not (hac_key and key_id and xdev):
        _LOGGER.error(
            "条目 %s 缺少签名身份（hac_key/key_id/x_chj_deviceid）—— "
            "请删除该条目后重新添加以重新派生", entry.entry_id)
    app_type = entry.data.get(CONF_APP_TYPE) or APP_LIXIANG

    signer = LiCarSigner(hac_key=hac_key, key_id=key_id, device_id=xdev)
    client = LiCarClient(session, signer, app_token=app_token, vin=vin)

    li_api = None
    phone = entry.data.get(CONF_PHONE)
    password = entry.data.get(CONF_PASSWORD)
    if phone and password:
        from .li_api import LiApiClient
        _LOGGER.info(
            "条目 %s 身份来源=%s", entry.entry_id[:8],
            "理想同学" if app_type == APP_LIVIS else "理想汽车")

        # ★ 2026-10-02 持久化：token 轮换后回写 config entry
        #   此前缺陷：_login()/refresh() 的新 token 只存内存，
        #   重启后读回首次登录的旧值 → refresh_token 轮换即失效
        #   → 每次重启都要密码重登（有风控风险）。
        async def _apply_patch(patch: dict) -> None:
            """（事件循环内）真正写 config entry。

            ★ 必须是 async：hass.add_job(同步函数) 会在【调用者线程】就地执行，
              协程才会被投递到事件循环。
            """
            try:
                cur = {k: entry.data.get(k) for k in patch}
                if all(cur.get(k) == v for k, v in patch.items()):
                    return
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **patch})
                # ★ 2026-10-10：身份被迁移（老条目 → 本设备派生身份）时，
                #   已按旧身份构造的签名器必须同步更新 —— 否则
                #   coordinator 的 client.update() 仍用旧身份签名。
                if patch.get(CONF_HAC_KEY):
                    try:
                        signer.update_identity(
                            patch[CONF_HAC_KEY], patch.get(CONF_KEY_ID) or key_id,
                            patch.get(CONF_XDEV) or xdev)
                    except Exception as _e:  # noqa: BLE001
                        _LOGGER.warning("更新签名器身份失败: %s", _e)
                _LOGGER.debug("已回写 token: %s", list(patch))
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("回写 token 失败: %s", err)

        def _persist_tokens(patch: dict) -> None:
            """把新 token 写回 config entry（仅在有变化时）。

            ★ 关键：本函数在【executor 线程】被调用（_login 是同步的），
              而 async_update_entry 必须在事件循环线程 → 用 add_job 投递。
              否则 HA 报 "Detected that custom integration calls
              hass.config_entries.async_update_entry from a thread"。
            """
            try:
                hass.add_job(_apply_patch, patch)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("投递 token 回写失败: %s", err)

        li_api = LiApiClient(
            phone=phone, password=password, vin=vin or "",
            hac_key=hac_key, key_id=key_id, xdev=xdev,
            app_token=app_token, device_id=device_id,
            on_token_update=_persist_tokens,
            app_type=app_type,
            # ★ 标记为空 = v1.4.7 之前的老条目（内置抓包身份）→ 登录后迁移
            identity_source=entry.data.get(CONF_IDENTITY_SOURCE) or "",
            # ★ 2026-10-10：复用上次存下的登录会话 cookie（重启不再密码登录）
            session_cookies=entry.data.get(CONF_SESSION_COOKIES) or None,
            # ★ 2026-10-10：这两个 token 之前【只写不读】—— entry 里存着，
            #   但启动时从不传回客户端 → 重启后 self._refresh_token/_main_bearer
            #   都是空 → travel/充电 首次调用必然走 _login()（密码登录 = 可能顶掉手机 App），
            #   且 v1.4.10 的「refresh_token 免密续期」在启动路径上永远不会生效。
            refresh_token=entry.data.get(CONF_REFRESH_TOKEN) or "",
            main_bearer=(entry.data.get(CONF_MAIN_BEARER)
                         or entry.data.get(CONF_ACCESS_TOKEN) or ""),
        )
    else:
        _LOGGER.warning(
            "lixiang_auto 未配置密码登录 (phone/password 缺失), "
            "仅提供静态车辆信息, 无实时信号."
        )

    coordinator = LiCarCoordinator(hass, client, li_api=li_api, entry=entry)

    # 首次刷新（验证凭据）
    await coordinator.async_config_entry_first_refresh()
    # ★ 2026-10-11：加载任务条件/动作字典（读本地 → 立即可用；后台按新鲜度刷新）。
    #   放在 first_refresh 之后：此时 hass/lifecycle 就绪，且不阻塞集成加载
    #   （字典缺失只影响「新建任务」表单，不影响已有任务的展示与开关）。
    await coordinator.async_load_task_dict()
    # ★ 任务字典视图：卡片只能访问 hass（拿不到 coordinator）→ 必须经 REST。
    #   放在这里是因为需要 coordinator 已存在（注册时代码才拿得到它）。
    try:
        hass.http.register_view(LiXiangTaskDictView(hass, coordinator))
    except Exception as _tdverr:  # noqa: BLE001
        _LOGGER.debug("注册任务字典视图失败（新建任务将回退简表）: %s", _tdverr)
    # ★ 2026-10-12：车模图视图（车型 + 车漆色码 + 图片直链）
    try:
        hass.http.register_view(LiXiangCarImageView(hass, coordinator, li_api))
        _LOGGER.info("已注册车模图视图 /lixiang_auto/car-image.json")
    except Exception as _civer:  # noqa: BLE001
        _LOGGER.warning("注册车模图视图失败（首页将无车模图）: %s", _civer)

    # 车型功能探测（VSS 信号探测法; 失败则全部按不支持处理, 不影响只读实体）
    features: dict[str, bool] = {}
    vehicle_config: dict[str, str] = {}
    ability = None
    # ★ 账号角色（vehicle_role.REL_*）：失败时为 0（None），按车主处理
    _rel: int = 0
    if li_api is not None:
        try:
            from .features import detect_features, read_vehicle_config
            from .vehicle_ability import get_ability

            # ★ 2026-09-26：先拿车型能力表（读 APK 内置 JSON，与 App 一致）
            #   各平台用它决定"生成哪些实体"（如 L8/L9 的三排座椅）
            ability = await hass.async_add_executor_job(get_ability, li_api)
            # ★ 预热名称表（在 executor 里，避免事件循环读文件告警）
            from .vehicle_ability import preload_names
            await hass.async_add_executor_job(preload_names)

            # ★ 2026-09-26：车辆显示名（服务端 vehicleNickname / spu）
            #   在 executor 里取一次，缓存到 coordinator.data，
            #   各平台的 build_device_info 直接读缓存（零网络、不阻塞事件循环）
            #    ★ 传本 entry 的 VIN（多车账号必须按 VIN 匹配，不能盲取第一辆）
            from .device import vehicle_names as _veh_names
            _names = await hass.async_add_executor_job(
                _veh_names, li_api, ability, None,
                entry.data.get(CONF_VIN) or "")
            if coordinator.data is None:
                coordinator.data = {}
            coordinator.data["vehicle_name_info"] = _names
            _LOGGER.info("车辆显示名: %s (%s)", _names.get("zh"), _names.get("en"))
            features = await hass.async_add_executor_job(detect_features, li_api)
            vehicle_config = await hass.async_add_executor_job(
                read_vehicle_config, li_api)
            _LOGGER.info(
                "车型功能: 支持=%s",
                [k for k, v in features.items() if v] or "（探测失败）")
            # ★ 2026-09-28：账号角色（车主/家人共享/试驾）
            #   复刻 App 的 setupVehicleUserRelation()，见 vehicle_role.py。
            #   用途【仅限展示策略】：带只读标注的实体默认禁用，
            #   但不影响实体是否存在、也不影响能否调用。
            try:
                from .vehicle_role import (relation_label, relation_name,
                                           relation_of)
                # ★ 2026-10-11：优先用落盘缓存 —— get_vehicles 走 saos_vehicle，
                #   该 audience 白名单只认主 App client → 每次都会回退并
                #   用主 App 凭据换取 → **顶掉用户手机 App**（单设备登录）。
                #   角色信息仅用于展示策略，不值得每次付出这个代价。
                from .vehicle_role import current_vehicle as _cv
                _cd = getattr(getattr(hass, "config", None), "path", "")
                _cd = _cd() if callable(_cd) else (_cd or "")
                _veh = await hass.async_add_executor_job(
                    lambda: _cv(li_api, _cd))
                _rel = relation_of(_veh)
                _LOGGER.info(
                    "账号角色: %s (%s) — vehicleType=%s roleId=%s",
                    relation_label(_veh), relation_name(_veh),
                    (_veh or {}).get("vehicleType"),
                    (_veh or {}).get("vehicleRoleId"))
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("账号角色探测失败（按车主处理）: %s", err)
            if ability is not None and getattr(ability, "available", False):
                _LOGGER.info(
                    "车型能力表: %s (modelId=%s, %s, 温区 %s-%s)",
                    ability.desc, ability.model_id, ability.seat_layout(),
                    *ability.temp_range())
            else:
                _LOGGER.info("车型能力表: 无此车型配置，回退 VSS 探测")

            # ★ 2026-10-11：M 系（理想ONE 等老平台）未开通 VSS → 实时状态改走
            #   real-time-state（App 侧同款判定：platform == '1'）
            try:
                from .m01_state import is_m_series
                if is_m_series(ability):
                    coordinator.enable_realtime_state(True)
            except Exception as _err:  # noqa: BLE001
                _LOGGER.debug("老平台通道判定失败（忽略）: %s", _err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("车型功能探测异常（忽略）: %s", err)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator, "client": client, "li_api": li_api,
        "features": features, "vehicle_config": vehicle_config,
        "ability": ability,
        # ★ 账号角色（0=None 1=Owner 5=FamilyShared 6=Experience）
        #   见 vehicle_role.py；失败时为 0（按车主处理，不误禁用展示项）
        "vehicle_relation": _rel,
    }

    # ★ 注册服务（仅首次）
    _async_register_services(hass)

    # ★ 注册首次登录辅助页面（让用户自己过滑动验证）
    try:
        from .auth_web import async_register_login_views
        await async_register_login_views(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册登录辅助页面失败: %s", err)

    _LOGGER.info(
        "lixiang_auto 配置成功: vin=%s 实时信号=%d 条",
        vin, len((coordinator.data or {}).get("vss") or {}),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


SERVICE_WAKEUP = "wakeup"
SERVICE_REFRESH = "refresh"
SERVICE_DUMP_ABILITY = "dump_ability"
# ★ 2026-10-11：老平台车型（理想ONE/M01）实时状态通道诊断
SERVICE_DUMP_REALTIME_STATE = "dump_realtime_state"
SERVICE_GET_IOT2_JWT = "get_iot2_jwt"          # KMS 软签换长连接 JWT
SERVICE_PROBE_GFM = "probe_gfm_face"            # 验证 JWT 是否被长连接网关接受
SERVICE_PROBE_SEND_CMD = "probe_send_command"      # ★ M 系车控通道探测（不会动到车）
# ★ 2026-10-02：行程/陪伴里程查询服务（逆向自 App travel 接口）
SERVICE_GET_TRAVEL = "get_travel"
SERVICE_GET_CHARGE = "get_charge"
SERVICE_GET_SVM_PHOTO = "get_svm_photo"
SERVICE_CREATE_TASK = "create_task"
SERVICE_GET_TASKS = "get_tasks"
SERVICE_UPDATE_TASK = "update_task"
SERVICE_DELETE_TASK = "delete_task"


def _async_register_services(hass: HomeAssistant) -> None:
    """注册集成服务（幂等，只在首次调用时注册）。"""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    async def _handle_refresh(call) -> None:
        """立即刷新所有（或指定 VIN 的）条目。"""
        target_vin = (call.data or {}).get("vin")
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            coord = d.get("coordinator")
            entry = hass.config_entries.async_get_entry(eid)
            if coord is None or entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            await coord.async_request_refresh()
        _LOGGER.debug("已触发手动刷新 vin=%s", target_vin)

    async def _handle_wakeup(call) -> None:
        """唤醒车辆。"""
        target_vin = (call.data or {}).get("vin")
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            coord = d.get("coordinator")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            try:
                await hass.async_add_executor_job(api.wakeup)
                _LOGGER.info("已发送唤醒命令")
                if coord is not None:
                    await coord.async_request_refresh()
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("唤醒失败: %s", err)

    async def _handle_get_iot2_jwt(call) -> dict:
        """诊断：KMS 软签（软件 Ed25519）换取长连接 iot2 JWT。

        ★ 只读诊断：仅做签名与一次兑换请求，**不建任何长连接**。
          官方在手机本地用 SE 安全区签名，我们用 App SO 里的出厂兜底密钥做软件签名，
          服务端同样接受（实测 code=0，JWT 有效期 30 天）。

        ★ 错误码有排查价值（详见 kms_softsig 模块）：
          144001=参数组合非法 / 144011=keyId 未注册 / 144014=签名不对

        调用：lixiang_auto.get_iot2_jwt
        返回：{"ok":bool,"jwt":"<已截断>","code":..,"msg":..,"summary":{..}}
        """
        api = getattr(hass.data.get(DOMAIN, {}).get(call.data.get("entry_id"), {}) or {},
                      "li_api", None)
        if api is None:
            # 未指定 entry 时用第一个
            for _eid, _v in hass.data.get(DOMAIN, {}).items():
                if isinstance(_v, dict) and _v.get("li_api") is not None:
                    api = _v["li_api"]
                    break
        if api is None:
            return {"ok": False, "msg": "找不到已连接的条目"}

        result = await hass.async_add_executor_job(api.get_iot2_jwt)
        jwt = result.get("jwt") or ""
        _LOGGER.info("get_iot2_jwt: ok=%s code=%s msg=%s", result.get("ok"),
                     result.get("code"), result.get("msg"))
        # ★ 只回前 40 字符，不把完整 token 写进日志
        return {**result, "jwt": (jwt[:40] + "…") if len(jwt) > 40 else jwt}

    async def _handle_probe_send_command(call) -> dict:
        """★ 2026-10-19：探测 M 系（理想ONE）车控通道 —— **不会动到车**。

        手法：用【服务端一定不存在】的 cmdKey 调 send-command：
          · 返回「命令不存在」类错误 → **通道通了**（只是 cmdKey 不对）→ 换键即可
          · 返回 100035 / access_denied → **入口就拒** → 得换授权方式

        调用：lixiang_auto.probe_send_command
        参数：entry_id（可选；省略则取第一个条目）
        """
        api = None
        eid = call.data.get("entry_id")
        if eid:
            api = (hass.data.get(DOMAIN, {}).get(eid, {}) or {}).get("li_api")
        if api is None:
            for _v in hass.data.get(DOMAIN, {}).values():
                if isinstance(_v, dict) and _v.get("li_api") is not None:
                    api = _v["li_api"]
                    break
        if api is None:
            return {"error": "无可用 li_api（条目未加载？）"}
        return await hass.async_add_executor_job(api.probe_send_command)

    async def _handle_probe_gfm(call) -> dict:
        """诊断：拿 JWT 去查长连接接入点，验证它**真被网关接受**。

        只读：返回「有哪些 NFD 可连」，不建连、不订阅。

        调用：lixiang_auto.probe_gfm_face
        """
        api = getattr(hass.data.get(DOMAIN, {}).get(call.data.get("entry_id"), {}) or {},
                      "li_api", None)
        if api is None:
            for _eid, _v in hass.data.get(DOMAIN, {}).items():
                if isinstance(_v, dict) and _v.get("li_api") is not None:
                    api = _v["li_api"]
                    break
        if api is None:
            return {"accepted": False, "msg": "找不到已连接的条目"}

        result = await hass.async_add_executor_job(api.probe_gfm_face)
        _LOGGER.info("probe_gfm_face: accepted=%s http=%s code=%s faces=%s",
                     result.get("accepted"), result.get("http_status"),
                     result.get("code"), result.get("faces"))
        return result

    async def _handle_dump_realtime_state(call) -> dict:
        """诊断：探测 real-time-state（老平台车型的实时状态通道）并写盘。

        ★ 用途：理想ONE（M01）等**没有 VSS 服务**的车型，实时数据应走
          `/ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state`。
          但字段映射必须依**真实响应**建立 → 本服务把原始 JSON 写到
          `<config>/lixiang_realtime_state_<vin>.json`，用户回传即可。
          内置对照组（travel 月里程），可区分「端点不可用」与「会话/权限问题」。
        """
        import json as _json  # noqa: PLC0415
        from pathlib import Path as _Path  # noqa: PLC0415

        target_vin = (call.data or {}).get("vin")
        results: list[dict] = []
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            entry = hass.config_entries.async_get_entry(eid)
            if entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            api = d.get("li_api")
            if api is None:
                _LOGGER.warning("real-time-state 探针：该条目没有 API 客户端（无密码登录？）")
                continue
            res = await hass.async_add_executor_job(api.probe_realtime_state)
            vin = entry.data.get(CONF_VIN) or "unknown"
            out_path = _Path(hass.config.path(f"lixiang_realtime_state_{vin}.json"))

            def _write() -> None:
                out_path.write_text(_json.dumps(res, ensure_ascii=False, indent=2),
                                    encoding="utf-8")

            try:
                await hass.async_add_executor_job(_write)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("real-time-state 探针写盘失败: %s", err)
                continue
            summary = {
                k: {"ok": v.get("ok"), "code": v.get("code"),
                    "error": (v.get("error") or "")[:60] or None}
                for k, v in (res.get("attempts") or {}).items()
            }
            _LOGGER.info("real-time-state 探针 VIN=%s → %s | 已写入 %s",
                         vin, summary, out_path)
            results.append({"vin": vin, "file": str(out_path), "attempts": summary})
        if not results:
            _LOGGER.warning("real-time-state 探针：没有找到匹配的条目（检查 vin 参数）")
        return {"results": results}

    async def _handle_dump_ability(call) -> None:
        """导出车型能力表（诊断用）。

        ★ 2026-09-26 新增：把车型能力表（来自 APK 内置 JSON）写入
          `<config>/lixiang_ability_<modelId>.json`，方便：
            · 排查"为什么某个实体没出现"
            · 用户提交到 issue 帮我们支持新车型

        同时把摘要打到日志（INFO）。
        """
        import json as _json  # noqa: PLC0415
        from pathlib import Path as _Path  # noqa: PLC0415

        target_vin = (call.data or {}).get("vin")
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            entry = hass.config_entries.async_get_entry(eid)
            if entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            ab = d.get("ability")
            feats = d.get("features") or {}
            if ab is None:
                _LOGGER.warning("能力表不可用（无 modelId 或未探测）")
                continue
            try:
                dump = ab.dump()
                dump["features_detected"] = feats
                # ★ 2026-09-27：附带【整车配置表 Hpcm】——
                #   比车型能力表更精确（同款车选装不同）
                #   含 SS3/SS4 协议判定（hmi_platform）
                try:
                    from .vehicle_hpcm import get_hpcm  # noqa: PLC0415
                    _hpcm = get_hpcm(d.get("coordinator"))
                    if _hpcm.available:
                        dump["vehicle_config"] = _hpcm.dump()
                except Exception as _e:  # noqa: BLE001
                    _LOGGER.debug("Hpcm 导出跳过: %s", _e)
                out = _Path(hass.config.config_dir) / (
                    f"lixiang_ability_{ab.model_id or 'unknown'}.json")
                out.write_text(
                    _json.dumps(dump, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                _LOGGER.info(
                    "能力表已导出: %s（%s，%s）| 三排=%s 二排中=%s 冰箱=%s",
                    out, ab.desc, ab.seat_layout(),
                    ab.has("thirdLSeatSw"), ab.has("secMSeatSw"),
                    ab.is_supported("fridge"))
                # ★ Hpcm 摘要
                if dump.get("vehicle_config"):
                    _vc = dump["vehicle_config"]
                    _LOGGER.info(
                        "整车配置: hmi_platform=%s（%s）| EEA=%s | 支持 %d 项硬件",
                        _vc.get("hmi_platform"),
                        "SS4" if _vc.get("is_ss4") else "SS3",
                        _vc.get("eea"), len(_vc.get("supported") or []))
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("导出能力表失败: %s", err)

    async def _handle_get_travel(call) -> ServiceResponse:
        """查询行程/陪伴里程。

        ★ 2026-10-02：逆向自 App travel 接口（见
          lixiang-reverse/docs/SUBPAGES.md §十七）。

        参数（三选一）：
          · year + month  → 单月详情（含每日明细）
          · start_date + end_date → 时间段汇总
          · 都不传      → 各月里程汇总

        结果写入日志（INFO），同时返回到服务响应（HA 2024+ 支持）。
        """
        import json as _json  # noqa: PLC0415

        data = call.data or {}
        target_vin = data.get("vin")
        year = data.get("year")
        month = data.get("month")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        result = {}
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            try:
                if year and month:
                    r = await hass.async_add_executor_job(
                        api.get_travel_monthly, int(year), int(month))
                    kind = f"{year}-{month} 单月"
                elif start_date and end_date:
                    r = await hass.async_add_executor_job(
                        api.get_travel_daily, str(start_date), str(end_date))
                    kind = f"{start_date}~{end_date} 时间段"
                else:
                    r = await hass.async_add_executor_job(api.get_travel_months)
                    kind = "各月汇总"
                code = r.get("code")
                ok = code is None or code == 0
                payload = r.get("data") if ok else r
                result[entry.data.get(CONF_VIN) or eid] = {"kind": kind, "data": payload}
                if ok:
                    _LOGGER.info("行程查询成功(%s): %s", kind,
                                 _json.dumps(payload, ensure_ascii=False)[:400])
                else:
                    _LOGGER.warning("行程查询失败(%s): code=%s msg=%s", kind,
                                    code, r.get("message") or r.get("msg"))
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("行程查询异常: %s", err)
                result[entry.data.get(CONF_VIN) or eid] = {"error": str(err)}
        return result

    async def _handle_get_charge(call) -> ServiceResponse:
        """查询充电记录。

        ★ 2026-10-02：与行程同一根因（App 头 + 主 Bearer）。
          详见 lixiang-reverse/docs/SUBPAGES.md §十七 / §十八。

        参数：
          · dt ("年-月") + charging_type → 某月明细
          · 都不传 → 按月统计（次数 + 总电量）

        ★ 2026-10-09：服务端按账号角色限制 —— 家人/试驾账号调用会返回明确原因，
          而不是让服务端回 401/100105（用户改不了，不该伪装成故障）。
        """
        import json as _json  # noqa: PLC0415

        data = call.data or {}
        target_vin = data.get("vin")
        dt = data.get("dt")
        ctype = data.get("charging_type")
        result = {}
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue
            # ★ 2026-10-09 角色守卫：非车主直接给出可读原因
            #   ★ 2026-10-10：探测走 executor（事件循环里同步 HTTP 会
            #     中断整个条目遍历 → 服务返回空 []，实测事故）
            if await _is_non_owner_async(hass, api):
                result[entry.data.get(CONF_VIN) or eid] = {
                    "error": _OWNER_ONLY_NOTICE}
                continue
            try:
                if dt:
                    # ★ 2026-10-09：默认聚合全部 4 种充电类型（1/2/3/4），
                    #   避免只能看到单一充电方式的明细（如看不到理想超充）。
                    #   charging_type 传 0 / "all" 也表示聚合；
                    #   传 1~4 则只查该类型（保持原有能力）。
                    _raw = str(ctype).strip().lower() if ctype not in (None, "") else ""
                    if _raw in ("", "0", "all", "全部"):
                        r = await hass.async_add_executor_job(
                            api.get_charge_records_monthly_all, str(dt))
                        kind = f"{dt} 明细(全部类型聚合)"
                    elif _raw in ("hpc", "理想超充", "5"):
                        # ★ App 的「理想超充」= 5C(3) + 4C/5C(4)；
                        #   此前这里直接 int(ctype) → int("hpc") 会抛异常。
                        r = await hass.async_add_executor_job(
                            api.get_charge_records_monthly_all, str(dt), (3, 4))
                        kind = f"{dt} 明细(理想超充=3+4)"
                    else:
                        ct = int(ctype)
                        r = await hass.async_add_executor_job(
                            api.get_charge_records_monthly, str(dt), ct)
                        kind = f"{dt} 明细(type={ct})"
                else:
                    # ★★ 2026-10-11 修复：按月统计必须**聚合全部 4 种类型**。
                    #   服务端 monthlyStatistics 每个 chargingType 只返回该类型，
                    #   且没有"全部"取值。此前走默认 type=1（仅 DC 直流快充）
                    #   → 只显示实际电量的约 1/3（实测 10 月 78.65 vs 真实 223.32）。
                    #   传 0 / "all" / "全部" / 不传 → 聚合；传 1~4 → 只查该类型
                    #   （对应 App 的「交流慢充 / 直流快充 / 理想超充」筛选）。
                    _raw2 = str(ctype).strip().lower() if ctype not in (None, "") else ""
                    if _raw2 in ("", "0", "all", "全部"):
                        r = await hass.async_add_executor_job(
                            api.get_charge_monthly_stats_all)
                        kind = "按月统计(全部类型聚合)"
                    elif _raw2 in ("hpc", "理想超充", "5"):
                        # App 的「理想超充」= 5C 超充(3) + 4C/5C 理想超充(4)
                        r = await hass.async_add_executor_job(
                            api.get_charge_monthly_stats_all, (3, 4))
                        kind = "按月统计(理想超充=3+4)"
                    else:
                        ct = int(ctype)
                        r = await hass.async_add_executor_job(
                            api.get_charge_monthly_stats, ct)
                        kind = f"按月统计(type={ct})"
                code = r.get("code")
                ok = code is None or code == 0
                payload = r.get("data") if ok else r
                result[entry.data.get(CONF_VIN) or eid] = {"kind": kind, "data": payload}
                if ok:
                    _LOGGER.info("充电查询成功(%s): %s", kind,
                                 _json.dumps(payload, ensure_ascii=False)[:400])
                else:
                    _LOGGER.warning("充电查询失败(%s): code=%s msg=%s", kind,
                                    code, r.get("message") or r.get("msg"))
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("充电查询异常: %s", err)
                result[entry.data.get(CONF_VIN) or eid] = {"error": str(err)}
        return result

    async def _handle_get_svm_photo(call) -> ServiceResponse:
        """查询驻车照片（SVM）的签名 URL。

        ★ 2026-10-03：从抓包逆向（lixiang-reverse/data/2026-05-05_licar_captures.json）。
          完整链路：
            ① 读 VSS `Vehicle.360Svm.Park.Filekey` 拿拍照时间
            ② 按模板构造 5 路 OSS key
            ③ 调 /ois/file/service/urls 换签名 URL → 可直接 <img src>

        参数：
          · vin     可选，多车时指定
          · time    可选，拍照时间（缺省用集成当前状态里的拍照时间）
          · angles  可选，只取部分方位（如 ["Front","Rear"]）

        返回：``{vin: {photo_time, urls: {...}, error?}}``
        """
        data = call.data or {}
        target_vin = data.get("vin")
        want_time = data.get("time")
        want_angles = data.get("angles")
        want_car_type = data.get("car_type")
        result: dict = {}
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            vin = entry.data.get(CONF_VIN) or eid
            if target_vin and (entry.data.get(CONF_VIN) or "") != target_vin:
                continue

            # ① 拍照时间：优先入参，其次从实体拿。
            #   ★ 实测（2026-10-03）：时间**不在** coordinator 的 vss 里，
            #     而在 `sensor.*_360_pai_zhao_xin_xi` 的【属性】"拍照时间" 上
            #     （sensor.py 的 extra_state_attributes 从 VSS JSON 提出来）。
            #     所以先走实体注册表，再退回 vss 原始数据。
            when = want_time
            if not when:
                # ★ 2026-10-03 修 bug：原来遍历所有实体、匹配「拍照时间」或
                #   「上报时间」属性 —— 但「上报时间」**每个实体都有**，
                #   于是先撞上了 `sensor.*_chu_shuang_mo_shi`（除霜模式），
                #   拿它的上报时间当拍照时间去构造 OSS key → 接口返回 data:{}
                #   → 卡片永远显示「图片已过期」。
                #
                #   现在只认拍照专用实体，且只认「拍照时间」属性。
                _reg = er.async_get(hass)
                for st in hass.states.async_all("sensor"):
                    eid_reg = _reg.async_get(st.entity_id)
                    if (eid_reg is None or eid_reg.platform != DOMAIN
                            or eid_reg.config_entry_id != eid):
                        continue
                    if "pai_zhao_xin_xi" not in st.entity_id:
                        continue          # 只认「360 拍照信息」实体
                    cand = (st.attributes or {}).get("拍照时间")
                    if cand:
                        when = cand
                        break
            if not when:
                # 退回：coordinator 里的 VSS 原始 JSON
                coord = d.get("coordinator")
                sig = None
                if coord is not None and getattr(coord, "data", None):
                    sig = (coord.data.get("vss") or {}).get(
                        "Vehicle.360Svm.Park.Filekey")
                raw = sig.get("value") if isinstance(sig, dict) else None
                if isinstance(raw, str):
                    try:
                        import json as _json  # noqa: PLC0415
                        when = (_json.loads(raw) or {}).get("picTime") or raw
                    except (ValueError, TypeError):
                        when = raw
            # ★ 2026-10-03 修 bug：**不要因为 when 为空就提前退出**。
            #   此前是 `if not when: continue` —— 而 when 来自实体属性，
            #   车辆离线/实体 unavailable 时它是空的，于是根本走不到
            #   下面读 VSS fileKeys 的逻辑 → 永远返回「无拍照时间」。
            #   现在：先尽力读 VSS，when 仅用于展示。
            try:
                # ★ 2026-10-03 决定性修正：**不要拼路径**。
                #   VSS `Vehicle.360Svm.Park.Filekey` 的 JSON 自带 fileKeys
                #   （App 的 XPhotoDataHandle.smali 就是这么用的）。
                #   拼路径之所以总是失败：文件名时间戳 ≠ picTime
                #   （实测 18:43:29 vs 20260903184323，差 6 秒）。
                keys = []
                raw_fk = None
                coord = d.get("coordinator")
                if coord is not None and getattr(coord, "data", None):
                    sig = (coord.data.get("vss") or {}).get(
                        "Vehicle.360Svm.Park.Filekey")
                    raw_fk = sig.get("value") if isinstance(sig, dict) else None
                # 缓存里没有 → 直接问一次服务端（VSS 缓存会滞后，实测差 3 小时）
                if not raw_fk:
                    try:
                        live = await hass.async_add_executor_job(
                            api.get_vss_state, ["Vehicle.360Svm.Park.Filekey"])
                        sig2 = (live.get("data") or live).get(
                            "Vehicle.360Svm.Park.Filekey") or {}
                        raw_fk = sig2.get("value") if isinstance(sig2, dict) else None
                    except Exception:  # noqa: BLE001
                        pass
                if raw_fk:
                    fk_map = await hass.async_add_executor_job(
                        api.svm_filekeys_from_vss, raw_fk)
                    keys = list(fk_map.values())
                    # 顺带刷新展示用的时间（VSS 里的 picTime 比实体属性新）
                    _pt = await hass.async_add_executor_job(api.svm_pic_time, raw_fk)
                    if _pt:
                        when = _pt
                if not keys and when:
                    # 兜底：真没有 fileKeys 时才按模板拼（通常拿不到）
                    keys = await hass.async_add_executor_job(
                        api.svm_photo_filekeys, when, want_car_type or "")
                if not keys:
                    result[vin] = {"error": "服务端未返回 fileKeys（先触发一次远程拍照）"}
                    continue
                # 只取要求的方位
                if want_angles:
                    keys = [k for k in keys
                            if any(f"picIn{a}.jpg" in k for a in want_angles)] or keys
                r = await hass.async_add_executor_job(api.get_svm_photo_urls, keys)
                code = r.get("code")
                ok = code is None or code == 0
                urls = {}
                if ok and isinstance(r.get("data"), dict):
                    urls = r["data"].get("urls") or r["data"]
                elif ok and isinstance(r.get("data"), list):
                    for item in r["data"]:
                        if isinstance(item, dict) and item.get("url"):
                            urls[item.get("fileKey") or item.get("key") or ""] = item["url"]
                out = {"photo_time": when, "urls": urls}
                if not ok:
                    out["error"] = f"code={code} {r.get('message') or r.get('msg') or ''}".strip()
                result[vin] = out
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("驻车照片查询异常: %s", err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:200]}
        return result

    async def _handle_create_task(call) -> ServiceResponse:
        """创建任务大师任务（HTTP /task-config/mob/save，2026-10-07 抓包实证）。

        参数：
          · name        任务名（必填）
          · actions     动作数组（必填，object/JSON 字符串均可），如
                        [{"actionType": "PowerOutlet",
                          "params": [{"key": "operation", "value": "open"}]}]
          · conditions  条件数组（可选，默认无条件），如
                        [{"conditionType": "Microphone",
                          "params": [{"key": "state", "value": "connected"}]}]
          · automate / voice_execute / run_once / enabled  可选（默认 true/false/false/true）
          · vin         多车时指定（可选）

        返回：{vin: {"configId", "configName", "response"}} 或 {vin: {"error": ...}}
        """
        from .li_api import build_task_payload

        data = call.data or {}
        conditions = data.get("conditions") or []
        actions = data.get("actions")
        # object selector 在 UI 里可能给 JSON 字符串
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        if isinstance(actions, str):
            actions = json.loads(actions)
        try:
            payload = build_task_payload(
                str(data.get("name") or ""),
                conditions,
                actions or [],
                automate=bool(data.get("automate", True)),
                voice_execute=bool(data.get("voice_execute", False)),
                run_once=bool(data.get("run_once", False)),
                enabled=bool(data.get("enabled", True)),
            )
        except (ValueError, json.JSONDecodeError, TypeError) as err:
            raise HomeAssistantError(f"任务参数错误: {err}") from err

        target_vin = data.get("vin")
        result: dict = {}
        errors = 0
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            vin = entry.data.get(CONF_VIN) or eid
            if target_vin and vin != target_vin:
                continue
            coord = d.get("coordinator")
            try:
                resp = await hass.async_add_executor_job(api.save_task, payload)
                if coord is not None and hasattr(coord, "invalidate_task_cache"):
                    coord.invalidate_task_cache()
                    await coord.async_request_refresh()
                result[vin] = {
                    "configId": payload["configId"],
                    "configName": payload["configName"],
                    "response": resp,
                }
            except Exception as err:  # noqa: BLE001
                errors += 1
                _LOGGER.error("创建任务失败 (%s): %s", vin, err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:300]}
        if not result:
            raise HomeAssistantError(await _owner_only_hint(hass, result))
        if errors and errors == len(result):
            first = next(iter(result.values()))
            raise HomeAssistantError(f"创建任务失败: {first.get('error')}")
        return result

    # ---- 任务大师服务套件（2026-10-07：查询/更新/删除，按需调用的"接口"）----

    async def _li_task_entries(target_vin):
        """→ [(vin, api, coordinator)]，按可选 vin 过滤配置条目。

        ★ 2026-10-10：改为 async（角色探测走 executor，见 _is_non_owner_async）。

        ★ 2026-10-09：非车主账号的条目会被过滤（服务端仅车主可用任务大师）。
        """
        out = []
        for eid, d in (hass.data.get(DOMAIN) or {}).items():
            if not isinstance(d, dict):
                continue
            api = d.get("li_api")
            entry = hass.config_entries.async_get_entry(eid)
            if api is None or entry is None:
                continue
            vin = entry.data.get(CONF_VIN) or eid
            if target_vin and vin != target_vin:
                continue
            # ★ 2026-10-09 角色守卫：服务端仅对【车主】开放任务大师
            #   （实测家人账号拿不到）。非车主条目不返回，
            #   由各 handler 给出「仅车主可用」的可读原因，
            #   避免服务端 401/100105 被当成可修复故障反复重试。
            #   ★ 2026-10-10：探测走 executor（同上，实测事故）。
            if await _is_non_owner_async(hass, api):
                _LOGGER.info("非车主账号，跳过任务大师请求（服务端按角色限制）")
                continue
            out.append((vin, api, d.get("coordinator")))
        return out

    def _task_fail(msg: str) -> None:
        if msg:
            raise HomeAssistantError(msg)

    async def _handle_get_tasks(call) -> ServiceResponse:
        """查询任务大师列表（完整 data，含 taskValue）。

        返回：{vin: {"count": N, "tasks": [...]}} 或 {vin: {"error": ...}}
        """
        target_vin = (call.data or {}).get("vin")
        result: dict = {}
        errors = 0
        for vin, api, _coord in await _li_task_entries(target_vin):
            try:
                tasks = await hass.async_add_executor_job(api.get_tasks)
                result[vin] = {"count": len(tasks), "tasks": tasks}
            except Exception as err:  # noqa: BLE001
                errors += 1
                _LOGGER.error("查询任务失败 (%s): %s", vin, err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:300]}
        _task_fail((await _owner_only_hint(hass, result) if not result else None))
        if errors and errors == len(result):
            raise HomeAssistantError(
                f"查询任务失败: {next(iter(result.values())).get('error')}")
        return result

    async def _handle_update_task(call) -> ServiceResponse:
        """按 config_id 更新任务（先拉线上最新，再合并覆盖字段，防止旧缓存回写）。

        可覆盖字段：name / conditions / actions / automate / voice_execute /
        run_once / enabled（不传=保持原值）。
        """
        data = call.data or {}
        config_id = str(data.get("config_id") or "").strip()
        if not config_id:
            raise HomeAssistantError(
                "update_task 需要 config_id"
                "（从任务大师传感器属性或 lixiang_auto.get_tasks 获取）")
        conditions = data.get("conditions")
        actions = data.get("actions")
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        if isinstance(actions, str):
            actions = json.loads(actions)
        target_vin = data.get("vin")
        result: dict = {}
        errors = 0
        for vin, api, coord in await _li_task_entries(target_vin):
            try:
                tasks = await hass.async_add_executor_job(api.get_tasks)
                cur = next((t for t in tasks
                            if isinstance(t, dict) and t.get("configId") == config_id),
                           None)
                if cur is None:
                    raise HomeAssistantError(
                        f"线上没有该任务: {config_id}（ vin={vin} ）")
                payload = dict(cur)
                if data.get("name") is not None:
                    payload["configName"] = str(data["name"]).strip()
                for src, dst in (("automate", "automate"),
                                 ("voice_execute", "voiceExecute"),
                                 ("run_once", "runOnce"),
                                 ("enabled", "enabled")):
                    if src in data:
                        payload[dst] = bool(data[src])
                tv = dict(payload.get("taskValue") or {})
                if conditions is not None:
                    tv["conditions"] = conditions
                if actions is not None:
                    tv["actions"] = actions
                payload["taskValue"] = tv
            except HomeAssistantError:
                raise
            except Exception as err:  # noqa: BLE001
                errors += 1
                _LOGGER.error("读取任务失败 (%s): %s", vin, err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:300]}
                continue
            try:
                resp = await hass.async_add_executor_job(api.update_task, payload)
                if coord is not None and hasattr(coord, "invalidate_task_cache"):
                    coord.invalidate_task_cache()
                    await coord.async_request_refresh()
                result[vin] = {
                    "configId": config_id,
                    "configName": payload.get("configName"),
                    "enabled": payload.get("enabled"),
                    "response": resp,
                }
            except Exception as err:  # noqa: BLE001
                errors += 1
                _LOGGER.error("更新任务失败 (%s): %s", vin, err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:300]}
        _task_fail((await _owner_only_hint(hass, result) if not result else None))
        if errors and errors == len(result):
            raise HomeAssistantError(
                f"更新任务失败: {next(iter(result.values())).get('error')}")
        return result

    async def _handle_delete_task(call) -> ServiceResponse:
        """按 config_id 删除任务。"""
        data = call.data or {}
        config_id = str(data.get("config_id") or "").strip()
        if not config_id:
            raise HomeAssistantError(
                "delete_task 需要 config_id"
                "（从任务大师传感器属性或 lixiang_auto.get_tasks 获取）")
        target_vin = data.get("vin")
        result: dict = {}
        errors = 0
        for vin, api, coord in await _li_task_entries(target_vin):
            try:
                resp = await hass.async_add_executor_job(api.delete_task, config_id)
                if coord is not None and hasattr(coord, "invalidate_task_cache"):
                    coord.invalidate_task_cache()
                    await coord.async_request_refresh()
                result[vin] = {"configId": config_id, "response": resp}
            except Exception as err:  # noqa: BLE001
                errors += 1
                _LOGGER.error("删除任务失败 (%s): %s", vin, err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:300]}
        _task_fail((await _owner_only_hint(hass, result) if not result else None))
        if errors and errors == len(result):
            raise HomeAssistantError(
                f"删除任务失败: {next(iter(result.values())).get('error')}")
        return result

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)
    hass.services.async_register(DOMAIN, SERVICE_WAKEUP, _handle_wakeup)
    hass.services.async_register(DOMAIN, SERVICE_DUMP_ABILITY, _handle_dump_ability)
    hass.services.async_register(DOMAIN, SERVICE_GET_IOT2_JWT,
                                 _handle_get_iot2_jwt)
    hass.services.async_register(DOMAIN, SERVICE_PROBE_GFM,
                                 _handle_probe_gfm)

    hass.services.async_register(DOMAIN, SERVICE_PROBE_SEND_CMD,
                                 _handle_probe_send_command)
    hass.services.async_register(DOMAIN, SERVICE_DUMP_REALTIME_STATE,
                                  _handle_dump_realtime_state,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_TRAVEL, _handle_get_travel,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_CHARGE, _handle_get_charge,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_SVM_PHOTO, _handle_get_svm_photo,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_TASK, _handle_create_task,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_TASKS, _handle_get_tasks,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_TASK, _handle_update_task,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_TASK, _handle_delete_task,
                                  supports_response=SupportsResponse.OPTIONAL)

    _LOGGER.debug(
        "已注册服务: %s.refresh / %s.wakeup / %s.dump_ability / %s.get_travel",
        DOMAIN, DOMAIN, DOMAIN, DOMAIN)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载条目."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # ★ 清理通知轮询定时器（否则重载后 poller 叠加，重复请求）
        data = hass.data[DOMAIN].get(entry.entry_id) or {}
        poller = data.get("notify_poller")
        if poller is not None:
            try:
                poller.stop()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("停止通知轮询失败")
        hass.data[DOMAIN].pop(entry.entry_id)
        # 最后一个条目卸载时移除服务
        if not hass.data.get(DOMAIN):
            for svc in (SERVICE_REFRESH, SERVICE_WAKEUP, SERVICE_DUMP_ABILITY):
                if hass.services.has_service(DOMAIN, svc):
                    hass.services.async_remove(DOMAIN, svc)
            _LOGGER.debug("已移除服务")
    return unload_ok
