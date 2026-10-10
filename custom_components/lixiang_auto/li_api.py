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

EP_CMD_SEND = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd/send"
EP_CMD_RESULT = "/ssp-vehicle-control-service/ssp-vehicle-control/cmd-result"
EP_WAKEUP = "/iot-connect-manager-service/v2/wakeup"
CTRL_DOMAIN = "xcu"

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
            raise LiApiError(
                f"换 token 失败 ({scope}): HTTP {r.status_code} {_hint} "
                f"{r.text[:120]}")
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
        return (r or {}).get("data") or {}

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

    def get_charge_records_monthly_all(self, dt: str) -> dict:
        """某月充电记录明细（**聚合全部 4 种类型**，按时间倒序）。

        ★ 2026-10-09：单一 charging_type 只能取到一种充电方式的记录，
          而 App 明细页展示的是全部类型。默认应聚合，避免「明细里看不到
          5C超充 / 理想超充」——与 get_charge_current_month_kwh 的
          统计口径漏算是同一类问题。

        返回结构与单类型一致：{"code": 0, "data": [...]}，每条记录补充
        chargingType 字段标明来源；全部类型都失败才返回错误码。
        """
        merged: list = []
        got = False
        failed = 0
        for ct, _pfx in CHARGE_TYPE_PREFIX:
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
