---
name: lixiang-task-master
description: 管理 Home Assistant 集成 lixiang_auto 的「任务大师」功能：生成和讲解 create_task / get_tasks / update_task / delete_task 四个服务的调用写法，构造任务 conditions/actions 的 JSON，获取 config_id，以及排查任务数为 0、创建失败、服务列表不显示等问题。Use when the user mentions 任务大师、创建任务/改任务/删任务、条件动作、config_id、lixiang_auto.create_task, or asks to turn a natural-language request into a Li Auto automation task. 不适用于车控命令（车锁/车窗等 cmd/send 通道）或情景模式开关。
---

# 理想任务大师 · HA 集成操作

针对 Home Assistant 自定义集成 `lixiang_auto`（部署位置：HA 配置目录下的
`custom_components/lixiang_auto`；修改文件后**必须重启 HA**，重载集成无效）。

## Important（先记住这五条）

1. 任务大师走**独立 HTTP 服务** `/ssp-task-master-service`，与车控 `cmd/send`（易 2009）、
   LiNdn 长连接无关——遇到 2009 不要往任务大师上联想。
2. `update_task` 是**先拉线上最新、再合并你传的字段**——只传要改的字段，没传的保持原值。
3. `config_id` 形如 `mob_1791366893482`（客户端生成），来源：任务大师传感器属性、
   `get_tasks` 返回、或 `create_task` 的响应。
4. 任何写服务成功后集成会**自动失效缓存并刷新**，不要额外调 refresh。
5. 条件/动作的 `params` 是 `[{key, value}]` 数组，value 多为字符串；**不要发明
   conditionType/actionType**，只能用字典里存在的（见 references/schema.md 实测样例，
   完整字典在 App 任务编辑页，或接口 `GET /task-basic/mob/condition-and-action/{VIN}`）。

## Instructions

### 第 1 步：确定操作类型 → 对应服务

| 用户意图 | 服务 | 必填字段 |
|---|---|---|
| 新建任务 | `lixiang_auto.create_task` | `name`、`actions` |
| 查列表/拿 config_id | `lixiang_auto.get_tasks` | 无（可选 `vin`） |
| 改任务（改名/换条件/启停） | `lixiang_auto.update_task` | `config_id` |
| 删任务 | `lixiang_auto.delete_task` | `config_id` |

带响应的服务在开发者工具里执行时勾选"返回响应"；脚本/自动化里用 `response_variable` 接。

### 第 2 步：生成服务调用（模板）

创建（YAML）：

```yaml
service: lixiang_auto.create_task
data:
  name: 到家自动解锁
  conditions:
    - conditionType: OutRange
      params:
        - {key: address, value: "家的地址"}
        - {key: lat, value: "28.111128"}
        - {key: lon, value: "121.253022"}
        - {key: radius, value: "200"}
        - {key: mapName, value: amap}
        - {key: poiId, value: ""}
        - {key: locationType, value: ""}
  actions:
    - actionType: AutoUnlock
      params:
        - {key: operation, value: open}
  automate: true          # 可选：voice_execute/run_once/enabled 同理
```

更新（只改启停举例；改条件/动作/名字同理，字段都是可选的）：

```yaml
service: lixiang_auto.update_task
data:
  config_id: mob_1791366893482
  enabled: false
```

删除：`service: lixiang_auto.delete_task` + `config_id`。
查询：`service: lixiang_auto.get_tasks`（响应里 `tasks[]` 含完整 taskValue）。

### 第 3 步：把自然语言变成 conditions/actions

1. 先判断需求是"条件"（何时触发）还是"动作"（做什么），各取字典中同类型的条目；
2. 参数照抄 references/schema.md 的实测样例结构（同类型的 key 组合基本固定，
   如 OutRange 必须带 address/lat/lon/radius/mapName/poiId/locationType 七件套）；
3. 生成后提醒用户：**首次执行任务以 App 内验证一次**，集成侧无法保证车辆侧执行效果。

## Troubleshooting

| 症状 | 原因 | 处置 |
|---|---|---|
| 任务大师传感器 = 0 | 列表拉取失败或文件未部署 | 看传感器属性**「拉取错误」**：`li_api 缺少 get_tasks` → 拷全 `li_api.py/coordinator.py/sensor.py`；`无 li_api` → 集成未用密码登录；HTTP 403 → scope/头问题（scope 已固定为 App 权威完整五件套；任务接口已照抄 App 头并同步重签，2026-10-08 修正——若仍 403，把「拉取错误」全文发回分析） |
| 服务列表里没有 create_task 等 | `__init__.py` / `services.yaml` 未部署 | 覆盖这两个文件并**重启 HA**（重载集成无效，Python 模块有 import 缓存） |
| 创建/更新报 LiApiError | 服务端拒绝（参数/权限） | 读错误文本中的服务端响应；检查 conditionType/actionType 是否字典外编造 |
| update 后字段"被改回" | 不会——除非没等自动刷新就看 | 等几秒（写后自动 invalidate+refresh）；仍异常则调 `lixiang_auto.refresh` |
| 找不到任务开关实体 | v1.7 起已移除 | 不是故障；用 `update_task` 传 `config_id` + `enabled` 启停 |

## 部署文件清单（任务大师功能涉及）

`li_api.py`（接口+build_task_payload）、`coordinator.py`（拉取/缓存/错误上浮）、
`sensor.py`（列表传感器）、`__init__.py` + `services.yaml`
（★ v1.7 起任务开关实体已移除，见下文「为什么不生成任务开关实体」）
（四个服务）。验证：`PYTHONUTF8=1 python -m pytest tests/ -q`（上游仓库，1136+ 通过）。

更完整的请求/响应样例、端点与鉴权说明见 [references/schema.md](references/schema.md)。

## 为什么不生成任务开关实体（v1.7 起）

**曾经的实现**：按 `data["tasks"]` 为每个任务动态注册一个
`switch.理想LX_<任务名>`，切换时 `payload = dict(task)` 后整条 `update_task` 回传。

**为什么要删**：

1. **会冲掉 App 的修改（主要）**
   `payload` 取自 coordinator 的任务快照，而 `TASK_POLL_INTERVAL_SECONDS = 600`（10 分钟）。
   用户在 App 改完任务（改条件/动作/名字）后，若在 HA 点了某个任务开关，
   集成会把**最长 10 分钟前的旧快照**整条推回服务端 → App 上的修改被静默覆盖。
   车主反馈的「集成导致 App 任务大师无法正常使用」就是这个。

2. **本来就没用**
   启停单个任务在 App 里一步就能做；HA 自动化几乎不会去开关一个任务。
   而几十条任务会生成几十个 switch 实体，名字还是中文任务名，把注册表塞满。

**保留了什么**：
- `sensor.任务大师` —— 只读汇总，能看到任务数/启停/条件动作摘要，无害
- 四个服务 —— 用户主动调用
- `update_task` 的实现是「先 `get_tasks` 拉线上最新 → 只覆盖传入字段」，
  不会写回旧快照，因此用它启停任务是安全的：
  ```yaml
  service: lixiang_auto.update_task
  data:
    config_id: "xxx"
    enabled: false
  ```

**回归保护**：`tests/test_task_master.py::test_task_switch_entities_are_not_generated`
断言 `LiTaskSwitch` 类与 `_add_task_switches` 都不存在 —— 有人加回来就会红。
