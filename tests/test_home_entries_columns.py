"""车控首页入口区（.entries）必须始终两列。

★ 2026-10-28 车主反馈：「下面默认都显示两节…有些人反馈只显示 1 列」。

根因：`@container (max-width: 340px)` 里把 .entries 收成单列。
实测两种场景都会命中（都会让用户看到 1 列）：
  ① 视口 ≤340px（iPhone SE 1 代 320px 等）
  ② **卡片被放进 ≤340px 的容器**（HA 桌面端分栏 / 平板多列 / 窄侧边栏）
     ← 桌面和平板上极易触发，是"有些人"的主因

官方 App 在任何手机宽度下入口都是并排两列 → .entries 一律两列。
（2026-10-14 曾修过同类问题「为什么下面是一列了」，但当时只把阈值
  从 480 调到 340，仍然太容易命中 —— 这次彻底移除单列规则。）
"""
from __future__ import annotations

import re
from pathlib import Path

HOME = (Path(__file__).resolve().parent.parent / "custom_components"
        / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-app-home.js")


def _src() -> str:
    return HOME.read_text(encoding="utf-8")


class TestEntriesAlwaysTwoColumns:
    def test_entries_declares_two_columns(self):
        src = _src()
        m = re.search(r"\.entries\s*\{[^}]*grid-template-columns:\s*repeat\(2", src)
        assert m, ".entries 必须声明 repeat(2, …) 两列"

    def test_entries_never_collapsed_to_single_column(self):
        """任何断点里都不许把 .entries 收成单列。"""
        src = _src()
        bad = re.findall(r"\.entries\s*\{[^}]*grid-template-columns:\s*(?:minmax\(0,\s*1fr\)|1fr)\b[^}]*\}", src)
        assert not bad, (
            "发现把 .entries 收成单列的规则（会让部分用户只看到 1 列）：\n  "
            + "\n  ".join(bad))

    def test_no_breakpoint_above_300_collapses_entries(self):
        """340px 这类"中等窄"断点不得再收 single column（会误伤 320/360 设备与窄容器）。"""
        src = _src()
        # 逐个 @container 块检查：若阈值 >300 且块内含 .entries 单列 → 失败
        for m in re.finditer(r"@container\s*\(\s*max-width:\s*(\d+)px\s*\)\s*\{", src):
            width = int(m.group(1))
            if width <= 300:
                continue
            # 取到下一个 @container 之前的内容作为该块
            rest = src[m.end():]
            nxt = rest.find("@container")
            block = rest[: nxt if nxt >= 0 else len(rest)]
            assert not re.search(
                r"\.entries\s*\{[^}]*grid-template-columns:\s*(?:minmax\(0,\s*1fr\)|1fr)",
                block,
            ), f"max-width:{width}px 断点里把 .entries 收成了单列"

    def test_row2_still_collapses_when_very_narrow(self):
        """极窄时 .row2（空调/位置大卡）仍应叠起来，避免两张大卡挤爆。"""
        src = _src()
        i = src.index("@container (max-width: 300px)")
        block = src[i: i + 400]
        assert ".row2" in block, "极窄断点应保留 .row2 单列（大卡会挤）"
