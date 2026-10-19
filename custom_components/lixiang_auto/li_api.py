"""理想汽车同步 API 客户端 (认证链端到端验证版, 2026-09-06).

认证链 (全部经真实请求验证, 见 docs/实时状态打通_20260906.md):
  1. PAKE 密码登录 (pake_login) → 会话 sso_token cookie (13天) + 主Bearer + refresh_token
  2. 会话 cookie POST /api/auth (response_type=token) → 各服务 scope token (15分钟)
     注意: 裸 Bearer 换不了 scope token (login_required), 必须带登录会话 cookie;
     refresh_token 续期不会重新种 cookie, 故密码是唯一的长期免维护凭据。
    ★ 2026-10-10：据此把恢复分成两档 ——
      · scope token 通道（VSS/车控/任务大师）→ 只能密码重登（cookie 不可再生）
      · 主 Bearer 通道（travel/充电明细）→ 先用 refresh_token **免密续期**
        （`_refresh_main_bearer`），失败才密码重登；续期不碰 cookie，救不了前者。
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

from homeassistant.exceptions import HomeAssistantError


from .const import (
    APP_LIXIANG,
    CONF_HAC_KEY,
    CONF_IDENTITY_SOURCE,
    CONF_KEY_ID,
    CONF_SESSION_COOKIES,
    CONF_XDEV,
    IDENTITY_SOURCE_DERIVED,
    IDENTITY_SOURCE_MANUAL,
)
from .policy import (
    POLICY_COMMAND,
    POLICY_RESULT,
    POLICY_VSS,
    TokenExpired,
    is_token_expired,
    run_with_retry,
)
from .pake_login import (
    APP_LOGIN_PARAMS,
    CredentialRejected,
    is_credential_rejection,
    APP_VERSION as LOGIN_APP_VERSION,
    BASE_ID,
    LixiangDirectLogin,
    LoginError,
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

# ★★ 2026-10-19（车主日志实证，决定性）：
#   SCOPE_MESH 上面只有 **3 项**，而官方 subTokenData 里 httpLiMeshServiceV2
#   的 scope 是 **5 项**（多 vss:get-batch 与 task-master）。
#   我们 2026-10-08 早就实测过：「单换子集被 SSO 拒绝（300 access_denied），
#   完整五件套可正常换取 —— App 从不单换，只用完整包」。
#
#   车主 18:30 的日志正是这条：
#     车控 remoteVehPlgControl 失败: 换 token 失败
#       （scope=remote-wakeup:wakeup veh-ctrl:cmd-send veh-ctrl:cmd-result-get,
#        error=access_denied）
#     ⇒ 判据已经生效（日志有「车型判据：real-time-state 含 M 系独有字段」），
#       但**取 token 这一步就被 SSO 拒了**，根本没走到 send-command。
#
#   ⇒ M 系必须用【官方完整五件套】取 MESH token。
#     （X 系保持原 3 项不变 —— 它现在能正常工作，不动它。）
SCOPE_MESH_FULL = (
    "remote-wakeup:wakeup veh-ctrl:cmd-result-get "
    "veh-ctrl:cmd-send vss:get-batch task-master")
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
# ★★ 2026-10-07 修正（真机 HAR 抓包实证，Reqable 理想 App 8.27.0）：
#   App 对同一 audience (AUD_VAT) POST /api/auth 实际请求【14 个】scope，
#   服务端 302 正常全量授权（原 12 个 + cpCtrl:<VIN> + ssCtrl:<VIN>）。
#
#   历史误判回顾（2026-09-26）：当时自己拼 14 个被服务端降级到 8 个，
#   据此得出「12 个才对」。现在看，当时多拼了 App 没有的名字
#   （ChargingControl）才是降级主因【推测】；按真机的 14 个原样请求
#   是可回退的低风险改动（最坏情况=回到现状）。
#
#   各 scope 佐证：
#     cpCtrl = 充电盖（HAR：job_key=cpCtrl 执行成功）
#     rmCtrl = 后视镜（HAR：failReason="后视镜控制完成"）
#     ssCtrl = 含义未证实（推测遮阳帘类；7 个抓包动作均未出现，
#              纯为复刻真机完整 scope 集，防整批降级）
#
# ⚠️ 名字已含完整前缀，vat_scope() 只加 ":<VIN>" 后缀。
# ⚠️ 充电【启停】没有独立 scope —— 走 JOB（NDN）路由，与 scope 无关；
#     cpCtrl 只是「充电盖」开关的 scope，不是充电控制。
VAT_SCOPE_COMMANDS = (
    "remoteVehACSmartControl", "remoteVehFrgControl", "remoteVehAuth",
    "remoteVehLockControl", "remoteVehPlgControl", "remoteVehSearch",
    "remoteVehWdwControl", "remoteVehACFirstControl",
    "remoteADCtrl", "remoteADInit", "fTkC", "rmCtrl",
    "cpCtrl", "ssCtrl",
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

#: ★ 2026-10-17：KMS 软签换长连接 JWT（见 kms_softsig 模块）
KMS_JWT_EP = "/bcs-kms-jwt/jwt/iot2/v1-0/"

EP_CMD_SEND = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send"
EP_CMD_RESULT = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd-result"
EP_WAKEUP = "/iot-connect-manager-service/v2/wakeup"
CTRL_DOMAIN = "xcu"

# ══════════════════════════════════════════════════════════════════════════
#  ★★★ 2026-10-12：App 的**权威车控配置表**（第二轮逆向的重大修正）
# ══════════════════════════════════════════════════════════════════════════
#
#  来源：assets/2025/LXMVehicleConfig2025.json —— 70 条 LXVehicleControlType*，
#  每条给出 sendUrl / verificationUrl / skipVerification / successfulCode 等。
#
#  ★ 为什么重要：此前本项目只认一条 HTTP 车控路径（cmd/send），并把
#    「充电 / 哨兵 / 拍照」归为「走 JOB 长连接、HTTP 不可达」。
#    **该结论是错的** —— App 对这些功能有另一套 HTTP 端点：
#
#    · send-command（70 条里 65 条走它，**含充电启停/哨兵/拍照**）
#        POST /ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command
#        body: OperateReq{vin, commandKey, commandData, commandDataLi,
#                         safetyToken?, taskId?}
#        → operationId，再轮询 verificationUrl 取结果
#        GET  /ssp-as-mobile-api/v1-0/remote-vehicle-control/{vin}/command/{opId}/result
#
#    · 3 条**同步** API（skipVerification=1，一次调用直接拿结果，无需轮询）：
#        POST /ssp-as-mobile-api/v1-0/vehicles/charge-threshold-update {vin, threshold}
#        POST /ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch   {vin, switchState}
#        POST /ssp-as-mobile-api/v1-0/vehicles/ac-appointment-update {...}
#
#  注意：cmd/send 仍然存在且仍走 JOB —— 只是它**不是**这些功能的唯一通道。
EP_RVC_SEND = "/ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command"
EP_RVC_RESULT = (
    "/ssp-as-mobile-api/v1-0/remote-vehicle-control/{vin}/command/{op_id}/result")
EP_CHARGE_THRESHOLD = "/ssp-as-mobile-api/v1-0/vehicles/charge-threshold-update"
EP_BATTERY_WARM = "/ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch"
EP_AC_APPOINTMENT = "/ssp-as-mobile-api/v1-0/vehicles/ac-appointment-update"
#: ★ 2026-10-18：预约充电（M 系专属，取证自 NetApiConst.chargeAppointmentUpdate）
EP_CHARGE_APPOINTMENT = "/ssp-as-mobile-api/v1-0/vehicles/charge-appointment-update"
EP_SVM_TAKE_PHOTO = "/ssp-as-mobile-api/v1-0/vehicles/svm/take-photo"
EP_OTA_UPGRADE = "/ssp-as-mobile-api/v1-0/vehicles/ota/upgrade"
EP_MAINT_PLAN = "/ssp-as-mobile-api/v1-0/vehicles/maint/plan/"
EP_MAINT_RESET = "/ssp-as-mobile-api/v1-0/vehicles/maint/item/reset"
EP_TIRE_ALARM = "/ssp-as-mobile-api/v1-0/vehicles/tire/alarm/"

#: 权威配置表里的成功 / 失败码（70 条命令一致）
RVC_SUCCESS_CODE = "5"
RVC_FAILURE_CODE = "7"
#: send-command 的结果轮询上限（配置表 expireAt=30s）
RVC_POLL_TIMEOUT = 30.0
RVC_POLL_INTERVAL = 1.0

#: 充电上限的取值范围 —— App 的滑块是 80~100（步进 1）。
#  ★ 2026-10-12：从 number.py 搬到这里，供 li_api.set_charge_threshold 复用；
#    number.py 改为 import 本模块的常量（避免两处各写一份而漂移）。
CHARGE_MIN = 80
CHARGE_MAX = 100
CHARGE_STEP = 1


def _as_text(value) -> str:
    """安全转字符串（只把 None 当空）。

    ★ 不要用「取值或空串」的写法（把 `or ""` 跟在原值后面）——
      项目里的 `_LazySecret` 是惰性凭据对象，那种写法会对它取到空值，
      `tests/test_secrets.py` 有守卫专门抓这类模式。
      这里只判 None；其余值（含 0 / False / 空串）都正常转成字符串。
    """
    return "" if value is None else str(value)


def _control_permission_hint(api_self) -> str:
    """车控失败时，若【确定不是车主账号】→ 给出准确原因（否则返回 ""）。

    ★ 2026-10-18（理想ONE 家人账号实测发现的【误导】）：
      家人账号（`vehicleType=authorized` / `vehicleRoleId=15`）发车控时，
      `cmd/send` 返回的是 **HTTP 503「服务暂时不可用」** ——
      但真实原因不是服务端故障，而是**服务端按账号角色拒绝**
      （同一辆车走 `send-command` 通道会明确报 `241000 用户没有权限`）。

      若不改述，用户会以为「等会儿再试」——实际上等也没用，必须换车主账号。
      这与 App 一致：App 对家人账号同样不开放车控。
    """
    try:
        from .vehicle_role import REL_OWNER, relation_of

        veh = api_self.get_vehicles() or []
        rel = relation_of(veh[0] if veh else None)
        if rel in (None, 0, REL_OWNER):
            return ""            # 车主 / 无法判定 → 不猜，保持原错误
        return ("当前是【家人/授权账号】，服务端按角色限制不允许远程车控"
                "（用车主账号即可；App 对家人账号同样不开放车控）。"
                "注：cmd/send 对此返回 HTTP 503「服务暂时不可用」，并非服务端故障。")
    except Exception:  # noqa: BLE001
        return ""


def _first_of(payload, *names: str):
    """从响应里按顺序取第一个存在的键值（容错不同后端字段命名）。

    新通道的响应字段名未在真机确认，故对 operationId/taskId/opId/id 等
    常见命名做一次探测；取不到返回 None，由调用方决定如何降级。
    """
    if not isinstance(payload, dict):
        return None
    for n in names:
        v = payload.get(n)
        if v not in (None, ""):
            return v
    # 有些实现把结果放在 data / result 里
    for nest in ("data", "result", "body"):
        inner = payload.get(nest)
        if isinstance(inner, dict):
            for n in names:
                v = inner.get(n)
                if v not in (None, ""):
                    return v
    return None

# ---------- 任务大师（2026-10-07 真机抓包实证：全 HTTP，非 JOB 通道）----------
# 白名单: subTokenData → type=httpLiMeshServiceV2:
#   urls 含 /ssp-task-master-service, 同条目 scope 含 "task-master"
# 鉴权: HZ 级 token (scope=task-master) + _signed_call 的 x-chj-* 签名头
#   （抓包实测: Authorization: Bearer HZ:… + X-CHJ-Sign / X-CHJ-TOKEN）
# ★ 2026-10-08 实测：单换 "task-master" 被 SSO 拒绝
#   （POST /api/auth → HTTP 300 {"location":"…app-auth?error=access_denied"}），
#   完整五件套可正常换取 —— 与 App 行为一致（App 从不单换，只用完整包）。
#   故固定使用 App subTokenData → httpLiMeshServiceV2.scope 的权威 5 项：
#   remote-wakeup / cmd-result / cmd-send / vss / task-master。
SCOPE_TASK_MASTER = (
    "remote-wakeup:wakeup veh-ctrl:cmd-result-get "
    "veh-ctrl:cmd-send vss:get-batch task-master")

# 任务接口专用头（对照 2026-10-07 抓包；travel 接口同款教训：
# 默认头会被拒，必须照抄 App 头并同步重签——签名覆盖第 7 段语言字段）
TASK_APP_VERSION = "8.27.0"            # x-chj-app-version / x-chj-version
TASK_UA = "M01/8.27.0 (Xiaomi; 16)"    # user-agent
TASK_DEVICE_MODEL = "23127PN0CC"       # x-chj-devicemodel（真机型号）
TASK_META = '{"language":"zh","code":"102004"}'  # x-chj-metadata（travel 同款）

# ★ 2026-10-11 实测更正：字典接口路径**必须带 /v1/**，漏掉会返回
#   100012「没有接口访问权限」（与"无权限"无法区分，容易误判成路径错）。
#   该接口在 APK 里搜不到任何字符串（连上面这条正在用的 task-config 也搜不到）
#   → 路径本身也由服务端配置下发，逆向拿不到，只能运行时调。
EP_TASK_DICT = "/ssp-task-master-service/v1/task-basic/mob/condition-and-action/{vin}"

EP_TASK_LIST = "/ssp-task-master-service/v1/task-config/mob/my-task-by-vin/{vin}"
EP_TASK_SAVE = "/ssp-task-master-service/v1/task-config/mob/save/{vin}"
EP_TASK_UPDATE = "/ssp-task-master-service/v1/task-config/mob/update-task/{vin}"
EP_TASK_DELETE = "/ssp-task-master-service/v1/task-config/mob/delete/{vin}/{config_id}"

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
# ★ 2026-10-07 新增 rmCtrl (后视镜加热, APK 实证):
#   App 侧 REAR_MIRROR_HEAT_DURATION=660000ms (11 分钟), 与空调同属
#   长有效期命令 —— 用默认 30s 有超时风险, 按 900 覆盖 (>=660)。
LONG_RUNNING_CMD_KEYS = {
    "remoteVehACSmartControl",   # 空调/座椅/方向盘加热/除霜
    "rmCtrl",                    # 后视镜加热 (App TimeOut=660s)
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


def build_task_payload(
    config_name: str,
    conditions: list,
    actions: list,
    *,
    config_id: str | None = None,
    automate: bool = True,
    voice_execute: bool = False,
    run_once: bool = False,
    run_once_frequency: str = "2",
    enabled: bool = True,
) -> dict:
    """构造任务大师 save 请求体（字段与 2026-10-07 真机抓包逐字段一致）。

    抓包样本（POST /task-config/mob/save/{VIN}）:
      {"configName","configId","automate","voiceExecute","runOnceFrequency",
       "runOnce","taskValue":{"conditions":[...],"actions":[...]},"enabled"}

    configId 由客户端生成：``mob_<13位毫秒>``（样本 mob_1791366893482）。
    conditions/actions 为字典数组，结构见 condition-and-action 字典接口
      （GET /task-basic/mob/condition-and-action/{VIN}，15 条件/17 动作）。
    """
    if not config_name or not str(config_name).strip():
        raise ValueError("任务名称 (name) 不能为空")
    if conditions is None:
        conditions = []
    if not isinstance(conditions, list):
        raise ValueError("conditions 必须是列表")
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions 必须是非空列表")
    return {
        "configName": str(config_name).strip(),
        "configId": config_id or f"mob_{int(time.time() * 1000)}",
        "automate": bool(automate),
        "voiceExecute": bool(voice_execute),
        "runOnceFrequency": str(run_once_frequency),
        "runOnce": bool(run_once),
        "taskValue": {"conditions": conditions, "actions": actions},
        "enabled": bool(enabled),
    }


def _ensure_task_ok(op: str, resp) -> None:
    """任务大师接口成功判定（抓包响应: {"message":"SUCCESS","code":0,"success":true}）。"""
    if isinstance(resp, dict) and (resp.get("code") in (0, "0") or resp.get("success")):
        return
    raise LiApiError(f"任务大师{op}失败: {str(resp)[:200]}")


def is_signature_error(err_or_payload) -> bool:
    """签名错误判定（100005 / 「签名错误」文案）。

    ★ 必须认两种形态（实测都有）：
      · HTTP 非 2xx → _signed_call 抛 LiApiError，错误文本里带 100005；
      · HTTP 200 但 body 是 {"code": 100005, ...} —— 服务端把签名错误
        当业务码返回，此时不会抛异常，调用方只会拿到「空 items」。
    """
    if isinstance(err_or_payload, dict):
        raw = err_or_payload.get("code")
        try:
            if raw is not None and int(raw) == 100005:
                return True
        except (TypeError, ValueError):
            pass
        text = json.dumps(err_or_payload, ensure_ascii=False)
    else:
        text = str(err_or_payload)
    return "100005" in text or "签名错误" in text


def _exchange_client_order(app_type: str, win: str | None) -> list[str]:
    """决定 /api/auth 的 client 参数尝试顺序（2026-10-10 实测对照矩阵）。

    · 常规：先登录身份（app_type），被拒回退主 App client（"lixiang"）
      —— saos_vehicle(7gbe) 白名单只认主 client（A/C ❌ → B/D ✅ 实测）；
      VSS 等 audience 在 livis client 下已通，不能一刀切全用主 client。
    · 记忆胜出：win = 该账号上次换取成功的 client key → 直接置顶。
    · app_type=lixiang 时主 App 即第一选择，顺序无冗余。
    """
    primary = app_type or APP_LIXIANG
    if primary not in APP_LOGIN_PARAMS:
        primary = APP_LIXIANG
    order: list[str] = []
    for k in (win, primary, APP_LIXIANG):
        if k and k in APP_LOGIN_PARAMS and k not in order:
            order.append(k)
    return order


def _is_scope_denied(err) -> bool:
    """换取 scope 被服务端策略拒绝（≠ 会话失效，不应触发重登）。

    实测 2026-10-08：单 scope task-master → HTTP 300 access_denied；
    若误判为会话失效会走 _login()（其内 _tokens.clear()）→ 每分钟
    「重登+清全缓存」风暴（真机 87 次/1.5h）。

    ★ 2026-10-08 二次修正（真机故障实证）：**不能只看 "HTTP 300"**。
    HTTP 300 有两种语义完全不同的情况：

      · `300 + access_denied`  → scope 被策略拒绝 → 重登无用，直接抛
      · `300 + login_required` → 会话失效 → **必须重登**，否则永久失效

    此前用 `"HTTP 300" in m` 一刀切，把 login_required 也判为 scope 拒绝
    → `_get_scoped` 永不重登 → 通知/VSS/任务大师全部持续失败且**无法自愈**
    （真机 22:33 起每 30~60s 失败一次，持续十余分钟仍未恢复，只能手动重载）。
    故此处仅以 access_denied 为准，并显式排除 login_required。
    """
    m = str(err)
    if "login_required" in m:
        return False          # 会话失效 → 允许走重登分支
    return "access_denied" in m or "HTTP 300" in m


def _is_session_loss(err) -> bool:
    """换取失败的**唯一**重登判据：错误是否真的表示「登录会话失效」。

    ★ 2026-10-10（真机取证）：此前 `_get_scoped` 把**任何** LiApiError 都当
      会话失效 → 5xx、空响应、响应格式异常都会白白触发一次 `_login()`。
      而**每次密码登录都可能把手机上已登录的 App 顶下线**（用户实测），
      所以「不该重登时重登」是有实际代价的。

    判据来自实测形态：
      · `300 + login_required` → 会话失效 → 必须重登（见 _is_scope_denied 注释）
      · `100105 / 用户未登录`   → 会话失效（主 Bearer 路径的已知业务码）
      · HTTP 401               → 会话失效
      · 其它（5xx / 空响应 / 解析异常）→ **与会话无关** → 原样抛出交给上层重试
    """
    m = str(err)
    low = m.lower()
    return ("login_required" in low
            or "100105" in m
            or "用户未登录" in m
            or "http 401" in low)


def _is_unauthorized(err) -> bool:
    """业务调用返回 401（token 被服务端拒绝）→ 应失效缓存重取，而非重登。

    ★ 2026-10-08 真机实测：任务接口 401 连续 147 次（10:07→20:52，跨 10 小时）。
    token 缓存 ttl=1800s 在正常情况下不会失效 → 每 60s 重试都复用同一个
    被拒 token，必须等到 ttl 到期才重新换取，故障恢复被严重拖慢。
    """
    m = str(err)
    return "HTTP 401" in m or "Unauthorized" in m


#: 充电类型 → 字段前缀。来源：App bundle `chargingType === 1/2/3/4`
#: 与 I18N 文案（chargingTypeDC / chargingTypeAC / chargingTypeSC / chargingType4CAnd5C）。
#:
#: ★ 2026-10-08：统计「本月充电量 / 累计充电量」必须遍历**全部 4 种**——
#:   此前只用 1+2，漏掉 5C超充 与 **理想超充**，真机实测少算 53.19 kWh/月。
CHARGE_TYPE_PREFIX: tuple[tuple[int, str], ...] = (
    (1, "dc"),    # DC  直流快充
    (2, "ac"),    # AC  交流慢充
    (3, "sc"),    # SC  5C 超充
    (4, "hpc"),   # 4CAnd5C 理想超充
)


class LiApiError(HomeAssistantError):
    """理想 API 认证/请求错误.

    ★ 2026-10-07：基类由 RuntimeError 改为 HomeAssistantError ——
      所有车控/HTTP/通道错误冒泡到 HA 前端时显示真实文案
      （如 "pushState=7 resultCode=-3 msg=执行失败"），
      而不是笼统的「Unexpected exception」。
      （代码库内只按 LiApiError 子类捕获，无按 RuntimeError 捕获，改基类安全。）
    """


# ---------------------------------------------------------------------------
# JOB 通道命令判定（2026-09-26）
# ---------------------------------------------------------------------------
# 逆向来源：LiveNetControlRouter.resolveRoute()
#   destParams 含 "mob.vehCtrlService.vehCtrlJobList" → VEH_CONTROL（HTTP cmd/send）
#   否则（mob.metaJobService.* 等）                    → JOB（LiNdn/NDN）
#
# ★ destParams 权威表：XVehicleJobHelper.commandDestParamsMap（APK 反编译 2026-10-07）：
#     充电 → mob.metaJobService.remoteChargingControl
#     哨兵 → mob.metaJobService.sentinelModeSetting   ← HTTP 真机实测 2009
#     拍照 → mob.metaJobService.mobileVehSvm          ← HTTP 真机实测 2009
#     推流 → mob.metaJobService.mobileVehSvm（同表）
#   → 这些 command_key 用 HTTP 发必然 2009。
_JOB_CHANNEL_COMMANDS = frozenset({
    # ---- 充电控制（已实测 2009）----
    "remote_charge_control",          # 启停 / 上限 / 保温 / 预约
    "remote_charging_start",
    "remote_charging_stop",
    "remoteChargingControl",
    "chargeLimit",
    # ---- 哨兵 / 远程拍照（2026-10-07 真机实测 2009 + APK destParams 实证）----
    "sentinelModeSetting",            # 哨兵模式开关
    "mobileVehSvm",                   # 驻车/远程拍照
    "mobileVehPushStream",            # 推流（destParams 与 SVM 同表）
    "mobileVehCloseStream",
    # ---- 未实测但有同样特征（destParams 走 metaJob）----
    "MoveOffAdd",                     # 按时出发
    "MoveOffModify",
    "ReserveFridgeData",              # 冰箱预约
    "sceneModeCtrl",                  # 场景模式
})
# ⚠️ 历史误判记录（2026-10-07 修正）：
#   本表注释曾把 sentinelModeSetting 与 "remoteVehSvm" 列为「HTTP 实测能用」
#   的反面例证。用户真机实测 mobileVehSvm 返回 pushState=7 resultCode=2009，
#   且 APK destParams 表证明哨兵/拍照均走 metaJobService 路由；
#   "remoteVehSvm" 本身也不是真实 cmdKey（真实值 mobileVehSvm）。已按实证修正。


def _is_job_channel_command(command_key: str) -> bool:
    """判断命令是否走 JOB（LiNdn）通道（HTTP 不支持）。"""
    key = str(command_key) if command_key is not None else ""
    return key in _JOB_CHANNEL_COMMANDS


#: ★ 统一文案：供【所有】走 JOB 通道的实体复用（充电/哨兵/拍照…）。
#:   实体在 extra_state_attributes 里暴露它，并在写入时抛出，保证
#:   「用户看到的提示」与「实际抛出的错误」逐字一致。
#:   （文案须保留 "LiNdn" 与 "不支持" 关键词 —— 有测试断言。）
JOB_CHANNEL_NOTICE = "该命令走理想 App 的 LiNdn（JOB）通道，当前版本不支持控制"

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


#: 服务端 resultCode → 人话（★ 真车实测，msg 由服务端直接给出）
#: 只收录**实测见过**的；未收录的回落到服务端 msg，不猜。
RESULT_CODE_HINTS = {
    -1:  "车辆当前状态不支持该操作",
    -2:  "车辆侧未执行（信号设置失败，请检查车辆状态后重试）",   # ★ 2026-10-12 实测 cpCtrl
    -3:  "操作被拒绝（可能车辆未熄火或状态不满足）",
    -4:  "车辆已启动，不支持远程控制",   # ★ 实测：READY / 通电 / 启动 均为此码
    -51: "闭锁失败，主驾有人，请稍后再试",  # ★ 实测
}

class LiCommandError(LiApiError):
    """车控命令执行失败 (含服务端 resultCode / pushState)."""

    def __init__(self, message: str, *, request_id: str = "",
                 result_code: int | None = None, push_state: int | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.result_code = result_code
        self.push_state = push_state


def label_command_error(label: str, err: BaseException) -> BaseException:
    """给车控错误补上「是哪个部件」（★ 2026-10-12）。

    背景
    ----
    车主点「充电盖」开关失败，HA 只显示：
        「命令执行失败 (cpCtrl): pushState=7 resultCode=-2 msg=执行失败（set signal err!）」
    —— 用户看不出是哪个功能、为什么。

    App 那边显示的是「充电口盖已开启，请前往手动关闭」。查清了它的来源：
      · **部件名**来自 VSS 路径表 —— 实测
        ``spec_X01-VSS-Path_148.json`` 里
        ``Vehicle.Body.DoorSwitchStatus.ChrgPorLidStsV2.description``
        = "充电口盖开启状态新信号"
      · **提示模板**来自 RN bundle 的 Hermes 字符串表（UTF-16 存储，
        所以按 UTF-8 搜不到）——"请前往手动关闭"
      · 完整句子在 APK 里**不存在** → App 是**两段拼接**出来的

    我们不需要为此引入那张 541 KB 的 VSS 表 —— 实体名本身就是中文。
    这里只做「实体名 + 原始错误」的拼接，并**保留 result_code/push_state**
    （自动化里常用它们做判断，不能因为换了个消息就丢掉）。
    """
    if not label:
        return err
    msg = f"{label}：{err}"
    if isinstance(err, LiCommandError):
        try:
            return type(err)(msg, request_id=err.request_id,
                             result_code=err.result_code,
                             push_state=err.push_state)
        except Exception:  # noqa: BLE001
            # 子类构造签名不同 → 退化为基类，但仍保留关键字段
            return LiCommandError(msg, request_id=err.request_id,
                                  result_code=err.result_code,
                                  push_state=err.push_state)
    return err


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
        main_bearer: str = "",
        on_token_update=None,
        app_type: str = APP_LIXIANG,
        identity_source: str = "",
        session_cookies: list | None = None,
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
        # ★ 2026-10-10 身份迁移：来源标记为空 = v1.4.7 之前建的老条目
        #   （身份来自已删除的内置抓包值）→ 下次拿到新鲜会话时迁移。
        self._identity_source = (
            str(identity_source) if identity_source is not None else "")
        self._identity_dirty = False      # 身份有变更待回写 entry
        self._sig_recover_ts = 0.0        # 签名错误自愈的冷却时间戳
        self._app_token = str(app_token) if app_token is not None else ""
        # ★ 2026-10-18：缓存最近一帧信号，供「预约充电开关」这类需要
        #   "读当前模式/时间 → 只改开关位" 的同步写接口使用
        #   （否则会把用户已设的预约时间清空）。
        self._last_vss: dict = {}
        # ★ 2026-10-19：最近一帧 real-time-state（M 系车型指纹来源）
        self._last_rts: dict = {}
        # ★ 主 Bearer（PAKE 登录后的 access_token）—— travel 等接口需要（App 抓包 x-chj-token = APP-xxx）
        # ★ 2026-10-10：main_bearer 也要能从 entry 复用（此前恒为空 →
        #   travel/充电 首次调用必然密码重登）
        self._main_bearer: str = str(main_bearer) if main_bearer else ""
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
        # ★ 登录身份来源（lixiang=理想汽车 / livis=理想同学，仅日志标识用）
        self._app_type = str(app_type) if app_type else APP_LIXIANG
        # ★ 2026-10-10：该账号上次换取胜出的 client key（access_denied 回退后记忆）
        self._exchange_client_win: str | None = None
        # ★ 2026-10-10：持久化的登录会话 cookie（重启复用，避免每次都密码登录顶号）
        self._session_cookies: list = list(session_cookies or [])
        self._cookies_dirty = False

    # ---------- 身份迁移 / 签名错误自愈（★ 2026-10-10）------------------

    #: 签名错误自愈冷却（秒）—— 历史教训：无守卫的重登/重试会变成
    #  每分钟风暴（实测 87 次/1.5h，有账号风控风险），必须节流。
    SIG_RECOVER_COOLDOWN = 600.0

    def _identity_needs_migration(self) -> bool:
        """当前身份是否应迁移为「本设备现场派生」的身份。

        ★ 判据是【来源标记】而不是比对旧内置值 —— 后者等于把抓包身份
          再写回代码里，正是「去 iPad 化」要避免的。
            · derived → 已是本设备派生身份，跳过
            · manual  → 用户在手动流程里自填四件套，尊重其选择，不动
            · 标记缺失 → v1.4.7 之前建的老条目（身份=内置抓包值）→ 迁移
        """
        return self._identity_source not in (
            IDENTITY_SOURCE_DERIVED, IDENTITY_SOURCE_MANUAL)

    def _migrate_identity_if_needed(self, reason: str) -> bool:
        """把老条目的内置抓包身份迁移成本设备派生身份。

        ★ 触发时机：PAKE 登录成功之后 —— 只有这时主 Bearer 一定新鲜，
          而 keySuite 派生必须带有效 Bearer（别处触发可能因过期而失败）。
        ★ 失败绝不破坏现状：保留旧身份、只告警，下次登录再试。
        """
        if not self._identity_needs_migration():
            return False
        xdev = str(self._device_id or self._xdev or "")
        bearer = self._main_bearer
        if not xdev or not bearer:
            _LOGGER.warning(
                "身份迁移跳过（缺设备号或 Bearer）: xdev=%s bearer=%s",
                bool(xdev), bool(bearer))
            return False
        try:
            from .key_suite import derive_identity
            hac_hex, key_id = derive_identity(self._app_type, xdev, bearer)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("身份迁移失败（保留原身份，下次登录重试）: %s", err)
            return False
        self._hac = _hac_key_bytes(hac_hex)
        self._key_id = str(key_id)
        self._xdev = xdev          # ★ 与登录设备对齐（v1.4.7：PAKE/签名/exchange 三者一致）
        self._identity_source = IDENTITY_SOURCE_DERIVED
        self._identity_dirty = True
        self._tokens.clear()
        self._notify_token_update()
        _LOGGER.info("签名身份已迁移为本设备派生身份（reason=%s, xdev=%s…）",
                     reason, xdev[:12])
        return True

    def _recover_signature_error(self) -> bool:
        """签名错误（100005）后的自愈：迁移身份或重登拿新 Bearer。

        带冷却节流：同一客户端 10 分钟内只尝试一次，避免风暴。
        返回 True 表示状态已变（调用方可重试请求一次）。
        """
        now = time.monotonic()
        if (now - self._sig_recover_ts) < self.SIG_RECOVER_COOLDOWN:
            return False
        self._sig_recover_ts = now

        # ① 老身份 → 先用现有 Bearer 迁移（迁移成功即换了签名身份）
        if self._identity_needs_migration() and self._migrate_identity_if_needed(
                "signature_error"):
            return True
        # ② 仍需修复且持有密码 → 重登一次（_login 内部会再尝试迁移）
        if self._password:
            try:
                _LOGGER.info("签名错误自愈：重新登录")
                self._cli = None
                self._login()
                return True
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("签名错误自愈失败（重登异常）: %s", err)
                return False
        return False

    # ---------- 登录会话 ----------

    def _login(self) -> None:
        """PAKE 密码登录, 建立 sso_token 会话 (cookie 13 天有效)."""
        # ★ 2026-10-02 修正：必须用 _xdev（与签名头 X-CHJ-Deviceid 同一个），
        #   否则服务端认为「token 来自别的设备」→ 100105 用户未登录。
        cli = LixiangDirectLogin(device_id=self._xdev or self._device_id,
                                 debug=False, app_type=self._app_type)
        try:
            tok = cli.login(self._phone, self._password)
        except LoginError as err:
            # ★ 2026-10-10：凭据被拒（账号/密码变更）→ 转成结构化异常，
            #   由 coordinator 转成 ConfigEntryAuthFailed，让 HA 自动弹出
            #   「需要重新认证」，而不是让用户面对一句含糊的「连接异常」。
            if is_credential_rejection(err):
                detail = str(getattr(err, "detail", "") or "")
                raise CredentialRejected(
                    getattr(err, "step", "login"),
                    getattr(err, "status", 401), detail) from err
            raise
        if not tok.get("access_token"):
            raise LiApiError("登录成功但无 access_token")
        self._cli = cli
        # ★ 保存主 Bearer：travel/陪伴里程接口用（此前只存 refresh_token → travel 120001）
        self._main_bearer = str(tok.get("access_token") or "")
        # ★★★ 2026-10-17（理想 ONE 实车定位出的重大 bug）：
        #   `X-CHJ-Token` 请求头此前一直取 self._app_token —— 那是【配置条目里
        #   上次保存的旧值】，而登录后只更新了 _main_bearer（Authorization 头）。
        #   两者不同步 → 车机网关（尤其 M01 / as-mobile 域）判定会话过期：
        #       240225 账号登录已过期，请重新登录
        #   实测（同账号、同一份登录会话，只改这个头）：
        #       X-CHJ-Token = 旧 entry 值 → 240225
        #       X-CHJ-Token = 登录返回值  → code=0 SUCCESS（23 字段真实车况）
        self._app_token = self._main_bearer
        self._refresh_token = tok.get("refresh_token", "") or self._refresh_token
        self._tokens.clear()
        # ★ 2026-10-10：把本次建立的会话 cookie 存下来（下次启动直接复用）
        _cookies = cli.export_session_cookies()
        if _cookies and _cookies != getattr(self, "_session_cookies", []):
            self._session_cookies = _cookies
            self._cookies_dirty = True
        self._notify_token_update()
        _LOGGER.info("li_api PAKE 登录成功 (device_id=%s, app_type=%s)",
                     self._device_id, self._app_type)
        # ★ 2026-10-10：老条目的内置身份在此迁移（此时 Bearer 最新鲜）。
        #   非老条目（已派生/手填）直接跳过，不产生额外请求。
        self._migrate_identity_if_needed("login")

    def set_last_vss(self, vss: dict | None) -> None:
        """coordinator 每轮轮询后回填最近一帧信号（供同步写接口读当前值）。"""
        self._last_vss = vss or {}

    def _notify_token_update(self) -> None:
        """把最新 token 交给回调（由集成侧写入 config entry 持久化）。

        回调失败不影响主流程（token 已在内存中可用）。
        """
        cb = getattr(self, "_on_token_update", None)
        if not cb:
            return
        patch = {
            "refresh_token": self._refresh_token,
            "main_bearer": self._main_bearer,
            "access_token": self._main_bearer,
            # ★ 2026-10-17：X-CHJ-Token 用的就是它，不同步会 240225（见 _login 注释）
            #   getattr 容忍半初始化实例（与 _cookies_dirty / _main_bearer 同风格）
            "app_token": getattr(self, "_app_token", ""),
        }
        # ★ 2026-10-10：会话 cookie 变化时回写（重启复用会话，少一次密码登录）
        #   getattr 与 _main_bearer / _on_token_update 同风格：容忍半初始化实例
        if getattr(self, "_cookies_dirty", False):
            patch[CONF_SESSION_COOKIES] = getattr(self, "_session_cookies", [])
            self._cookies_dirty = False
        # ★ 2026-10-10：身份被迁移/派生刷新时才回写身份字段。
        #   只在「有变化」时带，避免把手工流程用户自填的四件套
        #   被归一化后覆盖写回（dirty 标记见 _migrate_identity_if_needed）。
        if self._identity_dirty:
            patch.update({
                CONF_HAC_KEY: self._hac.hex(),
                CONF_KEY_ID: self._key_id,
                CONF_XDEV: self._xdev,
                CONF_IDENTITY_SOURCE: self._identity_source,
            })
            self._identity_dirty = False
        try:
            cb(patch)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("token 回写回调失败（不影响运行）: %s", err)

    def _ensure_session(self) -> LixiangDirectLogin:
        """保证登录会话可用（★ 优先复用已持久化的登录会话）。

        ★ 2026-10-10：会话 cookie 有 13 天有效期，此前只活在内存里 →
          每次启动/会话丢失都重新做一次**密码登录**，而每次密码登录都可能
          把手机上的「理想汽车」App 顶下线（用户实测）。
          现在先装载上次存下的 cookie；若 cookie 全部过期或服务端已不认，
          后续换取失败会走既有的「会话失效 → 密码重登」路径（fail-safe：
          最坏情况与改动前完全一致）。
        """
        if self._cli is not None:
            return self._cli
        if self._session_cookies:
            cli = LixiangDirectLogin(
                device_id=self._xdev or self._device_id,
                debug=False, app_type=self._app_type)
            loaded = cli.import_session_cookies(self._session_cookies)
            if loaded:
                self._cli = cli
                _LOGGER.info(
                    "复用持久化的登录会话（装入 %d 个 cookie，未做密码登录）", loaded)
                return cli
            _LOGGER.debug("持久化的会话 cookie 已全部过期，改走密码登录")
        self._login()
        return self._cli

    def _exchange(self, scope: str, audience: str) -> str:
        """用登录会话 cookie 换 scope token (response_type=token).

        ★ 2026-10-10 client 参数回退（实测对照矩阵 B/D ✅ vs A/C ❌）：
          audience↔client 是白名单配对 —— saos_vehicle(7gbe) 只认主 App client，
          而 VSS 等 audience 在 livis client 下本来就通（集成日志实证）。
          故不能一刀切：先按登录身份（app_type）取参，仅当被服务端
          access_denied 时回退主 App client 重试一次；回退成功后该实例
          记忆胜出参数，后续换取直接使用（避免每次先撞一次失败）。

        ★ 去掉 offline_access（2026-10-10 实测 B 组）：不带照样换到 token，
          且不签发无人使用的 refresh_token —— 对主 App 凭据零接触。
        """
        cli = self._ensure_session()
        order = _exchange_client_order(self._app_type, self._exchange_client_win)
        last_err: LiApiError | None = None
        for idx, key in enumerate(order):
            try:
                tok = self._do_exchange(cli, key, scope, audience)
            except LiApiError as err:
                last_err = err
                # 仅 access_denied 才值得换 client 重试（网络错/参数错换也没用）
                if "access_denied" in str(err) and idx < len(order) - 1:
                    _LOGGER.info(
                        "换token被拒(%s, client=%s)，回退 %s 重试",
                        scope, key, order[idx + 1])
                    continue
                raise
            if key != order[0]:
                # 记忆胜出参数：该 audience 下次直接用回退后的 client
                self._exchange_client_win = key
                _LOGGER.debug(
                    "换token胜出参数已记忆: aud=%s client=%s", audience, key)
            return tok
        raise last_err if last_err else LiApiError(f"换 token 失败 ({scope})")

    def _do_exchange(self, cli, client_key: str,
                     scope: str, audience: str) -> str:
        """单次 /api/auth 换取（client 参数由 client_key 指定，失败抛 LiApiError）。"""
        # ★ client_id/redirect_uri：lixiang=主 App，livis=理想同学独立 client
        client_id, _, redirect_uri = (
            APP_LOGIN_PARAMS.get(client_key) or APP_LOGIN_PARAMS["lixiang"]
        )
        r = cli._sess.post(
            f"{BASE_ID}/api/auth",
            data={
                "prompt": "none",
                "redirect_uri": redirect_uri, "scope": scope,
                "response_type": "token", "device_id": self._device_id,
                "client_id": client_id, "audience": audience,
            },
            headers={
                "idaas-data": (
                    f"model_name=OpenHarmony;device_id={self._device_id};"
                    f"app_version={LOGIN_APP_VERSION};client_id={client_id};"
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
        loc = r.headers.get("location", "") or ""
        _loc = urllib.parse.urlparse(loc)
        frag = _loc.fragment
        params = dict(urllib.parse.parse_qsl(frag))
        tok = params.get("access_token", "")
        if not tok:
            # ★ 2026-10-10：失败原因常在 location 的 query/fragment（如
            #   `error=login_required`），正文里可能什么都没有 —— 不带出来
            #   就没法判断「会话失效（该重登）」还是「与会话无关（不该重登）」。
            #   只取这几个诊断键，避免把 token 等敏感值写进日志。
            _hints = {k: v for k, v in
                      {**dict(urllib.parse.parse_qsl(_loc.query)), **params}.items()
                      if k in ("error", "error_description", "prompt",
                               "login_required", "code")}
            _hint = " ".join(f"{k}={v}" for k, v in _hints.items())

            # ★ 2026-10-18（车主实测反馈优化）：换 token 被拒时，原实现在尾部拼
            #   `r.text[:120]` —— 而服务端 JSON 里带着**本次请求的全部 cmdKey**
            #   （车主实测 14 个，一屏糊满），对用户毫无帮助、还抖出内部细节。
            #   改为：只说清【发生了什么 + 下一步怎么做】。
            #
            #   实测两种成因（2026-10-18）：
            #     · 车主机主账号（L6, app_type=lixiang）→ 换得到 mesh token ✅
            #     · 理想同学 / 家人账号（车主反馈）→ access_denied ❌
            #       且换 client 重试（lixiang / livis）都被拒
            #   ⇒ 大概率是**服务端对家人账号不授予车控 scope**（而非我们参数错），
            #     但需 ONE 车主账号实测才能坐实 —— 故此处只说现象 + 可执行下一步。
            _err_kind = (_hints.get("error") or "").strip()
            if _err_kind in ("access_denied", "unauthorized"):
                # ★ 2026-10-18 二次修正（依据车主实测日志 + 本机对照实测）：
                #   先前写的「与账号角色有关」【是错的】—— 实测【车主账号】
                #   （日志：vehicleType=owned roleId=1）同样被拒；而**完全相同的
                #   代码 + 相同的 scope 格式**在 L6（X 系车主）上换到 1884 字符 JWT。
                #   ⇒ 真因是【这套「cmdKey:VIN」scope 属于 X 系，M 系不认】。
                #   按是否 M 系给两种准确说法，避免继续误导用户。
                # ★ 判据用 get_vehicles()（已调过、无额外网络开销）：
                # ★ 2026-10-19：与车控分派【用同一个可靠判据】——
                #   之前这里自己抄了一份 modelId 前缀判据，而那份判据
                #   未实测且 modelId 往往取不到 ⇒ 恒 False ⇒ 文案分错支。
                #   教训：同一个判断在两处各写一遍，迟早只改一处。
                try:
                    _is_m = self._use_send_command_channel()
                except Exception:  # noqa: BLE001
                    _is_m = False
                if _is_m:
                    # ★ 2026-10-19 更新：M 系车控【代码已改走】send-command
                    #   （只用 MESH），依据充分；但**尚未经真车验证**，措辞
                    #   不能说成「已适配」（教训：别把代码写对说成问题解决）。
                    #   走到这里说明**仍然**被拒 —— 即便如此，也不是"尚未适配"，
                    #   而是该车/该账号的具体限制。措辞必须如实，不要误导车主。
                    _why = ("服务端拒绝了该 M 系车型（理想ONE）的这次车控授权"
                            "（access_denied）")
                    _todo = ("本集成对 M 系车控已改走官方 send-command 通道（仅需 MESH）。"
                             "若仍失败，请核对：① 集成是否为最新版本；"
                             "② 该账号是否为【车主本人】（家人/授权账号受服务端角色限制，"
                             "与官方 App 一致）；③ 日志里 probe_send_command 的结果。"
                             "只读数据（电量/续航/位置/充电状态等）不受影响。")
                else:
                    _why = "服务端拒绝为该账号签发车控授权（access_denied）"
                    _todo = ("请确认集成为最新版本；若是家人/授权账号，"
                             "远程车控受服务端角色限制（与官方 App 一致）")
            elif _err_kind == "login_required":
                _why = "服务端要求重新登录（登录会话已过期）"
                _todo = "在集成里点「重新认证」重新登录即可"
            else:
                _why = _hint or _err_kind or "未知原因"
                _todo = "查看集成日志（调试级别）里的完整响应"
            # ★ 保留 HTTP 状态码：既有守卫要求非 OAuth 失败时消息里含 "HTTP <code>"
            _code = f"HTTP {r.status_code} " if not _err_kind else ""
            raise LiApiError(
                f"换 token 失败（scope={scope}，error={_err_kind or 'unknown'}）："
                f"{_code}{_why}。下一步：{_todo}。")
        # ★ 诊断：HZ token 不透明，fragment 里的 scope/expires 是唯一能观察
        #   「服务端实际授予了什么」的窗口（排查 403 用，只打非敏感参数）
        if params.get("scope") or params.get("audience"):
            _LOGGER.debug("换token成功 grant参数: scope=%s aud=%s keys=%s",
                          params.get("scope", "?"), params.get("audience", "?"),
                          sorted(params.keys()))
        return tok

    def _get_scoped(self, name: str, scope: str, audience: str, ttl: int = 780) -> str:
        """scope token 缓存获取 (默认提前 2 分钟过期; 失效自动重登一次)."""
        ent = self._tokens.get(name)
        if ent and ent[1] > time.monotonic():
            return ent[0]
        try:
            tok = self._exchange(scope, audience)
        except LiApiError as err:
            # ★ 2026-10-08：scope 被策略拒绝 ≠ 会话失效 —— 重登不仅修不了，
            #   还会因 _login() 内的 _tokens.clear() 形成「每分钟重登+清缓存」
            #   风暴（真机实测 87 次/1.5h，有账号风控风险）→ 直接抛出。
            if _is_scope_denied(err):
                raise
            if not _is_session_loss(err):
                # ★ 2026-10-10：与会话无关的失败（5xx / 空响应 / 解析异常）
                #   **不再重登** —— 每次重登都可能顶掉手机 App，且重登也修不好。
                raise
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
        """MESH token: cmd/send 与 send-command 的 Authorization 头 (~15min)。

        ★★ 2026-10-19：M 系（理想ONE）必须用【官方完整五件套】scope 换取。
           用 3 项子集会被 SSO 直接拒（300 access_denied）——
           车主日志实证（见 SCOPE_MESH_FULL 上方注释）。
           ★ 缓存键也分开（mesh_full vs mesh），避免两套 scope 互相污染。
        """
        if self._use_send_command_channel():
            return self._get_scoped("mesh_full", SCOPE_MESH_FULL, AUD_MESH, ttl=780)
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
        """签名调用。★ 2026-10-10：签名错误（100005）时自愈并重试一次。

        自愈会把客户端身份换成本设备派生身份（_recover_signature_error），
        因为身份是客户端级共享状态，所以只要任一签名调用触发自愈，
        其余通道（任务大师 / travel）随之受益。
        """
        try:
            resp = self._signed_call_raw(method, path, body, bearer)
        except LiApiError as err:
            if is_signature_error(err) and self._recover_signature_error():
                return self._signed_call_raw(method, path, body, bearer)
            raise
        # 100005 也可能以 HTTP 200 + {"code":100005} 返回（不抛异常）
        if is_signature_error(resp) and self._recover_signature_error():
            return self._signed_call_raw(method, path, body, bearer)
        return resp

    def _signed_call_raw(self, method: str, path: str, body: str, bearer: str) -> dict:
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

    def _signed_call_task(self, method: str, path: str, body: str,
                          bearer: str) -> dict:
        """任务大师专用签名调用（2026-10-08：App 实测头对照 + 同步重签）。

        与 _signed_call 的差异（对照抓包，travel 接口同款教训）：
          · Content-Language: zh-CN（App 值；★签名第 7 段必须同步）
          · X-CHJ-APP-Version / X-CHJ-Version: 8.27.0（App 值）
          · X-CHJ-ModelName: ANDROID + X-CHJ-DeviceModel（App 值）
          · 新增 X-CHJ-Metadata / Accept-Language / App UA
        签名第 2 段必须与请求头版本一致（2026-10-08 维护者真机变体矩阵：
        8.25.4签名+8.27.0头 → 100005 签名错误；两段同为 8.27.0 → 通过；
        第 7 段语言 zh-CN/zh-Hans-CN 均可——真正要对齐的是版本段）。
        """
        ts = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        if body:
            md5 = base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
        else:
            md5 = EMPTY_MD5
        data = "\n".join([
            "prod", TASK_APP_VERSION, self._key_id, self._xdev, method, "*/*",
            "zh-CN", md5, "application/json", ts, nonce,
        ]) + "\n"
        sig = base64.b64encode(
            hmac.new(self._hac, data.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "X-CHJ-Env": "prod", "X-CHJ-APP-Version": TASK_APP_VERSION,
            "X-CHJ-Key": self._key_id, "X-CHJ-Deviceid": self._xdev,
            "X-CHJ-Timestamp": ts, "X-CHJ-Nonce": nonce, "X-CHJ-Sign": sig,
            "Content-MD5": md5, "Content-Type": "application/json",
            "Content-Language": "zh-CN", "Accept": "*/*",
            "Accept-Language": "zh-CN",
            "X-CHJ-Version": TASK_APP_VERSION, "X-CHJ-DeviceType": "2",
            "X-CHJ-ModelName": "ANDROID",
            "X-CHJ-DeviceModel": TASK_DEVICE_MODEL,
            "X-CHJ-Tag": "1", "X-CHJ-Metadata": TASK_META,
            "X-CHJ-TOKEN": self._app_token,
            "X-CHJ-VIN": self._vin,
            "Authorization": f"Bearer {bearer}",
            "User-Agent": TASK_UA,
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

    def get_realtime_state(self) -> dict:
        """老平台车型（M 系 / 理想ONE）实时状态 → 返回 `DynamicInfoRes` 本体。

        ★ 端点来自 App 逆向：`NetApiConst.GET_VEHICLE_STATE(vin)` →
          `GET /ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state`（方法 get）。
          这些车型 `vss:get-batch` 恒返 `access_denied`，只能走这条。
        """
        path = f"/ssp-as-mobile-api/v3-0/vehicles/{self._vin}/real-time-state"
        r = self._signed_call_travel("GET", path, "", self._travel_bearer())
        # ★ 2026-10-19：缓存最近一帧，供车型判据使用。
        #   M 系响应的顶层字段是【只有 M 系才有】的车型指纹 ⇒ 事实判据，
        #   不依赖取不到的 modelId / platform。
        self._last_rts = (r or {}).get("data") or {}
        return self._last_rts
        return (r or {}).get("data") or {}

    def probe_send_command(self) -> dict:
        """★ 2026-10-19：M 系车控通道探测（**不会动到车**）。

        手法：用【一定不存在】的 cmdKey 调 send-command：
          · 返回「命令不存在」类错误 → **通道本身通了**（只是 cmdKey 不对）→ 换键即可
          · 返回 100035 / access_denied     → **入口就拒** → 得换授权方式
        两者区分开，就能确定「改 cmdKey」还是「改授权」，不必盲改。

        ★ 为什么安全：__PROBE__ 这个 cmdKey 在服务端不存在，
          服务端不会执行任何动作，只返回错误 —— 车辆不会有反应。

        同时探测 M 系官方 cmdKey 里**最无害**的一条（remote_veh_search 寻车），
        但**只取返回码不下发结果**（poll=False）。
        """
        out: dict = {"vin": self._vin, "platform": None, "probes": []}
        try:
            vs = self.get_vehicles() or []
            for v in vs:
                if str(v.get("vin") or "") == self._vin:
                    out["platform"] = v.get("vehicleType")
                    out["modelId"] = v.get("modelId")
                    break
        except Exception:  # noqa: BLE001
            pass
        for key, note in (("__PROBE_NOT_EXIST__", "不存在的键（安全）"),
                          ("remote_veh_search", "M 系官方：获取车辆位置")):
            try:
                r = self.send_vehicle_command(key, {}, poll=False)
                out["probes"].append({"cmdKey": key, "note": note,
                                      "ok": r.get("ok"),
                                      "resultCode": r.get("resultCode"),
                                      "msg": str(r.get("msg"))[:120],
                                      "raw": json.dumps(r.get("raw"),
                                                        ensure_ascii=False)[:220]})
            except Exception as err:  # noqa: BLE001
                out["probes"].append({"cmdKey": key, "note": note,
                                      "error": f"{type(err).__name__}: {str(err)[:160]}"})
        return out

    def get_iot2_jwt(self) -> dict:
        """换取长连接用的 iot2 JWT（KMS 软签，软件 Ed25519 顶替 SE）。

        ★ 2026-10-17 落地自 `docs/方向A_KMS软签打通_20261017.md`（队友逆向）。
          官方在手机本地用 SE 安全区签名换 JWT；我们用 **App SO 里的出厂兜底密钥**
          做软件 Ed25519，服务端照收（实测 `code:0` + 30 天有效期）。

        返回 `{"ok": bool, "jwt": str, "code": ..., "msg": ..., "raw": dict}`
        —— 失败时 `ok=False` 并带服务端原始 code/msg，**不抛异常**
          （诊断性质，且错误码本身有排查价值，见 kms_softsig 模块说明）。
        """
        import json as _json

        from .kms_softsig import build_kms_body, summarize_jwt

        device_id = self._xdev or self._device_id
        body, message = build_kms_body(device_id)
        payload = _json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        try:
            resp = self._signed_call("POST", KMS_JWT_EP, payload, self._main_bearer)
        except Exception as err:  # noqa: BLE001
            return {"ok": False, "jwt": "", "code": None,
                    "msg": f"请求失败: {err}", "raw": {}}

        code = resp.get("code")
        data = resp.get("data") or {}
        jwt = str(data.get("jwt") or "") if isinstance(data, dict) else ""
        out: dict = {
            "ok": code == 0 and bool(jwt),
            "jwt": jwt,
            "code": code,
            "msg": _as_text(resp.get("msg") or resp.get("message")),
            "raw": resp,
            "device_id": device_id,
        }
        if jwt:
            out["summary"] = summarize_jwt(jwt)
        _LOGGER.info(
            "KMS 软签换 iot2 JWT: code=%s ok=%s%s",
            code, out["ok"],
            (f"（有效期 {out['summary'].get('valid_seconds', 0) // 86400} 天）"
             if out.get("summary") else ""),
        )
        return out

    def probe_gfm_face(self) -> dict:
        """用刚换到的 JWT 查长连接接入点 —— **验证 JWT 是否真被网关接受**。

        端点与请求头取自队友的实测（`docs/方向A_KMS软签打通_20261017.md` §5.3/§5.4）：
            POST https://api-app-cnhz2n01-b.lixiang.com
                 /li-ndn-gfm/gfm-server/v2-0/nfd-face?device_id=<deviceId>&device_type=MOBILE
        注意头名 `x-chj-kms-verify-type` 的值是字面量 `KMS-JWT`（不是 MOBILE）。

        只读：拿到的只是「有哪些 NFD 可以连」，**不会真的建连**。
        """
        import json as _json

        import requests

        from .kms_softsig import gfm_face_headers, gfm_face_url

        minted = self.get_iot2_jwt()
        out: dict = {"jwt_ok": minted.get("ok"), "jwt_code": minted.get("code"),
                     "jwt_msg": minted.get("jwt_msg") or minted.get("msg")}
        if not minted.get("ok"):
            out["error"] = "JWT 未取到，无法验证网关"
            return out

        device_id = self._xdev or self._device_id
        url = gfm_face_url(device_id)
        try:
            r = requests.post(
                url,
                headers={**gfm_face_headers(device_id, minted["jwt"]),
                         "Content-Type": "application/json",
                         "x-chj-key": self._key_id,
                         "X-CHJ-TOKEN": self._app_token},
                data=_json.dumps({}, separators=(",", ":")), timeout=20,
                verify=False)  # noqa: S501 —— 该域证书链与本地 CA 不匹配
        except Exception as err:  # noqa: BLE001
            out["error"] = f"GFM 请求失败: {err}"
            return out

        try:
            j = r.json()
        except Exception:  # noqa: BLE001
            out["http_status"] = r.status_code
            out["body"] = r.text[:300]
            return out

        data = j.get("data")
        out["http_status"] = r.status_code
        out["code"] = j.get("code")
        out["msg"] = j.get("msg")
        out["faces"] = len(data) if isinstance(data, list) else 0
        if isinstance(data, list) and data:
            out["sample"] = data[0]
        out["accepted"] = (r.status_code == 200 and j.get("code") == 0 and out["faces"] > 0)
        _LOGGER.info("GFM 接入点查询: HTTP %s code=%s faces=%d accepted=%s",
                     r.status_code, j.get("code"), out["faces"], out.get("accepted"))
        return out

    def probe_realtime_state(self) -> dict:
        """诊断：探测「老平台车型（如理想ONE / M01）」的 real-time-state 通道。

        ★ 为什么需要它（2026-10-11，理想ONE 车主日志实证）：
          VSS（`vss:get-batch`）对该车返回 `access_denied` —— 该车型没有开通
          VSS 信号服务；而本项目文档早就记录
          `/ssp-as-mobile-api/v3-0/vehicles/{vin}/real-time-state`
          是社区方案（hasscc）的**默认数据源**，**新车型（L6）反而报 100035**。
          → 老车型应走 real-time-state，但必须先拿到**真实响应**才能建字段映射。

        ★ 铁律 2（对照组）：同时打一条**已知可用**的接口（travel 月里程，
          与本次探测共用同一套签名 + 主 Bearer）—— 否则分不清
          「端点不可用」与「会话/权限/签名问题」。

        只读：不触发任何车控。
        """
        out: dict = {"vin": self._vin, "attempts": {}}
        bearer = self._travel_bearer()

        def _try(path: str) -> dict:
            try:
                r = self._signed_call_travel("GET", path, "", bearer)
            except Exception as err:  # noqa: BLE001
                return {"ok": False, "error": str(err)[:200]}
            code = r.get("code")
            data = r.get("data")
            return {
                "ok": code == 0,
                "code": code,
                "message": r.get("message") or r.get("msg"),
                "data_type": type(data).__name__,
                "data_keys": (sorted(str(k) for k in data.keys())[:60]
                              if isinstance(data, dict) else None),
                "raw": r,
            }

        # 对照组（已知可用）：travel 月里程 —— 同一套签名/主 Bearer
        out["attempts"]["control_travel_months"] = _try(
            f"/ssp-travel-x-service/v1-0/travel/months/{self._vin}")
        # 目标①：hasscc 默认数据源（v3-0，带 vin）
        out["attempts"]["realtime_state_v3"] = _try(
            f"/ssp-as-mobile-api/v3-0/vehicles/{self._vin}/real-time-state")
        # 目标②：文档中出现过的 v1-0 变体（不带 vin）—— 一并试，省一轮往返
        out["attempts"]["realtime_state_v1"] = _try(
            "/ssp-as-mobile-api/v1-0/vehicles/real-time-state")
        return out

    def _refresh_main_bearer(self) -> bool:
        """用 refresh_token **免密**续期主 Bearer；成功返回 True。

        ★ 2026-10-10（接通 `pake_login.refresh()`，此前是死代码）：
          会话失效分两种，代价完全不同 ——
            · scope token 通道（VSS / 车控 / 任务大师）：换 token 必须带
              **登录会话 cookie**，而 refresh **不会重新种 cookie**
              → 这里救不了，只能密码重登（见 _get_scoped）。
            · 主 Bearer 通道（travel 陪伴里程 / 充电明细与月统计）：
              只吃 access_token → 可用 refresh_token 免密续期，
              **省掉一次密码重登**（少一次风控风险与等待）。
          本方法只服务后者。

        ⚠️ 关键：refresh_token **会轮换** —— 新值必须回写 config entry
           （`_notify_token_update`），否则「续期一次 → 下次重启必须密码重登」，
           反而**制造**风控。这条有专门的回归测试。
        """
        if not self._refresh_token:
            # ★ 2026-10-10：这条此前是静默 return —— 于是「entry 里存着
            #   refresh_token 但启动没传进来」这种 bug 完全看不见（真机取证踩坑）
            _LOGGER.debug("无 refresh_token 可续期（将回退密码重登）")
            return False
        try:
            cli = self._cli or LixiangDirectLogin(
                device_id=self._xdev or self._device_id,
                debug=False, app_type=self._app_type)
            tok = cli.refresh(self._refresh_token)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info("refresh_token 续期失败，回退密码重登: %s", err)
            return False
        access = str(tok.get("access_token") or "")
        if not access:
            _LOGGER.info("refresh_token 续期未返回 access_token，回退密码重登")
            return False
        self._cli = cli
        self._main_bearer = access
        new_rt = str(tok.get("refresh_token") or "")
        if new_rt and new_rt != self._refresh_token:
            self._refresh_token = new_rt
            _LOGGER.debug("refresh_token 已轮换，随回写持久化")
        self._notify_token_update()
        _LOGGER.info("主 Bearer 已用 refresh_token 免密续期（未走密码重登）")
        return True

    def _travel_bearer(self, force_login: bool = False) -> str:
        """travel 接口用的主 Bearer（App 抓包里 x-chj-token = APP-xxx）。

        ★ 2026-10-02：主 Bearer 会过期（服务端 100105「用户未登录」）。
          调用方收到 100105 时用 force_login=True 重登一次再试。
        ★ 2026-10-02 修正：_login() 里 `if self._cli is not None` 之类的短路会让
          force_login 无效 —— 这里强制清空 _cli 再登录，确保真的换新 token。
        ★ 2026-10-10：先试【免密续期】（refresh_token），失败才密码重登。
          顺序等价于「最坏情况与原来一致」—— 续期不可用时行为不变。
        """
        if force_login or not getattr(self, "_main_bearer", ""):
            if not self._refresh_main_bearer():
                self._main_bearer = ""
                self._cli = None        # ★ 关键：清掉旧 session，强制重新登录
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
        """某月充电记录明细（单一类型）。

        dt: "年-月" 如 "2026-9"
        charging_type: 见 ``CHARGE_TYPE_PREFIX`` —— 1=DC 直流快充 / 2=AC 交流慢充
                       / 3=SC 5C超充 / 4=4CAnd5C 理想超充
        """
        return self._signed_call_travel(
            "GET",
            f"/bsp-vcp-message/v1/app/vehicle/chargeRecords/monthly"
            f"?vin={self._vin}&dt={dt}&chargingType={charging_type}",
            "", self._travel_bearer())

    def get_charge_records_monthly_all(
            self, dt: str, types: tuple[int, ...] | None = None) -> dict:
        """某月充电记录明细（**聚合全部 4 种类型**，按时间倒序）。

        ★ 2026-10-09：单一 charging_type 只能取到一种充电方式的记录，
          而 App 明细页展示的是全部类型。默认应聚合，避免「明细里看不到
          5C超充 / 理想超充」——与 get_charge_current_month_kwh 的
          统计口径漏算是同一类问题。

        返回结构与单类型一致：{"code": 0, "data": [...]}，每条记录补充
        chargingType 字段标明来源；全部类型都失败才返回错误码。

        types: 只聚合指定类型（如 ``(3, 4)`` = App 的「理想超充」）；None = 全部。
        """
        wanted = set(types) if types else None
        merged: list = []
        got = False
        failed = 0
        for ct, _pfx in CHARGE_TYPE_PREFIX:
            if wanted is not None and ct not in wanted:
                continue
            try:
                r = self.get_charge_records_monthly(dt, ct)
            except Exception:  # noqa: BLE001
                failed += 1
                continue
            if r.get("code") not in (None, 0):
                failed += 1
                continue
            for x in (r.get("data") or []):
                if isinstance(x, dict):
                    x = dict(x)
                    x.setdefault("chargingType", ct)
                merged.append(x)
                got = True
        try:
            merged.sort(key=lambda x: (x.get("startTime") or 0), reverse=True)
        except Exception:  # noqa: BLE001
            pass
        if not got and failed:
            return {"code": -1, "message": f"全部 {failed} 种充电类型均拉取失败"}
        return {"code": 0, "message": "SUCCESS", "data": merged}

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
        """本月充电量（App 充电页同口径：**全部 4 种充电类型**）。

        ★ 2026-10-08 修正：原先只统计 `chargingType` 1(DC)+2(AC)，漏掉了
          3(SC 5C超充) 与 4(4CAnd5C **理想超充**)，导致「本月充电量」少算。
          真机实测（同一账号同一月）：
             1 DC = 78.65 / 2 AC = 41.18 / 3 SC = 29.43 / 4 理想超充 = 23.76
             旧口径 = 119.83（正是用户报告的 119.80）❌
             正确值 = 173.02 ✅   （少算 53.19 kWh）
          类型语义来自 App bundle（`chargingType === 1/2/3/4`）与 I18N 文案
          （chargingTypeDC/AC/SC/4CAnd5C）。

        返回 {dc_kwh, ac_kwh, sc_kwh, hpc_kwh, total_kwh,
              dc_times, ac_times, sc_times, hpc_times, total_times}；
        失败返回 None。
        """
        import datetime as _dt
        now = _dt.datetime.now()
        out: dict = {}
        for _ct, _pfx in CHARGE_TYPE_PREFIX:
            out[f"{_pfx}_kwh"] = 0.0
            out[f"{_pfx}_times"] = 0
        got = False
        for ct, pfx in CHARGE_TYPE_PREFIX:
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
        out["total_kwh"] = round(
            sum(out[f"{p}_kwh"] for _, p in CHARGE_TYPE_PREFIX), 2)
        out["total_times"] = sum(
            out[f"{p}_times"] for _, p in CHARGE_TYPE_PREFIX)
        return out

    def get_charge_total_kwh(self) -> float | None:
        """累计充电量（kWh，**全部 4 种充电类型**所有月份求和）。

        ★ 用途：给 HA 能源面板提供一个「总充电量」传感器。
          数据源是官方按月统计（天然递增 → total_increasing）。
          失败返回 None（调用方保留上次值，不写 0 以免破坏递增曲线）。

        ★ 2026-10-08 修正：原先只遍历 (1, 2)，漏掉 3(SC 5C超充) 与
          4(4CAnd5C **理想超充**) → 累计量同样少算。改为遍历
          ``CHARGE_TYPE_PREFIX`` 全部类型。
        """
        total = 0.0
        got = False
        for ct, _pfx in CHARGE_TYPE_PREFIX:
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

    def get_charge_monthly_stats_all(
            self, types: tuple[int, ...] | None = None) -> dict:
        """按月充电统计（**聚合全部 4 种充电类型**）。

        ★★ 2026-10-11 修复一个用户可感知的数据错误：

        服务端 `monthlyStatistics` 接口**必须带 `chargingType`**，且每个类型
        **只返回该类型的统计** —— 没有"全部"这个取值（实测 0 返回空）。

        而此前前端"按月统计"走的是 `get_charge_monthly_stats()`（默认
        `charging_type=1` = 仅 DC 直流快充）→ **只显示实际电量的约 1/3**。

        实测对照（车主 App 截图 vs 本方法聚合值，2026 年 8 个月全部吻合）：

        | 月 | 单 type=1（旧）| 4 类型聚合（本方法）| App 显示 |
        |---|---|---|---|
        | 10月 | 6 次 / 78.65 | 13 次 / 223.32 | 13 次 / 223.32 ✅ |
        |  9月 | 1 次 / 12.93 | 28 次 / 529.18 | 28 次 / 529.18 ✅ |
        |  8月 | 12 次 / 151.3 | 40 次 / 611.00 | 40 次 / 611.00 ✅ |

        返回结构与单类型一致：`{"code": 0, "data": [{year, month,
        chargingTimes, chargingCapacity}]}`，按 (year, month) **求和**后
        时间倒序。全部类型都失败才返回错误码（避免部分失败伪装成"没数据"）。

        types: 只聚合指定的类型（如 ``(3, 4)`` = App 的「理想超充」，
               含 5C 超充 + 4C/5C 理想超充）；``None`` = 全部 4 种。
        """
        wanted = set(types) if types else None
        by_key: dict[tuple, dict] = {}
        got = False
        failed = 0
        for ct, _pfx in CHARGE_TYPE_PREFIX:
            if wanted is not None and ct not in wanted:
                continue
            try:
                r = self.get_charge_monthly_stats(ct)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("充电统计 type=%s 失败: %s", ct, err)
                failed += 1
                continue
            if r.get("code") not in (None, 0):
                failed += 1
                continue
            for x in (r.get("data") or []):
                if not isinstance(x, dict):
                    continue
                key = (x.get("year"), x.get("month"))
                cur = by_key.setdefault(key, {
                    "year": x.get("year"), "month": x.get("month"),
                    "chargingTimes": 0, "chargingCapacity": 0.0,
                })
                cur["chargingTimes"] += int(x.get("chargingTimes") or 0)
                cur["chargingCapacity"] += float(x.get("chargingCapacity") or 0)
                got = True
        if not got:
            return {"code": -1, "msg": f"全部充电类型均失败({failed}/4)", "data": []}
        out = sorted(by_key.values(),
                     key=lambda a: (a.get("year") or 0, a.get("month") or 0),
                     reverse=True)
        for x in out:
            x["chargingCapacity"] = round(x["chargingCapacity"], 2)
        return {"code": 0, "data": out}

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

    # ══════════════════════════════════════════════════════════════════
    #  ★ 2026-10-12：App 权威车控通道（第二轮逆向修正）
    #
    #  此前本项目只认 cmd/send，并把「充电 / 哨兵 / 拍照」判为
    #  「走 JOB 长连接、HTTP 不可达」。**该结论是错的**：
    #  App 的 LXMVehicleConfig2025.json 给出 70 条 LXVehicleControlType*，
    #  其中 65 条走 send-command，另有 3 条同步 API。参见文件头注释。
    # ══════════════════════════════════════════════════════════════════

    def send_vehicle_command(
        self, command_key: str,
        command_data: dict | None = None,
        *, poll: bool = True, timeout: float = RVC_POLL_TIMEOUT,
    ) -> dict:
        """用 App 的权威通道下发车控命令。

        与 `send_command_raw`（走 cmd/send）的区别：
          · 该通道是 App 真正的入口，**没有 JOB 通道限制** —— 充电启停 /
            哨兵 / 拍照 / 解锁 / 后备箱等 65 条命令都走它。
          · 返回 `operationId`（任务号），结果需查 verificationUrl。

        参数：
          command_key  配置表里的 cmdKey，如 remote_central_lock_unlock /
                       remote_plg_open / remote_charging_start。
                       配置表里 cmdKey 为空的那几条，App 用类型名当键
                       （见 vehicle_control_types 模块），调用方负责传对。
          command_data 命令参数（如 {"ctrlType": 1}），可为空。
          poll         True=轮询结果；False=只下发拿 operationId。
          timeout      轮询上限（配置表 expireAt=30s）。

        返回：
          {"ok": bool, "operationId": str, "resultCode": str|int,
           "msg": str, "raw": dict}

        ★ 未在真机验证：本方法按配置表 + OperateReq 字段实现，
          首次调用请先看返回的 raw，据实修正（项目规则：不猜）。
        """
        body = {
            "vin": self._vin,
            "commandKey": command_key,
            "commandData": command_data or {},
            "commandDataLi": command_data or {},
        }
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        resp = self._signed_call("POST", EP_RVC_SEND, payload, self._get_mesh_token())

        op_id = _first_of(resp, "operationId", "taskId", "opId", "id", "txId")
        out = {
            "ok": False,
            "operationId": str(op_id) if op_id is not None else "",
            "resultCode": _first_of(resp, "resultCode", "code"),
            "msg": _as_text(_first_of(resp, "msg", "message", "resultMsg")),
            "raw": resp,
        }
        if op_id is None:
            # 有些实现直接同步返回结果码
            code = str(out["resultCode"]) if out["resultCode"] is not None else ""
            out["ok"] = code in ("", RVC_SUCCESS_CODE, "0", "200")
            return out
        if not poll:
            out["ok"] = True
            return out

        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(RVC_POLL_INTERVAL)
            try:
                r = self._signed_call(
                    "GET",
                    EP_RVC_RESULT.format(vin=self._vin, op_id=op_id),
                    "", self._get_mesh_token())
            except LiApiError as err:
                out["msg"] = str(err)
                continue
            code = str(_first_of(r, "resultCode", "code") or "")
            if code and code not in ("", "0", RVC_SUCCESS_CODE):
                out.update(ok=False, resultCode=code,
                           msg=_as_text(_first_of(r, "msg", "message")), raw=r)
                return out
            state = str(_first_of(r, "state", "status", "pushState") or "")
            if code == RVC_SUCCESS_CODE or state in ("5", "success", "done"):
                out.update(ok=True, resultCode=code or RVC_SUCCESS_CODE, raw=r)
                return out
        if not out["msg"]:
            out["msg"] = f"轮询 {timeout:.0f}s 未拿到结果"
        return out

    def _sync_update(self, path: str, body: dict, what: str) -> dict:
        """同步更新类 API（配置表 skipVerification=1，一次调用即结果）。

        用于 charge-threshold-update / battery-warm-switch /
        ac-appointment-update —— 它们**不需要轮询**。
        """
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        resp = self._signed_call("POST", path, payload, self._get_mesh_token())
        code = str(_first_of(resp, "resultCode", "code") or "")
        ok = code in ("", "0", RVC_SUCCESS_CODE, "200")
        return {
            "ok": ok, "resultCode": code,
            "msg": str(_first_of(resp, "msg", "message") or ""),
            "raw": resp, "what": what,
        }

    def set_charge_threshold(self, threshold: int) -> dict:
        """设置充电上限（+ 未达上限继续充电的行为由车端决定）。

        端点：POST /ssp-as-mobile-api/v1-0/vehicles/charge-threshold-update
        请求体（VehicleChargetThresholdReq）：{vin, threshold}

        ★ 这条是**同步** API —— 不需要 JOB 长连接，也不需要轮询。
          此前项目把「充电上限」做成只读，是因为只找到了 cmd/send 那条路。
        """
        threshold = max(CHARGE_MIN, min(CHARGE_MAX, int(threshold)))
        return self._sync_update(
            EP_CHARGE_THRESHOLD,
            {"vin": self._vin, "threshold": str(threshold)},
            f"充电上限 → {threshold}%")

    def set_battery_warm(self, on: bool) -> dict:
        """电池保温开关。

        端点：POST /ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch
        请求体（BatteryInsulationReq）：{vin, switchState}  1=开 0=关
        """
        return self._sync_update(
            EP_BATTERY_WARM,
            {"vin": self._vin, "switchState": 1 if on else 0},
            f"电池保温 → {'开' if on else '关'}")

    def set_charge_warm(self, enable: bool) -> dict:
        """设置**充电保温**（电池加热）开关。

        端点（官方 M 系 NetApiConst.chargeWarmSwitch）：
            POST /ssp-as-mobile-api/v1-0/vehicles/battery-warm-switch
        请求体：{vin, switchState}
            switchState: "0"=关闭  "1"=开启

        ★ **理想 ONE（M 系）专属功能** —— 权威依据：
            ① M 系配置表 assets/2025/LXMVehicleConfig2025.json 有
               `SetChargeInsulation`（充电保温），而 X 系 LXXVehicleConfig2025.json
               **没有这一条** → 只有 M 系有此功能。
            ② 官方 M 系代码 `NetApiConst.chargeWarmSwitch` 给出上面的端点。
            ③ 状态来源：real-time-state 的
               `chargeSetting.batteryWarmSwitch.switchState`（m01_state 已映射
               到 `charge_insulation` signal）。

        这是**同步** API —— 不需要 JOB 长连接，也不需要轮询。
        """
        return self._sync_update(
            EP_BATTERY_WARM,
            {"vin": self._vin, "switchState": "1" if enable else "0"},
            ("充电保温 → 开启" if enable else "充电保温 → 关闭"))

    def set_charge_appointment(self, enable: bool) -> dict:
        """设置**预约充电**开关（M 系专属：只改开关，保留当前模式与时间）。

        端点（官方 M 系 `NetApiConst.chargeAppointmentUpdate`）：
            POST /ssp-as-mobile-api/v1-0/vehicles/charge-appointment-update
        请求体字段（沿用我们已实证的 controlType='3' 那套命名）：
            statusControlRequest / controlType="3"
            OrderChargingSwitch: "1"/"0"
            OrderChargingMode / reserveStartTime / NewReserveFinishTime / isContinue
            —— 开关切换时后几项要**带当前值**，否则服务端会清掉原预约。

        状态来源：real-time-state 的
            `chargeSetting.appointmentTime.{chargeOnOff,startTime,endTime,isContinue}`
            （m01_state 已映射到 charge_appointment / _start / _end）。

        ★ 只有 M 系（理想ONE）走这个端点；X 系无此功能
          （M 系配置表有 SetChargeAppointment，X 系表没有）。
        """
        vss = (getattr(self, "_last_vss", None) or {})
        _appt = ((vss.get("charge_appointment") or {}).get("value"))
        _st = ((vss.get("charge_appointment_start") or {}).get("value")) or "00:00"
        _et = ((vss.get("charge_appointment_end") or {}).get("value")) or "00:00"
        return self._sync_update(
            EP_CHARGE_APPOINTMENT,
            {"vin": self._vin,
             "statusControlRequest": 255,
             "controlType": "3",
             "OrderChargingSwitch": "1" if enable else "0",
             "reserveStartTime": _st,
             "NewReserveFinishTime": _et},
            ("预约充电 → 开启" if enable else "预约充电 → 关闭"))

    def set_ac_appointment(self, body: dict) -> dict:
        """预约空调。

        端点：POST /ssp-as-mobile-api/v1-0/vehicles/ac-appointment-update
        请求体（AcAppointmentUpdateReq）：
          {vin, switchOn, temp, startTime, workingDay,
           flLevel, frLevel, rlLevel, rrLevel, steerSet, battWarmUp}
        """
        return self._sync_update(
            EP_AC_APPOINTMENT, {"vin": self._vin, **body}, "预约空调")

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

    # ★ M 系（real-time-state）响应里【独有】的顶层字段 —— 用作车型指纹。
    #   来源：理想ONE 实测响应 vs L6(VSS) 响应逐字段比对。
    #   这些字段 X 系响应里不存在 ⇒ 命中即 M 系 ⇒ 不会误判 X 系。
    #   ★ 相比"猜 modelId 前缀"，这是**事实判据**：接口已在线使用。
    _M01_ONLY_FIELDS: tuple[str, ...] = (
        "versionSupport", "wheelWarmStatus", "ringLightStatus",
        "remoteStartStatus", "vehPowerMode", "otaUpgradeInfo",
        "vehOnlineStatus", "rearviewMirrorFoldStatus", "caseCoverStatus",
        "seatStatus", "airConditioningStatus", "chargeSetting",
    )

    # M 系（理想 ONE）专用 cmdKey —— 官方 MControlKeyConst 常量表
    #
    # ★ 来源（REA 静态读取 smali 静态字段初始值，逐条核对）：
    #     com/chehejia/lib/vehicle/m/constant/MControlKeyConst.smali
    #   并与 LXMVehicleConfig2025.json（70 条）的 cmdKey 完全一致。
    #
    # ⚠️ 与 X 系（remoteVeh*）是【两套并存】的键，不能混用：
    #     M 系示例：remote_central_lock_lock / remote_window_open
    #     X 系示例：remoteVehLockControl / remoteVehWdwControl
    _M01_CMDKEY_MAP: dict[str, str] = {
        # ── X 系 cmdKey → M 系 cmdKey（两套并存，按车型选）──────────────────
        # ★★ 2026-10-19 补全：此前只映射了锁车一把键，导致其余车控
        #   在 M 系上会拿 X 系键去调 send-command ⇒ 必然失败。
        #   来源（★ 官方，非推测）：
        #     ① LXMVehicleConfig2025.json 的 70 条能力表（13 个 cmdKey）
        #     ② MControlKeyConst 的静态字段（LXVehicleControlType*）
        #     ③ a0.smali 构造 OperateReq 时的 cmdData.Type 取值
        #
        # ★★ 重要差异：M 系的 **commandKey 与 cmdData.Type 是两个层次** ——
        #   · commandKey：13 个（remote_central_lock_lock / remote_plg_open …）
        #   · cmdData.Type：另一组（空调全部挤在 remote_ac_ctrl_new 里，
        #     靠 Type + Temp/SteerSet/FLLevel… 区分具体功能）
        #   ⇒ 锁车/车窗/尾门/寻车/充电启停 是 1:1 映射 ✓
        #   ⇒ 空调/座椅加热/方向盘加热 需要再按 Type 分流（本表只给 commandKey，
        #     Type 由各平台按需放进 cmdData）✓
        "remoteVehLockControl": "remote_central_lock_lock",      # 锁车
        "remoteVehWdwControl": "remote_window_open",              # 开窗（关窗另用 _close）
        "remoteVehPlgControl": "remote_plg_open",                 # 开尾门（关用 _close）
        "remoteVehSearch": "remote_veh_search",                   # 寻车 / 车辆位置
        "remoteVehACSmartControl": "remote_ac_ctrl_new",          # 空调（含座椅/方向盘）
        "remote_charge_control": "remote_charging_start",         # 开始充电（停止用 _stop）
        "remoteVehAuth": "remote_veh_search",                     # 授权驾驶：无专属键，复用寻车
        "remoteVehFrgControl": "remote_ac_ctrl_new",              # 冰箱/除霜等 → 走空调通道
        "remoteVehSvm": "remote_veh_search",                      # 哨兵/闪灯 → 复用寻车
        "remoteVehACFirstControl": "remote_ac_ctrl_new",          # 一键空调
    }

    #: M 系「反向动作」键 —— 开↔关、成对出现。
    #: ★ 来自官方能力表：每个开/关/停都是**独立的 cmdKey** ✓
    _M01_CMDKEY_INVERSE: dict[str, str] = {
        "remote_central_lock_lock": "remote_central_lock_unlock",
        "remote_window_open": "remote_window_close",
        "remote_plg_open": "remote_plg_close",
        "remote_charging_start": "remote_charging_stop",
        "remote_engine_start": "remote_veh_stop_m01",
    }

    #: M 系官方 cmdKey 全集（13 个，来源：LXMVehicleConfig2025.json + MControlKeyConst）
    _M01_CMDKEYS: tuple[str, ...] = (
        "fTkC",
        "remote_ac_ctrl_new",
        "remote_central_lock_lock",
        "remote_central_lock_unlock",
        "remote_charging_start",
        "remote_charging_stop",
        "remote_engine_start",
        "remote_plg_close",
        "remote_plg_open",
        "remote_veh_search",
        "remote_veh_stop_m01",
        "remote_window_close",
        "remote_window_open",
    )

    def _use_send_command_channel(self) -> bool:
        """本车是否应走 send-command（M 系专用通道）而非 cmd/send。

        ################ ################  重要提醒  ################ ################
        # ★★ 静态逆向的产出只是【必要条件】，不是【充分条件】★
        #
        #   本函数配套的证据（均可复核，不是猜测）：
        #     ① M 系配置表 LXMVehicleConfig2025.json 70 条全带 sendUrl
        #     ② subTokenData 权威表：send-command 只需 MESH，VAT 属 cmd/send 专用
        #     ③ MControlKeyConst：M 系 13 个真实 cmdKey
        #     ④ 请求体字段 / ⑤ 回查规则（成功 5、失败 7、30 秒窗口）
        #
        #   ★ 但"读懂了说明书"≠"钥匙能转这扇锁"——
        #     真实下发是否成功，**只有真车能回答**。
        #     2026-10-19 教训（本判据曾恒为 False 而静态完全查不出来：
        #     因为那不是协议问题，是代码写错了）：
        #       —— 别把「静态全部确认」说成「已适配/已解决」。
        #       —— 要说「代码已改对、依据充分，待真机确认」。
        ##############################################################################

        ★★ 2026-10-19 更正（原实现有严重缺陷）：
          原判据是 `modelId.startswith("1002043")` 或 `platform=="1"`，
          但**这两个值都取不到 / 未实测**：
            · modelId 要靠 get_vehicles()，而 M 系车主的会话能拉
              real-time-state 却可能拉不到该接口 ⇒ 判据恒为 False
            · platform 字段 get_vehicles() 根本不返回
          ⇒ 实测表现：M 系车控**仍走 cmd/send** ⇒ 仍报 access_denied
            （对方 2026-10-19 反馈 fan/turn_on 依然失败，且文案还是旧的）

        ★ 现判据（**事实驱动，不猜**）：
          用 `real-time-state` 响应里【M 系独有的顶层字段】做车型指纹。
          集成本来就在拉这个接口（只读数据正常 ⇒ 已验证可用），
          且这些字段 X 系响应里【不存在】⇒ 不会误判。
        """
        data = self._last_rts
        if isinstance(data, dict):
            for key in self._M01_ONLY_FIELDS:
                if key in data:
                    _LOGGER.debug(
                        "车型判据：real-time-state 含 M 系独有字段 %s "
                        "⇒ 走 send-command 通道", key)
                    return True
        # 兜底：能力表（若已加载）
        try:
            ab = getattr(self, "_ability", None)
            if ab is not None:
                from .m01_state import is_m_series
                if is_m_series(ab):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False

    def _send_command_via_rvc(self, command_key: str,
                              command_data: dict | None,
                              *, poll: bool, timeout: float) -> dict:
        """经 send-command 下发（M 系专用），并把结果对齐 send_command 的形状。

        ★ cmdKey 需要按车型换成 M 系键（两套并存，不能混用）。
        ★ 只用 MESH token —— 不需要 VAT（官方 subTokenData 已证实）。
        """
        key = self._M01_CMDKEY_MAP.get(command_key, command_key)
        res = self.send_vehicle_command(key, command_data or {}, poll=poll)
        # 形状对齐：send_command 返回 {...}、调用方读 resultCode / msg
        return {
            "ok": bool(res.get("ok")),
            "resultCode": res.get("resultCode"),
            "msg": res.get("msg") or "",
            "operationId": res.get("operationId") or "",
            "raw": res.get("raw") or {},
        }

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

        # ★★ 2026-10-19（车主实测 + 官方配置表双重确认）：
        #   M 系（理想 ONE）的车控**不能走 cmd/send**（需要 VAT token，
        #   而服务端不向 M 系签发 —— 实测 access_denied）。
        #   官方配置表 LXMVehicleConfig2025.json（70 条）**全部**带 sendUrl =
        #   /ssp-as-mobile-api/v3-0/remote-vehicle-control/send-command
        #   ⇒ M 系车控改走 send-command，且**只用 MESH token**（ONE 拿得到 ✓）。
        #
        #   依据链（三条独立证据，非推测）：
        #     ① subTokenData（m01config.json 权威表）：
        #        httpLiMeshServiceV2.scope = veh-ctrl:cmd-send …（MESH）
        #        VAT.scope = remoteVehACSmartControl, remoteVehLockControl …
        #        ⇒ VAT 的 scope 全是 X 系 cmdKey ⇒ VAT 属于 cmd/send 专用
        #     ② MControlKeyConst（M 系 cmdKey 常量表）+ BaseAppWidget.H() 下发入口
        #     ③ L6 实测：send-command 仅带 MESH → 100035（X 系不开放），
        #        不是「token 无效」⇒ MESH 就够了
        if self._use_send_command_channel():
            return self._send_command_via_rvc(command_key, command_data,
                                              poll=poll, timeout=timeout)

        if wake:
            try:
                self.wakeup()
            except LiApiError as err:  # 唤醒失败不阻断 (车辆可能已在线)
                _LOGGER.debug("唤醒失败(忽略, 继续下发): %s", err)

        try:
            resp = self.send_command_raw(command_key, command_data)
        except LiApiError as err:
            # ★ 2026-10-18：家人/授权账号发车控 → cmd/send 返回 HTTP 503，
            #   但真实原因是【服务端按角色拒绝】（同一辆车走 send-command 通道
            #   明确报 241000 用户没有权限）。不改述会让用户干等 —— 必须说清。
            _hint = _control_permission_hint(self)
            if _hint:
                raise LiCommandError(
                    f"命令下发失败 ({command_key})：{_hint}｜原始错误：{err}",
                    request_id="", result_code=None,
                ) from err
            raise
        request_id = resp.get("requestId") or resp.get("data", {}).get("requestId") or ""

        # cmd/send 自身可能在响应里直接带业务错误
        rc = resp.get("resultCode")
        if rc not in (None, 0):
            _hint = _control_permission_hint(self)
            raise LiCommandError(
                f"命令下发被拒 ({command_key}): resultCode={rc} "
                f"msg={resp.get('resultMsg') or resp.get('message')}"
                + (f"｜{_hint}" if _hint else ""),
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
            # ★★ 2026-10-12：把 **failReason** 也带上。
            #   实测 cpCtrl 关闭充电口盖失败时服务端返回：
            #       pushState=7 pushStateText="执行失败"
            #       resultCode="-2" resultMsg="执行失败"
            #       failReason="set signal err!"      ← 真正有信息量的是这个
            #   此前只取 msg/resultMsg（都是"执行失败"这种无信息量的），
            #   failReason 被整个丢弃 → 用户看不出到底为什么失败。
            #   注：App 里那句"充电口盖已开启，请前往手动关闭"**不在**服务端响应里
            #   （已实测 dump 全部字段），本地 APK 也没有该文案的对照表
            #   （strings.xml / i18n 表 / RN bundle 全搜过）——那是 App 侧
            #   基于车辆状态自行生成的提示，我们无法照搬，只能如实暴露服务端原因。
            _msg = (result.get("msg") or result.get("resultMsg")
                    or RESULT_CODE_HINTS.get(rc_err))
            _fail = str(result.get("failReason")) if result.get("failReason") else ""
            _fail = _fail.strip()
            if _fail and _fail not in (str(_msg) if _msg else ""):
                _msg = f"{_msg}（{_fail}）" if _msg else _fail
            _head = (f"命令执行失败 ({command_key}): pushState={ps} "
                     f"resultCode={rc_err}")
            raise LiCommandError(
                f"{_head} msg={_msg}" if _msg else _head,
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
            command_key, command_data, ps,
            result.get("msg") or result.get("resultMsg"))
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

    # ---------- 任务大师 Task Master（2026-10-07 抓包实证，全 HTTP）----------

    def _get_task_token(self) -> str:
        """任务大师 token = App 权威完整五件套。

        ★ 单换 "task-master" 会被 SSO 拒绝（HTTP 300 access_denied，2026-10-08
          实测），故不再尝试单 scope，也没有回退分支。
        """
        return self._get_scoped(
            "taskmaster", SCOPE_TASK_MASTER, AUD_VSS, ttl=1800)

    def _task_call(self, method: str, path: str, body: str = "") -> dict:
        """任务接口统一入口：完整五件套 token + App 实测头签名调用。

        ★ 401 自愈（2026-10-08 真机教训）：服务端临时拒绝 401 时，
          token 缓存（ttl=1800s）不会自动失效 → 每 60s 重试都复用同一个
          被拒 token，要等 ttl 到期才重取（真机实测 401 连续 147 次、
          跨 10 小时）。故遇 401 主动失效缓存并重取一次。
          仅失效 taskmaster 一项，**不触发 _login()** —— 避免 PR #11
          已修掉的「重登 + 清全缓存」风暴。
        """
        try:
            return self._signed_call_task(
                method, path, body, self._get_task_token())
        except LiApiError as err:
            if not _is_unauthorized(err):
                raise
            _LOGGER.info("任务接口返回 401，失效 token 缓存并重取一次")
            self._invalidate_token("taskmaster")
            return self._signed_call_task(
                method, path, body, self._get_task_token())

    def get_tasks(self, page_size: int = 50, page_no: int = 1,
                  task_type: int = 0) -> list[dict]:
        """我的任务列表 → GET /task-config/mob/my-task-by-vin/{VIN}。

        抓包实测响应: {"message","data":[...45 条...],"code":0,"success":true}
        data 直接是列表，条目含完整 taskValue（开关切换可整条回传 update）。
        """
        path = (EP_TASK_LIST.format(vin=self._vin)
                + f"?pageSize={int(page_size)}&pageNo={int(page_no)}"
                + f"&taskType={int(task_type)}")
        resp = self._task_call("GET", path)
        data = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(data, list):
            raise LiApiError(f"任务列表响应异常: {str(resp)[:200]}")
        return data

    def get_task_dict(self) -> dict | None:
        """拉取任务条件/动作字典（服务端下发；App 靠它渲染"添加条件"页）。

        ★ 路径必须带 /v1/ —— 漏掉返回 100012，与"无权限"无法区分（实测踩过）。
          返回 None 表示"拿不到"（调用方应继续用本地缓存，不要清空）。
        """
        try:
            r = self._task_call("GET", EP_TASK_DICT.format(vin=self._vin))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("拉取任务字典失败（将沿用本地缓存）: %s", err)
            return None
        if not isinstance(r, dict) or r.get("code") != 0:
            _LOGGER.warning("任务字典接口返回异常: %s",
                           (r or {}).get("msg") if isinstance(r, dict) else r)
            return None
        return r

    def save_task(self, task: dict) -> dict:
        """创建任务 → POST /task-config/mob/save/{VIN}（body 用 build_task_payload）。"""
        path = EP_TASK_SAVE.format(vin=self._vin)
        body = json.dumps(task, ensure_ascii=False, separators=(",", ":"))
        resp = self._task_call("POST", path, body)
        _ensure_task_ok("创建任务", resp)
        return resp if isinstance(resp, dict) else {"success": True}

    def update_task(self, task: dict) -> dict:
        """更新任务 → POST /task-config/mob/update-task/{VIN}。

        抓包实测：body 为任务全量对象（与列表条目同构，改 enabled 即启停）。
        """
        if not isinstance(task, dict) or not task.get("configId"):
            raise ValueError("update_task 需要含 configId 的完整任务对象")
        path = EP_TASK_UPDATE.format(vin=self._vin)
        body = json.dumps(task, ensure_ascii=False, separators=(",", ":"))
        resp = self._task_call("POST", path, body)
        _ensure_task_ok("更新任务", resp)
        return resp if isinstance(resp, dict) else {"success": True}

    def delete_task(self, config_id: str) -> dict:
        """删除任务 → DELETE /task-config/mob/delete/{VIN}/{configId}。

        抓包实测（2026-10-07）：HTTP 200，响应 {"message":"SUCCESS","code":0,...}。
        """
        cid = str(config_id).strip() if config_id is not None else ""
        if not cid:
            raise ValueError("delete_task 需要 config_id")
        path = EP_TASK_DELETE.format(vin=self._vin, config_id=cid)
        resp = self._task_call("DELETE", path)
        _ensure_task_ok("删除任务", resp)
        return resp if isinstance(resp, dict) else {"success": True}



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
