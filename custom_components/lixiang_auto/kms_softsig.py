"""KMS 软签（软件 Ed25519）—— 换取 iot2 JWT。

★ 2026-10-17 落地自队友的逆向成果 `docs/方向A_KMS软签打通_20261017.md`。

## 它解决什么

理想 App 的**长连接（LiMesh / NDN / GFM）**需要一枚 `iot2 JWT`，
官方是在手机本地用 **SE 安全区**里的私钥签名换来的。我们没有 SE，
但**出厂兜底密钥**就在 App 的 SO 里（明文静态）→ **软件 Ed25519 顶替**即可，
服务端照收（实测 `code:0` + 30 天有效期 JWT）。

## 三个曾被读错的参数（这是 144014 的真因）

| 项 | 之前所有人试的 | ✅ 服务端只认 |
|---|---|---|
| `verifyType` | `"Veh"` | **`"MOBILE"`** |
| `verifyId` | VIN | **deviceId（`x-chj-deviceid`）** |
| `sign` | 被文档误读成「RSA 128 字节」 | **Ed25519，64 字节** |

配对正确 → `code:0`；否则报 144014（签名错）或 144001（参数组合非法）。

## 错误码语义（实测确立，排查时直接看）

```
0      = 成功，data.jwt 返回
144001 = args error（参数组合非法，例如 MOBILE + VIN）
144011 = device key not found（verifyKey 在该 verifyId 下没注册）
144014 = sign verification error（keyId 已注册，但 key/消息不对）
```

→ **144011 与 144014 的区分本身就是诊断工具**：前者是 keyId 没注册，
后者是签名本身不对。

## 签名消息的构成

```
message = f"{requestId}:{verifyId}:{nonce}:{timestamp}"
```
（顺序与分隔符均取自 smali `Ed25519Helper.java`，不能改）

签名用**出厂兜底密钥 A**（`KEY_A_ID` / `KEY_A_B64`）的 seed 部分，
产物为 Ed25519 **detached** 签名，**base64 编码**。

## 为什么不用 `cryptography`

本集成 `manifest.json` 的 `requirements` 是空的（不引入额外依赖），
而 HA 环境**不保证**装了 `cryptography`。因此这里内置一份纯 Python 的
RFC 8032 Ed25519（约 50 行），并用 `cryptography` 做过逐位交叉验证：
pubkey 与 detached 签名**完全一致**（见 `tests/test_kms_softsig.py`）。
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import Any

#: 签名兑换端点（App 侧同款）
KMS_JWT_EP = "/bcs-kms-jwt/jwt/iot2/v1-0/"

#: 长连接接入点查询端点（拿到 JWT 后打这个，可验证 JWT 是否真被网关接受）
GFM_FACE_EP = "/li-ndn-gfm/gfm-server/v2-0/nfd-face"

#: 长连接网关域名（按 region 不同，这里是文档实测到的那个）
GFM_HOST = "https://api-app-cnhz2n01-b.lixiang.com"

#: 出厂兜底密钥 A —— 明文存在于旧版 `libfOpenGLUtils.so`（VA 0x1d29c）
#:   64 字节 = seed(32) ‖ pubkey(32)；签名只用前 32 字节（seed）。
KEY_A_ID = "23002f4806a1000a15002200004b558e"
KEY_A_B64 = (
    "h5Gu/FJfKrn0kqw/IVsaifTC4nzCSWTX0FXwrCBRg1+77VThhs9NxU0trpW8fXL8"
    "9Y1F8VrLtLmLJ+zXaudjgw=="
)


# --------------------------------------------------------------------------
# 纯 Python Ed25519（RFC 8032）—— 不依赖 cryptography
# --------------------------------------------------------------------------
_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_D = -121665 * _inv(121666) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_B_Y = 4 * _inv(5)
_B_X = _xrecover(_B_Y)
_B = (_B_X % _Q, _B_Y % _Q, 1, (_B_X * _B_Y) % _Q)
_IDENTITY = (0, 1, 1, 0)


def _edwards_add(p: tuple[int, int, int, int], q: tuple[int, int, int, int]):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _Q
    b = (y1 + x1) * (y2 + x2) % _Q
    c = t1 * 2 * _D * t2 % _Q
    dd = z1 * 2 * z2 % _Q
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q)


def _edwards_double(p: tuple[int, int, int, int]):
    x1, y1, z1, _t = p
    a = x1 * x1 % _Q
    b = y1 * y1 % _Q
    c = 2 * z1 * z1 % _Q
    h = a + b
    e = (h - (x1 + y1) * (x1 + y1)) % _Q
    g = a - b
    f = c + g
    return (e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q)


def _scalarmult(p: tuple[int, int, int, int], e: int):
    q = _IDENTITY
    while e > 0:
        if e & 1:
            q = _edwards_add(q, p)
        p = _edwards_double(p)
        e >>= 1
    return q


def _encode_point(p: tuple[int, int, int, int]) -> bytes:
    x, y, z, _t = p
    zi = _inv(z)
    x = x * zi % _Q
    y = y * zi % _Q
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decode_point(data: bytes) -> tuple[int, int, int, int]:
    """把 32 字节曲线点编码解成扩展坐标（验签自测用）。"""
    value = int.from_bytes(data, "little")
    y = value & ((1 << 255) - 1)
    x = _xrecover(y)
    if x & 1 != value >> 255:
        x = _Q - x
    return (x, y, 1, x * y % _Q)


def _clamp(h: bytes) -> int:
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


def ed25519_pubkey(seed: bytes) -> bytes:
    """由 32 字节 seed 推出公钥（用于自检 seed‖pub 是否自洽）。"""
    return _encode_point(_scalarmult(_B, _clamp(_sha512(seed))))


def ed25519_sign(message: bytes, seed: bytes) -> bytes:
    """Ed25519 detached 签名（RFC 8032）。"""
    h = _sha512(seed)
    a = _clamp(h)
    r = int.from_bytes(_sha512(h[32:] + message), "little") % _L
    rr = _encode_point(_scalarmult(_B, r))
    s = (r + int.from_bytes(_sha512(rr + ed25519_pubkey(seed) + message), "little") * a) % _L
    return rr + int.to_bytes(s, 32, "little")


def _factory_seed() -> bytes:
    raw = base64.b64decode(KEY_A_B64)
    if len(raw) != 64:
        raise ValueError(f"内置密钥长度异常: {len(raw)}（应为 64）")
    return raw[:32]


def soft_sign(message: str) -> str:
    """出厂兜底密钥的软件 Ed25519 签名 → base64（detached，64 字节）。"""
    return base64.b64encode(ed25519_sign(message.encode(), _factory_seed())).decode()


def verify_seed_consistency() -> bool:
    """自检：内置密钥的 seed 能否推导出它自带的 pubkey（数学自洽性）。"""
    raw = base64.b64decode(KEY_A_B64)
    return ed25519_pubkey(raw[:32]) == raw[32:]


# --------------------------------------------------------------------------
# 换取 JWT
# --------------------------------------------------------------------------
def build_kms_body(device_id: str, request_id: str | None = None,
                   nonce: str | None = None, ts: str | None = None) -> tuple[dict, str]:
    """构造 KMS 请求体与被签名的消息。

    ★ `verifyType` 必须是 `MOBILE`、`verifyId` 必须是 **deviceId**（不是 VIN）
      —— 这正是历史 144014 的真因，别改回去。
    """
    rid = request_id or uuid.uuid4().hex
    nce = nonce or uuid.uuid4().hex
    stamp = ts or str(int(time.time() * 1000))
    message = f"{rid}:{device_id}:{nce}:{stamp}"
    body = {
        "requestId": rid,
        "nonce": nce,
        "verifyType": "MOBILE",
        "timestamp": stamp,
        "sign": soft_sign(message),
        "verifyId": device_id,
        "verifyKey": KEY_A_ID,
    }
    return body, message


def decode_jwt_claims(jwt: str) -> list[tuple[int, str]]:
    """把 JWT 三段解出来（给人看用；不做任何校验）。

    结构：`{"alg":"RS256","vt":"MOBILE"}` . `kms:<exp_ms>:<iat_ms>` . hex 签名
    → `exp - iat = 2_592_000_000 ms = 30 天`
    """
    out: list[tuple[int, str]] = []
    for idx, part in enumerate(jwt.split(".")):
        try:
            raw = base64.b64decode(part + "=" * (-len(part) % 4))
        except Exception:  # noqa: BLE001
            out.append((idx, "decode error"))
            continue
        try:
            out.append((idx, raw.decode()))
        except UnicodeDecodeError:
            out.append((idx, raw.hex()))
    return out


def gfm_face_headers(device_id: str, jwt: str) -> dict[str, str]:
    """长连接网关（GFM）认证头 —— 实测还原，别再猜。

    注意 `x-chj-kms-verify-type` 的值是字面量 **`KMS-JWT`**（不是 `MOBILE`）。
    """
    return {
        "x-chj-env": "prod",
        "x-chj-timestamp": str(int(time.time() * 1000)),
        "x-chj-nonce": uuid.uuid4().hex,
        "x-chj-kms-verify-type": "KMS-JWT",
        "x-chj-kms-verify-id": device_id,
        "x-chj-kms-jwt": jwt,
        "x-chj-deviceid": device_id,
    }


def gfm_face_url(device_id: str, host: str = GFM_HOST) -> str:
    """长连接接入点查询 URL（实测可用 → 返回 NFD 的 tls 接入地址）。"""
    return f"{host}{GFM_FACE_EP}?device_id={device_id}&device_type=MOBILE"


def summarize_jwt(jwt: str) -> dict[str, Any]:
    """把 JWT 摘要成便于展示/诊断的字典（不泄露完整 token）。"""
    info: dict[str, Any] = {"length": len(jwt)}
    parts = jwt.split(".")
    info["segments"] = len(parts)
    if len(parts) >= 2:
        try:
            seg1 = base64.b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode()
            bits = seg1.split(":")
            if len(bits) == 3 and bits[0] == "kms":
                exp_ms, iat_ms = int(bits[1]), int(bits[2])
                info["expires_at_ms"] = exp_ms
                info["valid_seconds"] = (exp_ms - iat_ms) // 1000
        except Exception:  # noqa: BLE001
            pass
    info["claims"] = [v for _i, v in decode_jwt_claims(jwt)]
    return info
