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
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import (
    config_validation as cv,
    aiohttp_client,
    entity_registry as er,
)

from .client import LiCarClient
from .const import (
    CONF_APP_TOKEN,
    CONF_DEVICE_ID,
    CONF_HAC_KEY,
    CONF_KEY_ID,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_VIN,
    CONF_XDEV,
    DEFAULT_APP_TOKEN,
    DEFAULT_DEVICE_ID,
    DEFAULT_HAC_KEY,
    DEFAULT_KEY_ID,
    DEFAULT_XDEV,
    DOMAIN,
    LOGGER_NAME,
)
from .coordinator import LiCarCoordinator
from .signer import LiCarSigner

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ★ 前端卡片静态资源（7 个自定义卡片随集成发布）
    #   URL: /lixiang_auto/lixiang-cards/<name>.js
    #   放在 entry 开头：只注册一次，且卡片不可用不应影响集成
    try:
        from pathlib import Path as _Path

        from homeassistant.components.http import StaticPathConfig

        _cards_dir = _Path(__file__).parent / "www"
        if _cards_dir.is_dir():
            await hass.http.async_register_static_paths([
                StaticPathConfig("/lixiang_auto", str(_cards_dir), False),
            ])
            _LOGGER.debug("已注册前端卡片静态路径: /lixiang_auto → %s", _cards_dir)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("注册前端卡片静态路径失败（不影响集成功能）: %s", err)

    """从配置条目设置理想汽车集成."""
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)

    hac_key = entry.data.get(CONF_HAC_KEY) or DEFAULT_HAC_KEY
    key_id = entry.data.get(CONF_KEY_ID) or DEFAULT_KEY_ID
    xdev = entry.data.get(CONF_XDEV) or DEFAULT_XDEV
    app_token = entry.data.get(CONF_APP_TOKEN) or DEFAULT_APP_TOKEN
    device_id = entry.data.get(CONF_DEVICE_ID) or DEFAULT_DEVICE_ID
    vin = entry.data.get(CONF_VIN)

    signer = LiCarSigner(hac_key=hac_key, key_id=key_id, device_id=xdev)
    client = LiCarClient(session, signer, app_token=app_token, vin=vin)

    li_api = None
    phone = entry.data.get(CONF_PHONE)
    password = entry.data.get(CONF_PASSWORD)
    if phone and password:
        from .li_api import LiApiClient

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
        )
    else:
        _LOGGER.warning(
            "lixiang_auto 未配置密码登录 (phone/password 缺失), "
            "仅提供静态车辆信息, 无实时信号."
        )

    coordinator = LiCarCoordinator(hass, client, li_api=li_api, entry=entry)

    # 首次刷新（验证凭据）
    await coordinator.async_config_entry_first_refresh()

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
                _veh = await hass.async_add_executor_job(
                    lambda: (li_api.get_vehicles() or [None])[0])
                _rel = relation_of(_veh)
                _LOGGER.info(
                    "账号角色: %s (%s) — vehicleType=%s roleId=%s",
                    relation_label(_veh), relation_name(_veh),
                    (_veh or {}).get("vehicleType"),
                    (_veh or {}).get("vehicleRoleId"))
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("账号角色探测失败（按车主处理）: %s", err)
                _rel = 0
            if ability is not None and getattr(ability, "available", False):
                _LOGGER.info(
                    "车型能力表: %s (modelId=%s, %s, 温区 %s-%s)",
                    ability.desc, ability.model_id, ability.seat_layout(),
                    *ability.temp_range())
            else:
                _LOGGER.info("车型能力表: 无此车型配置，回退 VSS 探测")
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
# ★ 2026-10-02：行程/陪伴里程查询服务（逆向自 App travel 接口）
SERVICE_GET_TRAVEL = "get_travel"
SERVICE_GET_CHARGE = "get_charge"
SERVICE_GET_SVM_PHOTO = "get_svm_photo"


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
            try:
                if dt:
                    ct = int(ctype) if ctype else 1
                    r = await hass.async_add_executor_job(
                        api.get_charge_records_monthly, str(dt), ct)
                    kind = f"{dt} 明细(type={ct})"
                else:
                    r = await hass.async_add_executor_job(api.get_charge_monthly_stats)
                    kind = "按月统计"
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
                for st in hass.states.async_all("sensor"):
                    eid_reg = er.async_get(hass).async_get(st.entity_id)
                    if eid_reg is None or eid_reg.platform != DOMAIN:
                        continue
                    if eid_reg.config_entry_id != eid:
                        continue
                    attrs = st.attributes or {}
                    cand = attrs.get("拍照时间") or attrs.get("上报时间")
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
            if not when:
                result[vin] = {"error": "无拍照时间（先触发一次远程拍照）"}
                continue

            _LOGGER.debug("svm: vin=%s when=%r", vin, when, type(when).__name__)
            try:
                keys = await hass.async_add_executor_job(
                    api.svm_photo_filekeys, when)
                _LOGGER.debug("svm: 生成 %d 个 key", len(keys), keys[:2])
                if not keys:
                    result[vin] = {"error": f"拍照时间无法解析: {when!r}"}
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
                _LOGGER.info("驻车照片(%s): %d 张, time=%s", vin, len(urls), when)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("驻车照片查询异常: %s", err)
                result[vin] = {"error": f"{type(err).__name__}: {err}"[:200]}
        return result

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, _handle_refresh)
    hass.services.async_register(DOMAIN, SERVICE_WAKEUP, _handle_wakeup)
    hass.services.async_register(DOMAIN, SERVICE_DUMP_ABILITY, _handle_dump_ability)
    hass.services.async_register(DOMAIN, SERVICE_GET_TRAVEL, _handle_get_travel,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_CHARGE, _handle_get_charge,
                                  supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, SERVICE_GET_SVM_PHOTO, _handle_get_svm_photo,
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
