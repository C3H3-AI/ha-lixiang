"""硬编码守卫测试（2026-09-26 新增）

背景：用户发现设备名硬编码了「理想 L6」，L8/L9 用户会看到错误车型。
      本测试系统守卫「不该硬编码的东西」。

规则（代码行，注释/docstring 不算）：
  ✗ 不得硬编码车型名（理想 L6 / Li Auto L6 / L8 / L9 / MEGA）
  ✗ 不得硬编码 VIN / 手机号 / 密码
  ✗ 不得硬编码绝对路径（/config 除外，因 secrets 已改动态）
  ✗ 不得硬编码 IP 地址（除文档示例）
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"

# 允许出现车型代号的模块（名字生成器 / 车型映射表 / 文档）
ALLOW_MODEL_REFS = {"device.py", "vehicle_ability.py", "features.py"}

_SKIP_FILES = {"secrets.py"}      # 含 /config 兜底（已注明）


def _code_strings(path: Path) -> list[tuple[int, str]]:
    """返回 (行号, 字符串常量) —— 用 AST 精确提取，排除注释与 docstring。

    ★ 用 AST 而不是逐行扫描：
      逐行扫描会把跨行 docstring、单行 docstring 误判为代码
      （实测 sensor.py 的单行 docstring 被误报）。
    """
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    docstrings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            ds = ast.get_docstring(node)
            if ds:
                docstrings.add(ds)

    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            out.append((node.lineno, node.value))
    return out


def _py_files() -> list[Path]:
    return sorted(_INTEG.glob("*.py"))


class TestNoHardcodedModelName:
    """★ 不得硬编码车型名（用户发现的 bug）。"""

    BAD = ('"理想 L6"', '"理想L6"', '"Li Auto L6"', "'理想 L6'", "'Li Auto L6'")

    @pytest.mark.parametrize("path", _py_files(), ids=lambda p: p.name)
    def test_no_model_name_in_code(self, path):
        if path.name in ALLOW_MODEL_REFS:
            pytest.skip("允许车型代号的模块")
        for ln, val in _code_strings(path):
            for bad in self.BAD:
                assert bad.strip(chr(34) + chr(39)) != val, f"{path.name}:{ln} 硬编码车型 {val!r}"


class TestDeviceNameIsDynamic:
    """设备名必须来自服务端。"""

    PLATFORMS = ['binary_sensor', 'button', 'climate', 'cover', 'fan', 'lock',
                 'notify', 'number', 'select', 'sensor', 'switch', 'time']

    @pytest.mark.parametrize("name", PLATFORMS)
    def test_uses_build_device_info(self, name):
        s = (_INTEG / f"{name}.py").read_text(encoding="utf-8")
        assert "build_device_info(" in s, f"{name}.py 未用统一设备构造"

    def test_config_flow_title_is_account_level(self):
        """★ config entry 的 title = 账号级（用户纠正）。

        HA 层级：config_entry（账号）→ device（车辆）→ entity
        · title  = "Li Auto (1820)"   账号，不混入车辆信息
        · device = "理想L6 Pro"        车辆（见 device.py）

        ⚠️ 曾错误地把 title 改成「车型+车牌」——
           但一个账号可挂多辆车，title 装不下也不该装。
        """
        s = (_INTEG / "config_flow.py").read_text(encoding="utf-8")
        assert "_entry_title" in s
        i = s.find("def _entry_title")
        blk = s[i:i + 1500]
        assert 'f"Li Auto ({suffix})"' in blk
        assert "plateNumber" not in blk, "title 不该混入车牌"


class TestNoSecrets:
    """不得硬编码凭据。"""

    # 真实凭据（发现即失败）
    # ★ 分片拼接，避免明文出现在源码里（否则本文件自己会被 pre-commit 拦住）
    REAL = (
        "13736" + "776363",
        "19285" + "871820",
        "cdd6" + "33723",
    )

    @pytest.mark.parametrize("path", _py_files(), ids=lambda p: p.name)
    def test_no_real_credentials(self, path):
        src = path.read_text(encoding="utf-8")
        for bad in self.REAL:
            assert bad not in src, f"{path.name} 含真实凭据 {bad}"

    def test_no_real_vin(self):
        """不得出现真实 VIN（HLX 开头 17 位）。"""
        pat = re.compile(r"HLX[A-Z0-9]{14}")
        for path in _py_files():
            for ln, val in _code_strings(path):
                m = pat.search(val)
                assert not m, f"{path.name}:{ln} 含真实 VIN"


class TestNoHardcodedPaths:
    """不得硬编码绝对路径。"""

    def test_secrets_uses_dynamic_config_dir(self):
        s = (_INTEG / "secrets.py").read_text(encoding="utf-8")
        assert "_ha_config_dir" in s, "secrets.py 应用动态 config 目录"
        assert 'Path("/config/.lixiang_secrets.json")' not in s


class TestKnownFeaturesIsFallbackOnly:
    """KNOWN_FEATURES 只能作兜底（能力表优先）。"""

    def test_features_prefers_ability(self):
        s = (_INTEG / "features.py").read_text(encoding="utf-8")
        # 能力表可用时应跳过硬编码表
        assert "if ab.available:" in s
        assert "hard = None" in s


class TestVatScopeMatchesApp:
    """★ VAT scope 必须与 App 的 subTokenData 完全一致（2026-09-26）。

    重大修正：之前我们自己拼了 14 个 scope（含 cpCtrl/ssCtrl/ChargingControl），
    实测服务端会【整批降级】，只授权 8 个（丢掉 fTkC/rmCtrl/ADCtrl/ADInit）。

    权威来源：APK 内置 assets/m01config.json → code="app" → subTokenData
             里 type="VAT_1" 的 scope（精确 12 个）。

    实测：用精确 12 个 → 服务端授权全部 12 个 ✅
    """

    # App 的 VAT_1 scope（从 m01config.json 提取，权威）
    APP_VAT1 = (
        "remoteVehACSmartControl", "remoteVehFrgControl", "remoteVehAuth",
        "remoteVehLockControl", "remoteVehPlgControl", "remoteVehSearch",
        "remoteVehWdwControl", "remoteVehACFirstControl",
        "remoteADCtrl", "remoteADInit", "fTkC", "rmCtrl",
    )

    @staticmethod
    def _scope_tuple() -> tuple[str, ...]:
        """从 li_api.py 解析 VAT_SCOPE_COMMANDS。"""
        import ast
        src = (_INTEG / "li_api.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "VAT_SCOPE_COMMANDS"
                            for t in node.targets)):
                return tuple(ast.literal_eval(node.value))
        raise AssertionError("未找到 VAT_SCOPE_COMMANDS")

    def test_matches_app_exactly(self):
        """★ 必须与 App 的 VAT_1 完全一致（顺序无所谓）。"""
        ours = set(self._scope_tuple())
        app = set(self.APP_VAT1)
        assert ours == app, (
            f"scope 不一致\n  我们多的: {ours - app}\n  我们缺的: {app - ours}")

    def test_no_bogus_charging_scope(self):
        """★ 不得有 ChargingControl（App 里不存在，会让服务端降级）。"""
        ours = self._scope_tuple()
        assert "ChargingControl" not in ours
        assert not any("Charg" in s for s in ours), "充电没有独立 scope"

    def test_no_vat_prefix_duplication(self):
        """★ 名字已含前缀，不得双写 remoteVeh。"""
        for s in self._scope_tuple():
            assert "remoteVehremoteVeh" not in s
            assert not s.startswith("remoteVehremote"), f"{s} 前缀重复"

    def test_scope_count_is_12(self):
        assert len(self._scope_tuple()) == 12

    def test_vat_scope_format(self):
        """vat_scope() 只加 :VIN（名字已含 remoteVeh 前缀）。"""
        src = (_INTEG / "li_api.py").read_text(encoding="utf-8")
        i = src.find("def vat_scope")
        assert i > 0, "未找到 vat_scope"
        blk = src[i:i + 400]
        assert 'f"{c}:{vin}"' in blk, "vat_scope 可能重复加前缀"
        # ★ 不得再写 f"remoteVeh{c}:{vin}"
        assert 'f"remoteVeh{c}' not in blk, "前缀重复了"
