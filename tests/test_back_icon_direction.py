"""二级页返回箭头必须朝左（<）。

★ 2026-10-28 车主反馈：「二级菜单返回的箭头好像反了」。

实测 `ic_home_return.webp`（官方素材，48×48）的形状是 **">"（尖朝右）** ——
那是「进入/前进」语义，用作返回按钮方向是反的。
（字符画确认：中线像素落在右侧 x=31..34，是 > 而非 <）

修法：生成水平镜像 `ic_home_return_left.webp`（形状 < 尖朝左），
11 个二级页的 16 处引用统一替换。
"""
from __future__ import annotations

import re
from pathlib import Path

CARDS = (Path(__file__).resolve().parent.parent / "custom_components"
         / "lixiang_auto" / "www" / "lixiang-cards")
ICONS = (Path(__file__).resolve().parent.parent / "custom_components"
         / "lixiang_auto" / "www" / "lixiang-icons")


def _pages() -> list[Path]:
    return [p for p in CARDS.glob("lixiang-*.js") if p.name != "lixiang-all.js"]


class TestBackIconDirection:
    def test_left_icon_file_exists(self):
        f = ICONS / "ic_home_return_left.webp"
        assert f.exists(), "缺少镜像后的返回图标 ic_home_return_left.webp"

    def test_left_icon_points_left(self):
        """像素级验证：图标尖端必须在左侧。"""
        from PIL import Image
        import numpy as np
        im = Image.open(ICONS / "ic_home_return_left.webp").convert("RGBA")
        a = np.array(im).astype(int)
        m = a[:, :, 3] > 60
        ys, _ = np.where(m)
        midy = int((ys.min() + ys.max()) / 2)
        # 中线行上，最早（最左）出现像素的位置应是尖端
        xs = np.where(m[midy])[0]
        assert len(xs), "中线无像素"
        # 尖端侧（最左）像素应为 1~2 个（尖），横杆侧更宽 —— 用整体重心判断
        allx = np.where(m.any(axis=0))[0]
        left_half = m[:, : allx.min() + 3].sum()
        right_half = m[:, allx.max() - 2:].sum()
        assert left_half <= right_half, (
            "图标尖端偏右 —— 这不是左箭头（返回应为 <）")

    def test_no_page_uses_right_arrow_icon(self):
        """任何卡片都不许再用原始（右向）图标做返回。"""
        bad = []
        for p in _pages():
            s = p.read_text(encoding="utf-8")
            # 排除 left 版本后，若还引用原版 → 报错
            cleaned = s.replace("ic_home_return_left.webp", "")
            if "ic_home_return.webp" in cleaned:
                bad.append(p.name)
        assert not bad, f"这些页面仍用右向返回图标：{bad}"

    def test_all_subpages_use_left_icon(self):
        """含返回按钮的二级页必须引用 left 图标。"""
        expect = {
            "lixiang-climate-page.js", "lixiang-charge-page.js", "lixiang-energy-page.js",
            "lixiang-health-page.js", "lixiang-location-page.js", "lixiang-task-page.js",
            "lixiang-scene-page.js", "lixiang-seat-page.js", "lixiang-setting-page.js",
            "lixiang-vehicle-info-page.js", "lixiang-ad-page.js",
        }
        for name in expect:
            p = CARDS / name
            assert p.exists(), f"缺页面 {name}"
            s = p.read_text(encoding="utf-8")
            assert "ic_home_return_left.webp" in s, f"{name} 未使用左向返回图标"
