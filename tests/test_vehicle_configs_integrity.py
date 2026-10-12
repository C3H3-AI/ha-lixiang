"""车型配置完整性守卫（2026-10-12）。

## 为什么要有这个文件

集成用 `assets/{modelId}.json`（从 APK 提取到 `vehicle_configs/`）判断
**某车型支持什么功能** —— `features.resolve_requirement()` 的
`version:` / `ability:` 两条 DSL 全靠它。

**配置缺失的后果不是"少个实体"，而是门控整体失效**：

```
load_vehicle_config(modelId) → None
  → VehicleAbility.available = False
  → resolve_requirement 全部落到「保守保留」分支
  → 该车型被建出【所有】实体，包括它硬件上根本没有的
```

真机实例：M 系没有 VSS 服务，L 系没有 `seat_heat_vent_*` 路径 ——
配置一缺，两边都会长出恒为 `unknown` 的死实体。

## 这次的真实缺陷

2026-10-12 用 REA 对比 APK 与集成目录，发现：

```
APK 车型 JSON : 69 个
集成 vehicle_configs : 68 个
缺失: 952447875932008064 = M01A车型（初代理想 ONE）
```

即 `platform=1`（M 系）三个车型里少了一个 —— 初代理想 ONE 车主
会命中上面那条「门控整体失效」的路径。

## 守卫策略

不断言"必须等于 69"（APK 会升级），而是断言**内部自洽** + **已知车型必须在**：

- `_index.json` 与目录里的文件**双向一致**（不多不少）
- 每个配置与索引都有关键字段
- 索引里的 `desc`/`platform` 与配置文件**实际内容一致**
- **M 系三个车型必须在**（今天的回归守卫）
- `VehicleAbility` 对缺失 modelId 的行为**保持保守可用**
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CONF = CC / "vehicle_configs"

#: 每条配置与索引都必须有的键
CONFIG_KEYS = ("desc", "unityModel", "platform", "config", "version")
INDEX_KEYS = ("desc", "unityModel", "platform", "seats")

#: M 系（platform=1，理想 ONE 系列）—— 必须在，且必须能被门控使用
#: ★ 2026-10-12：M01A 曾缺失（APK 有 69 个、集成只有 68 个）
M_SERIES = {
    "952447875932008064": "M01A车型",   # 初代理想 ONE ← 本次补回
    "100204301435085761": "M01B车型",
    "100618542440964164": "M01Ring车型",
}


def _files() -> dict[str, pathlib.Path]:
    return {f.stem: f for f in CONF.glob("[0-9]*.json")}


def _index() -> dict:
    return json.loads((CONF / "_index.json").read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════
#  ① 索引 ↔ 文件 双向一致
# ══════════════════════════════════════════════════════════════════


class TestIndexMatchesFiles:
    def test_index_not_empty(self):
        assert len(_index()) > 50, "车型索引异常（应覆盖几十个车型）"

    def test_every_index_entry_has_a_file(self):
        """索引里列了、目录里没有 → 该车型门控失效。"""
        miss = sorted(set(_index()) - set(_files()))
        assert not miss, f"_index.json 列出但缺少配置文件: {miss}"

    def test_every_file_is_in_index(self):
        """目录里有、索引里没有 → `load_model_index()` 看不到它。"""
        extra = sorted(set(_files()) - set(_index()))
        assert not extra, f"有配置文件但 _index.json 未登记: {extra}"


# ══════════════════════════════════════════════════════════════════
#  ② 字段完整性
# ══════════════════════════════════════════════════════════════════


class TestFields:
    def test_index_entries_complete(self):
        bad = [(m, k) for m, d in _index().items() for k in INDEX_KEYS if k not in d]
        assert not bad, f"索引条目缺字段: {bad[:5]}"

    def test_configs_have_required_keys(self):
        bad = []
        for mid, f in _files().items():
            d = json.loads(f.read_text(encoding="utf-8"))
            bad += [(mid, k) for k in CONFIG_KEYS if k not in d]
        assert not bad, f"配置文件缺关键键: {bad[:5]}"

    def test_configs_have_version_table(self):
        """`version` 是门控的数据源，空表等于门控失效。"""
        empty = [mid for mid, f in _files().items()
                 if not (json.loads(f.read_text(encoding="utf-8")).get("version") or {})]
        assert not empty, f"这些车型的 version 能力表为空: {empty}"

    def test_platform_values_are_known(self):
        odd = {mid: d.get("platform") for mid, d in _index().items()
               if str(d.get("platform")) not in ("1", "2")}
        assert not odd, f"未知平台代号: {odd}"


# ══════════════════════════════════════════════════════════════════
#  ③ 索引与文件内容一致
# ══════════════════════════════════════════════════════════════════


class TestIndexContentMatches:
    def test_desc_and_platform_agree(self):
        bad = []
        for mid, d in _index().items():
            f = CONF / f"{mid}.json"
            if not f.exists():
                continue
            j = json.loads(f.read_text(encoding="utf-8"))
            if d.get("desc") != j.get("desc") or str(d.get("platform")) != str(j.get("platform")):
                bad.append((mid, d.get("desc"), j.get("desc"), d.get("platform"), j.get("platform")))
        assert not bad, f"索引与配置文件不一致 (id, idx_desc, file_desc, idx_pf, file_pf): {bad[:3]}"


# ══════════════════════════════════════════════════════════════════
#  ④ ★ M 系回归守卫（本次缺陷）
# ══════════════════════════════════════════════════════════════════


class TestMSeriesPresent:
    """M 系（理想 ONE）三个车型必须齐全。

    2026-10-12：M01A 缺失导致初代理想 ONE 门控整体失效。
    本类是这个缺陷的回归守卫 —— 删掉会失败。
    """

    @pytest.mark.parametrize("mid,desc", sorted(M_SERIES.items()))
    def test_m_series_config_exists(self, mid, desc):
        f = CONF / f"{mid}.json"
        assert f.exists(), (
            f"M 系车型 {desc}({mid}) 的配置缺失 —— "
            f"该车型门控会整体失效（所有实体都被保守保留）"
        )

    @pytest.mark.parametrize("mid,desc", sorted(M_SERIES.items()))
    def test_m_series_indexed(self, mid, desc):
        assert mid in _index(), f"{desc}({mid}) 未登记进 _index.json"

    @pytest.mark.parametrize("mid,desc", sorted(M_SERIES.items()))
    def test_m_series_platform_is_1(self, mid, desc):
        d = json.loads((CONF / f"{mid}.json").read_text(encoding="utf-8"))
        assert str(d.get("platform")) == "1", f"{desc} 平台代号不是 1（M 系）"

    def test_all_platform_1_vehicles_in_index(self):
        """所有 platform=1 的配置文件都必须进索引（不能只保证那 3 个）。"""
        on_disk = {mid for mid, f in _files().items()
                   if str(json.loads(f.read_text(encoding="utf-8")).get("platform")) == "1"}
        assert on_disk <= set(_index()), f"platform=1 但未进索引: {sorted(on_disk - set(_index()))}"


# ══════════════════════════════════════════════════════════════════
#  ⑤ 能力查询语义（门控依赖它）
# ══════════════════════════════════════════════════════════════════


def _load_vehicle_ability():
    """加载 vehicle_ability.py（照搬 tests/test_vehicle_ability.py 的做法）。

    `vehicle_ability.py` 刻意不依赖 homeassistant，所以这里用 exec 直接
    执行源码 —— 直接 import 会经 `__init__.py`，那需要 HA 环境。
    """
    import types

    src = (CC / "vehicle_ability.py").read_text(encoding="utf-8")
    src = src.replace("from .const import LOGGER_NAME", "LOGGER_NAME = 'test'")
    src = src.replace(
        '_CONFIG_DIR = Path(__file__).parent / "vehicle_configs"',
        f'_CONFIG_DIR = Path({str(CONF)!r})')
    mod = types.ModuleType("va_under_test")
    exec(compile(src, "vehicle_ability.py", "exec"), mod.__dict__)
    return mod


_VA = _load_vehicle_ability()


class TestAbilitySemantics:
    """`is_supported` / `has` 的语义必须稳定 —— 门控正确性依赖它们。"""

    def _ability(self, mid: str):
        return _VA.VehicleAbility(mid)

    def test_unknown_model_is_unavailable(self):
        """未知 modelId → available=False（上层据此走保守分支）。"""
        a = self._ability("999999999999999999")
        assert a.available is False

    def test_unknown_tag_is_not_supported(self):
        """★ 标签不存在 → 不支持。

        这就是「L 系没有 upperLimitCharging 标签」被判为不支持的原因；
        若哪天改成 True，所有 `version:` 门控都会失效。
        """
        a = self._ability("100167931652606785")   # L6Pro
        assert a.is_supported("____不存在的标签____") is False

    def test_m01a_ability_available_after_fix(self):
        """★ M01A 现在必须能读到能力表（补配置的直接目的）。"""
        a = self._ability("952447875932008064")
        assert a.available is True, "M01A 能力表读不到 —— 门控会整体失效"
        assert str(a.platform) == "1"

    def test_m01a_has_version_table(self):
        a = self._ability("952447875932008064")
        tags = a.supported_features()
        assert len(tags) > 0, "M01A 的 version 表读出来是空的"

    def test_m_series_differs_from_l_series(self):
        """M 系与 L 系的能力表必须不同 —— 否则 platform 门控无从判断。"""
        m = self._ability("952447875932008064").supported_features()
        x = self._ability("100167931652606785").supported_features()
        assert set(m) != set(x), "M 系与 L 系能力表相同，platform 门控会失去区分度"
