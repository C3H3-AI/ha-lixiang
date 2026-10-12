# 理想汽车 App 逆向 —— 车控通道完整地图

> 面向：给 `lixiang_auto` 集成加/改车控功能的人。
> 本文只写**有证据**的结论，每条都标了证据来源与验证状态。
> 最后更新：2026-10-12

---

## 0. 先读这一条：别把 M 系和 X 系的表搞混

**这是本项目最容易犯、也最贵的错误**（2026-10-12 我自己犯过一次，
拿 M 系的接口测 X 系的车，白跑一轮）。

App 的 `assets/2025/` 下有**两张互不相同**的车控配置表：

| 文件 | 适用 | 命令数 | 结构 |
|---|---|---|---|
| `LXMVehicleConfig2025.json` | **M 系**（理想 ONE / M01A / M01B） | 69 | 每条 = `{des, cmdKey, config:{sendUrl, verificationUrl, skipVerification, expireAt, successfulCode, failureCode}}` |
| `LXXVehicleConfig2025.json` | **X 系**（L6 / L7 / L8 / L9 / W 系等） | 98 | 每条 = `{des, cmdKey, cmdData, uri, expireAt}` |

**判断某车是哪个系**：`VehicleAbility.platform`
（`"1"` = M 系，`"2"` = X 系；见 `vehicle_ability.py`）。

**搞混的代价**（L6 真车实测，2026-10-12）：

```
L6 调 /ssp-as-mobile-api/v1-0/vehicles/charge-threshold-update → 100035 服务暂时不可用
L6 调 /ssp-as/v1-0/app/vehicle-charge-threshold                → 100012 没有接口访问权限
```

对照组成立（同一 bearer、同一签名方法）：

```
GET /ssp-as-mobile-api/.../travel months → {"code": 0, "msg": "SUCCESS"}
```

→ **认证没错，是这两批端点本来就不属于 X 系。**

---

## 1. 三条通道，不是一个

集成历史上只认一条（`cmd/send`），因此把「充电 / 哨兵 / 拍照」误判为
「走 JOB 长连接、HTTP 不可达」。**实际上有三条**：

### 通道 A：HTTP `cmd/send`（X 系主力）

```
POST /ssp-vehicle-control-service/ssp-vehicle-control/cmd/send
GET  /ssp-vehicle-control-service/ssp-vehicle-control/cmd-result
```
- 请求体：`{vin, cmdKey, cmdData, domain:"xcu", jobExpire, expire, expireAt, token:<VAT>}`
- 头：`Authorization: Bearer <MESH token>`
- 轮询 `cmd-result` 至 `pushState=5`
- 集成实现：`li_api.send_command()` / `send_command_raw()`

### 通道 B：HTTP `send-command`（另一条通用车控）

```
POST /ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command
GET  /ssp-as-mobile-api/v1-0/remote-vehicle-control/{vin}/command/{operationId}/result
```
- 请求体（`OperateReq`）：`{vin, commandKey, commandData, commandDataLi, safetyToken?, taskId?}`
  - `safetyToken` 在 smali 里注解为 `@Nullable` → **非必需**
- M 系配置表：65/69 条命令的 `sendUrl` 指向它

### 通道 C：LiNdn / NDN 长连接（**HTTP 不可达**）

- 路由依据：`LiveNetControlRouter.resolveRoute()` 按 `destParams` 分流
- `destParams` 权威表：`XVehicleJobHelper.commandDestParamsMap`
  - 含 `mob.vehCtrlService.vehCtrlJobList` → **通道 A**
  - `mob.metaJobService.*` → **通道 C（JOB）**
- 已实测 2009（= 该命令不走 HTTP）的 cmdKey：
  `remote_charge_control` / `sentinelModeSetting` / `mobileVehSvm` /
  `mobileVehPushStream` / `MoveOffAdd` / `sceneModeCtrl` …
- 集成实现：`li_api._JOB_CHANNEL_COMMANDS` + `ensure_job_channel_supported()`

**注意**：配置表里 `uri: ""` **不等于「走 HTTP」**，它的含义是
**「交给 Router 按 destParams 路由」** —— `sentinelModeSetting` 的 `uri`
就是空的，但它走 JOB。

---

## 2. 端点清单（按归属分类）

### 2.1 只属于 M 系

| 端点 | 动词 | 请求体 | 用途 |
|---|---|---|---|
| `/ssp-as/v1-0/app/vehicle-charge-setting` | GET | — | 读充电设置 |
| `/ssp-as/v1-0/app/vehicle-charge-threshold` | POST | `{vin, threshold}` | 写充电上限 |
| `/ssp-as/v1-0/app/vehicle-charge-appointment` | POST | `{vin, timing, timingChargeStatus}` | 写预约充电 |
| `/ssp-as/v1-0/app/vehicle-activate` | POST | — | 车辆激活 |
| `/ssp-as/v1-0/app/vehicle-activate-notify` | GET | — | 激活通知 |
| `/ssp-as/v1-0/app/vehicle-maints-plan-list` | GET | — | 保养计划 |
| `/ssp-as-mobile-api/v1-0/vehicles/charge-threshold-update` | POST | `ThresholdUpdateReq{vin, target}` | 充电上限（另一套） |
| `/ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch` | POST | `BatteryInsulationReq{vin, switchState}` | 电池保温 |
| `/ssp-as-mobile-api/v1-0/vehicles/charge-appointment-update` | POST | `AppointmentUpdateReq{vin, chargeOnOff, startTime, endTime, isContinue}` | 预约充电 |
| `/ssp-as-mobile-api/v1-0/vehicles/charge-appointment-on-off-update` | POST | `OnOffUpdateReq{vin, chargeOnOff, version}` | 预约充电开关 |
| `/ssp-as-mobile-api/v1-0/vehicles/ac-appointment-update` | POST | `AcAppointmentUpdateReq{vin, switchOn, temp, startTime, workingDay, flLevel, frLevel, rlLevel, rrLevel, steerSet, battWarmUp}` | 预约空调 |
| `/ssp-as-mobile-api/v1-0/vehicles/svm/take-photo` | POST | `TakePhoneReq{vin}` | 拍照 |
| `/ssp-as-mobile-api/v1-0/vehicles/{vin}/charge-setting` | GET | — | 读充电设置 |
| `/ssp-as-mobile-api/v1-0/vehicles/{vin}/charge-setting/{txId}/result` | GET | — | 充电设置结果轮询 |
| `/ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state` | GET | — | **实时状态（集成已在用）** |

> `L6 实测：前两批分别返回 100012（无权限）与 100035（服务暂时不可用）。`

### 2.2 通用 / X 系

| 端点 | 动词 | 用途 |
|---|---|---|
| `/ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command` | POST | 通用车控（65/69 条 M 系命令） |
| `/ssp-as-mobile-api/v1-0/remote-vehicle-control/{vin}/command/{opId}/result` | GET | 结果轮询（注意是 `v1-0`） |
| `/ssp-as-mobile-api/v1-0/vehicles/{vin}/parking-photos` | GET | 泊车照片 |
| `/ssp-as-mobile-api/v1-0/vehicles/tire/alarm/{vin}` | GET | 轮胎告警 |
| `/ssp-as-mobile-api/v1-0/vehicles/maint/plan/{vin}` | GET | 保养计划 |
| `/ssp-as-mobile-api/v1-0/vehicles/maint/item/reset` | POST | 保养项复位 |
| `/ssp-as-mobile-api/v1-0/vehicles/ota/upgrade` | POST | OTA 升级 |
| `/ssp-as-mobile-api/v1-0/vehicles/ota/upgrade/status` | GET | OTA 状态 |
| `/ssp-as-mobile-api/v1-0/vehicles/wakeup` / `wakeup-hu` | POST | 唤醒（另一种） |
| `/ssp-as-mobile-api/v1-0/vehicles/wechat-data-sync-update` | POST | 微信数据同步 |
| `/ssp-as-mobile-api/v1-0/vehicles/{vin}/location` | GET | 车辆位置 |
| `/ssp-as-mobile-api/v3-0/vehicles/info/basic/{vin}` | GET | 车辆基本信息 |
| `/ssp-as-mobile-api/v3-0/vehicles/energy-cost/monthly/current/{vin}` | GET | 月度能耗费用 |

### 2.3 集成已在用（**不要重复实现**）

```
/ssp-cloud-vss-service/mobile/vss/get-batch                    ← X 系实时信号
/ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state         ← M 系实时状态
/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send      ← 车控
/ssp-vehicle-control-service/ssp-vehicle-control/cmd-result    ← 车控结果
/iot-connect-manager-service/v2/wakeup                         ← 唤醒
/ssp-task-master-service/v1/**                                 ← 任务大师
/aisp-account-api/v1-0/vehicles/                               ← 车辆列表
/mms-api/v1-0/**                                               ← 消息
/lcp-bff-app-api/**                                            ← PNC 开关等
/lcp-bff-app-api/vehicle-control/v1/query-vehicle-charge-no    ← 充电单号
```

---

## 3. X 系命令表怎么用（98 条，含权威 cmdKey + cmdData）

`LXXVehicleConfig2025.json` 是**官方给的 `cmdKey` + `cmdData` 标准答案**，
集成里的 cmdKey/cmdData 是逆向推出来的，**可逐条比对纠错**。

示例（节选）：

| des | cmdKey | cmdData |
|---|---|---|
| 解锁车门 | `remoteVehLockControl` | `{"lockSw":"1"}` |
| 锁上车门 | `remoteVehLockControl` | `{"lockSw":"0"}` |
| 打开车窗 | `remoteVehWdwControl` | `{"flWindPosi":"99","frWindPosi":"99","rlWindPosi":"99","rrWindPosi":"99"}` |
| 车窗开缝 | `remoteVehWdwControl` | `{"flWindPosi":"10",…}` |
| 打开后备箱 | `remoteVehPlgControl` | `{"plgPosi":"100"}` |
| 关闭后备箱 | `remoteVehPlgControl` | `{"plgPosi":"0"}` |
| 寻车 | `remoteVehSearch` | `{"searchType":"0"}` |
| 闪灯 | `remoteVehSearch` | `{"searchType":"1"}` |
| 鸣笛 | `remoteVehSearch` | `{"searchType":"2"}` |
| 授权驾驶 | `remoteVehAuth` | `{}` |
| 打开充电口盖 | `cpCtrl` | `{"cpOpen":"ON"}` |
| 关闭充电口盖 | `cpCtrl` | `{"cpOpen":"OFF"}` |
| 后视镜折叠 | `rmCtrl` | `{"ctrlType":"FOLD","ctrlValue":"ON"}` |
| 后视镜加热 | `rmCtrl` | `{"ctrlType":"HEAT","ctrlValue":"ON"}` |
| 遮阳帘（一体） | `ssCtrl` | `{"fPos":"100","ctrlType":"ABS"}` |
| 遮阳帘（前后） | `ssCtrl` | `{"fPos":"100","rPos":"100","ctrlType":"ABS"}` |
| 打开前备箱 | `fTkC` | `{"lockSw":"1"}` |
| 冰箱模式 | `remoteVehFrgControl` | — |
| 开始充电 | `remote_charge_control` | `{}` ← **走 JOB，HTTP 必 2009** |
| 停止充电 | `remote_charge_control` | `{}` |
| 哨兵模式 | `sentinelModeSetting` | `{"sentinelSwitch":"1"}` ← **走 JOB** |
| 开始拍照 | `mobileVehSvm` | `{"vehImage":"veh_svm_image"}` ← **走 JOB** |
| 导航到目的地 | `navigate_to_poi` | `{"poi":…,"poiWaypoint":…,"routeName":…}` |
| 宠物退出并闭锁 | `quit_lock` | — |

**读表方法**（Python）：

```python
import json, pathlib
d = json.loads(pathlib.Path('assets/2025/LXXVehicleConfig2025.json').read_text(encoding='utf-8'))
for k, v in d.items():
    print(k, v['des'], v['cmdKey'], v.get('cmdData'))
```

---

## 4. 错误码对照（都是真机实测，别猜）

| code | 含义 | 何时出现 |
|---|---|---|
| `0` / `SUCCESS` | 成功 | — |
| `2009` | **命令走 JOB 通道，HTTP 不可达** | 用通道 A/B 发 `remote_charge_control` 等 |
| `100035` | **服务暂时不可用** | **X 系调 M 系 REST 端点**（如 L6 调 `charge-threshold-update`） |
| `100012` | **没有接口访问权限** | **X 系调 `/ssp-as/v1-0/app/*`**（老平台 App API） |
| `100005` | 签名错 | 头/签名构造不对（`_signed_call` 会自愈重试一次） |
| `pushState != 5` | 车控未完成 | 轮询未到终态 |

**排查顺序**：先确认 code 是 2009 还是 100035/100012 ——
前者是**通道问题**（改走别的通道或放弃），后者是**平台归属问题**（表拿错了）。

---

## 5. 集成现状（2026-10-12）

| 能力 | M 系（理想ONE） | X 系（L6 等） |
|---|---|---|
| 实时状态 | ✅ `v3-0/real-time-state` | ✅ VSS `get-batch` |
| 状态映射 | ✅ `m01_state.py` 28 项 | ✅ VSS 信号表 |
| 车控 | ✅ 通道 A（`cmd/send`） | ✅ 通道 A |
| 充电上限 | ⚠️ 已接 `set_charge_threshold`（**未真机验证**） | ❌ `cmd/send` 必 2009 → 只读 |
| 电池保温 / 预约充电 / 哨兵 / 拍照 | ❌ 仍走通道 A 被静态拒绝 | ❌ 同左 |
| 车型能力门控 | ✅ 官方 `version` 表 | ✅ 同左 |

**未验证的部分已明确标注**：`set_charge_threshold` 等 4 个方法按
「配置表 + OperateReq 字段」实现，M 系真机尚未实测。

---

## 6. 下一步（按性价比排序）

1. **M 系真机验证通道 B / M 系 REST**
   用理想 ONE 车主实测 `charge-threshold-update` / `battery-warm-switch`。
   若通了 → M 系的充电控制可以立刻解锁（这是本文最大的悬而未决项）。
2. **X 系 cmdKey/cmdData 逐条比对**
   拿 98 条官方表核对集成现有实现，修掉参数偏差。
   这是**纯静态、零风险、可测**的收益。
3. **M 系 `set_charge_threshold` 的平台门控**（已做）
   只给 M 系接 `sync_setter`，X 系保持原路径 —— 避免 X 系车主看到
   含义不明的 100035。

---

## 7. 复查这份文档时请一并核对

- [ ] 两张配置表是否随 APK 升级变了内容（`git diff` assets）
- [ ] `_JOB_CHANNEL_COMMANDS` 是否仍与 `commandDestParamsMap` 一致
- [ ] 新增的端点是否在 `li_api` 里**按平台**接（别再全局接）
- [ ] 本文的「实测」标记是否被新的实测推翻
