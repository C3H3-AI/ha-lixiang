"""Li Auto x-chj-sign 签名器.

签名算法（100% 逆向破解，端到端验证）:
    data = "\n".join([env, appVersion, keyId, deviceId, method, accept,
                      contentLang, contentMD5, contentType, timestamp, nonce])
    sign = base64(HMAC-SHA256(hacKey, data))

重要（iOS 实证确认）:
- HMAC 的 key 必须是 hac_key 的【原始字节】。
  实测：用原始 32 字节 → 服务器接受；用 base64 文本 .encode() → "请求签名错误"。
- hac_key 在 iOS 上从 CCHmac 捕获为原始 32 字节（hex 表示）。
- 签名 data 的 11 个参数用 '\n' 拼接后【末尾再补一个 '\n'】（iOS 实证）。

hac_key 传入支持三种形式（自动识别）:
  - 直接传原始字节 (bytes)
  - 传 hex 字符串 (64位十六进制)
  - 传 base64 字符串
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import time
import uuid

from .const import (
    DEFAULT_ACCEPT,
    DEFAULT_CONTENT_LANG,
    DEFAULT_CONTENT_TYPE,
    EMPTY_MD5,
    ENV,
    SIGN_SEP,
)


def normalize_hac_key(hac_key: str | bytes) -> bytes:
    """把 hac_key 归一化为原始字节（HMAC 真正使用的 key）"""
    if isinstance(hac_key, bytes):
        return hac_key
    s = hac_key.strip()
    # 若已是纯 hex(32字节=64 hex)，则 hex 解码
    if re.fullmatch(r"[0-9a-fA-F]{64}", s):
        return bytes.fromhex(s)
    # 尝试 base64 解码（base64 解码后是 32 字节）
    try:
        dec = base64.b64decode(s)
        if len(dec) == 32:
            return dec
    except Exception:
        pass
    # 兜底：当作原始 ascii 字节
    return s.encode("utf-8")


class LiCarSigner:
    """理想汽车 API 签名器"""

    def __init__(
        self,
        hac_key: str | bytes,    # x-chj-sign 的 HMAC 密钥（原始字节 / hex / base64）
        key_id: str,             # x-chj-key
        device_id: str,          # x-chj-deviceid
        app_version: str = "8.25.4-10463",
    ) -> None:
        self._hac_key = normalize_hac_key(hac_key)
        self._key_id = key_id
        self._device_id = device_id
        self._app_version = app_version

    @property
    def app_version(self) -> str:
        return self._app_version

    @staticmethod
    def content_md5(body: str | bytes) -> str:
        """Content-MD5 = base64(MD5(body))，空 body 返回固定常量"""
        if not body:
            return EMPTY_MD5
        if isinstance(body, str):
            body = body.encode("utf-8")
        return base64.b64encode(hashlib.md5(body).digest()).decode()

    def _string_to_sign(
        self,
        method: str,
        content_md5: str,
        timestamp: str,
        nonce: str,
    ) -> str:
        """11 个参数用 '\n' 拼接，末尾再补一个 '\n'（iOS 实证：12 段，末段空）"""
        parts = [
            ENV,                      # 1  x-chj-env
            self._app_version,        # 2  x-chj-app-version
            self._key_id,             # 3  x-chj-key
            self._device_id,          # 4  x-chj-deviceid
            method.upper(),           # 5  method
            DEFAULT_ACCEPT,           # 6  accept
            DEFAULT_CONTENT_LANG,     # 7  content-language
            content_md5,              # 8  content-md5
            DEFAULT_CONTENT_TYPE,     # 9  content-type
            timestamp,                # 10 x-chj-timestamp
            nonce,                    # 11 x-chj-nonce
        ]
        return SIGN_SEP.join(parts) + SIGN_SEP  # iOS: 末尾补 \n

    def sign_request(
        self,
        method: str,
        body: str = "",
        timestamp: str | None = None,
        nonce: str | None = None,
    ) -> dict:
        """生成签名，返回 (sign, timestamp, nonce, content_md5)"""
        ts = timestamp or str(int(time.time() * 1000))
        nc = nonce or str(uuid.uuid4())
        md5 = self.content_md5(body)
        data = self._string_to_sign(method, md5, ts, nc)
        # 关键：HMAC key 用 hac_key 的【原始字节】（实测服务器只接受原始字节）
        sig = base64.b64encode(
            hmac.new(
                self._hac_key,        # 已归一化为 bytes
                data.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode()
        return {"sign": sig, "timestamp": ts, "nonce": nc, "content_md5": md5}

    def build_headers(self, method: str, body: str = "") -> dict:
        """生成带签名的请求头

        注意：理想服务器对 header 名大小写敏感（实证 Content-MD5 需此大小写），
        用 iOS app 实际发送的大小写命名。
        """
        r = self.sign_request(method, body)
        return {
            "X-CHJ-Env": ENV,
            "X-CHJ-APP-Version": self._app_version,
            "X-CHJ-Key": self._key_id,
            "X-CHJ-Deviceid": self._device_id,
            "X-CHJ-Timestamp": r["timestamp"],
            "X-CHJ-Nonce": r["nonce"],
            "X-CHJ-Sign": r["sign"],
            "Content-MD5": r["content_md5"],
            "Content-Type": DEFAULT_CONTENT_TYPE,
            "Content-Language": DEFAULT_CONTENT_LANG,
            "Accept": DEFAULT_ACCEPT,
        }
