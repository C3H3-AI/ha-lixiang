"""理想汽车集成 · 签名身份派生（keySuite → formatDK）

2026-10-10 Phase A 实测定案（v2_identity_chain / v4c_store_xdev / v4d_fresh_sim）：
  xdev、hac_key、key_id 是【每设备运行时身份】：
    · xdev    = identity store 的登录 device_id（config_flow 直接复用）
    · hac_key = 服务端下发 hmacKey，经 RSA 解密 + AES-CTR 派生
    · key_id  = 服务端按 (KID, xdev) 下发的 keyId（取响应 keyId 字段）
  三条实测结论（bootstrap 无鸡生蛋）：
    1. keySuite 的 x-chj 引导签名用【随机 hac】即可通过（服务端不校验）
    2. 派生对 (KID, xdev) 确定性（同参重派结果一致）
    3. 派生身份调业务接口（任务大师/travel）全 code:0

身份选择（config 表单 app_type）：
    lixiang → 主 App KID      + rsa_private_0x1e821.der
    livis   → 理想同学 KID    + rsa_private_livis_0x70818b.der
两把私钥均从官方 APK/so 【静态提取】（纯静态逆向），是 App 级常量——
等同用户手机上每个安装都内置的东西，不是任何用户的私有凭据。
（push 前已向维护者展示 diff 确认）

本模块只做 HTTP + 密码学运算，同步阻塞 —— HA 内必须经 executor 调用。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets as _pysecrets
import time
import urllib.error
import urllib.request
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_private_key

from .const import API_APP, APP_LIVIS, APP_LIXIANG, EP_KEY_SUITE_DDES, LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)

# 签名版本段（2026-10-10 实测通过值，与 li_api.SIGN_APP_VERSION 同源）
KEY_SUITE_VER = "8.25.4-10463"

# ---------- A 类常量：KID（App 内 getPriId 硬编码） ----------
MAIN_DEVICE_KEY_ID = "020026d02bf87a0a153144000075c05e"   # 理想汽车 App
LIVIS_DEVICE_KEY_ID = "02003dbe871b110a15088600003ddfea"  # 理想同学

# ---------- A 类常量：RSA 私钥（libfOpenGLUtils.so 静态提取，base64(DER)） ----------
MAIN_RSA_PRIVATE_DER_B64 = (
    (
    "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCMRBXH3xiTKCLvjxvSgnaGdDWN1QgS/OR6C4sl"
    "AuYfVUuvEyUZUnQS7PPRr5K8/Vs8DFvMrL13huAAFrlioDeB9j7PMLUwtw5LZxx4FUBiTYMQgUWrxB19kdd1MbgJ"
    "vACymTBuumFjBHiOHCRofDZ//VNrrSWezoqnWHNW4SINvbT2bO1qeXHp+UasgaKL6uRL/aufb4wsSiZiE7sRwQWl"
    "PWAMGncTPMjeiriNvfYRNbXhvE+qghucPmuSlg04cB7ZX7kSbwj32C9tllCEILAKK0RT3QKB+C86o4xYbU6dU098"
    "+fi04t9Tg6SIkuOwDOhHXhZKlFZNtI2SZqMbTIJJAgMBAAECggEAGMwIlbcpHwrfcj54irSpw4dT2Gkq7kBrG/Bi"
    "fv6ONEfeA2t9CYb8IkRlrlI9vM+Fi44bxIldTX44p4tc5sSwS3d/Dx3rSltyWX43GDuZkEdnvkk8Set30zUvQ/aw"
    "NHhaHzjZyRmGEf0+WtE61oXvFJ1yW/zWQ8b72C3Y5ikS3h7Cgp1y0XJE1GRgTWvguFftz/QVwDpJR6CwOXDoJNoB"
    "7tyJH9DwIF4Ta00VzB21DTd0n1Gc1sfz8iG5GC8amWfNsql1Q/wOr+o5sBnVrErj6otnHEiUGJEcYXV7icztTGK5"
    "2U3t0lzd4ALM/9sz9XsiEt6UgKIL4pW3xAN4NRoaCQKBgQDHbhORlFzsGCgALSGNWsCptDCHqim8g8PEGAMprCyJ"
    "WH5B5xBWMoZslPbPIlx0MsnbS9C6wD/7bFqV2jhUUbHrHHEcQl/Mrzvppa15AReoEKOXfThg5pjGgG7lM4MH+snP"
    "LpI7qowPAN03aIFYInVGJ1vohKJCB//je1LADY7+0wKBgQC0DbgeCYap/2Vu7+HekRcAkot6kOncKpSd5oVf6G1Q"
    "k09FHRVxUjw4dknHXZqqPT6bBX98g0ZwvvHFrkk+kZPXrWU5N8qXc2lffjWEyHKC1sQ5jOUNwwef0j+tvpoiA/py"
    "6mfB+72kPqkk0FfQNhHJrRjGQB9R0Rf/pn7H3Qjg8wKBgQCh6/sReW+U9ewMcJhMaAIEB9xbWkr219ksLv7qZ/Pl"
    "NCeXJJ+8DNvd73kRJuoAIniIiF8aMhwA7LID96FCvO4DYh1of2+/BgxUIYPeuodVmuToi/AppTEoAoGHsTJTWUlf"
    "4YUz0r5TNDVo1n4mbBvh8PULrhz8Ffiq36eJbbjLpwKBgF2yJfW7j1A3j1lDi45+gjHSELMfZhMkNWJV62IVWY1s"
    "mvukPtxRpvTa2Vnd4/ZjGIkjO0xYI/fX5YixQXxF1WGO4fX8inh1nogK7V7D0JM1n7czEp8utnD8wBZx8VNyLopO"
    "YOAZWH53/R0jLg8zk94XLaU9CQ9Sd+KZibAH3e7xAoGBAJ5EPf87Vbs5gC8DpVo0dOn1obATw1vEJ9Lii3uAn1gJ"
    "GWpyhk4zX154GLTYvI/md8z8Cos2UlMtUjzBqWroQ3VPcCufCmA2/5zj3Of0vgy418F3nLbsG+0kOvZeWbV2g/zu"
    "ofVHD1Yt/Bp1Kwxd2yBR7sljRuhZlV1CrwwG6CFb"
)
)
LIVIS_RSA_PRIVATE_DER_B64 = (
    (
    "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCk2YXvhCI6oVc9nN9R9ay5HaNJJINASSHXvgwc"
    "eBIRSkV/Z/kY4KsiyMNHUAwIjs8zG23Bpzt+QoKbEz6M9xtwofXjgpm5iLcdeCkvcM7ybF3mrDe4fpWFXTjkyIgh"
    "Tv7drLNgkJ5Iav1ZNxLicYw0dfx8py+glF6EGb1pjEmRDWvel9yZPReVwcYd2j0H6OcayCEtF1ztrEUSoOL0Z1aW"
    "Z16y6MueuulNHbeXy2EIYs4GA1gANHDvhNoAfNzLHYRk8dvJ9tRAzBQwasQBVDm6IHLessIDafNz1RDzz3y3kowj"
    "bx8LlJ2JCw17DgbAOKQ0PkUXRJVYRIAIK0hYRBW/AgMBAAECggEAdgTBDZvUgZMWiSaw/tVaxeDBENFSIgj5cKI/"
    "u3X+wWAh5zfBrxzRiIKgw4I8SzgqgNVHO5gFULw/EtSxOGyEuZtKFYpfkeOd7TwkiDFEB2yrwURUVAJT+3mlDK3A"
    "P9B1SLCmbyC6IPBv1ppGK9XM4ZYCoB91SopOLFbdMx5bYLtJZ0Ax7BeKBHuvFi1h6EFkxp5y5AQjshLqgfafPl9j"
    "I8BxNPUqNsjwMTKFXJinPQG5+WGkA2umDGMlLTl+Vuvd7UxgLOSCPM2fanJK/8NZKB2gyysLcgPO92fpB7AyRDMm"
    "bpuoObO3j0nLxl5fMAd1m46CXLmsiYn3M1AP8Yt4GQKBgQDqU9aeybB2bKkzrK3nqymTG3UI6iN9A9i79uH20UKh"
    "YF3lLiDMPc8jviEDZpHG4Zk/alNbbRJrltUfM2wIgIV5Zwes3qLsSbuHtmN2FeWJKbZjsiFKDRnNeaozMXJ5Fena"
    "VK0YVbBK/rQNAl+pSRaVjErScUii6usL7oxNnqT3AwKBgQC0GKmFuNfw5ydh7oFYoe41LNbOEL/3QP8yzuIoUb81"
    "Z23NwURLaqjUXxVJWR2DtN4F/rQTnbFINkzjKJs9Rw083Fi1CXQGr/RgivokPUYOx4ohojGypLVmPUNeIpquN8Bq"
    "Kz1+6K255FUpqjeeV84uTrViReOgkQIsAtcDZxEblQKBgQDE43DftqP4vVBmRN9SWvTx0A5EUUdEUakYNlai5i1Q"
    "HwKGAH46XmzfoW9nxhUSwJfdOt+TYFAr6m5kavaJJkQAP9upGuBWHZXecBeeLsPQviWsGw3xhJR7m5CwtwlySEFX"
    "2/IdElKwkNaEX8w1F15MhbaQn/LiQPUB74wf4/7ENQKBgCBmJ2klHcP68bzOeXqGdyId1O7xWHeUu9RaH5l9S1bC"
    "KqDPWgfvQjwiduPhIkwlZ6PQdHjq74+8JQzgqzzU4W7HfTXkY3kogmAz4FhQpZ/XCeSPFz26H+AquUngE8+vu+/d"
    "o4yHM2mzyBZcxvC3fyIZiswJIrAqJifgwumbyxoZAoGBAJ2EJIUevSSyhNepAa3ABopulEnVqeIaKYED4zGSBk9u"
    "hs+1c3Er74SqcKwGGyM9F8Z9OhSVSS+pdHKNO2ky+tgOlL7Y7pNnUjunhE4BFOffiRYwhVFZroPxCUHx8tQ0rGDG"
    "jz1KZRi09ZW9duseiQpnGkwV2jQH/xtuMrm8jWAh"
)
)


class IdentityDeriveError(RuntimeError):
    """签名身份派生失败（keySuite 非 0 / 网络错误 / 响应缺字段）。"""


def _b64decode(s: str) -> bytes:
    """容错 base64 解码（自动补 `=`）。"""
    return base64.b64decode(str(s) + "=" * (-len(str(s)) % 4))


def _load_private(app_type: str):
    """按身份加载 RSA 私钥。"""
    if app_type == APP_LIVIS:
        return load_der_private_key(
            base64.b64decode(LIVIS_RSA_PRIVATE_DER_B64), password=None)
    if app_type == APP_LIXIANG:
        return load_der_private_key(
            base64.b64decode(MAIN_RSA_PRIVATE_DER_B64), password=None)
    raise IdentityDeriveError(f"未知的 app_type: {app_type!r}")


def _kid_of(app_type: str) -> str:
    if app_type == APP_LIVIS:
        return LIVIS_DEVICE_KEY_ID
    if app_type == APP_LIXIANG:
        return MAIN_DEVICE_KEY_ID
    raise IdentityDeriveError(f"未知的 app_type: {app_type!r}")


def build_data_to_sign(request_id: str, xdev: str, kid: str,
                       nonce: str, ts: str) -> str:
    """keySuite body RSA 签名原文：requestId:deviceId:deviceKeyId:nonce:timestamp。"""
    return ":".join([request_id, xdev, kid, nonce, ts])


def build_key_suite_request(
    xdev: str,
    kid: str,
    priv,
    bearer: str,
    request_id: str,
    nonce: str,
    ts: str,
    boot_hac_hex: str,
    ver: str = KEY_SUITE_VER,
) -> tuple[bytes, dict[str, str]]:
    """纯函数：组装 keySuite 请求（body + headers），不发网络。

    boot_hac_hex：引导签名用的 hac（32B hex）。实测随机值即可通过
    （全新装机没有 hac —— 服务端不校验该引导签名）。
    """
    data_to_sign = build_data_to_sign(request_id, xdev, kid, nonce, ts)
    sign = base64.b64encode(
        priv.sign(data_to_sign.encode(), padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    # body 按 Gson 字母序：deviceId, deviceKeyId, nonce, requestId, sign, timestamp
    body = (
        '{"deviceId":"%s","deviceKeyId":"%s","nonce":"%s",'
        '"requestId":"%s","sign":"%s","timestamp":"%s"}'
        % (xdev, kid, nonce, request_id, sign, ts)
    ).encode()
    md5b = base64.b64encode(hashlib.md5(body).digest()).decode()
    # x-chj 11 段 HMAC（\n 拼接 + 末尾 \n，key = 引导 hac 原始 32 字节，
    # 第 3 段/头 X-CHJ-Key = hac 前 32 hex —— 与 keysuite 实测配方一致）
    dtsx = "\n".join([
        "prod", ver, boot_hac_hex[:32], xdev, "POST", "*/*", "zh-Hans-CN",
        md5b, "application/json", ts, nonce.upper() + ts,
    ])
    xsign = hmac.new(
        bytes.fromhex(boot_hac_hex), (dtsx + "\n").encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "Authorization": "Bearer " + bearer,
        "Content-Type": "application/json",
        "Content-MD5": md5b,
        "Accept": "*/*",
        "Content-Language": "zh-Hans-CN",
        "X-CHJ-Timestamp": ts,
        "X-CHJ-Nonce": nonce.upper(),
        "X-CHJ-Sign": xsign,
        "X-CHJ-Deviceid": xdev,
        "X-CHJ-Key": boot_hac_hex[:32],
        "X-CHJ-APP-Version": ver,
        "X-CHJ-Env": "prod",
        "X-CHJ-Version": ver,
    }
    return body, headers


def format_dk(temp_aes_key_b64: str, temp_iv_b64: str,
              hmac_key_b64: str, priv) -> bytes:
    """纯函数：keySuite 响应 → 32B hac_key。

    RD   = RSA-PKCS1v15 解密 tempAesKey
    hac  = AES-256-CTR(key=RD, iv=tempIv).decrypt(hmacKey)
    （2026-10-10 v2/v4 实测配方，与 SO 逆向 §60.1 一致）
    """
    ta = _b64decode(temp_aes_key_b64)
    ti = _b64decode(temp_iv_b64)
    hk = _b64decode(hmac_key_b64)
    rd = priv.decrypt(ta, padding.PKCS1v15())
    dec = Cipher(algorithms.AES(rd), modes.CTR(ti)).decryptor()
    hac = dec.update(hk) + dec.finalize()
    if len(hac) != 32:
        raise IdentityDeriveError(f"formatDK 派生长度异常: {len(hac)} 字节")
    return hac


def derive_identity(app_type: str, xdev: str, bearer: str,
                    timeout: int = 20) -> tuple[str, str]:
    """现场派生签名身份 → (hac_key_hex, key_id)。

    流程：随机 hac 引导签 keySuite → 响应 → formatDK 派生 hac → 取响应 keyId。
    同步阻塞，必须在 executor 线程中调用。
    失败抛 IdentityDeriveError（不回退、不静默 —— 由 config_flow abort 呈现）。
    """
    kid = _kid_of(app_type)
    priv = _load_private(app_type)
    ts = str(int(time.time() * 1000))
    request_id = uuid.uuid4().hex
    nonce = uuid.uuid4().hex
    boot_hac = _pysecrets.token_hex(32)   # 引导签名（V4d：随机值即通过）

    body, headers = build_key_suite_request(
        xdev, kid, priv, bearer, request_id, nonce, ts, boot_hac)
    req = urllib.request.Request(
        API_APP + EP_KEY_SUITE_DDES, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as err:
        raise IdentityDeriveError(
            f"keySuite HTTP {err.code}: {err.read().decode()[:200]}") from err
    except urllib.error.URLError as err:
        raise IdentityDeriveError(f"keySuite 网络错误: {err.reason}") from err

    try:
        j = json.loads(raw)
    except json.JSONDecodeError as err:
        raise IdentityDeriveError(f"keySuite 响应非 JSON: {raw[:160]}") from err
    if j.get("code") != 0:
        raise IdentityDeriveError(
            f"keySuite code={j.get('code')} msg={j.get('msg') or j.get('message') or ''}")

    dd = j.get("data") or {}
    ks = dd.get("keySuite") or {}
    sec = ks.get("keySecret") or {}
    for field, value in (("tempAesKey", dd.get("tempAesKey")),
                         ("tempIv", dd.get("tempIv")),
                         ("hmacKey", sec.get("hmacKey"))):
        if not value:
            raise IdentityDeriveError(f"keySuite 响应缺少字段: {field}")

    hac = format_dk(dd["tempAesKey"], dd["tempIv"], sec["hmacKey"], priv)
    key_id = ks.get("keyId") or kid    # 实测响应必带 keyId（服务端按设备下发）
    if not ks.get("keyId"):
        _LOGGER.warning("keySuite 响应无 keyId，退回 KID（可能被服务端拒签）")

    _LOGGER.info(
        "签名身份派生成功: app_type=%s xdev=%s... key_id=%s... hac=%s...",
        app_type, str(xdev)[:12], str(key_id)[:12], hac.hex()[:8])
    return hac.hex(), key_id


__all__ = [
    "IdentityDeriveError",
    "MAIN_DEVICE_KEY_ID",
    "LIVIS_DEVICE_KEY_ID",
    "build_data_to_sign",
    "build_key_suite_request",
    "format_dk",
    "derive_identity",
]
