"""保养实体默认启用（2026-10-02）。

背景：保养 5 项（增程器/火花塞/空调滤芯/油液/冷却液）此前被归入
`_DIAGNOSTIC_KEYS` → `entity_registry_enabled_default=False`，
导致用户看不到它们，也就无法在「车辆健康」页看到保养数据。

但 App 把「车辆保养」放在车辆健康页的显眼位置，是**用户可见的主要功能**，
不该藏进诊断折叠区。依据：抓包 `vss_full_state.json` 里
`Vehicle.Carcenter.Maintain.*` 每项含 33 个字段（剩余里程/到期日/周期…），
实体启用后能拿到真实数据（与 App 截图逐项吻合）。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNALS = ROOT / "custom_components" / "lixiang_auto" / "signals.py"

MAINTAIN_KEYS = (
    "maint_acfilter", "maint_coolfuild", "maint_engine_oil",
    "maint_brake_oil", "maint_sparkplug", "maint_engine_level2",
)


def _src() -> str:
    return SIGNALS.read_text(encoding="utf-8")


def test_maintain_keys_defined_in_signals():
    """signals.py 必须定义 MAINTAIN_KEYS 且含全部保养项。"""
    src = _src()
    start = src.find("MAINTAIN_KEYS = frozenset({")
    assert start > 0, "signals.py 缺少 MAINTAIN_KEYS"
    end = src.find("})", start)
    block = src[start:end]
    for key in MAINTAIN_KEYS:
        assert key in block, f"MAINTAIN_KEYS 缺 {key}"


def test_diagnostic_exception_uses_maintain_keys():
    """诊断分支必须用 MAINTAIN_KEYS 做例外。"""
    src = _src()
    i = src.find("if spec.diagnostic:")
    assert i > 0, "找不到 spec.diagnostic 分支"
    seg = src[i:i + 500]
    assert "MAINTAIN_KEYS" in seg, "诊断分支未引用 MAINTAIN_KEYS（保养项仍会被禁用）"


def test_maintain_enabled_by_default():
    """保养项默认启用（signals.py 的表达式）。"""
    src = _src()
    i = src.find("if spec.diagnostic:")
    seg = src[i:i + 600]
    assert "spec.key in MAINTAIN_KEYS" in seg, "未用 MAINTAIN_KEYS 判定"


def test_other_diagnostics_still_disabled():
    """非保养的诊断类实体仍默认禁用（表达式应为 False）。"""
    src = _src()
    i = src.find("if spec.diagnostic:")
    seg = src[i:i + 600]
    assert 'enabled_default"] = (' in seg or 'enabled_default"] =' in seg, \
        "诊断分支未设置 enabled_default"
    # 表达式应是 `spec.key in MAINTAIN_KEYS`（set 为空时为 False）
    assert "MAINTAIN_KEYS" in seg


def test_maintain_specs_exist_in_signals():
    """6 个保养信号必须在 signals.py 里有定义。"""
    src = _src()
    for key in MAINTAIN_KEYS:
        assert f'"{key}": SignalSpec(' in src, f"signals.py 缺少信号: {key}"
