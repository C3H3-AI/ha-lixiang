"""理想汽车集成 · 账号角色（车主 / 家人共享 / 试驾）

为什么需要
----------
同一个 VIN，不同登录账号拿到的能力【不完全一样】。App 用一套
`relationType` 机制区分，我们复刻它，用于：

  · 判断当前账号是不是车主
  · 对 App 明确【隐藏】的功能，创建实体但默认禁用（而不是删除）
  · 避免给家人账号展示 App 认为不该展示的东西

★★ 2026-10-11 重要：车辆信息必须**落盘缓存**，不能每次重取
------------------------------------------------------------------
`get_vehicles()` 走 `saos_vehicle`（audience `7gbeHMwBPMZA5SU1b2awIo`）token，
而该 audience 的**白名单只认主 App client（lixiang）**
（li_api._exchange_client_order 注释：A/C ❌ → B/D ✅ 实测）。

后果：每次取车辆信息 → 先撞一次 livis 被拒 → **回退 lixiang client 换取**
→ 而理想账号是**单设备登录** → **顶掉用户手机 App**。
实测用户现象：「App 的任务大师无法连接，禁用集成 + 重新登录 App 才恢复」。

而本模块的角色信息**仅用于展示策略**（见上文「只用于①」），
为此每次顶掉用户 App 完全不值得 → 故加落盘缓存（默认 7 天）。

车辆条目（VIN/车型/角色）几乎不变；账号关系变化时最多 7 天同步一次。

★ 但注意（2026-09-28 实测）：App 的"限制"分三类，不要一概而论
    ① UI 隐藏但服务端放行  → 位置 / 保养 / 里程（我们实测能拿到）
    ② 服务端真拦           → OTA / 行程自定义查询（120001）
    ③ 车控命令             → 家人账号几乎无限制（30 项实测可用）

  因此本模块的角色信息【只用于①的展示策略】，
  绝不用来禁用②③ —— 那会剥夺用户本来能用的能力。

App 的原始机制（依据）
---------------------
文件：`assets/index.vehicle.js` 的 `setupVehicleUserRelation()`

```javascript
setupVehicleUserRelation(t) {
  if (t.vehicleType === 'owned') {
      t.relationType = isReceiver(t) ? Transferring : Owner;
  } else if (t.vehicleType === 'inviting') {
      t.relationType = FamilyShareInviting;
  } else if (t.vehicleType === 'authorized') {
      if (String(t.vehicleRoleId) === '15')          t.relationType = FamilySharedAuthorized;
      else if (['10','13'].includes(String(t.vehicleRoleId))) t.relationType = ExperienceDriving;
  } else if (t.vehicleType === 'owned') {
      if (state === Transferred || state === ReverseActivating) t.relationType = TransferAccepted;
      else if (state === Registered)                            t.relationType = None;
  }
}
```

枚举：`LXVehicleUserRelation`
```
None=0  Owner=1  Transferring=2  TransferAccepted=3
FamilyShareInviting=4  FamilySharedAuthorized=5  ExperienceDriving=6
```

三个互斥谓词（App 侧）：`isOwner()` / `isFamily()` / `isTestDriver()`
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

# 兼容两种导入方式（便于单测，与 translations.py 保持一致）：
#   · HA 运行时：相对导入（包内）
#   · pytest：绝对导入（conftest 已把集成目录加入 sys.path）
#
# ★ 这里刻意【不】导入 const —— const.py 会链式导入 signals，
#   而 signals 依赖 HA 运行时，导致单测无法独立导入本模块。
#   日志名直接用字符串常量（与 const.LOGGER_NAME 同值）。
try:
    from .const import LOGGER_NAME
except ImportError:  # pragma: no cover - 单测路径
    LOGGER_NAME = "custom_components.lixiang_auto"  # type: ignore[assignment]

_LOGGER = logging.getLogger(LOGGER_NAME)


# ── 角色枚举（与 App 的 LXVehicleUserRelation 数值一致）──────────────
REL_NONE = 0
REL_OWNER = 1
REL_TRANSFERRING = 2
REL_TRANSFER_ACCEPTED = 3
REL_FAMILY_INVITING = 4
REL_FAMILY_SHARED = 5
REL_EXPERIENCE = 6

#: 数值 → 稳定字符串（用于属性与测试断言）
RELATION_NAMES: dict[int, str] = {
    REL_NONE: "none",
    REL_OWNER: "owner",
    REL_TRANSFERRING: "transferring",
    REL_TRANSFER_ACCEPTED: "transfer_accepted",
    REL_FAMILY_INVITING: "family_inviting",
    REL_FAMILY_SHARED: "family_shared",
    REL_EXPERIENCE: "experience",
}

#: 中文显示名
RELATION_LABELS: dict[int, str] = {
    REL_NONE: "未注册",
    REL_OWNER: "车主",
    REL_TRANSFERRING: "过户中",
    REL_TRANSFER_ACCEPTED: "已接受过户",
    REL_FAMILY_INVITING: "家人共享邀请中",
    REL_FAMILY_SHARED: "家人共享",
    REL_EXPERIENCE: "试驾",
}

#: `authorized` 类型下，vehicleRoleId → 角色
_AUTHORIZED_ROLE_MAP: dict[str, int] = {
    "15": REL_FAMILY_SHARED,   # ★ 家人共享（App 原文硬编码 '15'）
    "10": REL_EXPERIENCE,      # ★ 试驾
    "13": REL_EXPERIENCE,      # ★ 试驾（另一个 roleId）
}


def relation_of(vehicle: dict[str, Any] | None) -> int:
    """从车辆条目推导 `relationType`（复刻 App 的 setupVehicleUserRelation）。

    参数
    ----
    vehicle : get_vehicles() 返回的单个条目，形如
        {"vehicleType": "authorized", "vehicleRoleId": 15, "vehicleState": "..."}

    返回
    ----
    REL_* 常量；无法判定时返回 REL_NONE。

    ★ 依据：`assets/index.vehicle.js` 的 `setupVehicleUserRelation()`。
      注意 App 对 `vehicleRoleId` 做的是**字符串**比较（`String(...) === '15'`），
      这里保持一致 —— 服务端有时返回数字、有时返回字符串。
    """
    if not isinstance(vehicle, dict):
        return REL_NONE

    vtype = str(vehicle.get("vehicleType") or "").strip()
    role_id = str(vehicle.get("vehicleRoleId") or "").strip()
    vstate = str(vehicle.get("vehicleState") or "").strip()

    if vtype == "owned":
        # App：过户接收方 → Transferring；特定的车辆状态 → TransferAccepted / None
        if _is_receiver(vehicle):
            return REL_TRANSFERRING
        if vstate in ("Transferred", "ReverseActivating"):
            return REL_TRANSFER_ACCEPTED
        if vstate == "Registered":
            return REL_NONE
        return REL_OWNER

    if vtype == "inviting":
        return REL_FAMILY_INVITING

    if vtype == "authorized":
        hit = _AUTHORIZED_ROLE_MAP.get(role_id)
        if hit is not None:
            return hit
        # 未知 roleId → 保守当作家人共享（比当作车主安全：
        # 只会多禁用几个展示项，不会误开高权限功能）
        _LOGGER.debug("未知 vehicleRoleId=%r（按家人共享处理）", role_id)
        return REL_FAMILY_SHARED

    return REL_NONE


def _is_receiver(vehicle: dict[str, Any]) -> bool:
    """是否过户接收方。

    ★ 依据：App 的 `isReceiver()` 在本次逆向中未取得实现体
      （只在 setupVehicleUserRelation 里被调用）。
      这里用服务端可能给的字段做保守判断：拿不到就返回 False
      （即按 Owner 处理 —— 与 App 默认分支一致）。
    """
    for key in ("isReceiver", "receiver", "isTransferReceiver"):
        if vehicle.get(key) in (True, 1, "1", "true"):
            return True
    return False


# ── 便捷谓词（与 App 的三个互斥判定一一对应）────────────────────────
def is_owner(vehicle: dict[str, Any] | None) -> bool:
    """是否车主（App: isOwner()）。"""
    return relation_of(vehicle) == REL_OWNER


def is_family(vehicle: dict[str, Any] | None) -> bool:
    """是否家人共享账号（App: isFamily()）。"""
    return relation_of(vehicle) == REL_FAMILY_SHARED


def is_test_driver(vehicle: dict[str, Any] | None) -> bool:
    """是否试驾账号（App: isTestDriver() / isExperienceDriving()）。"""
    return relation_of(vehicle) == REL_EXPERIENCE


def relation_label(vehicle: dict[str, Any] | None) -> str:
    """中文角色名（用于实体属性展示）。"""
    return RELATION_LABELS.get(relation_of(vehicle), "未知")


def relation_name(vehicle: dict[str, Any] | None) -> str:
    """稳定英文名（用于属性与测试）。"""
    return RELATION_NAMES.get(relation_of(vehicle), "unknown")


#: 车辆信息落盘文件名（放 HA 配置目录）
VEHICLE_CACHE_FILENAME = "lixiang_vehicle_info.json"

#: 缓存有效期：车辆/账号关系极少变化（★ 每次重取都会顶用户 App，见模块头注释）
VEHICLE_CACHE_TTL = 7 * 86400


def cache_path(config_dir: str) -> str:
    """缓存文件路径。

    ★ 空 config_dir 必须返回空串 —— `os.path.join("", name)` 会得到**相对路径**，
      于是文件被写到进程的当前工作目录（HA 里就是 /config 之外的随机位置）。
      宁可"不缓存"，也不要写错地方。
    """
    d = str(config_dir or "").strip()
    return os.path.join(d, VEHICLE_CACHE_FILENAME) if d else ""


def load_cached_vehicle(config_dir: str) -> dict[str, Any] | None:
    """读本地车辆信息；不存在/损坏/过期返回 None（调用方转入网取）。"""
    path = cache_path(config_dir)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.warning("车辆信息缓存损坏（将重取）: %s", err)
        return None
    if not isinstance(d, dict) or not isinstance(d.get("vehicle"), dict):
        return None
    ts = d.get("saved_at")
    if not isinstance(ts, (int, float)) or (time.time() - ts) > VEHICLE_CACHE_TTL:
        return None
    return d["vehicle"]


def save_cached_vehicle(config_dir: str, vehicle: dict[str, Any]) -> bool:
    """原子写 + 仅属主可读（与 identity.py / task_dict.py 一致）。"""
    path = cache_path(config_dir)
    if not path or not isinstance(vehicle, dict):
        return False
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"saved_at": int(time.time()), "vehicle": vehicle},
                      fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except OSError as err:
        _LOGGER.warning("保存车辆信息缓存失败: %s", err)
        return False


def current_vehicle(li_api: Any, config_dir: str = "") -> dict[str, Any] | None:
    """取当前车辆条目 —— **优先本地缓存**，避免每次换 saos_vehicle token 顶掉 App。

    ★ 2026-10-11：加了 config_dir 参数。传了就先读缓存（7 天内有效），
      命中则**完全不发请求**；未命中才联网，成功后落盘。
      不传 config_dir 时行为与旧版一致（直接联网）——保证向后兼容。
    """
    if config_dir:
        cached = load_cached_vehicle(config_dir)
        if cached:
            return cached
    try:
        veh = li_api.get_vehicles() or []
        first = veh[0] if veh else None
        if first and config_dir:
            save_cached_vehicle(config_dir, first)
        return first
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("读取车辆条目失败（忽略）: %s", err)
        # ★ 联网失败时用**过期缓存兜底** —— 有数据总比没有好，
        #   且能避免"失败→重试→再顶一次 App"的连锁。
        if config_dir:
            path = cache_path(config_dir)
            try:
                with open(path, encoding="utf-8") as fh:
                    d = json.load(fh)
                v = d.get("vehicle")
                if isinstance(v, dict):
                    _LOGGER.debug("车辆信息改用过期缓存（联网失败）")
                    return v
            except Exception:  # noqa: BLE001
                pass
        return None


# ── 展示策略：App 对家人账号【隐藏】的功能 ──────────────────────────
#: 这些 key 前缀在家人/试驾账号下应【创建但默认禁用】，并标注原因。
#:
#: ★ 重要：这里【只】列 App 明确隐藏入口的项。
#:   · 不包含任何车控（实测家人账号能用全部车控）
#:   · 不包含服务端真拦的项（那些本来就拿不到，无需处理）
#:
#: 依据：
#:   · "家人账号无法查看车辆位置和驻车照片"（App 文案）
#:   · VehicleHealthy 页的 rightTitle 对 isFamily() 返回 ''（隐藏入口）
FAMILY_HIDDEN_PREFIXES: tuple[str, ...] = (
    "location",            # 车辆位置（device_tracker）
    "charge_here",         # 充电位置（常驻位置信息）
    "remote_photo",        # 远程拍照
    "parking_photo",       # 驻车照片
    "maintain",            # 保养计划（车辆健康页对家人隐藏）
    "maintenance",
)
#: 试驾账号额外隐藏的项
TEST_DRIVER_HIDDEN_PREFIXES: tuple[str, ...] = (
    "ota",                 # 整车软件更新（App：试驾模式暂不支持该功能）
)

#: 标注文案（与 App 的行为对齐，但不删除实体）
FAMILY_HIDDEN_NOTICE = "App 对家人账号隐藏此功能入口（服务端实际允许访问）"
TEST_DRIVER_HIDDEN_NOTICE = "App 对试驾账号隐藏此功能入口"


def is_hidden_for_relation(key: str, relation: int) -> bool:
    """该信号 key 在给定角色下是否应「默认禁用 + 标注」。

    ★ 只影响【展示策略】，不影响实体是否存在，也不影响能否调用。
    """
    k = str(key or "")
    if relation in (REL_FAMILY_SHARED, REL_FAMILY_INVITING):
        return any(k == p or k.startswith(p + "_") for p in FAMILY_HIDDEN_PREFIXES)
    if relation == REL_EXPERIENCE:
        if any(k == p or k.startswith(p + "_") for p in TEST_DRIVER_HIDDEN_PREFIXES):
            return True
        return any(k == p or k.startswith(p + "_") for p in FAMILY_HIDDEN_PREFIXES)
    return False


def hidden_notice(relation: int) -> str:
    """对应角色的隐藏说明文案（无隐藏则返回空串）。"""
    if relation == REL_EXPERIENCE:
        return TEST_DRIVER_HIDDEN_NOTICE
    if relation in (REL_FAMILY_SHARED, REL_FAMILY_INVITING):
        return FAMILY_HIDDEN_NOTICE
    return ""
