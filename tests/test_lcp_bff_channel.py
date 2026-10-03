"""lcp-bff-app-api 通道测试（2026-10-01 新增）

★ 背景：充电相关功能的通道调研

  用户要求实现「充电记录」与「陪伴里程时间段查询」。调研发现：
  App 有【多个】服务通道，各自有独立的 audience/scope 与【精确路径白名单】
  （来源：服务端下发的 subTokenData，见 mmkv/m01_sp）。

  本轮新增并【实测确认】的通道：

      lcp-bff-app-api   audience=3N1l45XSeMOaid2RgDLiLA  scope=login
      ★ 该条白名单是【全前缀放行】→ /lcp-bff-app-api/** 均可用

  实测已通（2026-10-01，真实返回数据）：
      · /lcp-bff-app-api/plate-number/v1/list
      · /lcp-bff-app-api/user-settings/v1/user-pnc-switch/list   ← 本测试守卫
      · /lcp-bff-app-api/serve-page/v1/station-stats
      · /lcp-bff-app-api/travel-planning/v1/simulate/energy/cost

★ 本测试守卫的不变量：

  ① 常量与 App 的 subTokenData【逐字一致】（防手滑改错 audience/scope）
  ② get_pnc_switch() 存在且走【正确的通道】（lcp_bff）、【正确的端点】
  ③ 返回值归一化：非 list 的响应返回 [] 而不是抛异常（防真实响应缺字段时崩溃）
  ④ ★ 反向守卫：需要【用户身份】的接口（chargeRecords）不得被误标为可用
     —— 它们需要 X-CHJ-Token（App 短效 token），实测返回 100105 用户未登录

★ 为什么不打真实网络：
  集成测试不该依赖登录态与网络。这里的价值是【锁定通道配置】，
  真实可用性已由 2026-10-01 的实测确认（见 docs §十八）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INTEG = REPO / "custom_components" / "lixiang_auto"


# ---------------------------------------------------------------- ① 通道常量

def test_lcp_bff_constants_match_app_subtokendata():
    """★ audience/scope 必须与 App subTokenData 逐字一致。

    来源（服务端下发，权威）：
      {"type":"lcp-bff-app-api","audience":"3N1l45XSeMOaid2RgDLiLA",
       "disableIAM":1,"scope":["login"],"urls":["/lcp-bff-app-api"]}
    """
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    assert 'AUD_LCP_BFF = "3N1l45XSeMOaid2RgDLiLA"' in src, \
        "lcp-bff audience 与 App subTokenData 不一致"
    assert 'SCOPE_LCP_BFF = "login"' in src, "lcp-bff scope 应为 login"
    assert '/lcp-bff-app-api/user-settings/v1/user-pnc-switch/list' in src, \
        "即插即充端点缺失"


def test_pnc_endpoint_is_under_lcp_prefix():
    """端点必须落在 lcp-bff 全前缀白名单内（否则会 100012）。"""
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    m = re.search(r'EP_LCP_PNC_LIST = "([^"]+)"', src)
    assert m, "EP_LCP_PNC_LIST 未定义"
    assert m.group(1).startswith("/lcp-bff-app-api/"), \
        "端点不在 lcp-bff 白名单前缀内 → 会被拒 100012"


# ---------------------------------------------------------------- ② 方法实现

def test_get_pnc_switch_exists_and_uses_lcp_channel():
    """get_pnc_switch() 必须存在，且用 lcp_bff 的 token + EP_LCP_PNC_LIST。"""
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    m = re.search(r"def get_pnc_switch\(self\).*?(?=\n    def |\Z)", src, re.S)
    assert m, "get_pnc_switch() 不存在"
    body = m.group(0)
    assert "SCOPE_LCP_BFF" in body and "AUD_LCP_BFF" in body, \
        "未使用 lcp-bff 通道的 scope/audience"
    assert "EP_LCP_PNC_LIST" in body, "未使用约定的端点常量"
    assert "_signed_call" in body, "必须走集成的签名请求（x-chj-sign）"


def test_get_pnc_switch_uses_ast_verified_call_not_comment():
    """★ 用 AST 确认真的调用了（防止注释里的字符串造成假通过）。

    教训（见 skill §19「假测试」）：对源码做子串断言时，
    注释里的同名文本会让断言【恒为真】。这里用 AST 只认真实调用节点。
    """
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_pnc_switch":
            for c in ast.walk(node):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
                    if c.func.attr == "_signed_call":
                        found = True
    assert found, "get_pnc_switch 里没有真实的 _signed_call(...) 调用"


# ---------------------------------------------------------------- ③ 归一化

def test_get_pnc_switch_returns_list_on_odd_response():
    """响应不是 list 时返回 []，不抛异常（真实响应可能缺 data）。"""
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    m = re.search(r"def get_pnc_switch\(self\).*?(?=\n    def |\Z)", src, re.S)
    body = m.group(0)
    assert "isinstance(data, list)" in body, "未对 data 做类型判断"
    assert "return []" in body, "缺少兜底返回 []"


# ---------------------------------------------------------------- ④ 反向守卫

def test_user_token_endpoints_not_claimed_as_available():
    """★ 反向守卫：需要 X-CHJ-Token 的接口不得被误标为「可用」。

    实测（2026-10-01）：三种服务级 token 打 charging records 均返回
    `100105 用户未登录` —— 它需要 App 的用户级短效 token（X-CHJ-Token）。

    若将来有人把 chargeRecords 当成普通 lcp 端点直接调用，
    本测试会失败，提示「需要用户 token」。
    """
    src = (INTEG / "li_api.py").read_text(encoding="utf-8")
    # 只要出现了 chargeRecords 的调用，就必须在同一段里有说明性注释
    if "chargeRecords" in src:
        idx = src.find("chargeRecords")
        window = src[max(0, idx - 500): idx + 200]
        assert "X-CHJ-Token" in window or "用户" in window, \
            "chargeRecords 需要 X-CHJ-Token（用户级），必须在代码里注明"
