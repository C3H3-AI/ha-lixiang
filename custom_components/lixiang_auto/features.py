"""理想汽车 · 车型功能探测 (features.py)

原理
----
不同车型 (L6/L7/L8/L9/MEGA) 支持的硬件功能不同。App 通过 `CLVehicleConfig`
(信号 `Vehicle.Information.ConfigCode`) 拿到编码后的配置, 再用服务端字典解码。

我们拿不到服务端字典, 但可以用【VSS 信号探测法】判断功能是否存在:
  - 车辆支持的硬件 → 该功能的所有 VSS 信号都能读到值
  - 不支持的硬件   → 整批路径返回 400 invalid_path (我们已在 get_vss_state
                     里做了容错, 不存在的路径被静默跳过)

因此: 【探测组内至少一个路径有值 → 认为支持】

用法
----
    feats = detect_features(li_api)      # 返回 {功能名: bool}
    if feats.get("冰箱"):
        ...创建冰箱实体...

实测（2026-09-23，XM01 车型）:
    ✅ 冰箱 / 哨兵 / 前备箱 / 座椅加热 / Xmode
    ❌ 旋转座椅
"""

from __future__ import annotations

import logging
from typing import Any

from .const import LOGGER_NAME
from .vehicle_ability import VehicleAbility, get_ability

_LOGGER = logging.getLogger(LOGGER_NAME)

# ============================================================================
# ★ 两种判断方式的说明（2026-09-23）
# ============================================================================
# 【App 的方式：编译期硬编码】
#   每个车型一个 StateDelegate 类，例如 LXM01StateDelegate：
#     getSupportPlateDisplay() { return 1; }              // ✅ 支持
#     getSupportFridge() { getUN_SUPPORT().invoke();
#                          throw new KotlinNothingValueException(); }  // ❌ 不支持
#   调用方 (LxVehicleHelperStateDelegate) 用 try/catch 包装：
#     try   { return delegate.getSupportFridge(); }   // 支持
#     catch { return 0; }                              // 不支持
#
#   实测 L6 (M01) 的硬编码表：
#     ✅ getSupportPlateDisplay
#     ❌ getSupportFridge / getSupportFrontTrunk /
#        getSupportRotatableSeat / getSupportAutopilot
#
#   优点: 准确（官方定义）  缺点: 需要 App 发版才能加车型
#
# 【我们的方式：运行时 VSS 探测】
#   读一组 VSS 信号，多数有有效 ts（≠"0"）判定为支持。
#   优点: 换车型无需改代码  缺点: 信号选择必须准确
#
# ⚠️ 陷阱：某些信号是【通用信号】（所有车型都上报），会造成误报。
#    例: Vehicle.Body.DoorLockStatus.FrontTrunkDoor 在所有车型都有，
#        不能用来判断"是否有前备箱"（真前备箱应有 Vehicle.Body.FrontTrunk.* 一组）
#
# 本模块策略: 【硬编码表优先, VSS 探测兜底】
#   1) 若车型在 KNOWN_FEATURES 里 → 用硬编码表（最准）
#   2) 否则 → 用 VSS 探测
# ============================================================================

# App 的硬编码功能表（从 smali 提取）
# key = 车型代号, value = {功能名: 是否支持}
KNOWN_FEATURES: dict[str, dict[str, bool]] = {
    # ⚠️ 本表必须【覆盖 FEATURE_PROBES 的所有功能】！
    #    否则未覆盖的项会继续走 VSS 探测 ——
    #    而 VSS 探测有 7 天新鲜度判据，会把"存在但久未使用"的功能误判为不支持
    #    （实测：方向盘加热被误判过）
    # ★★ 2026-09-29 更正键名：M01 → X04
    #
    #   此前用 "M01" 当键，理由是「我们车的 App 委托类叫 LXM01StateDelegate，
    #   所以我们的车属于 M01 平台」。**该推理不成立**：
    #     · 服务端实测我们车 vehicleInfo.seriesNo = 'X04'
    #       （bleModuleCode = 'XTA2B6'，modelName = '理想L6'）
    #     · App 自己的分类器把 M 与 X 当作【不同车系】：
    #         isM() = platform === '1'                     → M 系（M01B 是唯一 platform='1'）
    #         isM01AVehicle(t) = t === 'MTA0B0'            → M01A
    #         isM01BVehicle(t) = t === 'MTA1B1'/'MNA1B1'   → M01B
    #         isXVehicle(t) = t.startsWith('X')            → X 系（我们车 XTA2B6 属此）
    #       且 UI 分派也是分开的：M01A/M01B 用 M01A*/M01B*Helper，
    #       X 系与 W 系用 X01A*Helper。
    #     · 名字里带 M01 的那个委托类，是 App 里【唯一】以车型命名的
    #       StateDelegate（其余都是按通道分：BLE / LiMesh / Http）——
    #       这只能说明它是个具名实现，**不能推出我们车就是 M01**。
    #
    #   ⚠️ 下表【内容】是实车验证过的（L6 五座、方向盘加热、遮阳帘等），
    #      错的只是键名。改用服务端确认的 X04，避免与真正的 M01 车系混淆 ——
    #      这个误标一度让人（包括我）以为 M01B 就是 MEGA。
    "X04": {                      # 理想 L6（服务端系列号 X04；实车验证）
        # ---- App 硬编码的（来自 LXM01StateDelegate）----
        # ★ 2026-09-24 修正：与 App 一致
        #   LXM01StateDelegate.getSupportPlateDisplay() → getUN_SUPPORT
        "牌显": False,
        "冰箱": False,
        "前备箱": False,
        "旋转座椅": False,
        "自动驾驶": False,
        # ---- 2026-09-24 实车验证补充 ----
        # L6 是【五座】SUV（前排 2 + 二排 3，无三排）
        #   服务端对不存在的三排硬件也返回 value=0 + 有效 ts，
        #   所以不能靠信号探测，必须靠车型判断。
        "三排座椅": False,
        "二排座椅": True,         # 五座车的二排（3 座）
        "座椅加热": True,         # 前后排都有
        "方向盘加热": True,       # ★ 实车确认有（曾因 VSS 探测新鲜度误判）
        "哨兵模式": True,
        "远程拍照": True,         # 360 泊车影像
        # ★ 2026-09-24 修正：L6 确实【有】遮阳帘（用户确认）
        #   ⚠️ 之前误判为 False 的依据（"App 引用数 0"）不成立 ——
        #     那只能说明反编译代码里没找到消费者，不代表硬件不存在。
        "遮阳帘": True,
        # L6 Pro 无空气悬架 / 无电动尾翼 / 无旋转座椅
        "空气悬架": False,
        "电动尾翼": False,
    },
}

# 功能名 → 探测用 VSS 路径组（任一有值即视为支持）
# 路径来自 docs/VSS路径全集_20260922.md（实测有效 167 个）
FEATURE_PROBES: dict[str, list[str]] = {
    "冰箱": [
        "Vehicle.Cabin.Fridge.ActWorkSts",
        "Vehicle.Cabin.Fridge.ModeState",
        "Vehicle.Cabin.Fridge.CoolTempSt",
        "Vehicle.Cabin.Fridge.DlyTmRemain",
    ],
    # 注: ReserveFridge 是通用 Xmode 信号（无冰箱的车也有），不能单独用于探测。
    #     "冰箱预约" 由 "冰箱" 推导，见 detect_features 末尾。
    "哨兵模式": [
        "Vehicle.Sentry.SentinelStatus",
        "Vehicle.Sentry.SettingsStatus",
        "Vehicle.Sentry.Video.Count",
    ],
    # ★ 修正 (2026-09-23): DoorLockStatus.FrontTrunkDoor 是所有车型都有的
    #   通用锁状态信号，不能判断是否有前备箱硬件。
    #   真前备箱应有 Vehicle.Body.FrontTrunk.* 一组信号。
    #   实测 L6: 无这些信号 → 判为不支持（与 App 硬编码 getSupportFrontTrunk
    #   抛异常一致）。
    "前备箱": [
        "Vehicle.Body.FrontTrunk.Status",
        "Vehicle.Body.FrontTrunk.DoorStatus",
        "Vehicle.Body.Frunk.Status",
    ],
    "座椅加热": [
        "Vehicle.Cabin.Seat.FLSeatHeatState",
        "Vehicle.Cabin.Seat.FRSeatHeatState",
        "Vehicle.Cabin.Seat.SLSeatHeatState",
        "Vehicle.Cabin.Seat.SRSeatHeatState",
    ],
    "二排座椅": [
        "Vehicle.Cabin.Seat.SLSeatHeatState",
        "Vehicle.Cabin.Seat.SRSeatHeatState",
    ],
    # ★ 2026-09-24 新增：三排座椅（L8/L9/MEGA 有，L6/L7 无）
    #
    # ⚠️ 探测可靠性说明：
    #   服务端对【不存在的三排硬件】也返回 value=0 + 有效 ts（实测 L6），
    #   所以【信号探测无法区分】。
    #   → 因此本项优先由 KNOWN_FEATURES（车型硬编码表）决定；
    #     未知车型才退回探测（可能误判，但至少不会漏掉真有六座的车）。
    "三排座椅": [
        "Vehicle.Cabin.Seat.TLSeatHeatState",
        "Vehicle.Cabin.Seat.TRSeatHeatState",
        "Vehicle.Cabin.Seat.TMSeatHeatState",
    ],
    "旋转座椅": [
        "Vehicle.Cabin.Seat.RotatableStatus",
        "Vehicle.Seat.Rotatable.Status",
    ],
    "方向盘加热": [
        "Vehicle.Cabin.WheelWarmStatus.WarmOnOff",
    ],
    "空气悬架": [
        "Vehicle.Chassis.AirSuspension.Status",
        "Vehicle.Chassis.SuspensionHeight",
    ],
    "电动尾翼": [
        "Vehicle.Body.Spoiler.Status",
        "Vehicle.Body.RearSpoiler.Status",
    ],
    # 注: Vehicle.360Svm.ParkPhoto.State (泊车拍照) 是通用功能, 不在此探测
    # 遮阳帘（L6 有，用户确认）
    "遮阳帘": [
        "Vehicle.Body.SunshadeStatus.FrtSunshdSwSts",
        "Vehicle.Body.SunshadeStatus.RrSunshdSwSts",
    ],
    # ★ 2026-09-24 修正：原先探测路径用错
    #   错误路径（L6 无数据）：
    #     Vehicle.Camera.Photo.Status
    #     Vehicle.Camera.RemotePhoto.Status
    #   正确路径（L6 实测有数据）：
    #     Vehicle.360Svm.ParkPhoto.State   ← 泊车拍照状态
    #     Vehicle.360Svm.Park.Filekey      ← 拍照文件 key
    "远程拍照": [
        "Vehicle.360Svm.ParkPhoto.State",
        "Vehicle.360Svm.Park.Filekey",
    ],
}

# 车型编码（来自 VehicleModelCodeConst，用于日志识别）
VEHICLE_MODEL_CODES = {
    "101074633608064581": "A00",
    "952447875932008064": "M01A",
    "100204301435085761": "M01B",
    "100618542440964164": "M01B_RING_FIVE",
    "100174236664108736": "X01",
    "100618542440964163": "X02_22",
    "101492138788971191": "X02_MAX",
    "100980659723641806": "X02_PRO",
    "100980659723641805": "X03_22",
}




# ============================================================================
# ★ variableModel：中文配置串（2026-09-26 发现，比 ConfigCode 友好）
# ============================================================================
# 来源：GET /saos-vehicle-api/v2-0/vehicles/basics 的 vehicleInfo.variableModel
#
# 实测我们的车（理想L6 Pro）：
#   "AD PRO+无踏板+电池CATL+后驱汇川+伯特利后卡钳+天纳克减振器
#    +西菱增压器+德赛XCU+威孚催化剂+斯泰必鲁斯背门撑杆+无冰箱+高级音响"
#
# 相比 App 的 ConfigCode（{"vehRefrigerator":"LI2", ...} 需服务端字典翻译），
# variableModel 是【中文，直接可读】，能更可靠地判断硬件有无。
#
# ⚠️ 注意：这是【配置串】，不是【功能开关】。
#    它描述"选装了什么"，不描述"App 是否支持某功能"。
#    所以只用于硬件判断（冰箱/踏板），功能开关仍看 KNOWN_FEATURES / VSS。

# 关键词 → 功能名（出现即表示【有】该硬件）
_VM_POSITIVE = {
    "冰箱": ("冰箱", "冷藏", "冷热"),
    "空气悬架": ("空气悬架", "魔毯", "空悬"),
    "电动踏板": ("踏板",),          # 与 "无踏板" 区分，见下
    "电动尾翼": ("尾翼",),
    "高级音响": ("高级音响", "铂金音响"),
}

# 关键词 → 功能名（出现即表示【无】该硬件）
_VM_NEGATIVE = {
    "无冰箱": "冰箱",
    "无踏板": "电动踏板",
    "无空悬": "空气悬架",
    "无尾翼": "电动尾翼",
}


# ═══════════════════════════════════════════════════════════════════════════
#  信号 key 前缀 → 功能名（实体级门控）
# ═══════════════════════════════════════════════════════════════════════════
#
#  ★ 2026-09-28 从 sensor.py 提升到本模块，供 sensor / binary_sensor 共用。
#
#  背景（真实缺陷）：
#    该表原本只定义在 sensor.py 里，只在 sensor 平台生效 ——
#    binary_sensor 平台【完全没有功能门控】，于是：
#      · L6（Hpcm hc_frunk=0，无前备箱）上依然生成了
#          binary_sensor.…_qian_bei_xiang_men（前备箱门）
#          binary_sensor.…_qian_bei_xiang_suo（前备箱锁）
#      · 用户看到的"多出来的实体"就是这么来的
#    提升为共享表后，两个平台行为一致。
#
FEATURE_BY_KEY_PREFIX: dict[str, str] = {
    "fridge": "冰箱",
    "sentry": "哨兵模式",
    "lock_front_trunk": "前备箱",
    # ★ 2026-09-28 补：前备箱门（原路径无效，已修正为 DoorLockStatus.FrontTrunkDoor）
    #   实体本身仍按车型创建 —— L6 无前备箱，不该出现"前备箱门"
    "door_front_trunk": "前备箱",
    # ★ 2026-09-24 修复：座椅映射不完整
    #   问题：L6（五座）也创建了三排座椅实体
    #   原因：
    #     ① "seat_tl"/"seat_tr"/"seat_tm"/"seat_sm" 缺映射 → 不受功能过滤
    #     ② 服务端对不存在的三排硬件也返回 value=0 + 有效 ts
    #        → 信号探测无法区分 → 必须靠车型判断
    #
    #   座椅代号：F=Front(前) S=Second(二排) T=Third(三排)
    #             L=Left R=Right M=Middle
    "seat_sl": "二排座椅",
    "seat_sr": "二排座椅",
    "seat_sm": "二排座椅",     # ★ 二排中（L6 有，L8/L9 无）
    "seat_tl": "三排座椅",     # ★ 三排左（仅 L8/L9/MEGA）
    "seat_tr": "三排座椅",     # ★ 三排右
    # ★ 2026-10-02：本月耗油量 —— 增程专属（纯电车无燃油，不该显示）
    "month_fuel_l": "燃油",
    # ★ 2026-10-02：发动机里程 —— 增程专属（纯电车无发动机）
    "stat_engine_mileage": "燃油",
    "seat_tm": "三排座椅",     # ★ 三排中
    "wheel_heat": "方向盘加热",
    "spoiler": "电动尾翼",
    "suspension": "空气悬架",
    # ★ 2026-09-28 新增：燃油（增程）——用户反馈「i6 显示燃油续航」
    #   i6 = i 系列纯电（W04），无油箱，不应出现油量/燃油续航
    "fuel": "燃油",            # fuel_level / fuel_low_warning
    "range_fuel": "燃油",      # range_fuel_cltc / range_fuel_wltc
    # ★ 2026-09-28 补齐【同类遗漏】——纯电车同样不该有这些：
    #   发现方式：按「增程专属」关键词（Fuel/Oil/Tank/Engine/sparkplug…）
    #   全表扫描 156 个信号，逐个核对语义。
    "tank_lock": "燃油",         # 油箱盖 —— 纯电无油箱
    "maint_engine_oil": "燃油",  # 机油   —— 纯电无发动机
    "maint_sparkplug": "燃油",   # 火花塞 —— 纯电无点火系统
    # ⚠️ 暂不门控（语义未确证，宁可留着也不误删）：
    #   · maint_engine_level2「保养二级」—— enginelevel2 的含义不明，
    #     可能是通用保养档位而非发动机专属，需更多证据
    #   · maint_brake_oil「刹车油」/ maint_coolfuild「冷却液」/
    #     maint_acfilter「空调滤芯」—— 纯电车同样有，本就该保留
}


def feature_of(key: str) -> str | None:
    """根据信号 key 判断所属功能；None 表示通用信号（始终创建）。

    匹配规则：key 等于前缀，或以「前缀 + _」开头。

    ⚠️ 2026-09-28 起本函数【只作为兼容层】保留：
       新的判据是 SignalSpec 上的 `requires` / `universal` 声明
       （见 signals.SignalSpec 与下面的 resolve_requirement）。
       这张前缀表是旧的"独立映射表"，正是它漏登记导致 i6 拿到燃油实体。
    """
    for prefix, feat in FEATURE_BY_KEY_PREFIX.items():
        if key == prefix or key.startswith(prefix + "_"):
            return feat
    return None


# ══════════════════════════════════════════════════════════════════════════
#  ★ 车型能力判定（2026-09-28）—— 取代 FEATURE_BY_KEY_PREFIX
# ══════════════════════════════════════════════════════════════════════════
#
#  每个信号在 SIGNALS 里【自己声明】依赖什么能力（requires / universal），
#  本模块负责把声明解析成"这个车型要不要建这个实体"。
#
#  为什么要这样做（用户提问）：
#      「app 都能区分，我们为什么不能？直接照搬 app 的区分逻辑不就好了？」
#    能。App 的能力数据就是 assets/{modelId}.json 的 54 个标签，
#    我们已完整读取（vehicle_ability.py）。缺的是「标签 → 实体」的映射，
#    而旧实现把它放在一张独立表里且只登记了 21/156 → 漏登记即默认全建。
#    现在声明就在信号旁边，且由测试强制【每个信号都必须表态】。
#
def _ability_bev(ability) -> bool:
    """安全读取 ability.is_bev；无 ability 时按「非纯电」处理（保守保留燃油类）。"""
    if ability is None:
        return False
    try:
        return bool(ability.is_bev)
    except Exception:  # noqa: BLE001
        return False


def resolve_requirement(spec, features: dict, ability) -> tuple[bool, str]:
    """判断某个信号对本车型是否应创建。

    返回 (是否创建, 说明)。说明用于日志与测试断言。

    requires 语法（见 signals.SignalSpec 的文档）：
        "version:<tag>"   App version 标签 → is_supported(tag)
        "ability:<tag>"   App temp.config  → ability_level(tag) >= 2
        "feature:<名称>"   我们的 VSS 探测功能 → features[名称]
        "combustion"      增程专属 → not is_bev
        "bev"             纯电专属 → is_bev
        universal=True    所有车型都有
    """
    req = getattr(spec, "requires", None)
    if not req:
        if getattr(spec, "universal", False):
            return True, "universal"
        # 未表态：保守【保留】，但 tests 的穷尽性检查会失败（不允许留空）
        return True, "未声明(保守保留)"

    if req == "combustion":
        return (not _ability_bev(ability)), "combustion"
    if req == "bev":
        return _ability_bev(ability), "bev"

    kind, _, arg = req.partition(":")

    if kind == "feature":
        # features 缺失该项时保留（宁多不误删）
        return bool(features.get(arg, True)), req

    if kind == "version":
        if ability is None or not getattr(ability, "available", False):
            return True, req + "(无能力表,保守保留)"
        try:
            return bool(ability.is_supported(arg)), req
        except Exception:  # noqa: BLE001
            return True, req + "(异常,保守保留)"

    if kind == "ability":
        if ability is None or not getattr(ability, "available", False):
            return True, req + "(无能力表,保守保留)"
        try:
            # ★ 必须用 has() 而不是 ability_level(tag) >= 2：
            #   ability_level 对【未配置的 tag】返回 DEFAULT_ABILITY_LEVEL(2)，
            #   于是 ">= 2" 会把"配置里压根没提"误判为"有该硬件"。
            #   实例：thirdMSeatHeatSw 只在 6 个 W 系(i系列)车型里存在，
            #   其余 62 个 L 系车型根本没这个键 → 用 ability_level 会给
            #   所有 L 系车建出「三排中座椅」。
            #   has() 的规则是「未配置 → False」，正是我们要的（见其文档）。
            return bool(ability.has(arg)), req
        except Exception:  # noqa: BLE001
            return True, req + "(异常,保守保留)"

    # 未知 DSL：保守保留，并在日志里可见
    return True, f"未知DSL({req})"


def filter_specs(specs, features: dict, ability) -> tuple[list, list]:
    """按 SignalSpec 的能力声明过滤。返回 (保留, 跳过说明)。

    入参可以是 SignalSpec，也可以是 (desc, spec) 元组 —— 两种都由
    specs_for / to_*_descriptions 产出，这里统一兼容。

    说明形如 "range_fuel_cltc(combustion)"，便于日志排查。
    """
    keep, skipped = [], []
    for item in specs:
        if isinstance(item, tuple):
            desc, spec = item[0], item[1]
        else:
            desc, spec = item, item
        key = (getattr(desc, "key", "") or getattr(spec, "key", "") or "")
        ok, why = resolve_requirement(spec, features, ability)
        if ok:
            keep.append(item)
        else:
            skipped.append(f"{key}({why})")
    return keep, skipped




def _desc_key(item) -> str:
    """取出一条「实体描述」的 key。

    ★ 2026-09-28 血泪：`to_binary_descriptions()` 产出的是
      **(description, spec) 元组**，不是 description 对象本身。
      最初的实现只做 `getattr(item, "key", "")` ——
      元组没有 .key → 取到空串 → feature_of 返回 None → 一个都不过滤。
      **过滤器静默失效，看起来却像在工作**（正是本次要修的那类 bug）。
      所以这里显式兼容两种形状。
    """
    if isinstance(item, tuple) and item:
        item = item[0]
    return getattr(item, "key", "") or ""


def is_supported_by_features(item, features: dict) -> bool:
    """该项是否应创建（features 缺失时【保留】—— 宁多不误删）。"""
    key = _desc_key(item)
    feat = feature_of(key)
    return not (feat and not features.get(feat, True))


def filter_by_features(descriptions, features: dict) -> tuple[list, list]:
    """按车型功能过滤实体描述（保持输入形状：元组进 → 元组出）。

    返回 (保留, 跳过)。跳过项是 "key(功能)" 字符串，便于日志排查。
    """
    keep, skipped = [], []
    for item in descriptions:
        key = _desc_key(item)
        feat = feature_of(key)
        if feat and not features.get(feat, True):
            skipped.append(f"{key}({feat})")
            continue
        keep.append(item)
    return keep, skipped


def parse_variable_model(vm: str | None) -> dict[str, Any]:
    """解析 variableModel 中文配置串，返回硬件推断。

    返回:
        {
            "raw": ["AD PRO", "无踏板", ...],
            "autopilot": "AD PRO" | None,
            "battery": "电池CATL" | None,
            "drive": "后驱汇川" | None,
            "factors": {功能名: bool},   # 仅含【能明确判断】的
        }

    ★ 只返回能明确判断的项；模糊的（如"高级音响"）也返回，但调用方可忽略。
    """
    out: dict[str, Any] = {"raw": [], "factors": {}}
    if not vm:
        return out

    parts = [p.strip() for p in str(vm).split("+") if p.strip()]
    out["raw"] = parts

    for p in parts:
        if p.startswith("AD"):
            out["autopilot"] = p
        elif p.startswith("电池"):
            out["battery"] = p
        elif "驱" in p:
            out["drive"] = p

    joined = "+".join(parts)

    # ① 先处理否定（"无冰箱" 优先于 "冰箱"）
    for neg_kw, feat in _VM_NEGATIVE.items():
        if neg_kw in joined:
            out["factors"][feat] = False

    # ② 再处理肯定（已被否定覆盖的不改）
    for feat, kws in _VM_POSITIVE.items():
        if feat in out["factors"]:
            continue          # 已由否定确定
        if any(kw in joined for kw in kws):
            out["factors"][feat] = True

    return out


def _ts_fresh(ts: str, max_days: float = 7.0) -> bool:
    """判断信号时间戳"存在"（非 "0" / 非空）。

    ★ 判据说明（2026-09-23 实测修正）：
      实测 ts 分层：
        · 实时（<1天）:   51 个信号  — 车的当前状态
        · 2-3 天:         若干      — 车辆激活快照（无变化不更新）
        · 42~792 天:      config_code / charge_limit / ota_* 等
                                    — 【仍然有效】！只是长期未变

      因此不能用"年龄"判断有效性。
      真正无效的标志是 ts == "0"（服务端从未上报该信号），
      典型：无冰箱的车 Cabin.Fridge.* 全部 ts=0。
    """
    try:
        from datetime import datetime
        t = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - t).total_seconds() < max_days * 86400
    except Exception:  # noqa: BLE001
        return True   # 解析失败时不惩罚（保守）


def _ability_to_features(ab) -> dict:
    """把车型能力表映射到我们的功能名（2026-09-26）。

    判定规则（与 App 一致）：
      · 座椅/硬件类 → ability_level(tag) >= 2（= ab.has(tag)）
      · 功能开关类  → is_supported(tag)

    ★ 只返回【能从能力表确定】的项；其余由调用方走 VSS 探测。
    """
    out: dict = {}

    # ---- 座椅硬件（用 ability_level）----
    # ★ 关键改进：三排 / 二排中 用各自的 tag 明确判断，不再靠 ts 猜
    out["三排座椅"] = ab.has("thirdLSeatSw") or ab.has("thirdRSeatSw")
    out["二排座椅"] = (ab.has("secLSeatSw") or ab.has("secMSeatSw")
                       or ab.has("secRSeatSw"))
    out["座椅加热"] = ab.has("flSeatSw") or ab.has("frSeatSw")
    out["方向盘加热"] = ab.has("strgWhlHeatSw")

    # ---- 功能开关（用 is_supported）----
    out["哨兵模式"] = ab.is_supported("sentry")
    out["冰箱"] = ab.is_supported("fridge")
    out["远程拍照"] = True          # L6/L7/L8/L9 都有 360 泊车影像
    out["遮阳帘"] = True            # 能力表无对应 tag，保持已确认的结论

    # ---- ★ 2026-09-28 新增：燃油（增程）能力 ----
    #   用户反馈「i6 车型显示燃油续航」。i6 属 i 系列纯电（W04），无油箱。
    #   判据来自车型配置 config.energy.power（见 VehicleAbility.has_combustion_engine）：
    #     ["1"]      → 纯电（21 个 W 系车型）→ 不建油量/燃油续航实体
    #     ["1","2"]  → 增程（47 个 L 系车型）→ 正常创建
    try:
        out["燃油"] = ab.has_combustion_engine
    except Exception:  # noqa: BLE001
        # 老版本 ability 对象无该方法时保守放行（宁多不误删）
        out["燃油"] = True

    # ---- 明确【无】的（能力表 isSupport=false 且 config 里有该 tag）----
    for tag, feat in (("sideDoor", "侧滑门"),
                      ("electricFrontDoor", "电动前门"),
                      ("rotatableSeatLockLinkage", "旋转座椅")):
        v = ab.version_info(tag)
        if v and not v.get("isSupport"):
            out[feat] = False
        elif v and v.get("isSupport"):
            out[feat] = True

    return out


def _hardcoded_features(li_api: Any) -> dict[str, Any] | None:
    """用 Vehicle.Information.ConfigCode 识别车型, 返回 App 的硬编码功能表。

    返回 None 表示无法识别（调用方回退到 VSS 探测）。
    """
    try:
        state = li_api.get_vss_state(["Vehicle.Information.ConfigCode"]) or {}
        raw = state.get("Vehicle.Information.ConfigCode", {}).get("value")
        if not raw:
            return None
        import json
        cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:  # noqa: BLE001
        return None

    # ★ 2026-09-24 启用（原先 return None 导致 KNOWN_FEATURES 完全没用上）
    #
    # 车型判定依据：
    #   ConfigCode.vehModel 的编码（如 "JR7"）需要服务端字典才能翻译，
    #   App 里【没有】该字典（已在 smali/Hermes/resources 全面搜索确认）。
    #
    #   因此用【可验证的特征组合】判定：
    #     ① KNOWN_FEATURES 的键用【服务端确认的平台号】（X04 = L6），
    #        不用 App 里的类名（详见 KNOWN_FEATURES 上方的更正说明）
    #     ② 经验判据：有 360Svm.ParkPhoto.State（泊车拍照）
    #        + 无冰箱信号 → L6
    #
    #   ⚠️ 保守策略：
    #     · 只有能【明确判定】车型时才返回硬编码表
    #     · 判不出 → 返回 None → 回退 VSS 探测
    #     · 这样不会把 L9 误判成 L6（进而隐藏三排座椅）
    code = cfg.get("vehModel") or ""
    seats_cfg = cfg.get("seats") or ""
    fridge_cfg = cfg.get("vehRefrigerator") or ""
    _LOGGER.debug(
        "ConfigCode: vehModel=%s seats=%s fridge=%s configLevel=%s",
        code, seats_cfg, fridge_cfg, cfg.get("configLevel"))

    # 已知车型样本（ConfigCode.vehModel 编码 → KNOWN_FEATURES 的 key）
    # ★ 目前只确证了我们的车：
    #     vehModel='JR7' + seriesNo='X04' + modelName='理想L6'
    #   （前两项均实测自服务端 /vehicles/basics）
    KNOWN_CODES = {
        "JR7": "X04",      # 实测样本（2026-09-23）
    }

    model_key = KNOWN_CODES.get(code)
    if not model_key:
        _LOGGER.debug("未知车型编码 %s，回退 VSS 探测", code)
        return None

    hard = dict(KNOWN_FEATURES.get(model_key) or {})
    if not hard:
        return None
    hard["_model"] = model_key
    return hard


def _variable_model_factors(li_api: Any) -> dict[str, bool]:
    """从 variableModel 中文配置串推断硬件有无。

    数据源：get_vehicles() → vehicleInfo.variableModel
    失败时返回空 dict（不影响主流程）。

    ★ 与 VSS 探测的关系：
      · variableModel 更【权威】（服务端明确声明"无冰箱"）
      · 但只有部分字段（冰箱/踏板/悬架/尾翼）
      · 其余功能仍走 VSS 探测
    """
    try:
        veh = li_api.get_vehicles() or []
        if not veh:
            return {}
        info = veh[0].get("vehicleInfo") or {}
        vm = info.get("variableModel")
        if not vm:
            return {}
        parsed = parse_variable_model(vm)
        return dict(parsed.get("factors") or {})
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("variableModel 读取失败（忽略）: %s", err)
        return {}


def detect_features(li_api: Any) -> dict[str, bool]:
    """探测车辆实际支持的功能。

    返回 {功能名: 是否支持}；探测失败的组按 False 处理（保守）。
    """
    result: dict[str, bool] = {}

    # ⓪-1 ★ 2026-09-26：先查【车型能力表】（读 APK 内置 JSON，与 App 完全一致）
    #    ★ 放在最前面：即使 VSS 请求失败（401 等），能力表仍然可用
    ab = get_ability(li_api)
    if ab.available:
        _LOGGER.debug("使用车型能力表 %s (%s): %d 座",
                      ab.desc, ab.model_id, ab.vehicle_seat())
        result.update(_ability_to_features(ab))

    # ⓪-2 然后做 VSS 探测（补充能力表没覆盖的项）
    all_paths: list[str] = []
    for paths in FEATURE_PROBES.values():
        all_paths.extend(paths)

    try:
        state = li_api.get_vss_state(all_paths) or {}
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("VSS 功能探测失败（能力表结果仍保留）: %s", err)
        # ★ 不再全部返回 False —— 能力表已有的结果保留
        for k in FEATURE_PROBES:
            result.setdefault(k, False)
        if "冰箱" in result:
            result["冰箱预约"] = result["冰箱"]
        return result

    # ⓪-3 ★ 2026-09-26：优先用【车型能力表】（读 APK 内置 JSON，与 App 完全一致）
    #    这比 ConfigCode 硬编码表准确得多：覆盖 68 个车型，且是官方数据。
    # ★★ 权威性规则（2026-09-26）：
    #   能力表（官方 APK 数据）> variableModel（服务端中文串）> ConfigCode 表 > VSS 探测
    #
    #   已被能力表确定的功能，【后续任何来源都不得覆盖】。
    #   原因：VSS 探测无法区分"服务端对不存在硬件也返回 value=0 + 有效 ts"，
    #         实测会把 L6（五座）误判为有三排座椅。
    authoritative: set[str] = set(result.keys())

    # 未被能力表覆盖的，尝试 ConfigCode 硬编码表（回退路径）
    if ab.available:
        hard = None          # 能力表已覆盖，不再用 ConfigCode
    else:
        hard = _hardcoded_features(li_api)

    if hard:
        _LOGGER.debug("使用 App 硬编码功能表 (%s): %s", hard.get("_model", "?"),
                        {k: v for k, v in hard.items() if not k.startswith("_")})
        # 用硬编码结果覆盖对应功能
        for feat, val in hard.items():
            if feat.startswith("_"):
                continue
            result[feat] = val
        # 未被硬编码覆盖的，继续走 VSS 探测
        remaining = {k: v for k, v in FEATURE_PROBES.items() if k not in result}
    else:
        remaining = FEATURE_PROBES

    # ①-b ★ 2026-09-26：用 variableModel（中文配置串）校准硬件判断
    #   来源：GET /saos-vehicle-api/v2-0/vehicles/basics → vehicleInfo.variableModel
    #   例："AD PRO+无踏板+无冰箱+高级音响"
    #   ★ 比 VSS 探测更可靠（服务端明确说了"无冰箱"）
    vm_factors = _variable_model_factors(li_api)
    if vm_factors:
        _LOGGER.debug("variableModel 硬件判断: %s", vm_factors)
        for feat, val in vm_factors.items():
            if feat in FEATURE_PROBES or feat in result:
                result[feat] = val
        # 已由 variableModel 确定的，不再走 VSS（避免被误判）
        remaining = {k: v for k, v in remaining.items() if k not in vm_factors}

    for feat, paths in remaining.items():
        # ★ 判据 (2026-09-23 修正):
        #   服务端对【不存在的硬件】也返回 value=0, 但 ts="0"（从未上报）。
        #   因此必须同时满足: value 非空 且 ts 非 "0"。
        #   例: Cabin.Fridge.ActWorkSts=0 ts=0 → 无冰箱
        #       Body.DoorLockStatus.FrontTrunkDoor=1 ts=2026-09-21 → 有前备箱
        # 统计"有效信号"数
        # ★ 判据 (2026-09-23 改进)：
        #   ① value 非空
        #   ② ts != "0"（从未上报）
        #   ③ ts 在 7 天内（避免"残留默认值"，如 FrontTrunkDoor 停在 49h 前）
        valid = 0
        for p in paths:
            sig = state.get(p)
            if not sig:
                continue
            val = sig.get("value")
            ts = str(sig.get("ts") or "")
            if val is None or not ts or ts == "0":
                continue
            valid += 1
        # ★ 判据：多数信号有效才算支持（避免个别通用信号造成误报）
        #   实测: 无冰箱时仅 DlyTmRemain 有 ts，其余 3 个都是 ts=0 → 判为无
        need = 1 if len(paths) == 1 else max(2, (len(paths) + 1) // 2)
        # ★★ 权威性：能力表已确定的功能，VSS 探测不得覆盖
        #   实测 VSS 会把 L6（五座）误判为"有三排座椅"，
        #   因为服务端对不存在的三排硬件也返回 value=0 + 有效 ts。
        if feat in authoritative:
            continue
        result[feat] = valid >= need

    # "冰箱预约" 依赖冰箱硬件
    if "冰箱" in result:
        result["冰箱预约"] = result["冰箱"]

    supported = [k for k, v in result.items() if v]
    unsupported = [k for k, v in result.items() if not v]
    _LOGGER.info("车型功能探测: 支持=%s | 不支持=%s", supported, unsupported)
    return result


def read_vehicle_config(li_api: Any) -> dict[str, str]:
    """读取车型配置 (Vehicle.Information.ConfigCode)。

    返回服务端下发的原始编码字典, 例如:
        {"vehModel":"JR7","configLevel":"IZ8","seats":"AE4", ...}
    编码需要服务端字典才能翻译成人话, 这里仅原样返回。
    """
    try:
        state = li_api.get_vss_state(["Vehicle.Information.ConfigCode"]) or {}
        raw = state.get("Vehicle.Information.ConfigCode", {}).get("value")
        if not raw:
            return {}
        import json
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("读取车型配置失败: %s", err)
        return {}
