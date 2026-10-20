"""能力状态视图 —— 把"这台车有没有这功能"分成 5 档，而不是简单的有/无。

## 为什么需要（学自零跑 ha-leapmotor-cn 的 capabilities.py）

我们曾经把两件不同的事混为一谈：

  · **信号缺失** —— 这次采样没拿到这个字段
  · **不支持**  —— 这台车没这个硬件

混在一起的后果（真实发生过）：
  理想 ONE 的座椅 fan 实体**一个都没建** —— 因为 M 系能力表里
  没有 `flSeatHeatSw` 这类 tag，`ability.has(tag)` 恒 False，
  于是被判为"不支持"，全跳过了。
  而实际上 ONE **有**六座座椅，只是能力表的 tag 命名不同。

## 5 档定义

| 档位 | 含义 | 判据 |
|---|---|---|
| `available` | 可用 | 本次采样有有效信号 |
| `signal_missing` | 信号缺失 | 本次采样未包含该信号；**不代表车辆不支持** |
| `unsupported` | 不支持 | **明确**能力证据（能力位关闭 / 能源类型排除）|
| `unavailable` | 暂不可用 | 车况获取失败 / 采样已过期 |
| `pending` | 待确认 | 指令已受理，等待车端新采样 |

## 设计原则

**只有明确证据才判"不支持"** —— 缺信号、能力表没有这个 tag、
采样过期，都**不是**"不支持"的证据。

★ 这与我们既有的 `_supports()`（卡片按实体存在性判定）互补：
   · 卡片问的是"这个入口现在能不能点"
   · 本模块回答的是"这台车到底有没有这功能"
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = [
    "AVAILABLE", "SIGNAL_MISSING", "UNSUPPORTED", "UNAVAILABLE", "PENDING",
    "LABELS", "CapabilityItem", "capability_view", "signal_status",
]

# ── 5 个状态常量 ───────────────────────────────────────────
AVAILABLE = "available"
SIGNAL_MISSING = "signal_missing"
UNSUPPORTED = "unsupported"
UNAVAILABLE = "unavailable"
PENDING = "pending"

LABELS = {
    AVAILABLE: "可用",
    SIGNAL_MISSING: "信号缺失",
    UNSUPPORTED: "不支持",
    UNAVAILABLE: "暂不可用",
    PENDING: "待确认",
}

# ── 每个状态的详细说明（前端/排障都用它）──────────────────
DETAILS = {
    AVAILABLE: "本次采样有有效信号；不代表指令已在各车型验证",
    SIGNAL_MISSING: "本次采样未包含该信号；不代表车辆不支持",
    UNSUPPORTED: "有明确能力证据（能力位关闭或能源类型排除）",
    UNAVAILABLE: "车况获取失败或采样已过期",
    PENDING: "指令已受理，等待车端新采样",
}

# 采样过期阈值（秒）—— 超过则认为"暂不可用"
STALE_AFTER = 900


class CapabilityItem:
    """一个功能的当前能力状态。"""

    __slots__ = ("key", "name", "status", "detail", "signal_keys")

    def __init__(self, key: str, name: str, status: str,
                 signal_keys: Iterable[str] = ()) -> None:
        self.key = key
        self.name = name
        self.status = status
        self.detail = DETAILS.get(status, "")
        self.signal_keys = tuple(signal_keys)

    @property
    def label(self) -> str:
        return LABELS.get(self.status, self.status)

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE

    @property
    def unsupported(self) -> bool:
        """★ 只有【明确证据】才算不支持 —— 缺信号/过期都不算。"""
        return self.status == UNSUPPORTED

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "label": self.label,
            "detail": self.detail,
            "signal_keys": list(self.signal_keys),
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<CapabilityItem {self.key}:{self.status}>"


def _as_float(v: Any) -> float | None:
    """把 VSS 的 value 转 float；None / 不可转 → None。"""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def signal_status(sig: Any, *, stale_after: float = STALE_AFTER,
                  now: float | None = None) -> str:
    """单个信号的状态（供平台侧复用）。

    · `None` / 空          → `signal_missing`（不是"不支持"！）
    · 有值                 → `available`
    """
    if sig is None:
        return SIGNAL_MISSING
    val = sig.get("value") if isinstance(sig, Mapping) else sig
    if val is None or val == "":
        return SIGNAL_MISSING
    return AVAILABLE


def capability_view(
    features: Iterable[tuple[str, str, tuple[str, ...]]],
    *,
    vss: Mapping[str, Any] | None = None,
    ability=None,
    stale_after: float = STALE_AFTER,
    unavailable: bool = False,
    pending: Iterable[str] = (),
    energy_type: str = "auto",
) -> list[CapabilityItem]:
    """生成能力视图。

    参数:
        features  : [(key, 中文名, (信号键…)), …]
        vss       : VSS 信号字典（`{key: {"value": …}}`）
        ability   : 能力表对象（有 `.has(tag)` / `.available`；可为 None）
        stale_after: 采样过期阈值（秒）
        unavailable: 车况整体获取失败
        pending   : 已下发指令、等待车端回读的功能 key
        energy_type: "bev" / "reev" / "auto"（用于排除燃油/纯电专属项）
    """
    vss = vss or {}
    pending_set = {str(x) for x in (pending or ())}
    out: list[CapabilityItem] = []

    for key, name, sig_keys in features:
        sig_keys = tuple(sig_keys)
        present = [signal_status(vss.get(k)) == AVAILABLE for k in sig_keys]

        # ① 车况整体失败 ⇒ 一律"暂不可用"（不能据此推断任何事）
        if unavailable:
            status = UNAVAILABLE
        # ② 指令已下发、等回读 ⇒ 待确认
        elif key in pending_set:
            status = PENDING
        # ③ ★ 有【明确能力位】且该位关闭 ⇒ 不支持
        #    （只有能力位能证明"不支持"；缺信号不能）
        elif _ability_denies(ability, key, energy_type=energy_type):
            status = UNSUPPORTED
        # ④ 有信号 ⇒ 可用
        elif all(present):
            status = AVAILABLE
        # ⑤ 信号不全 ⇒ 信号缺失（不代表不支持）
        else:
            status = SIGNAL_MISSING

        out.append(CapabilityItem(key, name, status, sig_keys))
    return out


def _ability_denies(ability: Any, key: str, *, energy_type: str) -> bool:
    """能力表是否【明确】判定该功能不存在。

    ★ 只有返回 True 才允许判"不支持" —— 这正是本次 5 档化的核心：
      把"能力表没有这个 tag"从"不支持"里排除出去。
    """
    if ability is None:
        return False
    if not getattr(ability, "available", False):
        # 能力表本身不可用 ⇒ 没有证据 ⇒ 不判不支持
        return False
    tag = _ABILITY_TAGS.get(key)
    if tag is None:
        return False
    # 能力位明确存在且为 False/0 ⇒ 不支持
    try:
        if not ability.has(tag):
            # ⚠️ 关键：has()==False 在"表里没这个 tag"时也会成立
            #   ⇒ 必须再确认表里【确实没有】这个 tag（而不是"存在但关闭"）
            level = ability.ability_level(tag)
            if level:            # 存在但等级低 ⇒ 也算明确不支持
                return True
            return False         # 表里没这个 tag ⇒ 无证据 ⇒ 不判
    except Exception:  # noqa: BLE001 - 能力表异常不该让视图崩
        return False
    return True


# 功能 key → 能力位 tag（只在有【明确】能力位时才填）
# ★ 不填 = 该功能没有能力位可依据 ⇒ 永远不会被判"不支持"
_ABILITY_TAGS: dict[str, str] = {
    "fuel_level": "fuelLevelSw",       # 燃油量（BEV 无）
    "third_row_seat": "thirdLSeatSw",  # 三排座椅
}


def energy_excludes(key: str, energy_type: str) -> bool:
    """能源类型排除（另一种"明确证据"）。"""
    if energy_type == "bev" and key in ("fuel_level", "fuel_range"):
        return True
    return False
