"""任务大师条件 / 动作字典（服务端下发 + 本地持久化）。

为什么需要这个模块
------------------
App 的「添加条件 / 添加操作」界面是**服务端驱动**的：分类、条目、参数模板
（类型 / 可选值 / 默认值）都来自

    GET /ssp-task-master-service/v1/task-basic/mob/condition-and-action/{VIN}

★ 证据（2026-10-11 实证）：
  · 该接口路径在 APK 里**搜不到任何字符串**（连我们正在成功调用的
    `task-config/mob/my-task-by-vin` 也搜不到）→ 路径本身也是服务端配置下发的，
    不是客户端硬编码。所以**逆向拿不到，只能运行时调**。
  · 返回结构是**两层**：`classification`（分类）→ `functions[]`（条目）
    → 每个条目带 `params[]`（key / type / label / 可选值 / defaultValue）。
    实测一份：15 分类 / 80 条件、16 分类 / 126 动作（会随服务端版本变）。

★ 早期文档里记的「15 条件 / 17 动作」是**误读** —— 那两个数字其实是
  **分类数**，不是条目数。代码注释已按本次实测更正。

持久化策略
----------
字典是**低频变化**的配置，没必要每次开页面都拉：

1. 启动 / 首次使用时拉取 → 落盘到 `<config>/lixiang_task_dict.json`
2. 之后从本地读（UI 立即可用，不阻塞）
3. 每次启动**后台尝试刷新一次**；成功则更新落盘，失败则继续用旧版
4. 拉取失败时诊断属性显示原因（不猜、不编造）

这样即使服务端临时不可用或账号权限不足，UI 仍能用上次成功的字典。

dataSource 的含义（实测）
------------------------
`mob` = 需客户端提供（如 Delay / NaviDest / Reminder）
`clo` = 车端（绝大多数）
`veh` = 车辆配置项（如 Glasses 的 mac、VoiceCommand）—— 这类我们通常**无权创建**，
        UI 应标注，避免用户选了必然失败。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: 落盘文件名（放在 HA 配置目录下，与 ability 缓存同级）
DICT_FILENAME = "lixiang_task_dict.json"

#: 字典的"新鲜度"上限：超过这个天数就在启动时主动刷新
MAX_AGE_DAYS = 7


def dict_path(config_dir: str) -> str:
    """字典落盘路径。"""
    return os.path.join(config_dir, DICT_FILENAME)


# --------------------------------------------------------------------------
# 解析 / 规范化
# --------------------------------------------------------------------------
def normalize(raw: Any) -> dict[str, Any]:
    """把服务端返回整理成便于 UI 使用的结构。

    服务端原始结构::

        {"code":0,"data":{"conditions":[{"classification":"ConditionTimes",
          "functions":[{"conditionType":"Time","dataSource":"mob","params":null}]}]}}

    整理后::

        {"conditions":[{"classification":"ConditionTimes","items":[
           {"type":"Time","source":"mob","label":null,"params":[]}]}], ...}
    """
    data = raw if isinstance(raw, dict) else {}
    # ★ 兼容两种形态：完整响应（{"code":0,"data":{...}}）与已解包（{"conditions":[...]}）
    inner = data.get("data")
    if isinstance(inner, dict) and (
        isinstance(inner.get("conditions"), list) or isinstance(inner.get("actions"), list)
    ):
        data = inner
    elif not isinstance(data.get("conditions"), list):
        return {"conditions": [], "actions": []}
    out: dict[str, Any] = {"conditions": [], "actions": []}
    for src_key, dst_key, type_key in (
        ("conditions", "conditions", "conditionType"),
        ("actions", "actions", "actionType"),
    ):
        for group in data.get(src_key) or []:
            if not isinstance(group, dict):
                continue
            items = []
            for fn in group.get("functions") or []:
                if not isinstance(fn, dict):
                    continue
                t = fn.get(type_key)
                if not t:
                    continue
                items.append({
                    "type": t,
                    "source": fn.get("dataSource") or "clo",
                    "label": fn.get("label") or fn.get("name") or "",
                    # params 可能是 null（无需参数）
                    "params": [p for p in (fn.get("params") or []) if isinstance(p, dict)],
                })
            if items:
                out[dst_key].append({
                    "classification": group.get("classification") or "",
                    "items": items,
                })
    return out


def count_items(dict_: dict[str, Any]) -> tuple[int, int]:
    """(条件条目数, 动作条目数) —— 用于日志与诊断。"""
    c = sum(len(g.get("items") or []) for g in dict_.get("conditions") or [])
    a = sum(len(g.get("items") or []) for g in dict_.get("actions") or [])
    return c, a


def requires_vehicle_data(dict_: dict[str, Any]) -> dict[str, list[str]]:
    """按 `dataSource=veh` 挑出条目 —— 这些通常需要车辆配置，我们无权创建。"""
    out: dict[str, list[str]] = {}
    for key in ("conditions", "actions"):
        names = [
            it["type"]
            for g in dict_.get(key) or []
            for it in (g.get("items") or [])
            if it.get("source") == "veh"
        ]
        if names:
            out[key] = sorted(set(names))
    return out


# --------------------------------------------------------------------------
# 持久化
# --------------------------------------------------------------------------
def load(config_dir: str) -> dict[str, Any] | None:
    """读本地字典；不存在 / 损坏返回 None。"""
    path = dict_path(config_dir)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.warning("任务字典文件损坏（将重新拉取）: %s", err)
        return None
    if not isinstance(data, dict) or "conditions" not in data:
        return None
    return data


def save(config_dir: str, data: dict[str, Any]) -> bool:
    """原子写 + 仅属主可读（与 identity.py 一致）。"""
    path = dict_path(config_dir)
    payload = dict(data)
    payload["saved_at"] = int(time.time())
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except OSError as err:
        _LOGGER.warning("保存任务字典失败: %s", err)
        return False


def is_stale(data: dict[str, Any], max_days: int = MAX_AGE_DAYS) -> bool:
    """是否该刷新（无时间戳按陈旧处理 → 宁可多拉一次）。"""
    ts = data.get("saved_at")
    if not isinstance(ts, (int, float)):
        return True
    return (time.time() - ts) > max_days * 86400


def describe(data: dict[str, Any] | None) -> str:
    """给诊断属性用的一行摘要。"""
    if not data:
        return "未获取"
    c, a = count_items(data)
    groups_c = len(data.get("conditions") or [])
    groups_a = len(data.get("actions") or [])
    ts = data.get("saved_at")
    when = ""
    if isinstance(ts, (int, float)):
        when = time.strftime("%Y-%m-%d", time.localtime(ts))
    return f"{groups_c} 分类/{c} 条件 · {groups_a} 分类/{a} 动作 · 拉取于 {when or '未知'}"