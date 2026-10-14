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
        i = s.find("_loadArt()")
        assert i > 0
        assert "if (this._config.image) return" in s[i:i + 300], "config.image 应优先且不被覆盖"

    def test_failure_keeps_layout(self):
        """接口失败不得出现破图（保持空 src）。"""
        s = _strip_comments(_src())
        i = s.find("_loadArt()")
        seg = s[i:i + 700]
        assert "catch" in seg, "取车图无异常保护"


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
        #   （车主截图证实：他手机上还是一行 2 个）→ 阈值再降到 330px。
        for thr in (400,):
            seg = s.find("@container (max-width: %dpx)" % thr)
            if seg > 0:
                assert ".quick { grid-template-columns: repeat(2" not in s[seg:seg + 200], (
                    "≤%dpx 段里仍有快捷按钮 2 列 —— 手机宽度会被误伤" % thr)
        j = s.find("@container (max-width: 330px)")
        assert j > 0, "缺 ≤330px 的窄屏段（快捷按钮 2 列应在这里）"
        assert ".quick { grid-template-columns: repeat(2" in s[j:j + 200], "≤330px 段里没有 2 列规则"

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
        """★ 车主："授权驾驶为什么一直显示开着" → 对照官方 App 车控页截图修正。

        官方那里第 4 个按钮在已授权时**标签变成「已授权」+ 实心圆**，未授权时是「授权驾驶」。
        所以状态要保留，但**标签必须跟着变** —— 只高亮不改标签，用户看到的就是
        "授权驾驶一直开着"。
        """
        s = self._src()
        i = s.find('{ key:"auth"')
        assert i > 0
        entry = s[i:s.find("}", i) + 1]
        assert 'stateField:"auth_state"' in entry, "auth 应保留状态实体（用于显示已授权）"
        assert 'onName:"已授权"' in entry, "缺 onName：授权后标签不会变成「已授权」"

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
        现在：≤480 一律不收；只在极窄 ≤330px 才收。
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
        # 极窄兜底必须齐
        j = s.find("@container (max-width: 330px)")
        assert j > 0
        tail = s[j:j + 400]
        for frag in (".quick { grid-template-columns: repeat(2", ".row2 { grid-template-columns: minmax(0,1fr)",
                     ".entries { grid-template-columns: minmax(0,1fr)"):
            assert frag in tail, f"≤330px 段缺兜底：{frag}"

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
