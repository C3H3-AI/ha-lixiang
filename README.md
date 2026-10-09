# Li Auto for Home Assistant

理想汽车（Li Auto）Home Assistant 集成 —— 实时车辆状态 + 远程控制。

[![Validate](https://github.com/C3H3-AI/ha-lixiang/actions/workflows/validate.yml/badge.svg)](https://github.com/C3H3-AI/ha-lixiang/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-1.4.6-blue.svg)

> ⚠️ **Beta 阶段** —— 功能可用，但边界场景尚未覆盖，不建议用于关键场景。
> 当前仅 **理想 L6** 长期验证；L7 / L8 / L9 / MEGA / i 系列**未验证**。
> 完整验证范围、已知问题与版本路线见 [项目状态与验证范围](#项目状态与验证范围)。
>
> 本项目为个人学习/研究用途，非理想汽车官方项目，未获官方授权。
> 使用可能违反理想汽车的服务条款，所有风险由使用者自行承担。
> 请勿用于商业用途，请勿公开你的账号、车辆、位置等敏感信息。

---

## 目录

- [功能](#功能)
- [安装](#安装)
- [配置](#配置)
- [实体](#实体)
- [服务](#服务)
- [前端卡片（理想 App 风格）](#前端卡片理想-app-风格)
- [通知事件](#通知事件)
- [故障排查](#故障排查)
- [已知限制](#已知限制)
- [升级注意（实体 ID 变更）](#升级注意实体-id-变更)
- [项目状态与验证范围](#项目状态与验证范围)
- [技术说明](#技术说明)
- [开发](#开发)
- [更新日志](#更新日志)
- [赞助](#赞助)
- [许可](#许可)

---

## 功能

- **实时状态**（156 个信号）：电量、续航、门锁、车窗、胎压、温度、
  充电状态、位置、座椅加热、空调、哨兵模式等
- **远程控制**：锁车/解锁、空调（开关/温度/快热快冷/除霜）、车窗、尾门、
  寻车（含闪灯/鸣笛）、远程启动、哨兵开关、远程拍照、
  座椅加热/通风（8 个位置，含档位）、方向盘加热
- **车辆定位**：GPS 轨迹（可显示在地图上）
- **服务器通知**：拉取理想服务器的车辆预警通知（充电完成、电量不足等）
- **任务大师**（v1.4.0+）：查看车机「任务大师」的任务列表，支持**创建 / 查询 /
  更新 / 删除**任务，并按车上任务数量**动态注册启停开关**
- **车型自适应**：自动探测车辆支持的功能，不同的车显示不同的实体
- **账号自适应**：识别车主 / 家人共享 / 试驾（`vehicle_role.py`，复刻 App 的 `relationType`）
- **多车支持**：一个账号多辆车（每辆车独立接入）

> ⚠️ **充电控制暂不可用**：充电启停 / 上限 / 预约 / 保温这 6 个实体
> **状态可读、控制不可用** —— 它们走理想 App 的 LiNdn(JOB) 长连接，
> HTTP 车控接口不支持。集成会在属性中标注「只读原因」，
> 并在点击时给出明确提示（而不是静默失败）。详见 [已知限制](#已知限制)。

---

## 安装

### 方式一：HACS（推荐）

1. HACS → 集成 → 右上角菜单 → 自定义存储库
2. 添加本仓库地址（`https://github.com/C3H3-AI/ha-lixiang`），类别选「Integration」
3. 搜索 "Li Auto" 安装
4. 重启 Home Assistant

### 方式二：手动

把 `custom_components/lixiang_auto` 复制到你的 HA 配置目录：

```bash
cp -r custom_components/lixiang_auto /path/to/homeassistant/config/custom_components/
```

然后重启 Home Assistant。

---

## 配置

1. HA → **设置 → 设备与服务 → 添加集成**
2. 搜索 **Li Auto**
3. 输入理想账号的**手机号 + 密码**

### 首次登录需要验证

理想对新设备有风控：首次登录需要**短信验证码**，而验证码有
**滑动验证**保护（第三方，无法自动完成）。

集成会引导你：

```
① 添加集成 → 输手机号 + 密码
② 集成显示一个「辅助页面」链接
③ 打开链接 → 点【▶ 点这里打开理想登录页】
④ 在新窗口里：输手机号+密码 → 点获取验证码 → 拖动滑块 → 收短信 → 输验证码 → 登录
⑤ 回到辅助页面，看到绿色提示 = 成功
⑥ 回 HA 点【提交】继续
```

**验证成功后，这个设备会被理想标记为受信任，以后都不用再验证。**

> 💡 **关于 API 签名凭据**
> 集成已内置签名所需的默认凭据（`hac_key` / `keyId` / `deviceId`），
> 登录后还会从服务端 `GET /aisp-app-api/v1-0/keySuite` 获取密钥套件
> （响应经 App 内嵌常量解密 + AES-256-CTR 派生）—— **开箱即用**。
>
> 若遇到 `100005 签名错误`（密钥套件约 **120 天轮换一次**），
> 可在集成选项里手动填入更新后的凭据。

### 轮询间隔

默认 60 秒（可在集成选项里改，30~3600 秒）。

---

## 实体

**174 个实体**（其中 **136 个默认启用**、38 个诊断类默认隐藏；L6 实测，
其他车型按功能探测自动增减），按平台分类：

| 平台 | 数量 | 说明 |
|---|---|---|
| sensor | 65 | 电量、续航、温度、胎压、充电… |
| binary_sensor | 37 | 门锁、车窗、充电枪、告警… |
| **fan** | **10** | **座椅加热/通风（关闭·低·中·高，含二排左中右）+ 方向盘加热** |
| **switch** | **7** | **快热、快冷、除霜、哨兵、方向盘加热、充电相关** |
| button | 5 | 寻车、授权驾驶、闪灯、鸣笛、远程拍照 |
| **cover** | **2** | **尾门 / 全车窗** |
| number | 2 | 空调设定温度、充电上限 ⚠️ |
| select | 2 | 空调控制类型、充电模式 ⚠️ |
| time | 2 | 充电开始/结束时间 ⚠️ |
| climate | 1 | 空调（温度/模式）|
| lock | 1 | 车锁 |
| device_tracker | 1 | 车辆位置 |
| notify | 1 | 通知事件 |

> ⚠️ = **状态可读但控制不可用**（走 LiNdn 通道），详见 [已知限制](#已知限制)。

> 💡 **域选择说明**：
> · 座椅加热/通风 → `fan`（HA 原生「关闭/低/中/高」档位 UI）
> · 尾门/车窗 → `cover`（支持 open/close + 位置读回，无需单独开/关按钮）
> · 哨兵/快冷/快热/除霜 → `switch`（带状态读回，一眼可见开关状态）

诊断类实体（OTA、保养、版本、遮阳帘、后视镜加热状态、主驾有人等）默认隐藏，
需要时可在设备页面启用。

> 💡 别混淆：`binary_sensor.<车名>_左/右后视镜加热`（诊断、默认隐藏、只读状态）
> 与 `switch.<车名>_后视镜加热`（可控开关，2026-10-09 实车实测通过）是两个实体。
> 充电口盖同理：`binary_sensor.充电口盖` 只读展示，`switch.充电盖` 可开合。

> 💡 **任务大师相关实体（v1.4.0+，未计入上表数量）**：
> · `sensor.<车名>_任务大师` —— 任务总数；属性含每个任务的启用状态与 `config_id`
> · `switch.<车名>_<任务名>` —— **按车上任务数量动态注册**，用于启停单个任务
>   （车上没有任务时不出现；在 App 里新增任务后会自动出现）
> · 删除任务后，对应的开关会保留为「不可用」状态（HA 实体注册表的既有行为）

---

## 服务

| 服务 | 说明 |
|---|---|
| `lixiang_auto.refresh` | 立即刷新一次数据 |
| `lixiang_auto.wakeup` | 唤醒休眠的车辆 |
| `lixiang_auto.dump_ability` | 导出车型能力表（探测本车支持哪些功能）|
| `lixiang_auto.get_travel` | 查询行程 / 陪伴里程 |
| `lixiang_auto.get_charge` | 查询充电记录 |
| `lixiang_auto.get_svm_photo` | 查询驻车照片 |
| `lixiang_auto.get_tasks` | 查询任务大师任务列表 |
| `lixiang_auto.create_task` | 创建任务大师任务 |
| `lixiang_auto.update_task` | 更新任务大师任务（只传要改的字段）|
| `lixiang_auto.delete_task` | 删除任务大师任务 |

> 除 `wakeup` / `refresh` 外的服务都支持可选 `vin` 字段（多车场景指定车辆），
> 单车时省略即可。

### 任务大师（v1.4.0+）

任务大师走**独立的 HTTP 服务**（`/ssp-task-master-service`），与车控命令
（`cmd/send`）是两条不同通道 —— 因此不受「充电控制走 LiNdn 通道不可用」的
限制影响。

- **参数说明与 JSON 构造** → [技能文档](docs/skills/lixiang-task-master/SKILL.md)
- **条件 / 动作类型字典** → [schema.md](docs/skills/lixiang-task-master/references/schema.md)

```yaml
# 创建任务（conditionType / actionType 必须取自上面的字典，不要自造）
service: lixiang_auto.create_task
data:
  name: 我的任务
  conditions: []          # 留空 = 手动触发
  actions:
    - actionType: <取自字典>
      params:
        - key: <取自字典>
          value: "<值>"
```

获取 `config_id` 的三种方式：**「任务大师」传感器的属性**、`get_tasks` 的返回值、
或 `create_task` 的响应。

> · `update_task` 会**先拉线上最新再合并你传的字段** —— 只传要改的字段，
>   未传的保持原值。
> · `delete_task` 成功后，对应的启停开关会转为「不可用」。
> · 写操作成功后集成会自动失效缓存并刷新，无需手动再调 `refresh`。

---

## 前端卡片（理想 App 风格）

集成自带 **13 个自定义卡片**，UI 逐页对齐理想 App。

### ✨ 零配置：自动发现实体

**用户不用手填 90 个实体 ID** —— 卡片按**中文名**自动匹配实体（实测匹配率 98.7%）：

```yaml
type: custom:lixiang-app-home
# 完了。其他全自动。
```

多车时指定 VIN：

```yaml
type: custom:lixiang-app-home
vin: HLX32XXXXXXXXXXXX
```

### 卡片清单

| 卡片 | 说明 |
|---|---|
| `lixiang-app-home` | **车控首页** —— 8 圆按钮 + 双态 3D + 空调/位置/里程/电量/哨兵 + 9 个入口 |
| `lixiang-energy-page` | **里程能耗** —— 环形图（陪伴里程 + 电/油占比）+ 智驾占比 + 年/月/日折叠 |
| `lixiang-charge-page` | **充电** —— 实时状态、年月记录、单次明细 |
| `lixiang-health-page` | **车辆健康** —— 胎压图（bar + 胎温）+ 车辆保养计划 |
| `lixiang-setting-page` | **车辆设置** —— 空调/充电/安全/远程操作（可控制）|
| `lixiang-scene-page` | **情景模式** —— 宠物/露营/擦车/离车不下电（只读）|
| `lixiang-ad-page` | **智驾统计** —— NOA/LCC/ACC 里程与占比 |
| `lixiang-climate-page` | **空调控制** —— 温度 + 空调/极速制冷/极速制热/除雪除冰 + 空气质量 |
| `lixiang-seat-page` | **座椅控制** —— 座椅俯视图：主/副驾 + 二排三座 + 方向盘加热（可控制）|
| `lixiang-location-page` | **车辆位置** —— 地图/坐标 + 距离 + 闪灯/鸣笛 + 驻车照片 |
| `lixiang-vehicle-info-page` | **车辆信息** —— 昵称/车牌/型号/车架号/配置等级 |
| `lixiang-task-page` | **任务大师（HA 版）** —— 用 App 的交互创建 **HA 自动化** |
| `lixiang-bindings-card` | **实体自动发现（诊断）** —— 查看绑定详情、一键复制反馈 |

### 特性

- **自动发现** —— 按中文名匹配，零手填；`custom:lixiang-bindings-card` 可查看绑定详情
- **车型识别** —— 自动读设备注册表（理想L6 Pro / L6 / 配置等级 / 智驾等级）
- **能力边界诚实标注** —— 不可控的按钮置灰并说明原因，不会静默失败
- **任务大师替代** —— App 的云端规则用 **HA 自动化**实现（本地执行，可联动所有设备）
- **无障碍** —— 145+ 元素键盘可达、`aria-label` 齐全、尊重 `prefers-reduced-motion`
- **资源可选** —— 图标/字体缺失时优雅降级（功能不受影响）
- **离线友好** —— 数据读不到时显示「加载失败 + 重试」，不空白

📖 **安装、配置、能力边界、排查详见 [docs/CARDS.md](docs/CARDS.md)**

> 卡片**不强制依赖**图标与字体 —— 缺失时自动降级。
> 如需完全还原 App 外观，可自备资源（见文档「可选资源」章节）。

---

## 通知事件

集成会监听理想服务器的车辆通知，并以 HA 事件形式抛出：

```yaml
automation:
  - alias: 理想车辆告警
    trigger:
      - platform: event
        event_type: lixiang_auto_notification
        event_data:
          category: vehicle      # 只监听车辆通知（过滤广告）
    action:
      - service: notify.mobile_app_xxx
        data:
          title: "🚗 {{ trigger.event.data.title }}"
          message: "{{ trigger.event.data.summary }}"
```

---

## 故障排查

### 帮助 → 下载诊断

设备页面有「下载诊断」按钮，会导出脱敏的 JSON（不含密码/密钥/位置）。

### 常见问题

**Q: 提示"需要短信验证"**
A: 正常流程，按上面「首次登录需要验证」操作。

**Q: 实体显示未知（unknown）**
A: 车辆离线时部分信号可能无数据。集成会保留最后一次有效值。

**Q: 无法控制车辆**
A: 检查集成选项里「允许远程控制」是否开启。

**Q: 数据不更新**
A: 车辆可能离线（集成会自动跳过轮询以省流量）。
   可用 `lixiang_auto.wakeup` 服务唤醒。

**Q: 任务大师传感器显示 0，或服务列表里找不到任务大师服务**
A: 先看「任务大师」传感器属性里的**「拉取错误」**字段（会写明原因）。常见情况：
   - **必须用手机号 + 密码登录**（任务大师不支持其它登录方式）
   - 车上确实还没有任务 —— 列表为空是正常的
   - 接口偶发限流（集成有 120 秒缓存 + 失败重试，稍后自行恢复）
   - 服务列表里找不到 → 集成版本低于 v1.4.0，或改了文件后**没有重启 HA**
     （集成文件变更必须重启，重载集成无效）
   完整排障表见 [技能文档](docs/skills/lixiang-task-master/SKILL.md)。

**Q: 充电控制点了没反应 / 提示「充电走 LiNdn 通道，当前版本不支持控制」**
A: **这是已知限制，不是故障。** 充电启停 / 上限 / 预约 / 保温走理想 App 的
   **LiNdn(JOB) 长连接**，而 HTTP 车控接口（`cmd/send`）不支持这些命令。
   - ✅ **状态照常可读**（是否充电中、上限、预约时段等）
   - ❌ **控制不可用**（点击会立即给出上述明确提示，不会静默失败）

   这些实体的属性里有 `只读原因` 字段，可在「开发者工具 → 状态」查看。

**Q: 我是家人共享账号，功能会比车主少吗？**
A: **车控、状态读取等主要能力与车主基本一致**，甚至多于 App。
   实测（2026-09-28）：App 界面只给家人显示车锁和空调，但服务端
   **不限制**其他车控（车窗/尾门/座椅/方向盘/寻车/拍照/哨兵 均实测通过）；
   位置、保养、里程也照常返回。

   **但有两项是服务端按账号角色硬限制，只有车主能用**：

   | 功能 | 车主 | 家人 / 试驾 |
   |---|---|---|
   | **任务大师**（列表 / 创建 / 启停 / 删除）| ✅ | ❌ 服务端不返回数据 |
   | **充电记录 / 充电量**（本月、累计、能耗页）| ✅ | ❌ 服务端不返回数据 |

   > 从 v1.4.5 起，集成会**先判断账号角色**：非车主时不再反复请求
   > （避免"失败 → 定时重试 → 一直刷警告"），相关实体与服务会直接
   > 标注「仅车主账号可用」。这是服务端限制，不是配置问题，无需排查。

   另外 OTA 相关与行程自定义查询也是服务端真拦（返回 `120001`）。

---

## 已知限制

| 项 | 状态 | 说明 |
|---|---|---|
| **充电控制** | ❌ 不可用 | 走 LiNdn(JOB) 通道，HTTP 接口不支持；状态仍可读 |
| **OTA 相关** | ❌ 无数据 | 服务端按账号拦截（家人账号返回空）|
| **行程自定义查询** | ❌ 不可用 | 服务端返回 `120001` |
| **按时出发** | 👁 只读 | 可看开关状态与计划内容；**不做可控开关** —— 它本质是自定义模式，HA 自动化可实现同等效果，且写命令走 JOB 通道 |
| **场景模式 / 冰箱预约** | ❌ 未实现 | 走 JOB 通道 |
| **宠物模式 / 洗车模式** | ❌ 未实现 | App 8.25.3+ 新增，走 JOB 通道 |
| 极速制冷/制热状态 | ⚠️ unknown | App 无独立状态路径 |
| 充电位置 | — | 该信号已修正语义：是「仅在此地预约」开关，不是位置 |

### 为什么车控走不了 HTTP（2026-09-26 逆向结论）

App 的路由规则（`LiveNetControlRouter.resolveRoute()`）：

```kotlin
if (key.contains("mob.vehCtrlService.vehCtrlJobList"))
    VEH_CONTROL     // ← 走 HTTP cmd/send（我们能实现）
else
    JOB             // ← 走 LiNdn（NDN），HTTP 不执行
```

充电的 `destParams = "mob.metaJobService.remoteChargingControl"`
不含 `vehCtrlJobList` → **走 JOB → HTTP 发不出去**（服务端返回
`pushState=7 resultCode=2009`）。

**参数已验证全对**（cmdKey / cmdData / expire / jobExpire / token），
只是**通道不对** —— 不是"没逆向好"，是 HTTP 通道根本不支持。

LiNdn 是 Rust 实现的 NDN 协议栈（`liblivenet.so`，9.4 MB），
需要 JOB_PORT token + GFM forwarding hint + HTTP-over-NDN 封装。

> ✅ **这些功能的 sensor 全部正常** —— 可以只看不用改。

---

## 升级注意（实体 ID 变更）

HA 的实体注册表**不会**因为平台或名称变化而自动改名 ——
升级后旧实体不会消失，而是变成「**不可用**」的僵尸实体，
引用它的自动化也会失效。

已知的 ID 变更：

| 实体 | 旧 ID | 新 ID | 原因 |
|---|---|---|---|
| 方向盘加热 | `fan.…_fang_xiang_pan_jia_re` | `switch.…_fang_xiang_pan_jia_re` | 协议只支持开/关，从 fan(3档) 改为 switch |

**升级后请：**

1. 在 **设置 → 设备与服务 → 实体** 中搜索旧 ID，删除显示为「不可用」的僵尸实体
2. 检查自动化 / 仪表盘里对旧 ID 的引用并改为新 ID
3. 「方向盘加热」现在只有开/关（**没有档位**）—— 这是正确的：
   协议白名单里 `strgWhlHeatSw` 属 ON/OFF 类，下发 `LEVEL3` 服务端不接受

---

## 项目状态与验证范围

> 本节说明 Beta 阶段的**验证边界** —— 哪些经过实测、哪些还是未知。

### 验证范围

| 项 | 状态 |
|---|---|
| 车型 | ✅ 理想 L6（一辆，长期运行）<br>❓ L7 / L8 / L9 / MEGA / i 系列**未验证** |
| 账号 | ✅ 车主账号<br>✅ **家人共享账号**（2026-09-28 实测）<br>❓ 试驾账号**未验证** |
| 多车 | ✅ 一个账号多辆车<br>❌ 一辆车接两个账号（VIN 冲突）|
| 信号语义 | ✅ **已用 App 官方 spec 全量审计**（150 信号 × 1563 路径，2026-09-28）<br>发现并修正 2 处语义错误 |
| 车控（新增两路）| ✅ **充电盖（`cpCtrl`）· 后视镜加热（`rmCtrl`）实车实测通过**（2026-10-09，开/关均生效）|
| 首次登录 | ⚠️ 辅助页面方案**刚验证 1 次**，不同网络/浏览器未测 |
| 单元测试 | ✅ **1188 个通过**（signals / rendering / policy / coordinator / features / vehicle_role / task_master / 卡片绑定 / 发布流程）<br>❓ 实车端到端仍需手工验证 |

### 2026-10-09 实车新增验证：充电盖 / 后视镜加热

这两路车控 2026-10-07 由 APK 反编译得到（`XVehicleJobHelper.handleCmdKey`），
2026-10-09 由**实车实测确认可用**：

| 实体 | 命令 | 状态源 | 实测结论 |
|---|---|---|---|
| `switch.<车名>_充电盖` | `cpCtrl` `{"cpOpen":"ON"/"OFF"}` | `ChrgPorLidStsV2`（-1 无效 / 0 关 / 非 0 开）| ✅ 开/关均生效，状态回读一致 |
| `switch.<车名>_后视镜加热` | `rmCtrl` `{"ctrlType":"HEAT","ctrlValue":"ON"/"OFF"}` | `RearMirro.LHeatSts/RHeatSts`（任一非 0 → 开）| ✅ 开/关均生效；660s 后按 App 语义自动停止 |

> 补充说明：2026-09-26 曾判定 VAT token 的 `cpCtrl` scope 被服务端 `access_denied`。
> 实车结果表明**车控通道的 cmdKey 分发不受该 scope 判定影响** —— 那条结论只针对
> 旧版 VAT 的 scope 申请，不代表充电盖不能控制。
>
> 只读的 `binary_sensor.<车名>_充电口盖`（展示用）与可控制的 `switch.充电盖` 是两个实体；
> 卡片的「充电口盖」按钮走的就是后者。

### 家人共享账号（2026-09-28 实测）

App 按 `relationType` 区分账号（车主 / 家人共享 / 试驾），实测结论：

| 类别 | App 行为 | 服务端 |
|---|---|---|
| **车控命令** | 界面只显示车锁/空调 | ✅ **不限制**（锁/窗/尾门/座椅/方向盘/寻车/拍照/哨兵 30 项实测通过）|
| 车辆位置、保养、里程 | 隐藏入口 | ✅ **照常返回**（实测能拿到 GPS 坐标）|
| OTA、行程自定义查询 | 隐藏入口 | ❌ 真拦（`120001`）|

**即：App 的"家人限制"大部分是 UI 隐藏，不是权限拦截。**
本集成因此对家人账号提供的能力**多于 App**（这是有意的）。

### 已知问题

- 部分信号语义仍在核实（`charge_gun_ac` 等）
- 车控命令下发后，车辆状态可能有几十秒延迟才同步
  （已用「乐观更新 + TTL」缓解，见下）
- 一辆车被第二个账号接入会被拒绝（VIN 唯一性冲突，HA 限制）
- 任务大师接口偶发限流（集成有 120 秒缓存 + 失败重试，正常使用无感）

### ⚠️ 待实车验证的控制项

以下 controlType 在 App 反编译中**未找到**，是依据同族命名**推测**的：

| 实体 | 推测的 controlType | 依据 |
|---|---|---|
| 二排中座椅加热 | `secMSeatHeatSw` | 状态信号 `SMSeatHeatState` 存在 |
| 二排左座椅通风 | `secLSeatVentSw` | 状态信号新鲜（09-23/09-24）|
| 二排右座椅通风 | `secRSeatVentSw` | 同上 |

若点击后日志出现 `resultCode=2009`，说明服务端不认该 controlType，
请提 [Issue](https://github.com/C3H3-AI/ha-lixiang/issues) 告知，我们会改为「只显示状态」。

### 💡 状态同步机制（乐观更新）

车机上报状态有延迟（几秒~几十秒）。为避免"刚点开开关就显示关闭"，
集成采用**乐观更新 + TTL**：

1. 下发命令后，立即用目标值显示（乐观值）
2. 45~150 秒内，若服务端状态还没跟上 → 继续显示乐观值
3. 服务端状态追上 或 超过 TTL → 以服务端为准

适用：座椅档位 / 空调温度 / 尾门 / 车窗 / 哨兵 / 快冷快热。

### 版本路线

- `1.x` —— Beta（当前）：功能持续补齐，边界场景逐步覆盖
- `2.x` —— 稳定版（条件：多车型验证 + 长期观察）

### 反馈与交流

遇到问题请提 [Issue](https://github.com/C3H3-AI/ha-lixiang/issues)，
并附上「设备 → 下载诊断」导出的 JSON（已脱敏）。

也欢迎加入 QQ 群交流：**1094493886**

---

## 技术说明

- 通信方式：HTTPS（理想 App 的 API），非 MQTT
- 登录：PAKE 协议（手机号 + 密码）
- 状态读取：VSS 实时信号通道
- 车辆控制：车控 API（需要 VAT token）
- 任务大师：独立 HTTP 服务（`/ssp-task-master-service`），与车控通道分离
- 车控路由：只有 `mob.vehCtrlService.vehCtrlJobList` 类命令走 HTTP，
  其余走 LiNdn(JOB) 长连接（见 [已知限制](#已知限制)）

---

## 开发

### 本地检查

```bash
# 安装 pre-commit hook（提交前自动检查语法/JSON/敏感信息）
cp .github/pre-commit.sh .git/hooks/pre-commit && chmod +x .github/pre-commit.sh
```

### 运行测试

```bash
PYTHONUTF8=1 python -m pytest tests/ -q
```

### 版本发布

```bash
./bump.sh patch     # 1.4.0 → 1.4.1（修 bug）
./bump.sh minor     # 1.4.0 → 1.5.0（加功能）
./bump.sh major     # 1.4.0 → 2.0.0（不兼容变更）
```

推送到 `main` 且 `manifest.json` 版本号增大后，CI 会**自动打 tag 并生成
草稿 Release**（含 zip 资产与自动分组更新日志）—— 人工 review 后点发布即可。

> ⚠️ 不要手动抢跑创建 tag/release：版本比较会因此跳过，导致自动化失效。

### CI

推送到 `main` 或提 PR 时自动运行：

| 检查 | 说明 |
|---|---|
| **hassfest** | HA 官方集成结构校验 |
| **HACS validate** | HACS 规范校验 |
| **lint & security** | Python 语法 + JSON + 敏感信息 + manifest 字段 |
| **pr guard** | PR 标题规范（Conventional Commits）+ 分支复用检查 |

### 双副本同步

集成在测试机运行时，代码与仓库是两份。使用同步脚本：

```bash
./li-sync.sh status            # 查看差异
./li-sync.sh push-repo         # 测试机 → 仓库
./li-sync.sh commit "说明"     # 同步 + 提交 + 推送
```

> 注：HA 无法从软链接加载 custom_component，所以必须双副本。

### 技能文档

面向 AI 助手（及贡献者）的操作手册位于 `docs/skills/`：

| 文档 | 内容 |
|---|---|
| [`docs/skills/lixiang-task-master/SKILL.md`](docs/skills/lixiang-task-master/SKILL.md) | 任务大师服务调用、JSON 构造、排障 |
| [`docs/skills/lixiang-task-master/references/schema.md`](docs/skills/lixiang-task-master/references/schema.md) | 接口/条件/动作字典与鉴权说明 |

---

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。当前版本 **v1.4.6**。

---

## 赞助

如果这个集成帮到了你，欢迎请我喝杯咖啡 ☕

| 微信支付 | 支付宝 |
|:--------:|:------:|
| ![微信](sponsor/wechat.jpg) | ![支付宝](sponsor/alipay.jpg) |

---

## 许可

MIT License

第三方商标（理想汽车、Li Auto 等）归其各自权利人所有。
