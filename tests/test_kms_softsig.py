"""★ 2026-10-17：KMS 软签（软件 Ed25519 换长连接 JWT）—— 集成侧回归测试。

背景（队友逆向成果 `docs/方向A_KMS软签打通_20261017.md`）：
    理想 App 的长连接（LiMesh / GFM）需要一枚 `iot2 JWT`，官方在手机本地用
    **SE 安全区**签名换。我们没有 SE，但**出厂兜底密钥**明文存在于 App 的
    `libfOpenGLUtils.so` → 软件 Ed25519 顶替即可，服务端照收。

    历史踩坑（这是 144014 的真因）：`verifyType` 应为 `MOBILE`（不是 `Veh`）、
    `verifyId` 应为 **deviceId**（不是 VIN）、`sign` 是 **Ed25519 64 字节**
    （不是文档里写的「RSA 128 字节」）。

本测试覆盖：
    · 内置密钥的 seed‖pubkey 数学自洽（若 SO 换版导致密钥不再自洽 → 立即告警）
    · 纯 Python Ed25519 与 `cryptography` 逐位一致（保证不依赖第三方库也对）
    · KMS 请求体三个关键字段（MOBILE / deviceId / 出厂 keyId）
    · 签名消息的构成顺序（`requestId:verifyId:nonce:timestamp`）
    · GFM 请求头的 `x-chj-kms-verify-type` 是字面量 `KMS-JWT`（不是 MOBILE）
    · 诊断服务已注册、且**只读**（不建长连接）
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
sys.path.insert(0, str(INTEG))

# RFC 8032 §7.1 测试向量（TEST 1，空消息）—— 防止纯 Python 实现写错
RFC8032_VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "72",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
]


class TestPureEd25519:
    """纯 Python 实现必须符合 RFC 8032（manifest 的 requirements 是空的）。"""

    @pytest.mark.parametrize("seed_hex,msg,pub_hex,sig_hex", RFC8032_VECTORS)
    def test_rfc8032_vectors(self, seed_hex, msg, pub_hex, sig_hex):
        import kms_softsig as K

        seed = bytes.fromhex(seed_hex)
        assert K.ed25519_pubkey(seed).hex() == pub_hex
        assert K.ed25519_sign(bytes.fromhex(msg), seed).hex() == sig_hex


class TestBuiltinKey:
    def test_seed_matches_embedded_pubkey(self):
        """内置密钥的 seed‖pubkey 必须数学自洽（换 SO 版本后要能立刻发现）。"""
        import kms_softsig as K

        raw = base64.b64decode(K.KEY_A_B64)
        assert len(raw) == 64, f"内置密钥应为 64 字节（seed32‖pub32），实为 {len(raw)}"
        assert K.ed25519_pubkey(raw[:32]) == raw[32:], (
            "内置密钥不自洽 —— SO 换版后密钥可能已变，别盲目请求")

    def test_matches_cryptography(self):
        """与 cryptography 交叉验证（该库装了才跑；没装说明 HA 环境也用不了）。"""
        cryptography = pytest.importorskip(
            "cryptography.hazmat.primitives.asymmetric.ed25519")
        from cryptography.hazmat.primitives import serialization

        import kms_softsig as K

        seed = base64.b64decode(K.KEY_A_B64)[:32]
        priv = serialization.load_der_private_key(
            bytes.fromhex("302e020100300506032b657004220420") + seed, password=None)
        msg = b"requestId:deviceId:nonce:1700000000000"
        assert K.ed25519_sign(msg, seed) == priv.sign(msg)


class TestKmsRequest:
    def test_three_critical_fields(self):
        """★ 144014 的真因所在：MOBILE + deviceId + 出厂 keyId。"""
        import kms_softsig as K

        body, _msg = K.build_kms_body("dev-abc-123")
        assert body["verifyType"] == "MOBILE", 'verifyType 必须是 "MOBILE"，不是 "Veh"'
        assert body["verifyId"] == "dev-abc-123", "verifyId 必须是 deviceId，不是 VIN"
        assert body["verifyKey"] == K.KEY_A_ID, "verifyKey 用出厂兜底密钥的 keyId"
        assert body["timestamp"] and body["requestId"] and body["nonce"]

    def test_not_vin_as_verify_id(self):
        """防回归：别把 VIN 当 verifyId（服务端会报 144001 args error）。"""
        import kms_softsig as K

        vin = "LSJA0000000000001"
        body, _msg = K.build_kms_body("dev-1")
        assert body["verifyId"] != vin

    def test_message_layout(self):
        """签名消息顺序取自 smali Ed25519Helper：requestId:verifyId:nonce:timestamp。"""
        import kms_softsig as K

        body, message = K.build_kms_body("dev-1", "RID", "NON", "TS")
        assert message == "RID:dev-1:NON:TS"
        # sign 必须是 64 字节的 base64（Ed25519 detached），不是 RSA 128 字节
        assert len(base64.b64decode(body["sign"])) == 64

    def test_sign_is_verifiable_against_builtin_pubkey(self):
        """用内置 pubkey 验签自测：[S]B == R + [k]A（Ed25519 校验等式）。"""
        import hashlib

        import kms_softsig as K

        raw = base64.b64decode(K.KEY_A_B64)
        seed = raw[:32]
        pub = raw[32:]
        msg = b"abc"
        sig = K.ed25519_sign(msg, seed)
        R = sig[:32]
        S = int.from_bytes(sig[32:], "little")

        a = K._clamp(hashlib.sha512(seed).digest())
        A = K._scalarmult(K._B, a)                      # 公钥点 A = [a]B
        h = hashlib.sha512(sig[:32] + pub + msg).digest()  # H(R‖A‖M)
        lhs = K._scalarmult(K._B, S)                     # [S]B
        rhs = K._edwards_add(
            K._decode_point(R),                          # R
            K._scalarmult(A, int.from_bytes(h, "little")),  # [h]A
        )
        assert K._encode_point(lhs) == K._encode_point(rhs)


class TestGfmHeaders:
    def test_verify_type_literal_is_kms_jwt(self):
        """★ 队友实测：头值是字面量 KMS-JWT，不是 MOBILE（易错点）。"""
        import kms_softsig as K

        h = K.gfm_face_headers("dev-1", "jwt-token")
        assert h["x-chj-kms-verify-type"] == "KMS-JWT"
        assert h["x-chj-kms-verify-id"] == "dev-1"
        assert h["x-chj-kms-jwt"] == "jwt-token"
        assert h["x-chj-env"] == "prod"

    def test_face_url(self):
        import kms_softsig as K

        url = K.gfm_face_url("dev-1")
        assert "/li-ndn-gfm/gfm-server/v2-0/nfd-face" in url
        assert "device_id=dev-1" in url and "device_type=MOBILE" in url


class TestIntegration:
    def test_li_api_has_methods(self):
        src = (INTEG / "li_api.py").read_text(encoding="utf-8")
        assert "def get_iot2_jwt(" in src, "li_api 缺 get_iot2_jwt"
        assert "def probe_gfm_face(" in src, "li_api 缺 probe_gfm_face"
        assert 'KMS_JWT_EP = "/bcs-kms-jwt/jwt/iot2/v1-0/"' in src

    def test_services_registered(self):
        src = (INTEG / "__init__.py").read_text(encoding="utf-8")
        assert 'SERVICE_GET_IOT2_JWT = "get_iot2_jwt"' in src
        assert 'SERVICE_PROBE_GFM = "probe_gfm_face"' in src
        assert "async_register(DOMAIN, SERVICE_GET_IOT2_JWT" in src

    def test_services_yaml(self):
        import yaml

        d = yaml.safe_load((INTEG / "services.yaml").read_text(encoding="utf-8"))
        assert "get_iot2_jwt" in d and "probe_gfm_face" in d

    def test_no_new_requirement(self):
        """不得引入新依赖（manifest requirements 保持为空，纯 Python Ed25519）。"""
        import json

        mf = json.loads((INTEG / "manifest.json").read_text(encoding="utf-8"))
        assert not mf.get("requirements"), (
            f"本模块刻意不依赖 cryptography（requirements 应为空），实为 {mf.get('requirements')}")

    def test_readonly_guard(self):
        """这两个服务必须【只读】：文档里要写明不建连/不发车控。"""
        import yaml

        d = yaml.safe_load((INTEG / "services.yaml").read_text(encoding="utf-8"))
        for name in ("get_iot2_jwt", "probe_gfm_face"):
            desc = d[name]["description"]
            assert "只读" in desc, f"{name} 的描述必须写明「只读」"
            assert ("不建任何长连接" in desc) or ("不建连" in desc), (
                f"{name} 的描述必须写明「不建长连接」")
