# 前端卡片（Lovelace Cards）

理想 App 风格的 **13 个自定义卡片**，UI 逐页对齐官方 App，随集成一起发布。

---

## 一、快速安装

### 1. 注册资源

卡片随集成发布，URL 前缀是 `/<domain>/`：

| 资源 URL | 类型 |
|---|---|
| `/lixiang_auto/lixiang-cards/lixiang-app-home.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-energy-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-charge-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-health-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-setting-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-scene-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-ad-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-climate-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-seat-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-location-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-vehicle-info-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-task-page.js` | module |
| `/lixiang_auto/lixiang-cards/lixiang-auto-bind.js` | module (引擎，**必须最先加载**) |

> 集合「设置 → 仪表盘 → ⋮ → 资源」添加，或在 `.storage/lovelace_resources` 里写。
> 也可以复制到 `<config>/www/lixiang-cards/`，URL 换成 `/local/lixiang-cards/...`。

### 2. 添加卡片

**最小配置 —— 什么都不用填：**

```yaml
type: custom:lixiang-app-home
```

卡片会**自动发现**实体（见下方「自动发现」章节）。多车时指定 VIN：

```yaml
type: custom:lixiang-app-home
vin: HLX32XXXXXXXXXXXX
```

**手动覆盖**（可选，手填优先于自动发现）：

```yaml
type: custom:lixiang-app-home
title: 我的理想
nav:
  energy: /lixiang/energy
  charge: /lixiang/charge
  health: /lixiang/health
  setting: /lixiang/setting
  scene: /lixiang/scene
  task: /lixiang/task
  climate: /lixiang/climate
  location: /lixiang/location
  vinfo: /lixiang/vinfo
range_elec: sensor.li_auto_l6_chun_dian_xu_hang_cltc
battery: sensor.li_auto_l6_dian_chi_dian_liang
```

---

## 二、★ 自动发现（核心特性）

**用户不用手填 90 个实体 ID。** 卡片按**中文名**自动匹配：

```
① 从 hass.entities 取 platform === 'lixiang_auto' 的实体
② 用 original_name（中文名）匹配，不用实体 ID（拼音会变，中文名稳定）
③ 用 device_id 归属校验（多车不串）
```

实测匹配率 **98.7%**（76/77 字段），唯一未匹配的是车辆本就没有的功能。

### 诊断卡（推荐加一张）

添加 `custom:lixiang-bindings-card` 可以看到：

```
┌─────────┬─────────┬──────────┐
│   76    │    1    │  98.7%   │
│ 已绑定   │ 未匹配   │  匹配率   │
└─────────┴─────────┴──────────┘
车型 理想L6 Pro [L6]          实体池 151

已绑定 (76)     ← 完整表格（字段 → 实体 ID）
未匹配          ● btn_start   —   ← 一键复制反馈
```

- 点「复制详情」→ 粘贴到 issue，帮我们适配新车型
- 点「重新扫描」→ 清缓存重跑

### 优先级

```
手填配置  >  自动发现  >  空（显示 —）
```

---

## 三、卡片清单（13 个）

| 卡片 | 说明 | 依赖服务 |
|---|---|---|
| `lixiang-app-home` | **车控首页** —— 8 圆按钮 + 双态 3D + 空调/位置/里程/电量/哨兵 + 9 个入口 | `get_travel` |
| `lixiang-energy-page` | **里程能耗** —— 环形图（陪伴里程 + 电/油占比）+ 智驾占比 + 年/月/日折叠 | `get_travel` |
| `lixiang-charge-page` | **充电** —— 实时状态 + 年月记录 + 单次明细（直流/交流）| `get_charge` |
| `lixiang-health-page` | **车辆健康** —— 胎压图（bar + 胎温）+ 车辆保养计划 | — |
| `lixiang-setting-page` | **车辆设置** —— 空调/充电/安全/远程操作（**可控制**）| — |
| `lixiang-scene-page` | **情景模式** —— 宠物/露营/擦车/离车不下电（**只读**）| — |
| `lixiang-ad-page` | **智驾统计** —— NOA/LCC/ACC 里程 + 占比 | — |
| `lixiang-climate-page` | **空调控制** —— 温度 ± + 空调/极速制冷/极速制热/除雪除冰 + 空气质量 | — |
| `lixiang-seat-page` | **座椅控制** —— 座椅俯视图：主/副驾 + 二排三座 + 方向盘加热（**可控制**）| — |
| `lixiang-location-page` | **车辆位置** —— 地图/坐标 + 距离 + 闪灯/鸣笛 + 驻车照片入口 | — |
| `lixiang-vehicle-info-page` | **车辆信息** —— 昵称/车牌/型号/车架号/配置等级 | — |
| `lixiang-task-page` | **任务大师（HA 版）** —— 用 App 的交互创建 **HA 自动化** | — |
| `lixiang-bindings-card` | **实体自动发现（诊断）** —— 查看绑定详情 | — |

### 首页导航图

```
                    ┌── 空调卡 ──→ 空调控制 ──→ 座椅控制
                    ├── 位置卡 ──→ 车辆位置
                    ├── 电量卡 ──→ 充电
   车控首页 ────────┼── 里程卡 ──→ 里程能耗
   /lixiang/app     ├── 哨兵卡 ──→（直接切换开关）
                    ├── 车辆健康 → 车辆健康
                    ├── 车辆设置 → 车辆设置
                    ├── 情景模式 → 情景模式
                    ├── 任务大师 → 任务大师
                    └── 钥匙管理 → 车辆信息
```

---

## 四、可选资源（图标与字体）

卡片**不强制依赖**这些资源 —— 缺失时自动降级（图标隐藏、字体回退系统字体），
功能完全不受影响（已测：拦截全部资源请求，13 个页面仍 0 JS 错误）。

想要**完全还原 App 外观**时自备：

### 图标（`/config/www/lixiang-icons/`）

```
ic_home_lock_off_lisa.png          车锁
ic_home_window_off_lisa.png        车窗
ic_home_tail_w_off_2025.png        尾门
ic_home_authorization_off_lisa.png 授权驾驶
ic_home_chrgporlid_off_lisa.png    充电口盖
ic_home_seat_heating3.webp         座椅加热
ic_home_fan_on.webp                通风 / 空调
ic_home_sentry.png                 哨兵
ic_home_energy / battery / oil / mileage / health / navigation / control ...
```

### 字体（`/config/www/lixiang-fonts/`）

```
licium_regular.ttf          理想官方字体（正文）
licium_medium.ttf
licium_bold.ttf
roboto_medium_numbers.ttf   数字专用
```

> ⚠️ **版权提示**：Licium 是理想汽车的商业字体，App 图标同样是理想的美术资源。
> 本项目**不分发**这些文件，请自行评估使用范围。

### 自定义路径

```yaml
type: custom:lixiang-app-home
icon_base: /local/my-icons
font_base: /local/my-fonts
```

---

## 五、3D 车模（可选）

```yaml
type: custom:lixiang-app-home
car_iframe: http://<你的主机>:8899/index.html
car_image: /local/lixiang-icons/icon_car_loc.webp   # 3D 不可用时的回退图
car_scroll_collapse: true      # 上拉自动收起（默认开）
car_scroll_threshold: 60       # 滚动多少 px 后收起
car_default_collapsed: false   # 默认是否收起
```

**交互**：拖动旋转 · 上拉自动收起 · 点右上角箭头手动切换。

---

## 六、任务大师（HA 版）

App 的「任务大师」是**云端规则引擎**（规则存在理想服务器，集成没有 API）。

本卡片用 **App 的交互**（如果 / 就执行）创建 **HA 自动化**：

| App 任务大师 | 本卡片（HA 自动化）|
|---|---|
| 任务名称 | `alias` |
| 如果（触发）| `trigger` |
| 就执行（动作）| `action` |
| 不添加"如果"→ 手动运行 | `trigger: []` |
| ☁️ 云端执行 | 🏠 **本地执行（更快，不依赖网络）** |
| 只能控制理想车 | **可联动所有 HA 设备** |
| 不能发通知 | **支持通知 / 脚本** |

内置 6 个车控模板（一键创建）：

```
无人关闭通风 · 有人自动通风 · 离车关遮阳帘防晒
低电量提醒 · 哨兵模式自动开启 · 长途驾驶疲劳缓解
```

写入 API：`POST /api/config/automation/config/{id}`（HA 会校验配置合法性）。

---

## 七、能力边界（诚实说明）

不可控的按钮**置灰并在点击时说明原因**，不会静默失败。

| 功能 | 状态 | 原因 |
|---|---|---|
| 车锁 / 车窗 / 尾门 | ✅ 可控制 | `remoteVehLockControl` / `WdwControl` / `PlgControl` |
| 空调（温度/开关/除霜）| ✅ 可控制 | `remoteVehACSmartControl` |
| 座椅加热/通风（9 路）| ✅ 可控制 | 同上 + `acCtrlType` |
| 方向盘加热 | ✅ 可控制 | 同上（`strgWhlHeatSw`）|
| 哨兵模式 | ✅ 可控制 | `sentinelModeSetting` |
| 寻车（闪灯 / 鸣笛）| ✅ 可触发 | `remoteVehSearch` + `searchType` |
| 远程拍照 | ✅ 可触发 | `remoteVehSvm` |
| 授权驾驶 | ✅ 可触发 | `remoteVehAuth`（首页快捷按钮走 `button.<车名>_授权驾驶`）|
| **充电盖（开/合）** | ✅ 可控制 | `cpCtrl` `{"cpOpen":"ON"/"OFF"}` —— 2026-10-09 **实车实测通过** |
| **后视镜加热** | ✅ 可控制 | `rmCtrl` `{"ctrlType":"HEAT","ctrlValue":"ON"/"OFF"}` —— 同批实车实测通过（660s 长命令）|
| **情景模式（4 个）** | ⚠️ **只读** | HTTP `quit` 实测返回 **2009**（需 JOB 通道）|
| **直线召唤** | ⚠️ **只读** | 同上（快照里按 `note` 置灰并说明，不静默失败）|
| **充电启停 / 上限** | ⚠️ **只读** | 2009（走 JOB）|
| **按时出发 / 冰箱预约** | ⚠️ **只读** | 推定同上 |
| **任务大师（App 版）** | ❌ 无 API | 云端规则引擎 → **用本卡的 HA 版替代** |
| 车牌号 | ⚠️ 暂不可用 | 接口需特殊 token（返回 100032）|
| 整车软件版本 | ⚠️ 暂不可用 | 集成未采集 |
| 驻车照片（图片）| ⚠️ 仅状态 | 集成只读状态，图片需 App 查看 |

> **按钮点不动的历史原因**（2026-10-09 修复，v1.4.6）：
> ① `cover.open` / `cover.close` 在 HA 里**不存在**（应为 `open_cover` / `close_cover`），
>    导致「车窗」「尾门」必然失败；② 「充电口盖」没有绑定字段、③「后视镜加热」
>    绑到了只读 `sensor.左后视镜`（自动发现引擎 `any:` 分支忽略了 domain）、
>    ④「除雪除冰」规则名写错（实体名是「除雪除冰」，不是「除霜」）。
> 回归守卫：`tests/test_frontend_bindings.py`（服务名白名单 + Node 真跑绑定引擎）。

> **2009 的准确含义**（2026-10-02 实测修正）：
> 命令**被服务端受理**（返回 requestId），但**车机侧不处理** → 需走 JOB（LiNdn）通道。
> 不是"命令未注册"（早期文档的说法不准确）。

---

## 八、无障碍

所有卡片支持：

- **键盘操作**：`Tab` 聚焦，`Enter` / `Space` 触发（145+ 个元素可达）
- **屏幕阅读器**：`role` + `aria-label` + `aria-pressed` / `aria-checked`
- **焦点可见**：`:focus-visible` 描边
- **尊重动效偏好**：`prefers-reduced-motion: reduce` 时禁用动画
- **深色模式**：跟随系统
- **资源清理**：13 个卡片都实现 `disconnectedCallback`

---

## 九、故障排查

| 现象 | 排查 |
|---|---|
| 卡片不显示 | 资源是否注册为 `module`；`Ctrl+Shift+R` 强刷 |
| 数据全是 `—` | 加一张 `custom:lixiang-bindings-card` 看自动发现结果 |
| 大量 404 | 图标/字体未提供（**可忽略**，功能不受影响）|
| 「加载失败」| 点「重新加载」；检查集成是否正常 |
| 折线图/里程空白 | 需 `get_travel` 服务可用（集成版本 ≥ 1.2.5）|
| 自动发现结果不对 | 用 `custom:lixiang-bindings-card` 的「复制详情」提 issue |

---

## 十、开发说明（几个踩过的坑）

这些都是**真实踩过**的，写下来避免重复：

### 1. Shadow DOM 陷阱

HA 卡片渲染在 **Shadow DOM** 内 —— `document.querySelector` **查不到元素**，
必须用 `this.querySelector` / `this.querySelectorAll`。

> 症状：设置页数值一直显示 `—`（因为赋值用了 `document.querySelectorAll`）。

### 2. 服务响应的参数位置

```javascript
callService(domain, service, data, target, notifyOnError, returnResponse)
//                                              ^5            ^6
```

`returnResponse` 是**第 6 个**参数。传第 5 个只会拿到 `{context}`。

### 3. 日明细必须带 year/month

`get_travel` **无参调用返回的是 `yearEnergyList`**（年列表），不含 `dailyList`。
要日明细必须传 `{ year, month }`。

### 4. 静态路径注册的正确 API

```python
# ✅ 正确（HA 2026.8）
from homeassistant.components.http import StaticPathConfig
await hass.http.async_register_static_paths([
    StaticPathConfig("/lixiang_auto", str(_cards_dir), False),
])

# ❌ hass.async_register_static_paths 不存在
```

### 5. 空结果不要缓存

自动发现引擎的 `_autoBind()` 在 `hass.entities` 未就绪时会返回 `{}`。
若缓存空值会导致**永久空绑定**（真实踩过：app/energy 页全空）。

```javascript
if (out && Object.keys(out).length) this._bindCache = out;  // ✅ 只缓存非空
```

### 6. 批量文本替换必须验证

用脚本改 JS 时，**每次替换都要 assert 结果**。静默失败会让人误以为改好了
（踩过 3 次：`#lowbat` 未插入、`_a11y` 缺失、`#b3ph` 消失）。

> 更稳的做法：**按行号插入**，然后 `node --check` + 浏览器实测。
