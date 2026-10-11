"""信号值映射的证据等级守卫（2026-10-11）。

事故
----
后视镜「展开/收起」长期映射错误。复盘发现三个叠加问题：

1. 逆向产物里只有**路径对照表**（`LxMeshVssConstant` 只有路径常量；
   `LiAutoXSignal.json` 只有 `datatype` + `description`），
   **没有"值 → 含义"的对照表** —— 语义只能靠推断或实测。
2. 文档却写了「来源：xxx.smali:638」这种**看似具体的行号** ——
   实际那行只有路径常量。**推断被伪装成实证**，于是没人再去核实。
3. 当时唯一的"实测值 = 1"来自**模拟器** VIN `TESTVIN0000000001`，
   模拟器的值不能作为语义依据。真相（1 = 收起）直到车主物理确认才定案。

制度（见 `translations.py` 文件头）
-------------------------------
| 等级   | 含义                        | 要求                   |
|--------|-----------------------------|------------------------|
| [实测] | 真车物理状态对照            | 写明日期与条件         |
| [实证] | APK/资源里有可指认出处      | 写明文件               |
| [推断] | 依据命名/规律/同类项推测    | **必须显式标注**       |

未标注的一律按 [推断] 处理。

本守卫的作用
------------
1. 制度必须在文件里存在（防止被后人"清理"掉）
2. 已实测/实证的关键映射必须有标注（防止被误删依据）
3. **[推断] 条数锁定上限** —— 只能减少，不能悄悄增加。
   这是本守卫最重要的一条：让"未经确认就新增一条猜测"在测试里立刻暴露。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TR = ROOT / "custom_components" / "lixiang_auto" / "translations.py"

#: 2026-10-11 基线：VALUE_MAPS 里未标注 [实测]/[实证] 的条目数（= 视为 [推断]）
#: 只能下降。每次有映射被实测确认，就下调这个数字（并在 translations.py 补标注）。
MAX_UNVERIFIED = 26   # 基线实测值（2026-10-11），确认一条减一


def _src() -> str:
    return TR.read_text(encoding="utf-8")


def _value_map_lines() -> list[tuple[int, str]]:
    """VALUE_MAPS 内的映射条目 → [(行号, 该行)]"""
    src = _src()
    i = src.index("VALUE_MAPS")
    out = []
    for n, ln in enumerate(src[i:].splitlines(), start=1):
        if ln.strip().startswith("}"):
            break
        if re.match(r'^\s*"[^"]+"\s*:', ln):
            out.append((n, ln))
    return out


class TestEvidencePolicy:
    def test_policy_banner_exists(self):
        """证据等级制度必须写在文件头（防止被后人当无用注释删掉）。"""
        head = _src()[:6000]
        for token in ("[实测]", "[实证]", "[推断]", "证据等级"):
            assert token in head, f"translations.py 文件头缺少「{token}」（证据等级制度）"

    def test_banner_records_the_incident(self):
        """必须写清事故与复盘结论 —— 不知道为什么会错，就会再犯。"""
        head = _src()[:6000]
        assert "后视镜" in head, "制度说明未点明后视镜这次事故"
        assert "模拟器" in head, "必须写明「模拟器值不能作语义依据」"

    def test_verified_keys_are_annotated(self):
        """已实测/实证的关键映射必须带标注（依据不能被悄悄删掉）。"""
        src = _src()
        required = {
            "LRearMirro": "[实测]",   # 2026-10-11 车主物理确认
            "RRearMirro": "[实测]",
            "ChargeStatus": "[实测]",
            "DoorLockStatus.MainDoor": "[实证]",
        }
        for key, tag in required.items():
            idx = src.index(f'"{key}"')
            # 往前看 12 行注释
            ctx = src[max(0, idx - 900):idx]
            assert tag in ctx, f"{key} 缺少 {tag} 标注（依据被删了？）"

    def test_mirror_keeps_its_incident_note(self):
        """后视镜那条必须保留"旧映射是推断、且伪装成有出处"的记述。"""
        src = _src()
        idx = src.index('"LRearMirro"')
        ctx = src[max(0, idx - 1200):idx]
        assert "推断" in ctx, "后视镜映射必须写明旧值是推断而来"
        assert "638" in ctx or "只有路径常量" in ctx, \
            "必须点明所谓『来源行』其实只有路径常量（避免再次误信）"

    def test_unverified_count_within_cap(self):
        """★ 未标注 [实测]/[实证] 的映射数不得超过上限。

        这是本守卫最关键的一条：**禁止悄悄新增未验证的猜测**。
        每确认一条就把 MAX_UNVERIFIED 调小一格（并补标注）。
        """
        src = _src()
        lines = _value_map_lines()
        unverified = 0
        for _, ln in lines:
            key = re.match(r'^\s*"([^"]+)"', ln).group(1)
            idx = src.index(ln)
            ctx = src[max(0, idx - 900):idx]
            if "[实测]" not in ctx and "[实证]" not in ctx:
                unverified += 1
        assert unverified <= MAX_UNVERIFIED, (
            f"未标注证据等级的映射有 {unverified} 条，超过上限 {MAX_UNVERIFIED}。"
            "\n→ 新增映射必须：① 标 [实测]/[实证] 并写明依据，"
            "或 ② 先标 [推断] 并把 MAX_UNVERIFIED 一并上调（等于承认这是猜测）")

    def test_cap_only_decreases(self):
        """上限必须是非负且合理的整数（防止有人把它改成 9999 绕过守卫）。"""
        assert isinstance(MAX_UNVERIFIED, int)
        assert 0 < MAX_UNVERIFIED <= 69, (
            f"上限 {MAX_UNVERIFIED} 不合理（映射总数约 69；上限过大等于形同虚设）")
