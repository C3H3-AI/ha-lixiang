"""Li Auto 数据协调器（周期轮询车辆状态）."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import scan_interval_seconds, DOMAIN, LOGGER_NAME, SCAN_INTERVAL_SECONDS
from .signals import VSS_PATHS_COMPAT as VSS_PATHS
from .signals import SIGNALS as _SIGNALS

_LOGGER = logging.getLogger(LOGGER_NAME)


#: ★ 连续多少轮「本批健康但该 key 始终缺席」才判定车型不支持。
#:   30 轮 × 5 分钟 ≈ 2.5 小时 —— 足够避开偶发丢包，又不会让用户等太久。
ABSENT_POLLS_TO_UNSUPPORTED = 30


def _jitter(seconds: int, ratio: float = 0.1) -> int:
    """给轮询间隔加 ±ratio 随机抖动。

    ★ 目的（借自风控规避实践）：
      固定节奏的请求容易被服务端识别为脚本 →
      抖动后请求分布更接近真实客户端。
    """
    import random
    delta = max(1, int(seconds * ratio))
    return max(1, seconds + random.randint(-delta, delta))


class LiCarCoordinator(DataUpdateCoordinator[dict]):
    """理想汽车数据协调器.

    数据来源:
    - 异步 LiCarClient: 车辆列表 + basics (静态信息/在线标记)
    - 同步 LiApiClient (经 executor): vss/get-batch 实时信号 (电量/续航/门锁/胎压...)
    """

    def __init__(self, hass: HomeAssistant, client, li_api=None,
                 entry=None) -> None:
        _opts = getattr(entry, "options", None)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=_jitter(scan_interval_seconds(_opts))),
            always_update=False,
        )
        self._entry = entry
        self.client = client
        self.li_api = li_api
        self.vehicles: list[dict] = []
        # ★ 按 route 分桶（多车支持）—— 单车场景等价于单值
        self._online: dict[str, bool | None] = {}       # route_id → 在线
        self._mid_freq_ts: dict[str, float] = {}        # route_id → 时间戳
        self._mid_freq_cache: dict[str, dict] = {}      # route_id → 缓存
        self._low_freq_ts: dict[str, float] = {}
        self._low_freq_cache: dict[str, dict] = {}
        # ★ 2026-10-02：充电累计量（HTTP，24h 拉一次）—— 给 HA 能源面板
        self._charge_total_ts: dict[str, float] = {}
        self._charge_total_cache: dict[str, float] = {}
        # ★ 2026-10-02：本月里程 / 本月充电量（低频 1h）—— 与 App 首页对齐
        self._month_ts: dict[str, float] = {}
        self._month_cache: dict[str, dict] = {}
        # 主 route（当前唯一支持的车；多车时扩展为遍历）
        self._route_id: str = ""

        # ★ 2026-09-24 错误处理（ROADMAP P1）:
        #   连续失败计数 → 分级处理（不打扰 → 告警 → 停止重试）
        self._fail_count: int = 0
        self._fail_notified: bool = False
        self._last_error: str = ""
        self._unsub_notify = None

        # ★ 2026-09-29：数据驱动的「车型不支持」门控
        #
        #   背景：App 的 VSS 路径清单按车型下发，某些字段只有部分车型上报
        #   （实测：Vehicle.Cabin.CLTC.EnduranceMil「总续航」在 L6 上
        #     连续 112 次轮询都【不在响应里】，而同批次的纯电/燃油续航都有值）。
        #
        #   服务端对这种路径【不报 400】，只是静默不返回 —— 所以无法用
        #   「路径无效」来门控。这里改用数据驱动：连续 N 轮「本批整体拿到数据
        #   但该 key 始终缺席」→ 判定该车型不支持 → 实体报 unavailable。
        #
        #   ★ 关键防误判：只在【本批整体健康】时计数。
        #     车睡着了会整批为空，那种情况不计数（否则会把所有实体误判掉）。
        self._absent_count: dict[str, int] = {}
        self._unsupported: set[str] = set()

    # ★ 信号分级（借自 huawei-auto-cloud 的节流策略 + 实测 ts 分析）
    #
    # 实测变化频率（2026-09-23，按信号 ts 新鲜度分层）:
    #   ① <1h   25 个  → 电量/续航/温度/胎压/车窗  【每轮必拉】
    #   ② 1-6h  30 个  → 门锁/充电状态/保养        【每轮必拉】
    #   ③ 6-24h 18 个  → 座椅加热/空调/哨兵        【每轮必拉】
    #   ④ 1-3天 22 个  → 二排座椅/胎压告警/油量    【每轮必拉，但可降频】
    #   ⑥ 7-30天 4 个  → OTA 信息                  【24 小时】
    #   ⑦ >30天 11 个  → 车辆配置/充电桩预约        【24 小时】
    #
    # 分频策略: 三档轮询间隔
    #   HIGH   → 每轮（SCAN_INTERVAL_SECONDS = 300s）
    #   MID    → 1 小时（充电配置类，变化慢但需及时）
    #   LOW    → 24 小时（车辆配置/OTA/保养类）
    #
    MID_FREQ_PREFIXES = (
        "charge_limit", "scheduled_charge_",   # 充电桩配置（很少改）
        # ★ 胎压告警/TPMS 保持【高频】（安全相关）
        # ★ 2026-09-24 移除 "seat_s"/"seat_t"（用户反馈座椅状态显示错误）：
        #   座椅是【用户主动控制】的功能 —— 点了开关就要立即看到状态。
        #   原来归到 MID（1 小时）→ 控制后要等 1 小时才能同步真实状态。
        #   "很少用" ≠ "不需要及时反馈"。
        "fridge_",                              # 冰箱（无此硬件）
        "tank_lock",                            # 油箱锁
        "sunshade",                             # 遮阳帘
        "low_battery_mode",                     # 低电模式
        "low_vol_mode", "low_vol_flag",         # 低压模式
        "charge_fault", "charge_gun_dc",        # 充电故障/直流枪
        "park_fsd",                             # 泊车进度
        "fuel_low_warning",                     # 油量告警
        "charge_gun_ac",                        # 交流充电枪（慢变）
        "charge_remain_time",                   # 剩余充电时间（慢变）
    )
    MID_FREQ_INTERVAL = 3600            # 1 小时

    LOW_FREQ_PREFIXES = (
        "ota_",                             # OTA 信息
        "maint_",                           # 保养信息
        "config_code",                      # 车辆配置（出厂固定）
        "provision_auth",                   # 激活授权
        "battery_keep_warm",                # 电池保温设置
        "park_status",                      # 泊车状态
    )
    LOW_FREQ_INTERVAL = 24 * 3600       # 24 小时

    def _rid(self) -> str:
        """当前 route_id（延迟初始化）。"""
        if not self._route_id:
            try:
                from .entity_helper import route_id_of
                self._route_id = route_id_of(config_entry=self._entry)
            except Exception:  # noqa: BLE001
                self._route_id = "default"
        return self._route_id

    # ★ 在线探测信号（借自 huawei-auto-cloud 的在线驱动轮询策略）
    #   先只查 2 个连接状态字段，离线时跳过大轮询 → 省流量、降低风控风险
    PRESENCE_PATHS = [
        "Vehicle.ConnectManager.ConnectStatus.5G",
        "Vehicle.ConnectManager.ConnectStatus.xcu",
    ]

    # ---------- 失败处理（★ 2026-09-26 补齐：此前 _notify_failure /
    #            _clear_failure 被调用但从未定义，导致每次轮询成功都抛
    #            AttributeError，所有实体变 unavailable）----------

    @property
    def health(self) -> dict:
        """健康状态（供 diagnostics 使用）。"""
        return {
            "fail_count": self._fail_count,
            "last_error": self._last_error,
            "notified": self._fail_notified,
        }

    async def _notify_failure(self, n: int) -> None:
        """连续失败达到阈值（≥5 次）→ 发 HA 持久通知（用户可见）。

        幂等：同一次连续失败只通知一次（_fail_notified 标记）。
        """
        if self._fail_notified:
            return
        try:
            from homeassistant.components import persistent_notification as pn
            pn.async_create(
                self.hass,
                f"理想汽车轮询已连续失败 {n} 次。\n\n"
                f"最后错误：{self._last_error}\n\n"
                "可能原因：网络中断 / 车辆离线 / 凭据失效。\n"
                "恢复后本通知会自动消失。",
                title="理想汽车连接异常",
                notification_id=f"lixiang_poll_fail_{self._entry.entry_id}",
            )
            self._fail_notified = True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("发通知失败（忽略）: %s", err)

    async def _clear_failure(self) -> None:
        """轮询恢复正常 → 清除持久通知。

        幂等：没有通知过就不操作。
        """
        if not self._fail_notified:
            return
        try:
            from homeassistant.components import persistent_notification as pn
            pn.async_dismiss(
                self.hass,
                notification_id=f"lixiang_poll_fail_{self._entry.entry_id}",
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("清通知失败（忽略）: %s", err)
        finally:
            self._fail_notified = False

    async def _async_online(self) -> bool | None:
        """探测车辆是否在线。True=在线 / False=离线 / None=未知。

        ★ 判定规则（实测 5G=True / xcu=False 同时出现）:
            任一通道为 True  → 在线（多通道冗余）
            全部为 False     → 离线
            无有效值         → 未知

        注：5G 与 xcu 是两条独立链路，只要一条通就算在线。
        """
        if self.li_api is None:
            return None
        try:
            r = await self.hass.async_add_executor_job(
                self.li_api.get_vss_state, self.PRESENCE_PATHS)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("在线探测失败: %s", err)
            return None

        seen = False
        for sig in (r or {}).values():
            v = sig.get("value")
            if v is None:
                continue
            seen = True
            s = str(v).lower()
            if s in ("true", "1"):
                return True          # ★ 任一通道在线即在线
        if seen:
            return False             # 全部为 False → 离线
        return None                  # 无有效值 → 未知

    async def _async_update_data(self) -> dict:
        """轮询车辆数据（在线驱动）。

        策略（借自 huawei-auto-cloud）:
          ① 先探测在线状态（只读 2 个字段）
          ② 离线 → 跳过完整轮询，保留上一帧数据
          ③ 在线 → 完整轮询
          ④ 离线→在线切换 → 立即补取（本函数天然满足）
        """
        # ★ 2026-10-02：充电累计量（低频 24h）→ HA 能源面板
        #   放在函数开头，确保任何 return 路径都能带上该字段
        _charge_kwh = None
        _month_fields = {}
        try:
            import time as _t2
            _rid2 = self._rid()
            _now2 = _t2.time()          # ★ 绝对时间（monotonic 语义不稳）
            _last2 = self._charge_total_ts.get(_rid2, 0.0)
            # ★ 成功 → 24h 后再拉；失败 → 10 分钟后重试（避免一次失败卡 24h）
            if (_now2 - _last2) > 24 * 3600 or _last2 == 0.0:
                if self.li_api is not None and hasattr(self.li_api, "get_charge_total_kwh"):
                    _fetched = await self.hass.async_add_executor_job(
                        self.li_api.get_charge_total_kwh)
                    if _fetched is not None:
                        self._charge_total_cache[_rid2] = _fetched
                        self._charge_total_ts[_rid2] = _now2
                        _LOGGER.info("充电累计量更新: %s kWh", _fetched)
                    else:
                        # 失败：10 分钟冷却后重试
                        self._charge_total_ts[_rid2] = _now2 - 24 * 3600 + 600
                        _LOGGER.warning("充电累计量拉取失败（10 分钟后重试）")
            _charge_kwh = self._charge_total_cache.get(_rid2)
        except Exception as _err2:  # noqa: BLE001
            _LOGGER.warning("充电累计量拉取异常: %s", _err2)

        # ★ 2026-10-02：本月里程 / 本月充电量（1h 刷新）—— 与 App 首页/充电页同口径
        try:
            import time as _t3
            _rid3 = self._rid()
            _now3 = _t3.time()
            _last3 = self._month_ts.get(_rid3, 0.0)
            if (_now3 - _last3) > 3600 or _last3 == 0.0:
                _mc = self._month_cache.get(_rid3) or {}
                _api3 = self.li_api
                if _api3 is not None and hasattr(_api3, "get_travel_current_month_km"):
                    _tm = await self.hass.async_add_executor_job(
                        _api3.get_travel_current_month_km)
                    if _tm is not None:
                        # ★ 2026-10-02：日明细 + 极值（供里程能耗二级页）
                        _mc["daily"] = _tm.get("daily") or []
                        _mc["single_far"] = _tm.get("single_far")
                        _mc["single_elec"] = _tm.get("single_elec")
                        _mc["single_fuel"] = _tm.get("single_fuel")
                        _mc["month_km"] = _tm.get("km")
                        _mc["month_elec_km"] = _tm.get("elec_km")
                        _mc["month_elec_kwh"] = _tm.get("elec_kwh")
                        _mc["month_fuel_l"] = _tm.get("fuel_l")
                        _mc["month_days"] = _tm.get("days")
                if _api3 is not None and hasattr(_api3, "get_charge_current_month_kwh"):
                    _tc = await self.hass.async_add_executor_job(
                        _api3.get_charge_current_month_kwh)
                    if _tc is not None:
                        _mc["month_charge_kwh"] = _tc.get("total_kwh")
                        _mc["month_charge_times"] = (
                            (_tc.get("dc_times") or 0) + (_tc.get("ac_times") or 0))
                if _mc:
                    self._month_cache[_rid3] = _mc
                    self._month_ts[_rid3] = _now3
                    _LOGGER.info("本月数据更新: 里程=%s km 充电=%s kWh",
                                 _mc.get("month_km"), _mc.get("month_charge_kwh"))
                else:
                    self._month_ts[_rid3] = _now3 - 3600 + 300   # 失败 5 分钟重试
            _mcd = self._month_cache.get(_rid3) or {}
            _month_fields = {
                "month_km": _mcd.get("month_km"),
                "month_elec_km": _mcd.get("month_elec_km"),
                "month_elec_kwh": _mcd.get("month_elec_kwh"),
                "month_fuel_l": _mcd.get("month_fuel_l"),
                "month_days": _mcd.get("month_days"),
                "month_charge_kwh": _mcd.get("month_charge_kwh"),
                "month_charge_times": _mcd.get("month_charge_times"),
                # ★ 2026-10-02：日明细与极值（供里程能耗二级页从实体属性读取）
                "month_daily": _mcd.get("daily") or [],
                "month_single_far": _mcd.get("single_far"),
                "month_single_elec": _mcd.get("single_elec"),
                "month_single_fuel": _mcd.get("single_fuel"),
            }
        except Exception as _err3:  # noqa: BLE001
            _LOGGER.warning("本月数据拉取异常: %s", _err3)
            _charge_kwh = self._charge_total_cache.get(self._rid())


        try:
            data = await self.client.update()
        except Exception as err:  # noqa: BLE001
            # ★ 2026-09-24 分级错误处理：
            #   ①②次失败 → 静默重试（网络抖动很常见）
            #   ③次起    → 记录 warning
            #   ⑤次起    → 发 HA 持久通知（用户可见）
            #   成功后    → 清除通知
            self._fail_count += 1
            self._last_error = str(err)[:200]
            n = self._fail_count

            if n < 3:
                _LOGGER.debug("轮询失败（第 %d 次，静默重试）: %s", n, self._last_error)
            elif n < 5:
                _LOGGER.warning("轮询连续失败 %d 次: %s", n, self._last_error)
            else:
                _LOGGER.error("轮询连续失败 %d 次: %s", n, self._last_error)
                await self._notify_failure(n)

            raise UpdateFailed(f"更新失败（第 {n} 次）: {err}") from err

        # 成功 → 清除失败状态
        if self._fail_count:
            _LOGGER.info("轮询恢复正常（此前连续失败 %d 次）", self._fail_count)
            await self._clear_failure()
        self._fail_count = 0
        self._last_error = ""

        if self.li_api is not None:
            # ① 在线探测
            online = await self._async_online()
            self._online[self._rid()] = online
            if online is False:
                # ② 离线 → 保留上一帧，不发起完整轮询
                prev = (self.data or {}).get("vss") if self.data else None
                data["vss"] = prev or {}
                data["vss_polled_at"] = (self.data or {}).get("vss_polled_at")
                data["vss_skipped"] = "车辆离线，跳过完整轮询"
                _LOGGER.debug("车辆离线，跳过完整轮询（保留 %d 个信号）",
                              len(data["vss"]))
                data["charge_total_kwh"] = _charge_kwh
                for _k4, _v4 in (_month_fields or {}).items():
                    data[_k4] = _v4
                return data

            # ③ 在线（或未知）→ 完整轮询（三档分频）
            import time as _t
            now = _t.monotonic()
            # ★★ 2026-09-26 修复「首次永不拉取低频信号」的 bug
            #
            #   bug：原实现用 `now - self._xxx_ts.get(rid, 0.0)` 判断是否需要拉取。
            #        首次时 dict 为空 → get 返回 0.0 → 差值 = now = time.monotonic()，
            #        即【容器/进程的运行时长】。
            #        LOW_FREQ_INTERVAL = 24h = 86400s，
            #        所以只要 HA 进程启动不到 24 小时，need_low 恒为 False，
            #        低频信号（车辆授权/OTA/保养等 23 个）【在首个 24 小时内永不拉取】，
            #        对应实体一直显示 unknown。
            #
            #   修法：首次（cache 里没有该 rid 的时间戳）强制拉取。
            #        既修了 LOW，也顺带保证 MID 首轮就有数据。
            _mid_ts = self._mid_freq_ts.get(self._rid())
            _low_ts = self._low_freq_ts.get(self._rid())
            need_mid = _mid_ts is None or (now - _mid_ts) > self.MID_FREQ_INTERVAL
            need_low = _low_ts is None or (now - _low_ts) > self.LOW_FREQ_INTERVAL

            # ★ 2026-09-24 接入 signals.py（架构方案 2.3）
            #   从「前缀匹配」改为「读 spec.freq」——
            #   新增信号只需在 signals.py 里声明 freq，无需改这里。
            #
            #   等价性：gen_signals.py 已用同样的前缀规则生成 freq，
            #          所以分组结果应与旧逻辑一致（见 tests/test_signals.py）。
            from .signals import Freq, by_freq
            hi_paths = [sp.path for sp in by_freq(Freq.HIGH)]
            mid_paths = [sp.path for sp in by_freq(Freq.MID)]
            lo_paths = [sp.path for sp in by_freq(Freq.LOW)]

            # 兜底：signals.py 里没有、但 VSS_PATHS 里有的路径
            #   （避免新增路径时被漏掉）
            _covered = set(hi_paths) | set(mid_paths) | set(lo_paths)
            for _k, _p in VSS_PATHS.items():
                if _p not in _covered:
                    hi_paths.append(_p)

            try:
                # 高频：每轮都拉
                vss = await self.hass.async_add_executor_job(
                    self.li_api.poll, hi_paths
                )
                # 中频：1 小时一次
                if need_mid and mid_paths:
                    mid_vss = await self.hass.async_add_executor_job(
                        self.li_api.poll, mid_paths)
                    self._mid_freq_cache[self._rid()] = mid_vss.get("vss") or {}
                    self._mid_freq_ts[self._rid()] = now
                    _LOGGER.debug("拉取中频信号 %d 个（充电/胎压/座椅）",
                                  len(self._mid_freq_cache))
                _mid = self._mid_freq_cache.get(self._rid())
                if _mid:
                    vss["vss"].update(_mid)

                # 低频：24 小时一次
                if need_low and lo_paths:
                    lo_vss = await self.hass.async_add_executor_job(
                        self.li_api.poll, lo_paths)
                    self._low_freq_cache[self._rid()] = lo_vss.get("vss") or {}
                    self._low_freq_ts[self._rid()] = now
                    _LOGGER.debug("拉取低频信号 %d 个（OTA/保养/配置）",
                                  len(self._low_freq_cache))
                _low = self._low_freq_cache.get(self._rid())
                if _low:
                    vss["vss"].update(_low)
                # 反转: {实体key: {"value":..,"ts":..}} 方便实体取值
                data["vss"] = {
                    key: vss["vss"][path]
                    for key, path in VSS_PATHS.items()
                    if path in vss["vss"]
                }
                # ★ 2026-09-28：虚拟别名信号（path="" + alias_signal）
                #   同一个 VSS 路径被两种消费者语义需要时（如前备箱：
                #   lock_front_trunk 是「锁」、door_front_trunk 是「门」），
                #   只声明一次路径、其余用别名复制值 ——
                #   既满足 test_paths_unique，又不重复请求同一路径。
                for _k, _spec in _SIGNALS.items():
                    _alias = getattr(_spec, "alias_signal", None)
                    if _alias and _alias in data["vss"]:
                        data["vss"][_k] = data["vss"][_alias]

                # ★ 2026-09-30：派生信号（path="" + compute）
                #   不从 VSS 取，而是用其他信号算。
                #   典型用例：range_total = PureElec + Fuel
                #   （App 反编译证实服务端不返回 EnduranceMil 路径）。
                for _k, _spec in _SIGNALS.items():
                    _compute = getattr(_spec, "compute", None)
                    if _compute and _k not in data["vss"]:
                        try:
                            import math
                            _fn = eval(_compute)
                            _raw = _fn(data["vss"])
                            data["vss"][_k] = {"value": _raw, "computed": True}
                        except Exception as _err:  # noqa: BLE001
                            _LOGGER.debug("派生信号 %s 计算失败: %s", _k, _err)

                data["vss_polled_at"] = vss.get("polled_at")

                # ★ 2026-09-29 数据驱动的车型门控（见 __init__ 里的说明）
                #   本批至少要拿到一些数据才计数；整批为空视为车辆离线/休眠。
                _got = len(data["vss"])
                if _got >= 5:          # 本批整体健康
                    for _k in VSS_PATHS:
                        if _k in data["vss"]:
                            self._absent_count.pop(_k, None)
                            self._unsupported.discard(_k)
                        else:
                            # 虚拟信号（path 为空）不算
                            if not VSS_PATHS.get(_k):
                                continue
                            _n = self._absent_count.get(_k, 0) + 1
                            self._absent_count[_k] = _n
                            if _n >= ABSENT_POLLS_TO_UNSUPPORTED:
                                if _k not in self._unsupported:
                                    _LOGGER.info(
                                        "信号 %s 连续 %d 轮未在响应中出现，"
                                        "判定该车型不支持（实体将显示为不可用）",
                                        _k, _n)
                                self._unsupported.add(_k)
                data["unsupported_keys"] = set(self._unsupported)
                # ★ 2026-09-24 修复：basics 缺失/为空时用 VSS 连接信号兜底
                #
                #   bug：原条件是 `"vehicle_status" not in data`，
                #        但 basics 实测返回 None（saos 接口对该账号返回 null）
                #        → 键不存在 → 应该兜底才对
                #        ⚠️ 但 basics 为 None 时 data["vehicle_status"] 根本没被写入
                #           （见 client.py：只有 basics 是 dict 时才写），
                #           所以这个条件实际是生效的 —— 真正的问题是
                #           它在 `if self.li_api is not None:` 的 try 块内，
                #           而 vehicle_status 的兜底需要 VSS 数据已就绪。
                #
                #   现在的实现：值缺失（None 或键不存在）都兜底，
                #   并用 5G → XCU → hu-f 依次尝试。
                if data.get("vehicle_status") is None:
                    for _k in ("online_5g", "online_xcu", "online_huf"):
                        _sig = data["vss"].get(_k)
                        if _sig and _sig.get("value") is not None:
                            _v = str(_sig["value"]).strip().lower()
                            data["vehicle_status"] = 1 if _v in ("true", "1") else 0
                            _LOGGER.debug(
                                "vehicleStatus 缺失，用 %s 兜底 → %s",
                                _k, data["vehicle_status"])
                            break

                # ★ 补充：即使 VSS 轮询失败，也尝试从 data["vss"] 的旧数据兜底
                if data.get("vehicle_status") is None:
                    for _k in ("online_5g", "online_xcu", "online_huf"):
                        _sig = (data.get("vss") or {}).get(_k)
                        if _sig and _sig.get("value") is not None:
                            _v = str(_sig["value"]).strip().lower()
                            data["vehicle_status"] = 1 if _v in ("true", "1") else 0
                            break
            except Exception as err:  # noqa: BLE001
                # 实时信号失败不拖垮静态数据 (也避免反复触发登录)
                _LOGGER.warning("VSS 实时信号轮询失败: %s", err)



        data["charge_total_kwh"] = _charge_kwh
        for _k4, _v4 in (_month_fields or {}).items():
            data[_k4] = _v4
        return data
