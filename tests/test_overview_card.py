"""lixiang-overview-card —— 车辆总览卡回归测试（2026-10-13）。

背景
----
社区「尊界 S800 车辆总览」卡证明了「深色玻璃 + 三栏总览」这种形态受欢迎，
但它要求用户手填 28 个实体 ID。本集成新增的总览卡：

  · 走**实体自动发现**（`LixiangAutoBind`，按实体中文名匹配）→ 默认零配置
  · 车图/车型/车漆色都由 `/lixiang_auto/car-image.json` 给（与实车一致）
  · **只读展示**：不发送任何车控指令
  · 三档容器断点：≥950 三栏 / ≤750 两栏 / ≤480 手机单栏

这些约束用**子串 + node 真跑**双重断言，防止后续被改坏。
"""
from __future__ import annotations

import json
import subprocess
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CARDS = CC / "www" / "lixiang-cards"
CARD = CARDS / "lixiang-overview-card.js"
AUTOBIND = CARDS / "lixiang-auto-bind.js"


def _src() -> str:
    return CARD.read_text(encoding="utf-8")


def _strip_comments(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i)
            i = n if j < 0 else j + 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


class TestCardExists:
    def test_file_exists(self):
        assert CARD.is_file(), f"缺总览卡文件：{CARD}"

    def test_tag_and_registration(self):
        s = _strip_comments(_src())
        assert 'const CARD_TAG = "lixiang-overview-card"' in s, "卡片标签不对"
        assert "customElements.define(CARD_TAG, LixiangOverviewCard)" in s

    def test_registered_in_card_picker(self):
        """要出现在 HA「添加卡片」列表里。"""
        s = _src()
        assert "window.customCards" in s and "lixiang-overview-card" in s

    def test_shadow_dom(self):
        """隔离 HA 的全局样式（尊界卡同款做法）。"""
        s = _strip_comments(_src())
        assert 'attachShadow({mode:"open"})' in s or "attachShadow({ mode: \"open\" })" in s


class TestLayout:
    """三档容器断点 —— 桌面三栏 / 平板两栏 / 手机单栏。"""

    def test_container_type(self):
        assert "container-type:inline-size" in _strip_comments(_src()), "缺容器查询基座"

    def test_three_breakpoints(self):
        s = _strip_comments(_src())
        for bp in ("950", "750", "480"):
            assert f"@container (max-width: {bp}px)" in s, f"缺 {bp}px 断点"

    def test_three_column_grid(self):
        s = _strip_comments(_src())
        flat = s.replace(" ", "")
        assert "grid-template-columns:minmax(0,1.26fr)minmax(0,1fr)minmax(0,.86fr)" in flat, (
            "桌面三栏定义缺失")

    def test_mobile_single_column(self):
        s = _strip_comments(_src())
        # 480 断点里必须把 main 改回单列
        i = s.find("@container (max-width: 480px)")
        assert i > 0
        seg = s[i:i + 600]
        assert "grid-template-columns:1fr" in seg, "手机断点未改单列"


class TestEntities:
    """实体解析：手填优先 → 自动发现兜底。"""

    def test_uses_autobind(self):
        s = _strip_comments(_src())
        assert "window.LixiangAutoBind" in s, "未接入实体自动发现引擎"

    def test_manual_override_first(self):
        s = _strip_comments(_src())
        i = s.find("_eid(field)")
        assert i > 0
        seg = s[i:i + 400]
        assert "this._config.entities" in seg, "手填配置未优先"
        assert "autoBind" in seg, "自动发现未作为兜底"

    def test_no_hardcoded_entity_ids(self):
        """不得把某台车的实体 ID 写死进卡片。"""
        s = _strip_comments(_src())
        import re
        hits = re.findall(r'"(sensor|binary_sensor|switch|climate|lock|cover)\.[a-z0-9_]+"', s)
        # 允许 climate 之类的域级探测，但不得出现具体实体
        bad = [h for h in hits if h.startswith(("sensor.", "binary_sensor.", "switch."))]
        assert not bad, f"卡片里写死了具体实体 ID：{bad}"

    def test_autobind_has_overview_fields(self):
        """总览卡依赖的字段必须在自动绑定表里。"""
        s = AUTOBIND.read_text(encoding="utf-8")
        for field in ("range_total", "fuel", "wltc_total", "charge_voltage", "charge_current"):
            assert f"{field}:" in s, f"自动绑定表缺字段 {field}"


class TestReadOnly:
    """只读卡：绝不能发车控指令。"""

    def test_no_call_service(self):
        s = _strip_comments(_src())
        assert "callService" not in s, "总览卡不得调用服务（应只读）"

    def test_no_service_names(self):
        s = _strip_comments(_src())
        for svc in ("lock.lock", "lock.unlock", "switch.turn_on", "button.press"):
            assert svc not in s, f"出现控制调用 {svc}"

    def test_subscribes_but_never_writes(self):
        s = _strip_comments(_src())
        assert "set hass(hass)" in s, "未订阅 hass 状态"


class TestCarArt:
    """车图来源：配置覆盖 > 后端接口（侧视 > 横版 > 竖版）。"""

    def test_fetches_car_image_api(self):
        s = _strip_comments(_src())
        assert "/lixiang_auto/car-image.json" in s, "未从后端取车图"

    def test_prefers_side_then_horizontal_then_vertical(self):
        s = _strip_comments(_src())
        assert "data.side||data.horizontal||data.vertical" in s.replace(" ", ""), (
            "车图优先级不对（应 侧视 > 横版 > 竖版）")

    def test_config_image_wins(self):
        s = _strip_comments(_src())
        i = s.index("_loadArt() {")
        j = s.index("\n  }", i)        # ★ 不用写死窗口（加几行就被挤出窗口误报）
        assert "if (this._config.image) return" in s[i:j], "config.image 应优先且不被覆盖"

    def test_failure_keeps_layout(self):
        """接口失败不得出现破图（保持空 src）。"""
        s = _strip_comments(_src())
        i = s.find("_loadArt()")
        seg = s[i:i + 3000]
        assert "catch" in seg, "取车图无异常保护"

    def test_car_image_static_path_always_registered_with_cache(self):
        """★ 后端侧修「车图时有时无」的两处：

        ① 原来 `if _car_dir.is_dir()` 才注册 `/lixiang_car` → 首次安装/清缓存后
           目录还没建，图片 URL 会 **404 直到下次 HA 重启**；
        ② `cache_headers=False` → 响应无缓存头，手机每次重拉 224KB 大图，
           网络一抖就显示不出来。改为无条件注册 + 长缓存。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "__init__.py")
        s = p.read_text(encoding="utf-8")
        i = s.find('StaticPathConfig("/lixiang_car"')
        assert i > 0, "未注册车模图静态路径"
        # 第三个参数（cache_headers）必须是 True
        seg = s[i:i + 80]
        assert '"/lixiang_car", str(_car_dir), True' in seg.replace("\n", " "), (
            f"车图静态路径未开启缓存头：{seg[:70]}")
        # 注册前必须先建目录（无条件注册）
        j = s.find("_car_dir.mkdir(parents=True, exist_ok=True)")
        assert 0 < j < i, "未先创建车模图目录（会导致首次 404）"
        # 不得再有 is_dir() 门控
        assert "if _car_dir.is_dir():" not in s, "仍有 is_dir() 门控（首次会 404）"

    def test_more_data_expanded_by_default(self):
        """★ 2026-10-17 车主：「概览卡片下面有个更多数据，建议默认展开」。

        初次渲染默认展开；用户手动开合后沿用其状态（不覆盖用户选择）。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-overview-card.js")
        s = p.read_text(encoding="utf-8")
        assert "const open = _prev ? _prev.open : true;" in s, "「更多车辆数据」未默认展开"

    def test_overview_art_reapplied_after_rerender(self):
        """★ 2026-10-17 车主：「总览里面的车模图片也存在一会儿显示一会儿没显示的问题」

        根因：`_render()` 用 innerHTML 整块重画，模板里的车图 <img> 是
        `src="${config.image || ''}"` —— 用户没配图时就是 src="" 的空元素；
        而 `_loadArt()` 被 `_artDone` 只跑一次 → 重画后再没人给新 <img> 赋 src
        → **每重画一次（60s 定时器 / 任何状态更新）车图就消失一次**。

        修法：拆出 `_paintArt()`，每次渲染后从 localStorage 缓存把 URL 重新贴上
        （纯内存，不发请求），并保留 ?v= 重试兜底。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-overview-card.js")
        s = p.read_text(encoding="utf-8")
        assert "_paintArt() {" in s, "缺少 _paintArt（重画后车图不会被重新赋值）"
        # 必须在每次渲染后调用（与 _wireMap 并列）
        assert "this._paintArt();" in s, "_paintArt 未在渲染后调用"
        i = s.find("this._paintArt();")
        j = s.find("this._wireMap();")
        assert abs(i - j) < 400, "_paintArt 未与 _wireMap 一起在渲染末尾调用"
        # 贴图来源：缓存键 + 用户配图时不覆盖 + 失败重试
        assert "lx_car_img_v1" in s, "_paintArt 未从缓存取 URL"
        assert "img.src = src;" in s, "_paintArt 未设置 src"

    def test_overview_map_selfrenders_tiles_and_degrades(self):
        """总览卡地图：2026-10-18 由 <ha-map> 改为**自绘高德瓦片** + 降级处理。

        改 ha-map 的原因（实测，非猜测）：
          ha-map 的瓦片走 HA 代理 `/api/map_tiles` → 上游不可达时整块空白。
          测试机实测：容器内 DNS 只解析出 `tile.openstreetmap.org` 的 **IPv6**
          而无 IPv6 出口（`Network unreachable` / Errno 101）→ 代理 502 →
          「车辆位置」整段不显示（车控「位置页」因自拉高德瓦片而一直正常）。
          → 统一成与车控位置页相同的实现：直接拉高德瓦片自绘。

        本测试固化的核心意图（照顾其它车主，必须保持）：
          ① 只依赖高德，不依赖 HA 地图服务可用性
          ② `show_map: false` 可完全关闭
          ③ 拿不到经纬度（没开定位 / 车型无该实体 / 数据缺失）→ **不渲染**，
             不留空框或破图
          ④ `_st` 收【字段名】而不是实体 id（传 id 会二次解析成 null → 地图永不出现）
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-overview-card.js")
        s = p.read_text(encoding="utf-8")

        # ① 自绘高德瓦片，且不再依赖 ha-map
        assert "_renderTileMap" in s, "缺自绘瓦片实现"
        assert "webrd0" in s and "autonavi.com" in s, "应直接拉高德瓦片（与车控位置页一致）"
        # ★ style 必须是 8：实测高德已下线 style=6（深色）→ 404 → 地图空白
        assert "style=8" in s, "瓦片 style 必须为 8（实测 style=6 已 404）"
        # 只查代码行（注释里会提到 style=6 作为「已下线」的说明）
        _code = "\n".join(l for l in s.splitlines()
                              if not l.strip().startswith(("*", "//", "/*")))
        assert "style=6" not in _code, "style=6（深色瓦片）已被高德下线，会 404"
        assert 'querySelector(".lxmap .tiles")' in s, "瓦片容器未接上"
        # ② 降级与配置（原有意图必须保留）
        assert 'this._config.show_map === false' in s, "缺 show_map 关闭开关"
        assert "if (lat == null || lon == null) return" in s, (
            "无经纬度时仍会渲染（其他车主会看到空框/破图）")
        # ③ _st 收字段名（踩过的坑）
        assert 'this._st("tracker")' in s, "_st 必须传字段名而不是实体 id"
        # ④ 坐标系坑：偏移必须用小数部分 × 256，不能把整个瓦片坐标当像素
        assert "(fx - cx) * 256" in s, (
            "坐标系错误：车辆偏移要用瓦片坐标的小数部分 × 256"
            "（位置页曾因把整个 cx 当像素导致瓦片全跑到屏幕外）")
        # ⑤ 容器样式：瓦片要绝对定位 + 裁剪
        assert ".lxmap .tiles img" in s, "瓦片 <img> 缺绝对定位样式"

    def test_car_art_hardened_against_flaky_network(self):
        """★ 2026-10-16 车主："车辆图片经常显示不出来，有时候显示了过会儿又没了"。

        画像是网络抖动 + 后端静态路径/响应头问题。加固为：
          ① 上次成功的 URL 存 localStorage → 秒出，JSON 失败也能显示
          ② JSON 拉取失败重试一次（1.5s 后）
          ③ <img> onerror 带 ?v= 重试一次（破掉可能被缓存的坏响应）
        """
        s = _strip_comments(_src())
        assert "lx_car_img_v1" in s, "未做车图 URL 本地缓存"
        assert "localStorage.getItem(CK)" in s, "未先读缓存"
        assert "lxRetried" in s, "img 失败未重试"
        assert "catch" in s and "for (let i = 0; i < 2" in s, "JSON 拉取未重试"



class TestRuntime:
    """node 真跑：导入卡片 + 注入 mock hass，验证实体解析与格式化。

    卡片用 `__Base = typeof HTMLElement !== "undefined" ? HTMLElement : class {}`
    守卫，因此在 Node 里可导入、可实例化、可测纯逻辑。
    """

    def _run(self, code: str) -> str:
        r = subprocess.run(["node", "--input-type=module", "-e", code],
                           capture_output=True, text=True, timeout=90)
        assert r.returncode == 0, r.stderr[:800]
        return r.stdout.strip()

    def test_importable_without_dom(self):
        code = f"const m = await import('file://{CARD}'); process.stdout.write(m.CARD_TAG);"
        assert self._run(code) == "lixiang-overview-card"

    def test_resolves_entities_and_formats(self):
        """自动发现按中文名匹配；num/fmt 处理脏值。"""
        code = f"""
        const {{ LixiangOverviewCard }} = await import('file://{CARD}');
        const mk = (name, platform='lixiang_auto', domain='sensor') => ({{ platform, original_name: name, device_id: 'd1' }});
        const ENT = {{
          'sensor.b': mk('电池电量'),
          'sensor.rt': mk('总续航(CLTC)'),
          'sensor.re': mk('纯电续航(CLTC)'),
          'sensor.on': mk('在线状态'),
          'switch.s': mk('哨兵模式'),
        }};
        const states = {{
          'sensor.b': {{state:'62'}},
          'sensor.rt': {{state:'1094'}},
          'sensor.re': {{state:'152'}},
          'sensor.on': {{state:'在线'}},
          'switch.s': {{state:'off'}},
          'sensor.bad': {{state:'unknown'}},
        }};
        const hass = {{
          entities: Object.fromEntries(Object.entries(ENT).map(([k,v])=>[k, Object.assign({{entity_id:k}}, v)])),
          states, devices: {{}},
        }};
        globalThis.window = globalThis.window || {{}};
        await import('file://{AUTOBIND}');
        const el = new LixiangOverviewCard();
        el._config = {{}};
        el._hass = hass;
        const out = [
          el._eid('battery'), el._eid('range_total'), el._eid('online'), el._eid('sentry'),
          el.fmt('battery'), el.fmt('range_total'),
          String(el._num(undefined)), String(el._num('unknown')), String(el._num('2.5')),
          el._series('理想 L6 Pro'), el._series('MEGA'),
          el._eid('nonexistent_field') === null,
        ].join('|');
        process.stdout.write(String(out));
        """
        got = self._run(code).split("|")
        assert got[0] == "sensor.b", f"电池电量未解析：{got[0]}"
        assert got[1] == "sensor.rt", f"总续航未解析：{got[1]}"
        assert got[2] == "sensor.on", f"在线状态未解析：{got[2]}"
        assert got[3] == "switch.s", f"哨兵未解析：{got[3]}"
        assert got[4] == "62", f"格式化异常：{got[4]}"
        assert got[5] == "1,094", f"千分位异常：{got[5]}"
        assert got[6] == "null" and got[7] == "null", "脏值应判为 null（防止显示 NaN）"
        assert got[8] == "2.5", "数字解析异常"
        assert got[9] == "L6" and got[10] == "MEGA", f"车系识别异常：{got[9]}/{got[10]}"
        assert got[11] == "true", "未知字段应返回 null"

    def test_manual_config_overrides_autobind(self):
        code = f"""
        const {{ LixiangOverviewCard }} = await import('file://{CARD}');
        const hass = {{
          entities: {{ 'sensor.real': {{entity_id:'sensor.real', platform:'lixiang_auto', original_name:'电池电量', device_id:'d1'}} }},
          states: {{ 'sensor.real': {{state:'50'}}, 'sensor.mine': {{state:'77'}} }},
          devices: {{}},
        }};
        globalThis.window = globalThis.window || {{}};
        await import('file://{AUTOBIND}');
        const el = new LixiangOverviewCard();
        el._config = {{ entities: {{ battery: 'sensor.mine' }} }};
        el._hass = hass;
        process.stdout.write(el._eid('battery'));
        """
        assert self._run(code) == "sensor.mine", "手填实体应优先于自动发现"


class TestUnits:
    """★ 单位不能被假设（2026-10-14，车主截图实测到的真 bug）。

    截图里总览卡把胎压显示成 `250.3 bar`、油量显示成 `78 %`：
      · 胎压实体单位是 **kPa**（250.25），卡片直接当 bar 显示 → 250.3 bar
      · 油量实体当时标着 L，卡片当百分比画条 → 两者都不对

    现在卡片按实体真实 `unit_of_measurement` 换算/显示。
    """

    def _card(self) -> str:
        return _strip_comments(_src())

    def test_pressure_converts_kpa_to_bar(self):
        s = self._card()
        assert "_pressure(" in s, "缺胎压换算方法"
        assert 'u.includes("kpa")' in s and "v / 100" in s, "kPa 未换算成 bar"
        assert 'u.includes("psi")' in s, "未处理 psi"
        assert 'u.includes("bar")' in s, "未处理 bar"

    def test_tire_uses_pressure_helper(self):
        s = self._card()
        i = s.find("const tire = (field, label)")
        assert i > 0, "未找到胎压渲染"
        seg = s[i:i + 400]
        assert "this._pressure(field)" in seg, "胎压渲染没走换算"
        assert "2.0" in seg and "2.9" in seg, "低压/高压阈值缺失（应与健康页一致）"

    def test_percent_requires_percent_unit(self):
        s = self._card()
        assert "_pct(" in s, "缺百分比判定"
        i = s.find("_pct(field)")
        seg = s[i:i + 320]
        assert 'u.includes("%")' in seg, "百分比判定未校验实体单位"

    def test_no_hardcoded_bar_or_percent_labels(self):
        """胎压/油量的单位必须来自实体，不能写死。"""
        s = self._card()
        assert "<small>bar</small></div>" not in s, "胎压单位写死成 bar 了"
        assert '${this._unit(field)' in s, "未按实体单位显示"


class TestAppHomeLayoutRegressions:
    """2026-10-14 车主反馈的两个布局回归（都在车控首页）。"""

    HOME = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
            / "www" / "lixiang-cards" / "lixiang-app-home.js")

    def _src(self) -> str:
        return self.HOME.read_text(encoding="utf-8")

    def test_quick_two_columns_only_at_very_narrow(self):
        """快捷按钮收成 2 列只在**很窄**时。

        车主：「快捷按钮怎么一行只有2个了？」——
        容器查询在 v1.5.10 修好后，写在 ≤480px 里的 2 列规则在 460~490px 的
        desktop 栏里也命中。App 本体在 420pt 仍是 4 列，所以阈值必须更低。
        """
        s = self._src()
        # ≤480 那段里不能有 .quick 的 2 列规则
        i = s.find("@container (max-width: 480px)")
        assert i > 0
        blk = s[i:s.find("@container", i + 10)]
        assert ".quick { grid-template-columns: repeat(2" not in blk, (
            "≤480px 里又出现快捷按钮 2 列 —— 460~490px 的桌面栏会被误伤")
        # ★ 2026-10-14 二次修正：手机实测容器约 350~380px，400px 阈值仍会命中
        #   （车主截图证实：他手机上还是一行 2 个）→ 阈值再降到 340px。
        for thr in (400,):
            seg = s.find("@container (max-width: %dpx)" % thr)
            if seg > 0:
                assert ".quick { grid-template-columns: repeat(2" not in s[seg:seg + 200], (
                    "≤%dpx 段里仍有快捷按钮 2 列 —— 手机宽度会被误伤" % thr)
        # ★ 2026-10-28：阈值 340 → 300。340 会误伤「卡片被放进窄容器」
        #   （HA 桌面分栏/平板多列），导致入口掉成 1 列（用户多次反馈）。
        j = s.find("@container (max-width: 300px)")
        assert j > 0, "缺 ≤300px 的窄屏段（快捷按钮 2 列应在这里）"
        assert ".quick { grid-template-columns: repeat(2" in s[j:j + 200], "≤300px 段里没有 2 列规则"

    def test_car_image_leaves_side_margins(self):
        """车图要缩窄并居中，两侧留白给胎压标签（车主：胎压还在车子上）。"""
        s = self._src()
        i = s.find(".big3d img {")
        assert i > 0
        rule = s[i:s.find("}", i)]
        assert "display:block" in rule, "img 必须 display:block，否则 margin:auto 不居中"
        assert "margin:0 auto" in rule, "车图需居中"
        m = re.search(r"width:(\d+)%", rule)
        assert m and int(m.group(1)) <= 85, f"车图仍占满（{m.group(0)}），两侧没有留白给标签"

    def test_tire_labels_anchored_to_wheels(self):
        """★ 车主 2026-10-14 纠正：车是**横放**的，四个轮子在车的**上下两条边**上，
        标签要贴在各自车轮的上/下侧 —— 不是放在卡片左右两端（那是车头/车尾）。

        实测轮心：纵向 x≈28.4% / 71.4%（前/后），横向 y≈29% / 71%
        （车的右侧在上、左侧在下）；车体轮廓占图高 8%~92%。
        """
        s = self._src()
        i = s.find("_layoutTires() {")
        assert i > 0
        body = s[i:i + 2000]
        assert "cW * 0.284" in body and "cW * 0.714" in body, "标签未按实测轮心纵向定位（28.4%/71.4%）"
        assert "cH * 0.08" in body and "cH * 0.92" in body, "标签未贴车体轮廓上/下边缘（8%/92%）"
        # 上排是车的右侧、下排是车的左侧
        assert 'rf: [xF, yT], rr: [xR, yT]' in body, "上排应为右前/右后"
        assert 'lf: [xF, yB], lr: [xR, yB]' in body, "下排应为左前/左后"

    def test_tire_chip_transform_centers_on_point(self):
        """按"点"定位 → transform 需要双向居中。"""
        s = self._src()
        i = s.find(".big3d .tp {")
        assert i > 0
        rule = s[i:s.find("}", i)]
        assert "translate(-50%,-50%)" in rule, "tp 的 transform 应为 translate(-50%,-50%)（按点居中）"


class TestQuickActiveState:
    """快捷按钮"开着"判定（2026-10-14 车主："授权驾驶为什么一直显示开着"）。

    根因：`_on()` 用 `[…,"1"].some(x => v.includes(x))` ——
    button 实体的状态是**时间戳**（2026-10-14T07:14:35+00:00），里面含 "1"，
    于是「授权驾驶」永远被判为开着。叠加 `stateField` 解析不到时回退到动作实体，
    正好踩中这个坑。
    """

    HOME = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
            / "www" / "lixiang-cards" / "lixiang-app-home.js")

    def _src(self) -> str:
        return self.HOME.read_text(encoding="utf-8")

    def _on_body(self) -> str:
        s = self._src()
        i = s.find("_on(id) {")
        assert i > 0, "找不到 _on()"
        return s[i:i + 1400]

    def test_button_entity_never_on(self):
        b = self._on_body()
        assert 'split(".")[0] === "button"' in b, "button 实体（动作型）必须直接判为非开"

    def test_timestamp_state_rejected(self):
        b = self._on_body()
        assert "t/.test" in b or "T/.test" in b, "时间戳状态必须被判为非开"

    def test_no_loose_contains_one(self):
        """`includes("1")` 这种宽松判断必须消失。"""
        b = self._on_body()
        assert '.includes(x)' in b or '.includes((x))' in b, "缺少值包含判断"
        # 精确的 1 只允许全等
        assert 'v === "1"' in b, "数字 1 必须用全等判断（否则时间戳/小数都会命中）"

    def test_statefield_does_not_fall_back_to_action_entity(self):
        s = self._src()
        i = s.find("const stateEid =")
        assert i > 0
        line = s[i:s.find("\n", i)]
        assert "it.stateField ?" in line, (
            "配了 stateField 但解析不到时必须为 null，不能回退到动作实体（button 时间戳会被当开着）")


    def test_auth_label_follows_state(self):
        """★ 2026-10-14 写过一版「已授权时标签要变『已授权』」，**2026-10-17 推翻**。

        当年依据：官方截图里"已授权时标签变『已授权』"，我们用
        `binary_sensor.车辆授权`（`Vehicle.Provision.Authorize.State`）当依据。

        ★ 推翻理由（车主："已授权怎么一直显示？app 上显示是授权驾驶" + 实测）：
          · 那个信号是**这台车与账号的绑定关系，长期为 on** → 于是永远「已授权」；
          · 官方真正的依据是**车辆状态里的 BLE 组**（请求字段 `vehicleStateKey: 'BLE'`，
            枚举 connected/connecting/close/abnormal/unfamiliar），即**车端上报的
            蓝牙授权通道状态**，一次性的 —— 我们集成尚未订阅 `Vehicle.Ble.*`（缺实体）。

        所以：**拿不到依据就不假装有** —— auth 不再挂 stateField / onName，
        标签恒为官方动作名「授权驾驶」（动作下发是远程的，不受影响）。
        将来若接上 BLE 实体，这里才该恢复两态显示。
        """
        s = self._src()
        i = s.find('{ key:"auth"')
        assert i > 0
        j2 = s.find('{ key:', i + 5)          # ★ 取到下一条定义，别用第一个 '}' 截断
        entry = s[i:j2 if j2 > 0 else i + 400]
        assert 'stateField' not in entry, (
            "授权按钮不该再用长期 on 的『车辆授权』当依据（会永远显示已授权）")
        assert 'onName' not in entry, "拿不到 BLE 依据时不该显示『已授权』标签"
        assert 'name:"授权驾驶"' in entry, "应保持官方动作名「授权驾驶」"

    def test_auth_has_official_confirm_flow(self):
        """★ 官方逻辑（逆向证据）：授权驾驶是**动作**且有二次确认。

        来源 `docs/PAGE_GENERATION.md` / `docs/功能名称来源_20260926.md` 的
        `VehicleHomeControl` I18N：authorization=授权驾驶 / alreadyAuthorization=已授权
        / alreadyStart=已启动 / dismiss=不再提醒；
        车主截图也证实按下后弹「请在2分钟内上车并踩下刹车踏板，下车后请远程上锁。」
        """
        s = self._src()
        i = s.find('{ key:"auth"')
        ent = s[i:s.find("}", i) + 1]
        assert 'confirm:"请在 2 分钟内上车并踩下刹车踏板，下车后请远程上锁。"' in ent, "缺官方确认文案"
        assert "remember:true" in ent, "确认框应带「不再提醒」"
        assert 'startedName:"已启动"' in ent, "缺「已启动」态（车辆已启动时显示）"

    def test_confirm_dialog_component(self):
        s = self._src()
        assert "_confirm(opts)" in s, "缺二次确认组件"
        body = s[s.find("_confirm(opts)"):s.find("_confirm(opts)") + 1400]
        assert "取消" in body and "确定" in body, "确认框缺取消/确定"
        assert "不再提醒" in body, "确认框缺「不再提醒」"
        assert "resolve({ ok, remember })" in body, "确认框应回传 {ok, remember}"

    def test_action_gated_by_confirm(self):
        """动作必须先确认再执行（确认前不得调服务）。"""
        s = self._src()
        i = s.find("if (def.confirm && !this._noAsk(key))")
        assert i > 0, "动作未被确认门控"
        seg = s[i:i + 300]
        assert "await this._confirm(" in seg and "if (!r.ok) return;" in seg, "确认流程不完整"
        assert "this._setNoAsk(key, true)" in seg, "勾了「不再提醒」未持久化"

    def test_started_state_overrides_label(self):
        """车辆已启动（非驻车）→ 授权按钮显示「已启动」。"""
        s = self._src()
        i = s.find("if (it.startedName)")
        assert i > 0, "缺已启动态处理"
        seg = s[i:i + 400]
        assert "驻车" in seg and "startedName" in seg, "已启动判定未接状态实体"

    def test_home_has_no_secondary_page_cards(self):
        """★ 车主纠正："有些是二级菜单里面的"。

        权威依据 `lixiang-reverse/docs/SUBPAGES.md` §3.5：
        · `otaTag`   → 二级页 **VehicleOtaPage**（不是首页卡片）
        · `configTag`→ 二级页 **VehicleSetting**（不是首页卡片）
        · `lock/window/doorTag` → **首页快捷按钮**（不是状态卡）
        所以首页只应有官方 §12.2 证实的那几张卡（空调/地图/里程/电量/哨兵）。
        """
        import re as _re
        s = self._src()
        cards = set(_re.findall(r'class="card ([a-z0-9]+)"', s))
        assert not ({"door", "win", "stat4", "ota", "cfg"} & cards), (
            f"首页又出现二级页卡片：{sorted(cards)}（车门/车窗是按钮，OTA/配置是二级页）")

    def test_vinfo_page_shows_real_version_and_ota(self):
        """车辆信息页（二级）必须显示真实车机版本 / OTA —— 不能再写"集成未采集"。"""
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-vehicle-info-page.js")
        s = p.read_text(encoding="utf-8")
        assert 'this._eid("head_unit_ver")' in s, "车机版本未接实体"
        assert 'this._eid("ota_status")' in s, "OTA 状态未接实体"
        assert ('id: "v-ota"' in s) or ('id="v-ota"' in s), "缺 OTA 行"
        # 运行代码里不得再有"未采集"的提示（注释里保留历史说明可以）
        code = "\n".join(l for l in s.splitlines() if not l.strip().startswith(("*", "//")))
        assert "尚未采集" not in code, "仍在提示『整车软件版本集成尚未采集』"

    def test_autobind_has_version_ota_fields(self):
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-auto-bind.js")
        s = p.read_text(encoding="utf-8")
        for f in ("head_unit_ver", "ota_version", "ota_status", "ota_progress"):
            assert f in s, f"自动发现表缺字段 {f}"

    def test_phone_keeps_official_grid_columns(self):
        """★ 车主两次纠正："为什么下面是一列了？" / 官方全页截图对照。

        官方 App 在手机宽度（容器 ≈358px）：
          · 快捷按钮  一行 **4 个**
          · 下方两卡  一行 **2 个**（空调 + 地图）
          · 入口瓦片  一行 **2 个**（车辆健康|任务大师 / 钥匙管理|情景模式 / 车辆设置）
        我先后把 .row2 与 .entries 写在 `≤480px` 里收成一列 —— 都命中了手机宽度，全错。
        现在：≤480 一律不收；只在极窄 ≤300px 才收（且 .entries 永远两列）。
        """
        s = self._src()
        i = s.find("@container (max-width: 480px)")
        assert i > 0
        blk = s[i:s.find("@container", i + 10)]
        for sel in (".row2", ".entries"):
            assert f"{sel} {{ grid-template-columns: minmax(0,1fr)" not in blk, (
                f"≤480px 段又把 {sel} 收成一列了（手机宽度应与官方一样多列）")
        assert ".quick { grid-template-columns: repeat(2" not in blk, (
            "≤480px 段又把快捷按钮收成 2 列了（官方手机宽度是 4 列）")
        # 极窄兜底必须齐（★ 2026-10-28：阈值 340→300；
        #   .entries 不再收单列 —— 官方 App 任何手机宽度都是并排两列，
        #   收单列会让「卡片在窄容器里」的用户只看到 1 列（多次反馈））
        j = s.find("@container (max-width: 300px)")
        assert j > 0
        tail = s[j:j + 400]
        for frag in (".quick { grid-template-columns: repeat(2",
                     ".row2 { grid-template-columns: minmax(0,1fr)"):
            assert frag in tail, f"≤300px 段缺兜底：{frag}"
        assert ".entries { grid-template-columns: minmax(0,1fr)" not in tail, (
            "≤300px 段不许把 .entries 收成单列（用户会只看到 1 列）")

    def test_charge_page_has_official_four_metrics(self):
        """★ 官方充电页 4 项指标：充电效率 / 充电功率 / 输入电流 / 输入电压。

        依据：官方 i18n 对象 powernew/avnew/anew/vnew + 英文
        Efficiency/Power/Input current/Input voltage；组件 ChargePowerText /
        ChargeAVText / ChargeCurrentText / ChargeVoltageText。
        """
        import re as _re, collections as _c
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        for iid in ("m-power", "m-pw", "m-amp", "m-volt"):
            assert f'id="{iid}"' in s, f"缺官方 4 项指标之一：#{iid}"
        for label in ('power: "充电效率"', 'powerKw: "充电功率"', 'amp: "输入电流"', 'volt: "输入电压"'):
            assert label in s, f"指标文案不对：{label}"
        # 指标行顺序必须是官方的：充电效率 → 充电功率 → 输入电流 → 输入电压
        order = [_re.search(r'id="(m-power|m-pw|m-amp|m-volt)"', blk).group(1)
                 for blk in _re.findall(r'<div class="m">.*?</div></div>', s, _re.S)
                 if _re.search(r'id="(m-power|m-pw|m-amp|m-volt)"', blk)]
        assert order == ["m-power", "m-pw", "m-amp", "m-volt"], f"指标顺序不对：{order}"
        # 单位必须跟随实体（不写死）
        for uid in ("u-power", "u-amp", "u-volt"):
            assert f'id="{uid}"' in s, f"缺单位元素 {uid}"
        assert 'unit_of_measurement' in s, "单位未跟随实体"
        # 无重复 id（上次抠块差点留下重复）
        ids = _re.findall(r'id="([\w-]+)"', s)
        dup = {k: v for k, v in _c.Counter(ids).items() if v > 1}
        assert not dup, f"充电页有重复 id：{dup}"


    def test_overview_detail_grid_always_four_columns(self):
        """★ 车主："剩余时间下面，一行直接显示四个，跟 app 保持一致。我们这样两行不美观"

        总览卡统计区共 8 项，其中「剩余充电时间」后面还有 4 项
        （空调设定温度/电池包电压/本月里程/累计充电量）。原来窄屏断点把它降到
        3 列、2 列 → 那 4 项掉成两行。现固定为一行四个。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-overview-card.js")
        s = p.read_text(encoding="utf-8")
        import re as _re
        # 基准规则（容忍换行/缩进）
        assert _re.search(r"\.detail-grid \{[^}]*display:grid;[^}]*grid-template-columns:\s*repeat\(4,minmax\(0,1fr\)\)",
                          s), "统计区基准不是一行四个"
        # 三处（基准 + 两个窄屏断点）都必须是 4 列
        assert s.count("grid-template-columns:repeat(4,minmax(0,1fr))") >= 3, (
            "窄屏断点没全部改成一行四个")
        assert ".detail-grid { grid-template-columns:repeat(4,minmax(0,1fr)); }" in s, (
            "3 列断点未改成 4 列")
        assert ".detail-grid { grid-template-columns:repeat(2,minmax(0,1fr))" not in s, (
            "还有把统计区压成两列的规则")
        assert ".detail-grid { grid-template-columns:repeat(3,minmax(0,1fr))" not in s, (
            "还有把统计区压成三列的规则")


    def test_auth_button_not_permanently_authorized(self):
        """★ 2026-10-17 车主：「已授权怎么一直显示？app 上显示是授权驾驶」

        根因：我们拿 `binary_sensor.车辆授权`（= `Vehicle.Provision.Authorize.State`，
        那是**这台车与账号的绑定关系，长期为 on**）当作"是否已授权"的依据
        （onName 改标签 + stateField 点亮圆点）→ 于是永远显示「已授权」。

        官方依据（Hermes 包证据）：**LXVehicleBLEConnectState**
        （'bleConnected' / 'bleConnectionStatus'，55/78 处引用）—— 蓝牙连接状态，
        一次性的、下车即失效；我们集成**没有** BLE 信号，无法复现。

        结论：拿不到真实依据就不假装有 —— 去掉 onName 与 stateField，
        始终显示官方动作名「授权驾驶」，圆点也不常亮（点击下发不受影响）。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-app-home.js")
        s = p.read_text(encoding="utf-8")
        i = s.find('{ key:"auth"')
        assert i > 0, "未找到 auth 按钮定义"
        # 只取这一条定义（到下一个 { key: 为止）
        j = s.find('{ key:', i + 5)
        blk = s[i:j if j > 0 else i + 400]
        assert 'onName' not in blk, "授权按钮仍会用「已授权」标签（长期 on 的绑定关系当依据）"
        assert 'stateField' not in blk, "授权按钮仍绑定 stateField（圆点会常亮）"
        assert 'name:"授权驾驶"' in blk, "标签应保持官方的动作名「授权驾驶」"

    def test_multicar_entity_disambiguation(self):
        """★ 2026-10-18：账号里有【两辆车】时，总览卡地图不显示（删一辆就正常）。

        根因：自动绑定引擎各匹配分支都是 `cands[0]`（取第一个命中），
        而 `_pool()` 里的 `isMine` 判定是
            `e.platform === "lixiang_auto" || devIds.has(e.device_id)`
        —— 前者【不区分车】→ 两辆车的同名实体（都叫「车辆位置」「车锁」…）
        一起进池 → 命中哪辆不确定 → 若命中的是没有位置的另一辆，
        `_mapHtml()` 的 lat/lon 为 null → 整段 return "" → 地图消失。

        修法：`_pick()` 消歧 —— 多候选时优先选状态有值（非 unknown）的。
        """
        bind = (Path(__file__).resolve().parent.parent / "custom_components"
                / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-auto-bind.js")
        src = bind.read_text(encoding="utf-8")

        assert "_pick(cands)" in src, "匹配分支必须走 _pick 消歧"
        # _pool 的 isMine：有 vin 时按 device 收窄，不要无差别按 platform 收
        assert 'const scoped = !!(vin && devIds && devIds.size);' in src, (
            "_pool 应在有 vin 时按设备收窄（否则两辆车实体混在一起）")
        assert "const isMine = scoped ? byDevice" in src, (
            "isMine 需按 scoped 决定是否只看 device")
        # 消歧逻辑本身：多候选时选有值的
        i = src.find("_pick(cands) {")
        assert i > 0, "缺 _pick 方法"
        body = src[i:i + 1200]
        assert 'unknown' in body and 'unavailable' in body, (
            "_pick 必须排除 unknown/unavailable 的候选")
    def test_chev_expands_quick_not_car(self):
        """★ 2026-10-16 车主定稿（两次澄清）：

          「小箭头不是收齐车模的功能，是展开和收齐快捷键的功能。
            比如有车可能有 8 个快捷，那么小箭头就可以展开更多。
            车模是上滑收起，下拉展开。」

        所以三条硬规则：
          ① 默认只显示**第一行 4 个**快捷键；按小箭头展开更多（全部可用项）
          ② 小箭头**永不**碰车模（车模由滚动驱动）
          ③ 可用项 ≤4 时（没有"更多"）箭头藏起来，不留无用按钮
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-app-home.js")
        s = p.read_text(encoding="utf-8")
        # ① 默认收起第一行 4 个 + 展开态
        assert ".root:not(.quick-open) .quick > .q:nth-child(n+5) { display:none; }" in s, (
            "默认没有收起成第一行 4 个")
        assert ".root.quick-open .chev img { transform:rotate(180deg); }" in s, "缺展开态样式"
        # ② 接线分离：小箭头→快捷，右上小车→车模
        assert 'bind(this.querySelector("#chev"), toggleQuick);' in s, "小箭头没接快捷开关"
        assert 'bind(this.querySelector("#mini"), toggle3d);' in s, "右上小车没接车模开关"
        # ③ ≤4 项藏箭头
        assert 'chevEl.style.display = avail.length > 4 ? "" : "none";' in s, (
            "可用项 ≤4 时没有隐藏箭头")

    def test_car_area_collapses_without_gap(self):
        """★ 2026-10-16 车主：「车模都右上角了，中间车模地方空着了，没收起来」

        手机断点里曾经是 `.big3d, .root.expanded3d .big3d { height:188px }` ——
        裸 .big3d 盖掉了收起态的 height:0，收起后仍占 188px 空白，
        而车模已经缩到右上角小图里了。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-app-home.js")
        s = p.read_text(encoding="utf-8")
        assert ".big3d, .root.expanded3d .big3d { height: 188px; }" not in s, (
            "手机断点还有裸 .big3d —— 收起后会留空白")
        assert ".root.expanded3d .big3d { height: 188px; }" in s, "手机断点缺展开态高度"

    def test_charge_monthly_count_refreshed_after_fetch(self):
        """★ 2026-10-17 车主：「本月充电次数没正确显示」

        根因是**时序**：`_update()` 先跑（此时月度统计还没到 → 本月次数显示「—」），
        末尾才发起**不 await** 的 `_fetchStats()`；等数据回来后只调了 `_renderYears()`
        （记录区），**没刷新顶部统计** → 本月次数一直停在「—」，只有手动刷新才好。

        修法：把电量三栏抽成 `_updateStats()`，在月度统计到位后单独调它
        （不整卡重绘，避免连带重画车图/滑杆/地图）。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        assert "_updateStats() {" in s, "缺少 _updateStats（顶部电量三栏无法单独刷新）"
        # 本月次数的赋值必须在 _updateStats 里
        i = s.find("_updateStats() {")
        assert 'q("#s-times")' in s[i:i + 2000], "本月次数赋值不在 _updateStats 内"
        # 月度统计到位后必须调用它
        # 锚在「月度统计解析成功」那段（_years 组装之后），而不是别处的 _renderYears()
        j = s.find("this._years = Object.keys(byYear)")
        assert j > 0, "未找到月度统计解析处"
        assert "this._updateStats();" in s[j:j + 800], "月度统计到位后未补刷顶部统计"

    def test_charge_idle_hides_empty_metrics(self):
        """★ 2026-10-16 车主截图标注：「这个信息可否在不充电时自动隐藏起来?」

        未充电时 4 项指标恒为「—」（截图：已预约 · 20% · 剩余0分钟 ·
        — km/hr — kW — A — V），一片空值既占版面又像坏掉 → 只在充电中显示。
        判定复用 isCharging（充电状态含「充电中」），与环形表/闪电同一口径。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        # ① 指标行随充电状态显隐
        assert 'mBox.style.display = isCharging ? "" : "none"' in s, (
            "指标行没有随充电状态显隐")
        # ② 剩余时间：**只在真有时长时显示**（0 / 空都收起）
        #   ★ 2026-10-17 修正：原来写 `!(isCharging || hasDur)` —— 充电中但车给 0 时
        #     仍会显示「剩余0分钟」这种假信息（车主："剩余充电时间没显示"）。
        #     官方 Hermes 包证据：App 取的是同一个路径
        #     'Vehicle.Powertrain.Battery.ChargeSurplusTime'，车此刻就是没给估值。
        # 按官方 PowerDisplay 三分支（Hermes 包还原）：
        #   有值 → 剩余X小时Y分钟 ｜ 充电中但=0 → 充电校准中，预计5-10分钟 ｜ 其余 → 收起
        assert "I18N.calibrating" in s, "缺官方「充电校准中」分支"
        assert "rEl.hidden = false;" in s and "rEl.hidden = true;" in s, "剩余时间行没有三分支显隐"
        assert 'calibrating: "充电校准中，预计5-10分钟"' in s, "缺官方校准文案原文"
        # ③ 必须有 CSS 兜底：.metrics 是 display:grid，会盖掉 hidden 属性的 display:none
        assert ".hero .metrics[hidden], .remline[hidden] { display:none; }" in s, (
            "缺 [hidden] 的 CSS 兜底（display:grid 会盖掉 hidden）")


    def test_charge_metrics_single_row_four_columns(self):
        """★ 车主："剩余时间下面，一行直接显示四个，跟 app 保持一致。我们这样两行不美观"

        官方充电管理页的 4 项指标（充电效率/充电功率/输入电流/输入电压）在手机宽度
        也是【一行四列】。我们原来在 ≤480px 里压成 2×2 两行。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        assert ".hero .metrics { display:grid; grid-template-columns:repeat(4, minmax(0,1fr))" in s, (
            "指标行基准不是一行四列")
        i = s.find("@container (max-width: 480px)")
        # 找到含 .hero .metrics 的那个手机断点块
        j = s.find(".hero .metrics { grid-template-columns: repeat(4, minmax(0,1fr))", i)
        assert j > 0, "手机断点没有保持一行四列"
        # 不得再出现两列写法
        assert ".hero .metrics { grid-template-columns: minmax(0,1fr) minmax(0,1fr); }" not in s, (
            "还有把指标压成两行的规则")


    def test_charge_manage_page_matches_official(self):
        """★ 官方「充电管理」页（车主 2026-10-14 截图）逐块对齐。

        官方结构：标题充电管理 + 右上充电记录 · 环形电量表(SOC+绿弧+闪电) ·
        「剩余2小时7分钟」 · 4 项指标 · 充电上限滑杆(80–100%) + 提示 ·
        预约充电开关 · 按时结束 · 页脚。
        （「停止充电」不做：命令 remote_charge_control 走 App metaJob 通道，
          HTTP 实测 2009，见 li_api.py 的 _JOB_CHANNEL_COMMANDS。）
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        for eid in ("ring-arc", "ring-soc", "rem-text", "limit-range",
                    "limit-min", "limit-max", "tg-appt", "end-time", "go-records"):
            assert f'id="{eid}"' in s, f"缺官方元素 #{eid}"
        assert 'title: "充电管理"' in s, "标题应为官方的「充电管理」"
        assert 'records: "充电记录"' in s, "缺右上角「充电记录」入口"
        assert "日常快充建议最高设置为95%" in s, "缺官方提示原文"
        assert "适用于交流充电桩和理想20kW直流充电桩" in s, "缺官方页脚原文"
        assert 'apptEnd: "按时结束"' in s, "缺官方文案「按时结束」"
        # 时长格式：官方「剩余2小时7分钟」（不是 185 min）
        i = s.find("_fmtDur(minutes)")
        assert i > 0, "缺时长格式化"
        seg = s[i:i + 400]
        assert "I18N.hour" in seg and "I18N.min" in seg, "时长格式未用官方单位"
        # 滑杆要真的能下发（number.set_value）且范围取实体 min/max
        assert 'callService("number", "set_value"' in s, "上限滑杆未接下发"
        assert 'attributes.min' in s.replace("a.min", "attributes.min") or "a.min" in s, "滑杆未取实体 min/max"
        # 预约开关 / 按时结束也要能下发
        assert 'callService("switch", on ? "turn_off" : "turn_on"' in s, "预约开关未接下发"
        assert 'callService("time", "set_value"' in s, "按时结束未接下发"

    def test_no_host_selector_without_shadow_dom(self):
        """★ 2026-10-14 真 bug：14 个卡把主题变量写在 `:host`，但它们都不用 Shadow DOM
        → `:host` 永不匹配 → 强调色变量（--lx-green/orange/red）一直是空的
        （实测：环形电量表的弧线 stroke 计算成 none、状态点不变绿）。

        仓库里 test_card_container_queries.py 早就记录过同类教训（container-type 挂 :host
        导致容器查询永不触发），这次是主题变量重蹈覆辙。
        """
        import re as _re
        d = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards")
        bad = []
        for f in sorted(d.glob("lixiang-*.js")):
            if f.name == "lixiang-all.js":
                continue
            src = f.read_text(encoding="utf-8")
            # 只认「选择器」形式（:host 后跟 { ），排除注释里提到 :host 的情况
            if _re.search(r":host\s*(\{|,)", src) and "attachShadow" not in src:
                bad.append(f.name)
        assert not bad, f"这些卡不用 Shadow DOM 却写了 :host：{bad}"

    def test_charge_page_wording_matches_official(self):
        """★ 车主："文案还有问题，充电效率，不是充电功率，单位也有问题。"

        官方充电页（i18n 对象，中英双语，从 index.vehicle.bundle 提取）：
          powernew='充电效率' / avnew='充电功率' / anew='输入电流' / vnew='输入电压'
          （英文：Efficiency / Power / Input current / Input voltage）
        另外官方状态词是「等待充电 / 充电中 / 充电完成」（不是"未充电/已充满"）。
        """
        p = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
             / "www" / "lixiang-cards" / "lixiang-charge-page.js")
        s = p.read_text(encoding="utf-8")
        assert 'power: "充电效率"' in s, "功率指标文案应为官方的「充电效率」"
        assert 'notCharging: "等待充电"' in s, "未充电状态应为官方的「等待充电」"
        assert 'done: "充电完成"' in s, "充满状态应为官方的「充电完成」"
        # 单位跟随实体，不再写死 kW
        assert 'id="u-power"' in s, "缺单位元素"
        assert 'unit_of_measurement' in s and '"km/hr"' in s, "单位应跟随实体（默认 km/hr）"
        # 「充电效率」那一项的单位不能写死（跟随实体）；「充电功率」用 kW 是对的
        i_eff = s.find('id="m-power"')
        seg_eff = s[i_eff:i_eff + 160]
        assert "kW" not in seg_eff, "充电效率的单位不能写死 kW（应跟随实体）"

    def test_charge_efficiency_signal_renamed(self):
        """信号/实体的名称与单位同步改为官方的「充电效率(km/hr)」。"""
        base = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
        sig = (base / "signals.py").read_text(encoding="utf-8")
        sen = (base / "sensor.py").read_text(encoding="utf-8")
        bind = (base / "www" / "lixiang-cards" / "lixiang-auto-bind.js").read_text(encoding="utf-8")
        for src in (sig, sen):
            assert "充电效率(CLTC)" in src and "充电效率(WLTC)" in src, "信号/实体名未改"
            assert "充电功率(CLTC)" not in src, "旧名残留（会与单位矛盾）"
        assert 'unit="km/hr"' in sig, "信号单位未改为 km/hr"
        # 自动发现的匹配名必须同步，否则绑不上新实体
        assert "充电效率(CLTC)" in bind, "自动发现表未同步新实体名"

    def test_ac_chip_labels_match_official(self):
        """★ 官方空调页文案（从 index.vehicle.bundle 反汇编提取，23 项）：
        deicing='除雪除霜' · rapidCool='极速制冷' · rapidHeat='极速制热' · steeringWheelHeat='方向盘加热'。
        我们原来写的 座椅/吹风/除霜 与官方不一致。
        """
        s = self._src()
        assert '"除雪除霜"' in s, "除霜 chip 文案应为官方的「除雪除霜」"
        assert '"极速制冷"' in s, "吹风 chip 文案应为官方的「极速制冷」"
        assert '"方向盘加热"' in s and '"极速制热"' in s, "座椅 chip 应随绑定显示「方向盘加热」/「极速制热」"

    def test_ac_fan_blue_spin_when_on(self):
        """★ 车主："风扇能动吗？开起来的时候风扇蓝色转动。"

        官方资源本就是配套的（app 内实测）：
          home_fan_open.png  = 纯白 (255,255,255)  → 开启态，配**蓝底**
          ic_fan_close.png   = 灰色 (153,153,153)  → 关闭态，配浅底
        我们此前永远用白色图标（浅底上几乎看不见），且用 `_on()` 判 climate 实体
        （状态是 cool/heat/auto，不是 on）→ 永远判为关。
        """
        s = self._src()
        # ① 默认必须是深色图标（浅底可见）
        assert 'id="fan"><img src="${__iconBase}/ic_home_fan_off.webp"' in s, (
            "风扇默认图标应为深色版（白色版在浅底上看不见）")
        # ② 开启 = 蓝底 + 白图标 + 转动
        assert ".ac .fan.on { background:var(--lx-blue)" in s, "开启态不是蓝底"
        assert ".ac .fan.on img { animation:spin" in s, "开启态风扇不转"
        # ③ climate 状态判定
        i = s.find("const acRaw")
        assert i > 0, "缺空调状态读取"
        seg = s[i:i + 500]
        for st in ("cool", "heat", "auto", "fan_only"):
            assert f'"{st}"' in seg, f"空调状态判定漏了 {st}"
        assert 'this._img(acOn ? "ic_home_fan_on.webp" : "ic_home_fan_off.webp")' in seg, (
            "未按开关切换图标")

    def test_on_handles_climate_states(self):
        """`_on()` 也要认 climate 域（别处复用时不至于误判为关）。"""
        s = self._src()
        i = s.find("_on(id) {")
        seg = s[i:i + 1400]
        assert '"cool"' in seg and '"heat_cool"' in seg, "_on() 未处理 climate 状态"

    def test_no_duplicate_ids_in_template(self):
        """★ 模板里不得有重复 id。

        本轮真实踩到：新加的哨兵徽标用了 `id="v-sentry"`，与卡片里已有元素同名 →
        `querySelector` 命中旧元素，徽标永远显示成别的元素（实测宽 356px、文字"已激活"）。
        同类坑还有 **class 撞车**：徽标用了 `class="sentry"`，被哨兵卡的 `.sentry{display:flex}`
        规则命中 → 变成一个撑满整行的 flex 块。
        """
        import re as _re, collections as _c
        s = self._src()
        ids = _re.findall(r'id="([\w-]+)"', s)
        dup = {k: v for k, v in _c.Counter(ids).items() if v > 1}
        assert not dup, f"模板里有重复 id：{dup}"

    def test_map_photo_button(self):
        """官方的地图卡有拍照按钮（HomeControlMapPhoto）。"""
        s = self._src()
        assert 'id="hm-shot"' in s, "地图卡缺拍照按钮"
        assert "ic_home_photo.png" in s, "拍照按钮应使用官方相机图标"
        i = s.find("const shotEl = this.querySelector(\"#hm-shot\")")
        assert i > 0, "拍照按钮未接线"
        seg = s[i:i + 500]
        assert 'callService("button", "press"' in seg, "拍照按钮应调用 button.press"
        assert 'this._eid("btn_photo")' in seg, "拍照按钮应绑 btn_photo 实体"

    def test_ac_card_seat_art(self):
        """官方空调卡右下角有座椅插图。"""
        s = self._src()
        assert 'class="seatart"' in s, "空调卡缺座椅插图"
        assert ".ac .seatart" in s, "座椅插图缺样式"
        assert "position:absolute" in s[s.find(".ac .seatart"):s.find(".ac .seatart") + 200], (
            "座椅插图应绝对定位在卡片右下角")

    def test_header_badges(self):
        """官方顶部徽标（HomeControlHeaderWarning / HeaderSentry）。"""
        s = self._src()
        assert 'id="v-badge-warn"' in s and 'id="v-badge-sentry"' in s, "缺告警/哨兵徽标"
        assert "src_assets_images_vehicle_header_ic_home_warning.png" in s, "告警徽标应用官方 header 图标"
        assert "src_assets_images_vehicle_header_ic_home_sentry.png" in s, "哨兵徽标应用官方 header 图标"
        # 类名不得与既有 .sentry 撞车
        assert 'class="badge badge-sentry"' in s, "哨兵徽标类名必须唯一（badge-sentry）"
        # 数据来源
        i = s.find('const wEl = this.querySelector("#v-badge-warn")')
        assert i > 0, "告警徽标未接数据"
        seg = s[i:i + 600]
        assert "warn_lf" in seg and "warn_rr" in seg, "告警徽标应汇总胎压告警实体"

    def test_active_button_is_filled_circle(self):
        """★ 车主两次澄清后定案：状态用**圆圈**表达。

        官方 App 车控页：未激活 = **空心圆** + 深色线稿图标；
        激活 = **实心深色圆** + 白色图标（官方图资本来就是配套的：
        *_off_* 是深色线稿、*_on_* 是纯白）。
        原来是"蓝圈 + 浅蓝底"，与官方不一致。
        """
        s = self._src()
        i = s.find(".q.on .c {")
        assert i > 0, "缺 .q.on .c 规则"
        rule = s[i:s.find("}", i)]
        assert "background:#1b1f27" in rule, "激活态不是实心深色圆"
        assert "border-color:#1b1f27" in rule, "激活态边框色应与填充一致（实心效果）"
        assert "rgba(10,88,246" not in rule, "仍是旧的浅蓝底，不是实心圆"

    def test_on_icons_are_white(self):
        """实心圆上必须配白色图标 —— 官方 *_on_* 资源就是纯白。"""
        from PIL import Image
        import numpy as _np
        base = (Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"
                / "www" / "lixiang-icons")
        for name in ("ic_home_lock_open_lisa.png", "ic_home_rearmirroheat_on_lisa.png"):
            p = base / name
            if not p.is_file():
                continue
            a = _np.array(Image.open(p).convert("RGBA"))
            vis = a[..., 3] > 40
            if not vis.any():
                continue
            lum = a[..., :3][vis].mean()
            assert lum > 200, f"{name} 不是白色图标（亮度 {lum:.0f}），配实心深色圆会看不见"

    def test_quick_label_switches_on_state(self):
        """_applyQuick 必须真的把标签切过去（不是只定义了 onName）。"""
        s = self._src()
        i = s.find("const nameEl = el.querySelector")
        assert i > 0, "未找到标签切换逻辑"
        seg = s[i:i + 400]
        assert "it.onName" in seg and "active ? it.onName : it.name" in seg, (
            "标签未按 active 在 onName/name 之间切换")


class TestPhoneLayoutThresholdAlignment:
    """★ 手机宽度阈值必须【低于官方实测的 358px】（2026-10-20）。

    背景：维护者反馈「其他用户看到一列，我们看到两列」。
    官方 App 手机宽度（容器 ≈358px）实测**全是多列**：
      · 快捷按钮  一行 4 个
      · 下方两卡  一行 2 个
      · 入口瓦片  一行 2 个
    ⇒ 阈值必须低于 358px，否则官方同宽度下反而被收窄。
    旧值 330px 让 358 落在阈值之下 ⇒ 就是「一列」的原因。
    """

    @staticmethod
    def _home_src() -> str:
        from pathlib import Path

        p = (Path(__file__).resolve().parent.parent / "custom_components"
             / "lixiang_auto" / "www" / "lixiang-cards" / "lixiang-app-home.js")
        return p.read_text(encoding="utf-8")

    def test_threshold_below_official_358(self):
        """★ 阈值必须 < 358px（官方实测宽度），否则与官方不一致。"""
        import re

        s = self._home_src()
        m = re.search(r"@container \(max-width: (\d+)px\)", s[s.find(".quick {"):])
        thresholds = [int(x) for x in re.findall(
            r"@container \(max-width: (\d+)px\)", s)]
        assert thresholds, "未找到任何断点"
        narrow = min(thresholds)
        assert narrow < 358, (
            f"最窄断点 {narrow}px 必须低于官方实测 358px，"
            f"否则官方同宽度下被误收成一列")

    def test_358px_keeps_multi_column(self):
        """★ 官方 358px 下三处都应保持多列（不被收窄）。"""
        s = self._home_src()
        narrow = min(int(x) for x in __import__("re").findall(
            r"@container \(max-width: (\d+)px\)", s))
        assert 358 > narrow, (
            f"358px（官方实测）不应命中 {narrow}px 断点，否则会收成一列")

    def test_no_330px_left(self):
        assert "max-width: 330px" not in self._home_src(), (
            "旧的 330px 阈值应已改为 340px（否则 358px 仍被收窄）")


class TestSceneEntryGating:
    """★ 情景模式入口按车型隐藏（2026-10-20 维护者反馈）。

    背景：ONE 车主看到车控卡上有「情景模式」入口，点进去只有 unknown。
    根因：
      · M 系 real-time-state 无场景字段 ⇒ scene_mode 实体不创建
      · M 系能力表无 version:scene
      · 而卡片入口区（entries）没有像 QUICK 那样的实体存在性门控
    """

    @staticmethod
    def _home_src() -> str:
        from pathlib import Path

        return (Path(__file__).resolve().parent.parent / "custom_components"
                / "lixiang_auto" / "www" / "lixiang-cards"
                / "lixiang-app-home.js").read_text(encoding="utf-8")

    def test_entry_starts_hidden(self):
        """入口默认 hidden，再由 JS 按实体存在性决定是否显示。"""
        s = self._home_src()
        assert 'id="e-scene" role="button" tabindex="0" hidden>' in s, (
            "情景模式入口应默认 hidden（避免无车型能力时闪现）")

    def test_gating_logic_exists(self):
        s = self._home_src()
        assert "_el.hidden = !_has" in s, "缺按实体存在性显示的逻辑"
        assert 'scene_mode' in s

    def test_gate_checks_entity_existence(self):
        """必须查实体是否存在，而不是硬编码车型名。"""
        s = self._home_src()
        assert '_eid("scene_mode")' in s, "应查 scene_mode 实体是否存在"
        assert 'M01' not in s.split('e-scene')[1][:600], "不应硬编码车型"
