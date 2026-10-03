"""Li Auto — 主Bearer → scope token 管理器（理想后端核心）

理想逆向要点（鸿蒙抓包实证，2026-05）:
- 登录后拿到【主Bearer】(JWT, client=2AQClOaegaA7XecMSFx1p 签发, 有效期内)
- 用主Bearer POST id.lixiang.com/api/auth, body{scope, audience, response_type:"token",
  device_id, client_id} 换取该服务的 scope token (如 service-card 的 login token,
  vss/get-batch 的 token, 车控 remoteVeh*Control:VIN token)
- 各 aud token 互相隔离, 必须用对 aud 的 token 调对应接口
- service-card(首页状态) 用 aud=26Fehzs + scope=login

本模块:
- 持有主Bearer, 按需缓存并换取各 aud scope token
- HTTP 后端: 优先用 curl 子进程(实测到 id.lixiang.com 稳定), 避免 python SSL/代理坑
   (HA 环境如有独立网络, 可改用 aiohttp)
"""

from __future__ import annotations

import json
import logging
import subprocess
import time

from .const import (
    AUD_SERVICE_CARD,
    AUD_VEHICLE_VSS,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE_SERVICE_CARD,
    SCOPE_VEHICLE_VSS,
    veh_ctrl_scope,
)

_LOGGER = logging.getLogger(__name__)

_AUTH_URL = "https://id.lixiang.com/api/auth"


class LiAuthError(RuntimeError):
    """理想认证错误"""


def _curl_post_form(url: str, data: dict, bearer: str | None = None, timeout: int = 20) -> str:
    """用 curl 发 form POST, 返回 body."""
    cmd = ["curl", "-sS", "--http1.1", "--max-time", str(timeout), "-X", "POST", url]
    if bearer:
        cmd += ["-H", f"Authorization: Bearer {bearer}"]
    cmd += ["-H", "Content-Type: application/x-www-form-urlencoded"]
    cmd += ["-H", "Accept: application/json"]
    cmd += ["-H", "User-Agent: m01/8.25.4 (Li Auto)"]
    for k, v in data.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return p.stdout
    except Exception as e:  # pragma: no cover
        return f'{{"err": "{e}"}}'


class LiBearerTokenMgr:
    """主Bearer scope-token 管理器.

    用法:
      mgr = LiBearerTokenMgr(main_bearer="eyJ...", device_id="13BF...")
      mgr.get_service_card_token()   # service-card 状态接口用
      mgr.get_vss_token()            # vss/get-batch 用
      mgr.get_veh_ctrl_token(vin)    # 车控用
    """

    def __init__(self, main_bearer: str, device_id: str = "") -> None:
        self._main = main_bearer
        self._device_id = device_id or "13BFCE38F5774D0DBE21B625AA179AE0"
        self._cache: dict[str, dict] = {}

    def _exchange(self, scope: str, audience: str) -> str:
        body = {
            "prompt": "none",
            "offline_access": "true",
            "redirect_uri": REDIRECT_URI,
            "scope": scope,
            "response_type": "token",
            "device_id": self._device_id,
            "audience": audience,
            "client_id": CLIENT_ID,
        }
        resp = _curl_post_form(_AUTH_URL, body, bearer=self._main)
        try:
            obj = json.loads(resp)
        except json.JSONDecodeError:
            obj = {}
        if obj.get("access_token"):
            return obj["access_token"]
        if "login_required" in resp or obj.get("error") == "login_required":
            raise LiAuthError("主Bearer 无效/过期 (login_required), 需重新登录")
        raise LiAuthError(f"换token失败: {resp[:200]}")

    def _cached_or_new(self, key: str, scope: str, audience: str) -> str:
        now = int(time.time())
        ent = self._cache.get(key)
        if ent and ent["exp"] > now + 60:
            return ent["token"]
        tok = self._exchange(scope, audience)
        exp = 0
        try:
            pl = tok.split(".")[1]
            import base64
            pl += "=" * (-len(pl) % 4)
            exp = json.loads(base64.urlsafe_b64decode(pl)).get("exp", 0)
        except Exception:
            pass
        self._cache[key] = {"token": tok, "exp": exp or (now + 1800)}
        return tok

    def get_service_card_token(self) -> str:
        return self._cached_or_new("service", SCOPE_SERVICE_CARD, AUD_SERVICE_CARD)

    def get_vss_token(self) -> str:
        return self._cached_or_new("vss", SCOPE_VEHICLE_VSS, AUD_VEHICLE_VSS)

    def get_veh_ctrl_token(self, vin: str) -> str:
        return self._cached_or_new(f"ctrl:{vin}", veh_ctrl_scope(vin), AUD_VEHICLE_VSS)

    def invalidate(self) -> None:
        self._cache.clear()
