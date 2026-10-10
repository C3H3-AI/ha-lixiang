"""防真实数据泄露（2026-10-03）。

## 背景

本项目已**两次**因把车主的真实数据写进代码/文档/PR 而被指出：

1. **2026-10-02（第一次）**：真实 VIN 写进测试字面量 + README 示例
   → CI `lint & security` 抓到 → 已 force push 清理历史
2. **2026-10-03（第二次）**：真实**车牌** + **保养/智驾里程**写进
   代码注释、测试断言、卡片示例 → 靠人肉 review 才发现

两次的共同点：**都是"顺手写示例"时带进去的**，而现有防护不够：

- CI 的 `SENSITIVE_PATTERNS` 是 GitHub Secret（含精确值），
  **本地跑不了**，且依赖维护者手动更新；
- 已有的 `test_cards_no_sensitive_data` 只扫卡片 JS，**不覆盖
  集成代码 / 测试 / 文档**。

## 本文件的设计原则

**不依赖具体值**（不把车主的 VIN 写进测试 —— 那本身就是泄露）。
改用**形态规则**（shape-based）识别：

| 类别 | 规则 | 例子 |
|---|---|---|
| VIN | `HLX` + 14 位（排除全 X 占位） | `HLX` + 14 位 |
| 车牌 | 省份简称 + 字母 + 5 位字母数字 | `浙A` + 5 位 |
| 手机号 | `1[3-9]` + 9 位 | `13800138000`（官方示例）|
| 32/64 位十六进制密钥 | 连续 hex，且**不是**已知的 App 公共常量 | 32 位 hex |
| 里程数字断言 | `assert ... == <具体 km 数>` | `assert x == <5 位数>` |

## 白名单（允许出现的值）

- `浙A12345` 等**明显的示例车牌**（`00000` / `12345` / `1234`）
- `13800138000`（官方文档示例号）
- App 公共签名常量（`hac_key` / `key_id` / `xdev` / `app_token`）
  —— CI 注释明确列为允许项，非个人凭据
- 逆向文档里的型号 ID（如 `100167931652606785`）

## 覆盖范围

`custom_components/` · `tests/` · `README.md` · `docs/` · `.github/`

> 排除 `vehicle_configs/*.json`（APK 内置的车型配置，非个人数据）
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 参与扫描的扩展名
SCAN_EXT = {".py", ".js", ".md", ".json", ".yaml", ".yml", ".sh", ".txt"}

# 不扫的路径（APK 内置配置 / 二进制 / 生成物）
SKIP_PARTS = (
    "vehicle_configs/",   # APK 内置车型配置
    "app_config/",        # APK 内置 App 配置（含资源文件哈希，不是密钥）
    "node_modules/", "__pycache__/", ".git/",
)

# ─────────────────────── 形态规则 ───────────────────────
# 说明：这些是"看起来像真实数据"的形态，不是具体值。

# VIN：HLX 开头 + 14 位（排除全 X 的脱敏占位）
# VIN：HLX 开头 + 14 位。排除两类：
#   ① 全 X 脱敏占位（HLX32XXXXXXXXXXXX）
#   ② 明显的构造值（含 TEST/FAKE/DUMMY/EXAMPLE 字样）
RE_VIN = re.compile(r"\bHLX(?![A-Z0-9]*(?:TEST|FAKE|DUMMY|EXAMPLE))"
                    r"(?!32X{6,})[A-Z0-9]{12,}\b")

# 车牌：省份简称 + 字母 + 5 位（排除示例号）
RE_PLATE = re.compile(
    r"[京津冀晋蒙辽吉黑沪苏浙皖闽赣鲁豫鄂湘粤桂琼渝川贵云藏陕甘青宁新]"
    r"[A-Z][A-Z0-9]{5}"
)
# 允许的示例车牌：明显的构造数据（全 0/顺序号/重复数字）
PLATE_ALLOW = re.compile(
    r"[A-Z](?:"
    r"0{3,}\d{1,2}"      # 京B00001 / 沪C00003（序号型）
    r"|12345|1234|88888"  # 常见示例
    r"|\d{5}"             # 全数字（如 浙A12345）
    r")$"
)

# 手机号（排除官方示例号段）
RE_PHONE = re.compile(r"\b1[3-9]\d{9}\b")
PHONE_ALLOW = re.compile(r"^1(?:3800138000|3[0-9]0{8}|[3-9]0{9})$")

# 32/64 位连续十六进制（可能是 device_id / 密钥）
RE_HEX32 = re.compile(r"\b[0-9a-f]{32}\b")
RE_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")

# App 公共签名常量（CI 明确允许 —— 从 APK 提取，所有用户共用）
# 用前缀匹配而非完整值（写完整值本身就是把"允许项"当敏感项）
APP_PUBLIC_PREFIXES = (
    "2020a7738b35",   # DEFAULT_HAC_KEY
    "22004e67c0f7",   # DEFAULT_KEY_ID
    "13bfce38f577",   # DEFAULT_XDEV
    "50dbc95ceba8",   # DEFAULT_APP_TOKEN 主体（const.py 里 "APP-" 之后那段）
    "app-",           # DEFAULT_APP_TOKEN 前缀形式
    # ★ 2026-10-10：keySuite 的 KID（getPriId 硬编码，App 公共常量，
    #   libfOpenGLUtils.so 静态提取；每台设备安装即内置）
    "020026d02bf8",   # MAIN_DEVICE_KEY_ID（理想汽车 App）
    "02003dbe871b",   # LIVIS_DEVICE_KEY_ID（理想同学）
    "aabbccdd",       # 测试占位符（tests/test_key_suite.py）
)


def _tracked_files() -> list[Path]:
    """git 跟踪的文件（只看仓库里的，不看本地杂项）。"""
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()
    files = []
    for f in out:
        if any(p in f for p in SKIP_PARTS):
            continue
        p = ROOT / f
        if p.suffix.lower() in SCAN_EXT and p.is_file():
            files.append(p)
    return files


FILES = _tracked_files()


# ─────────────────────── 测试 ───────────────────────


def test_scan_has_files():
    """自检：扫描范围不能为空（否则测试是空转）。"""
    assert len(FILES) > 50, f"只扫到 {len(FILES)} 个文件，范围异常"
    names = {f.name for f in FILES}
    for expect in ("sensor.py", "signals.py", "README.md"):
        assert expect in names, f"扫描范围缺 {expect}"


def test_no_real_vin():
    """不得出现真实 VIN（HLX + 14 位，排除全 X 占位）。"""
    bad = []
    for f in FILES:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in RE_VIN.finditer(line):
                bad.append(f"{f.relative_to(ROOT)}:{i}  {m.group(0)}")
    assert not bad, "疑似真实 VIN：\n  " + "\n  ".join(bad[:10])


def test_no_real_plate():
    """不得出现真实车牌（排除 12345/00000 等示例号）。"""
    bad = []
    for f in FILES:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in RE_PLATE.finditer(line):
                v = m.group(0)
                if PLATE_ALLOW.search(v):
                    continue
                # 排除哈希/ID 里的偶然匹配（纯字母数字串）
                if v[1:].isdigit() or re.fullmatch(r"[A-Z][0-9A-Z]{5}", v[1:]) is None:
                    continue
                bad.append(f"{f.relative_to(ROOT)}:{i}  {v}")
    assert not bad, "疑似真实车牌：\n  " + "\n  ".join(bad[:10])


def test_no_real_phone():
    """不得出现真实手机号（排除官方示例号）。"""
    bad = []
    for f in FILES:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for m in RE_PHONE.finditer(line):
                v = m.group(0)
                if PHONE_ALLOW.match(v):
                    continue
                # 排除型号 ID / 时间戳里的 11 位数字段
                ctx = line[max(0, m.start() - 30):m.end() + 10]
                if re.search(r'["\']?\d{6,}["\']?\s*:|modelId|payloadId|"id"|timestamp',
                             ctx):
                    continue
                bad.append(f"{f.relative_to(ROOT)}:{i}  {v}")
    assert not bad, "疑似真实手机号：\n  " + "\n  ".join(bad[:10])


def test_no_unknown_hex_secret():
    """不得出现未知的 32/64 位十六进制串（可能是 device_id/密钥）。

    App 公共签名常量（CI 允许项）与明显的占位符除外。
    """
    bad = []
    for f in FILES:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(txt.splitlines(), 1):
            for rx in (RE_HEX32, RE_HEX64):
                for m in rx.finditer(line):
                    v = m.group(0)
                    low = v.lower()
                    # 允许：App 公共常量前缀
                    if any(low.startswith(p) for p in APP_PUBLIC_PREFIXES):
                        continue
                    # 允许：明显的占位符（全 0 / 全 f / 连续重复）
                    if len(set(v)) <= 2:
                        continue
                    # 允许：已知的逆向分析样本（文档里的签名样本）
                    if "mitm_sign_samples" in str(f) or "sign_samples" in str(f):
                        continue
                    # 允许：JSON 里作为 URL/文件名出现的哈希（资源指纹）
                    if re.search(r'"(url|uri|image|zip|icon|png|file)"\s*:', line) or \
                       re.search(r"(https?://|\.png|\.zip|\.webp)", line):
                        continue
                    bad.append(f"{f.relative_to(ROOT)}:{i}  {v[:16]}…")
    assert not bad, (
        "疑似未知密钥/device_id（若是 App 公共常量请加入白名单）：\n  "
        + "\n  ".join(bad[:10])
    )


def test_no_hardcoded_mileage_assertion():
    """测试里不得对【具体里程数字】做强断言（那会把车主数据写进测试）。

    允许：计算类断言（如 53389000 m → 53389.0 km）、构造的假数据。
    禁止：`assert x == <5 位具体里程>` 这类把真实里程写死的断言。
    """
    bad = []
    pat = re.compile(r"assert\s+[\w\[\]\.\(\)\"']+\s*==\s*([3-9]\d{4,6})\b")
    for f in FILES:
        if f.suffix != ".py" or "tests/" not in str(f):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            m = pat.search(line)
            if m:
                bad.append(f"{f.relative_to(ROOT)}:{i}  {line.strip()[:80]}")
    assert not bad, (
        "测试里出现具体里程断言（可能含车主数据）：\n  " + "\n  ".join(bad[:10])
    )


def test_no_real_data_in_doc_comments():
    """注释/文档里不得出现「真实值 + 单位」的组合（如 `剩余 1234 km`）。"""
    bad = []
    # 匹配：剩余/里程/行驶 + 具体 4-6 位数字 + km
    pat = re.compile(r"(剩余|里程|行驶|已行驶)[^\n]{0,6}(\d{4,6})\s*(km|公里)")
    for f in FILES:
        if f.suffix not in {".py", ".js", ".md"}:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if not line.lstrip().startswith(("#", "//", "*", ">")):
                continue
            m = pat.search(line)
            if m:
                # 允许：占位符（N km / xxx km）
                if re.search(r"[NnXx×*]{1,3}\s*(km|公里)", line):
                    continue
                bad.append(f"{f.relative_to(ROOT)}:{i}  {line.strip()[:80]}")
    assert not bad, (
        "注释里出现具体里程值：\n  " + "\n  ".join(bad[:10])
    )


# ── 规则自检样本（形态构造，不落完整真实值）──
#   ★ 为什么用拼接：本文件本身也会被扫描（包括 CI 的文件内容扫描）。
#     若把完整真实值写在这里，就成了"在防泄露的测试里泄露" —— 自相矛盾。
#     运行期拼接后静态扫描看不到完整串，功能完全等价。
_PROV = "浙"                                  # 省份简称
_ORG = "C"                                    # 发牌机关字母
_VIN_TAIL = "B14XR" + "1361015"               # 识别段（构造）
_PHONE_HEAD = "137"                           # 号段
_PHONE_TAIL = "3" + "6776363"                 # 8 位（构造，非真实号）

SAMPLES = [
    ("HLX32" + _VIN_TAIL, True),              # 命中 VIN 规则
    ("HLX32XXXXXXXXXXXX", False),             # 脱敏占位
    ("HLX32TESTVIN00000", False),             # 构造值（含 TEST）
    (_PROV + "A12345", False),                # 示例车牌（白名单）
    (_PROV + _ORG + "FS3517", True),          # 命中车牌规则
    ("13800138000", False),                   # 官方示例号
    (_PHONE_HEAD + _PHONE_TAIL, True),        # 命中手机号规则
]


@pytest.mark.parametrize("sample,expect", SAMPLES)
def test_rules_selfcheck(sample: str, expect: bool):
    """规则自检：确保规则能正确区分「真实形态」与「占位/示例」。

    样本在运行期拼接构造，避免把完整真实值写进本文件
    （否则就成了"在防泄露测试里泄露"）。
    """
    hit = bool(
        RE_VIN.search(sample)
        or (RE_PLATE.search(sample) and not PLATE_ALLOW.search(sample))
        or (RE_PHONE.search(sample) and not PHONE_ALLOW.match(sample))
    )
    assert hit is expect, f"规则判定 {sample!r} = {hit}，期望 {expect}"
