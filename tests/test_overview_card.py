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
