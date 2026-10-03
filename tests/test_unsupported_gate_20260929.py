"""数据驱动的「车型不支持」门控（2026-09-29）。

背景
----
App 的 VSS 路径清单**按车型下发**，某些字段只有部分车型上报。

实测案例：`Vehicle.Cabin.CLTC.EnduranceMil`（总续航）
  · 静态证据三源一致：spec_X01-VSS-Path_148.json 有它、
    LXLiMeshPathConfig 把它列进 LXVehicleInfoKeyEndurance.subKeys、
    App 车控头部订阅该组
  · 但我们的 L6 **连续 112 次轮询都拿不到它**，
    而同批次的纯电/燃油续航（172/147/139/115）都有值

★ 关键：服务端对这种路径**不报 400**，只是静默不返回 ——
  所以无法用「路径无效」门控，必须改成**数据驱动**：
  连续 N 轮「本批整体有数据、但该 key 始终缺席」→ 判定该车型不支持。

为什么不做「按车型名硬编码门控」
--------------------------------
我们没有「哪些车型有该字段」的证据，硬编码就是猜 ——
而数据驱动的门控**不需要先验知识**：
i6 车主那边有数据，实体就自然出现；L6 没有，就显示不可用。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ★ 项目惯例：测试 coordinator 时读源码文本，不 import（避免依赖 homeassistant）
_COORD = (Path(__file__).resolve().parent.parent
          / "custom_components/lixiang_auto/coordinator.py")
_SENSOR = (Path(__file__).resolve().parent.parent
           / "custom_components/lixiang_auto/sensor.py")


def _coord_src() -> str:
    return _COORD.read_text(encoding="utf-8")


def _sensor_src() -> str:
    return _SENSOR.read_text(encoding="utf-8")


class TestConstantExists:
    def test_threshold_defined(self):
        src = _coord_src()
        m = re.search(r"ABSENT_POLLS_TO_UNSUPPORTED\s*=\s*(\d+)", src)
        assert m, "缺少门控阈值常量"
        n = int(m.group(1))
        # 30 轮 × 5 分钟 ≈ 2.5 小时：够避开偶发丢包，又不至于让用户等太久
        assert 5 <= n <= 200, f"阈值 {n} 不合理"

    def test_threshold_documented(self):
        assert "数据驱动" in _coord_src(), "门控设计要写清为什么这么做"


class TestCoordinatorTracksAbsence:
    """协调器必须统计缺席次数，并且【只在整批健康时】计数。"""

    def setup_method(self):
        self.src = _coord_src()

    def test_has_absent_counter(self):
        assert "_absent_count" in self.src, "缺少缺席计数"

    def test_has_unsupported_set(self):
        assert "_unsupported" in self.src, "缺少不支持集合"

    def test_publishes_to_data(self):
        assert "unsupported_keys" in self.src, (
            "必须把判定结果放进 data，否则实体取不到"
        )

    def test_only_counts_when_batch_healthy(self):
        """★ 核心防误判：车睡着了整批为空，不能把实体全判成不支持。"""
        assert re.search(r"if\s+_got\s*>=\s*\d+", self.src), (
            "必须有「本批至少拿到 N 条才计数」的保护，否则车辆休眠时"
            "会把所有实体误判为不支持"
        )

    def test_skips_virtual_signals(self):
        """虚拟信号（path 为空，如 online_status）不该被计入缺席。"""
        assert "VSS_PATHS.get(_k)" in self.src or "if not VSS_PATHS" in self.src, (
            "虚拟信号必须跳过，否则会被误判（历史上踩过这个坑）"
        )

    def test_clears_on_reappear(self):
        """信号重新出现时要清除计数（避免误判后无法恢复）。"""
        assert "pop(_k, None)" in self.src or "_absent_count.pop" in self.src, (
            "信号回来后必须清除计数"
        )
        assert "discard(_k)" in self.src or "_unsupported.discard" in self.src, (
            "信号回来后必须解除不支持判定"
        )


class TestSensorHonoursGate:
    def test_sensor_returns_none_for_unsupported(self):
        src = _sensor_src()
        assert "unsupported_keys" in src, (
            "sensor 必须读取 unsupported_keys，否则门控不生效"
        )

    def test_gate_returns_none_not_string(self):
        """必须返回 None（HA 显示 unavailable），不能返回字符串。"""
        src = _sensor_src()
        m = re.search(r"unsupported_keys.*?\n(.*?)\n", src, re.S)
        assert m, "找不到门控代码"
        block = src[m.start():m.start() + 400]
        assert "return None" in block, (
            "门控分支必须 return None；返回 'unknown' 会被 HA 校验拒绝"
        )


class TestNoHardcodedModelGate:
    """★ 不许按车型名硬编码 —— 我们没有那个证据。"""

    def test_no_seriesno_gate_for_endurance(self):
        import signals as sg
        spec = sg.SIGNALS.get("range_total_cltc")
        if spec is None:
            pytest.skip("该分支没有总续航信号")
        req = getattr(spec, "requires", None) or ""
        assert "version:" not in req, (
            "不要用 version 门控总续航 —— 没有任何证据支持某个版本有/没有"
        )

    def test_endurance_signals_have_no_guesswork_requirement(self):
        import signals as sg
        for key in ("range_total_cltc", "range_total_wltc",
                    "range_display_mode"):
            spec = sg.SIGNALS.get(key)
            if spec is None:
                continue
            req = getattr(spec, "requires", None)
            assert req is None or req in ("bev", "combustion"), (
                f"{key} 的 requires={req!r} 是按车型猜的；"
                "应留给数据驱动门控处理"
            )


class TestUnavailableSemantics:
    """★ 「该车型不上报」必须表达为 unavailable，不是 unknown。

    修复的语义 bug：原代码在「从未上报」时 `return None`，
    而 HA 把 None 显示为 **unknown** —— 但注释写的是 unavailable。
    两者对用户含义完全不同：
        unknown     = 暂时没拿到（可能稍后就有）
        unavailable = 这个实体在此车上不存在/不可用
    """

    def test_available_property_exists(self):
        src = _sensor_src()
        assert "def available" in src, (
            "必须有 available 属性，否则无法区分 unknown 与 unavailable"
        )

    def test_available_honours_unsupported_keys(self):
        src = _sensor_src()
        i = src.find("def available")
        assert i > 0
        block = src[i:i + 1600]
        assert "unsupported_keys" in block, (
            "available 必须读取数据驱动门控的结果"
        )

    def test_available_checks_empty_ts(self):
        """服务端返回了路径但 ts 为空（从未上报）也算不可用。"""
        src = _sensor_src()
        i = src.find("def available")
        block = src[i:i + 1600]
        assert 'ts in ("", "0")' in block, (
            "available 必须处理「路径有效但 ts 恒空」的情况"
        )

    def test_available_calls_super(self):
        """★ 不能覆盖掉基类的判定（车辆离线时基类会返回 False）。"""
        src = _sensor_src()
        i = src.find("def available")
        block = src[i:i + 600]
        assert "super().available" in block, (
            "必须先看基类的 available，否则车辆离线时实体反而显示可用"
        )

    def test_does_not_affect_healthy_signals(self):
        """有正常数据的信号不受影响（回归保护）。"""
        src = _sensor_src()
        i = src.find("def available")
        block = src[i:i + 1600]
        # 两个判定都是「命中才 False」，末尾必须 return True
        assert "return True" in block, (
            "默认必须返回可用，只对明确不支持的 key 返回 False"
        )
