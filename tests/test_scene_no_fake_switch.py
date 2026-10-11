"""情景模式页 —— 去掉误导性开关（2026-10-11）。

问题
----
页面给 4 个场景各渲染了一个 **`role="switch"` 的开关造型**，
但集成里**根本没有情景模式的控制实体**（`switch.py` 无 scene），
且 `_update()` 里四个开关**恒显"关"**：

```js
// 已验证的映射有限：0/1 表示无激活或第一档；其余按位/序号推断不做承诺
this.querySelectorAll("[data-sw]").forEach(sw => { ...全部置 false });
```

结果：页面看起来能点开某个场景，点下去只弹一句"请在 App 里开启"。
这是**用状态冒充开关**（技能 §2），用户会以为集成坏了。

修正
----
1. 去掉 switch 外形与 `role="switch"` → 换成 `.ro-badge`「需在 App / 车机开启」
2. 顶部加说明，讲清"控制通道未打通，这里只做说明与状态展示"
3. 整页场景卡可点 → **统一**给说明（原来每个开关点一下弹同样的话）
4. ★ `_update()` 不再做逐场景状态判断 —— 映射未经证实，**不做假状态**
5. 死代码清理（`data-sw` 绑定与未使用的 `n`）

★ 本文件按本轮新立的【证据等级】制度标注：情景模式数值 → 场景的映射属 **[推断]**，
  App 侧只有 `ModeState` 的 0=未设置/1=已设置，没有场景枚举。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-scene-page.js"


class TestNoFakeSwitch:
    """★ 核心：不允许再出现"看起来能点、实际只弹提示"的假开关。"""

    def test_no_role_switch(self):
        src = PAGE.read_text(encoding="utf-8")
        assert 'role="switch"' not in src, (
            "只读功能不该用 role=\"switch\" —— 技能 §2：不要用状态冒充开关")

    def test_no_data_sw_rendering(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "data-sw=" not in src, "不应再渲染 data-sw 开关元素"
        assert "[data-sw]" not in src, "不应再绑定 data-sw"

    def test_readonly_badge_present(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "ro-badge" in src, "需要只读徽标替代开关"
        assert "需在 App / 车机开启" in src, "徽标要说明去哪开"

    def test_notice_explains_limitation(self):
        src = PAGE.read_text(encoding="utf-8")
        assert '<div class="notice">' in src, "顶部要有说明"
        i = src.index('<div class="notice">')
        blk = src[i:i + 300]
        assert "LiNdn" in blk or "JOB" in blk, "要说明控制通道未打通（诚实标注）"


class TestNoFakeState:
    """★ 映射未证实 → 不做逐场景状态判断（此前恒显"关"= 假状态）。"""

    def test_update_does_not_force_all_off(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("  _update() {")
        blk = src[i:i + 900]
        assert 'setAttribute("aria-checked", "false")' not in blk, (
            "_update 不应再把所有开关强制置 false（那是假状态）")
        assert "querySelectorAll(\"[data-sw]\")" not in blk

    def test_raw_value_still_exposed(self):
        """原始值仍挂到 data-scene（调试用）—— 不能为了去掉假状态而丢掉真实数据。"""
        src = PAGE.read_text(encoding="utf-8")
        assert 'setAttribute("data-scene"' in src, "应保留原始值输出供排查"

    def test_evidence_level_noted(self):
        """★ 按证据等级制度：映射未证实必须写明（[推断]）。"""
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("  _update() {")
        blk = src[i:i + 900]
        assert ("推断" in blk or "未经证实" in blk), "必须标注映射属推断/未证实"
        assert "证据等级" in blk, "要写明这是【证据等级】标注（与 translations.py 制度一致）"


class TestInteraction:
    def test_page_level_note(self):
        src = PAGE.read_text(encoding="utf-8")
        assert "sceneNote" in src, "整页应有统一的说明入口"
        assert 'querySelectorAll("[data-k]")' in src, "场景卡按 data-k 绑定"
        assert "该场景" in src, "要能取到场景名做提示"

    def test_scene_note_actually_bound(self):
        """★ sceneNote 必须真的被绑定到卡片上（不能只定义不用 → 点了没反应）。"""
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("sceneNote = ")
        blk = src[i:i + 500]
        assert "addEventListener(\"click\", sceneNote)" in blk, \
            "sceneNote 只定义未绑定 → 场景卡点了没反应"

    def test_no_leftover_unused_var(self):
        src = PAGE.read_text(encoding="utf-8")
        i = src.index("  _update() {")
        blk = src[i:i + 700]
        assert not re.search(r"const n = .*\n\s*//", blk), "_update 里不该留下未使用的 n"


class TestPreserved:
    def test_scenes_intact(self):
        src = PAGE.read_text(encoding="utf-8")
        for key in ('key: "pet"', 'key: "camp"', 'key: "wash"', 'key: "keep"'):
            assert key in src, f"场景 {key} 丢了（本次只改交互形态，不删场景）"

    def test_shell_kept(self):
        src = PAGE.read_text(encoding="utf-8")
        for token in ('id="back"', 'class="toast"', "_toast("):
            assert token in src, f"外壳元素 {token} 丢了"

    def test_sub_button_kept(self):
        """舱内影像入口保留（它另有说明）。"""
        src = PAGE.read_text(encoding="utf-8")
        assert 'data-sub' in src


class TestNoDeadCode:
    def test_sw_class_still_used_or_removed(self):
        """`.sw` 样式若已无对应元素，应连样式一起删（避免死 CSS）。"""
        src = PAGE.read_text(encoding="utf-8")
        has_style = bool(re.search(r'\n\s*\.sw\s*\{', src))
        has_elem = 'class="sw' in src
        assert not (has_style and not has_elem), (
            "`.sw` 样式还在但已无对应元素 → 死 CSS，应删除")