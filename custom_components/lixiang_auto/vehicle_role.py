"""理想汽车集成 · 账号角色（车主 / 家人共享 / 试驾）

为什么需要
----------
同一个 VIN，不同登录账号拿到的能力【不完全一样】。App 用一套
`relationType` 机制区分，我们复刻它，用于：

  · 判断当前账号是不是车主
  · 对 App 明确【隐藏】的功能，创建实体但默认禁用（而不是删除）
  · 避免给家人账号展示 App 认为不该展示的东西

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

import logging
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


def current_vehicle(li_api: Any) -> dict[str, Any] | None:
    """取当前车辆的条目（失败返回 None，不影响主流程）。"""
    try:
        veh = li_api.get_vehicles() or []
        return veh[0] if veh else None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("读取车辆条目失败（忽略）: %s", err)
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
