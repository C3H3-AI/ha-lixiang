"""理想账号直接登录 — 手机号 + 密码 PAKE 协议复刻 (2026-09-06 实测通过).

协议来源: account.lixiang.com 登录页 JS 逆向 (webpack chunk 130/702, 模块 6702),
抓包验证 data/2026-05-05_licar_captures.json 的 /api/devices → /api/idps → /api/login
→ /api/token 全链。协议为自研 PAKE, 非标准 SRP:

  1. seed = sha256(password) mod 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF61   (createSeed)
  2. POST /api/idps {seed, strategy:PASSWORD, connection:LI_USER}
     → t_login_use {option:"bcrypt$2a$10$", seeded:<账号注册盐32hex>, snonce:"HZ:<32hex>"}
  3. salt     = "$2a$10$" + bcrypt_b64(bytes.fromhex(seeded))          (22 字符)
     ed_priv  = sha256( bcrypt(password, salt) )                      (32 字节 ed25519 种子)
     msg      = sha256( snonce后缀字节 ‖ cnonce字节 )
     proof    = Ed25519.sign(msg, ed_priv).hex()                       (128 hex)
  4. POST /api/login {proof:{cnonce, snonce, proof}}
     → 401(空体)=密码错误; 成功=响应带 location 头(code=HZ.xxx&state=...)
  5. POST /api/token {grant_type:authorization_code, code, code_verifier}
     → access_token(主Bearer) + refresh_token

实测要点 (2026-09-06):
- 无需极验/滑块验证码 (新设备 API 登录路径不触发风控)
- seeded 是账号注册时 createVerifier 固化的盐, 同账号恒定, 与客户端提交的 seed 无关
- 客户端提交的 seed 只作为服务端账号查找键
- access_token 需 PKCE: /api/auth 先注册 code_challenge(S256), login 后 code 换 token

依赖: requests, bcrypt, PyNaCl (nacl) — 已写入 manifest.json requirements。
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
import uuid

import requests

_LOGGER = logging.getLogger(__name__)

try:  # HA 环境由 manifest requirements 安装; 独立脚本可用 pylib/
    import bcrypt as _bcrypt
    import nacl.signing as _nacl_signing
except ImportError:  # pragma: no cover
    _bcrypt = None
    _nacl_signing = None

BASE_ID = "https://id.lixiang.com"
BASE_ACCT = "https://account.lixiang.com"
CLIENT_ID = "2AQClOaegaA7XecMSFx1p"
LOGIN_AUDIENCE = "5iIapSfVJlln0vU0OzUCH9"
LOGIN_SCOPE = "iam:client:type:app openid"
REDIRECT_URI = BASE_ACCT + "/app-auth"
SDK_VERSION = "0.0.0-snapshot-20240614055722"
APP_VERSION = "8.22.0"
DEFAULT_UA = (
    "Mozilla/5.0 (Phone; OpenHarmony 6.1) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36  ArkWeb/6.1.0.117 Mobile m01/8.22.0"
)

# ------------------------------------------------------------------
# 理想同学（Livis）独立 OAuth client —— 2026-10-10 静态逆向 + 实测
#
# 静态来源（理想同学 APK smali, /tmp/livis_dec）：
#   ApiConfig.smali:37  LOGIN_CLIENT_ID = "40amUDKOdqQTaGDONZC1oY"
#   MainApplication     启动时覆写 IDaasConfig.RELEASE_KEY = LOGIN_CLIENT_ID
#                       （IDaasConfig 静态默认 2AQCl... 是死值）
#   jk/a.smali (LoginWebViewConst)
#                       登录 URL "%sapp-auth/livis" + scope "iam:client:type:lisa"
#   audience 与主 App 相同（ApiConfig.LOGIN_AUDIENCE = 5iIapSf...）
#
# 实测（2026-10-10 V5/V6）：
#   · PAKE 登录成功 → 返回 LISA- 前缀独立 token（90 天，非 JWT）
#   · LISA token 可驱动 keySuite 派生（livis KID, code:0）
#   · 派生身份调业务接口 code:0（端到端全通）
#   · 与主 App（2AQCl...）互为独立登录位
# ------------------------------------------------------------------
LIVIS_LOGIN_CLIENT_ID = "40amUDKOdqQTaGDONZC1oY"
LIVIS_LOGIN_SCOPE = "iam:client:type:lisa"
LIVIS_REDIRECT_URI = BASE_ACCT + "/app-auth/livis"

# app_type → (client_id, scope, redirect_uri)；audience 两分支相同
APP_LOGIN_PARAMS = {
    "lixiang": (CLIENT_ID, LOGIN_SCOPE, REDIRECT_URI),
    "livis": (LIVIS_LOGIN_CLIENT_ID, LIVIS_LOGIN_SCOPE, LIVIS_REDIRECT_URI),
}

# createSeed 的模数 (登录页 JS: new BigNumber("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF61", 16))
SEED_MOD = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF61
# bcrypt 自定义 base64 字母表 (登录页 JS chunk 702, bcryptjs)
B64_BCRYPT = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


class LoginError(RuntimeError):
    """理想账号登录失败"""

    def __init__(self, step: str, status: int = 0, detail: str = "") -> None:
        self.step = step
        self.status = status
        self.detail = detail
        super().__init__(f"[{step}] HTTP {status} {detail}" if status else f"[{step}] {detail}")


class CredentialRejected(LoginError):
    """账号/密码被服务端拒绝 —— 需要【用户】重新认证。

    ★ 与网络抖动、风控（短信）区分开：只有这一类才应该让 HA 弹出
      「需要重新认证」（ConfigEntryAuthFailed），否则会把网络问题
      也变成要用户改密码的提示。
    实测：401 空体 = 密码错误（见 login() 内注释）。
    """


def is_credential_rejection(err: BaseException) -> bool:
    """判断登录失败是否属于「账号/密码被拒」。

    注意：**不**把风控（require=SMS_CODE / 300）算进来 —— 那是「设备未受信任」，
    走浏览器辅助登录，不该让用户以为密码错了。
    """
    if isinstance(err, CredentialRejected):
        return True
    if not isinstance(err, LoginError):
        return False
    detail = str(getattr(err, "detail", "") or "")
    return getattr(err, "status", 0) == 401 or "密码错误" in detail


# ---------------------------------------------------------------- PAKE 原语

def create_seed(password: str) -> str:
    """createSeed: sha256(password) 作为大整数 mod SEED_MOD, 补齐 32 hex."""
    x = int(hashlib.sha256(password.encode()).hexdigest(), 16) % SEED_MOD
    return format(x, "032x")


def bcrypt_b64(data: bytes) -> str:
    """bcryptjs encodeBase64 (字母表 './A-Za-z0-9', 无填充)."""
    out = []
    acc = 0
    bits = 0
    for byte in data:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 6:
            bits -= 6
            out.append(B64_BCRYPT[(acc >> bits) & 0x3F])
    if bits:
        out.append(B64_BCRYPT[(acc << (6 - bits)) & 0x3F])
    return "".join(out)


def seeded_to_salted_str(seeded_hex: str) -> str:
    """JS w(): seeded(32hex) → 大整数 → 补齐32hex → 16字节 → bcrypt b64 (22字符盐体)."""
    return bcrypt_b64(bytes.fromhex(format(int(seeded_hex, 16), "032x")))


def create_v2_proof(password: str, t_login_use: dict, cnonce: str | None = None) -> dict:
    """createV2Proof: 依服务器 t_login_use 计算 {cnonce, snonce, proof}."""
    if _bcrypt is None or _nacl_signing is None:
        raise LoginError("proof", detail="缺少 bcrypt / PyNaCl 依赖 (manifest requirements)")
    option = t_login_use.get("option") or t_login_use.get("kdf") or ""
    snonce = t_login_use.get("snonce")
    if not option or not snonce:
        raise LoginError("proof", detail=f"t_login_use 字段缺失: {list(t_login_use)}")
    salted_hex = t_login_use.get("salted")
    if salted_hex:
        # hex(字符码序列) → 还原 22 字符盐体; h() 跳过 0 字节
        salt_body = "".join(
            chr(b) for b in bytes.fromhex(salted_hex) if b
        )
    else:
        salt_body = seeded_to_salted_str(t_login_use["seeded"])
    # S(option): 前缀 "bcrypt" 后即为 bcrypt salt 头 "$2a$10$"
    salt_head = option[6:] if option.startswith("bcrypt") else option
    bc_hash = _bcrypt.hashpw(password.encode(), (salt_head + salt_body).encode()).decode()
    ed_priv = hashlib.sha256(bc_hash.encode()).digest()
    cnonce = cnonce or secrets.token_hex(16)
    msg = hashlib.sha256(
        bytes.fromhex(snonce.split(":")[-1]) + bytes.fromhex(cnonce)
    ).digest()
    sig = _nacl_signing.SigningKey(ed_priv).sign(msg).signature
    return {"cnonce": cnonce, "snonce": snonce, "proof": sig.hex()}


# ---------------------------------------------------------------- 登录客户端

class LixiangDirectLogin:
    """手机号 + 密码直接登录理想账号, 获取主 Bearer / refresh_token."""

    def __init__(self, device_id: str | None = None, user_agent: str = DEFAULT_UA,
                 timeout: int = 20, debug: bool = False,
                 app_type: str = "lixiang") -> None:
        self.device_id = device_id or uuid.uuid4().hex
        self.user_agent = user_agent
        self.timeout = timeout
        self.debug = debug
        # ★ 2026-10-10：登录身份参数化（"lixiang" 主 App / "livis" 理想同学）
        #   两分支 audience 相同，仅 client_id / scope / redirect_uri 不同。
        self.app_type = app_type
        self.client_id, self.login_scope, self.redirect_uri = (
            APP_LOGIN_PARAMS.get(app_type) or APP_LOGIN_PARAMS["lixiang"]
        )
        self._sess = requests.Session()
        self._sess.headers.update({"User-Agent": self.user_agent,
                                   "x-requested-with": "XMLHttpRequest"})
        for dom in ("account.lixiang.com", "id.lixiang.com"):
            self._sess.cookies.set("X-LX-Deviceid", self.device_id, domain=dom)
            self._sess.cookies.set("authli_device_id", self.device_id, domain=dom)
        self._sess.cookies.set("isapp", "1", domain="account.lixiang.com")

    # ---------- 登录会话 cookie 的导出 / 装载（★ 2026-10-10） --------------

    def export_session_cookies(self) -> list[dict]:
        """导出登录态 cookie（可 JSON 序列化），供下次启动复用会话。

        ★ 为什么要它：会话 cookie 有 13 天有效期，但此前只活在内存里 ——
          于是**每次 HA 启动、每次会话丢失都要重新做一次密码登录**，
          而每次密码登录都可能把手机上的 App 顶下线。
        """
        out: list[dict] = []
        for ck in self._sess.cookies:
            if not ck.value:
                continue
            try:
                exp = int(ck.expires) if ck.expires else 0
            except (TypeError, ValueError):
                exp = 0
            out.append({
                "name": str(ck.name),
                "value": str(ck.value),
                "domain": str(ck.domain or ""),
                "path": str(ck.path or "/"),
                "expires": exp,
            })
        return out

    def import_session_cookies(self, cookies) -> int:
        """装载持久化的 cookie；返回真正装入的条数（过期的丢弃）。

        幂等：同名同域直接覆盖。任何异常都跳过该条，绝不让脏数据
        打断启动流程（最坏情况退化为「重新登录」，与改动前一致）。
        """
        import time as _time
        now = _time.time()
        n = 0
        for ck in cookies or []:
            if not isinstance(ck, dict):
                continue
            name = str(ck.get("name") or "")
            if not name:
                continue
            try:
                exp = int(ck.get("expires") or 0)
            except (TypeError, ValueError):
                exp = 0
            if exp and exp < now:
                continue                       # 已过期 → 不装
            # ★ domain 为空时【不要】显式传 None：requests 会拒绝该 cookie
            kw: dict = {"path": str(ck.get("path") or "/")}
            if ck.get("domain"):
                kw["domain"] = str(ck["domain"])
            try:
                self._sess.cookies.set(name, str(ck.get("value") or ""), **kw)
            except Exception:  # noqa: BLE001  —— 单条脏数据不该影响启动
                continue
            n += 1
        return n

    def _sync_parent_domain_cookies(self) -> None:
        """把登录态 cookie 同步到父域 `.lixiang.com`。

        ★ 2026-10-02 实测修复（顺藤摸瓜定位）：
          H5 页面（www.lixiang.com）依赖 `sso_token`，但服务端 Set-Cookie 时
          把它的域设成了 `id.lixiang.com` —— 于是 www 读不到，H5 会跳登录。
          App 的做法（`util/e.smali:1143`）是注入到父域 `.lixiang.com`。
          这里对齐 App：把 sso_token 等设备/登录 cookie 一并设到父域。

        幂等：重复设置同名同值无副作用。
        """
        sso = None
        for ck in self._sess.cookies:
            if ck.name == "sso_token" and ck.value:
                sso = ck.value
                break
        if not sso:
            return
        for name, val in (("sso_token", sso),
                          ("isapp", "1"),
                          ("X-LX-Deviceid", self.device_id),
                          ("authli_device_id", self.device_id)):
            self._sess.cookies.set(name, val, domain=".lixiang.com", path="/")

    # ---- 基础请求 ----
    def _idaas_headers(self) -> dict:
        return {
            "idaas-data": (
                f"model_name=OpenHarmony;device_model=;device_id={self.device_id};"
                f"app_version={APP_VERSION};client_id={self.client_id};"
                f"sdk_version={SDK_VERSION};timestamp={int(time.time() * 1000)}"
            ),
            "idaas-data-x": "source_url=registerAction=&pageUrl=&eventID=",
            "origin": BASE_ACCT,
            "referer": BASE_ACCT + "/",
        }

    def _post_json(self, url: str, payload: dict | list, step: str) -> dict:
        r = self._sess.post(url, json=payload, headers=self._idaas_headers(),
                            timeout=self.timeout)
        if self.debug:
            _LOGGER.debug("[%s] %s %s", step, r.status_code, r.text[:300])
        if r.status_code != 200:
            raise LoginError(step, r.status_code, r.text[:200])
        return r.json()

    # ---- 登录主流程 ----
    def login(self, phone: str, password: str) -> dict:
        """完整登录. 返回 /api/token 响应 (access_token / refresh_token / token_type...)."""
        phone_tip = phone if phone.startswith("+") else "+86" + phone

        # 1. PKCE 授权请求 → auth_session cookie
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(21)[:21]
        r = self._sess.post(
            f"{BASE_ID}/api/auth",
            data={
                "client_id": self.client_id, "device_id": self.device_id,
                "response_type": "code", "redirect_uri": self.redirect_uri,
                "offline_access": "true", "state": state,
                "audience": LOGIN_AUDIENCE, "scope": self.login_scope,
                "code_challenge": code_challenge, "code_challenge_method": "S256",
            },
            headers={**self._idaas_headers(),
                     "content-type": "application/x-www-form-urlencoded"},
            timeout=self.timeout)
        if r.status_code not in (200, 300):
            raise LoginError("auth", r.status_code, r.text[:200])

        # 2. 打开登录页 (初始化页面会话)
        self._sess.get(f"{BASE_ACCT}/login", params={
            "client_id": self.client_id, "redirect_uri": self.redirect_uri},
            headers={"accept": "text/html", "referer": BASE_ACCT + "/app-auth"},
            timeout=self.timeout)

        # 3. 设备注册
        r = self._sess.post(f"{BASE_ID}/api/devices", json={
            "client_id": self.client_id, "device_id": self.device_id,
            "user_agent": self.user_agent, "model": "", "manufacturer": "",
            "os": "OpenHarmony", "os_version": "6.1", "screen_height": 843,
            "screen_width": 374, "app_version": APP_VERSION,
        }, headers=self._idaas_headers(), timeout=self.timeout)
        if r.status_code != 200:
            raise LoginError("devices", r.status_code, r.text[:200])

        # 4. PAKE 握手: seed → t_login_use
        data = self._post_json(f"{BASE_ID}/api/idps", {
            "origin": BASE_ACCT, "connection": "LI_USER",
            "seed": create_seed(password), "strategy": "PASSWORD",
            "user_tip": phone_tip,
        }, "idps")
        t_login_use = data.get("t_login_use") or {}
        if not t_login_use:
            raise LoginError("idps", detail=f"响应无 t_login_use: {str(data)[:200]}")

        # 5. proof → 授权码
        proof = create_v2_proof(password, t_login_use)
        r = self._sess.post(f"{BASE_ID}/api/login", json={
            "client_id": self.client_id, "connection": "LI_USER",
            "user_tip": phone_tip, "proof": proof,
        }, headers=self._idaas_headers(), timeout=self.timeout, allow_redirects=False)
        if r.status_code not in (200, 300, 302):
            # 401 空体 = 密码错误 (实测)
            raise LoginError("login", r.status_code,
                             "密码错误或账号不存在" if r.status_code == 401 else r.text[:200])
        if "require=SMS_CODE" in (r.headers.get("location") or ""):
            raise LoginError("login", r.status_code,
                             "密码正确但风控要求短信验证 (用受信任的 --device-id 可跳过)")
        location = r.headers.get("location") or (r.json() or {}).get("location") or ""
        code = _query_param(location, "code")
        if not code:
            raise LoginError("login", r.status_code, f"响应无授权码: {location[:200]}")

        # 6. 授权码 + PKCE verifier 换 token
        r = self._sess.post(f"{BASE_ID}/api/token", data={
            "client_id": self.client_id, "grant_type": "authorization_code",
            "code": code, "code_verifier": code_verifier,
        }, headers={**self._idaas_headers(),
                    "content-type": "application/x-www-form-urlencoded"},
            timeout=self.timeout)
        if r.status_code != 200:
            raise LoginError("token", r.status_code, r.text[:200])
        self._sync_parent_domain_cookies()
        return r.json()

    # ---- 刷新 ----
    def refresh(self, refresh_token: str) -> dict:
        """用 refresh_token 换新 access_token (免密码)."""
        r = self._sess.post(f"{BASE_ID}/api/token", data={
            "client_id": self.client_id, "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, headers={**self._idaas_headers(),
                    "content-type": "application/x-www-form-urlencoded"},
            timeout=self.timeout)
        if r.status_code != 200:
            raise LoginError("refresh", r.status_code, r.text[:200])
        self._sync_parent_domain_cookies()
        return r.json()


def _query_param(url: str, name: str) -> str:
    from urllib.parse import parse_qs, urlparse
    return parse_qs(urlparse(url).query).get(name, [""])[0]


# ---------------------------------------------------------------- scope 换取

def exchange_scope_token(main_bearer: str, scope: str, audience: str,
                         device_id: str, timeout: int = 20,
                         app_type: str = "lixiang") -> dict:
    """主 Bearer → POST /api/auth (response_type=token) 换服务 scope token.

    见 auth.py LiBearerTokenMgr — 此处为独立函数供脚本/集成复用.
    ★ app_type：livis 分支用理想同学 client_id/redirect_uri（2026-10-10）。
    """
    client_id, _, redirect_uri = (
        APP_LOGIN_PARAMS.get(app_type) or APP_LOGIN_PARAMS["lixiang"]
    )
    r = requests.post(f"{BASE_ID}/api/auth", data={
        "prompt": "none", "offline_access": "true", "redirect_uri": redirect_uri,
        "scope": scope, "response_type": "token", "device_id": device_id,
        "audience": audience, "client_id": client_id,
    }, headers={
        "Authorization": f"Bearer {main_bearer}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": DEFAULT_UA,
    }, timeout=timeout)
    try:
        return r.json()
    except ValueError:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:200]}
