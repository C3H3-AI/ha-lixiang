"""理想汽车 · VSS 状态值翻译（2026-09-23）

背景
----
App 返回的是**裸数字**（0/1/2/15/70...），且 **App 里没有数字→文案的映射表**。

严谨验证（详见 docs/状态值翻译表_20260923.md）：
  · smali（16 DEX）        → 只有数字，无枚举类
  · Hermes bundle          → 字符串表去重，只有零散词
  · res/values/strings.xml → 有中文文案，但无【数字→文案】映射
  · 编码字典               → 在服务端（ConfigCode 同理）

因此本翻译表由**实测 + 惯性推断**建立：
  · 已知值（如 ChargeStatus=15 未插枪）→ 实测确认
  · 未知值                            → 原样显示数字（不猜测）

⚠️ 待插枪/操作车辆时可进一步验证（见文档"待验证项"）。
文案来源（2026-09-23 修正）
------------------------
App 的 UI 文案【在本地 Hermes bundle 里】（UTF-16-LE 编码），
已提取 1063 条保存于 lixiang-reverse/data/app_ui_texts.txt。

本翻译表的文案已按 App 实际用语对齐：
  · 充电枪: "充电枪已插入" / "充电枪未插入"（非"已连接"）
  · 车门:   "主驾车门打开"（非"已打开"）
  · 尾门:   "尾门开启"
  · 前备箱: "前备箱已开启"
  · 车锁:   "车辆已上锁" / "车辆已解锁"

提取工具：lixiang-reverse/tools/extract_hermes_strings.py
详见：docs/App文案提取_20260923.md
"""

from __future__ import annotations

# 信号路径后缀 → {原始值: 中文文案}
# 匹配规则：path.endswith(suffix)
VALUE_MAPS: dict[str, dict] = {
    # ---------- 座椅加热/通风（0=关，1/2/3=档位）----------
    "SeatHeatState":        {0: "关闭", 1: "1档", 2: "2档", 3: "3档"},
    "SeatVentilationState": {0: "关闭", 1: "1档", 2: "2档", 3: "3档"},
    "WarmOnOff":            {0: "关闭", 1: "开启"},

    # ---------- 空调 ----------
    "WindMode":             {0: "关闭", 1: "自动", 2: "手动", 3: "吹面", 4: "吹脚"},
    "DefrostModeStatus":    {0: "关闭", 1: "开启"},
    "ACSmartControl":       {0: "关闭", 1: "开启"},
    "FrtACAUTOSw":          {0: "关闭", 1: "开启"},
    "FrtACSw":              {0: "关闭", 1: "开启"},

    # ---------- 车门 / 车窗 / 后备箱 ----------
    # ★ 关键（App LiMeshPathHelper 定义）：
    #   LXVehicleInfoKeyLock → Vehicle.Body.DoorLockStatus.*   门的【锁】状态
    #   LXVehicleInfoKeyDoor → Vehicle.Body.DoorSwitchStatus.* 门的【开关】状态
    #   两者语义不同，翻译也不同！
    #
    # 锁状态（0=已上锁 / 1=已解锁）
    "DoorLockStatus.MainDoor":        {0: "已上锁", 1: "已解锁"},
    "DoorLockStatus.CopilotDoor":     {0: "已上锁", 1: "已解锁"},
    "DoorLockStatus.BackLeftDoor":    {0: "已上锁", 1: "已解锁"},
    "DoorLockStatus.BackRightDoor":   {0: "已上锁", 1: "已解锁"},
    "DoorLockStatus.TrunkDoor":       {0: "已上锁", 1: "已解锁"},
    "DoorLockStatus.FrontTrunkDoor":  {0: "已上锁", 1: "已解锁"},
    # ★ 2026-09-23 补充（task-14 高价值遗漏信号）
    # ★ 2026-09-24 补充（新增信号的值翻译）
    "RmtVirtualKeyAuthSts":   {0: "未授权", 1: "已授权"},
    # ★ 2026-09-28 语义修正：ChargeHere 是「是否启用仅在此固定地点预约充电」
    #   的开关（App spec: "此地执行预约状态"），不是"车在不在充电位"。
    "ChargeHere":             {0: "未启用", 1: "仅在此地预约"},
    "OGCType":                {0: "未连接", 1: "国标", 2: "欧标", 3: "美标"},
    "InterferenceSts":        {0: "正常", 1: "干涉"},
    "FrtWindTempColor":       {0: "默认", 1: "冷色", 2: "暖色", 3: "中性"},
    "RESSPowerBarCol":        {0: "绿色", 1: "黄色", 2: "红色"},
    "PowerBatteryType":       {0: "未知", 1: "三元锂", 2: "磷酸铁锂"},
    "OrderChargingMode":      {0: "未设置", 1: "按时间", 2: "按电价"},
    "MSG_DCDCFltLvl":         {0: "正常", 1: "一级故障", 2: "二级故障", 3: "三级故障"},
    "LowVolPwrMdSts":         {0: "正常", 1: "低压模式"},
    "LowVolPwrMdFlag":        {0: "关闭", 1: "开启"},
    "BatteryInsulation":      {0: "未开启", 1: "已开启"},
    "EVESFltStopChrg":        {0: "正常", 1: "故障"},
    "CaseCoverStatus":        {0: "未装", 1: "已装"},
    # 开关状态（0=已关闭 / 1=开启中 / 2=已开启）
    # ★ 2026-09-23 源码修正（XDoorDataHandle.smali:310）：
    #   App 是【二态布尔】—— 只有 0 和 1 两个结果：
    #     int v = toInt(doorValue);
    #     boolean open = (v == 1);      // 1 = 打开，其他 = 关闭
    #   尾门额外证据（XHttpOpen/CloseTrunkControl）：
    #     开成功等 v==1，关成功等 v==2  →  2 = 关闭
    #   ⚠️ 旧映射把 1 说成"开启中"、2 说成"打开"，恰好颠倒。
    "DoorSwitchStatus.MainDoor":      {0: "已关闭", 1: "已打开", 2: "已关闭", 3: "已关闭"},
    "DoorSwitchStatus.CopilotDoor":   {0: "已关闭", 1: "已打开", 2: "已关闭", 3: "已关闭"},
    "DoorSwitchStatus.BackLeftDoor":  {0: "已关闭", 1: "已打开", 2: "已关闭", 3: "已关闭"},
    "DoorSwitchStatus.BackRightDoor": {0: "已关闭", 1: "已打开", 2: "已关闭", 3: "已关闭"},
    "DoorSwitchStatus.TrunkDoor":     {0: "已关闭", 1: "已打开", 2: "已关闭", 3: "已关闭"},
    # ★ 2026-09-23 源码修正（XWindowDataHandle.smali:556-566）：
    #   窗口信号是【0-100 的位置值】，不是 {0,1,2} 枚举：
    #     setMainWindowState(I)   ← (I) 不是 (Z)，存原始 int
    #     且 L132-143: toInt 后 if-gt v,3 → 返回位置值
    #   → 只保留 0 的"已关闭"，其余交给数值直显（百分比语义）
    "MainWindow":           {0: "已关闭"},
    "CopilotWindow":        {0: "已关闭"},
    "BackLeftWindow":       {0: "已关闭"},
    "BackRightWindow":      {0: "已关闭"},
    # ⚠️ 以下两条是【死条目】：实际 VSS 路径用 BackLeft/BackRightWindow
    "LeftRearWindow":       {},
    "RightRearWindow":      {},
    "LockSts":              {0: "车辆已上锁", 1: "车辆已解锁"},
    "FrtSunshdSwSts":       {0: "关闭", 1: "开启"},
    "SunShade":             {0: "关闭", 1: "开启"},

    # ---------- 充电 ----------
    # 证据: App 日志 chargingStatus=30/70/130, 实测未插枪=15
    "ChargeStatus":         {0: "未充电", 10: "已插枪", 15: "未充电",
                             30: "充电中", 70: "充电中", 130: "充电完成"},
    "ACChgrActualConnSts":  {0: "充电枪未插入", 1: "充电枪已插入", 2: "充电枪已插入"},
    "DCChrgngGunActuSts":   {0: "充电枪未插入", 1: "充电枪已插入", 2: "充电枪已插入"},
    "VehicleChrgComplete":  {0: "未完成", 1: "已完成", 2: "未充电"},
    "ChargeFaults":         {0: "正常"},
    "EVESFltStopChrg":      {0: "正常", 1: "故障停止充电"},
    "ScheduledCharging.Switch": {0: "关闭", 1: "开启"},
    "ScheduledCharging.State":  {0: "未预约", 1: "已预约", 2: "已预约"},
    "BatteryInsulation":    {0: "关闭", 1: "开启"},

    # ---------- 轮胎 ----------
    "FLTireWarning":        {0: "正常", 1: "告警"},
    "FRTireWarning":        {0: "正常", 1: "告警"},
    "RLTireWarning":        {0: "正常", 1: "告警"},
    "RRTireWarning":        {0: "正常", 1: "告警"},
    "TPMSSysSts":           {0: "正常", 1: "故障", 2: "学习中"},

    # ---------- 哨兵 ----------
    "SentinelStatus":       {0: "已关闭", 1: "警戒中", 2: "已触发"},

    # ---------- 其他状态 ----------
    "LowBatteryMode":       {0: "关闭", 1: "开启"},
    "LowVolEngyMngtMd":     {0: "关闭", 1: "开启"},
    "LowVolPwrMdFlag":      {0: "正常", 1: "低电量"},
    # Vehicle.CarSettings.Privacy.PosService —— 车辆定位服务授权
    # 源码 (XLocationDataHandle):
    #   if ("1".equals(v)) stateModel.setHasVehicleLocationJurisdiction(true)
    # 即: 1 = 车辆已授权定位服务（App 缓存字段名 hasVehicleLocationJurisdiction）
    #     0 = 未授权，此时 CurrentLocationInfo 可能无效
    "PosService":           {0: "未授权定位", 1: "已授权定位"},
    "Privacy.PosService":   {0: "未授权定位", 1: "已授权定位"},
    "SceneMode.ModeState":  {0: "未设置", 1: "已设置"},
    "ParkPhoto.State":      {0: "空闲", 1: "拍摄中", 2: "已完成"},
    # ★★ 2026-09-28 修正冰箱映射（用户反馈「i6 冰箱状态错误」）
    #
    #   ① 冰箱模式 Vehicle.Cabin.Fridge.ModeState
    #      spec desc = 「冰箱制冷/制热模式」→ 是【制冷/制热】枚举，不是开/关！
    #      App index.vehicle.js 的 getCurrentMode()：
    #          case 1: return mode.COOL;    // 制冷
    #          case 2: return mode.HEAT;    // 制热
    #          default: return mode.CLOSE;  // 关闭
    #      文案依据 App i18n：FridgeModeClose:'关闭' / FridgeModeCool:'制冷'
    #                                              / FridgeModeHeat:'制热'
    #      ❌ 原映射 {0:关闭, 1:开启} → 制冷(1) 被显示成「开启」，制热(2) 显示裸数字「2」
    #
    #      ⚠️ 必须用【两段】键 Fridge.ModeState：
    #         translate() 按后缀长度降序匹配，同类还有
    #         CarSettings.SceneMode.ModeState（已有自己的键），
    #         若继续用通用键「ModeState」会牵连其他 .ModeState 路径。
    "Fridge.ModeState":     {0: "关闭", 1: "制冷", 2: "制热"},
    #
    #   ② 冰箱实际工作状态 Vehicle.Cabin.Fridge.ActWorkSts
    #      App getFridgeTip(workSts, remainTime) 用它触发提示：
    #          case 2 → i18n FridgeTip:「远程开启24小时或电量低于10%时自动关闭以节省电量」
    #          case 3 → i18n remainTime*Tip:「离车持续运行中，剩余时间…」
    #      故 2/3 是【运行中的特殊态】而非错误码，此前未映射 → 界面显示裸数字
    #      0/1 语义（关闭/运行中）依 spec desc「冰箱实际工作状态」
    "Fridge.ActWorkSts":    {0: "关闭", 1: "运行中",
                             2: "自动关闭（省电）", 3: "离车持续运行"},
    "LicLghtSts":           {0: "关闭", 1: "开启"},
    # ★ 2026-10-11 修正（此前写反）：后视镜 0=展开 / 1=收起（折叠）
    #   依据① 实车实测：锁车 + 后视镜物理收起时，裸值 LRearMirro/RRearMirro = 1
    #            （同一状态下 HA 曾显示"展开" → 暴露映射颠倒）
    #   依据② App 侧符号名 Left/RightRearviewMirrorFolded（Folded = 折叠 → 1=折叠）
    #   ⚠️ 旧值（0=收起/1=展开）来自 2026-09 的**推断**，且当时的"实测值"取自
    #      模拟器 VIN（TESTVIN0000000001），不能作为语义依据 —— 故以实车为准。
    "LRearMirro":           {0: "展开", 1: "收起"},
    "RRearMirro":           {0: "展开", 1: "收起"},
}


def translate(path: str, value):
    """把 VSS 裸数字翻译成中文文案。

    · 有映射且值已知 → 返回文案
    · 有映射但值未知 → 返回 f"{value}"（不猜测）
    · 无映射         → 原样返回
    """
    if value is None:
        return None
    if not isinstance(path, str):
        return value
    # ★ 2026-10-11：部分字段（如后视镜 LRearMirro）在 App 侧类型是 **String**，
    #   服务端可能给 "0"/"1" 而不是数字 → 数字字符串按数字查表，否则会显示裸数字。
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        try:
            value = int(value.strip())
        except (TypeError, ValueError):
            pass
    # ★ 按后缀长度降序匹配（避免 FrontTrunkDoor 被 TrunkDoor 抢先）
    for suffix in sorted(VALUE_MAPS, key=len, reverse=True):
        if path.endswith(suffix):
            return VALUE_MAPS[suffix].get(value, value)
    return value


def has_map(path: str) -> bool:
    """该信号是否有翻译映射。"""
    return any(path.endswith(s) for s in sorted(VALUE_MAPS, key=len, reverse=True))
