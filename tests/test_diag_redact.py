"""脱敏模块的离线单测 —— 不 import HA，纯函数可直接跑。

★ 这些测试的职责：把"密码/token 不出现、位置被掩码、VIN 只留指纹"
  钉死。将来有人改了脱敏逻辑，测试先红。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / "custom_components" / "lixiang_auto" / "diag_redact.py"


def _load():
    spec = importlib.util.spec_from_file_location("diag_redact", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dr = _load()


# ── 位置掩码 ────────────────────────────────────────────────
class TestLocationMasking:
    @pytest.mark.parametrize("key", [
        "longitude", "latitude", "lng", "lat",
        "gps_longitude", "gps_latitude", "coord", "vehiclePosition", "location",
    ])
    def test_location_values_are_masked(self, key):
        out = dr.redact_realtime_state({"data": {key: "999.999999"}})
        got = out["data"][key]
        assert got == "<masked-location>", f"{key} 未被掩码: {got!r}"
        assert "999.999999" not in str(out), "原始坐标泄露！"

    def test_real_world_sample(self):
        """用真实 ONE 响应里出现过的位置字段名。"""
        raw = {"data": {"vehiclePosition": {
            "longitude": "999.999999", "latitude": "999.999998",
            "altitude": "44", "direction": "180"}}}
        out = dr.redact_realtime_state(raw)
        vp = out["data"]["vehiclePosition"]
        assert vp["longitude"] == "<masked-location>"
        assert vp["latitude"] == "<masked-location>"
        assert "999.999999" not in str(out)
        assert "999.999998" not in str(out)


# ── 凭据掩码 ────────────────────────────────────────────────
class TestCredentialMasking:
    @pytest.mark.parametrize("key,val", [
        ("token", "eyJhbGciOiJSUzI1NiJ9.payload.sig"),
        ("accessToken", "abc123"),
        ("refresh_token", "r-xyz"),
        ("jwt", "eyJ..."),
        ("password", "p@ssw0rd"),
        ("session", "sess-1"),
        ("cookie", "a=b"),
        ("hac_key", "k"),
        ("xdev", "device"),
        ("phone", "13900000000"),
        ("device_id", "d-1"),
        ("imei", "860000000000000"),
    ])
    def test_credential_values_are_masked(self, key, val):
        out = dr.redact_realtime_state({"data": {key: val}})
        got = out["data"][key]
        assert val not in str(got), f"{key} 泄露了原值: {got!r}"
        assert got.startswith("<") or got == "", "应被替换为类型+长度指纹"

    def test_credential_masking_is_recursive(self):
        raw = {"data": {"deep": {"deeper": {"token": "SECRET"}}}}
        out = dr.redact_realtime_state(raw)
        assert "SECRET" not in str(out)
        assert out["data"]["deep"]["deeper"]["token"].startswith("<")

    def test_no_real_phone_number_anywhere(self):
        """★ 用真实出现过手机号做样本，确保字符串形式也不残留。"""
        raw = {"data": {"phone": "13900000000",
                        "nested": {"mobile": "13900000000"}}}
        out = dr.redact_realtime_state(raw)
        assert "13900000000" not in str(out)


# ── VIN 指纹 ────────────────────────────────────────────────
class TestVinFingerprint:
    def test_vin_becomes_stable_fingerprint(self):
        fp1 = dr.vin_fingerprint("HLX0000000000000TEST")
        fp2 = dr.vin_fingerprint("HLX0000000000000TEST")
        assert fp1 == fp2, "同一辆车必须得到同一个指纹"
        assert fp1.startswith("vin-")
        assert "HLX0000000000000TEST" not in fp1, "VIN 本身不得出现"

    def test_different_vins_differ(self):
        assert dr.vin_fingerprint("AAA") != dr.vin_fingerprint("BBB")

    def test_empty(self):
        assert dr.vin_fingerprint("") == ""
        assert dr.vin_fingerprint(None) == ""

    def test_filename_token_safe(self):
        t = dr.safe_filename_token("HLX0000000000000TEST")
        assert t.isalnum()
        assert len(t) == 8
        assert "HLX0000000000000TEST" not in t


# ── 条目白名单 ──────────────────────────────────────────────
class TestEntryAllowlist:
    def test_only_allowlisted_keys_survive(self):
        data = {
            "vin": "HLX0000000000000TEST",       # ❌ 直接 VIN
            "vin_fingerprint": dr.vin_fingerprint("HLX0000000000000TEST"),
            "car_type": "L6",                  # ✅
            "car_nickname": "小L",              # ✅
            "platform": "1",                   # ✅
            "token": "SECRET",                 # ❌
            "refresh_token": "SECRET",         # ❌
            "password": "p",                   # ❌
            "phone": "13900000000",            # ❌
        }
        out = dr.redact_entry_data(data)
        assert set(out) == {"vin_fingerprint", "car_type", "car_nickname", "platform"}
        assert "SECRET" not in str(out)
        assert "13900000000" not in str(out)
        assert "HLX0000000000000TEST" not in str(out)

    def test_none_input(self):
        assert dr.redact_entry_data(None) == {}

    def test_new_sensitive_field_defaults_to_dropped(self):
        """★ 关键承诺：将来新增敏感字段，默认行为是「不导出」而非「泄露」。"""
        data = {"car_type": "L6", "some_new_secret_field": "oops"}
        out = dr.redact_entry_data(data)
        assert "some_new_secret_field" not in out
        assert out == {"car_type": "L6"}


# ── 普通信号不被误伤 ────────────────────────────────────────
class TestNormalSignalsPreserved:
    def test_signal_values_survive(self):
        """信号号/值是协议层公共信息，是"某车型上报哪些信号"的唯一证据。"""
        raw = {"data": {"batteryLevel": "78", "mileage": "1234.5",
                        "doorLock": "1", "tirePressure": "2.4"}}
        out = dr.redact_realtime_state(raw)
        assert out["data"]["batteryLevel"] == "78"
        assert out["data"]["mileage"] == "1234.5"
        assert out["data"]["doorLock"] == "1"

    def test_structure_preserved(self):
        raw = {"data": {"a": {"b": {"c": "1"}}}}
        out = dr.redact_realtime_state(raw)
        assert out["data"]["a"]["b"]["c"] == "1"
        assert out["_redacted"] is True

    def test_lists_preserved(self):
        raw = {"data": {"tips": ["a", "b"]}}
        out = dr.redact_realtime_state(raw)
        assert out["data"]["tips"] == ["a", "b"]

    def test_non_dict_input(self):
        out = dr.redact_realtime_state("string")
        assert out["_redacted"] is True


# ── 日志摘要 ────────────────────────────────────────────────
class TestLogSummary:
    def test_summary_has_no_values(self):
        raw = {"data": {"batteryLevel": "78", "doorLock": "1"},
               "attempts": {"a": {"ok": True}}}
        s = dr.summarize_for_log(raw)
        assert "78" not in str(s)
        assert "batteryLevel" in str(s) or s["top_level_count"] >= 1
        assert s["top_level_count"] == 2

    def test_truncates(self):
        raw = {f"g{i}": {} for i in range(30)}
        s = dr.summarize_for_log(raw, max_keys=5)
        assert s["truncated"] is True
        assert len(s["groups"]) == 5


# ── mask_value ──────────────────────────────────────────────
class TestMaskValue:
    def test_preserves_type_and_length_only(self):
        assert dr.mask_value("12345") == "<str:len5>"
        assert dr.mask_value(42) == "<int:len2>"
        assert dr.mask_value(None) == ""
        assert dr.mask_value("") == ""

    def test_does_not_leak(self):
        m = dr.mask_value("supersecret")
        assert "supersecret" not in m


# ── VIN 掩码（端到端验证抓到的真 bug）──────────────────────
class TestVinMasking:
    """★ 2026-10-20：端到端验证（注入真实 VIN）发现 VIN 键未被命中。

    单测漏掉的原因：只想到 token/phone，没想到 VIN 本身也要掩。
    教训：**用真实出现过的敏感值做样本**，而不是只测"想得到的键名"。
    """

    @pytest.mark.parametrize("key", ["vin", "VIN", "vehicle_id",
                                     "vehicleId", "frame_no"])
    def test_vin_variants_masked(self, key):
        out = dr.redact_realtime_state({"data": {key: "HLX0000000000000TEST"}})
        got = out["data"][key]
        assert "HLX0000000000000TEST" not in str(got), f"{key} 泄露了 VIN"

    def test_vin_in_nested_structure(self):
        raw = {"data": {"vehicleInfo": {"vin": "HLX0000000000000TEST"}}}
        out = dr.redact_realtime_state(raw)
        assert "HLX0000000000000TEST" not in str(out)

    def test_realistic_injection_scenario(self):
        """★ 模拟最坏情况：原始响应里同时有 token/手机号/VIN/坐标。"""
        raw = {"data": {
            "token": "FAKE_TOKEN_VALUE",
            "phone": "13900000000",
            "vin": "HLX0000000000000TEST",
            "vehiclePosition": {"longitude": "999.999999",
                                "latitude": "999.999998"},
        }}
        out = dr.redact_realtime_state(raw)
        blob = str(out)
        for bad in ("FAKE_TOKEN_VALUE", "13900000000",
                    "HLX0000000000000TEST", "999.999999", "999.999998"):
            assert bad not in blob, f"{bad} 泄露！"

    def test_structure_survives_redaction(self):
        """脱敏不得破坏结构（排障要靠结构）。"""
        raw = {"data": {"a": {"b": "1"}, "c": {"d": "2"}}}
        out = dr.redact_realtime_state(raw)
        assert set(out["data"]) == {"a", "c"}
        assert out["data"]["a"]["b"] == "1"


# ── 位置容器不被整树掩掉（另一个真 bug）───────────────────
class TestLocationContainerNotOverMasked:
    """★ vehiclePosition / gpsInfo 这类"装着位置的组"要递归，
    不能把整棵树掩成一个字符串（否则组里其它字段也丢了）。
    """

    def test_position_group_recursed(self):
        raw = {"data": {"vehiclePosition": {
            "longitude": "999.999999", "latitude": "999.999998",
            "altitude": "44", "direction": "180"}}}
        out = dr.redact_realtime_state(raw)
        vp = out["data"]["vehiclePosition"]
        assert isinstance(vp, dict), "位置组被整树掩掉了！"
        assert vp["longitude"] == "<masked-location>"
        assert vp["latitude"] == "<masked-location>"
        # 组里的非坐标字段必须保留
        assert vp["altitude"] == "44"
        assert vp["direction"] == "180"


# ── 位置规则的误伤（服务级测试抓到的真 bug）────────────────
class TestLocationFalsePositives:
    """★ 2026-10-20：服务级验证发现位置规则误伤了排障关键字段。

    bug ① "lat" 子串命中 "hmi_platform"（p-lat-form）
           —— hmi_platform 是 SS3/SS4 协议判定，排障关键，被误掩
    bug ② "position" 子串命中 gearPosition/windowPosition/seatPosition
           等【档位/开度】字段，同样是排障关键

    修法：短键（lat/lng/coord）改精确匹配；去掉 "position" 子串，
          只留真坐标语义（longitude/latitude/vehiclePosition/gps_*）。
    """

    @pytest.mark.parametrize("key", [
        "hmi_platform", "platform",                    # bug ①
        "gearPosition", "windowPosition", "seatPosition",  # bug ②
        "chargePosition", "transmissionPosition",
        "sunroofPosition", "doorPosition", "acPosition",
    ])
    def test_gear_and_platform_not_masked(self, key):
        out = dr.redact_realtime_state({"data": {key: "5"}})
        assert out["data"][key] == "5", (
            f"{key} 被误掩 —— 它是档位/协议判定，不是坐标")

    @pytest.mark.parametrize("key", [
        "longitude", "latitude", "lat", "lng",
        "gps_longitude", "gps_latitude", "gps_info",
        "vehiclePosition", "location",
    ])
    def test_real_coordinates_still_masked(self, key):
        out = dr.redact_realtime_state({"data": {key: "116.397128"}})
        got = out["data"][key]
        assert "116.397128" not in str(got), f"{key} 应被掩码"

    def test_vehicle_position_group_recursed(self):
        """坐标组仍要递归（组内非坐标字段保留）。"""
        raw = {"data": {"vehiclePosition": {
            "longitude": "116.397128", "latitude": "39.916527",
            "altitude": "44"}}}
        out = dr.redact_realtime_state(raw)
        vp = out["data"]["vehiclePosition"]
        assert vp["longitude"] == "<masked-location>"
        assert vp["altitude"] == "44"        # 非坐标字段保留
