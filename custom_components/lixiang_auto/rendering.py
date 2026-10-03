"""传感器值的渲染逻辑（纯函数，可单测）

★ 2026-09-23 从 sensor.py 抽出（架构优化方案 阶段 1.3）

目的：把 29 处 `if key ==` 的分支逻辑变成【可单测的纯函数】。
这是**纯搬家** —— 行为与原实现完全一致（由 tests/ 兜底）。

为什么抽出来？
  · 原实现依赖 self.coordinator.data / self.entity_description，
    无法在单测里构造 → 改了不知道对不对
  · 抽成纯函数后，可参数化喂各种输入做等价性验证
  · 历史教训：`n != 0` → `n == 1` 的语义 bug（391cd8a），
    若有这套测试，5 分钟就能发现

函数契约
--------
输入：
  key   信号 key（如 "battery_level" / "charge_status"）
  val   该信号的原始值（可能为 None）
  sig   信号完整 dict（{"value":..,"ts":..}）或 None
  data  coordinator.data（含 vehicle_status 等非 VSS 字段）

输出：
  渲染值（str / int / float / dict / None / STATE_UNKNOWN）

用法
----
  # sensor.py
  from .rendering import render_value
  ...
  return render_value(self.entity_description.key, val, sig, self.coordinator.data)

  # tests/test_rendering.py
  assert render_value("charge_status", 3, {"value": 3}, {}) == "充电中"
"""

from __future__ import annotations

import json
from typing import Any

# ★ 2026-09-23 修复：抽 rendering.py 时漏了这两个 import，
#   导致 translate() 从未被调用（值永远是裸数字）。
#
# 兼容两种导入方式（便于单测）：
#   · HA 运行时：相对导入（包内）
#   · pytest：绝对导入（conftest 已把集成目录加入 sys.path）
try:
    from .signals import path_of
    from .translations import translate
except ImportError:  # pragma: no cover - 单测路径
    from signals import path_of  # type: ignore[no-redef]
    from translations import translate  # type: ignore[no-redef]

# 与 sensor.py 保持一致
STATE_UNKNOWN = "unknown"


#: 里程统计的三个派生字段 → 上游 trip_total JSON 里的字段名（2026-09-28）
_STAT_MILEAGE_FIELDS = {
    "stat_days":         "ownerTransferDate",
    "stat_mileage":      "ownerTransferMileage",
    "stat_elec_mileage": "ownerTransferCdMileage",
    # ★ 2026-10-02：Trip.Total 里 App 显示、此前未暴露的高价值字段
    #   单位均为【米】，渲染时 /1000 转 km（见下方分支）
    "stat_total_mileage":  "mileage",           # 总里程（车辆累计）
    "stat_engine_mileage": "engineMileage",     # 发动机里程（增程专属）
    "stat_ad_mileage":     "adMileage",         # 辅助驾驶里程（AD）
    "stat_noa_mileage":    "noaMileage",        # NOA 领航里程
    "stat_acc_mileage":    "accMileage",        # ACC 里程
    # ★ 2026-10-02 补：剩余有价值字段
    "stat_lcc_mileage":    "lccMileage",        # LCC 车道居中里程
    "stat_cd_mileage":     "cdMileage",         # 纯电（CD）里程
    "stat_ad_days":        "adMileageDate",     # 辅助驾驶天数（天，非米）
}


def render_value(
    key: str,
    val: Any,
    sig: dict | None = None,
    data: dict | None = None,
) -> Any:
    """把信号的原始值渲染成实体值（纯函数）。

    对应原 LiCarSensor._compute_value()，逻辑逐行照搬。
    """
    data = data or {}
    # ★ 2026-10-02：充电累计量（虚拟信号，path=""）
    #   值来自 coordinator 的低频 HTTP（data["charge_total_kwh"]），
    #   不来自 VSS，也不来自 val —— 必须放在 `if val is None` 之前。
    #   用途：HA 能源面板「总充电量」传感器。
    # ★ 2026-10-02：本月里程/充电量（虚拟信号，值来自 coordinator 低频 HTTP）
    if key in ("month_km", "month_elec_km", "month_elec_kwh",
               "month_fuel_l", "month_charge_kwh"):
        v = data.get(key)
        if v is None:
            return STATE_UNKNOWN
        try:
            return round(float(v), 1)
        except (TypeError, ValueError):
            return STATE_UNKNOWN

    if key == "charge_total_energy":
        kwh = data.get("charge_total_kwh")
        if kwh is None:
            return STATE_UNKNOWN
        try:
            return round(float(kwh), 2)
        except (TypeError, ValueError):
            return STATE_UNKNOWN

    if key == "online_status":
        st = data.get("vehicle_status")
        if st is None:
            return STATE_UNKNOWN
        return "在线" if int(st) == 1 else "离线"

    # ---- 里程统计（2026-09-28，虚拟信号）----
    # ★ 这三个是【虚拟信号】（signals.py 里 path=""），
    #   值派生自已轮询的 trip_total（Vehicle.Carcenter.Trip.Total），
    #   因此必须放在 `if val is None: return None` 之前 —— 否则永远拿不到值。
    #   取数方式同 online_status（从 coordinator data 里拿上游信号）。
    #
    #   字段名与语义来自 App JS bundle 的 aggregate 映射（权威）：
    #     X.ownerTransferDate      = day               → 陪伴天数（天）
    #     X.ownerTransferMileage   = 1e3*travelMileage → 陪伴里程（原始：米）
    #     X.ownerTransferCdMileage = 1e3*elecMileage   → 耗电行驶（原始：米）
    #   ⚠️ 里程原始单位是米，渲染时 /1000 转 km。
    if key in _STAT_MILEAGE_FIELDS:
        up = (data.get("vss") or {}).get("trip_total") or {}
        v = up.get("value")
        if v is None:
            return STATE_UNKNOWN
        field = _STAT_MILEAGE_FIELDS[key]
        try:
            o = json.loads(v) if isinstance(v, str) else v
            raw = o.get(field) if isinstance(o, dict) else None
            if raw is None or raw == "":
                return STATE_UNKNOWN
            # 陪伴天数是天数，直接取整；里程是米 → 公里
            if key in ("stat_days", "stat_ad_days"):
                return int(float(raw))          # 天：直接取整
            return round(float(raw) / 1000.0, 1)   # 米 → km
        except (ValueError, TypeError, AttributeError, KeyError):
            return STATE_UNKNOWN

    if sig is None:
        return None
    if val is None:
        return None

    # ---- 特殊信号: 返回可读值 ----
    if key == "location" and isinstance(val, str):
        try:
            loc = json.loads(val)
            return f"{loc.get('lat', 0):.5f},{loc.get('lon', 0):.5f}"
        except (ValueError, TypeError):
            return STATE_UNKNOWN
    if key == "sentry" and isinstance(val, str):
        try:
            return "已开启" if int(json.loads(val).get("sentinelStatus", 0)) else "已关闭"
        except (ValueError, TypeError):
            return STATE_UNKNOWN
    if key == "sentry_switch" and isinstance(val, str):
        try:
            return "已开启" if int(json.loads(val).get("sentinelSwitch", 0)) else "已关闭"
        except (ValueError, TypeError):
            return STATE_UNKNOWN
    if key == "ota_progress":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            p = o.get("progress")
            return round(float(p) * 100, 1) if isinstance(p, (int, float)) and p <= 1 else p
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN
    if key == "ota_state" and isinstance(val, str):
        try:
            o = json.loads(val)
            return o.get("currentVersion") or o.get("displayTargetVersion") or STATE_UNKNOWN
        except (ValueError, TypeError):
            return STATE_UNKNOWN
    if key == "charge_status":
        # ★ 2026-09-23 复刻 App 的 XChargeDataHandle.getChargeState()
        #   （smali:80-241）—— 不再自造枚举。
        #
        #   App 逻辑（输入 6 个信号 → 输出归一化状态码）：
        #     if 预约开关==1 && AC枪==2 && 预约state==1      → 90  预约充电
        #     if chargeStatus==3                             → 50  充电中
        #     if chargeStatus==5 && chrgComplete==1          → 60  已完成
        #     if chargeStatus==5 && !complete && eveFlt==1   → 111 告警
        #     if chargeStatus==5 && !complete                → 70  已停止
        #     if chargeStatus==7                             → 111 告警
        #     if chargeStatus==2                             → 40  电池加热
        #     if chargeStatus==4                             → 80  电池保温
        #     else                                            → 0
        #
        #   枚举（XChargeDataHandle$Status.smali:18-32）：
        #     BATTERY_HEAT=40 CHARGING=50 COMPETE=60 STOP=70
        #     BATTERY_INSULATION=80 APPOINT_CHARGE=90 CHARGE_ALARM=111
        _vss = (data or {}).get("vss", {})

        def _v(k: str):
            _s = _vss.get(k) or {}
            v = _s.get("value")
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        cs = _v("charge_status")
        # 预约充电判定（三条件同时满足）
        if _v("scheduled_charge_switch") == 1 \
                and _v("charge_gun_ac") == 2 \
                and _v("scheduled_charge_state") == 1:
            return "预约充电"
        if cs == 3:
            return "充电中"
        if cs == 5:
            if _v("charge_complete") == 1:
                return "充电完成"
            if _v("charge_fault") == 1:
                return "充电告警"
            return "已停止"
        if cs == 7:
            return "充电告警"
        if cs == 2:
            return "电池加热"
        if cs == 4:
            return "电池保温"
        # ---- ★ 2026-09-28 修复：兜底先查 translations 映射，再退回 "—" ----
        #
        # 缺陷：此处原先直接 `return "—"`，把 raw 值 0/10/15/130 等
        #   全部吞掉，导致 translations.py 的 ChargeStatus 映射表（下方 306 行
        #   ／本文件末尾的统一 translate 调用）**永远轮不到**。
        #   实测：车未充电时 raw=15，用户看到「—」而非「未充电」。
        #
        # 为什么不能简单删掉这段分支：上面 3/5/7/2/4 是对 App
        #   XChargeDataHandle.getChargeState() 的**正确复刻**（5 还要看
        #   charge_complete / charge_fault 子条件），必须保留。
        #
        # 修复策略：只改【未匹配时的兜底】——
        #   先尝试翻译表；翻译表能给出文案就用文案，否则才退回 "—"。
        #   这样 3/5/7/2/4 的行为一字未动（回归安全），
        #   而 15 因在 ChargeStatus 映射表里 → 正确显示「未充电」。
        if cs is None:
            return None
        _tr = translate(path_of("charge_status"), cs)
        # translate() 契约：映射命中 → 返回【str 文案】；未命中 → 原样返回入参。
        # 我们传入的是 int，所以「返回 str」等价于「映射命中」。
        # 用 isinstance 判定，避免把未知码 1/99 显示成裸数字。
        if isinstance(_tr, str):
            return _tr
        return "—"
    if key.startswith("seat_") and key.endswith("_heat"):
        return {0: "关", 1: "低", 2: "中", 3: "高"}.get(int(val) if str(val).isdigit() else -1, val)
    if key.startswith("seat_") and key.endswith("_vent"):
        return {0: "关", 1: "低", 2: "中", 3: "高"}.get(int(val) if str(val).isdigit() else -1, val)
    if key == "scheduled_charge_switch":
        return "已开启" if int(val) else "已关闭"
    if key == "scheduled_charge_state":
        return {0: "未预约", 1: "已预约", 2: "充电中"}.get(int(val) if str(val).isdigit() else -1, val)
    if key.startswith("tire_") and key.endswith("_warning"):
        return "正常" if not int(val) else "告警"
    if key == "tpms_status":
        return "正常" if not int(val) else "异常"
    if key == "charge_fault":
        return "正常" if not int(val) else "故障"
    if key == "fuel_low_warning":
        return "正常" if not int(val) else "油量低"
    if key in ("online_5g", "online_xcu"):
        return "在线" if val else "离线"
    if key == "provision_auth":
        return "已授权" if val else "未授权"
    if key.startswith("window_"):
        try:
            return int(val)          # 单位已是 %, 只返回值
        except (ValueError, TypeError):
            return val
    if key == "sunshade":
        return {0: "关闭", 1: "打开"}.get(int(val) if str(val).isdigit() else -1, val)
    if key in ("battery_keep_warm",):
        return "已开启" if val else "已关闭"
    if key == "svm_filekey" and isinstance(val, str):
        try:
            o = json.loads(val)
            return o.get("picTime") or STATE_UNKNOWN
        except (ValueError, TypeError):
            return STATE_UNKNOWN
    if key == "ac_set_temp":
        try:
            return float(val)
        except (ValueError, TypeError):
            return val

    # ---- ★ 2026-09-24 保养二级（maint_engine_level2）----
    #   ⚠️ 必须放在 maint_ 前缀判断【之前】——
    #      它的字段结构不同（无 maintainLeftMileage 之外的常见字段组合），
    #      用通用逻辑会误返回"正常"。
    if key == "maint_engine_level2":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            name = o.get("name") or "保养"
            left = o.get("maintainLeftMileage")
            due = str(o.get("maintainDueDate") or "")
            parts = [str(name)]
            if isinstance(left, (int, float)):
                parts.append(f"剩余 {left:.0f} km")
            if len(due) == 8 and due.isdigit():
                parts.append(f"{due[:4]}-{due[4:6]}-{due[6:]} 到期")
            return " · ".join(parts) if len(parts) > 1 else str(name)
        except (ValueError, TypeError, AttributeError):
            return "未知"

    # ---- 保养类: 提取关键字段 ----
    if key.startswith("maint_"):
        try:
            o = json.loads(val) if isinstance(val, str) else val
            left = o.get("maintainLeftMileage")
            due = o.get("maintainDueDate")
            if left is not None:
                return f"剩余 {left:.0f} km"
            if due and due != "--":
                return f"到期 {due}"
            return "正常"
        except (ValueError, TypeError, AttributeError):
            return "未知"
    if key == "travel_status":
        # ★ 2026-09-24 新增：档位/行驶状态
        #   来源：App 的 parseTravelStatus()（VehicleBaseState.smali:716）
        #     源码逻辑：gear == "P" → 4 ；否则 → 1
        #   含义：
        #     4 = P 档（已驻车）
        #     1 = 其他档位（行驶中）
        #   这是 App 首页「已驻车 / 行驶中」的数据源（VSS 可拿到）。
        _GEAR = {
            4: "已驻车（P 档）",
            1: "行驶中",
            0: "未知",
            2: "行驶中",
            3: "行驶中",
        }
        try:
            return _GEAR.get(int(float(val)), f"档位 {val}")
        except (TypeError, ValueError):
            return STATE_UNKNOWN

    if key == "trip_total":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            mi = o.get("totalMileage") or o.get("adMileage")
            if isinstance(mi, (int, float)) and mi > 1000:
                return round(mi / 1000, 1)      # 转为 km
            return mi if mi is not None else STATE_UNKNOWN
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN
    # ★ 统一翻译：0/1 等裸数字 → 中文（translations.py）
    #   App 里没有数字→文案映射表，我们用实测表翻译（见 translations.py 说明）
    _path = path_of(key)
    if _path:
        _tr = translate(_path, val)
        if _tr != val:
            return _tr

    if key == "config_code":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return o.get("configLevel") or o.get("autopilot") or STATE_UNKNOWN
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN
    if key == "hu_diag":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return f"EEA{o.get('eea', '?')}"
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN
    if key == "battery_keep_warm":
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return "已开启" if o.get("startTime") else "已关闭"
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN
    if key == "scheduled_charge_start":
        return str(val)[:5] if val else STATE_UNKNOWN
    if key == "scheduled_charge_end":
        return str(val)[:5] if val else STATE_UNKNOWN

    # ---- ★ 2026-09-24 新增：复杂 JSON 信号 → 可读值 ----
    #   用户反馈："离车模式好像有问题"（显示一坨 JSON）
    if key == "xmode":
        # 按时出发：{mainSwitch, maxItemCount, moveOffDatas:{id:{...}}}
        #
        # ★ 2026-09-28 修正（用户报告"我们按时出发是没有打开的"却显示已开启）：
        #   旧逻辑只看 mainSwitch —— 那只是【功能模板层】的总开关。
        #   一条计划是否真正生效，还要看【该条自己的开关】：
        #
        #     subSwitch       该条计划的开关（False = 这条是关的）
        #     weekOfDayStates 每天是否启用（全 DISABLE = 七天都不生效）
        #
        #   实测（用户确认"没打开"）：
        #     mainSwitch=True                  ← 旧逻辑据此误判为"已开启"
        #     moveOffDatas[0].subSwitch=False  ← ★ 该条是关的
        #     weekOfDayStates 全 DISABLE       ← ★ 七天全禁用
        #
        #   信号语义依据（App spec）：
        #     VehInfo.CarXMode.MoveOffOnTime.Switch = "按时出发模式-开关状态"
        try:
            o = json.loads(val) if isinstance(val, str) else val

            def _day_enabled(d: dict) -> bool:
                """该条计划当天是否有启用（无该字段时视为启用，向后兼容）。"""
                st = d.get("weekOfDayStates")
                if not isinstance(st, dict) or not st:
                    return True
                return any(str(v).upper() == "ENABLE" for v in st.values())

            items = list((o.get("moveOffDatas") or {}).values())
            # 生效的计划 = 该条 subSwitch 非 False 且当天有启用
            active = [
                d for d in items
                if d.get("subSwitch") is not False and _day_enabled(d)
            ]

            if not active:
                # ★ 没有生效的计划 → 关闭（无论 mainSwitch 是什么）
                return "已关闭"

            d = active[0]
            parts = []
            if d.get("startTime"):
                parts.append(str(d["startTime"])[:5])
            if d.get("acSwitch"):
                t = d.get("temp")
                parts.append(f"空调{int(t)}°C" if isinstance(t, (int, float)) else "空调")
            if d.get("dayDesc"):
                parts.append(str(d["dayDesc"]))
            more = f" +{len(active)-1}" if len(active) > 1 else ""
            return ("已开启 · " + " ".join(parts) + more) if parts else "已开启"
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    if key == "fridge_reserve":
        # 冰箱预约：{reserveSwitch, startTime, temp, workMode, dayDesc}
        try:
            o = json.loads(val) if isinstance(val, str) else val
            if not bool(o.get("reserveSwitch")):
                return "已关闭"
            parts = []
            if o.get("startTime"):
                parts.append(str(o["startTime"])[:5])
            t = o.get("temp")
            if isinstance(t, (int, float)) and t:
                parts.append(f"{int(t)}°C")
            if o.get("dayDesc"):
                parts.append(str(o["dayDesc"]))
            return ("已开启 · " + " ".join(parts)) if parts else "已开启"
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    if key == "charge_calibration":
        # 充电校准：{id, ...} —— 只显示是否启用
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return "已启用" if o else STATE_UNKNOWN
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    if key == "vehicle_accounts":
        # 车辆账号：{accountId: {role: ...}} → 显示账号数
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return f"{len(o)} 个账号"
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    if key == "provision_finish":
        # 激活成功信息：{accountId, ...} → 已激活
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return "已激活" if o else STATE_UNKNOWN
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    if key == "rear_load_mode":
        # 后负载模式：{id, ...}
        try:
            o = json.loads(val) if isinstance(val, str) else val
            return o.get("name") or o.get("mode") or ("已设置" if o else STATE_UNKNOWN)
        except (ValueError, TypeError, AttributeError):
            return STATE_UNKNOWN

    # ---- 通用: 长 JSON 截断, 其余直返 ----
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
        return s if len(s) <= 250 else s[:247] + "..."
    if isinstance(val, str) and len(val) > 250:
        return val[:247] + "..."
    return val

