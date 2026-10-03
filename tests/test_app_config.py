"""App 配置表测试（app_config.py）—— 2026-09-26 新增

背景：我们自己拼 VAT scope（14 个含 cpCtrl/ssCtrl/ChargingControl）导致
      服务端整批降级，只授权 8 个。权威来源是 APK 内置的 subTokenData。

本测试守卫：
  · 配置表能正常加载（40 项）
  · 端点 → audience/type/scope 反查正确
  · ★ 关键端点的 audience 与集成常量一致（防止再猜错）
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
_CFG = _INTEG / "app_config"


def _load():
    src = (_INTEG / "app_config.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", 'LOGGER_NAME = "test"')
    src = src.replace(
        '_CONFIG_DIR = Path(__file__).parent / "app_config"',
        f'_CONFIG_DIR = Path({str(_CFG)!r})')
    mod = types.ModuleType("ac_test")
    exec(compile(src, "app_config.py", "exec"), mod.__dict__)
    return mod


ac = _load()


class TestConfigFiles:
    def test_sub_token_data_exists(self):
        assert (_CFG / "sub_token_data.json").is_file()

    def test_app_config_exists(self):
        assert (_CFG / "app_config.json").is_file()

    def test_40_token_types(self):
        assert len(ac.all_types()) == 40, f"实际 {len(ac.all_types())}"


class TestTokenConfig:
    def test_vat_1(self):
        cfg = ac.token_config("VAT_1")
        assert cfg["audience"] == "5Tc7yDrnMzALwc9Rytl9sp"
        assert len(cfg["scope"]) == 12
        assert "remoteVehACSmartControl" in cfg["scope"]

    def test_vat_1_has_no_charging_scope(self):
        """★ App 的 VAT_1 里没有充电 scope（充电走 JOB）。"""
        cfg = ac.token_config("VAT_1")
        for s in cfg["scope"]:
            assert "Charg" not in s
            assert s != "cpCtrl"

    def test_mms(self):
        cfg = ac.token_config("mms-api")
        assert cfg["audience"] == "5a1X5rZcWZNeEOYlyRigUs"
        assert cfg["scope"] == ["ALL"]

    def test_unknown_type(self):
        assert ac.token_config("NOPE") == {}


class TestReverseLookup:
    """按端点反查（长前缀优先）。"""

    def test_cmd_send(self):
        assert ac.type_for(
            "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send"
        ) == "httpLiMeshServiceV2"
        assert ac.audience_for(
            "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send"
        ) == "1j0vgTqagJUHuT6nLmbTGx"

    def test_vss(self):
        assert ac.audience_for(
            "/ssp-cloud-vss-service/mobile/vss/get-batch"
        ) == "1j0vgTqagJUHuT6nLmbTGx"

    def test_mms(self):
        assert ac.audience_for("/mms-api/v1-0/message") == "5a1X5rZcWZNeEOYlyRigUs"

    def test_saos_vehicle(self):
        assert ac.audience_for(
            "/saos-vehicle-api/v2-0/vehicles/basics"
        ) == "7gbeHMwBPMZA5SU1b2awIo"

    def test_unknown_path(self):
        assert ac.audience_for("/nonexistent/path") == ""
        assert ac.type_for("/nonexistent/path") == ""

    def test_scope_for(self):
        sc = ac.scope_for(
            "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send")
        assert "veh-ctrl:cmd-send" in sc


class TestMatchesIntegrationConstants:
    """★ 集成里的 audience 常量必须与权威表一致。"""

    @staticmethod
    def _consts() -> dict:
        import ast
        src = (_INTEG / "li_api.py").read_text(encoding="utf-8")
        out = {}
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    n = getattr(t, "id", "")
                    if n.startswith("AUD_") and isinstance(node.value, ast.Constant):
                        out[n] = node.value.value
        return out

    def test_all_audiences_in_table(self):
        """集成用的每个 audience 都应在权威表里出现。"""
        known = {c["audience"] for c in ac.load_token_table().values()}
        for name, val in self._consts().items():
            assert val in known, f"{name}={val} 不在权威表里（可能是猜的）"

    def test_vat_audience(self):
        c = self._consts()
        assert c.get("AUD_VAT") == "5Tc7yDrnMzALwc9Rytl9sp"

    def test_mms_audience(self):
        c = self._consts()
        assert c.get("AUD_MMS") == "5a1X5rZcWZNeEOYlyRigUs"


class TestAppConfig:
    def test_has_lid_domain(self):
        cfg = ac.load_app_config()
        assert cfg.get("LiIDDomain") == "https://account.lixiang.com"

    def test_has_sub_token_data(self):
        cfg = ac.load_app_config()
        assert "subTokenData" in cfg
