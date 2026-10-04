"""理想汽车同步 API 客户端 (认证链端到端验证版, 2026-09-06).

认证链 (全部经真实请求验证, 见 docs/实时状态打通_20260906.md):
  1. PAKE 密码登录 (pake_login) → 会话 sso_token cookie (13天) + 主Bearer + refresh_token
  2. 会话 cookie POST /api/auth (response_type=token) → 各服务 scope token (15分钟)
     注意: 裸 Bearer 换不了 scope token (login_required), 必须带登录会话 cookie;
     refresh_token 续期不会重新种 cookie, 故密码是唯一的长期免维护凭据。
  3. x-chj 签名请求 (hac_key/KEY_ID/X-CHJ-Deviceid 用 iPad 捕获的一套) + scope Bearer
     → /ssp-cloud-vss-service/mobile/vss/get-batch 读实时信号

同步 requests 实现, HA 侧经 hass.async_add_executor_job 调用。
"""

from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


from .policy import (
    POLICY_COMMAND,
    POLICY_RESULT,
    POLICY_VSS,
    TokenExpired,
    is_token_expired,
    run_with_retry,
)
from .pake_login import (
    APP_VERSION as LOGIN_APP_VERSION,
    BASE_ID,
    CLIENT_ID,
    LixiangDirectLogin,
    LoginError,
    REDIRECT_URI,
    SDK_VERSION,
)

_LOGGER = logging.getLogger(__name__)

API_APP = "https://api-app.lixiang.com"
SIGN_APP_VERSION = "8.25.4-10463"
AUD_VSS = "1j0vgTqagJUHuT6nLmbTGx"
AUD_SERVICE_CARD = "26FehzsHlrllCSaqI9bFYG"
SCOPE_VSS = "vss:get-batch"
SCOPE_CARD = "login offline_access"

# ---------- 车控双 token (2026-09-22 实测打通) ----------
# cmd/send 需要【两个】token, 缺一不可:
#   Authorization: Bearer <MESH>   认证     (aud=1j0vgTqagJUHuT6nLmbTGx, ~15min)
#   body.token     = <VAT>         业务授权 (aud=5Tc7yDrnMzALwc9Rytl9sp, JWT ~20h)
# 两者都用登录会话 POST https://id.lixiang.com/api/auth (response_type=token) 换取。
AUD_MESH = "1j0vgTqagJUHuT6nLmbTGx"
SCOPE_MESH = "remote-wakeup:wakeup veh-ctrl:cmd-send veh-ctrl:cmd-result-get"
AUD_VAT = "5Tc7yDrnMzALwc9Rytl9sp"

# ★ 2026-10-01 实测新增：lcp-bff-app-api 通道
#   来源：App subTokenData（服务端下发，mmkv/m01_sp）
#   {"type":"lcp-bff-app-api","audience":"3N1l45XSeMOaid2RgDLiLA",
#    "disableIAM":1,"scope":["login"],"urls":["/lcp-bff-app-api"]}
#   ★ 该白名单是【全前缀放行】→ /lcp-bff-app-api/** 均可用
#   实测已通：plate-number/v1/list、user-settings/v1/user-pnc-switch/list、
#             serve-page/v1/station-stats、travel-planning/v1/simulate/energy/cost
#   ⚠️ 需要【用户身份】的接口（充电记录 chargeRecords 等）额外要 X-CHJ-Token
#      （App 短效 token，集成无法自行获取 → 100105 用户未登录）
AUD_LCP_BFF = "3N1l45XSeMOaid2RgDLiLA"
SCOPE_LCP_BFF = "login"
EP_LCP_PNC_LIST = "/lcp-bff-app-api/user-settings/v1/user-pnc-switch/list"

# VAT scope
#
# ★★ 2026-09-26 重大修正：
#   之前我们自己拼了 14 个（含 cpCtrl / ssCtrl / ChargingControl）—— 那是错的！
#   实测：多请求 App 没有的 scope 会让服务端【整批降级】，只授权 8 个
#        （丢掉 fTkC / rmCtrl / ADCtrl / ADInit）。
#
#   权威来源：APK 内置 assets/m01config.json → code="app" → subTokenData
#             里 type="VAT_1" 的 scope（精确 12 个，含 remoteVeh 前缀）
#
#   实测对比（2026-09-26）：
#     · 我们拼的 14 个 → 服务端只给 8 个   ❌
#     · App 的 12 个   → 服务端给全部 12 个 ✅
#
# ⚠️ 名字已含完整前缀，vat_scope() 只加 ":<VIN>" 后缀。
# ⚠️ 充电没有独立 scope（subTokenData 40 项里搜不到 cpCtrl/Charging*）——
#    充电走 JOB（NDN）路由，与 scope 无关。
VAT_SCOPE_COMMANDS = (
    "remoteVehACSmartControl", "remoteVehFrgControl", "remoteVehAuth",
    "remoteVehLockControl", "remoteVehPlgControl", "remoteVehSearch",
    "remoteVehWdwControl", "remoteVehACFirstControl",
    "remoteADCtrl", "remoteADInit", "fTkC", "rmCtrl",
)

# 车控端点
# ---------- 服务器通知（MMS，2026-09-23 实测打通）----------
# 端点: GET /mms-api/v1-0/message?appId=<>&channelType=1&pageSize=&pageNumber=
# token: audience=5a1X5rZcWZNeEOYlyRigUs, scope=ALL
# 实测: channelType=1 → 通知列表（2165 条）；2/4 → 其他类别
AUD_MMS = "5a1X5rZcWZNeEOYlyRigUs"
SCOPE_MMS = "ALL"
MMS_APP_ID = "chj_app_m01"
EP_MMS_MESSAGE = "/mms-api/v1-0/message"

# ---------- 车辆列表（★ 2026-09-23 实测打通）----------
AUD_SAOS_VEHICLE = "7gbeHMwBPMZA5SU1b2awIo"
SCOPE_SAOS_VEHICLE = "login"
EP_SAOS_VEHICLES = (
    "/saos-vehicle-api/v2-0/vehicles/basics"
    "?types=owned,transferring,authorized,inviting"
    "&roleIds=1,10,11,13,15&vehicleInfo=true"
)
EP_MMS_NOTIFICATION = "/mms-api/v1-0/notification"
EP_MMS_DEVICE = "/mms-api/v1-0/device"
CHANNEL_NOTICE = 1          # 通知类别
CHANNEL_OTHER_2 = 2
CHANNEL_OTHER_4 = 4

EP_CMD_SEND = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send"
EP_CMD_RESULT = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd-result"
EP_WAKEUP = "/iot-connect-manager-service/v2/wakeup"
CTRL_DOMAIN = "xcu"

# cmd-result pushState 语义
PUSH_STATE_SUCCESS = 5     # 执行成功
PUSH_STATE_FAILED = 7      # 执行失败

# ★ resultCode 的"成功"集合 (2026-09-23 从 XHttpOpenAcControl.isSuccessResultCode 逆向)
#   "-15" = 倒计时完成 (座椅加热/空调倒计时到期, App 视为成功)
#   "-8"  = 同类特判, 也视为成功
#   源码: if ("-15".equals(code)) return true; if ("-8".equals(code)) return true;
SUCCESS_RESULT_CODES = {0, "0", -15, "-15", -8, "-8"}

# 命令有效期: 源码真实值 (const/16 0x1e = 30 秒, const-wide/16 0x7530 = 30000ms)。
# 服务端只校验 jobExpire >= 1; 填 1 也能成功, 用 30 更贴近真机、更保险。
CMD_EXPIRE = 30
CMD_EXPIRE_MS = 30_000

# ★ 长短命令分级 (2026-09-23 实测):
#   短命令 (锁/窗/寻车/启动)     -> jobExpire=30 足够
#   长命令 (座椅加热/通风/空调)  -> jobExpire>=900 (实测 30 会超时 ps=7 rc=空)
#   App 源码里开空调也有 1860 的分支 (getVehPowerMode()!=2)
LONG_RUNNING_CMD_KEYS = {
    "remoteVehACSmartControl",   # 空调/座椅/方向盘加热/除霜
}
LONG_CMD_EXPIRE = 900
LONG_CMD_EXPIRE_MS = 900_000

# 空请求体 Content-MD5 常量 (base64(MD5("")))
EMPTY_MD5 = "1B2M2Y8AsgTpgAmY7PhCfg=="


def vat_scope(vin: str) -> str:
    """构造 VAT scope。

    ★ 2026-09-26：VAT_SCOPE_COMMANDS 里【已含完整 scope 名】
      （如 "remoteVehACSmartControl"），所以这里只加 :VIN 后缀。
    """
    return " ".join(f"{c}:{vin}" for c in VAT_SCOPE_COMMANDS)


class LiApiError(RuntimeError):
    """理想 API 认证/请求错误"""


# ---------------------------------------------------------------------------
# JOB 通道命令判定（2026-09-26）
# ---------------------------------------------------------------------------
# 逆向来源：LiveNetControlRouter.resolveRoute()
#   key 含 "mob.vehCtrlService.vehCtrlJobList" → VEH_CONTROL（HTTP cmd/send）
#   否则                                       → JOB（LiNdn/NDN）
#
# 充电的 destParams = "mob.metaJobService.remoteChargingControl" → 走 JOB。
# 因此这些 command_key 用 HTTP 发必然 2009。
_JOB_CHANNEL_COMMANDS = frozenset({
    # ---- 充电控制（已实测 2009）----
    "remote_charge_control",          # 启停 / 上限 / 保温 / 预约
    "remote_charging_start",
    "remote_charging_stop",
    "remoteChargingControl",
    "chargeLimit",
    # ---- 未实测但有同样特征（destParams 走 metaJob）----
    "MoveOffAdd",                     # 按时出发
    "MoveOffModify",
    "ReserveFridgeData",              # 冰箱预约
    "sceneModeCtrl",                  # 场景模式
})
# ⚠️ 反面例证（这些【不】在列表里，因为实测能用）：
#   · sentinelModeSetting —— App 走 JOB，但 HTTP cmd/send 也能成功 ✅
#   · remoteVehSvm        —— 远程拍照，实测能用 ✅
#   ★ 说明「App 走 JOB」不等于「HTTP 一定不能用」；
#     只有实测 2009 的才列入。


def _is_job_channel_command(command_key: str) -> bool:
    """判断命令是否走 JOB（LiNdn）通道（HTTP 不支持）。"""
    key = str(command_key) if command_key is not None else ""
    return key in _JOB_CHANNEL_COMMANDS


#: ★ 统一文案：供【所有】走 JOB 通道的实体复用。
#:   实体在 extra_state_attributes 里暴露它，并在写入时抛出，保证
#:   「用户看到的提示」与「实际抛出的错误」逐字一致。
JOB_CHANNEL_NOTICE = "充电走 LiNdn 通道，当前版本不支持控制"

#: 属性名（中文，便于用户在 HA 开发者工具里直接读懂）
JOB_CHANNEL_REASON_ATTR = "只读原因"


def job_channel_readonly_attrs(command_key: str) -> dict:
    """★ 2026-09-28：给走 JOB 通道的实体生成「只读标注」属性。

    背景：充电相关的 6 个实体在 HA 里是【可写平台】（number/select/switch/time），
    用户能点，但命令必然 2009 失败且没有解释 —— 看起来像集成坏了。

    本函数让实体在状态属性里【自曝】为什么不能控制，
    实体本身【不删除】（用户可能已用其状态做自动化）。

    非 JOB 通道的命令返回 {}（不污染属性）。
    """
    if not _is_job_channel_command(command_key):
        return {}
    return {JOB_CHANNEL_REASON_ATTR: JOB_CHANNEL_NOTICE}


def ensure_job_channel_supported(command_key: str) -> None:
    """★ 2026-09-28：写入【之前】拦截 JOB 通道命令。

    ★ 为什么要在发送前拦，而不是等 2009：

      旧行为：实体可写 → 下发 → 服务端 ~120ms 后回 2009 → 抛 LiChannelNotSupported。
      问题：① 白白消耗一次车控请求（有风控风险）
            ② 失败原因要在一次网络往返后才可知，
               而它其实【是静态已知的】（命令在 _JOB_CHANNEL_COMMANDS 里）
            ③ 用户在 HA 里看到的是「执行失败」，而不是「这个功能不支持」

      新行为：命令静态已知不支持 → 立即抛 LiChannelNotSupported，
              消息与 extra_state_attributes 里的「只读原因」完全一致。

    非 JOB 通道命令：直接返回（无副作用）。
    """
    if not _is_job_channel_command(command_key):
        return
    raise LiChannelNotSupported(
        f"「{command_key}」{JOB_CHANNEL_NOTICE}。"
        f"这是已知限制：该命令走理想 App 的 LiNdn（JOB）长连接，"
        f"HTTP 车控接口（cmd/send）不支持。状态读取不受影响，仍可正常查看。",
        result_code=2009, push_state=PUSH_STATE_FAILED,
    )


class LiCommandError(LiApiError):
    """车控命令执行失败 (含服务端 resultCode / pushState)."""

    def __init__(self, message: str, *, request_id: str = "",
                 result_code: int | None = None, push_state: int | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.result_code = result_code
        self.push_state = push_state


class LiChannelNotSupported(LiCommandError):
    """命令走【不支持的通道】—— 典型是充电控制。

    ★ 2026-09-26：逆向确认，充电命令走 LiveNetControlRoute.JOB（LiNdn/NDN）通道，
      而 HTTP cmd/send 只支持 VEH_CONTROL 通道（车门锁/车窗/空调/座椅等）。

      App 的路由规则（LiveNetControlRouter.resolveRoute）：
        key 含 "mob.vehCtrlService.vehCtrlJobList" → VEH_CONTROL（HTTP）
        否则                                       → JOB（NDN）

      充电的 destParams = "mob.metaJobService.remoteChargingControl"
      → 走 JOB → HTTP 通道不执行 → pushState=7 resultCode=2009

    本异常让用户得到【明确提示】，而不是"点了没反应"。
    """


class _TokenExpired(TokenExpired):
    """VSS token 失效（401），触发上层清除缓存并重试。

    ★ 2026-09-23：改为继承 policy.TokenExpired（结构化异常）。
      名字保留，避免改动所有调用点。
    """


class LiApiClient:
    """同步版理想客户端: 管理登录会话与 scope token, 提供实时信号读取."""

    def __init__(
        self,
        phone: str,
        password: str,
        vin: str,
        hac_key: str,
        key_id: str,
        xdev: str,
        app_token: str,
        device_id: str | None = None,
        refresh_token: str = "",
        on_token_update=None,
    ) -> None:
        self._phone = str(phone) if phone is not None else ""
        self._password = str(password) if password is not None else ""
        self._vin = str(vin) if vin is not None else ""
        # ★ 2026-09-24 修复（严重 bug）：
        #   secrets 模块的 _LazySecret 是 str 子类，构造时内容为空，
        #   真实值靠 __str__() 延迟求值。
        #   如果直接存对象（self._key_id = key_id），
        #   后续用作 HTTP 头时可能拿到【空字符串】：
        #     requests 对 str 子类可能不调用 __str__()
        #   → 服务端报「缺少必要的请求参数: X-CHJ-Key,X-CHJ-Deviceid」
        #
        #   ★ 必须显式 str() 强制求值。
        self._hac = _hac_key_bytes(hac_key)
        self._key_id = str(key_id) if key_id is not None else ""
        self._xdev = str(xdev) if xdev is not None else ""   # x-chj 签名身份 (与 hac_key 绑定的设备)
        self._app_token = str(app_token) if app_token is not None else ""
        # ★ 主 Bearer（PAKE 登录后的 access_token）—— travel 等接口需要（App 抓包 x-chj-token = APP-xxx）
        self._main_bearer: str = ""
        self._refresh_token = str(refresh_token) if refresh_token is not None else ""
        self._cli: LixiangDirectLogin | None = None
        if device_id:
            self._device_id = device_id
        else:
            import secrets
            self._device_id = secrets.token_hex(16)
        self._tokens: dict[str, tuple[str, float]] = {}   # name -> (token, expiry_monotonic)
        # ★ 2026-10-02 持久化：token 轮换后回写 config entry。
        #   入参是 dict（只含变化的键），由 __init__.py 注入 — 避免 li_api 依赖 HA。
        #   此前缺陷：新 token 只存内存，重启后读回首次登录的旧值
        #   → refresh_token 轮换即失效 → 每次重启都要密码重登（有风控风险）。
        self._on_token_update = on_token_update

    # ---------- 登录会话 ----------

    def _login(self) -> None:
        """PAKE 密码登录, 建立 sso_token 会话 (cookie 13 天有效)."""
        # ★ 2026-10-02 修正：必须用 _xdev（与签名头 X-CHJ-Deviceid 同一个），
        #   否则服务端认为「token 来自别的设备」→ 100105 用户未登录。
        cli = LixiangDirectLogin(device_id=self._xdev or self._device_id, debug=False)
        tok = cli.login(self._phone, self._password)
        if not tok.get("access_token"):
            raise LiApiError("登录成功但无 access_token")
        self._cli = cli
        # ★ 保存主 Bearer：travel/陪伴里程接口用（此前只存 refresh_token → travel 120001）
        self._main_bearer = str(tok.get("access_token") or "")
        self._refresh_token = tok.get("refresh_token", "") or self._refresh_token
        self._tokens.clear()
        self._notify_token_update()
        _LOGGER.info("li_api PAKE 登录成功 (device_id=%s)", self._device_id)

    def _notify_token_update(self) -> None:
        """把最新 token 交给回调（由集成侧写入 config entry 持久化）。

        回调失败不影响主流程（token 已在内存中可用）。
        """
        cb = getattr(self, "_on_token_update", None)
        if not cb:
            return
        try:
            cb({
                "refresh_token": self._refresh_token,
                "main_bearer": self._main_bearer,
                "access_token": self._main_bearer,
            })
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("token 回写回调失败（不影响运行）: %s", err)

    def _ensure_session(self) -> LixiangDirectLogin:
        """保证登录会话可用 (尝试换取 token 探测会话有效性)."""
        if self._cli is not None:
            return self._cli
        self._login()
        return self._cli

    def _exchange(self, scope: str, audience: str) -> str:
        """用登录会话 cookie 换 scope token (response_type=token)."""
        cli = self._ensure_session()
        r = cli._sess.post(
            f"{BASE_ID}/api/auth",
            data={
                "prompt": "none", "offline_access": "true",
                "redirect_uri": REDIRECT_URI, "scope": scope,
                "response_type": "token", "device_id": self._device_id,
                "client_id": CLIENT_ID, "audience": audience,
            },
            headers={
                "idaas-data": (
                    f"model_name=OpenHarmony;device_id={self._device_id};"
                    f"app_version={LOGIN_APP_VERSION};client_id={CLIENT_ID};"
                    f"sdk_version={SDK_VERSION};timestamp={int(time.time() * 1000)}"
                ),
                "origin": "https://account.lixiang.com",
                "referer": "https://account.lixiang.com/",
                "x-requested-with": "XMLHttpRequest",
                "User-Agent": f"m01/{LOGIN_APP_VERSION}",
                "content-type": "application/x-www-form-urlencoded",
            },
            allow_redirects=False, timeout=20,
        )
        frag = urllib.parse.urlparse(r.headers.get("location", "")).fragment
        tok = dict(urllib.parse.parse_qsl(frag)).get("access_token", "")
        if not tok:
            raise LiApiError(f"换 token 失败 ({scope}): HTTP {r.status_code} {r.text[:120]}")
        return tok

    def _get_scoped(self, name: str, scope: str, audience: str, ttl: int = 780) -> str:
        """scope token 缓存获取 (默认提前 2 分钟过期; 失效自动重登一次)."""
        ent = self._tokens.get(name)
        if ent and ent[1] > time.monotonic():
            return ent[0]
        try:
            tok = self._exchange(scope, audience)
        except LiApiError:
            if self._password:
                _LOGGER.info("会话失效, 重新登录 (%s)", name)
                self._cli = None
                self._login()
                tok = self._exchange(scope, audience)
            else:
                raise
        self._tokens[name] = (tok, time.monotonic() + ttl)
        return tok

    # ---------- 车控双 token ----------

    def _get_mesh_token(self) -> str:
        """MESH token: cmd/send 的 Authorization 头 (~15min)."""
        return self._get_scoped("mesh", SCOPE_MESH, AUD_MESH, ttl=780)

    def _get_vat_token(self) -> str:
        """VAT token: cmd/send 的 body.token 字段 (JWT, ~20h)。

        scope 必须按 remoteVeh<Cmd>:<VIN> 逐条列出。
        """
        return self._get_scoped("vat", vat_scope(self._vin), AUD_VAT, ttl=19 * 3600)

    def invalidate_tokens(self) -> None:
        """清空 token 缓存 (强制下次重新换取)."""
        self._tokens.clear()

    # ---------- x-chj 签名请求 ----------

    def _signed_call(self, method: str, path: str, body: str, bearer: str) -> dict:
        ts = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        if body:
            md5 = base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
        else:
            md5 = EMPTY_MD5
        data = "\n".join([
            "prod", SIGN_APP_VERSION, self._key_id, self._xdev, method, "*/*",
            "zh-Hans-CN", md5, "application/json", ts, nonce,
        ]) + "\n"
        sig = base64.b64encode(hmac.new(self._hac, data.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "X-CHJ-Env": "prod", "X-CHJ-APP-Version": SIGN_APP_VERSION,
            "X-CHJ-Key": self._key_id, "X-CHJ-Deviceid": self._xdev,
            "X-CHJ-Timestamp": ts, "X-CHJ-Nonce": nonce, "X-CHJ-Sign": sig,
            "Content-MD5": md5, "Content-Type": "application/json",
            "Content-Language": "zh-Hans-CN", "Accept": "*/*",
            "X-CHJ-Version": SIGN_APP_VERSION, "X-CHJ-DeviceType": "2",
            "X-CHJ-ModelName": "IOS", "X-CHJ-Tag": "1",
            "X-CHJ-TOKEN": self._app_token,
            "X-CHJ-VIN": self._vin,
            "Authorization": f"Bearer {bearer}",
            "User-Agent": f"m01/{SIGN_APP_VERSION} (iPad; iOS 16.7.12; Scale/2.00)",
        }
        req = urllib.request.Request(
            API_APP + path, method=method,
            headers=headers, data=body.encode() if body else None)
        try:
            with urllib.request.urlopen(
                    req, context=_ssl_ctx(), timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise LiApiError(f"{method} {path}: HTTP {e.code} {e.read().decode()[:200]}")

    # ---------- 业务接口 ----------

    def _invalidate_token(self, name: str) -> None:
        """清除某个 scope token 的缓存（401 时调用，强制下次重新换取）。"""
        self._tokens.pop(name, None)

    # ---- 行程/陪伴里程（2026-10-02 逆向）----
    #
    # ★ 为什么单独一套：travel 接口对请求头有校验。
    #   实测：用集成默认头（Accept:*/* / zh-Hans-CN / iPad UA / IOS modelname /
    #   无 metadata/devicemodel/accept-language）→ 120001「系统繁忙」；
    #   换成 App 抓包的头 → code=0 SUCCESS。
    #   为保证现有功能零回归，这里【只给 travel 用】，不动全局 _signed_call。
    #
    # 参考：lixiang-reverse/docs/SUBPAGES.md §十七

    # App（Harmony）风格头值 —— 来自抓包 data/2026-05-05_licar_captures.json
    _TRAVEL_ACCEPT = "application/json, text/plain, */*"
    _TRAVEL_LANG = "zh-CN"
    _TRAVEL_UA = "M01/8.22.0 (HUAWEI; 6)"
    _TRAVEL_MODELNAME = "harmony"
    _TRAVEL_DEVICEMODEL = "HBP-AL00"
    _TRAVEL_AL = "zh-CN,en-AS;q=0.9"
    _TRAVEL_META = '{"code":102004, "language":"zh"}'

    def _signed_call_travel(self, method: str, path: str, body: str, bearer: str) -> dict:
        """travel 接口专用：用 App 头 + 同步重算签名。

        签名覆盖 Accept / Content-Language，所以这两个值变了必须一起改签名数据。
        """
        ts = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        md5 = (base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
               if body else EMPTY_MD5)
        data = "\n".join([
            "prod", SIGN_APP_VERSION, self._key_id, self._xdev, method,
            self._TRAVEL_ACCEPT,      # ← Accept（签名第 6 段）
            self._TRAVEL_LANG,        # ← Content-Language（第 7 段）
            md5, "application/json", ts, nonce,
        ]) + "\n"
        sig = base64.b64encode(
            hmac.new(self._hac, data.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "accept-encoding": "deflate, gzip, br",
            "x-chj-metadata": self._TRAVEL_META,
            "user-agent": self._TRAVEL_UA,
            "x-chj-traceid": str(uuid.uuid4()),
            "x-chj-modelname": self._TRAVEL_MODELNAME,
            "x-chj-devicetype": "2",
            "x-chj-token": bearer,
            "x-chj-nonce": nonce,
            "content-language": self._TRAVEL_LANG,
            "content-type": "application/json",
            "x-chj-devicemodel": self._TRAVEL_DEVICEMODEL,
            "x-chj-version": SIGN_APP_VERSION,
            "content-md5": md5,
            "x-chj-timestamp": ts,
            "x-chj-key": self._key_id,
            "x-chj-env": "prod",
            "x-chj-vin": self._vin,
            "accept-language": self._TRAVEL_AL,
            "x-chj-app-version": SIGN_APP_VERSION,
            "x-chj-sign": sig,
            "x-chj-deviceid": self._xdev,
            "accept": self._TRAVEL_ACCEPT,
            "Authorization": f"Bearer {bearer}",
        }
        req = urllib.request.Request(API_APP + path, method=method, headers=headers,
                                     data=body.encode() if body else None)

        def _do(rq):
            with urllib.request.urlopen(rq, context=_ssl_ctx(), timeout=20) as resp:
                return json.loads(resp.read().decode())

        try:
            return _do(req)
        except urllib.error.HTTPError as e:
            raise LiApiError(f"{method} {path}: HTTP {e.code} {e.read().decode()[:200]}")
        except Exception:  # noqa: BLE001
            raise

    def _travel_bearer(self, force_login: bool = False) -> str:
        """travel 接口用的主 Bearer（App 抓包里 x-chj-token = APP-xxx）。

        ★ 2026-10-02：主 Bearer 会过期（服务端 100105「用户未登录」）。
          调用方收到 100105 时用 force_login=True 重登一次再试。
        ★ 2026-10-02 修正：_login() 里 `if self._cli is not None` 之类的短路会让
          force_login 无效 —— 这里强制清空 _cli 再登录，确保真的换新 token。
        """
        if force_login or not getattr(self, "_main_bearer", ""):
            self._main_bearer = ""
            self._cli = None            # ★ 关键：清掉旧 session，强制重新登录
            self._tokens.clear()
            self._login()
        return getattr(self, "_main_bearer", "") or self._app_token

    def get_travel_months(self) -> dict:
        """各月里程汇总 → GET /ssp-travel-x-service/v1-0/travel/months/{vin}"""
        path = f"/ssp-travel-x-service/v1-0/travel/months/{self._vin}"
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        if r.get("code") == 100105:
            r = self._signed_call_travel("GET", path, "", self._travel_bearer(True))
        return r

    def get_travel_monthly(self, year: int, month: int) -> dict:
        """单月详情（含每日 dailyList）→ .../travel/monthly/{year}/{month}/{vin}"""
        path = (f"/ssp-travel-x-service/v1-0/travel/monthly/{year}/{month}"
                f"/{self._vin}")
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        if r.get("code") == 100105:
            r = self._signed_call_travel("GET", path, "", self._travel_bearer(True))
        return r

    def get_travel_daily(self, start_date: str, end_date: str) -> dict:
        """时间段汇总 → .../travel/daily/aggregate/{vin}?startDate=&endDate="""
        path = (f"/ssp-travel-x-service/v1-0/travel/daily/aggregate/{self._vin}"
                f"?startDate={start_date}&endDate={end_date}")
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        if r.get("code") == 100105:
            r = self._signed_call_travel("GET", path, "", self._travel_bearer(True))
        return r

    def get_travel_all_aggregate(self) -> dict:
        """全里程汇总 → GET /ssp-travel-x-service/v1-0/travel/all/aggregate/{vin}

        ★ 2026-10-03：从抓包（data/2026-05-05_licar_captures.json）发现
          App 还会调这个端点，之前集成漏了。实测 App 在进入里程页时
          调用一次，推测返回「陪伴里程」等全量累计值。
        """
        path = f"/ssp-travel-x-service/v1-0/travel/all/aggregate/{self._vin}"
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        if r.get("code") == 100105:
            r = self._signed_call_travel("GET", path, "", self._travel_bearer(True))
        return r

    # ---- 驻车照片（SVM，2026-10-03 抓包逆向）----
    # ★ 完整链路（依据 data/2026-05-05_licar_captures.json 的真实请求）：
    #
    #   GET /chehejia-service-ois-app/ois/file/service/urls
    #       ?fileKeys=<逗号分隔的 OSS key>&identify=vehicle
    #
    #   fileKey 路径模板（抓包原文）：
    #     vehicle/svm_photo/{车型代码}/YYYYMMDD/{VIN}/data/data_center/upload/
    #         {YYYYMMDDHHmmss}pic{方位}.jpg
    #
    #   方位共 5 路：Front / Rear / Left / Right / Top
    #   例：vehicle/svm_photo/X04/20260505/{VIN}/data/data_center/upload/
    #       20260505202638picInRear.jpg
    #
    #   → 接口返回每张图的签名 URL（可直接 <img src> 显示）
    #
    # ⚠️ 图片本身存在理想 OSS，URL 有过期时间，需现取现用。

    SVM_ANGLES = ("Front", "Rear", "Left", "Right", "Top")

    @staticmethod
    def svm_filekeys_from_vss(raw) -> dict:
        """从 VSS `Vehicle.360Svm.Park.Filekey` 的 JSON 里取 fileKeys。

        ★ 2026-10-03 决定性修正（依据 APK 的 XPhotoDataHandle.smali）：

            该信号返回的 JSON **本身就带 fileKeys 字段**：

                {"picTime":"2026-09-05 20:27:20",
                 "fileKeys":{
                   "picInRear": "vehicle/svm_photo/X04/20260905/{VIN}/.../20260905202717picInRear.jpg",
                   "picInFront":"...",
                   "picInRight":"...","picInLeft":"...","picInTop":"..."}}

            App 的做法（smali 逐行可读）：

                item = map.get("Vehicle.360Svm.Park.Filekey")
                json = item.getDp().getValue()
                fileKeys = fromJson(json).get("fileKeys").getAsJsonObject()
                list = fileKeys.values()
                → 调 /ois/file/service/urls?fileKeys=<list>

            **所以不要去拼路径** —— 文件名里的时间戳与 picTime **并不相同**
            （实测 picTime=20:27:20 而文件名=20260905202717，差 3 秒），
            拼出来的 key 在 OSS 里根本不存在（接口会返回 data:{}）。

        返回：``{方位: fileKey}``；解析失败返回 ``{}``。
        """
        if not raw:
            return {}
        obj = raw
        if isinstance(raw, str):
            try:
                obj = json.loads(raw)
            except (ValueError, TypeError):
                return {}
        if not isinstance(obj, dict):
            return {}
        fk = obj.get("fileKeys")
        if not isinstance(fk, dict):
            return {}
        return {k: v for k, v in fk.items() if isinstance(v, str) and v}

    @staticmethod
    def svm_pic_time(raw) -> str:
        """从同一个 JSON 里取 picTime（用于界面展示）。"""
        if not raw:
            return ""
        obj = raw
        if isinstance(raw, str):
            try:
                obj = json.loads(raw)
            except (ValueError, TypeError):
                return ""
        if isinstance(obj, dict):
            return str(obj.get("picTime") or obj.get("picTimestamp") or "")
        return ""

    def svm_photo_filekeys(self, when, car_type: str = "") -> list[str]:
        """按抓包模板构造 5 路驻车照片的 OSS key。

        Args:
            when: 拍照时间（datetime，用 VSS `Vehicle.360Svm.Park.Filekey`
                  的 picTime；也接受 ``"2026-10-03 11:46:24"`` 这类字符串）
            car_type: 车型代码（如 X04）；空则用实例缓存值

        注：入参不标注 datetime 类型，避免为一个纯格式化函数引入模块级导入。
        """
        if isinstance(when, str):
            # VSS 常见格式： "2026-10-03 11:46:24" 或 ISO
            txt = when.strip().replace("T", " ").split(".")[0]
            try:
                when = datetime.strptime(txt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    when = datetime.fromisoformat(txt)
                except ValueError:
                    return []
        ct = car_type or getattr(self, "_car_type_code", "") or "X04"
        day = when.strftime("%Y%m%d")
        stamp = when.strftime("%Y%m%d%H%M%S")
        base = (f"vehicle/svm_photo/{ct}/{day}/{self._vin}"
                f"/data/data_center/upload/{stamp}")
        return [f"{base}picIn{a}.jpg" for a in self.SVM_ANGLES]

    def get_svm_photo_urls(self, file_keys: list[str]) -> dict:
        """OSS key → 签名 URL。

        返回形如 ``{"urls": {key: url}}``；失败时含 ``error``。
        """
        if not file_keys:
            return {"error": "empty file_keys"}
        keys = ",".join(file_keys)
        path = ("/chehejia-service-ois-app/ois/file/service/urls"
                f"?fileKeys={urllib.parse.quote(keys, safe='')}&identify=vehicle")
        try:
            r = self._signed_call_travel("GET", path, "", self._travel_bearer())
            if r.get("code") == 100105:
                r = self._signed_call_travel("GET", path, "", self._travel_bearer(True))
            _LOGGER.debug("svm urls: keys=%d code=%s body=%s",
                         len(file_keys), r.get("code"),
                         json.dumps(r, ensure_ascii=False)[:500])
            return r
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("svm urls 异常: %s: %s", type(e).__name__, e)
            return {"error": f"{type(e).__name__}: {e}"[:200]}

    # ---- 充电记录（2026-10-02 逆向）----
    # ★ 与 travel 同一根因：需要 App 头 + 主 Bearer。
    #   此前 100105「用户未登录」也是因为头/token 不对（不是缺身份机制）。

    def get_charge_records(self) -> dict:
        """充电记录（无参数）→ GET /bsp-vcp-message/v1/app/vehicle/chargeRecords"""
        return self._signed_call_travel(
            "GET", "/bsp-vcp-message/v1/app/vehicle/chargeRecords",
            "", self._travel_bearer())

    def get_charge_records_monthly(self, dt: str, charging_type: int) -> dict:
        """某月充电记录明细。

        dt: "年-月" 如 "2026-9"
        charging_type: 1=直流(DC) 2=交流(AC)（App 响应里的数字编码）
        """
        return self._signed_call_travel(
            "GET",
            f"/bsp-vcp-message/v1/app/vehicle/chargeRecords/monthly"
            f"?vin={self._vin}&dt={dt}&chargingType={charging_type}",
            "", self._travel_bearer())

    def get_travel_current_month_km(self) -> dict | None:
        """本月里程（App 首页「本月陪伴里程」同口径）。

        返回 {km, elec_km, hybrid_km, elec_kwh, fuel_l, avg_elec, avg_fuel, days}
        失败返回 None。
        """
        import datetime as _dt
        now = _dt.datetime.now()
        try:
            r = self.get_travel_monthly(now.year, now.month)
        except Exception:  # noqa: BLE001
            return None
        if r.get("code") not in (None, 0):
            return None
        d = r.get("data") or {}

        def _f(k):
            try:
                return round(float(d.get(k) or 0), 1)
            except (TypeError, ValueError):
                return None
        # ★ 2026-10-02：日明细 + 极值（App 里程能耗页的「单次最远/最低电耗/最低油耗」）
        daily = []
        for x in (d.get("dailyList") or []):
            try:
                daily.append({
                    "dayOfMonth": int(x.get("dayOfMonth") or 0),
                    "mileage": float(x.get("mileage") or 0),
                    "elecMileage": float(x.get("elecMileage") or 0),
                    "elecEnergy": float(x.get("elecEnergy") or 0),
                    "fuelConsumption": float(x.get("fuelConsumption") or 0),
                    "hybridMileage": float(x.get("hybridMileage") or 0),
                })
            except (TypeError, ValueError):
                continue
        daily.sort(key=lambda r: r["dayOfMonth"])
        # 极值：只在有行驶的日里取
        moved = [r for r in daily if (r["mileage"] or 0) > 0]
        far = max((r["mileage"] for r in moved), default=None)
        elecs = [r["elecEnergy"] / (r["mileage"] / 100.0)
                 for r in moved if r["mileage"] > 0 and r["elecEnergy"] > 0]
        fuels = [r["fuelConsumption"] / (r["mileage"] / 100.0)
                 for r in moved if r["mileage"] > 0 and r["fuelConsumption"] > 0]
        return {
            "daily": daily,
            "single_far": round(far, 1) if far else None,
            "single_elec": round(min(elecs), 1) if elecs else None,
            "single_fuel": round(min(fuels), 1) if fuels else None,
            "km": _f("travelMileage"),
            "elec_km": _f("elecMileage"),
            "hybrid_km": _f("hybridMileage"),
            "elec_kwh": _f("elecEnergy"),
            "fuel_l": _f("fuelConsumption"),
            "avg_elec": _f("avgElecEnergy"),
            "avg_fuel": _f("avgFuelConsumption"),
            "days": len(d.get("dailyList") or []),
        }

    def get_charge_current_month_kwh(self) -> dict | None:
        """本月充电量（App 充电页同口径：直流 + 交流分别取当月）。

        返回 {dc_kwh, ac_kwh, total_kwh, dc_times, ac_times}；失败返回 None。
        """
        import datetime as _dt
        now = _dt.datetime.now()
        out = {"dc_kwh": 0.0, "ac_kwh": 0.0, "dc_times": 0, "ac_times": 0}
        got = False
        for ct, pfx in ((1, "dc"), (2, "ac")):
            try:
                r = self.get_charge_monthly_stats(ct)
            except Exception:  # noqa: BLE001
                continue
            if r.get("code") not in (None, 0):
                continue
            for x in (r.get("data") or []):
                if x.get("year") == now.year and x.get("month") == now.month:
                    try:
                        out[pfx + "_kwh"] = round(float(x.get("chargingCapacity") or 0), 2)
                        out[pfx + "_times"] = int(x.get("chargingTimes") or 0)
                        got = True
                    except (TypeError, ValueError):
                        pass
                    break
        if not got:
            return None
        out["total_kwh"] = round(out["dc_kwh"] + out["ac_kwh"], 2)
        return out

    def get_charge_total_kwh(self) -> float | None:
        """累计充电量（kWh，直流+交流所有月份求和）。

        ★ 用途：给 HA 能源面板提供一个「总充电量」传感器。
          数据源是官方按月统计（天然递增 → total_increasing）。
          失败返回 None（调用方保留上次值，不写 0 以免破坏递增曲线）。
        """
        total = 0.0
        got = False
        for ct in (1, 2):
            try:
                r = self.get_charge_monthly_stats(ct)
                _LOGGER.debug("{d}ct=%s code=%s msg=%s data_len=%s",
                                ct, r.get("code"), r.get("message") or r.get("msg"),
                                len(r.get("data") or []))
                if r.get("code") not in (None, 0):
                    continue
                for x in (r.get("data") or []):
                    v = x.get("chargingCapacity")
                    if v is None:
                        continue
                    try:
                        total += float(v)
                        got = True
                    except (TypeError, ValueError):
                        continue
            except Exception as _e:  # noqa: BLE001
                _LOGGER.debug("{d}get_charge_monthly_stats(%s) 异常: %r", ct, _e)
                continue
        _LOGGER.debug("{d}total=%s got=%s", total, got)
        return round(total, 2) if got else None

    def get_charge_monthly_stats(self, charging_type: int = 1) -> dict:
        """按月充电统计（次数 + 总电量）→ .../chargeRecords/monthlyStatistics

        ★ 主 Bearer 过期会返回 100105「用户未登录」→ 自动重登一次再试。
        """
        path = ("/bsp-vcp-message/v1/app/vehicle/chargeRecords/monthlyStatistics"
                f"?vin={self._vin}&chargingType={charging_type}")
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        if r.get("code") == 100105:
            _LOGGER.info("充电统计 100105（主 Bearer 过期）→ 重新登录后重试")
            r = self._signed_call_travel("GET", path, "",
                                         self._travel_bearer(force_login=True))
        return r

    def get_vss_state(self, paths: list[str]) -> dict:
        """读取实时 VSS 信号. 返回 {path: {"value":..,"ts":..}}; 未返回的路径不含在内.

        ★ 关键: 服务端对【任一无效 path】返回 400 (invalid_path), 会导致整批失败.
        因此采用: 分批 + 失败降级(逐个重试) + 失败批次二次拆分.
        """
        tok = self._get_scoped("vss", SCOPE_VSS, AUD_VSS)
        out: dict = {}
        B = 50

        def _one_batch(batch: list[str]) -> bool:
            """返回 True 表示成功(无 400)."""
            body = json.dumps({"vin": self._vin, "paths": batch})
            try:
                resp = self._signed_call(
                    "POST", "/ssp-cloud-vss-service/mobile/vss/get-batch", body, tok)
            except LiApiError as err:
                # 400 invalid_path: 整批失败
                if "400" in str(err) or "invalid_path" in str(err):
                    return False
                # ★ 401: token 失效 —— 抛结构化异常，由外层重试
                #   （用 is_token_expired 兜住「结构化」和「旧字符串」两种）
                if is_token_expired(err):
                    raise _TokenExpired(str(err)) from err
                raise
            for it in resp.get("items") or []:
                dp = it.get("dp") or {}
                out[it["path"]] = {"value": dp.get("value"),
                                   "ts": (dp.get("tsFormat") or "")[:19]}
            return True

        def _fetch(batch: list[str], depth: int = 0) -> None:
            """容错抓取: 失败则二分, 直到定位到坏 path 并跳过.

            ★ 2026-09-24 改进（修复"VSS 批次(2)反复失败, 跳过"）：
              原逻辑：深度 >= 4 就【整批放弃】→ 44 个有效信号一起丢失。

              新逻辑：深度超限后改为【逐条尝试】——
                坏路径只有 1~2 个，逐条能救回其余 98% 的信号。
                代价：最坏情况多发 N 次请求，但只在异常批上发生。
            """
            if not batch:
                return
            if _one_batch(batch):
                return
            if len(batch) == 1:
                _LOGGER.debug("VSS path 无效, 跳过: %s", batch[0])
                return

            # ★ 深度超限 → 逐条尝试（而不是整批放弃）
            if depth >= 4:
                recovered = 0
                for one in batch:
                    if _one_batch([one]):
                        recovered += 1
                _LOGGER.info(
                    "VSS 批次(%d)二分失败，逐条尝试救回 %d/%d 个信号",
                    len(batch), recovered, len(batch))
                return

            mid = len(batch) // 2
            _fetch(batch[:mid], depth + 1)
            _fetch(batch[mid:], depth + 1)
            return

        for i in range(0, len(paths), B):
            _fetch(paths[i:i + B])
        return out

    def poll(self, paths: list[str]) -> dict:
        """coordinator 周期调用: 返回 {"vss": {path: value}, "polled_at": ...}.

        ★ 401 自动重试 (2026-09-23): VSS token 缓存可能因服务端提前失效而 401，
          此时清缓存重新换取 token 并重试一次。
        """
        # ★ 2026-09-23：重试逻辑收敛到 policy.run_with_retry（原先手写 try/except）
        state = run_with_retry(
            lambda: self.get_vss_state(paths),
            on_token_expired=self.invalidate_tokens,
            policy=POLICY_VSS,
        )
        return {"vss": state, "polled_at": time.strftime("%F %T")}

    # ---------- 车控 (2026-09-22 实测打通, pushState=5 / resultCode=0) ----------
    #
    # 完整流程:
    #   ① POST /iot-connect-manager-service/v2/wakeup   远程唤醒车机
    #   ② POST /ssp-vehicle-control-service/.../cmd/send → {"requestId": "..."}
    #   ③ GET  /ssp-vehicle-control-service/.../cmd-result/{requestId}
    #        轮询直到 pushState==5(成功) / ==7(失败)
    #
    # ⚠️ 车控会真实作用于车辆。

    # ---------- 服务器通知（MMS）----------

    def _get_mms_token(self) -> str:
        """MMS token（通知 API 用）。"""
        return self._get_scoped("mms", SCOPE_MMS, AUD_MMS, ttl=780)

    def get_notifications(
        self,
        page: int = 1,
        page_size: int = 20,
        channel_type: int = CHANNEL_NOTICE,
    ) -> list[dict]:
        """拉取服务器通知列表。

        返回通知 dict 列錨，每条含:
            requestId, messageId, title, summary, category,
            tag[], status(0=未读), sendOn(ms), action, pushId, sendBy

        ★ category='vehicle' 为车辆通知（充电完成/电量不足告警等）

        来源: /mms-api/v1-0/message  (2026-09-23 实测: 2165 条)
        """
        tok = self._get_mms_token()
        q = (f"?appId={MMS_APP_ID}&channelType={channel_type}"
             f"&pageSize={page_size}&pageNumber={page}")
        r = self._signed_call("GET", EP_MMS_MESSAGE + q, "", tok)
        data = r.get("data") or {}
        return data.get("elements") or []

    def get_unread_vehicle_notifications(self) -> list[dict]:
        """只看【未读的车辆通知】（用于告警联动）。"""
        out = []
        for m in self.get_notifications(page=1, page_size=20):
            if m.get("status") == 0 and m.get("category") == "vehicle":
                out.append(m)
        return out

    def get_notification_settings(self, user_id: str = "me") -> dict:
        """读取通知设置（含车辆通知开关）。

        返回 {"attention":1,"comment":1,"favour":1,"notice":1,"vehicle":1}
        """
        tok = self._get_mms_token()
        r = self._signed_call(
            "GET", f"{EP_MMS_NOTIFICATION}/{user_id}?appId={MMS_APP_ID}", "", tok)
        return ((r.get("data") or {}).get("categoryStatus") or {})

    def register_push_device(self, push_id: str = "", platform: int = 2) -> dict:
        """注册推送设备（订阅）。push_id 为空则用 deviceId 占位。"""
        tok = self._get_mms_token()
        body = {
            "appId": MMS_APP_ID,
            "deviceId": self._xdev,
            "pushId": push_id or (self._xdev + "_ha"),
            "platform": platform,
            "status": "1",
        }
        return self._signed_call(
            "POST", EP_MMS_DEVICE,
            json.dumps(body, separators=(",", ":")), tok)

    def get_vehicles(self) -> list[dict]:
        """获取账号名下的车辆列表（★ 2026-09-23 实测打通）。

        端点: GET /saos-vehicle-api/v2-0/vehicles/basics
              ?types=owned,transferring,authorized,inviting
              &roleIds=1,10,11,13,15&vehicleInfo=true
        audience: 7gbeHMwBPMZA5SU1b2awIo, scope: login

        返回每辆车的:
            vin, modelName, seriesName, seriesId, modelId,
            vehicleType(owned/authorized/...), vehicleRoleId,
            vehicleInfo{...}

        ★ 为什么不用 /aisp-account-api/v1-0/vehicles？
          那个接口依赖 X-CHJ-TOKEN（App 的短效 token，已过期 → 240225）。
          本接口走 IDaaS scope token，登录后即可用。
        """
        tok = self._get_scoped("saos_vehicle", SCOPE_SAOS_VEHICLE,
                               AUD_SAOS_VEHICLE, ttl=780)
        r = self._signed_call("GET", EP_SAOS_VEHICLES, "", tok)
        data = r.get("data")
        if isinstance(data, list):
            return data
        if isinstance(r, list):
            return r
        return []

    # ---------- lcp-bff-app-api 通道（★ 2026-10-01 实测新增） ----------

    def get_pnc_switch(self) -> list[dict]:
        """即插即充（Plug & Charge）开关状态。

        端点: GET /lcp-bff-app-api/user-settings/v1/user-pnc-switch/list
        audience: 3N1l45XSeMOaid2RgDLiLA, scope: login
        实测返回（2026-10-01）:
            [{"status": 10, "vin": "HLX***************",
              "vehicleNickname": "理想L6", "pictureUrl": "..."}]

        ★ 走 lcp-bff-app-api 通道 —— 该 audience 的白名单为全前缀
          `/lcp-bff-app-api`，故此通道下其余端点（充电偏好、充电记录等）
          在拿到 X-CHJ-Token 后亦可复用本方法模式。
        """
        tok = self._get_scoped("lcp_bff", SCOPE_LCP_BFF, AUD_LCP_BFF, ttl=780)
        r = self._signed_call("GET", EP_LCP_PNC_LIST, "", tok)
        data = r.get("data") if isinstance(r, dict) else None
        if isinstance(data, list):
            return data
        if isinstance(r, list):
            return r
        return []

    def get_primary_vin(self) -> str:
        """取账号名下第一辆车的 VIN（车主优先）。"""
        cars = self.get_vehicles()
        if not cars:
            return ""
        # 车主（owned）优先
        for c in cars:
            if str(c.get("vehicleType") or "") == "owned":
                vin = str(c.get("vin") or "")
                if vin:
                    return vin
        return str(cars[0].get("vin") or "")

    def wakeup(self) -> dict:
        """远程唤醒车机 (发命令前调用, 提高下发成功率)."""
        return self._signed_call(
            "POST", EP_WAKEUP,
            json.dumps({"source": "0x3B", "bizId": "0"}, separators=(",", ":")),
            self._get_mesh_token(),
        )

    def send_command_raw(self, command_key: str, command_data: dict | None = None) -> dict:
        """仅下发命令, 不轮询结果. 返回 cmd/send 的原始响应.

        结构 (实测 pushState=5 / resultCode=0):
          {"vin":..,"cmdKey":..,"cmdData":{..},"domain":"xcu",
           "jobExpire":30,"expire":30,"expireAt":now+30000,"token":"<VAT>"}
        请求头 Authorization: Bearer <MESH>。
        ★ 易错点:
          - jobExpire 必须 >= 1, 否则 400 "参数错误[jobExpire必须大于等于1]"
            (服务端只校验下界; 填 1 可成功, 但采用源码真实值 30 更保险)
          - token 必须是 VAT(token), 不是 MESH / "0" / 空 (旧代码填 "0" 会 2009)
        """
        # ★ 2026-09-28：JOB 通道命令在【发送前】就明确拒绝。
        #   理由见 ensure_job_channel_supported() 的 docstring：
        #   这些命令必然 2009，失败是静态已知的，不该浪费一次车控请求，
        #   也不该让用户看到含糊的「执行失败」。
        ensure_job_channel_supported(command_key)

        now_ms = int(time.time() * 1000)
        # ★ 长命令 (座椅加热/通风/空调) 需更长有效期:
        #   实测 remoteVehACSmartControl 用 jobExpire=30 会 ps=7 rc=空;
        #   改 900 后 [4s] ps=5 rc=0 成功。
        if command_key in LONG_RUNNING_CMD_KEYS:
            je, je_ms = LONG_CMD_EXPIRE, LONG_CMD_EXPIRE_MS
        else:
            je, je_ms = CMD_EXPIRE, CMD_EXPIRE_MS
        body = {
            "vin": self._vin,
            "cmdKey": command_key,
            "cmdData": command_data if command_data is not None else {},
            "domain": CTRL_DOMAIN,
            "jobExpire": je,
            "expire": je,
            "expireAt": now_ms + je_ms,
            "token": self._get_vat_token(),
        }
        # ★ 401 自动重试（2026-09-23）：
        #   MESH / VAT token 缓存可能被服务端提前失效，
        #   旧行为是「点两次才生效」；现在捕获 401 → 清缓存 → 重试一次。
        def _do() -> dict:
            return self._signed_call(
                "POST", EP_CMD_SEND,
                json.dumps(body, separators=(",", ":")),
                self._get_mesh_token(),
            )

        def _refresh_body() -> None:
            """重试前重算 expireAt 与 VAT token（时间已推进）。"""
            body["expireAt"] = int(time.time() * 1000) + je_ms
            body["token"] = self._get_vat_token()

        # ★ 2026-09-23：重试逻辑收敛到 policy.run_with_retry
        return run_with_retry(
            _do,
            on_token_expired=self.invalidate_tokens,
            before_retry=_refresh_body,
            policy=POLICY_COMMAND,
        )

    def get_command_result(self, request_id: str) -> dict:
        """查询单条命令的执行结果（401 自动重试）。"""
        # ★ 2026-09-23：重试逻辑收敛到 policy.run_with_retry
        return run_with_retry(
            lambda: self._signed_call(
                "GET", f"{EP_CMD_RESULT}/{request_id}", "", self._get_mesh_token()),
            on_token_expired=self.invalidate_tokens,
            policy=POLICY_RESULT,
        )

    def send_command(
        self,
        command_key: str,
        command_data: dict | None = None,
        *,
        wake: bool = True,
        poll: bool = True,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> dict:
        """下发车控命令并等待执行结果.

        返回 {"requestId","pushState","resultCode","resultMsg","cmdKey","cmdData"}。
        失败抛 LiCommandError (含 resultCode / pushState)。

        参数:
          wake  : 下发前先远程唤醒 (默认 True, 可提高成功率)
          poll  : 是否轮询 cmd-result 直到 pushState 终态
          timeout / poll_interval: 轮询上限 (默认最多 ~60s, 每 2s 一次)
        """
        if wake:
            try:
                self.wakeup()
            except LiApiError as err:  # 唤醒失败不阻断 (车辆可能已在线)
                _LOGGER.debug("唤醒失败(忽略, 继续下发): %s", err)

        resp = self.send_command_raw(command_key, command_data)
        request_id = resp.get("requestId") or resp.get("data", {}).get("requestId") or ""

        # cmd/send 自身可能在响应里直接带业务错误
        rc = resp.get("resultCode")
        if rc not in (None, 0):
            raise LiCommandError(
                f"命令下发被拒 ({command_key}): resultCode={rc} "
                f"msg={resp.get('resultMsg') or resp.get('message')}",
                request_id=request_id, result_code=rc,
            )

        if not request_id:
            raise LiCommandError(
                f"命令下发无 requestId ({command_key}): {json.dumps(resp, ensure_ascii=False)[:200]}")
        # ★ 记录命令信息，供下面的通道检测用
        self._last_cmd_key = command_key

        if not poll:
            return {"requestId": request_id, "cmdKey": command_key,
                    "cmdData": command_data or {}, "raw": resp}

        result = self._poll_result(request_id, timeout, poll_interval)
        result.update({"requestId": request_id, "cmdKey": command_key,
                       "cmdData": command_data or {}})
        ps = result.get("pushState")
        rc_final = result.get("resultCode")
        if ps == PUSH_STATE_SUCCESS:
            # pushState=5 但 resultCode=-15/-8 表示"倒计时完成", App 视为成功
            if rc_final not in SUCCESS_RESULT_CODES and rc_final is not None:
                _LOGGER.info(
                    "车控完成(非零码) %s %s rc=%s msg=%s",
                    command_key, command_data, rc_final, result.get("resultMsg"))
            else:
                _LOGGER.info("车控成功 %s %s (requestId=%s)",
                             command_key, command_data, request_id)
            return result
        if ps == PUSH_STATE_FAILED:
            # pushState=7 但 resultCode 属于成功集合 → 同样视为成功
            if rc_final in SUCCESS_RESULT_CODES:
                _LOGGER.info(
                    "车控成功(pushState=7 但 rc=%s 属成功码) %s %s",
                    rc_final, command_key, command_data)
                return result
            rc_err = result.get("resultCode")
            # ★★★ 2026-09-26：resultCode=2009 且是充电命令 → 明确提示"通道不支持"
            #
            #   逆向确认：充电走 LiveNetControlRoute.JOB（LiNdn/NDN），
            #   而 HTTP cmd/send 只支持 VEH_CONTROL 通道。
            #   给用户明确提示，而不是"点了没反应"。
            # ⚠️ 服务端可能返回字符串 "2009"（实测），必须容错比较
            try:
                _rc_int = int(rc_err) if rc_err is not None else None
            except (TypeError, ValueError):
                _rc_int = None
            if _rc_int == 2009 and _is_job_channel_command(command_key):
                raise LiChannelNotSupported(
                    f"「{command_key}」走的是理想 App 的 LiNdn（JOB）通道，"
                    f"HTTP 车控接口不支持。这是已知限制，"
                    f"充电相关控制暂不可用（状态读取正常）。"
                    f"（resultCode={rc_err}）",
                    request_id=request_id, result_code=rc_err, push_state=ps,
                )
            raise LiCommandError(
                f"命令执行失败 ({command_key}): pushState={ps} "
                f"resultCode={rc_err} msg={result.get('resultMsg')}",
                request_id=request_id,
                result_code=rc_err, push_state=ps,
            )
        # ★ 超时未终态（2026-09-23 修复）
        #   pushState=1（执行中）时服务端只是没及时置终态，但命令【可能已生效】。
        #   实测：开空调命令超时后，FOffStatus 已变为 1（车确实开了）。
        #   这种情况【不应抛错】——否则 HA 会显示"失败"而实际成功，
        #   用户会重复点击。
        #   改为：记 warning + 返回结果，由实体状态（下一次轮询）反映真实情况。
        _LOGGER.warning(
            "车控命令未在超时内进入终态 %s %s pushState=%s msg=%s "
            "（命令可能已生效，状态以下次轮询为准）",
            command_key, command_data, ps, result.get("resultMsg"))
        return result

    def _poll_result(self, request_id: str, timeout: float, interval: float) -> dict:
        """轮询 cmd-result 直到 pushState 进入终态 (5 成功 / 7 失败) 或超时."""
        deadline = time.monotonic() + timeout
        last: dict = {}
        while time.monotonic() < deadline:
            try:
                last = self.get_command_result(request_id)
            except LiApiError as err:
                _LOGGER.debug("查命令结果失败(重试): %s", err)
                time.sleep(interval)
                continue
            if last.get("pushState") in (PUSH_STATE_SUCCESS, PUSH_STATE_FAILED):
                return last
            time.sleep(interval)
        return last

    def send_command_fire_and_forget(self, command_key: str,
                                    command_data: dict | None = None) -> dict:
        """下发但不等待结果 (用于寻车等不需要确认的命令)."""
        return self.send_command(command_key, command_data, poll=False)



# ★★★★★ 实验（2026-10-02）：X-CHJ-CAFC 完整公式
#
#   smali 铁证（LXNativeRNModule.smali:6154-6400）：
#     v1  = URL.toUpperCase()
#     v28 = String.valueOf(System.currentTimeMillis())      ← 时间戳
#     salt= InternalStub.c(ApiConstants.HEADER_SALT)
#     X-CHJ-CAFC = utils/e.c( v1 + v28 + salt )             ← utils/e.c = MD5 小写 hex
#
#   ⚠️ InternalStub.c 是 native 解密，静态拿不到明文。
#      这里先用几种候选（含 base64 解码），方便一次试多组。
_HEADER_SALT = "I3uByzvBWHzGMKB5yeMfLUS9IsPx0Ct1bZqiDf+CxTk="
_CAFC_SALT_MODE = 2   # 1=原串 2=base64decode 3=去padding 4=base64decode->hex 5=空


def _cafc_salt() -> str:
    import base64 as _b
    if _CAFC_SALT_MODE == 1:
        return _HEADER_SALT
    if _CAFC_SALT_MODE == 2:
        try:
            return _b.b64decode(_HEADER_SALT).decode("latin-1")
        except Exception:
            return _HEADER_SALT
    if _CAFC_SALT_MODE == 3:
        return _HEADER_SALT.rstrip("=")
    if _CAFC_SALT_MODE == 4:
        try:
            return _b.b64decode(_HEADER_SALT).hex()
        except Exception:
            return _HEADER_SALT
    return ""


def _cafc(url: str, ts: str) -> str:
    """X-CHJ-CAFC = MD5( URL大写 + 时间戳 + 解密SALT )"""
    try:
        raw = url.upper() + ts + _cafc_salt()
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    except Exception:  # noqa: BLE001
        return ""

def _hac_key_bytes(hac_key: str) -> bytes:
    """hac_key 归一化: hex(64字符) / base64 / 原始串 → 原始 32 字节.

    ★ 2026-09-24 修复（严重 bug，导致 VIN 取不到 / 所有 API 报
      「缺少必要的请求参数: X-CHJ-Key」）：

      问题：secrets._LazySecret 是 str 子类，构造时内容为空字符串，
            真实值靠 __str__() 延迟求值。
            但 str 子类的 .strip() / len() 走的是【空内容】：
              s = (hac_key or "").strip()   →  ""   （丢了真实值！）
              len(s) == 64                  →  False
              s.encode()                    →  b""  ❌

            表现为：_hac 长度为 0 → 签名错误 → 服务端拒绝。

      修复：先显式 str() 强制求值，再做后续处理。
    """
    # ★ 关键修复（2026-09-24 第二次修正）：
    #   不能用 `hac_key or ""` —— `or` 会触发 _LazySecret.__bool__()，
    #   而它基于【底层空内容】返回 False → 直接走 "" 分支！
    #   必须用 `is not None` 判断，再 str() 强制求值。
    s = str(hac_key).strip() if hac_key is not None else ""
    if len(s) == 64:
        try:
            return bytes.fromhex(s)
        except ValueError:
            pass
    try:
        raw = base64.b64decode(s)
        if len(raw) == 32:
            return raw
    except Exception:  # noqa: BLE001
        pass
    return s.encode()


_SSL_CTX = None

def _ssl_ctx():
    global _SSL_CTX
    if _SSL_CTX is None:
        import ssl
        _SSL_CTX = ssl.create_default_context()
    return _SSL_CTX
