"""理想汽车 cover 实体 — 尾门 / 全车窗.

★ 为什么用 cover 而不是 button？
  · cover 是 HA 对"可开合设备"的标准域
    → 状态与操作合一（open/closed + open_cover/close_cover）
    → 语音助手（HA Assist）/ 第三方桥接都能识别
  · button 只有"按一下"，无状态、无开合语义

命令（全部来自 App 反编译 XHttp*Control.getParams）:
  尾门    remoteVehPlgControl  {"plgPosi":"100"} / {"plgPosi":"0"}
  车窗    remoteVehWdwControl  四窗位置 99 / 0
  ★ 前备箱 fTkC                {"lockSw":"1"}(开) / {"lockSw":"0"}(关)  ★ 2026-09-30 修正（用户实测方向反了）
  ★ 左滑门 remoteVehPlgControl  {"lSlidingDoor":"100"}(开) / {"lSlidingDoor":"0"}(关)
  ★ 右滑门 remoteVehPlgControl  {"rSlidingDoor":"100"}(开) / {"rSlidingDoor":"0"}(关)

★ 2026-09-27 新增前备箱 / 左右滑门（用户要求"全部实现"）
  来源：smali_classes11/com/chehejia/lib/vehicle/http/x/control/
        XHttpFrunkControl / XHttpLSlideDoorControl / XHttpRSlideDoorControl

状态:
  尾门  VSS door_trunk（DoorSwitchStatus.TrunkDoor，1=开，0/2/3=关）
  车窗  VSS window_main / copilot / back_left / back_right（0-100%）

⚠️ 车控会真实作用于车辆。
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN, LOGGER_NAME
from .entity_helper import route_id_of_vin
from .gate import require_control
from .device import build_device_info

_LOGGER = logging.getLogger(LOGGER_NAME)

_WIN_KEYS = ("flWindPosi", "frWindPosi", "rlWindPosi", "rrWindPosi")
_WIN_STATE_KEYS = ("window_main", "window_copilot", "window_back_left", "window_back_right")
_TRUNK_STATE_KEY = "door_trunk"
# ★ 2026-09-27：前备箱状态（App 的 XHttpStateModel.setFrunkState）
#   DoorLockStatus 编码与 DoorSwitchStatus 一致：0=上锁/关, 1=解锁/开
_FRUNK_STATE_KEY = "door_front_trunk"
# ★ 滑门状态（仅有滑门的车型，见 detect_slide_door）
_LSLIDE_STATE_KEY = "door_slide_left"
_RSLIDE_STATE_KEY = "door_slide_right"


def detect_slide_door(features: dict, hpcm) -> tuple[bool, str]:
    """判断本车型是否有【电动侧滑门】。返回 (有, 依据说明)。

    ★ 2026-09-28 新增（用户报告「L6 没有滑门」）

    滑门是【可控】能力，所以判据必须是【肯定证据】——
    按「宁可少做，也不给出虚假的可控能力」，没有证据就不建。

    两项肯定证据：
      ① features["侧滑门"] —— 来自 App 能力表 version.sideDoor（权威）
      ② Hpcm 的 hc_psd / hc_automatic_door —— 硬件自报

    ★ 明确【不】采用的旧推断（都会在 L6 上误判为"有滑门"）：
      · "door_slide_left 在 vss 里" —— vss 的键是信号 key，而该信号
        只要被轮询就在里面，轮询又【不按车型过滤】→ 恒真。
      · seat_count >= 6 —— L8/L9 是 6 座但【没有】滑门
        （App 里 sideDoor 只在 W01/W01B/W10B 为真）。

    抽成独立函数是为了**可测**：可以直接喂假 features/hpcm 断言行为，
    而不是靠对源码做子串断言（那种断言会被注释骗过，见 CONTRIBUTING）。
    """
    if bool((features or {}).get("侧滑门")):
        return True, "App能力表(sideDoor)"

    if hpcm is not None and getattr(hpcm, "available", False):
        try:
            if hpcm.has("hc_psd") or hpcm.has("hc_automatic_door"):
                return True, (f"Hpcm(hc_psd={hpcm.get('hc_psd')}, "
                              f"hc_automatic_door={hpcm.get('hc_automatic_door')})")
        except Exception:  # noqa: BLE001
            pass

    return False, ""


# ★ 2026-09-24 乐观更新有效期（秒）
#   依据：HA 轮询间隔 DEFAULT_SCAN_INTERVAL_SECONDS = 60 秒
#   取 2.5 倍轮询周期 = 150 秒 → 保证至少 2 次轮询机会让 VSS 追上
#   （过短：VSS 还没更新乐观值就失效 → 显示回退；
#     过长：服务端真实变化被掩盖过久）
OPTIMISTIC_TTL = 150.0
CMD_PLG = "remoteVehPlgControl"
CMD_WDW = "remoteVehWdwControl"
# ★ 2026-09-27：前备箱用独立 cmdKey（不是 remoteVehXxx）
#   来源 XHttpFrunkControl.getParams()：cmdKey = "fTkC"
CMD_FRUNK = "fTkC"


def _windows(pos: str | int) -> dict:
    return {k: str(pos) for k in _WIN_KEYS}


def _sig_num(vss: dict, key: str) -> float | None:
    sig = vss.get(key) or {}
    raw = sig.get("value")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


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
        _LOGGER.warning("无密码登录凭据，跳过 cover 实体")
        return
    # ★ 2026-09-27：前备箱 / 滑门按【车型能力】条件创建
    #
    #   判定依据（优先级）：
    #     ① 车型能力表（vehicle_configs/{modelId}.json 的 version 段）
    #     ② 运行时 VSS 信号（有信号 → 有硬件）
    #     ★ L6/L7（五座无滑门无前备箱）→ 不创建
    #     ★ L8/L9/MEGA（六座/MPV）→ 创建
    features = data.get("features") or {}
    ability = data.get("ability")
    vss = (coordinator.data or {}).get("vss") or {}

    entities = [
        LiCarTrunkCover(coordinator, li_api, device_info, vin),
        LiCarWindowCover(coordinator, li_api, device_info, vin),
    ]

    # ---- ★ 2026-09-27：优先用【整车配置表 Hpcm】判断 ----
    #   来源 Vehicle.HU.Diag.Hpcm 的 hc_frunk / hc_psd 等字段
    #   ★ 比车型能力表更精确（同款车选装不同）
    try:
        from .vehicle_hpcm import get_hpcm
        hpcm = get_hpcm(coordinator)
        if hpcm.available:
            data["hpcm"] = hpcm
            _LOGGER.info("整车配置表: SS4=%s 支持 %d 项硬件",
                         hpcm.is_ss4(), len(hpcm.supported_features()))
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Hpcm 解析失败（忽略）: %s", err)
        hpcm = None
    if hpcm is None:
        from .vehicle_hpcm import VehicleHpcm
        hpcm = VehicleHpcm()

    # ---- 前备箱 ----
    #   判定：Hpcm 的 hc_frunk / soft_close_frunk → 最权威
    #         能力表 version tag → 次之
    #         VSS 信号 → 兜底
    #   ★★ 判定优先级（2026-09-27 修正）：
    #     ① Hpcm 有 hc_frunk 字段 → 【权威】，直接决定（True 或 False）
    #     ② Hpcm 无该字段 → 用能力表 tag
    #     ③ 都没有 → VSS 信号兜底
    #
    #   ⚠️ 曾经踩的坑：Hpcm 判定 False 后又被兜底改回 True，
    #      导致 L6（无前备箱）错误创建实体。**权威结论必须短路**。
    frunk_ok = False
    frunk_decided = False           # ★ 是否已由权威源决定
    if hpcm.available and "hc_frunk" in hpcm.raw:
        # ★ 只用 hc_frunk 判断"有没有前备箱"！
        #   ⚠️ soft_close_frunk 是"电吸"特性，不是"有无"——
        #      实测 L6 Pro：hc_frunk="0" 但 soft_close_frunk="1"
        frunk_ok = hpcm.has("hc_frunk")
        frunk_decided = True        # ★ 短路：不再走后面的兜底
        _LOGGER.debug("Hpcm 权威判定前备箱=%s（hc_frunk=%r）",
                      frunk_ok, hpcm.get("hc_frunk"))

    if not frunk_decided and ability is not None and getattr(ability, "available", False):
        for tag in ("frunk", "frontTrunk", "electricFrunk", "FrunkSw"):
            try:
                if ability.is_configured(tag) and ability.is_supported(tag):
                    frunk_ok = True
                    frunk_decided = True
                    break
            except Exception:  # noqa: BLE001
                pass

    if not frunk_decided:
        # 回退：靠 features["前备箱"]（vehicle_ability + VSS 探测的结果）
        #
        # ★★ 2026-09-28 修复：这里原本是
        #       frunk_ok = any(k in vss for k in ("door_front_trunk",)) or ...
        #   与滑门同一类错误 —— `vss` 的键是【信号 key】，而
        #   door_front_trunk 只要被轮询就在里面，轮询又【不按车型过滤】
        #   → 这个条件恒为真，Hpcm 一旦不可用就会给【每辆车】建前备箱。
        #   现在只看 features（其本身来自 App 能力表 + VSS 硬件探测）。
        frunk_ok = bool(features.get("前备箱", False))
        _LOGGER.debug("VSS 兜底判定前备箱=%s", frunk_ok)

    if frunk_ok:
        entities.append(LiCarFrunkCover(coordinator, li_api, device_info, vin))
        _LOGGER.info("前备箱: 支持，已创建实体（判定源=%s）",
                     "Hpcm" if frunk_decided else "VSS")
    else:
        _LOGGER.debug("前备箱: 不支持，跳过")

    # ---- 左/右滑门 ----
    # ══════════════════════════════════════════════════════════════════════
    #  ★★ 2026-09-28 修复（用户报告：「L6 没有滑门」）
    #
    #  用户是对的。L6 上出现了 4 个不该存在的实体：
    #      cover.li_xiang_l6_zuo_hua_men / _you_hua_men            ← 可控！
    #      binary_sensor.li_xiang_l6_pro_zuo_hua_men / _you_hua_men
    #
    #  根因就是下面这段"信号在不在 vss 里"的判断，它有【两处】错：
    #
    #    ① `vss` 的键是【信号 key】，不是 VSS 路径 —— 所以
    #       "Vehicle.Body.SeatLDoor.InterferenceSts" 这类路径【永远不在】vss 里。
    #       那两条恒为假，看着像"没生效"，实则掩盖了第 ② 条真问题。
    #    ② "door_slide_left" 只要【被轮询】就在 vss 里，而 coordinator 的
    #       轮询路径来自 signals.by_freq()，**不按车型过滤**
    #       → 于是【每一辆车】都被判定"有滑门"。
    #
    #  L6 实测，三项证据全说"没有"：
    #      App version.sideDoor.isSupport = false
    #      features["侧滑门"]              = false
    #      Hpcm hc_psd="0" / hc_automatic_door="0"
    #  却仍然建了两个【可控】的 cover。
    #
    #  ★ 原则：滑门是可控能力。按「宁可少做，也不给出虚假的可控能力」
    #    → 必须有【肯定证据】才建，不能从"信号存在"推断硬件。
    #
    #  现在的判据（两项肯定证据，与 signals 的 requires 口径一致）：
    #     ① features["侧滑门"]（来自 App 能力表 version.sideDoor）—— 权威
    #     ② Hpcm 的 hc_psd / hc_automatic_door（硬件自报；L6 实测为 "0"）
    #  同时【删除】过去两条错误推断：
    #     · "信号在 vss 里"（轮询不按车型过滤 → 恒真）
    #     · seat_count >= 6（L8/L9 是 6 座但【没有】滑门 —— App 里 sideDoor
    #       只在 W01/W01B/W10B 为真，该启发式会误建）
    #  判据实现见 detect_slide_door()，便于单测。
    # ══════════════════════════════════════════════════════════════════════
    slide_ok, slide_src = detect_slide_door(features, hpcm)
    if slide_ok:
        _LOGGER.info("滑门: 支持（依据 %s），已创建左右实体", slide_src)
        entities.append(LiCarSlideDoorCover(coordinator, li_api, device_info, vin,
                                           side="left"))
        entities.append(LiCarSlideDoorCover(coordinator, li_api, device_info, vin,
                                           side="right"))
    else:
        _LOGGER.debug("滑门: 不支持，跳过（App sideDoor=false 且 Hpcm 无 hc_psd）")

    _LOGGER.info("cover 实体: %d 个（尾门/车窗/前备箱?/滑门?）", len(entities))
    async_add_entities(entities)


class LiCarTrunkCover(CoordinatorEntity, CoverEntity):
    """尾门（开/关 → cover，标准开合设备语义）."""

    _attr_has_entity_name = True
    _attr_name = "尾门"
    # ★ 2026-09-24 修正图标（用户反馈）：car-door 是【侧车门】（带门把手），
    #   不是尾门语义。car-back 是【从车尾看的车】，更贴合尾门。
    _attr_icon = "mdi:car-back"
    _attr_device_class = None  # 不标 garage：通用开合语义
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_cover_trunk"
        self._attr_device_info = device_info
        self._last_result: dict | None = None
        self._optimistic_closed: bool | None = None
        self._optimistic_until: float = 0.0

    @property
    def is_closed(self) -> bool | None:
        """★ 2026-09-24：乐观更新带 TTL（同 fan/switch/number 修复）"""
        import time as _t

        vss = (self.coordinator.data or {}).get("vss") or {}
        v = _sig_num(vss, _TRUNK_STATE_KEY)
        # DoorSwitchStatus.TrunkDoor: 1=开, 0/2/3=关
        vss_closed: bool | None = None if v is None else (v != 1)

        if self._optimistic_closed is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_closed is None or vss_closed != self._optimistic_closed:
                    return self._optimistic_closed
            self._optimistic_closed = None
            self._optimistic_until = 0.0

        return vss_closed

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"cmd_key": CMD_PLG}
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._send({"plgPosi": "100"}, closed=False)

    @require_control
    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._send({"plgPosi": "0"}, closed=True)

    async def _send(self, cmd_data: dict, *, closed: bool) -> None:
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_PLG, cmd_data)
            self._last_result = res
            self._optimistic_closed = closed
            import time as _t
            self._optimistic_until = _t.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", CMD_PLG, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", CMD_PLG, cmd_data, err)
            self._optimistic_closed = None
            raise
        await self.coordinator.async_request_refresh()


class LiCarWindowCover(CoordinatorEntity, CoverEntity):
    """全车窗 cover — 支持全开/全关 + 位置（开部分窗）.

    ★ 2026-09-24 位置语义改为标准 cover（便于滑条开部分窗）：
      HA position 0 = 物理全关
      HA position N = 物理开约 N%（车端 0…99）
      HA position 100 = 物理全开
      open_cover → 开窗; close_cover → 关窗; set_position → 按开度

    外部调用可走 async_physical_*（与 UI 方向无关）。
    """

    _attr_has_entity_name = True
    _attr_name = "车窗"
    # ★ 2026-09-24 修正图标（用户反馈"车窗没图标"）：
    #   ❌ mdi:car-window 在 MDI 图标库里【不存在】→ HA 显示不出图标
    #   ✅ mdi:window-closed-variant 是四格窗形，语义中性
    _attr_icon = "mdi:window-closed-variant"
    _attr_device_class = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_cover_window"
        self._attr_device_info = device_info
        self._last_result: dict | None = None
        # optimistic 存 HA position（0关…100开，与物理一致）
        self._optimistic_pos: int | None = None
        self._optimistic_until: float = 0.0

    def _physical_open_pct(self) -> float | None:
        """物理开度 0=全关 … ~99=全开；无信号返回 None。"""
        vss = (self.coordinator.data or {}).get("vss") or {}
        out: list[float] = []
        for key in _WIN_STATE_KEYS:
            v = _sig_num(vss, key)
            if v is not None:
                out.append(max(0.0, min(100.0, v)))
        if not out:
            return None
        return max(out)

    @property
    def physical_open_percent(self) -> int | None:
        """物理开度（0关…100开），供诊断用。

        ★ 2026-09-24：改为复用 current_cover_position（含 TTL 乐观逻辑），
          避免两处逻辑不一致。
        """
        return self.current_cover_position

    @property
    def current_cover_position(self) -> int | None:
        """★ 2026-09-24：乐观更新带 TTL（同 fan/switch/number 修复）"""
        import time as _t

        p = self._physical_open_pct()
        vss_pos = None if p is None else int(round(p))

        if self._optimistic_pos is not None:
            if _t.monotonic() < self._optimistic_until:
                # 车窗开合较慢，允许 3% 误差
                if vss_pos is None or abs(vss_pos - self._optimistic_pos) > 3:
                    return self._optimistic_pos
            self._optimistic_pos = None
            self._optimistic_until = 0.0

        return vss_pos

    @property
    def is_closed(self) -> bool | None:
        p = self.current_cover_position
        if p is None:
            return None
        return p <= 1

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "cmd_key": CMD_WDW,
            "physical_open_percent": self.physical_open_percent,
            "window_positions": {
                k: _sig_num((self.coordinator.data or {}).get("vss") or {}, k)
                for k in _WIN_STATE_KEYS
            },
        }
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    # ---- 物理动作（真正发给车的）----
    async def _open_windows(self, pct: int = 99) -> None:
        await self._send(pct)

    async def _close_windows(self) -> None:
        await self._send(0)

    async def async_physical_open(self, pct: int = 99) -> None:
        """物理开窗（pct 0-100）。供外部服务调用。"""
        await self._open_windows(99 if pct >= 100 else max(1, pct))

    async def async_physical_close(self) -> None:
        """物理关窗。"""
        await self._close_windows()

    @require_control
    async def async_open_cover(self, **kwargs: Any) -> None:
        """开窗（全开）。"""
        await self._open_windows(99)

    @require_control
    async def async_close_cover(self, **kwargs: Any) -> None:
        """关窗（全关）。"""
        await self._close_windows()

    @require_control
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """按开度设置：position=物理开度百分比（0关…100开）。"""
        pos = int(kwargs.get("position") or 0)
        pos = max(0, min(100, pos))
        if pos <= 0:
            await self._close_windows()
        else:
            # 车端全开为 99
            await self._open_windows(99 if pos >= 100 else pos)

    async def _send(self, physical_posi: int) -> None:
        """physical_posi: 0=关, 99≈全开。"""
        cmd_data = _windows(physical_posi)
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_WDW, cmd_data)
            self._last_result = res
            self._optimistic_pos = max(0, min(100, physical_posi))
            import time as _t2
            self._optimistic_until = _t2.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", CMD_WDW, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", CMD_WDW, cmd_data, err)
            self._optimistic_pos = None
            raise
        await self.coordinator.async_request_refresh()

# ===========================================================================
# ★ 2026-09-27 新增：前备箱 / 左右滑门（用户要求"全部实现"）
#
#   全部来自 App 反编译：
#     XHttpFrunkControl.getParams()
#       → cmdKey = "fTkC", cmdData = {"lockSw": "0"(开) / "1"(关)}
#     XHttpLSlideDoorControl.getParams()
#       → cmdKey = "remoteVehPlgControl", cmdData = {"lSlidingDoor": "100"(开) / "0"(关)}
#     XHttpRSlideDoorControl.getParams()
#       → cmdKey = "remoteVehPlgControl", cmdData = {"rSlidingDoor": "100"(开) / "0"(关)}
#
#   ★ 注意滑门的开值是 "100"（不是 "1"）—— App 源码实测
# ===========================================================================


class LiCarFrunkCover(CoordinatorEntity, CoverEntity):
    """前备箱（开/关 → cover）。

    ★ cmdKey 特殊：`fTkC`（不是 remoteVehXxx）
    ★ 状态：Vehicle.Body.DoorLockStatus.FrontTrunkDoor（锁状态）
           真正的开关状态信号 L6 没有 → 用乐观更新兜底
    """

    _attr_has_entity_name = True
    _attr_name = "前备箱"
    _attr_icon = "mdi:car-door"
    _attr_device_class = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def __init__(self, coordinator, li_api, device_info, vin: str) -> None:
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_cover_frunk"
        self._attr_device_info = device_info
        self._last_result: dict | None = None
        self._optimistic_closed: bool | None = None
        self._optimistic_until: float = 0.0

    @property
    def is_closed(self) -> bool | None:
        """★ 乐观更新带 TTL（同尾门）。"""
        import time as _t

        vss = (self.coordinator.data or {}).get("vss") or {}
        v = _sig_num(vss, _FRUNK_STATE_KEY)
        vss_closed: bool | None = None if v is None else (v != 1)

        if self._optimistic_closed is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_closed is None or vss_closed != self._optimistic_closed:
                    return self._optimistic_closed
            self._optimistic_closed = None
            self._optimistic_until = 0.0

        return vss_closed

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"cmd_key": CMD_FRUNK}
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_open_cover(self, **kwargs: Any) -> None:
        # ★ 2026-09-30 修正：用户实测 lockSw="1" 才是开
        await self._send({"lockSw": "1"}, closed=False)

    @require_control
    async def async_close_cover(self, **kwargs: Any) -> None:
        # ★ 2026-09-30 修正：用户实测 lockSw="0" 才是关
        await self._send({"lockSw": "0"}, closed=True)

    async def _send(self, cmd_data: dict, *, closed: bool) -> None:
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_FRUNK, cmd_data)
            self._last_result = res
            self._optimistic_closed = closed
            import time as _t
            self._optimistic_until = _t.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", CMD_FRUNK, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", CMD_FRUNK, cmd_data, err)
            self._optimistic_closed = None
            raise
        await self.coordinator.async_request_refresh()


class LiCarSlideDoorCover(CoordinatorEntity, CoverEntity):
    """滑门（左/右，L8/L9/MEGA 等有滑门的车型）。

    ★ cmdKey = `remoteVehPlgControl`（与尾门共用）
    ★ cmdData 用 lSlidingDoor / rSlidingDoor 区分
    ★ 开值 = "100"（不是 "1"）—— App 源码实测
    """

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def __init__(self, coordinator, li_api, device_info, vin: str, *,
                 side: str) -> None:
        """side: "left" 或 "right"。"""
        super().__init__(coordinator)
        self._api = li_api
        self._rid = route_id_of_vin(vin)
        self._side = side
        self._data_key = "lSlidingDoor" if side == "left" else "rSlidingDoor"
        self._state_key = _LSLIDE_STATE_KEY if side == "left" else _RSLIDE_STATE_KEY
        self._attr_name = "左滑门" if side == "left" else "右滑门"
        self._attr_icon = "mdi:car-door"
        self._attr_unique_id = f"{DOMAIN}_{self._rid}_cover_slide_{side}"
        self._attr_device_info = device_info
        self._last_result: dict | None = None
        self._optimistic_closed: bool | None = None
        self._optimistic_until: float = 0.0

    @property
    def is_closed(self) -> bool | None:
        import time as _t

        vss = (self.coordinator.data or {}).get("vss") or {}
        v = _sig_num(vss, self._state_key)
        vss_closed: bool | None = None if v is None else (v != 1)

        if self._optimistic_closed is not None:
            if _t.monotonic() < self._optimistic_until:
                if vss_closed is None or vss_closed != self._optimistic_closed:
                    return self._optimistic_closed
            self._optimistic_closed = None
            self._optimistic_until = 0.0

        return vss_closed

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"cmd_key": CMD_PLG, "side": self._side}
        if self._last_result is not None:
            attrs["last_command_result"] = self._last_result
        return attrs

    @require_control
    async def async_open_cover(self, **kwargs: Any) -> None:
        # ★ App 源码：滑门开值 = "100"
        await self._send({self._data_key: "100"}, closed=False)

    @require_control
    async def async_close_cover(self, **kwargs: Any) -> None:
        # ★ App 源码：滑门关值 = "0"
        await self._send({self._data_key: "0"}, closed=True)

    async def _send(self, cmd_data: dict, *, closed: bool) -> None:
        try:
            res = await self.hass.async_add_executor_job(
                self._api.send_command, CMD_PLG, cmd_data)
            self._last_result = res
            self._optimistic_closed = closed
            import time as _t
            self._optimistic_until = _t.monotonic() + OPTIMISTIC_TTL
            _LOGGER.info("车控 %s %s 已执行: %s", CMD_PLG, cmd_data, res)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("车控 %s %s 失败: %s", CMD_PLG, cmd_data, err)
            self._optimistic_closed = None
            raise
        await self.coordinator.async_request_refresh()
