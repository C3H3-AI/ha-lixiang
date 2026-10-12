"""官方静态车模图（car_image.py）与座椅死实体门控（2026-10-12）。

两件事的来龙去脉
================

## 一、车模：为什么放弃自建 3D

车主连续追问：「车模有，但是不成形」→「很多空的地方」→「缺少前保险杠、
后保险杠、车门」。逐层查下来：

1. **官方包的网格就是不全** —— 92 个网格逐一核对，只有 ``Door_*``
   （材质是"车门内_金属""内饰底绒_侧面"= 内衬），**没有前/后保险杠、车门外壳**。
   下载官方包与本地 ``carmodel.bundle`` md5 完全一致
   （``35d03160af465b563bc5dae0d68e954c``）→ 不是导出错误，是素材如此。
2. **成本高** —— 转出的 GLB 61 MB（手机每次清缓存都重下），
   而官方静态图仅 ~230 KB/张。
3. **颜色拿不到** —— 7 个 ``CarPaint_*`` 材质共用同一张贴图、``_BaseColor``
   全 ``[1,1,1]``，车漆色不在模型里。

改用官方渲染好的竖版整车图后，颜色/车型全自动对上。

## 二、数据链路（实测打通）

```
GET /saos-vehicle-api/v2-0/vehicles/basics?vehicleInfo=true
   → modelId=100167931652606785  colorCode=FA9
本地 vehicle_configs/{modelId}.json
   → config.vertical[] = [{"key":"FA9","value":"https://…png"}, …]
p.ampmake.com 明文直链（无鉴权）→ 下载 → config/lixiang-car/{modelId}/
```

★ ``colorCode`` 与 ``vertical[].key`` **是同一套 key** → 精确匹配，零人工配置。

## 三、座椅"死实体"

车主问：「座椅加热，通风这些传感器有没有必要存在？开关里面不是显示状态了吗？」

实测结果是**一半对**：

- ``seat_fl_heat`` / ``seat_fl_vent`` 等**独立**传感器：状态有值（"关"），
  且 ``switch.py`` 里**没有**座椅加热开关 → **保留**（自动化要用）。
- ``seat_heat_vent_fl/fr/rl/rr``（"XX座椅加热通风"）：``path=""``（无数据源），
  真机状态恒为 ``unknown`` → **死实体**。但它们在 **M 系**（理想ONE）有真实来源
  （``seatStatus.<座>SeatHeatVentState``）→ 所以是**按平台门控**，不是删除。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import car_image as ci

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "lixiang_auto"
CAR_IMAGE = PKG / "car_image.py"
SIGNALS = PKG / "signals.py"
FEATURES = PKG / "features.py"
CARD = PKG / "www" / "lixiang-cards" / "lixiang-app-home.js"
INIT = PKG / "__init__.py"
CONFIGS = PKG / "vehicle_configs"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ───────────────────────── 纯函数：图片清单与选色 ─────────────────────────

class TestListImages:
    def _cfg(self) -> dict:
        return {
            "config": {
                "vertical": [
                    {"key": "FAH", "value": "https://p.ampmake.com/a.png"},
                    {"key": "FA9", "value": "https://p.ampmake.com/b.png"},
                ],
                "minIcon": [{"key": "FA9", "value": "https://p.ampmake.com/c.png"}],
                "color": [{"key": "FA9", "value": "ex_color_4_LXVR_L7"}],
            }
        }

    def test_vertical(self):
        got = ci.list_images(self._cfg(), ci.KIND_VERTICAL)
        assert got == {"FAH": "https://p.ampmake.com/a.png",
                       "FA9": "https://p.ampmake.com/b.png"}

    def test_minicon(self):
        assert list(ci.list_images(self._cfg(), ci.KIND_MINICON)) == ["FA9"]

    def test_skips_non_url_values(self):
        """`color` 字段的 value 是资源名（ex_color_…）不是 URL —— 必须跳过。"""
        cfg = {"config": {"vertical": [{"key": "FA9", "value": "ex_color_4_LXVR_L7"}]}}
        assert ci.list_images(cfg, ci.KIND_VERTICAL) == {}

    def test_empty_inputs(self):
        assert ci.list_images(None) == {}
        assert ci.list_images({}) == {}
        assert ci.list_images({"config": {}}, ci.KIND_VERTICAL) == {}

    def test_unknown_kind(self):
        assert ci.list_images(self._cfg(), "nonexistent") == {}


class TestPickKey:
    """★ 核心：服务器给的 colorCode 必须精确命中同名的图。"""

    IMGS = {"FAH": "u1", "FA2": "u2", "FA9": "u9"}

    def test_exact_match(self):
        assert ci.pick_key(self.IMGS, "FA9") == "FA9"

    def test_unknown_falls_back_to_first(self):
        """服务器给了没见过的色码 → 用第一张（保证有图，不显示空）。"""
        assert ci.pick_key(self.IMGS, "ZZZ") == "FAH"

    def test_none_falls_back_to_first(self):
        assert ci.pick_key(self.IMGS, None) == "FAH"

    def test_explicit_fallback_wins_over_first(self):
        assert ci.pick_key(self.IMGS, "ZZZ", "FA2") == "FA2"

    def test_empty(self):
        assert ci.pick_key({}, "FA9") is None


# ───────────────────────── 真实车型配置（离线断言）─────────────────────────

class TestRealL6Config:
    """用**真实的** L6Pro 配置验证（车主这台车 modelId=100167931652606785）。"""

    MODEL_ID = "100167931652606785"
    COLOR_CODE = "FA9"          # ★ 服务器实测返回：珠光漆 - 新白色-EA05 → FA9

    def _cfg(self) -> dict:
        f = CONFIGS / f"{self.MODEL_ID}.json"
        if not f.is_file():
            pytest.skip("车型配置不在本机")
        return json.loads(_read(f))

    def test_config_exists(self):
        assert (CONFIGS / f"{self.MODEL_ID}.json").is_file()

    def test_has_vertical_images(self):
        imgs = ci.list_images(self._cfg(), ci.KIND_VERTICAL)
        assert len(imgs) >= 5, f"竖版图太少: {len(imgs)}"
        assert all(u.startswith("https://p.ampmake.com/") for u in imgs.values())

    def test_color_code_hits(self):
        """★ 端到端：实测的 colorCode 必须能在配置里命中。"""
        imgs = ci.list_images(self._cfg(), ci.KIND_VERTICAL)
        assert ci.pick_key(imgs, self.COLOR_CODE) == self.COLOR_CODE, \
            "colorCode 与 vertical key 不是同一套 —— 自动匹配会失效"

    def test_color_and_vertical_share_keys(self):
        """config.color 与 config.vertical 用同一套 key（自动匹配的前提）。"""
        cfg = self._cfg()
        cols = {i["key"] for i in (cfg["config"].get("color") or [])}
        vert = {i["key"] for i in (cfg["config"].get("vertical") or [])}
        assert cols and vert
        assert cols & vert, "两套 key 没有交集 → 无法按车漆自动选图"


class TestAllConfigs:
    """全部车型都应可自动匹配（不只是 L6）。"""

    def test_every_config_has_vertical(self):
        # 只取车型配置（数字命名）；_index.json / _names_*.json 是辅助文件
        files = sorted(f for f in CONFIGS.glob("*.json") if f.stem.isdigit())
        if not files:
            pytest.skip("无车型配置")
        bad = []
        for f in files:
            try:
                cfg = json.loads(_read(f))
            except Exception:
                continue
            if not ci.list_images(cfg, ci.KIND_VERTICAL):
                bad.append(f.name)
        assert not bad, f"这些车型没有可用的竖版图: {bad[:6]}"

    def test_color_code_always_resolvable(self):
        """每个车型：用它的任一 color key 都应能选出图。"""
        # 只取车型配置（数字命名）；_index.json / _names_*.json 是辅助文件
        files = sorted(f for f in CONFIGS.glob("*.json") if f.stem.isdigit())
        if not files:
            pytest.skip("无车型配置")
        bad = []
        for f in files:
            try:
                cfg = json.loads(_read(f))
            except Exception:
                continue
            imgs = ci.list_images(cfg, ci.KIND_VERTICAL)
            cols = [i["key"] for i in ((cfg.get("config") or {}).get("color") or [])]
            for c in cols:
                if ci.pick_key(imgs, c) != c and c in imgs:
                    bad.append(f"{f.name}:{c}")
        assert not bad, f"这些色码选不出对应图: {bad[:6]}"


# ───────────────────────── 实现细节守卫 ─────────────────────────

class TestDownloadImplementation:
    def _src(self) -> str:
        return _read(CAR_IMAGE)

    def test_streams_chunks(self):
        """★ 必须分块读 —— 一次性 read 实测只拿到 16384 字节（图被截断）。

        实测：231621 字节的 PNG 用 `await resp.content.read(n)` 只存下 16384 字节，
        磁盘文件也是 16 KB → 卡片显示破图。改 `iter_chunked` 后正常。
        """
        s = self._src()
        assert "iter_chunked" in s, "没有分块读取（图会被截断）"
        assert "resp.content.read(" not in s, "又用了不可靠的一次性 read"

    def test_file_io_in_executor(self):
        """文件写盘必须走 executor —— 否则 HA 记 blocking call 告警。"""
        s = self._src()
        assert "async_add_executor_job" in s, "同步写文件会阻塞事件循环"

    def test_host_allowlist(self):
        """只允许已知 CDN，避免配置被改成任意主机后盲目拉取。"""
        s = self._src()
        assert "_ALLOWED_HOSTS" in s and "p.ampmake.com" in s

    def test_size_cap(self):
        s = self._src()
        assert "_MAX_BYTES" in s, "缺单图体积上限"

    def test_concurrency_lock(self):
        """并发请求同一张图只下一次。"""
        s = self._src()
        assert "asyncio.Lock" in s and "lock" in s

    def test_failed_download_not_cached(self):
        """失败不落盘 → 下次请求会重试。"""
        s = self._src()
        # 只有校验通过才 replace 到目标路径
        assert ".part" in s and "replace(" in s

    def test_rejects_non_image(self):
        s = self._src()
        assert b"\\x89PNG".decode() in s or "PNG" in s, "没有校验文件头"

    def test_no_blocking_http(self):
        s = self._src()
        assert "aiohttp" in s and "async_get_clientsession" in s


class TestIntegrationWiring:
    def test_static_path_registered(self):
        s = _read(INIT)
        assert "/lixiang_car" in s, "车模图缓存目录没注册成静态路径"

    def test_view_registered(self):
        s = _read(INIT)
        assert "LiXiangCarImageView" in s, "车模图视图没注册"

    def test_view_is_homeassistant_view(self):
        """★ 必须是 HomeAssistantView —— 用 aiohttp 的 web.View 会
        `object has no attribute 'register'`（实测踩过）。"""
        s = _read(INIT)
        m = re.search(r"class LiXiangCarImageView\((\w+)\)", s)
        assert m, "找不到车模图视图类"
        assert m.group(1) == "HomeAssistantView", \
            f"基类是 {m.group(1)}，register_view 只接受 HomeAssistantView"

    def test_manager_key(self):
        s = _read(INIT)
        assert "lixiang_auto__car_image" in s

    def test_card_uses_static_by_default(self):
        s = _read(CARD)
        assert "c.car_3d === true" in s, "3D 应是 opt-in"
        assert "/lixiang_auto/car-image.json" in s
        assert "_loadCarImage" in s

    def test_card_has_fallback(self):
        s = _read(CARD)
        assert "icon_car_loc" in s, "缺占位兜底"


# ───────────────────────── 座椅死实体门控 ─────────────────────────

class TestSeatGating:
    """★ 车主问：「座椅加热，通风这些传感器有没有必要存在？」

    答案分两半：
    - 独立传感器（seat_fl_heat 等）：有值、无替代开关 → **保留**
    - 组合传感器（seat_heat_vent_*）：L 系 path="" 恒 unknown → **按平台门控**
      （M 系有真实来源 seatStatus.<座>SeatHeatVentState，不能删）
    """

    DEAD = ("seat_heat_vent_fl", "seat_heat_vent_fr",
            "seat_heat_vent_rl", "seat_heat_vent_rr")

    def test_dead_keys_are_platform_gated(self):
        s = _read(SIGNALS)
        for k in self.DEAD:
            m = re.search(r'"' + k + r'": SignalSpec\((.*?)\),', s, re.S)
            assert m, f"找不到 {k}"
            assert 'requires="platform:1"' in m.group(1), \
                f"{k} 没有按平台门控（L 系会建出死实体）"

    def test_not_universal_anymore(self):
        """不能再是 universal=True —— 那会让 L 系也建。"""
        s = _read(SIGNALS)
        for k in self.DEAD:
            m = re.search(r'"' + k + r'": SignalSpec\((.*?)\),', s, re.S)
            assert "universal=True" not in m.group(1), f"{k} 又变成 universal"

    def test_platform_dsl_supported(self):
        s = _read(FEATURES)
        assert 'kind == "platform"' in s, "resolve_requirement 没实现 platform: 分支"

    def test_platform_dsl_uses_ability_platform(self):
        s = _read(FEATURES)
        i = s.index('kind == "platform"')
        blk = s[i:i + 900]
        assert '"platform"' in blk, "没读 ability.platform"

    def test_platform_dsl_conservative_when_unknown(self):
        """拿不到能力表时保守保留（宁多不误删）。"""
        s = _read(FEATURES)
        i = s.index('kind == "platform"')
        blk = s[i:i + 900]
        assert "保守保留" in blk

    def test_m_series_platform_is_1(self):
        import m01_state as m
        assert m.M_SERIES_PLATFORM == "1", "M 系平台代号变了（门控会失效）"

    def test_platform_values(self):
        """实测：L6 platform=2（X 系），M01B platform=1（M 系）。"""
        l6 = json.loads(_read(CONFIGS / "100167931652606785.json"))
        m01 = json.loads(_read(CONFIGS / "100204301435085761.json"))
        assert str(l6["platform"]) == "2", "L6 平台号变了"
        assert str(m01["platform"]) == "1", "M01 平台号变了"

    def test_independent_seat_sensors_kept(self):
        """独立传感器要保留（有值、且没有对应的控制开关）。"""
        s = _read(SIGNALS)
        for k in ("seat_fl_heat", "seat_fl_vent", "seat_sl_heat", "seat_sl_vent"):
            assert f'"{k}"' in s, f"{k} 被误删了（它是有数据的）"

    def test_no_seat_switch_in_switch_py(self):
        """佐证：switch.py 里没有座椅加热开关 → 传感器不是冗余。"""
        sw = _read(PKG / "switch.py")
        assert "flSeatHeatSw" not in sw or "SEAT_SWITCHES" not in sw, \
            "switch.py 若有座椅加热开关，则传感器可能确实冗余，需重新评估"


class TestResultCodeMinus2:
    """cpCtrl 关闭充电口盖失败（车主实测）。"""

    def test_minus2_recorded(self):
        s = _read(PKG / "li_api.py")
        assert "-2:" in s, "-2 未收录"

    def test_failreason_exposed(self):
        """★ 服务端给的 failReason 必须暴露（此前被整个丢弃）。

        实测响应：
            pushState=7 pushStateText="执行失败"
            resultCode="-2" resultMsg="执行失败"
            failReason="set signal err!"     ← 唯一有信息量的字段
        """
        s = _read(PKG / "li_api.py")
        assert 'result.get("failReason")' in s, "failReason 没被使用"

    def test_no_unsafe_str_or(self):
        """`str(x or "")` 对 _LazySecret 会取到空值 —— 必须用条件表达式。"""
        s = _read(PKG / "li_api.py")
        bad = re.findall(r'str\(\w+ or ""\)', s)
        assert not bad, f"危险的 str(x or \"\") 写法: {bad}"
