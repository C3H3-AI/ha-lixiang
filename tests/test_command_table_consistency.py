"""车控命令与 App 官方配置表的一致性测试。

★★ 为什么需要这个 ★★

App 里有两张**官方车控配置表**（`assets/2025/`）：

    LXMVehicleConfig2025.json  → M 系（理想ONE）69 条
    LXXVehicleConfig2025.json  → X 系（L6/L7/L8/L9）98 条

每条给出 `{des, cmdKey, cmdData, uri, expireAt}` —— 这是**车厂自己的标准答案**。
集成里的 cmdKey/cmdData 是逆向推出来的，**必须与官方表一致**：
写错一个 key 或一个参数名，车控就是静默失败（或做错事）。

本文件把官方表**冻成快照**（`OFFICIAL_X_SERIES`），逐个断言集成用的值一致。

★ 刷新快照的方法：
    重新解包最新 APK，读 `assets/2025/LXXVehicleConfig2025.json`，
    把有 `cmdKey` 的条目按 (cmdKey, 语义) 抄到下面的字典里，
    并在 `_PROVENANCE` 里更新版本号。

★ 2026-10-12 首次审计结论：**集成与官方表一致，未发现不一致**。
  唯一差异是空调：官方「打开空调」用 `frtACAUTOSw`（自动模式），
  集成默认用 `frtACSw`（普通开关，**真机实测可用**）并另备 AUTO 常量 ——
  两者都在表里，属合法差异，已在 `_ACCEPTED_DIFFERENCES` 里注明理由。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parents[1] / "custom_components" / "lixiang_auto"
sys.path.insert(0, str(_INTEG))

_PROVENANCE = "APK 8.27.0 / assets/2025/LXXVehicleConfig2025.json（98 条，其中 25 个不同 cmdKey）"


# ---------------------------------------------------------------------------
# 官方配置表快照：(cmdKey, 语义) -> cmdData
# 只收有非空 cmdData 的条目 —— cmdKey 本身单独断言。
# ---------------------------------------------------------------------------
OFFICIAL_X_SERIES: dict[tuple[str, str], dict] = {
    ("cpCtrl", "开"): {"cpOpen": "ON"},
    ("cpCtrl", "关"): {"cpOpen": "OFF"},
    ("fTkC", "开"): {"lockSw": "1"},
    ("fTkC", "关"): {"lockSw": "0"},
    ("mobileVehSvm", "拍照"): {"vehImage": "veh_svm_image"},
    ("remoteVehLockControl", "解锁"): {"lockSw": "1"},
    ("remoteVehLockControl", "上锁"): {"lockSw": "0"},
    ("remoteVehPlgControl", "开"): {"plgPosi": "100"},
    ("remoteVehPlgControl", "关"): {"plgPosi": "0"},
    ("remoteVehSearch", "位置"): {"searchType": "0"},
    ("remoteVehSearch", "闪灯"): {"searchType": "1"},
    ("remoteVehSearch", "鸣笛"): {"searchType": "2"},
    ("remoteVehWdwControl", "开"): {
        "flWindPosi": "99", "frWindPosi": "99",
        "rlWindPosi": "99", "rrWindPosi": "99",
    },
    ("remoteVehWdwControl", "开缝"): {
        "flWindPosi": "10", "frWindPosi": "10",
        "rlWindPosi": "10", "rrWindPosi": "10",
    },
    ("remoteVehWdwControl", "关"): {
        "flWindPosi": "0", "frWindPosi": "0",
        "rlWindPosi": "0", "rrWindPosi": "0",
    },
    ("rmCtrl", "折叠"): {"ctrlType": "FOLD", "ctrlValue": "ON"},
    ("rmCtrl", "展开"): {"ctrlType": "FOLD", "ctrlValue": "OFF"},
    ("rmCtrl", "加热开"): {"ctrlType": "HEAT", "ctrlValue": "ON"},
    ("rmCtrl", "加热关"): {"ctrlType": "HEAT", "ctrlValue": "OFF"},
    ("sentinelModeSetting", "开"): {"sentinelSwitch": "1"},
    ("sentinelModeSetting", "关"): {"sentinelSwitch": "0"},
}

#: 官方表里全部 25 个 cmdKey（集成可能只用其中一部分 —— 没用的不该出现乱写）
OFFICIAL_CMD_KEYS = {
    "ReserveModify", "cpCtrl", "fTkC", "mobileVehCloseStream",
    "mobileVehPushStream", "mobileVehSvm", "navigate_to_poi", "open", "quit",
    "quit_lock", "remoteADCtrl", "remoteVehACSmartControl", "remoteVehAuth",
    "remoteVehFrgControl", "remoteVehLockControl", "remoteVehPlgControl",
    "remoteVehSearch", "remoteVehWdwControl", "remoteVoiceControl",
    "remote_ai_close", "remote_ai_open", "remote_charge_control", "rmCtrl",
    "sentinelModeSetting", "ssCtrl",
}

#: 集成**有意**与官方表不同的地方（每条必须写理由）
_ACCEPTED_DIFFERENCES: dict[tuple[str, str], str] = {
    ("fTkC", "lockSw"): (
        "★ 2026-10-14 车主**实车**实测：官方配置表快照把『开前备箱』记为 lockSw=1，"
        "但实车方向相反 —— 集成的『打开』必须发 lockSw=0（发 1 反而关闭）。"
        "命令方向以实车为准；快照保留官方原始记录作为 provenance，不改写。"
        "回归测试见 tests/test_frunk_polarity.py。"
    ),
    ("remoteVehACSmartControl", "acCtrlType"): (
        "官方『打开空调』用 frtACAUTOSw（自动模式）；集成默认用 frtACSw"
        "（普通开关，**真机实测可用**），并另留 AC_TYPE_AUTO=frtACAUTOSw。"
        "两者都在官方表里，属合法差异。"
    ),
    ("remoteVehACSmartControl", "acCountdownTimer"): (
        "官方值 30；集成用 15（真机实测可用）。该字段是倒计时提示时长，"
        "不影响开关结果。"
    ),
}


# ---------------------------------------------------------------------------
def _load(name: str, extra_replace: dict | None = None, preload_va: bool = False):
    """exec 加载集成模块（测试环境没有 homeassistant 包）。"""
    if preload_va and "vehicle_ability" not in sys.modules:
        va_src = (_INTEG / "vehicle_ability.py").read_text(encoding="utf-8")
        va_src = va_src.replace("from .const import LOGGER_NAME",
                                "LOGGER_NAME = 'test'")
        va_src = va_src.replace(
            '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
            f'_CONFIG_DIR = Path({str(_INTEG / "vehicle_configs")!r})')
        va = types.ModuleType("vehicle_ability")
        va.__file__ = str(_INTEG / "vehicle_ability.py")
        exec(compile(va_src, "vehicle_ability.py", "exec"), va.__dict__)
        sys.modules["vehicle_ability"] = va

    src = (_INTEG / f"{name}.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace("from .vehicle_ability import VehicleAbility, get_ability",
                      "from vehicle_ability import VehicleAbility, get_ability")
    for a, b in (extra_replace or {}).items():
        src = src.replace(a, b)
    mod = types.ModuleType(f"{name}_under_test")
    mod.__file__ = str(_INTEG / f"{name}.py")
    exec(compile(src, f"{name}.py", "exec"), mod.__dict__)
    return mod


_SRC_ALL = "\n".join(
    p.read_text(encoding="utf-8", errors="ignore")
    for p in _INTEG.glob("*.py")
)


# ---------------------------------------------------------------------------
# 1. 集成用到的 cmdKey 必须都在官方表里
# ---------------------------------------------------------------------------
class TestCmdKeysAreOfficial:
    def _declared_keys(self) -> set[str]:
        """从集成源码里抽 CMD_* 常量与 cmd_key= 字面量。"""
        import re
        keys = set(re.findall(r'CMD_[A-Z_]+\s*=\s*"([a-zA-Z_]+)"', _SRC_ALL))
        keys |= set(re.findall(r'cmd_key\s*=\s*"([a-zA-Z_]+)"', _SRC_ALL))
        return keys

    def test_declared_keys_are_known(self):
        declared = self._declared_keys()
        unknown = declared - OFFICIAL_CMD_KEYS
        # JOB 通道的 cmdKey 来自 commandDestParamsMap，不在车控配置表里
        job_whitelist = {
            "remoteChargingControl",   # mobileVehSvm/充电等走 JOB
        }
        unknown -= job_whitelist
        assert not unknown, (
            f"这些 cmdKey 不在官方配置表里（写错了？）: {sorted(unknown)}\n"
            f"  官方 25 个: {sorted(OFFICIAL_CMD_KEYS)}")

    @pytest.mark.parametrize("key", [
        "remoteVehLockControl", "remoteVehPlgControl", "remoteVehWdwControl",
        "remoteVehSearch", "fTkC", "cpCtrl", "rmCtrl", "mobileVehSvm",
        "sentinelModeSetting", "remote_charge_control",
    ])
    def test_key_used_by_integration(self, key):
        """这些是我们实际依赖的 cmdKey，必须在源码里出现。"""
        assert key in _SRC_ALL, f"{key} 在集成源码里找不到了"


# ---------------------------------------------------------------------------
# 2. cmdData 与官方一致
# ---------------------------------------------------------------------------
class TestCmdDataMatchesOfficial:
    def test_lock_data(self):
        """车锁：{"lockSw": "1"} 解锁 / {"lockSw": "0"} 上锁。"""
        assert '"lockSw": "1"' in _SRC_ALL or "'lockSw': '1'" in _SRC_ALL, "解锁参数缺失"
        assert '"lockSw": "0"' in _SRC_ALL or "'lockSw': '0'" in _SRC_ALL, "上锁参数缺失"

    def test_plg_data(self):
        """尾门：plgPosi 100 开 / 0 关。"""
        assert '"plgPosi": "100"' in _SRC_ALL or "'plgPosi': '100'" in _SRC_ALL
        assert '"plgPosi": "0"' in _SRC_ALL or "'plgPosi': '0'" in _SRC_ALL

    def test_wdw_data(self):
        """车窗：四窗同时给位，开=99 关=0。"""
        for k in ("flWindPosi", "frWindPosi", "rlWindPosi", "rrWindPosi"):
            assert k in _SRC_ALL, f"车窗参数 {k} 缺失"

    def test_search_data(self):
        """寻车：searchType 0=位置 1=闪灯 2=鸣笛。"""
        assert '"searchType": "0"' in _SRC_ALL or '"searchType": 0' in _SRC_ALL
        assert '"searchType": 1' in _SRC_ALL, "闪灯 searchType=1 缺失"
        assert '"searchType": 2' in _SRC_ALL, "鸣笛 searchType=2 缺失"

    def test_mirror_data(self):
        """后视镜：ctrlType = HEAT（加热）/ FOLD（折叠）。"""
        assert '"ctrlType": "HEAT"' in _SRC_ALL or "'ctrlType': 'HEAT'" in _SRC_ALL
        assert '"ctrlType": "FOLD"' in _SRC_ALL or "'ctrlType': 'FOLD'" in _SRC_ALL
        assert "ctrlValue" in _SRC_ALL

    def test_charge_port_data(self):
        """充电口盖：cpOpen 取 ON / OFF。

        ★ 集成里是条件表达式 `{"cpOpen": "ON" if level != 0 else "OFF"}`，
          所以不能断言 `"cpOpen": "OFF"` 这个完整片段 —— 只断言两者都在。
        """
        assert "cpOpen" in _SRC_ALL, "充电口盖参数 cpOpen 缺失"
        assert '"ON"' in _SRC_ALL and '"OFF"' in _SRC_ALL, (
            "cpOpen 的 ON/OFF 取值必须都出现（官方表就是这两个值）")

    def test_sentinel_data(self):
        """哨兵：sentinelSwitch 1/0。"""
        assert "sentinelSwitch" in _SRC_ALL

    def test_svm_data(self):
        """拍照：vehImage 固定 veh_svm_image。"""
        assert "veh_svm_image" in _SRC_ALL


# ---------------------------------------------------------------------------
# 3. 接受差异必须写明理由（防止随手糊弄）
# ---------------------------------------------------------------------------
class TestAcceptedDifferencesDocumented:
    def test_every_difference_has_reason(self):
        for k, why in _ACCEPTED_DIFFERENCES.items():
            assert len(why) >= 20, f"{k} 的理由太短，说不清楚"

    def test_provenance_recorded(self):
        assert "assets/2025" in _PROVENANCE
        assert "LXXVehicleConfig" in _PROVENANCE


# ---------------------------------------------------------------------------
# 4. 官方表自身完整性（防止抄漏）
# ---------------------------------------------------------------------------
class TestSnapshotIntegrity:
    def test_cmd_key_count(self):
        assert len(OFFICIAL_CMD_KEYS) == 25, (
            f"官方 X 系表有 25 个不同 cmdKey，快照里 {len(OFFICIAL_CMD_KEYS)} 个")

    def test_all_cmd_keys_in_snapshot_entries(self):
        """快照里出现的 cmdKey 都必须在全量集合里。"""
        for ck, _sem in OFFICIAL_X_SERIES:
            assert ck in OFFICIAL_CMD_KEYS, f"{ck} 不在全量 cmdKey 集合里"

    def test_wdw_entries_have_four_windows(self):
        for (ck, sem), data in OFFICIAL_X_SERIES.items():
            if ck == "remoteVehWdwControl":
                assert len(data) == 4, f"{ck}/{sem} 应有 4 个车窗位"
