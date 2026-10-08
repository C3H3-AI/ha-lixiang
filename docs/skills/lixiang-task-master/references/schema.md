# 任务大师 · 技术参考（抓包与 APK 实证）

数据来源：2026-10-07 Reqable 真机抓包 `情景模式任务大师.har`（App 8.27.0）+
理想 App APK 反编译交叉验证。所有字段均为服务端实收格式。

## 1. 端点清单

Base：`https://api-app.lixiang.com`（集成内 `API_APP`）

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/ssp-task-master-service/v1/task-config/mob/my-task-by-vin/{VIN}?pageSize=50&pageNo=1&taskType=0` | 我的任务列表 |
| GET | `/ssp-task-master-service/v1/task-config/mob/detail/{VIN}/{configId}` | 任务详情 |
| POST | `/ssp-task-master-service/v1/task-config/mob/save/{VIN}` | 创建 |
| POST | `/ssp-task-master-service/v1/task-config/mob/update-task/{VIN}` | 更新（全量对象） |
| DELETE | `/ssp-task-master-service/v1/task-config/mob/delete/{VIN}/{configId}` | 删除 |
| GET | `/ssp-task-master-service/v1/task-basic/mob/condition-and-action/{VIN}` | 条件/动作字典（15 条件 + 17 动作，约 66KB） |
| GET | `/ssp-task-master-service/v1/square-recommendation/mob/query-task-list/{VIN}` | 广场推荐任务 |

鉴权（抓包实测 + 2026-10-08 修正）：`Authorization: Bearer <五件套token>` +
`X-CHJ-Sign` 签名头（集成 `_signed_call_task`）。
★ **签名串第 2 段版本必须与请求头 `x-chj-version`/`x-chj-app-version` 一致**
（实测：旧版本签名 + 新版本头 → `100005 请求签名错误`；两段同为同一版本 → 通过。
第 7 段语言 `zh-CN` / `zh-Hans-CN` 均可，**不影响校验**）。
★ 单换 `task-master` 会被 SSO 拒绝（HTTP 300 `access_denied`，且重登会引发
「每分钟重登+清缓存」风暴——已加 `_is_scope_denied` 守卫禁止对 scope 拒绝重登），
故固定使用 App subTokenData 权威五件套：
`remote-wakeup:wakeup veh-ctrl:cmd-result-get veh-ctrl:cmd-send vss:get-batch task-master`。
任务接口头照抄 App：`content-language=zh-CN`、`modelname=ANDROID`、
`version=8.27.0`、`x-chj-metadata`、`accept-language=zh-CN`、M01 UA
（★ 头里的版本一旦改动，**签名第 2 段必须同步改**，否则 100005）。

## 2. create 请求体（原样抓包）

```json
{
  "configName": "123",
  "configId": "mob_1791366893482",
  "automate": false,
  "voiceExecute": false,
  "runOnceFrequency": "2",
  "runOnce": false,
  "taskValue": {
    "conditions": [
      {"conditionType": "Microphone",
       "paramsDescs": ["已连接"],
       "params": [{"value": "connected", "key": "state"}]}
    ],
    "actions": [
      {"actionType": "PowerOutlet",
       "paramsDescs": ["打开"],
       "params": [{"value": "open", "key": "operation"}]}
    ]
  },
  "enabled": true
}
```

- `configId` 客户端生成：`mob_` + 13 位毫秒时间戳（集成 `build_task_payload` 自动做）。
- 响应统一：`{"message":"SUCCESS","data":null,"code":0,"success":true}`（57 字节）。

## 3. 列表响应条目（15 个字段）

```json
{"configId": "mob_1778760513248",
 "configName": "在外打开无感解锁关闭便捷上下车",
 "taskType": 0, "orderNo": 1,
 "createTime": 1778760514000, "updateTime": 1785723107000,
 "creatorShareCode": null, "creatorName": null, "shareCode": null,
 "automate": true, "enabled": true, "runOnce": false,
 "runOnceFrequency": 2, "voiceExecute": false,
 "taskValue": {"conditions": [...], "actions": [...]}}
```

`data` 直接是**数组**（实测 45 条）；条目含完整 `taskValue`，
所以启停开关可以整条回传 update，无需再拉 detail。

## 4. 实测的条件/动作样例（可直接复用的结构）

### 条件
| conditionType | params 要点 |
|---|---|
| `Microphone` | `state=connected`（麦克风已连接） |
| `OutRange` | 七件套：`address, lat, lon, radius, mapName, poiId, locationType`（地理围栏离开） |
| `InRange`（同族推断） | 同 OutRange 结构 |

### 动作
| actionType | params 要点 |
|---|---|
| `PowerOutlet` | `operation=open/close`（电源插座） |
| `AutoUnlock` | `operation=open`（自动解锁） |
| `EasyGetOnOff` | `operation=open/close`（便捷上下车） |
| `RadarVolume` | `level=small/mid/loud`（雷达音量） |
| `VoiceVolume` | `percentage=35`（语音音量，数字） |
| `RoadMode` | `mode=road/slippery`（公路/雨雪模式） |

字典里还有 `classification`（如 `ConditionLocations`/`ActionDrivings`）、
`paramStyle`、`support` 等元数据——**下发时可以不带**（save 样例没有也成功），
但类型名必须与字典一致。

## 5. 更新（update-task）实测请求体

与列表条目同构（多字段全量回传），服务端只要求含 `configId`；
集成实现是"GET 最新 → 合并用户字段 → POST 全量"。
实测样本（改一个围栏任务）：conditions 两条 OutRange + actions 两条，`enabled:true`。

## 6. 与其它子系统的边界

- **车控**（锁/窗/空调…）：`/ssp-vehicle-control-service/.../cmd/send`，双 token
  （MESH + VAT），失败码 2009=JOB 通道——与任务大师无关。
- **情景模式**：cmdKey `open/quit`，destParams `mob.metaJobService.sceneModeCtrl`
  → LiNdn 长连接，HTTP 必 2009，集成刻意不提供执行实体。
- **VSS 状态**：`/ssp-cloud-vss-service/mobile/vss/get-batch` 批量读信号。

## 7. 集成侧实现要点（改代码前先读）

- `li_api.py`：`SCOPE_TASK_MASTER`（App 权威五件套）、`EP_TASK_*`、
  `_task_call`（五件套 token + `_signed_call_task` 签名调用）、
  `get_tasks/save_task/update_task/delete_task`、`build_task_payload`。
- `coordinator.py`：`data["tasks"]`（120s 缓存，失败 60s 重试）、
  `data["task_error"]`（上浮到传感器属性）、`invalidate_task_cache()`。
- `sensor.py`：`LiTaskMasterSensor`（state=任务数）+ `_task_summary`。
- `switch.py`：`LiTaskSwitch`（动态注册，update-task 翻转 enabled，乐观 TTL 150s）。
- `__init__.py`：四个服务处理器（`_li_task_entries` 多车过滤）。
- 测试：上游仓库 `tests/test_task_master.py`（ast 结构断言 + payload 实测执行）。
