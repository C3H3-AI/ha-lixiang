"""车型配置异常体（M01B）的记录与守卫。

为什么单独一份文件
------------------
这份记录【不是】滑门修复的一部分，而是一项独立的发现：**M01B 的
`version` 块本身不完整**，导致 15+ 个标签在它上面同时为假。它回答了
「那些门控到底在区分什么」这个问题，也约束了今后能拿哪些标签当门控依据。

放在独立文件里，是为了让"车型配置数据本身的异常"与"具体功能缺陷"
各自可追溯 —— 前者将来可能只需要更新数据，后者要改代码。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_CFG_DIR = REPO / "custom_components" / "lixiang_auto" / "vehicle_configs"

import sys

sys.path.insert(0, str(REPO / "custom_components" / "lixiang_auto"))
import signals as _sg  # noqa: E402

SIGNALS = _sg.SIGNALS


# ══════════════════════════════════════════════════════════════════════════
#  ★★ M01B 是配置异常体 —— 不要把它当成"真实车型缺 17 个功能"
# ══════════════════════════════════════════════════════════════════════════
class TestM01BIsConfigOutlier:
    """实测（2026-09-29）：**17 个不同的标签在完全相同的 2 个配置上为 false —— M01B**。

        sentry · sentryVideo · scene · ogcType · speedHeat · speedCool
        maintainConfig · remoteParkingOut · multiSlotChargingReservation
        petModeQuitAndLock · remoteInteriorVideo · realtimevideoAudio
        vlaSummon · remoteLockOnReady · autoWakeUp · adFailSafe …

    而且 M01B 的 `version` 块明显稀疏：

        M01B   34 个标签（12 true / 22 false）   ← 全场最少
        其他   40–43 个标签（32–35 true）
        中位   40

    ⇒ 这不是"某款车缺 17 个功能"，而是**该配置的 version 块本身不完整**。
      它极可能是内部/未发布配置（desc 是代号式的 "M01B车型"/"M01Ring车型"，
      而不是 "L6Pro" 这种可读名）。

    本类把它固定下来，原因有两个：

    ① **防止误判**：将来看到 M01B 少了保养/泊车/预约充电实体，
       不要以为是我们的门控 bug —— 它的标签就是这么说，
       而 App 读同一份 JSON、`isSupport` 语义相同，行为一致。
       **我们与 App 保持一致，不去"修正"厂商数据。**

    ② **防止误用**：任何"只在 M01B 上为假"的标签都【不适合】当门控依据 ——
       影响面只有一个异常配置，收益近零、误伤风险却不小。
       （已据此放弃给 ac_fan_speed 加 speedHeat/speedCool 门控。）
    """

    #: 实测只在 M01B 上为 false 的标签
    M01B_ONLY_FALSE = (
        "sentry", "sentryVideo", "scene", "ogcType", "speedHeat", "speedCool",
        "maintainConfig", "remoteParkingOut", "multiSlotChargingReservation",
        "petModeQuitAndLock", "remoteInteriorVideo", "realtimevideoAudio",
        "vlaSummon", "remoteLockOnReady", "autoWakeUp",
    )

    @staticmethod
    def _configs():
        out = []
        for f in sorted(_CFG_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            out.append((f.stem, json.loads(f.read_text(encoding="utf-8"))))
        return out

    def _false_models(self, tag: str) -> set[str]:
        bad = set()
        for _mid, cfg in self._configs():
            v = (cfg.get("version") or {}).get(tag)
            if not isinstance(v, dict) or not v.get("isSupport"):
                bad.add(str(cfg.get("unityModel") or ""))
        return bad

    @pytest.mark.parametrize("tag", M01B_ONLY_FALSE)
    def test_tag_false_only_on_m01b(self, tag):
        """这些标签为假的车型必须【只有】M01B —— 否则说明配置变了，需重评。"""
        bad = self._false_models(tag)
        assert bad == {"M01B"}, (
            f"标签 {tag} 为假的车型是 {sorted(bad)}，期望只有 M01B。\n"
            "  若 M01B 不再是唯一异常体，说明厂商改了配置 —— "
            "请重新评估「只在个别车型为假的标签是否适合当门控依据」。"
        )

    def test_m01b_version_block_is_sparse(self):
        """M01B 的 version 标签数应显著少于其他车型（配置不完整）。"""
        counts = {}
        for _mid, cfg in self._configs():
            um = str(cfg.get("unityModel") or "")
            counts.setdefault(um, []).append(len(cfg.get("version") or {}))
        m01b = max(counts.get("M01B", [0]))
        others = [max(v) for k, v in counts.items() if k != "M01B"]
        assert m01b < min(others), (
            f"M01B 的标签数({m01b}) 不再少于其他所有车型的最少值({min(others)}) —— "
            "配置已变，本测试记录的前提需要更新"
        )

    #: ★ 已知并【有意】使用 M01B-only 标签的 5 处门控（2026-09-29）
    #:
    #:   本测试把它们从"没人注意"变成"显式登记"，但**没有**擅自改行为 ——
    #:   因为改与不改各有一半道理，属于需要维护者拍板的取舍：
    #:
    #:   · 支持保留（= 现状）：App 读同一份 JSON、isSupport 语义相同，
    #:     所以 App 在 M01B 上也不显示保养/泊车/预约充电/场景/充电类型。
    #:     我们的宗旨是「照搬 App」→ 保留即一致。
    #:   · 支持去掉（倾向）：用户明确要求过「只增不删」；而这些标签的
    #:     "区分度"其实只来自 M01B 一份不完整的配置，并非真实产品差异 ——
    #:     据此删实体，等于拿厂商的配置残缺惩罚用户。
    #:
    #:   影响面：M01B 共 2 个配置（desc 均为代号式，疑为内部配置），
    #:   大概率没有真实用户 —— 两种选择实际影响都很小，但它决定了
    #:   【今后】要不要用"只有一个异常车型为假"的标签做门控。
    INTENTIONAL_M01B_GATES = (
        "maintainConfig",                  # 保养 ×3
        "multiSlotChargingReservation",    # 预约充电 ×5（含 1 个 switch）
        "ogcType",                         # OGC 充电类型 ×1
        "remoteParkingOut",                # 泊车状态 ×2
        "scene",                           # 场景模式 ×1
    )

    def test_no_ungated_use_of_m01b_only_tag(self):
        """★ 除上面显式登记的 5 处，不得再用 M01B-only 标签做门控。

        这样任何【新增】的此类门控都会立刻暴露，而不是悄悄混进来。
        """
        used = {
            s.requires.split(":", 1)[1]
            for s in SIGNALS.values()
            if (s.requires or "").startswith("version:")
        }
        unexpected = sorted(
            (used & set(self.M01B_ONLY_FALSE)) - set(self.INTENTIONAL_M01B_GATES)
        )
        assert not unexpected, (
            f"以下门控依据只在 M01B（一个配置异常体）上为假：{unexpected}\n"
            "  这是【新增】的此类门控 —— 请先确认该标签在其他车型上也有区分度，\n"
            "  或把它加进 INTENTIONAL_M01B_GATES 并说明理由。"
        )

    def test_intentional_gates_are_still_m01b_only(self):
        """登记的 5 处必须仍是 M01B-only —— 若某标签有了更广区分度，
        它就变成合理门控，应从例外名单移除（避免名单腐化）。"""
        stale = [t for t in self.INTENTIONAL_M01B_GATES
                 if self._false_models(t) != {"M01B"}]
        assert not stale, (
            f"这些标签已不再是 M01B-only，应从 INTENTIONAL_M01B_GATES 移除：{stale}"
        )
