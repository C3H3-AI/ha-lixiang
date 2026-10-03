# 验证流程（改完必跑）

> **背景**：2026-09-24 连续 4 次因"改完不验证"导致 HA 实体大面积不可用。

---

## 问题是什么

之前的流程：

```
改代码 → py_compile 语法检查 → 重启 HA → 看一眼日志 → 报告完成
                                          ↑
                                     ★ 这里不能发现问题
```

**为什么不够**：

| 检查 | 为什么不能证明功能正常 |
|---|---|
| `py_compile` | 只查语法，不查运行时依赖（`from .signals import xxx` 是否存在）|
| HA 返回 200 | 平台 setup 失败时 HA 照样 200 |
| 日志 grep "Error" | 错误在**状态更新时**才出现，重启后要等一轮轮询 |

**实际踩的坑**（同一天 4 次）：

| # | 问题 | 后果 |
|---|---|---|
| ① | `to_sensor_descriptions` 丢失 | 69 个 sensor unavailable |
| ② | `to_binary_descriptions` 丢失 | 35 个 binary_sensor unavailable |
| ③ | `Semantics.JSON_FIELD` 未定义 | 每次状态更新报错 |
| ④ | `Semantics.TRUNK` 未定义 | 同上 |

---

## 现在的流程（强制）

```
改代码
  ↓
./li-verify.sh          ← ★ 7 项检查，任何一项失败就是失败
  ↓
./li-pr.sh submit       ← 自动再跑一次验证（拦截）
  ↓
GitHub CI               ← hassfest + HACS + lint
```

---

## 7 项检查

| # | 检查 | 能发现什么 |
|---|---|---|
| 1 | **Python 语法** | 语法错误 |
| 2 | **单元测试** | 逻辑错误、等价性破坏（★ 以前经常跳过）|
| 3 | **关键函数完整性** | `to_*_descriptions` 等丢失 + 平台 import 能否解析 |
| 4 | **Semantics 引用** | `Semantics.XXX` 引用了未定义的枚举 |
| 5 | **HA 重启** | 启动失败 |
| 6 | **平台 setup 错误** | `Error while setting up lixiang_auto` + 状态更新异常 |
| 7 | **实体数与数据** | 实体数是否 ≥100、关键实体是否有真实数据 |

---

## 用法

```bash
# 改完代码立刻跑
./li-verify.sh

# 只查代码（不重启 HA，快）
./li-verify.sh quick

# 提 PR 时自动跑（li-pr.sh submit 内置）
./li-pr.sh submit
```

### 输出示例（通过）

```
▸ [1/7] Python 语法
  ✓ 全部 .py 文件语法正确
▸ [2/7] 单元测试
  ✓ 99 passed
▸ [3/7] 关键函数完整性
  ✓ signals.py 的 7 个关键函数都在
  ✓ sensor.py 导入的 to_sensor_descriptions 存在
  ✓ binary_sensor.py 导入的 to_binary_descriptions 存在
▸ [4/7] Semantics 枚举引用
  ✓ binary_sensor.py 引用的 Semantics 成员都已定义
▸ [5/7] 重启 HA 并等待就绪
  ✓ HA 就绪
▸ [6/7] 平台 setup / 状态更新错误
  ✓ 无平台 setup 错误
  ✓ 无状态更新异常
  ✓ 无导入错误
▸ [7/7] 实体数与真实数据
  ✓ 实体数 121（≥100）
  ✓   电量=100
  ✓   充电状态=充电完成
  ✓   车内温度=27.0

  ✅ 全部检查通过
```

### 输出示例（失败）

```
▸ [2/7] 单元测试
  ✗ 测试未通过
▸ [3/7] 关键函数完整性
  ✗ signals.py 缺少: to_binary_descriptions
  ✗ binary_sensor.py 导入 to_binary_descriptions 但 signals.py 里没有！

  ❌ 3 项检查失败
  ⚠️ 修复后才能提 PR
```

---

## 教训

**"改完 → 报告完成" 不是流程，"改完 → 验证 → 报告完成" 才是。**

验证标准不能是：
- ❌ 语法通过
- ❌ HA 返回 200
- ❌ 日志没有我 grep 的那几个词

必须是：
- ✅ 测试全过
- ✅ 函数/枚举引用完整
- ✅ 平台 setup 无错误
- ✅ 实体数正确
- ✅ 关键实体有真实数据
