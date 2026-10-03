"""车型能力表 (vehicle_ability.py) —— 复刻 App 的 VehicleDetails 机制

原理
----
App 的能力判断完全来自【APK 内置的车型配置 JSON】：

    assets/{modelId}.json         ← 68 个车型
      {
        "desc": "L6Pro",
        "unityModel": "L6",
        "platform": "2",
        "temp": {
            "config": [
                {"key": "strgWhlHeatSw", "value": "4", "desc": "方向盘加热"},
                {"key": "flSeatSw",      "value": "3", "desc": "主驾座椅能力"},
                {"key": "secMSeatSw",    "value": "4", "desc": "第二排中座椅能力"},
                {"key": "thirdLSeatSw",  "value": "1", "desc": "第三排左座椅能力"}
            ],
            "other": {"minTemp": 16, "maxTemp": 28, "vehicleSeat": 5}
        },
        "version": {
            "departOnTime": {"desc": "按时出发", "isSupport": true, "supportVersion": "7.1.0"},
            "fridge":       {"desc": "远程冰箱", "isSupport": false},
            ...
        },
        "config": {...外观...}
      }

App 的三个查询方法：

    · getAbilityLeven(tag)          → 查 temp.config，得能力等级
    · vehicleSeat()                 → 读 temp.other.vehicleSeat
    · isSupportCheck(tag, appVer)   → 查 version[tag].isSupport + 版本比较

本模块【逐一对齐】这三个方法。

★ 值语义（实测 68 个车型确认）:
    value = 1  →  【无该硬件】
    value >= 2 →  【有该硬件】（数字越大档位越多）

数据来源
--------
`vehicle_configs/` 目录，从官方 APK 提取（8.27.0，68 个车型）。
文件不随集成改动，新车型只需追加 JSON。

用法
----
    ab = VehicleAbility("100167931652606785")   # L6Pro
    if ab.has("thirdLSeatSw"):
        ...建三排座椅实体...
    if ab.is_supported("departOnTime"):
        ...建按时出发实体...
    print(ab.seat_layout())      # "五座"
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from .const import LOGGER_NAME

_LOGGER = logging.getLogger(LOGGER_NAME)

_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"

# App 在查不到 tag 时返回的默认值（见 JS 的 getAbilityLeven）
DEFAULT_ABILITY_LEVEL = 2

# 值语义：1 = 无硬件
ABILITY_HAS_THRESHOLD = 2


@lru_cache(maxsize=128)
def load_vehicle_config(model_id: str) -> dict[str, Any] | None:
    """读车型配置（等价 App 的 getVehicleConfig(modelId)）。

    App 读的是 `context.getAssets().open(modelId + ".json")`；
    我们读集成目录里的同名文件（从 APK 提取）。

    返回 None 表示该 modelId 没有配置（新车型 / 未知车型）。
    """
    if not model_id:
        return None
    # 防路径穿越：只允许数字
    if not model_id.isdigit():
        _LOGGER.debug("modelId 非法（非数字）: %r", model_id)
        return None

    f = _CONFIG_DIR / f"{model_id}.json"
    if not f.exists():
        _LOGGER.debug("车型配置不存在: %s", f.name)
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("解析车型配置失败 %s: %s", f.name, err)
        return None


@lru_cache(maxsize=1)
def load_model_index() -> dict[str, dict[str, Any]]:
    """读车型索引（modelId → {desc, unityModel, platform, seats}）。"""
    f = _CONFIG_DIR / "_index.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


@lru_cache(maxsize=1)
def load_ability_names() -> dict[str, str]:
    """能力 tag → 中文名（从所有车型 JSON 的 desc 汇总）。"""
    f = _CONFIG_DIR / "_names_zh.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def compare_versions(a: str, b: str) -> int:
    """版本比较（等价 App 的 compareVersions）。

    返回 -1 / 0 / 1。缺省段按 0 处理。
    """
    def _parts(v: str) -> list[int]:
        v = str(v or "").split("-")[0]
        out = []
        for x in v.split("."):
            try:
                out.append(int(x))
            except ValueError:
                out.append(0)
        return out

    pa, pb = _parts(a), _parts(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else 0
        y = pb[i] if i < len(pb) else 0
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


class VehicleAbility:
    """一辆车的能力表（等价 App 的 VehicleDetails + abilityMap）。

    构造后即可查询；若 modelId 无配置，`available` 为 False，
    调用方应回退到 VSS 探测（features.py）。
    """

    def __init__(self, model_id: str | None, app_version: str = "999.99.99"):
        """
        参数:
          model_id:    来自 get_vehicles() 的 modelId
          app_version: 用于 is_support 的版本比较（默认取很高的值，
                       表示"我们的 App 版本足够新"，与 App 行为一致）
        """
        self.model_id = str(model_id or "")
        self.app_version = app_version
        self._cfg = load_vehicle_config(self.model_id)
        self._ability_map: dict[str, int] = {}
        self._version_map: dict[str, dict] = {}
        if self._cfg:
            self._build_maps()

    # ------------------------------------------------------------------
    # 内部：建索引（等价 App 的 initTempConfig）
    # ------------------------------------------------------------------
    def _build_maps(self) -> None:
        cfg = self._cfg or {}
        # ① temp.config → abilityMap    （App: tempConfig.config.forEach(n => abilityMap.set(n.key, n.value))）
        for item in (cfg.get("temp") or {}).get("config") or []:
            key = item.get("key")
            if not key:
                continue
            try:
                self._ability_map[key] = int(item.get("value"))
            except (TypeError, ValueError):
                continue
        # ② version → versionMap
        for k, v in (cfg.get("version") or {}).items():
            if isinstance(v, dict):
                self._version_map[k] = v

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """是否有该车型的配置（无则需回退 VSS 探测）。"""
        return self._cfg is not None

    @property
    def desc(self) -> str:
        """车型名（如 "L6Pro"）。"""
        return (self._cfg or {}).get("desc", "")

    @property
    def unity_model(self) -> str:
        """3D 模型号（如 "L6"）。"""
        return (self._cfg or {}).get("unityModel", "")

    @property
    def platform(self) -> str:
        """平台代号（"1" = M 平台 / "2" = X 平台）。"""
        return str((self._cfg or {}).get("platform", ""))

    @property
    def is_bev(self) -> bool:
        """是否纯电（BEV）——★ 逐字复刻 App 的 `isBev()`。

        App 源码（assets/index.vehicle.js，VehicleTool 上的静态方法）：

            u.isBev = function() {
                var u = (VehicleTool.getVehicleDetails()
                         ?.config?.energy?.power) || [];
                return !(u.length !== 1 || !u.includes('1'));
            }

        即：`power.length === 1 && power.includes('1')`。

        ★ 为什么必须【照抄】而不是「取反」：
          写成 `has_fuel = len(power) >= 2` 看似等价，其实不是 ——
          若将来出现 `["2"]`（单一非电动力）这种取值：
              App 的 isBev  → false（长度不是 1）→ 视为「非纯电 → 有燃油」
              取反写法      → len 只有 1 → 「无燃油」
          两者结论相反。照抄 App 的判据才能保证与 App 行为一致。

        数据来源：APK 内置的车型配置 JSON（68 个），
        字段位置 `config.energy.power`。
        """
        power = self.power_sources
        return not (len(power) != 1 or "1" not in power)

    @property
    def power_sources(self) -> list[str]:
        """车型的动力源列表（config.energy.power）。

        来源：车型配置 JSON 的 `config.energy.power`
              {"desc": "车型基础数据", "energy": {"power": ["1", "2"]}, ...}

        ★ 2026-09-28 实测 68 个车型的取值：
            ["1"]        21 个 —— 全部是 W 系（W01/W02/W04/W05/W10 = i 系列纯电）
            ["1", "2"]   47 个 —— 全部是 L 系（L6/L7/L8/L9 = 增程）
        """
        cfg = self._cfg or {}
        power = ((cfg.get("config") or {}).get("energy") or {}).get("power")
        if isinstance(power, list):
            return [str(x) for x in power]
        return []

    @property
    def has_combustion_engine(self) -> bool:
        """是否带燃油（增程器）——决定是否创建「油量 / 燃油续航」实体。

        ★ 背景（用户反馈「i6 车型显示燃油续航」）：
            i6 属 i 系列纯电（W04），车上没有油箱，
            但集成原先【无条件】创建油量与燃油续航实体 → 用户看到"燃油续航"。

        判据：`not is_bev`（与 App 完全一致，见 is_bev 的说明）。

        ★ 实测 68 个车型：动力源与车系【完美分离，无例外】
            power=["1"]    21 个 → 全部 W 系（W01/W02/W04/W05/W10，i 系列纯电）
            power=["1","2"] 47 个 → 全部非 W 系
                                    （L6/L6B/L7/L7B/L7C/L8/L8B/L8C/L9/L9B/L9C/M01B）

        ⚠️ 更正一条此前的错误说法：曾以为「M01B = MEGA，属纯电却标 2 项动力，
           是配置表笔误」。**该说法不成立** ——
             · 68 个配置里【没有】MEGA（grep 到的 "mega" 是 UI 素材名，如
               config.trail = "mega"，与本车型无关）
             · M01B 实测 vehicleSeat=6、power=["1","2"]，且车系分组与
               L 系一致 → 属【增程】，有燃油是正确行为
           所以不存在例外，也不必为它做任何特殊处理。
        """
        return not self.is_bev

    # ------------------------------------------------------------------
    # ① 等价 App 的 getAbilityLeven(tag)
    # ------------------------------------------------------------------
    def ability_level(self, tag: str) -> int:
        """能力等级（等价 App 的 getAbilityLeven）。

        返回:
            1   = 无该硬件
            >=2 = 有该硬件（数字越大档位越多）
            DEFAULT_ABILITY_LEVEL(2) = **该车型配置里没有这个 tag**

        ⚠️ 注意区分两种情况：
            · tag 存在且 value=1  → 明确"无硬件"
            · tag 不存在          → 未知（App 返回 2）

        ★ 判断"是否有硬件"请用 `has()`，它区分了这两种情况。
        """
        if tag in self._ability_map:
            return self._ability_map[tag]
        return DEFAULT_ABILITY_LEVEL

    def is_configured(self, tag: str) -> bool:
        """该 tag 是否出现在本车型的配置里。

        ★ 用于区分"配置明确说没有"(value=1) 和 "配置里压根没提"(未知)。
        """
        return tag in self._ability_map

    def has(self, tag: str) -> bool:
        """是否有该硬件。

        ★ 与 App 的 getAbilityLeven(tag) > 1 略有不同：
          App 对未配置的 tag 也返回 2（当作"有"），
          但那会导致 [L6 误判为有三排中座椅] 这类问题。

          我们的规则（更严谨）：
            · tag 未配置  → False（宁可不建，也不要建错的）
            · tag=1      → False（明确无硬件）
            · tag>=2     → True

        ★ 这个差异是【刻意的】，并在测试里锁定。
        """
        if tag not in self._ability_map:
            # 未配置 → 不认为有
            return False
        return self._ability_map[tag] >= ABILITY_HAS_THRESHOLD

    # ------------------------------------------------------------------
    # ② 等价 App 的 vehicleSeat()
    # ------------------------------------------------------------------
    def vehicle_seat(self) -> int:
        """座椅总数（App 直接读 temp.other.vehicleSeat）。"""
        other = ((self._cfg or {}).get("temp") or {}).get("other") or {}
        try:
            return int(other.get("vehicleSeat", 0))
        except (TypeError, ValueError):
            return 0

    def seat_layout(self) -> str:
        """座椅布局的中文名。"""
        n = self.vehicle_seat()
        return {2: "两座", 4: "四座", 5: "五座", 6: "六座", 7: "七座"}.get(
            n, f"{n} 座" if n else "未知"
        )

    def temp_range(self) -> tuple[int, int]:
        """空调温度范围 (min, max)。"""
        other = ((self._cfg or {}).get("temp") or {}).get("other") or {}
        try:
            return (int(other.get("minTemp", 16)), int(other.get("maxTemp", 28)))
        except (TypeError, ValueError):
            return (16, 28)

    # ------------------------------------------------------------------
    # ③ 等价 App 的 isSupportCheck(tag, appVer)
    # ------------------------------------------------------------------
    def is_supported(self, tag: str) -> bool:
        """该功能是否被支持（等价 App 的 isSupportCheck）。

        判据（与 App 一致）：
          version[tag].isSupport == true
          且 app_version >= (subKey || supportVersion || appVersion)
        """
        v = self._version_map.get(tag)
        if not v:
            return False
        if not v.get("isSupport"):
            return False
        need = v.get("supportVersion") or v.get("appVersion") or ""
        if not need:
            return True
        return compare_versions(self.app_version, need) >= 0

    def version_info(self, tag: str) -> dict:
        """该 tag 的完整 version 信息（诊断用）。"""
        return dict(self._version_map.get(tag) or {})

    # ------------------------------------------------------------------
    # 便利方法
    # ------------------------------------------------------------------
    def seat_tags(self) -> dict[str, int]:
        """所有座椅/温度能力 tag → 等级。"""
        return {k: v for k, v in self._ability_map.items() if k.endswith("Sw")}

    def supported_features(self) -> list[str]:
        """所有 isSupport=true 的功能 tag。"""
        return [k for k in self._version_map if self.is_supported(k)]

    def unsupported_features(self) -> list[str]:
        """有 tag 但 isSupport=false 的。"""
        return [k for k in self._version_map if not self.is_supported(k)]

    def known_tags(self) -> list[str]:
        """配置里出现的所有 tag（version + temp）。"""
        return sorted(set(self._version_map) | set(self._ability_map))

    def name_of(self, tag: str) -> str:
        """能力 tag → 中文名（App 的 desc 字段）。"""
        return load_ability_names().get(tag, tag)

    def dump(self) -> dict[str, Any]:
        """完整能力表（诊断服务用）。"""
        return {
            "model_id": self.model_id,
            "desc": self.desc,
            "unity_model": self.unity_model,
            "platform": self.platform,
            "available": self.available,
            "seat_layout": self.seat_layout(),
            "vehicle_seat": self.vehicle_seat(),
            "temp_range": list(self.temp_range()),
            "seat_abilities": {k: {"level": v, "name": self.name_of(k)}
                               for k, v in self.seat_tags().items()},
            "features_supported": {k: {"name": self.name_of(k), **self.version_info(k)}
                                   for k in self.supported_features()},
            "features_unsupported": {k: {"name": self.name_of(k), **self.version_info(k)}
                                     for k in self.unsupported_features()},
        }


@lru_cache(maxsize=1)
def load_app_names() -> dict[str, dict[str, str]]:
    """实体名对齐表（key → {zh, en, source}）。

    ★ 名字取自官方 App（APK 的 I18N 与 res/values/strings.xml），
      保证我们的实体名与 App 的叫法一致。
    """
    f = _CONFIG_DIR / "_names_app.json"
    if not f.exists():
        _LOGGER.debug("名称表不存在: %s", f.name)
        return {}
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except Exception as err:  # noqa: BLE001
        # ★ 2026-09-26：文件损坏/编码异常时不能崩
        #   （实体 name 属性里调用它，抛异常会让整个平台 setup 失败）
        _LOGGER.warning("解析名称表失败（将回退默认名）: %s", err)
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, dict)}


def preload_names() -> None:
    """预热名称表（应在 executor 里调用一次，避免事件循环里读文件）。

    ★ HA 会在事件循环里构造实体，若那时首次读 JSON 会触发
      "Detected blocking call to open" 告警。
    """
    load_app_names()


def app_name(key: str, lang: str = "zh", default: str = "") -> str:
    """按 App 的官方叫法取实体名。

    参数:
        key:     我们的实体 key（如 "lock" / "seat_sl_heat"）
        lang:    "zh" 或 "en"
        default: 查不到时的回退值

    用法:
        name = app_name("lock")            # → "车锁"（App 就叫这个）
        name = app_name("lock", "en")      # → "Lock"
    """
    entry = load_app_names().get(key)
    if not entry:
        return default or key
    return entry.get(lang) or entry.get("zh") or default or key


def get_ability(li_api: Any, model_id: str | None = None) -> VehicleAbility:
    """便利函数：拿到当前车的 VehicleAbility。

    若未传 model_id，会尝试从 li_api.get_vehicles() 读。
    失败时返回 available=False 的对象（调用方回退 VSS 探测）。
    """
    if not model_id:
        try:
            veh = li_api.get_vehicles() or []
            if veh:
                model_id = veh[0].get("modelId")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("读 modelId 失败（将回退 VSS 探测）: %s", err)
    return VehicleAbility(model_id)


def list_known_models() -> list[dict[str, Any]]:
    """列出所有已知车型（诊断用）。"""
    idx = load_model_index()
    return [{"modelId": k, **v} for k, v in sorted(idx.items(), key=lambda x: x[1].get("desc", ""))]
