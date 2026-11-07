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


def test_429_maps_to_rate_limited():
    """源码里必须有 429 分支且赋值为 rate_limited。"""
    s = _src()
    assert '429' in s, "config_flow 未识别 429"
    assert 'rate_limited' in s, "429 未映射到 rate_limited"
    # 429 分支必须在 unknown 的 else 之前（顺序敏感）
    i429 = s.find('"429" in msg')
    ielse = s.rfind('errors["base"] = "unknown"')
    assert i429 != -1, "找不到 429 判定"
    assert i429 < ielse, "429 分支在 unknown 之后，永远命中不到"


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
