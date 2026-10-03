#!/usr/bin/env python3
"""从现有分散定义生成 signals.py（架构方案 2.2 的迁移脚本）

★ 一次性工具，**不在运行时使用**。

背景
----
新增一个信号要改 5 处：
  ① const.py         VSS_PATHS（路径）
  ② sensor.py        _mk(...) / binary_sensor.py 的 Description
  ③ coordinator.py   分频前缀
  ④ translations.py  值翻译
  ⑤ （二元传感器另算）

这个脚本把 ①~④ 合并成一张 `SIGNALS` 表，人工校对后替换。

用法
----
    python3 tools/gen_signals.py <集成目录> [--out signals_gen.py]

它会：
  1. 解析 const.py 的 VSS_PATHS
  2. 解析 sensor.py 的 _mk 调用（名称/单位/图标/分类）
  3. 解析 binary_sensor.py 的 Description（name/device_class/kind）
  4. 解析 coordinator.py 的 MID/LOW 前缀 → freq
  5. 解析 translations.py 的映射 → semantics/翻译
  6. 输出 signals_gen.py（人工校对后改名 signals.py）

★ 重要：脚本只做**机械合并**，无法判断语义正确性。
        生成的骨架必须人工逐条校对（尤其 kind → semantics 的映射）。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


def parse_vss_paths(const_py: Path) -> dict[str, str]:
    """解析 const.py 的 VSS_PATHS 字典。"""
    src = const_py.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "VSS_PATHS":
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError:
                        pass
    return {}


def parse_sensor_desc(sensor_py: Path) -> dict[str, dict]:
    """解析 sensor.py 的 _mk(key, (name, dclass, unit, sclass, icon, cat))。"""
    src = sensor_py.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    pattern = re.compile(
        r'_mk\(\s*"([^"]+)"\s*,\s*\(([^)]+)\)\s*\)',
        re.S,
    )
    for m in pattern.finditer(src):
        key = m.group(1)
        parts = [p.strip().strip("'\"") for p in m.group(2).split(",")]
        parts = [("" if p == "None" else p) for p in parts]
        while len(parts) < 6:
            parts.append("")
        out[key] = {
            "name": parts[0],
            "device_class": parts[1],
            "unit": parts[2],
            "state_class": parts[3],
            "icon": parts[4],
            "category": parts[5],
        }
    return out


def parse_binary_desc(bs_py: Path) -> dict[str, dict]:
    """解析 binary_sensor.py 的 BinarySensorEntityDescription + kind。"""
    src = bs_py.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    # 匹配 (BinarySensorEntityDescription(key="...", name="...", ...), "kind")
    pattern = re.compile(
        r'\(BinarySensorEntityDescription\(\s*key="([^"]+)"\s*,\s*name="([^"]+)"'
        r'(.*?)\)\s*,\s*"([^"]+)"\s*\)',
        re.S,
    )
    for m in pattern.finditer(src):
        key, name, rest, kind = m.groups()
        dc = re.search(r'device_class=BinarySensorDeviceClass\.(\w+)', rest)
        icon = re.search(r'icon="([^"]+)"', rest)
        out[key] = {
            "name": name,
            "device_class": dc.group(1) if dc else "",
            "icon": icon.group(1) if icon else "",
            "kind": kind,
        }
    return out


def parse_freq(coord_py: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """解析 coordinator.py 的 MID/LOW 前缀元组。"""
    src = coord_py.read_text(encoding="utf-8")
    mid = low = ()
    for name in ("MID_FREQ_PREFIXES", "LOW_FREQ_PREFIXES"):
        m = re.search(rf"{name}\s*=\s*\((.*?)\)", src, re.S)
        if m:
            items = tuple(re.findall(r'"([^"]+)"', m.group(1)))
            if name.startswith("MID"):
                mid = items
            else:
                low = items
    return mid, low


def parse_translations(tr_py: Path) -> dict[str, dict]:
    """解析 translations.py 的 VALUE_MAPS。

    ★ 不能用 ast.literal_eval —— 字典里含注释，需要逐行正则提取。
      格式： "Key":  {0: "文案", 1: "文案"},
    """
    src = tr_py.read_text(encoding="utf-8")
    out: dict[str, dict] = {}

    # 找 VALUE_MAPS = { ... } 的范围
    m = re.search(r"VALUE_MAPS[^=]*=\s*\{", src)
    if not m:
        return out
    start = m.end() - 1
    depth = 0
    end = start
    for i in range(start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    block = src[start:end + 1]

    # 逐条提取 "Key": {0: "x", 1: "y"},
    pat = re.compile(r'"([^"]+)"\s*:\s*\{([^}]*)\}')
    for mm in pat.finditer(block):
        key = mm.group(1)
        inner = mm.group(2)
        pairs = re.findall(r'(-?\d+)\s*:\s*"([^"]*)"', inner)
        if pairs:
            out[key] = {int(k): v for k, v in pairs}
    return out


def freq_of(key: str, mid: tuple[str, ...], low: tuple[str, ...]) -> str:
    for pre in low:
        if key == pre or key.startswith(pre + "_") or key.startswith(pre):
            return "LOW"
    for pre in mid:
        if key == pre or key.startswith(pre + "_") or key.startswith(pre):
            return "MID"
    return "HIGH"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("integration_dir", help="custom_components/lixiang_auto 目录")
    ap.add_argument("--out", default="signals_gen.py", help="输出文件")
    args = ap.parse_args()

    base = Path(args.integration_dir)
    if not base.is_dir():
        print(f"✗ 目录不存在: {base}", file=sys.stderr)
        return 1

    vss = parse_vss_paths(base / "const.py")
    sensors = parse_sensor_desc(base / "sensor.py")
    binaries = parse_binary_desc(base / "binary_sensor.py")
    mid, low = parse_freq(base / "coordinator.py")
    trs = parse_translations(base / "translations.py")

    print(f"  VSS_PATHS:        {len(vss)} 条")
    print(f"  sensor 描述:      {len(sensors)} 条")
    print(f"  binary 描述:      {len(binaries)} 条")
    print(f"  MID 前缀:         {len(mid)} 个")
    print(f"  LOW 前缀:         {len(low)} 个")
    print(f"  翻译映射:         {len(trs)} 条")

    # 合并（以 VSS_PATHS 为主键）
    lines = [
        '"""信号声明表（自动生成，需人工校对）',
        "",
        f"来源: {base}",
        f"生成: tools/gen_signals.py",
        "",
        "⚠️ 这是【机械合并】的结果，语义需人工校对：",
        "  · kind → semantics 的映射需逐条确认",
        "  · 分频是根据前缀猜的，可能不准",
        "  · 翻译需与 translations.py 对齐",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from enum import StrEnum",
        "from typing import Any",
        "",
        "",
        "class Freq(StrEnum):",
        '    """轮询频率档位。"""',
        '    HIGH = "high"',
        '    MID = "mid"',
        '    LOW = "low"',
        "",
        "",
        "class Semantics(StrEnum):",
        '    """值语义（决定实体平台与判定）。"""',
        '    RAW = "raw"                # 原样输出',
        '    LOCKED = "locked"          # 0=已锁 → on = 未落锁',
        '    DOOR_OPEN = "door_open"    # ==1 才开（XDoorDataHandle）',
        '    PLUGGED = "plugged"        # 非0 = 已连接',
        '    CONNECTED = "connected"    # 非0 = 已连接',
        '    ALARM = "alarm"            # 非0 = 告警',
        '    SWITCH_ON = "switch_on"    # 非0 = 开启',
        '    CHARGE_LID = "charge_lid"  # -1=无效(unknown)，0=关，非0=开',
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class SignalSpec:",
        '    """一个 VSS 信号的完整声明。"""',
        "    key: str",
        "    path: str",
        "    name: str",
        "    freq: Freq = Freq.HIGH",
        "    semantics: Semantics = Semantics.RAW",
        "    json_field: str | None = None",
        "    device_class: str | None = None",
        "    unit: str | None = None",
        "    state_class: str | None = None",
        "    icon: str | None = None",
        "    category: str = ''",
        "    platforms: frozenset[str] = field(default_factory=lambda: frozenset({'sensor'}))",
        "    diagnostic: bool = False",
        "",
        "",
        "SIGNALS: dict[str, SignalSpec] = {",
    ]

    # kind → semantics 映射（★ 需人工校对）
    KIND_MAP = {
        "lock": "LOCKED",        # 0=已锁 → on=未锁
        "door": "DOOR_OPEN",     # ==1 才开（XDoorDataHandle.smali:310）
        "trunk": "DOOR_OPEN",    # 同上（尾门还有 Lock 优先聚合）
        "plug": "PLUGGED",       # 非0 = 已插入
        "conn": "CONNECTED",     # 非0 = 已连接
        "warn": "ALARM",         # 非0 = 告警
        "heat": "SWITCH_ON",     # 非0 = 开启
        "charge_lid": "CHARGE_LID",  # ★ 有 -1 哨兵，需专门处理
    }

    only_vss = []
    for key in sorted(vss):
        path = vss[key]
        name = ""
        dclass = unit = sclass = icon = cat = ""
        platforms = {"sensor"}
        semantics = "RAW"
        diag = False
        kind = ""

        if key in sensors:
            s = sensors[key]
            name = s["name"]
            dclass = s["device_class"]
            unit = s["unit"]
            sclass = s["state_class"]
            icon = s["icon"]
            cat = s["category"]
            # ★ diagnostic 判定必须与 sensor.py 的 _DIAGNOSTIC_CATS + _DIAGNOSTIC_KEYS 一致
            #   （否则新表会漏标，导致诊断类实体默认启用、首屏噪音）
            DIAG_CATS = {"OTA", "保养", "信息", "设置", "电源"}
            DIAG_KEYS = {
                "config_code", "provision_auth", "hu_diag", "ota_version", "ota_short",
                "ota_state", "ota_status", "ota_progress", "maint_acfilter",
                "maint_coolfuild", "maint_engine_oil", "maint_brake_oil", "maint_sparkplug",
                "low_vol_flag", "low_vol_mode", "battery_keep_warm",
            }
            diag = (cat in DIAG_CATS) or (key in DIAG_KEYS)
        elif key in binaries:
            b = binaries[key]
            name = b["name"]
            dclass = b["device_class"]
            icon = b["icon"]
            kind = b["kind"]
            platforms = {"binary_sensor"}
            semantics = KIND_MAP.get(kind, "RAW")
        else:
            only_vss.append(key)
            name = key

        f = freq_of(key, mid, low)
        tr_note = "  # 有翻译映射" if any(
            path.endswith(k) for k in trs
        ) else ""

        parts = [
            f'    "{key}": SignalSpec(',
            f'        key="{key}",',
            f'        path="{path}",',
            f'        name="{name}",',
            f'        freq=Freq.{f},',
        ]
        if semantics != "RAW":
            parts.append(f'        semantics=Semantics.{semantics},')
        if dclass:
            parts.append(f'        device_class="{dclass}",')
        if unit:
            parts.append(f'        unit="{unit}",')
        if sclass:
            parts.append(f'        state_class="{sclass}",')
        if icon:
            parts.append(f'        icon="{icon}",')
        if cat:
            parts.append(f'        category="{cat}",')
        if platforms != {"sensor"}:
            parts.append(f'        platforms=frozenset({platforms!r}),')
        if diag:
            parts.append('        diagnostic=True,')
        parts.append(f'    ),{tr_note}')
        lines.extend(parts)

    lines.append("}")

    out = Path(args.out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"✓ 已生成 {out}（{len(vss)} 个信号）")
    if only_vss:
        print(f"⚠️  {len(only_vss)} 个 key 只有路径、无实体定义：")
        for k in only_vss[:10]:
            print(f"     {k}")
    print()
    print("下一步（人工）：")
    print("  1. 逐条校对 semantics（kind → Semantics 的映射可能不全）")
    print("  2. 校对外部 freq（前缀猜的可能不准）")
    print("  3. 校对 diagnostic（判断依据较粗）")
    print("  4. 改名 signals.py 并接入平台")
    return 0


if __name__ == "__main__":
    sys.exit(main())
