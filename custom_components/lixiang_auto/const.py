"""Constants for Li Auto (Ideal Car) integration.

核心常量来源：对理想汽车 App (com.chehejia.oc.m01) 的逆向分析。
"""

DOMAIN = "lixiang_auto"

# ---------- 理想 IDaaS 登录 (OAuth 设备码 / 验证码) ----------
# 来源: 抓包 account/id.lixiang.com 登录流程 + livis 组件
IDAAS_BASE = "https://id.lixiang.com/api"
ACCOUNT_BASE = "https://account.lixiang.com"

# App OAuth 客户端（来自抓包 /api/auth）
CLIENT_ID = "2AQClOaegaA7XecMSFx1p"
AUDIENCE = "5iIapSfVJlln0vU0OzUCH9"
SCOPE = "iam:client:type:app offline_access"

# ★ 2026-10-10：删除旧「livis 侧门」常量（6qxd1MLZ.../rZgT0SET.../super offline_access）。
#   该组值为早期设备码流程猜测，无任何调用方，且与本次静态逆向结论冲突：
#   理想同学真实登录 client = 40amUDKOdqQTaGDONZC1oY，
#   scope = iam:client:type:lisa，redirect = /app-auth/livis，
#   见 pake_login.LIVIS_LOGIN_CLIENT_ID / APP_LOGIN_PARAMS（V5/V6 实测通过）。

# ---------- 车辆 API 域名 ----------
API_APP = "https://api-app.lixiang.com"   # 车辆主网关（强制 x-chj-sign）

# ---------- API 端点 ----------
EP_KEY_SUITE = "/aisp-app-api/v1-0/keySuite"          # 密钥套件（登录后获取）
# ★ 2026-10-10：真正的设备身份派生端点（ddes 通道，key_suite.py 用）
#   实测：新装机用随机 hac 引导签名即可调通（无需任何旧凭据）
EP_KEY_SUITE_DDES = "/ddes/v1-1/app/key-suite"
EP_VEHICLES = "/aisp-account-api/v1-0/vehicles"       # 车辆列表（X-CHJ-TOKEN 已过期，240225）
# ★ 可用的车辆列表端点（2026-09-23 实测成功）
#   audience=7gbeHMwBPMZA5SU1b2awIo, scope=login
#   返回: {"data":[{vin, modelName, seriesName, vehicleType, vehicleRoleId, ...}]}
AUD_SAOS_VEHICLE = "7gbeHMwBPMZA5SU1b2awIo"
SCOPE_SAOS_VEHICLE = "login"
EP_SAOS_VEHICLES = (
    "/saos-vehicle-api/v2-0/vehicles/basics"
    "?types=owned,transferring,authorized,inviting"
    "&roleIds=1,10,11,13,15&vehicleInfo=true"
)
EP_VEHICLE = "/aisp-account-api/v1-0/vehicles/{vin}"  # 车辆详情
EP_VEHICLE_BASICS = "/saos-vehicle-api/v2-0/vehicles/basics"  # 车辆基础
EP_PROFILE = "/aisp-account-api/v1-0/profile"         # 用户资料

# 车辆控制（逆向自抓包）
EP_WAKEUP = "/iot-connect-manager-service/v2/wakeup"          # 远程唤醒
EP_KMS_JWT = "/bcs-kms-jwt/jwt/iot2/v1-0/"                    # KMS JWT（控制通道）
EP_ICN_GNS = "/icn-gns/gns/app/service/vin/{vin}"            # 控制通道

# ---------- 签名常量 ----------
# 11 参数分隔符 = '\n'（liblxnetwork.so 0xa1768 证实）
SIGN_SEP = "\n"
# 空 body 的 Content-MD5
EMPTY_MD5 = "1B2M2Y8AsgTpgAmY7PhCfg=="

# ---------- 请求头固定值 ----------
# 注: iOS app 实证值（来自抓取的实际请求头）
DEFAULT_ACCEPT = "*/*"                 # iOS 捕获实际为 */*
DEFAULT_CONTENT_TYPE = "application/json"
DEFAULT_CONTENT_LANG = "zh-Hans-CN"    # iOS 捕获
ENV = "prod"
DEVICE_TYPE = "2"                       # iOS
MODEL_NAME = "IOS"
DEVICE_MODEL = "9.7-INCH IPAD"

# 别名（兼容 client 直接引用短名）
CONTENT_TYPE = DEFAULT_CONTENT_TYPE
CONTENT_LANG = DEFAULT_CONTENT_LANG
DEVICE_MODEL_NAME = DEVICE_MODEL

# ---------- 配置项 ----------
CONF_PHONE = "phone"
CONF_PASSWORD = "password"        # PAKE 登录密码 (sso_token 会话13天过期后自动重登)
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN = "access_token"
#: 持久化的登录会话 cookie（★ 2026-10-10）：cookie 13 天有效，
#: 存下来重启即可复用 → **不必每次启动都做密码登录**。
#: 每次密码登录都可能把手机上已登录的「理想汽车」App 顶下线（实测），
#: 所以这条同时是「减少顶号」的关键。
CONF_SESSION_COOKIES = "session_cookies"
CONF_APP_TOKEN = "app_token"      # X-CHJ-TOKEN (APP-xxx), frida从app抓取
CONF_HAC_KEY = "hac_key"          # x-chj-sign 的 HMAC 密钥（k11）
CONF_KEY_ID = "key_id"            # x-chj-key
CONF_DEVICE_ID = "device_id"      # 登录身份 device_id (受信任的可跳短信风控)
CONF_XDEV = "x_chj_deviceid"      # x-chj 签名身份 deviceid (与 hac_key 绑定)
CONF_VIN = "vin"
# 主Bearer(登录后签发的JWT, client=2AQ...). 任意车主登录一次可得, 用它换各scope token
CONF_MAIN_BEARER = "main_bearer"

# ★ 登录身份来源（2026-10-10 新增，用户在配置表单选择）
#   lixiang = 理想汽车 App 身份（主 App KID 派生签名）
#   livis   = 理想同学身份（理想同学 KID 派生签名）
CONF_APP_TYPE = "app_type"
# ★ 2026-10-10：签名身份来源标记 —— 用于识别「v1.4.7 之前建的条目」。
#   老条目的身份来自已删除的内置抓包值（每台设备都一样的 iPad 身份），
#   这类条目应在下次拿到新鲜会话时迁移成【本设备现场派生】的身份。
#   用标记而不是比对旧值：把抓包身份写回代码里正是「去 iPad 化」要避免的。
CONF_IDENTITY_SOURCE = "identity_source"
IDENTITY_SOURCE_DERIVED = "derived"     # 由 key_suite 现场派生（本设备）
IDENTITY_SOURCE_MANUAL = "manual"       # 用户在手动流程里自填四件套
APP_LIXIANG = "lixiang"
APP_LIVIS = "livis"

# ---------- 签名身份默认值 ----------
#
# ★ 2026-10-10「去 iPad 化」（Phase A 实测 V2/V4b/V4c/V4d 定案）：
#   曾内置的 xdev/hac_key/key_id 是抓包抄来的【单台 iPad 的运行时值】，
#   属于每台设备各自生成/服务端下发的身份，已全部删除：
#     · xdev（x_chj_deviceid）← 新条目直接用 identity store 的登录 device_id
#     · hac_key / key_id       ← 由 key_suite.derive_identity() 现场派生
#   老条目 config entry 自带这些值，取值顺序不变，零迁移。
#
#   保留的唯一内置常量是 APP token：2026-10-10 实测（v2_identity_chain）
#   它不绑设备（旧 token 配全新派生身份业务接口 code:0），性质同客户端常量。
try:
    from .secrets import (  # noqa: E402
        DEFAULT_APP_TOKEN as _S_APP_TOKEN,
    )
except ImportError:  # pragma: no cover
    _S_APP_TOKEN = ""

DEFAULT_APP_TOKEN = _S_APP_TOKEN or "APP-50dbc95ceba84c05ac159ea96f2e6ffe"
# ★ 默认登录 device_id（留空 = 由 identity store 自动生成/复用）
#   说明：不要硬编码他人的 device_id —— 那会把所有用户绑到同一设备身份。
#   首次登录时【辅助页面】会让用户的 device_id 受信任，之后免 MFA。
DEFAULT_DEVICE_ID = ""

# ---------- VSS 实时信号路径 (实体key → VSS path, 见 docs/VSS信号映射_HA实体.md) ----------
# ★ 2026-09-24 架构方案 2.8：VSS_PATHS 已迁移到 signals.py
#   （消除重复 —— 原先这里有 127 条，signals.py 里也有一份）
#   这里保留别名，避免破坏外部引用；新代码请用 signals.SIGNALS
from .signals import VSS_PATHS_COMPAT as VSS_PATHS  # noqa: E402

# ---------- 各服务 audience / scope（鸿蒙逆向 /api/auth 实证） ----------
# 用主Bearer POST /api/auth, body{scope, audience, response_type:"token"} 换该服务token
# client_id 统一为 2AQClOaegaA7XecMSFx1p (App主客户端), device_id 用登录时的
REDIRECT_URI = "https://app.lixiang.com/login/subidaas/callback"

# service-card(首页状态): login scope
AUD_SERVICE_CARD = "26FehzsHlrllCSaqI9bFYG"
SCOPE_SERVICE_CARD = "login"
# vss/get-batch + 车控结果 + wakeup: 
AUD_VEHICLE_VSS = "1j0vgTqagJUHuT6nLmbTGx"
SCOPE_VEHICLE_VSS = (
    "remote-wakeup:wakeup veh-ctrl:cmd-result-get veh-ctrl:cmd-send "
    "vss:get-batch task-master"
)
# 车控(锁车/空调等, scope里VIN后缀)
AUD_VEHICLE_CTRL = "1j0vgTqagJUHuT6nLmbTGx"
def veh_ctrl_scope(vin):  # 车控scope含VIN, 运行时动态构造
    # ⚠️ 2026-10-07：本函数疑似旧路径 —— auth.get_veh_ctrl_token() 未见调用方，
    #    实际车控 VAT scope 以 li_api.vat_scope() / VAT_SCOPE_COMMANDS 为准
    #    （真机实证 14 项）。此表缺 remoteADCtrl/remoteADInit/fTkC，
    #    勿在此增删 scope；如确认废弃请整体删除。
    scopes = [
        f"remoteVehFrgControl:{vin}",
        f"remoteVehAuth:{vin}",
        f"remoteVehLockControl:{vin}",
        f"remoteVehPlgControl:{vin}",
        f"remoteVehSearch:{vin}",
        f"remoteVehWdwControl:{vin}",
        f"remoteVehACSmartControl:{vin}",
        f"remoteVehACFirstControl:{vin}",
        f"ssCtrl:{vin}",
        f"rmCtrl:{vin}",
        f"cpCtrl:{vin}",
    ]
    return " ".join(scopes)
# 充电状态 bsp-vcp-message/vehicle/charge
AUD_CHARGE = "1j0vgTqagJUHuT6nLmbTGx"  # 待实证, 预留

# ★ 2026-10-01 实测确认：lcp-bff-app-api 通道
#   来源：App 的 subTokenData（服务端下发，见 mmkv/m01_sp）
#   {"type":"lcp-bff-app-api","audience":"3N1l45XSeMOaid2RgDLiLA",
#    "disableIAM":1,"scope":["login"],"urls":["/lcp-bff-app-api"]}
#   ★ 该条白名单是【全前缀放行】，故 /lcp-bff-app-api/** 均可用
#   实测已通：plate-number/v1/list、user-settings/v1/user-pnc-switch/list、
#             serve-page/v1/station-stats、travel-planning/v1/simulate/energy/cost
AUD_LCP_BFF = "3N1l45XSeMOaid2RgDLiLA"
SCOPE_LCP_BFF = "login"
EP_LCP_PNC_LIST = "/lcp-bff-app-api/user-settings/v1/user-pnc-switch/list"

# 换token请求路径
EP_AUTH = "/api/auth"

# ---------- 状态 ----------
ATTR_STATUS = "status"
ATTR_BATTERY = "battery_level"
ATTR_RANGE = "range"
ATTR_ODOMETER = "odometer"
ATTR_LOCKED = "locked"
ATTR_CHARGING = "charging"
ATTR_TEMP = "temperature"

# 扫描周期（借鉴 huawei-auto-cloud 的可配置设计）
#   华为: DEFAULT=30s, MIN=10s
#   我们: DEFAULT=60s, MIN=30s（理想服务端压力较大，保守取 60s）
CONF_SCAN_INTERVAL = "scan_interval"
# 安全开关：关闭后所有车控实体变只读（防误操作）
CONF_ENABLE_CONTROL = "enable_control"
DEFAULT_ENABLE_CONTROL = True
DEFAULT_SCAN_INTERVAL_SECONDS = 60
MIN_SCAN_INTERVAL_SECONDS = 30
MAX_SCAN_INTERVAL_SECONDS = 3600

SCAN_INTERVAL_SECONDS = DEFAULT_SCAN_INTERVAL_SECONDS


def scan_interval_seconds(options=None) -> int:
    """从集成选项读取轮询间隔（秒），带范围钳制。"""
    try:
        sec = int((options or {}).get(CONF_SCAN_INTERVAL,
                                      DEFAULT_SCAN_INTERVAL_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL_SECONDS
    return max(MIN_SCAN_INTERVAL_SECONDS, min(MAX_SCAN_INTERVAL_SECONDS, sec))

# 日志
# ★ 2026-10-10：logger 必须落在 `custom_components.` 命名空间下。
#
#   事实（实测）：HA 的 root logger 默认是 WARNING
#   （bootstrap.py: `logger.setLevel(INFO if verbose else WARNING)`），
#   所以 `custom_components.*` **也**默认不输出 INFO —— 用户要开日志，
#   靠的是 HA 的标准入口：集成页「启用调试日志」按钮，或 configuration.yaml
#   里写 `logger.logs.custom_components.lixiang_auto: info`。
#
#   改名的真实收益（实测）：HA 那个一键入口用的就是这个命名空间。
#   改名之前，本集成 50+ 个模块用的是裸名 `lixiang_auto`，
#   `custom_components.lixiang_auto: info` 只能覆盖 4 个
#   用 `logging.getLogger(__name__)` 的模块（li_api/auth/client/pake_login）
#   → 一键调试是「半残」的（coordinator/config_flow 等全都不出日志）。
#   改名后同一行配置覆盖全部模块（实测 16 条 INFO 正常输出）。
LOGGER_NAME = "custom_components.lixiang_auto"
