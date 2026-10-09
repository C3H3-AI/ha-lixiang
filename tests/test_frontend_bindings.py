"""前端卡片「绑定 + 服务名」回归守卫（2026-10-09）。

背景（真事故，都是用户点不动的按钮）
------------------------------------
1) `lixiang-app-home` 首页「后视镜加热」绑到 `{any:["后视镜"], domain:"binary_sensor"}`：
   引擎的 `any:` 分支**忽略 domain**，于是命中只读的 `sensor.左后视镜`
   → 点击走 `homeassistant.toggle` 失败。
2) 首页「充电口盖」在 AUTO_BIND 里**根本没有字段**（只有只读的 `port_cover`）
   → 恒显示"尚未接入"。
3) 首页/空调页服务名写错：`cover.open` / `cover.close` / `switch.open`
   在 HA 里**不存在**（正确：`open_cover` / `close_cover` / `turn_on` / `turn_off`）
   → 「车窗」「尾门」「除雪除冰」按钮必然失败。
4) `ac_defrost` 规则写 `any:["除霜"]`，而实体名是「除雪除冰」
   → 命中只读的 `sensor.除霜模式`。
5) `btn_start` 找「远程启动」，而实体名是「授权驾驶」→ 设置页永远缺按钮。

本文件用两种手段守住：
  A. 静态：扫描所有卡片的 callService(域名, 服务名) —— 必须都在 HA 真实服务表内；
  B. 动态：在 Node 里真跑一遍自动发现引擎（tests/lx_bind_sim.js），
     用贴近真机的实体表断言首页 8 个快捷按钮的绑定结果。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "custom_components" / "lixiang_auto" / "www" / "lixiang-cards"
ENGINE = CARDS / "lixiang-auto-bind.js"
SIM = Path(__file__).resolve().parent / "lx_bind_sim.js"

#: HA 真实服务表（本项目用到的部分；来源：实机 GET /api/services）
#: 注意 cover / switch **没有** open / close —— 这正是踩过的坑。
ALLOWED_SERVICES = {
    "cover": {"open_cover", "close_cover", "toggle", "stop_cover"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "lock": {"lock", "unlock"},
    "button": {"press"},
    "select": {"select_option"},
    "number": {"set_value"},
    "fan": {"set_percentage", "turn_on", "turn_off", "toggle"},
    "climate": {"turn_on", "turn_off"},
    "automation": {"turn_on", "turn_off", "trigger"},
    "homeassistant": {"toggle", "turn_on", "turn_off"},
    "lixiang_auto": {
        "wakeup", "refresh", "dump_ability", "get_travel", "get_charge",
        "get_svm_photo", "create_task", "get_tasks", "update_task", "delete_task",
    },
}

#: 动态调用（callService(dom, svc)）允许的域名 —— svc 由 _on() 推导，只可能是 turn_on/turn_off
DYNAMIC_DOMAINS = {"switch", "fan", "climate", "input_boolean", "automation", "homeassistant"}


def _card_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(CARDS.glob("*.js"))}


def test_no_nonexistent_services_in_cards():
    """★ 卡片不得调用 HA 里不存在的服务（cover.open / switch.close 这类）。"""
    bad: list[str] = []
    for fname, src in _card_sources().items():
        for m in __import__("re").finditer(
            r'callService\(\s*"([a-z_]+)"\s*,\s*"([a-z_]+)"', src
        ):
            dom, svc = m.group(1), m.group(2)
            allowed = ALLOWED_SERVICES.get(dom)
            if allowed is None:
                bad.append(f"{fname}: callService(\"{dom}\", \"{svc}\") —— 未知域名")
            elif svc not in allowed:
                bad.append(
                    f"{fname}: callService(\"{dom}\", \"{svc}\") —— "
                    f"{dom} 域没有 {svc}（可用: {sorted(allowed)}）"
                )
    assert not bad, "卡片调用了不存在的服务：\n  " + "\n  ".join(bad)


def test_no_bare_open_close_service_names():
    """更直白的守卫：open/close 作为服务名出现就是错（HA 无此服务）。"""
    bad: list[str] = []
    for fname, src in _card_sources().items():
        for m in __import__("re").finditer(
            r'callService\([^)]*?"(open|close)"', src
        ):
            bad.append(f"{fname}: {m.group(0)}")
    assert not bad, (
        "出现 open/close 服务名（应为 open_cover/close_cover 或 turn_on/turn_off）：\n  "
        + "\n  ".join(bad)
    )


# ───────────────────────── B. 动态：真跑引擎 ─────────────────────────

def _entity(eid: str, name: str, device="dev1", platform="lixiang_auto",
            disabled=None, state="off") -> tuple[dict, dict]:
    ent = {
        "entity_id": eid,
        "original_name": name,
        "name": name,
        "platform": platform,
        "device_id": device,
        "disabled_by": disabled,
    }
    st = {"state": state, "attributes": {"friendly_name": name}}
    return ent, st


#: 贴近真机的实体表（含"诱饵"：只读同名词条，正是当初错绑的原因）
_LIVE = [
    ("lock.li_auto_l6_che_men_suo", "车锁", "locked"),
    ("cover.li_auto_l6_che_chuang", "车窗", "closed"),
    ("cover.li_auto_l6_wei_men", "尾门", "closed"),
    ("button.li_auto_l6_xun_che", "寻车", "unknown"),
    ("button.li_auto_l6_yuan_cheng_qi_dong", "授权驾驶", "unknown"),
    ("button.li_auto_l6_shan_deng", "闪灯", "unknown"),
    ("button.li_auto_l6_ming_di", "鸣笛", "unknown"),
    ("button.li_auto_l6_yuan_cheng_pai_zhao", "远程拍照", "unknown"),
    ("binary_sensor.li_auto_l6_che_liang_shou_quan", "车辆授权", "on"),
    # —— 后视镜：只读 sensor 是诱饵，控制实体是 switch ——
    ("sensor.li_auto_l6_zuo_hou_shi_jing", "左后视镜", "展开"),
    ("sensor.li_auto_l6_you_hou_shi_jing", "右后视镜", "展开"),
    ("switch.li_xiang_l6_hou_shi_jing_jia_re", "后视镜加热", "off"),
    # —— 充电口盖：只读 binary_sensor 是诱饵，控制实体是 switch「充电盖」——
    ("binary_sensor.li_auto_l6_chong_dian_kou_gai", "充电口盖", "off"),
    ("switch.li_xiang_l6_chong_dian_gai", "充电盖", "off"),
    # —— 空调：只读 sensor「除霜模式」是诱饵，实体名是「除雪除冰」——
    ("sensor.li_auto_l6_chu_shuang_mo_shi", "除霜模式", "关闭"),
    ("switch.li_auto_l6_kong_diao_chu_shuang", "除雪除冰", "off"),
    ("switch.li_auto_l6_kong_diao_kuai_su_zhi_leng", "空调快速制冷", "off"),
    ("switch.li_auto_l6_kong_diao_kuai_su_zhi_re", "空调快速制热", "off"),
    ("climate.li_auto_l6_kong_diao", "空调", "off"),
    ("switch.li_auto_l6_fang_xiang_pan_jia_re", "方向盘加热", "off"),
    ("switch.li_auto_l6_dian_chi_bao_wen", "电池保温", "off"),
    ("switch.li_auto_l6_shao_bing_mo_shi", "哨兵模式", "off"),
    ("sensor.li_auto_l6_dian_chi_dian_liang", "电池电量", "89"),
]

#: 首页 8 个快捷按钮（QUICK）+ 空调页 5 个模式按钮的期望绑定
EXPECTED_BINDINGS = {
    "lock": "lock.li_auto_l6_che_men_suo",
    "window": "cover.li_auto_l6_che_chuang",
    "trunk": "cover.li_auto_l6_wei_men",
    "auth": "button.li_auto_l6_yuan_cheng_qi_dong",
    "auth_state": "binary_sensor.li_auto_l6_che_liang_shou_quan",
    "find": "button.li_auto_l6_xun_che",
    "mirror": "switch.li_xiang_l6_hou_shi_jing_jia_re",
    "port": "switch.li_xiang_l6_chong_dian_gai",
    "ac": "climate.li_auto_l6_kong_diao",
    "ac_fast_cold": "switch.li_auto_l6_kong_diao_kuai_su_zhi_leng",
    "ac_fast_hot": "switch.li_auto_l6_kong_diao_kuai_su_zhi_re",
    "ac_defrost": "switch.li_auto_l6_kong_diao_chu_shuang",
    "steer_heat": "switch.li_auto_l6_fang_xiang_pan_jia_re",
    "sentry": "switch.li_auto_l6_shao_bing_mo_shi",
    "batt_warm": "switch.li_auto_l6_dian_chi_bao_wen",
    "btn_find": "button.li_auto_l6_xun_che",
    "btn_start": "button.li_auto_l6_yuan_cheng_qi_dong",
    "btn_flash": "button.li_auto_l6_shan_deng",
    "btn_horn": "button.li_auto_l6_ming_di",
    "btn_photo": "button.li_auto_l6_yuan_cheng_pai_zhao",
    "port_cover": "binary_sensor.li_auto_l6_chong_dian_kou_gai",
}


def _run_sim(tmp_path: Path) -> dict:
    entities, states = {}, {}
    for eid, name, st in _LIVE:
        ent, state = _entity(eid, name, state=st)
        entities[eid] = ent
        states[eid] = state
    # 真实里被集成本身禁用的实体不会有状态（`_pool()` 会跳过）
    devices = {"dev1": {"name": "理想L6", "model": "理想L6 Pro",
                        "identifiers": [["lixiang_auto", "TESTVIN"]]}}
    payload = {"entities": entities, "devices": devices, "states": states}
    f = tmp_path / "live.json"
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    out = subprocess.run(
        ["node", str(SIM), str(f), str(ENGINE)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert out.returncode == 0, f"仿真失败：{out.stderr[:800]}"
    return json.loads(out.stdout)


#: 卡片内部工具方法（调用前必须在同文件里定义过）
HELPERS = ["_toast", "_a11y", "_eid", "_eidIn", "_st", "_on", "_txt", "_num", "_img", "_online"]


def test_card_helpers_are_defined():
    """★ 卡片调用的内部工具方法必须在同文件定义过。

    真事故：新增「充电口盖」交互时调用了 `this._toast(...)`，
    而该卡片原本既没有 `_toast` 方法也没有 `.toast` 节点 →
    运行期静默抛 "this._toast is not a function"，提示语永远不显示
    （浏览器 DOM 仿真时才暴露）。静态查子串查不出这类问题，
    必须「有调用就必须有定义」。
    """
    bad: list[str] = []
    for fname, src in _card_sources().items():
        for h in HELPERS:
            used = f"this.{h}(" in src
            if not used:
                continue
            defined = (f"{h}(" in src.replace(f"this.{h}(", "this._CALL_")) or \
                      f"this.{h} =" in src
            if not defined:
                bad.append(f"{fname}: 调用了 this.{h}() 但没有定义")
    assert not bad, "卡片缺少内部方法定义：\n  " + "\n  ".join(bad)


def test_toast_element_matches_toast_method():
    """调用了 _toast 的卡片，必须有 `.toast` 节点（否则提示无处显示）。"""
    bad = [
        fname for fname, src in _card_sources().items()
        if "this._toast(" in src and 'class="toast"' not in src
    ]
    assert not bad, f"以下卡片调用了 _toast 但没有 .toast 节点：{bad}"


NODE_OK = shutil.which("node") is not None


def test_quick_keys_have_binding_or_are_documented_unsupported():
    """★ 首页每个快捷按钮，要么在 AUTO_BIND 里有可控制字段，要么明确"未实现"。

    「直线召唤」属于后者：车辆能力表（features_supported.parking）支持，
    但集成尚未实现该命令（走 JOB 通道），因此**故意**不给绑定字段，
    卡片会置灰并提示原因。
    """
    src = ENGINE.read_text(encoding="utf-8")
    quick = __import__("re").findall(
        r'\{\s*key:"([a-z_]+)"', 
        (CARDS / "lixiang-app-home.js").read_text(encoding="utf-8"),
    )
    assert quick, "没解析到首页 QUICK 按钮"
    unsupported = {"summon"}
    missing = [
        k for k in quick
        if k not in unsupported and not __import__("re").search(rf"\n\s+{k}:\s*\{{", src)
    ]
    assert not missing, (
        f"以下快捷按钮在 AUTO_BIND 里没有绑定字段（会显示'尚未接入'）：{missing}"
    )
    for k in unsupported:
        assert not __import__("re").search(rf"\n\s+{k}:\s*\{{", src), (
            f"{k} 已实现？请从 unsupported 集合移除，并补上绑定与卡片交互"
        )


@pytest.mark.skipif(not NODE_OK, reason="需要 node 才能跑引擎仿真")
def test_quick_buttons_bind_to_controllable_entities(tmp_path):
    """★ 首页快捷按钮 / 空调页模式按钮，必须绑到【可控制】的实体上。"""
    res = _run_sim(tmp_path)
    resolved = res["resolved"]
    wrong = {
        f: (resolved.get(f), want)
        for f, want in EXPECTED_BINDINGS.items()
        if resolved.get(f) != want
    }
    assert not wrong, (
        "绑定结果与预期不符（多半又绑到了只读实体/名字写错）：\n  "
        + "\n  ".join(f"{f}: {got} ≠ {want}" for f, (got, want) in wrong.items())
    )


@pytest.mark.skipif(not NODE_OK, reason="需要 node 才能跑引擎仿真")
def test_no_field_resolves_outside_declared_domain(tmp_path):
    """★ 规则声明了 domain，就必须落在该 domain —— any: 分支也不例外。"""
    res = _run_sim(tmp_path)
    assert not res["domainViolations"], (
        "字段解析出了声明域之外的实体（只读/错绑）："
        + json.dumps(res["domainViolations"], ensure_ascii=False)
    )


@pytest.mark.skipif(not NODE_OK, reason="需要 node 才能跑引擎仿真")
def test_quick_and_mode_fields_all_resolve(tmp_path):
    """首页快捷按钮 + 空调页模式按钮涉及的字段，一个都不能落空。"""
    res = _run_sim(tmp_path)
    missing = [f for f in EXPECTED_BINDINGS if not res["resolved"].get(f)]
    assert not missing, f"以下字段未匹配到实体：{missing}"
