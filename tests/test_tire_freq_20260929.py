"""胎压/胎温降频（2026-09-29）—— 减少高频轮询与数据库重复写入。

背景
----
HA 日志出现「Updating state ... took 0.5~10 seconds」警告，且
`home-assistant_v2.db` 涨到 512 MB（states 表 142 万行）。

查看数据库发现：**胎压/胎温的写入绝大多数是重复值**。

    实体                              写入行数   不同值
    sensor.…tai_ya_zuo_qian              9,925      11
    sensor.…tai_wen_zuo_qian             8,993      17

约 900:1 —— 即 99.9% 的轮询/写入是无意义的重复。

结论：胎压/胎温是**慢变量**，不需要 5 分钟一次。
    从 HIGH(300s) 降到 MID(3600s)，**轮询请求量降 92%**。

★ 唯独 `tire_xx_warning`（胎压告警）**保持 HIGH** —— 那是安全相关，
  必须第一时间发现（爆胎/扎钉）。

设计取舍
--------
慢漏气（例如每小时掉 10 kPa）在 1 小时粒度下仍能及时发现；
且告警信号仍是 5 分钟粒度，安全性不受影响。
"""
from __future__ import annotations

import pytest

import signals as sg

PRESSURE_TEMP_KEYS = [
    "tire_fl", "tire_fr", "tire_rl", "tire_rr",
    "tire_fl_temp", "tire_fr_temp", "tire_rl_temp", "tire_rr_temp",
]
WARNING_KEYS = [
    "tire_fl_warning", "tire_fr_warning",
    "tire_rl_warning", "tire_rr_warning",
]


class TestTireSlowSignalsAreMid:
    """胎压/胎温是慢变量 → MID（1 小时）。"""

    @pytest.mark.parametrize("key", PRESSURE_TEMP_KEYS)
    def test_is_mid(self, key):
        assert sg.SIGNALS[key].freq == sg.Freq.MID, (
            f"{key} 应为 MID：数据库实测约 900:1 的重复写入，"
            "5 分钟轮询没有意义"
        )

    def test_all_pressure_temp_covered(self):
        """八个胎压/胎温一个都不能漏（漏一个就白降频了）。"""
        for key in PRESSURE_TEMP_KEYS:
            assert key in sg.SIGNALS, f"{key} 不存在"

    def test_pressure_temp_not_high(self):
        high = {s.key for s in sg.by_freq(sg.Freq.HIGH)}
        leaked = [k for k in PRESSURE_TEMP_KEYS if k in high]
        assert not leaked, f"这些胎压/胎温仍是 HIGH: {leaked}"


class TestTireWarningsStayHigh:
    """★ 胎压告警必须保持 HIGH —— 安全相关，不能跟着降频。"""

    @pytest.mark.parametrize("key", WARNING_KEYS)
    def test_is_high(self, key):
        assert sg.SIGNALS[key].freq == sg.Freq.HIGH, (
            f"{key} 必须保持 HIGH：爆胎/扎钉要第一时间发现"
        )

    def test_warnings_are_alarm_semantics(self):
        for key in WARNING_KEYS:
            assert sg.SIGNALS[key].semantics == sg.Semantics.ALARM, (
                f"{key} 应是告警语义"
            )

    def test_warnings_are_binary_sensors(self):
        for key in WARNING_KEYS:
            assert "binary_sensor" in sg.SIGNALS[key].platforms, (
                f"{key} 应在 binary_sensor 平台"
            )


class TestNoFeatureLoss:
    """只增不删：降频不改变实体本身。"""

    @pytest.mark.parametrize("key", PRESSURE_TEMP_KEYS + WARNING_KEYS)
    def test_still_sensor_visible(self, key):
        spec = sg.SIGNALS[key]
        assert spec.path, f"{key} 必须仍有 VSS 路径"
        assert spec.name, f"{key} 必须仍有名称"
        assert spec.universal is True, f"{key} 应仍是 universal"

    def test_sensor_count_unchanged(self):
        """降频不减少任何 sensor 实体数。"""
        keys = {s.key for s in sg.specs_for("sensor")}
        for key in PRESSURE_TEMP_KEYS:
            assert key in keys, f"{key} 不该从 sensor 平台消失"


class TestSavingsAreReal:
    """把「省了多少」写进测试，避免以后有人随手改回去。"""

    def test_high_freq_count_reduced_by_eight(self):
        """HIGH 档应比「未降频」时少 8 个（这 8 个已移到 MID）。"""
        hi = {s.key for s in sg.by_freq(sg.Freq.HIGH)}
        overlap = [k for k in PRESSURE_TEMP_KEYS if k in hi]
        assert overlap == [], "这 8 个信号不应出现在 HIGH 里"

    def test_mid_freq_contains_them(self):
        mid = {s.key for s in sg.by_freq(sg.Freq.MID)}
        for key in PRESSURE_TEMP_KEYS:
            assert key in mid, f"{key} 应在 MID 档"
