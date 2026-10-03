"""features.py 测试：车型功能探测

★ 背景（2026-09-24）：
  用户发现 L6（五座）竟然有三排座椅传感器。
  排查出 3 个叠加的 bug：
    ① _hardcoded_features() 返回 None（硬编码表被禁用）
    ② seat_tl/tr/tm/sm 缺 FEATURE_BY_KEY_PREFIX 映射
    ③ 服务端对不存在的三排硬件也返回 value=0 + 有效 ts

  本测试用【文本解析】读取 features.py / sensor.py 的常量
  （这两个模块依赖 homeassistant，无法在纯 pytest 环境导入）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _extract_dict(filename: str, var: str) -> dict:
    """从源码中提取一个模块级 dict 字面量（支持嵌套）。

    用括号配平找范围，再 ast.literal_eval。
    """
    src = (INTEG / filename).read_text(encoding="utf-8")
    m = re.search(rf"^{var}\s*(?::[^=]+)?=\s*\{{", src, re.M)
    if not m:
        pytest.fail(f"未找到 {var} in {filename}")
    start = m.end() - 1
    depth = 0
    end = start
    for i in range(start, len(src)):
        c = src[i]
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                end = i
                break
    return ast.literal_eval(src[start:end + 1])


class TestSeatMapping:
    """★ 座椅 key → 功能的映射必须完整（否则信号不受功能过滤）"""

    @staticmethod
    def _mapping() -> dict:
        # ★ 2026-09-28：映射表已从 sensor.py 提升到 features.py，
        #   供 sensor / binary_sensor 两个平台共用
        #   （此前只在 sensor 生效 → binary_sensor 完全没有功能门控）。
        return _extract_dict("features.py", "FEATURE_BY_KEY_PREFIX")

    @staticmethod
    def _feature_of(key: str, mapping: dict) -> str | None:
        for prefix, feat in mapping.items():
            if key == prefix or key.startswith(prefix + "_"):
                return feat
        return None

    def test_third_row_seats_mapped(self):
        """★ 三排座椅必须有映射（否则 L6 会出现三排实体）"""
        m = self._mapping()
        for key in ("seat_tl_heat", "seat_tr_heat", "seat_tm_heat",
                    "seat_tl_vent", "seat_tr_vent"):
            feat = self._feature_of(key, m)
            assert feat == "三排座椅", f"{key} 应映射到「三排座椅」，实际 {feat}"

    def test_second_row_seats_mapped(self):
        """二排座椅（含中座）必须有映射"""
        m = self._mapping()
        for key in ("seat_sl_heat", "seat_sr_heat", "seat_sm_heat"):
            feat = self._feature_of(key, m)
            assert feat == "二排座椅", f"{key} 应映射到「二排座椅」，实际 {feat}"

    def test_front_seats_unfiltered(self):
        """前排座椅是通用功能 → 不映射是正确行为"""
        m = self._mapping()
        for key in ("seat_fl_heat", "seat_fr_heat"):
            assert self._feature_of(key, m) is None, f"{key} 不该有映射"


class TestKnownFeatures:
    """L6 的硬编码功能表"""

    def test_l6_is_five_seater(self):
        """★ L6 是五座 → 三排座椅必须为 False"""
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert "X04" in k, "KNOWN_FEATURES 缺少 X04（L6 的平台号）"
        assert k["X04"].get("三排座椅") is False, \
            f"L6 无三排座椅，实际 {k['X04'].get('三排座椅')}"

    def test_l6_has_no_fridge(self):
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert k["X04"].get("冰箱") is False

    def test_l6_has_no_front_trunk(self):
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert k["X04"].get("前备箱") is False

    def test_l6_has_sunshade(self):
        """★ L6 确实【有】遮阳帘（用户实车确认）

        ⚠️ 曾经的误判：
          依据"App 代码引用数 0"判为不存在 —— 这是错的。
          App 界面不显示该状态，只说明【产品设计没做入口】，
          不代表硬件不存在。

        教训：硬件存在性要靠【实车信号 + 用户确认】，不能靠 App 代码。
        """
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert k["X04"].get("遮阳帘") is True, "L6 有遮阳帘"

    def test_l6_plate_display_unsupported(self):
        """★ L6 不支持牌显

        依据：App 侧实现 getSupportPlateDisplay() → getUN_SUPPORT（不支持）
        """
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert k["X04"].get("牌显") is False

    def test_l6_has_steering_wheel_heat(self):
        """★ L6 有方向盘加热（曾因 VSS 探测 7 天新鲜度判据被误判为不支持）"""
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert k["X04"].get("方向盘加热") is True


class TestKnownFeaturesCoversProbes:
    """★ KNOWN_FEATURES 必须覆盖所有 FEATURE_PROBES 项

    否则未覆盖项会继续走 VSS 探测，而 VSS 探测有 7 天新鲜度判据，
    会把"存在但久未使用"的功能误判为不支持（实测：方向盘加热）。
    """

    def test_full_coverage(self):
        known = _extract_dict("features.py", "KNOWN_FEATURES")
        probes = _extract_dict("features.py", "FEATURE_PROBES")
        k = set(known["X04"].keys())
        p = set(probes.keys())
        missing = p - k
        assert not missing, (
            f"KNOWN_FEATURES[X04] 未覆盖: {sorted(missing)}\n"
            f"这些项会走不可靠的 VSS 探测，可能误判。"
        )


class TestHardcodedEnabled:
    """★ 硬编码表必须【被使用】（曾因 return None 而完全失效）"""

    def test_hardcoded_not_disabled(self):
        src = (INTEG / "features.py").read_text(encoding="utf-8")
        m = re.search(r"def _hardcoded_features.*?(?=\ndef )", src, re.S)
        assert m, "未找到 _hardcoded_features"
        body = m.group(0)
        assert "KNOWN_CODES" in body, \
            "_hardcoded_features 没有车型判定逻辑 —— 硬编码表会失效"
        assert "KNOWN_FEATURES.get" in body, \
            "_hardcoded_features 没有读取 KNOWN_FEATURES"


class TestProbePaths:
    """探测路径必须是实测有效的"""

    def test_remote_photo_uses_real_paths(self):
        """★ 远程拍照的探测路径（曾用错 → 误判为不支持）

        L6 实测：
          ✅ Vehicle.360Svm.ParkPhoto.State
          ✅ Vehicle.360Svm.Park.Filekey
          ❌ Vehicle.Camera.Photo.Status（无数据）
        """
        p = _extract_dict("features.py", "FEATURE_PROBES")
        paths = p["远程拍照"]
        assert any("360Svm" in x for x in paths), \
            "远程拍照应探测 360Svm 路径（L6 实际信号）"
        assert not any(x == "Vehicle.Camera.Photo.Status" for x in paths), \
            "Vehicle.Camera.Photo.Status 在 L6 上无数据，不该用于探测"

    def test_all_features_have_paths(self):
        p = _extract_dict("features.py", "FEATURE_PROBES")
        assert p, "FEATURE_PROBES 为空"
        for feat, paths in p.items():
            assert paths, f"{feat} 没有探测路径"
            assert all(x.startswith("Vehicle.") for x in paths), \
                f"{feat} 的路径格式错误"

    def test_third_row_probe_exists(self):
        """三排座椅应有探测路径（给未知车型用）"""
        p = _extract_dict("features.py", "FEATURE_PROBES")
        assert "三排座椅" in p, "FEATURE_PROBES 缺少「三排座椅」"
        assert any("TLSeat" in x for x in p["三排座椅"]), \
            "三排座椅应探测 TLSeat* 路径"


# ══════════════════════════════════════════════════════════════════════════
#  ★★ KNOWN_FEATURES 的键必须是【服务端确认的平台号】，不是 App 类名
# ══════════════════════════════════════════════════════════════════════════
class TestKnownFeaturesKeyIsServerPlatform:
    """2026-09-29 更正的错误（`M01` → `X04`）。

    原来的推理链是：

        我们车在 App 里的委托类叫 LXM01StateDelegate
          → 所以我们的车属于 M01 平台
          → 所以 KNOWN_FEATURES 用 "M01" 当键

    **三段都不成立**：

    · 服务端实测我们车 `vehicleInfo.seriesNo = 'X04'`、
      `bleModuleCode = 'XTA2B6'`、`modelName = '理想L6'`
    · App 自己把 M 与 X 当【不同车系】：
        `isM()`            = `platform === '1'`      （M01B 是唯一 platform='1'）
        `isM01AVehicle(t)` = `t === 'MTA0B0'`
        `isM01BVehicle(t)` = `t === 'MTA1B1'` / `'MNA1B1'`
        `isXVehicle(t)`    = `t.startsWith('X')`     ← 我们车 XTA2B6 属此
      且 UI 分派也是分开的（M01A/M01B 用 M01A*/M01B*Helper，
      X 系与 W 系用 X01A*Helper）。
    · `LXM01StateDelegate` 是 App 里【唯一】以车型命名的 StateDelegate
      （其余按通道分：BLE / LiMesh / Http）—— 这只说明它是个具名实现，
      **推不出我们车就是 M01**。

    ⚠️ 错的只是**键名**：下表内容一直是实车验证过的（L6 五座、方向盘加热、
       遮阳帘…），所以行为没有变化（本表也只在拿不到能力表时才用）。
       但这个误标会误导人 —— 它一度让人以为 M01B 就是 MEGA。
    """

    def test_key_is_x04(self):
        k = _extract_dict("features.py", "KNOWN_FEATURES")
        assert "X04" in k, "KNOWN_FEATURES 的键应为服务端平台号 X04（= L6）"
        assert "M01" not in k, (
            "不应再用 'M01' 当键 —— M01 是【另一个车系】（platform='1'），"
            "不是我们的车（X04 / XTA2B6）"
        )

    def test_known_codes_maps_jr7_to_x04(self):
        """ConfigCode.vehModel='JR7' 应对应平台号 X04。"""
        src = (INTEG / "features.py").read_text(encoding="utf-8")
        i = src.find("KNOWN_CODES = {")
        assert i > 0, "找不到 KNOWN_CODES"
        blk = src[i:i + 400]
        assert '"JR7": "X04"' in blk, (
            "KNOWN_CODES 应把 vehModel='JR7' 映射到 'X04'\n"
            f"实际片段：{blk[:200]}"
        )

    def test_no_comment_claims_our_car_is_m01(self):
        """源码里不得再出现「我们车属于 M01 平台」这类已被证伪的说法。"""
        src = (INTEG / "features.py").read_text(encoding="utf-8")
        for bad in ("该类的存在说明车型属于 M01 平台",
                    "JR7 = L6 / M01 平台",
                    "LXM01StateDelegate (L6 / M01)"):
            assert bad not in src, f"仍留有已被证伪的说法：{bad!r}"

    def test_content_unchanged_and_l6_verified(self):
        """键名变了，但 L6 的判定内容必须原样保留。"""
        k = _extract_dict("features.py", "KNOWN_FEATURES")["X04"]
        assert k.get("三排座椅") is False      # L6 五座，无三排
        assert k.get("二排座椅") is True
        assert k.get("方向盘加热") is True     # 实车确认
        assert k.get("遮阳帘") is True         # 用户确认
        assert k.get("冰箱") is False
        assert k.get("前备箱") is False
