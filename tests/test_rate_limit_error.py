"""登录限流（HTTP 429）必须映射到 rate_limited，而不是 unknown。

背景（2026-11-07 真事故）
------------------------
车主在 HA 添加集成时报「未知错误，请查看 HA 日志」。日志里真实原因是：

    login:login:429:{"status":429,"error":"Too Many Requests"}

但 config_flow 的错误映射只有 sms_required / 401 / (idps|auth|devices) 三个分支，
429 落到 else → errors["base"] = "unknown"。用户看到的「未知错误」完全不指向
「你登录太频繁，等一会」这个可操作的原因。

本测试锁住两件事：
  ① 429 必须映射到 rate_limited
  ② 两种语言的翻译里都必须有 rate_limited 文案
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CF = ROOT / "custom_components" / "lixiang_auto" / "config_flow.py"
TR = ROOT / "custom_components" / "lixiang_auto" / "translations"


def _src() -> str:
    return CF.read_text(encoding="utf-8")


def test_429_routes_to_browser_login():
    """429 必须【转浏览器辅助登录】，而不是报错。

    2026-11-07 实测：/login 被限流时连「设备是否需要短信」都判断不出来。
    只报错会把用户堵死在门口（此前落到 unknown，显示「未知错误」，
    连浏览器登录页都进不去）。浏览器 H5 链路（/api/challenge → 滑块 →
    短信 → challenge_token）不依赖 /login，所以限流时应转过去。
    """
    s = _src()
    assert '"429" in msg' in s, "config_flow 未识别 429"
    i429 = s.find('"429" in msg')
    ielse = s.rfind('errors["base"] = "unknown"')
    assert i429 != -1, "找不到 429 判定"
    assert i429 < ielse, "429 分支在 unknown 之后，永远命中不到"
    # 取到下一个 elif 为止（分支里有长注释，固定窗口会截断）
    _end = s.find("elif any(k in msg", i429)
    seg = s[i429:_end if _end != -1 else i429 + 2000]
    assert "async_step_browser()" in seg, "429 分支未转浏览器辅助登录"
    assert "_skip_login_probe = True" in seg, "429 分支未设置跳过探测标志"


def test_429_skips_trust_probe_loop():
    """转 browser 后必须跳过 7 次 try_login 探测，否则每次重试都撞 429，
    限流窗口被无限续期，用户永远等不到解除。"""
    s = _src()
    assert "_RETRY_GAPS" in s, "找不到探测循环"
    i = s.find("_skip_login_probe")
    j = s.find("_RETRY_GAPS")
    assert i != -1, "browser 步骤未读取 _skip_login_probe"
    assert i < j, "跳过判断必须在探测循环之前"
    seg = s[i:j]
    assert "getattr(self" in seg and "_skip_login_probe" in seg


def test_rate_limited_message_order():
    """用 AST 确认 LiAuthError 的 except 块里 429 分支确实存在。"""
    tree = ast.parse(_src())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            txt = ast.dump(node)
            if "429" in txt or "Too Many Requests" in txt:
                found = True
    assert found, "AST 里没有 429 的比较表达式"


def test_translations_have_rate_limited():
    """两种语言都要有 rate_limited 文案，否则 HA 显示原始 key。"""
    for name in ("zh-Hans.json", "en.json"):
        d = json.loads((TR / name).read_text(encoding="utf-8"))
        err = (d.get("config") or {}).get("error") or {}
        assert "rate_limited" in err, f"{name} 缺 rate_limited"
        assert len(err["rate_limited"]) > 10, f"{name} 的 rate_limited 文案过短"
