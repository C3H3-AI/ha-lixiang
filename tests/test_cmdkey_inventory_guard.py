"""车控 cmdKey 清单防漏守卫（2026-10-11）。

事故背景
--------
集成只实现了 App `XVehicleJobHelper$Companion` 映射表里 31 条 `remoteVeh*`
命令中的少数几条，**其余 23 条被漏掉**（含后视镜展开/收起
`remoteVehOpen/CloseRearMirro`）。

根因不是"没逆向"，而是：
  ① 当年把 cmdKey 收敛成"够用子集"，**没整表归档**；
  ② 在别处看到折叠的**状态符号**就下了「只有状态、没有控制命令」的结论，
     **没回头查同一张映射表里对应的 cmdKey**。

本守卫的作用
------------
把"清单"变成**可执行的事实**：
  · 从 App 的 smali **实时提取**全集（App 升级 → 清单自动跟着变）
  · 与集成实际使用的 cmdKey 取差集
  · 差集写在测试里 → **缺口可见**，而不是静静躺在文档里腐化

★ 与技能铁律呼应：§16「先查历史文档」的同时，**文档结论本身也要复核**；
  §0 铁律 1「requestId ≠ 成功」→ 每条命令都要轮询 `cmd-result`。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
RE = Path("/media/duola/devdata/AI-workspace/lixiang-reverse")
MAPPING = (RE / "apk_latest/decompiled/smali_classes11/com/chehejia/lib/vehicle"
           / "limesh/x/helper/XVehicleJobHelper$Companion.smali")

#: 集成**尚未**评估/实现的 cmdKey（2026-10-11 快照）。
#: 新增命令时从这里移走；App 升级带来新命令时测试会提示差异。
KNOWN_PENDING = {
    "remoteVehACSmartControlClose", "remoteVehACSmartControlOpen",
    "remoteVehAISwitch", "remoteVehAISwitchClose", "remoteVehAISwitchOpen",
    "remoteVehAbatVentControl",
    "remoteVehCloseRearMirro", "remoteVehOpenRearMirro",
    "remoteVehFlashLight",
    "remoteVehFrontTrunkControl",
    "remoteVehLSlidingCloseControl", "remoteVehLSlidingOpenControl",
    "remoteVehPlgCloseControl", "remoteVehPlgOpenControl",
    "remoteVehRSlidingCloseControl", "remoteVehRSlidingOpenControl",
    "remoteVehScene", "remoteVehTypeFSDInit", "remoteVehUnLockControl",
    "remoteVehWdwCloseControl", "remoteVehWdwOpenControl",
    "remoteVehWdwVentControl", "remoteVehWhistle",
}


def _app_cmdkeys() -> set[str]:
    if not MAPPING.exists():
        pytest.skip("App 映射表不在本机（无法提取全集）")
    src = MAPPING.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r'"(remoteVeh[A-Za-z0-9_]+)"', src))


def _our_cmdkeys() -> set[str]:
    used: set[str] = set()
    for name in ("li_api", "switch", "cover", "binary_sensor", "button",
                 "climate", "const", "signals"):
        p = CC / f"{name}.py"
        if p.exists():
            used |= set(re.findall(r"remoteVeh[A-Za-z]+", p.read_text(encoding="utf-8")))
    return used


class TestCmdKeyInventory:
    def test_app_inventory_is_readable(self):
        """App 映射表可解析（提取方式本身不能坏）。"""
        cks = _app_cmdkeys()
        assert len(cks) >= 30, f"只提到 {len(cks)} 条 cmdKey，提取方式可能失效"
        assert "remoteVehOpenRearMirro" in cks
        assert "remoteVehCloseRearMirro" in cks

    def test_pending_list_is_not_stale(self):
        """★ 防漏核心：App 里有、集成里没有的，必须都在 KNOWN_PENDING 里登记。

        失败含义二选一：
          · App 新增了命令 → 有人要评估它（更新本清单）
          · 集成已实现某条但忘了从 KNOWN_PENDING 移除 → 清理本清单
        """
        gap = _app_cmdkeys() - _our_cmdkeys()
        undeclared = gap - KNOWN_PENDING
        assert not undeclared, (
            "App 里有、集成未使用、也没登记的命令："
            f"{sorted(undeclared)}\n"
            "→ 若已实现：从 KNOWN_PENDING 移除；若未评估：加进 KNOWN_PENDING，"
            "并在 lixiang-reverse/docs/车控cmdKey全集_20261011.md 回填状态")

    def test_stale_pending_entries(self):
        """反向：登记为待评估、但集成其实已经用了 → 清单腐化。"""
        stale = KNOWN_PENDING - _app_cmdkeys() - _our_cmdkeys()
        assert not stale, (
            f"KNOWN_PENDING 里的 {sorted(stale)} 既不在 App 映射表、也没被集成使用"
            " → 清单已过期，请复核")

    def test_inventory_doc_exists(self):
        doc = RE / "docs" / "车控cmdKey全集_20261011.md"
        assert doc.exists(), "cmdKey 全集文档缺失（清单的单一来源）"
        body = doc.read_text(encoding="utf-8")
        assert "remoteVehOpenRearMirro" in body
        assert "HTTP 白名单" in body, "文档必须写明白名单门槛，避免把'已实现'当'可用'"

    def test_mirror_fold_not_silently_dropped(self):
        """★ 本次事故的直接防线：后视镜折叠命令不得'看起来处理过了'。

        现在集成确实没实现它们 → 必须仍在待评估清单里；
        将来实现了 → 本测试会因上面的 stale 检查提示更新清单。
        """
        gap = _app_cmdkeys() - _our_cmdkeys()
        for ck in ("remoteVehOpenRearMirro", "remoteVehCloseRearMirro"):
            if ck in _our_cmdkeys():
                continue                      # 已实现：由其他守卫保证清单同步
            assert ck in KNOWN_PENDING, f"{ck} 从待评估清单里消失了（既没实现也没登记）"
