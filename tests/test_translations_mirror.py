"""左右后视镜状态映射（展开 / 收起）—— 回归测试（2026-10-11）。

★ 事故：映射曾被写反（`{0:"收起", 1:"展开"}`）→ 锁车折叠时 HA 显示"展开"。
  修正依据（两条互相印证的实车/代码证据）：
    ① 实车实测：锁车且后视镜物理**收起**时，裸值 LRearMirro/RRearMirro = **1**
       （同状态下 HA 显示"展开"，暴露颠倒）
    ② App 侧符号名 Left/RightRearviewMirror**Folded**（Folded = 折叠 → 1 = 折叠）

  ⚠️ 旧映射是 2026-09 的**推断**，且当时"实测值"取自模拟器 VIN
     （TESTVIN0000000001）→ 不能作为语义依据。本测试把它钉死为**实车语义**。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"


def _translate(path: str, value):
    """用集成**真实**的翻译函数（与既有测试一致的导入方式：conftest 已加路径）。"""
    from translations import translate  # noqa: PLC0415

    return translate(path, value)


@pytest.mark.parametrize("path", ["Vehicle.Body.RearMirro.LRearMirro",
                                  "Vehicle.Body.RearMirro.RRearMirro"])
class TestMirrorState:
    def test_one_is_folded(self, path):
        """★ 1 = 收起（折叠）—— 锁车折叠时的实测值。"""
        assert _translate(path, 1) == "收起"
        assert _translate(path, "1") == "收起"

    def test_zero_is_unfolded(self, path):
        """0 = 展开。"""
        assert _translate(path, 0) == "展开"
        assert _translate(path, "0") == "展开"

    def test_unknown_value_untouched(self, path):
        """未知值不要乱翻（保留原值便于排查）。"""
        got = _translate(path, 9)
        assert got in (9, "9", None), got
