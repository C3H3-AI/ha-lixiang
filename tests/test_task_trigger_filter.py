"""任务大师页 —— 触发条件按实体过滤（2026-10-11）。

问题
----
`_pickAction()`（动作）已经用 `.filter(o => o.a)` 过滤掉了实体缺失的选项，
但 ★ **`_pickTrigger()`（触发条件）没有** —— 5 个条件无条件全出现：

```js
{ label: "车辆上锁", t: { platform:"state", entity_id: this._eid("lock"), to:"locked" } },
```

若这台车没有 `lock` 实体（或用户没配），用户仍能选中"车辆上锁"，
提交后服务端找不到该 `entity_id` → **任务创建失败**，且报错难以理解。

修正
----
与动作列表一致地过滤，并给出**明确提示**（而不是让用户选了个必失败的选项）。

★ 这也符合技能 §2 的精神：**不给用户"看起来能选、实际必失败"的选项**。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-task-page.js"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:700]
    return r.stdout


def harness(cfg: dict, states: dict) -> str:
    """最小宿主：只提供 _eid / _st / _toast / _choose（记录调用）。"""
    src = PAGE.read_text(encoding="utf-8")
    i = src.index("  async _pickTrigger() {")
    j = src.index("\n  async ", i + 10)
    body = src[i:j]
    return (
        f"const CFG = {json.dumps(cfg, ensure_ascii=False)};\n"
        f"const STATES = {json.dumps(states, ensure_ascii=False)};\n"
        "const PICKED = [];\n"
        "const TOASTS = [];\n"
        "const G = {\n"
        "  _config: CFG, _hass: { states: STATES },\n"
        "  _eid(f) { const m = this._config[f];\n"
        "    if (typeof m === 'string' && m.includes('.')) return m;\n"
        "    return null; },\n"
        "  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; },\n"
        "  _toast(msg, kind) { TOASTS.push([msg, kind || '']); },\n"
        "  async _ensureDict() { return false; },   // 桩：默认走旧简表路径\n"
        "  async _choose(title, labels) { PICKED.push(labels); return 0; },\n"
        "  _draft: { trigger: null },\n"
        "  _render() {},\n"
        + body + "\n"
        "};\n"
        "G._pickTrigger().then(() => {\n"
        "  process.stdout.write(JSON.stringify({ picked: PICKED, toasts: TOASTS,\n"
        "    trigger: G._draft.trigger }));\n"
        "});\n"
    )


def picked_labels(cfg, states) -> list[str]:
    """返回展示给用户的触发条件标签列表（未选就 return）。"""
    got = json.loads(run_node(harness(cfg, states)))
    return got["picked"][0] if got["picked"] else []


def toasts(cfg, states):
    return json.loads(run_node(harness(cfg, states)))["toasts"]


FULL = {"status": "sensor.x_status", "lock": "lock.x_lock",
        "battery": "sensor.x_batt", "room_temp": "sensor.x_temp"}


class TestTriggerFiltering:
    def test_all_available_when_entities_exist(self):
        states = {v: {"state": "0"} for v in FULL.values()}
        labels = picked_labels(FULL, states)
        assert len(labels) == 5, f"实体齐全时应显示 5 个条件，实际 {labels}"

    def test_missing_entity_hides_option(self):
        """★ 核心：实体缺失的条件不出现（否则用户选了必失败）。"""
        cfg = dict(FULL); cfg.pop("lock")
        states = {v: {"state": "0"} for v in cfg.values()}
        labels = picked_labels(cfg, states)
        assert "车辆上锁" not in labels, "没有 lock 实体就不该给『车辆上锁』"
        assert "电量低于 20%" in labels, "其他条件应保留"

    def test_config_not_set(self):
        """config 里没写字段 → 同样不该出现。"""
        labels = picked_labels({}, {})
        assert labels == [] or "车辆上锁" not in labels

    def test_entity_configured_but_state_missing(self):
        """★ 配了实体 id 但 hass 里还没有该状态 → 也过滤掉。"""
        labels = picked_labels(FULL, {})      # states 空
        assert labels == [], f"状态都不存在时不该给任何条件，实际 {labels}"

    def test_all_missing_gives_clear_message(self):
        """★ 全都没有 → 明确提示，而不是弹一个空选择框。"""
        got = json.loads(run_node(harness({}, {})))
        assert got["picked"] == [], "无可用条件时不该打开选择框"
        assert got["toasts"], "应给出提示"
        assert "触发条件" in got["toasts"][0][0], "提示要说清是触发条件的问题"
        assert got["toasts"][0][1] == "err", "应为错误态（红）"


class TestActionUnaffected:
    """★ 动作列表原本就有过滤，不能被这次改动破坏。"""

    def test_action_still_filters(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("async _pickAction()")
        blk = src[i:i + 1200]
        assert ".filter(o => o.a)" in blk, "动作列表仍需过滤（回归保护）"

    def test_trigger_and_action_consistent(self):
        """两处过滤口径应一致（都用实体存在性）。"""
        src = PAGE.read_text(encoding="utf-8")
        assert "this._st(o.t.entity_id)" in src, "触发条件过滤应基于 _st（状态存在）"


class TestWiring:
    def test_picktrigger_has_filter(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("async _pickTrigger()")
        j = src.index("\n  async ", i + 10)
        blk = src[i:j]
        assert ".filter(" in blk, "_pickTrigger 必须过滤（本次修复点）"

    def test_draft_still_assigned(self):
        """过滤后仍要能把选中的条件写进 draft。"""
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("async _pickTrigger()")
        j = src.index("\n  async ", i + 10)
        assert "this._draft.trigger = OPTS[pick].t" in src[i:j]

    def test_no_conditional_early_return_broken(self):
        """★ 空列表兜底必须在打开选择框【之前】。

        ★ 这条最初**没咬住**对应变异：把 `if (!OPTS.length) return` 挪到
        `await this._choose(...)` 之后，字符串下标顺序仍然满足
        （因为该行被插到 choose 行**前一行**，位置没真正变）。
        → 改为**执行验证**：空列表时不应调用 _choose（harness 会记录）。
        """
        got = json.loads(run_node(harness({}, {})))
        assert got["picked"] == [], "空列表时不该调用 _choose（否则弹出空选择框）"

        src = PAGE.read_text(encoding="utf-8")
        i = src.index("async _pickTrigger()")
        j = src.index("\n  async ", i + 10)
        blk = src[i:j]
        assert blk.index("if (!OPTS.length)") < blk.index("await this._choose"), \
            "源码层面也应在 _choose 之前"

    def test_st_helper_defined(self):
        """★ 本页此前【没有】_st()，新代码调用它会在浏览器里抛 TypeError。

        （由既有的 test_frontend_bindings 抓到过一次 —— 这条是本页自保。）
        """
        src = PAGE.read_text(encoding="utf-8")
        assert re.search(r'\n  _st\(id\)', src), "本页必须定义 _st()（过滤逻辑要用）"
        assert "  _st(id) { return (id && this._hass) ? this._hass.states[id] : null; }" in src


class TestGuardSelfCheck:
    def test_harness_uses_real_source(self):
        assert "_pickTrigger" in harness(FULL, {})

    def test_extract_needs_method(self):
        with pytest.raises(ValueError):
            PAGE.read_text(encoding="utf-8").index("  async _notThere() {")