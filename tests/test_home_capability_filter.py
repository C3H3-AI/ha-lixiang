"""首页车型适配 —— 数据驱动过滤（2026-10-11）。

背景
----
首页的快捷功能区（`QUICK`）原先是**硬编码 8 项、无条件全部渲染** →
不支持该功能的车也会出现入口，点了只提示「该功能尚未接入」。
用户会以为集成坏了，而实际上只是这台车没这个功能。

改造
----
渲染前先问 `_supports(def)`：**该功能对应的实体在这台车上是否存在**。
★ 判据是**实体存在性**（服务端已按车型能力门控），前端**不猜车型**、
  不维护"车型 → 功能"映射表 —— 这与卡片侧 `lixiang-assets.js` 的思路一致。

JS 行为用 node 真跑（子串断言挡不住"过滤条件写反"这类退化）。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
HOME = CARDS / "lixiang-app-home.js"


def _node_ok() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=20, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _node_ok(), reason="node 不可用")


def run_node(code: str) -> str:
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[:600]
    return r.stdout


# ══════════════════════════════════════════════════════════════════════
# ★ 关键：直接从**真实源文件**里抽出 _supports / _eidIn 执行，
#   而不是测试里抄一份逻辑。
#   教训（本轮实测踩到）：先写测试时用了 PRELUDE 里的**副本**，
#   结果"删掉页面里的 _supports 方法""忽略 unsupported 标志"两种变异
#   **照样全绿** —— 测试测的是副本，不是产品代码（技能 §19）。
# ══════════════════════════════════════════════════════════════════════
def _extract_method(src: str, name: str) -> str:
    """按大括号配平抽出方法**定义**（不做正则猜测，缩进/嵌套都安全）。

    ★ 必须匹配"定义处"（行首缩进 + 形参），不能匹配**调用点**
      （页面里 `this._supports(it, warmup)` 也含 "_supports("），
      否则会从调用处一路抽到文件尾 —— 本轮实际踩到过。
    """
    i = src.index(f"\n  {name}(")      # 方法定义在类里，行首两个空格缩进
    j = src.index("{", i)
    # 上方若是 JSDoc（/** ... */），把整段注释一并纳入再剥掉，
    # 否则会遗留 "*/" 让片段无法作为 JS 解析（本轮踩到）。
    start = i          # 从方法签名开始（上方 JSDoc 不取）
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[start:k + 1]  # 只取方法体，不含上方 JSDoc（JS 里本就合法）
        k += 1
    raise AssertionError(f"{name} 的大括号不配平")


def _harness() -> str:
    """拼一个最小宿主：注入 _supports 依赖（_eidIn / _st / _config / _hass）。"""
    src = HOME.read_text(encoding="utf-8")
    eid_in = _extract_method(src, "_eidIn")
    supports = _extract_method(src, "_supports")
    # 方法体里的 `this` 要绑到宿主对象上 → 拼成对象字面量（方法用逗号分隔）
    def lit(code: str) -> str:
        # 去掉方法体首尾花括号，转成 "name(args) {...}," 的字面量成员
        body = code.strip()
        body = body[body.index("{") + 1: body.rindex("}")]
        sig = body.split("{", 1)[0] if False else None
        head_txt = code.strip().split("{", 1)[0]
        return head_txt + "{" + body + "},"
    # 宿主字段
    stub = "_st(id) { return (id && this._hass) ? this._hass.states[id] : null; },"
    return (
        "const G = {\n"
        "  _config: CFG,\n"
        "  _hass: { states: STATES },\n"
        "  _autoBind: () => AUTO,\n"
        f"  {stub}\n"
        f"  {lit(eid_in)}\n"
        f"  {lit(supports)}\n"
        "};\n"
        "process.stdout.write(JSON.stringify(\n"
        "  DEFS.map(d => [d.key, G._supports(d, WARMUP)])));\n"
    )


class TestCapabilityFilter:
    def _run(self, defs, cfg, states, autoBind=None, warmup=False):
        # ⚠️ 常量必须【先于】harness 声明（harness 里对象字面量会立即求值）
        consts = (
            f"const DEFS = {json.dumps(defs, ensure_ascii=False)};\n"
            f"const CFG = {json.dumps(cfg, ensure_ascii=False)};\n"
            f"const STATES = {json.dumps(states, ensure_ascii=False)};\n"
            f"const AUTO = {json.dumps(autoBind or {}, ensure_ascii=False)};\n"
            f"const WARMUP = {str(warmup).lower()};\n"
        )
        js = consts + _harness()
        return dict(json.loads(run_node(js)))

    def test_only_existing_entities_render(self):
        """★ 核心：实体不存在 → 不渲染（这台车没这个功能）。"""
        got = self._run(
            defs=[{"key": "lock"}, {"key": "window"}, {"key": "trunk"}],
            cfg={"quick": {"lock": "switch.x_lock", "window": "cover.x_win",
                           "trunk": "cover.x_trunk"}},
            states={"switch.x_lock": {"state": "locked"},
                    "cover.x_win": {"state": "open"}},          # trunk 缺失
        )
        assert got == {"lock": True, "window": True, "trunk": False}

    def test_unsupported_never_renders(self):
        """标注 unsupported 的（如走 JOB 通道的直线召唤）→ 永不出现。"""
        got = self._run(
            defs=[{"key": "summon", "unsupported": True}],
            cfg={"quick": {"summon": "button.x_summon"}},
            states={"button.x_summon": {"state": "unknown"}},   # 实体其实在
        )
        assert got["summon"] is False, "标注 unsupported 的功能不该渲染"

    def test_auto_bind_fallback(self):
        """没在 config 写实体时，回退到 autoBind 提供的映射。"""
        got = self._run(
            defs=[{"key": "lock"}], cfg={}, states={},
            autoBind={"lock": "lock.auto_bound"},
        )
        assert got["lock"] is False        # 实体不存在 → 不渲染
        got2 = self._run(
            defs=[{"key": "lock"}], cfg={},
            states={"lock.auto_bound": {"state": "locked"}},
            autoBind={"lock": "lock.auto_bound"},
        )
        assert got2["lock"] is True

    def test_warmup_avoids_flicker(self):
        """★ 首帧实体表未就绪时：只要 config 声明过就先渲染，避免闪烁。"""
        got = self._run(
            defs=[{"key": "lock"}, {"key": "trunk"}],
            cfg={"quick": {"lock": "switch.x_lock", "trunk": "cover.x_trunk"}},
            states={}, warmup=True,
        )
        assert got["lock"] is True, "首帧不应隐藏已配置的功能"
        got_cold = self._run(
            defs=[{"key": "lock"}],
            cfg={"quick": {"lock": "switch.x_lock"}}, states={}, warmup=False,
        )
        assert got_cold["lock"] is False, "非首帧时实体不存在就该隐藏"

    def test_m_series_scenario(self):
        """理想ONE 场景：车锁/车窗在，但尾门/充电盖这类未必有 → 只显示有的。"""
        got = self._run(
            defs=[{"key": "lock"}, {"key": "window"}, {"key": "port"}],
            cfg={"quick": {"lock": "lock.m01", "window": "cover.m01",
                           "port": "switch.m01_port"}},
            states={"lock.m01": {"state": "locked"}},
        )
        assert got["lock"] is True and got["window"] is False and got["port"] is False


class TestHomePageWiring:
    """源码层面：确认过滤真的接在渲染路径上（不只是有个孤立方法）。"""

    def test_quick_filtered_at_render(self):
        src = HOME.read_text(encoding="utf-8")
        i = src.index('const q = this.querySelector("#quick")')
        blk = src[i:i + 500]
        assert "QUICK.filter" in blk, "渲染前必须过滤 QUICK"
        assert "avail.forEach" in blk, "必须遍历过滤后的集合"

    def test_empty_state_present(self):
        src = HOME.read_text(encoding="utf-8")
        assert "qempty" in src, "无可用功能时应有空态提示"

    def test_summon_marked_unsupported(self):
        src = HOME.read_text(encoding="utf-8")
        m = re.search(r'\{ key:"summon".*?\}', src, re.S)
        assert m and "unsupported:true" in m.group(0), (
            "直线召唤走 JOB 通道，应标 unsupported 以免给用户必然失败的入口")

    def test_readback_loop_safe(self):
        """回读循环必须跳过未渲染项。"""
        src = HOME.read_text(encoding="utf-8")
        i = src.rindex("QUICK.forEach")
        blk = src[i:i + 260]
        assert 'if (!el) return' in blk, "回读时未渲染的项要 return（否则会操作不存在的 DOM）"

    def test_no_model_to_feature_mapping(self):
        """★ 不允许"按具体车型枚举功能"——那正是这次要去掉的东西。

        ★ 注意区分：前端**允许**有【车系识别】与【车系外观/资源差异表】
          （如 L/W/M 系剪影、MEGA 的三排/冰箱 —— 用于选图，不用于决定功能显隐）。
        判据：这些表只能影响**资源**，不能影响**实体是否存在**。
        """
        src = HOME.read_text(encoding="utf-8")
        # 具体车型代码（如 M01B / L6Max25 / W01_25）不应出现在首页
        for model in ("M01B", "L6Max25", "L9Pro24", "W01_25", "W05车型"):
            assert model not in src, f"首页出现具体车型代码 {model} —— 功能显隐应由实体存在性表达"
        # 车系能力表若存在，必须只被用于资源/文案，不得用于实体显隐
        if "侧滑门: true" in src or "冰箱: true" in src:
            blk = src[max(0, src.find("冰箱: true") - 400): src.find("冰箱: true") + 400]
            assert "_supports" not in blk, "车系能力表不得参与功能显隐判定"

class TestGuardSelfCheck:
    """★ 守卫自身要能失败（技能 §19）。

    若这些变异抓不住，说明测试在测副本或根本没测产品代码。
    """

    def test_harness_uses_real_source(self):
        """测试必须执行**页面里的真方法**（抽取失败要报错，而不是静默用副本）。"""
        src = HOME.read_text(encoding="utf-8")
        h = _harness()
        assert "_supports" in h and "_eidIn" in h, "harness 没抽到真实方法"
        assert "makeSupports" not in h, "harness 里不应再有副本实现"

    def test_extractor_rejects_broken_source(self):
        """大括号不配平时必须抛错（不能悄悄返回错的东西）。"""
        # 不配平 → 必须抛错，不能悄悄返回半截代码
        with pytest.raises((AssertionError, ValueError)):
            _extract_method("\n  foo() { if (x) { ", "foo")
        # 方法名不存在 → 抛错
        with pytest.raises(ValueError):
            _extract_method("  bar() {}", "_nope")
        # ★ 只有【调用点】没有定义 → 必须抛错（本轮踩过：会一路抽到文件尾）
        with pytest.raises(ValueError):
            _extract_method("  this._supports(def, warmup);", "_supports")

    def test_missing_method_raises(self):
        with pytest.raises(ValueError):
            _extract_method(HOME.read_text(encoding="utf-8"), "_not_there")
