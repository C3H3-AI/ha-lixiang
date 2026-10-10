"""key_suite.py 测试 —— 签名身份派生（2026-10-10「去 iPad 化」核心模块）

锁定三类行为（对应 Phase A 实测结论）：
  1. data_to_sign / body / x-chj 11 段签名的拼接格式（§60.1 配方）
  2. formatDK 派生链（RSA 解密 → AES-CTR）可用且方向正确
  3. 两套身份常量（KID ↔ 私钥）结构完整、app_type 路由正确

不发网络 —— 只测纯函数（项目惯例：避开 homeassistant 依赖）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmod
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _load_key_suite():
    """加载 key_suite（其 from .const 由同名桩包解析，避开 homeassistant）。"""
    pkg = types.ModuleType("_lx_ks")
    pkg.__path__ = [str(INTEG)]
    sys.modules["_lx_ks"] = pkg
    spec = importlib.util.spec_from_file_location(
        "_lx_ks.key_suite", INTEG / "key_suite.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_lx_ks.key_suite"] = mod
    spec.loader.exec_module(mod)
    return mod


KS = _load_key_suite()


class TestIdentityConstants:
    """两套身份常量（A 类：App 级，可内置）结构完整。"""

    def test_kid_formats(self):
        for kid in (KS.MAIN_DEVICE_KEY_ID, KS.LIVIS_DEVICE_KEY_ID):
            assert len(kid) == 32 and all(c in "0123456789abcdef" for c in kid), kid

    def test_kids_distinct(self):
        assert KS.MAIN_DEVICE_KEY_ID != KS.LIVIS_DEVICE_KEY_ID

    def test_private_keys_load_rsa2048(self):
        for b64key in (KS.MAIN_RSA_PRIVATE_DER_B64,
                       KS.LIVIS_RSA_PRIVATE_DER_B64):
            raw = base64.b64decode(b64key)
            assert len(raw) == 1218, f"DER 长度异常: {len(raw)}"
            from cryptography.hazmat.primitives.serialization import (
                load_der_private_key,)
            pk = load_der_private_key(raw, password=None)
            assert isinstance(pk, RSAPrivateKey)
            assert pk.key_size == 2048

    def test_app_type_routing(self):
        assert KS._kid_of("lixiang") == KS.MAIN_DEVICE_KEY_ID
        assert KS._kid_of("livis") == KS.LIVIS_DEVICE_KEY_ID
        with pytest.raises(KS.IdentityDeriveError):
            KS._kid_of("unknown-app")
        with pytest.raises(KS.IdentityDeriveError):
            KS._load_private("unknown-app")


class TestDataToSign:
    """data_to_sign = requestId:deviceId:deviceKeyId:nonce:timestamp（§60.1）。"""

    def test_join_format(self):
        got = KS.build_data_to_sign("R1", "D1", "K1", "N1", "T1")
        assert got == "R1:D1:K1:N1:T1"
        assert got.count(":") == 4


class TestBuildKeySuiteRequest:
    """请求组装：body 字母序 + RSA 签名 + x-chj 11 段 HMAC。"""

    XDEV = "aabbccdd00112233445566778899aabb"
    BOOT = "0" * 64 + "1" * 64   # 128 hex → [:32] 用于第 3 段

    @pytest.fixture(scope="class")
    def built(self):
        from cryptography.hazmat.primitives.serialization import (
            load_der_private_key,)
        pk = load_der_private_key(
            base64.b64decode(KS.MAIN_RSA_PRIVATE_DER_B64), password=None)
        return pk, KS.build_key_suite_request(
            self.XDEV, KS.MAIN_DEVICE_KEY_ID, pk, "BEARER-TOK",
            "req1", "nonce1", "1700000000000", self.BOOT)

    def test_body_gson_alphabetical(self, built):
        _, (body, _h) = built
        j = json.loads(body.decode())
        assert list(j.keys()) == sorted(j.keys()), "body 必须按字母序（Gson）"
        assert j["deviceId"] == self.XDEV
        assert j["deviceKeyId"] == KS.MAIN_DEVICE_KEY_ID
        assert j["requestId"] == "req1"
        assert j["nonce"] == "nonce1"
        assert j["timestamp"] == "1700000000000"

    def test_body_rsa_signature_verifies(self, built):
        pk, (body, _h) = built
        j = json.loads(body.decode())
        data_to_sign = ":".join(
            [j["requestId"], j["deviceId"], j["deviceKeyId"],
             j["nonce"], j["timestamp"]])
        assert data_to_sign == KS.build_data_to_sign(
            "req1", self.XDEV, KS.MAIN_DEVICE_KEY_ID, "nonce1", "1700000000000")
        pub = pk.public_key()
        pub.verify(base64.b64decode(j["sign"]), data_to_sign.encode(),
                   padding.PKCS1v15(), hashes.SHA256())

    def test_headers(self, built):
        _pk, (body, h) = built
        assert h["X-CHJ-Deviceid"] == self.XDEV
        assert h["X-CHJ-Key"] == self.BOOT[:32]
        assert h["X-CHJ-Nonce"] == "NONCE1"          # 头用大写
        assert h["Authorization"] == "Bearer BEARER-TOK"
        md5b = base64.b64encode(hashlib.md5(body).digest()).decode()
        assert h["Content-MD5"] == md5b

    def test_x_chj_sign_11_segments(self, built):
        _pk, (body, h) = built
        md5b = h["Content-MD5"]
        expect_src = "\n".join([
            "prod", KS.KEY_SUITE_VER, self.BOOT[:32], self.XDEV, "POST",
            "*/*", "zh-Hans-CN", md5b, "application/json",
            "1700000000000", "NONCE1" + "1700000000000",
        ])
        expect = hmod.new(bytes.fromhex(self.BOOT),
                          (expect_src + "\n").encode(),
                          hashlib.sha256).hexdigest()
        assert h["X-CHJ-Sign"] == expect
        assert len(h["X-CHJ-Sign"]) == 64   # hex 输出（实测配方）


class TestFormatDK:
    """formatDK：RSA 解 tempAesKey → AES-CTR 解 hmacKey → 32B hac。"""

    @staticmethod
    def _priv():
        from cryptography.hazmat.primitives.serialization import (
            load_der_private_key,)
        return load_der_private_key(
            base64.b64decode(KS.LIVIS_RSA_PRIVATE_DER_B64), password=None)

    def test_roundtrip(self):
        pk = self._priv()
        rd = b"\x11" * 32                    # 会话密钥（服务器用公钥加密）
        iv = b"\x22" * 16
        plain_hac = b"\x33" * 32              # 目标 hac_key

        temp_aes_key = base64.b64encode(
            pk.public_key().encrypt(rd, padding.PKCS1v15())).decode().rstrip("=")
        temp_iv = base64.b64encode(iv).decode().rstrip("=")
        enc = Cipher(algorithms.AES(rd), modes.CTR(iv)).encryptor()
        hmac_key = base64.b64encode(
            enc.update(plain_hac) + enc.finalize()).decode().rstrip("=")

        got = KS.format_dk(temp_aes_key, temp_iv, hmac_key, pk)
        assert got == plain_hac
        assert len(got) == 32

    def test_bad_length_raises(self):
        pk = self._priv()
        rd = b"\x11" * 32
        iv = b"\x22" * 16
        temp_aes_key = base64.b64encode(
            pk.public_key().encrypt(rd, padding.PKCS1v15())).decode()
        temp_iv = base64.b64encode(iv).decode()
        hmac_key = base64.b64encode(b"\x33" * 16).decode()   # 16B → 长度错
        with pytest.raises(KS.IdentityDeriveError):
            KS.format_dk(temp_aes_key, temp_iv, hmac_key, pk)
