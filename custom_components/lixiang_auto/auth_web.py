"""理想汽车 · 首次登录辅助页面（让用户在自己浏览器里过滑动验证）

背景（2026-09-23 实测确立）
--------------------------
理想的新设备登录风控：
  · 新 device_id + 密码 → 服务端返回 require=SMS_CODE
  · 发短信前必须过【顶象滑动验证】（DX，第三方，无法在服务端绕过）
  · 但用户在【真实浏览器】里可以自己滑

同时确认的机制：
  · 服务端按 device_id 记信任（精确匹配，改 1 位即失效）
  · 任意 MFA 通过后，该 device_id 加入信任列表
  · 之后 device_id + 密码 → 免 MFA（免滑动、免短信）

本模块的方案
-----------
  ① HA 提供一个 HTTP 页面 /lixiang-login?token=xxx
  ② 页面里内嵌 iframe → 理想官方登录页（带 HA 的 device_id）
  ③ 用户在里面：输手机号 → 自己滑顶象 → 收短信 → 输验证码 → 登录成功
  ④ HA 后端【定时轮询】：用 ha_device_id + 密码 试登录
     一旦成功 → 说明设备已受信任 → 通知 config_flow 继续 ★
  ⑤ HA 保存 phone + password + device_id（不保存任何验证码）

安全
----
  · 不接触用户的短信/安全码（用户在理想官方页面里输入）
  · 密码由用户在 HA 表单里提供（config_flow 收集）
  · 页面 token 一次性、5 分钟有效
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
import time
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER_NAME, ACCOUNT_BASE, AUDIENCE, CLIENT_ID

_LOGGER = logging.getLogger(LOGGER_NAME)

# 会话表: token -> {phone, password, device_id, created_at, trusted}
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSION_TTL = 900          # 15 分钟
POLL_INTERVAL = 5           # 轮询间隔（秒）


def _gc() -> None:
    now = time.time()
    for k in [k for k, v in _SESSIONS.items() if now - v["created_at"] > _SESSION_TTL]:
        _SESSIONS.pop(k, None)


def create_session(phone: str, password: str, device_id: str) -> str:
    """创建一个登录会话，返回 token。

    ★ 2026-09-24（整合 shinnaluo 的 PR）：
      device_id 不能为空 —— 空值会让理想官方登录页一直转圈（loading）。
      若调用方传空，这里自动生成一个。
    """
    _gc()
    device_id = str(device_id or "").strip()
    if not device_id:
        device_id = uuid.uuid4().hex
        _LOGGER.warning("create_session 收到空 device_id，已自动生成 %s",
                        device_id[:12])
    tok = secrets.token_urlsafe(24)
    _SESSIONS[tok] = {
        "phone": phone,
        "password": password,
        "device_id": device_id,
        "created_at": time.time(),
        "trusted": False,
    }
    return tok


def get_session(tok: str) -> dict[str, Any] | None:
    _gc()
    return _SESSIONS.get(tok)


def mark_trusted(tok: str) -> None:
    s = _SESSIONS.get(tok)
    if s:
        s["trusted"] = True


def _load_login_html() -> str:
    """读取登录辅助页面的 HTML 模板。

    ★ 2026-09-23 外置（架构方案 2.7）：
      原先内联 113 行 HTML 在 Python 文件里 —— 改一行样式要动 .py、
      无语法高亮、diff 噪音大。现改为独立 .html 文件。

    模板占位符（运行时替换）：
      %%LOGIN_URL%%    理想官方登录页地址（带 device_id）
      %%DEVICE_ID%%    本次登录使用的 device_id
      %%TOKEN%%        辅助页面会话 token
    """
    path = os.path.join(os.path.dirname(__file__), "login_page.html")
    with open(path, encoding="utf-8") as fh:
        return fh.read()



class LiXiangLoginView(HomeAssistantView):
    """首次登录辅助页面。"""

    url = "/lixiang-login"
    name = "api:lixiang_auto:login"
    requires_auth = False        # ★ 用户可能未登录 HA，允许匿名访问

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        _gc()
        tok = request.query.get("token", "")
        s = _SESSIONS.get(tok)
        if not s:
            return web.Response(
                text="<h3>链接已失效</h3><p>请回到 Home Assistant 重新发起配置。</p>",
                content_type="text/html", status=404)

        # ★ 不在 HA 页面里嵌 iframe（会被 CORB/嵌入限制拦），
        #   改为提供【新窗口链接】，指向理想登录页并带上 HA 的 device_id
        #
        # ★ 2026-09-24 修复「一直转圈」（整合 shinnaluo 的 PR）：
        #   · 必须带 mode=h5
        #     /app-auth 默认 mode=app → 登录后会跳到 /login/App
        #     （App WebView 桥接页），普通浏览器里永远停在 loading。
        #   · audience 要用 pake 登录实测值（原来用的 VSS audience
        #     会走错授权分支）
        #   · scope 用 "iam:client:type:app openid"
        from urllib.parse import urlencode

        from .const import ACCOUNT_BASE

        dev = s["device_id"]
        # 主链接：H5 模式 + 完整授权参数
        login_url = ACCOUNT_BASE + "/app-auth?" + urlencode({
            "mode": "h5",
            "client_id": CLIENT_ID,
            "redirect_uri": f"{ACCOUNT_BASE}/app-auth",
            "response_type": "code",
            "scope": "iam:client:type:app openid",
            "audience": AUDIENCE,
            "device_id": dev,
        })
        # 备用链接：同样 mode=h5，但不带 audience/scope
        #   （authorize 参数异常导致卡住时用这条 → 走纯登录流程）
        alt_url = ACCOUNT_BASE + "/app-auth?" + urlencode({
            "mode": "h5",
            "client_id": CLIENT_ID,
            "redirect_uri": f"{ACCOUNT_BASE}/app-auth",
            "response_type": "code",
            "device_id": dev,
        })
        html = (_load_login_html()
                .replace("%%LOGIN_URL%%", login_url)
                .replace("%%ALT_LOGIN_URL%%", alt_url)
                .replace("%%DEVICE_ID%%", dev)
                .replace("%%TOKEN%%", tok))
        return web.Response(text=html, content_type="text/html")


class LiXiangLoginStatusView(HomeAssistantView):
    """登录状态查询（前端轮询用）。"""

    url = "/lixiang-login/status"
    name = "api:lixiang_auto:login_status"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        _gc()
        tok = request.query.get("token", "")
        s = _SESSIONS.get(tok)
        if not s:
            return web.json_response({"trusted": False, "expired": True})
        return web.json_response({
            "trusted": bool(s.get("trusted")),
            "expired": False,
        })


class LiXiangLoginCreateView(HomeAssistantView):
    """创建登录会话（供 config_flow 内部调用 / 测试用）。

    POST /lixiang-login/create
      Body: {"phone": "...", "password": "...", "device_id": "..."}
      → {"token": "...", "url": "..."}
    """

    url = "/lixiang-login/create"
    name = "api:lixiang_auto:login_create"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"error": "invalid json"}, status=400)
        phone = str(body.get("phone") or "")
        password = str(body.get("password") or "")
        device_id = str(body.get("device_id") or "")
        if not (phone and password and device_id):
            return web.json_response({"error": "missing fields"}, status=400)
        tok = create_session(phone, password, device_id)
        return web.json_response({"token": tok, "url": f"/lixiang-login?token={tok}"})


async def async_register_login_views(hass: HomeAssistant) -> None:
    """注册登录辅助页面（幂等）。"""
    if hass.data.get(f"{DOMAIN}_login_views"):
        return
    hass.http.register_view(LiXiangLoginView())
    hass.http.register_view(LiXiangLoginStatusView())
    hass.http.register_view(LiXiangLoginCreateView())
    hass.data[f"{DOMAIN}_login_views"] = True
    _LOGGER.debug("已注册 /lixiang-login 辅助页面")


def try_login(phone: str, password: str, device_id: str) -> bool:
    """尝试用 device_id + 密码 登录（用于检测设备是否已受信任）。

    返回 True 表示登录成功（设备已受信任）。
    """
    try:
        from .pake_login import LixiangDirectLogin
    except ImportError:
        return False
    try:
        cli = LixiangDirectLogin(device_id=device_id)
        tok = cli.login(phone, password)
        if tok.get("access_token"):
            _LOGGER.info("设备已受信任，登录成功: %s", device_id[:12])
            return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("检测登录（尚未受信任）: %s", str(err)[:80])
    return False


__all__ = [
    "create_session", "get_session", "mark_trusted", "try_login",
    "async_register_login_views", "POLL_INTERVAL",
]
