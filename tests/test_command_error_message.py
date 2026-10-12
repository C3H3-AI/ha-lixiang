"""车控失败消息 —— 服务端 msg 透传（2026-10-11）。

问题
----
`li_api.send_command()` 在 `pushState=7`（执行失败）时这样拼消息：

```python
f"... resultCode={rc_err} msg={result.get('resultMsg')}"
```

★ 但服务端返回的键是 **`msg`**，不是 `resultMsg` → `resultMsg` 恒为 `None`
→ **中文原因整段丢失**。用户只看到裸的：

```
命令执行失败 (rmCtrl): pushState=7 resultCode=-4 msg=None
```

而服务端其实明明白白说了：**"车辆已启动，不支持远程控制"**（与 App 提示一致）。

实测证据（2026-10-11 真车，理想 L6；VIN 不写入仓库）
------------------------------------------------------
| 状态 | 命令 | resultCode | 服务端 msg |
|---|---|---|---|
| 已熄火 | 折叠 ON / OFF | — | `pushState=5` ✅ |
| READY（待启动）| 寻车/折叠/空调/充电盖 | **-4** | 车辆已启动，不支持远程控制 |
| READY | 解锁（有人）| **-51** | 闭锁失败，主驾有人，请稍后再试 |
| 通电 | 空调（除 `dfstSw` 外全部）| **-1** | 执行失败 |
| 通电 | 前风挡除霜 `dfstSw` | — | `pushState=5` ✅ |

顺带结论：**READY 状态下车控同样被拒** —— 所以"车辆已启动"应理解为
「未熄火（含待启动）」。

本测试
------
1. 消息必须包含服务端 `msg`（回归防护：防止又改回 `resultMsg`）
2. 没有 msg 时回落到错误码人话表
3. 两者都没有时只给前缀（**不编造**）
4. 错误码表只收录**实测**见过的码（未实测的不猜）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LI_API = ROOT / "custom_components" / "lixiang_auto" / "li_api.py"


def _src() -> str:
    return LI_API.read_text(encoding="utf-8")


def _failure_block() -> str:
    """`pushState=7` 时抛异常的那段。"""
    src = _src()
    i = src.index("命令执行失败 ({command_key})")
    return src[max(0, i - 400): i + 400]


class TestServerMsgPassthrough:
    def test_uses_msg_key_first(self):
        """★ 核心回归：必须优先取服务端的 `msg`。"""
        blk = _failure_block()
        assert 'result.get("msg")' in blk, "必须读服务端的 msg 键"
        assert blk.index('result.get("msg")') < blk.index('result.get("resultMsg")'), \
            "msg 应优先于 resultMsg"

    def test_no_resultmsg_only(self):
        """不能只用 resultMsg（那是导致中文丢失的根因）。"""
        blk = _failure_block()
        # 允许作为**兜底**出现，但不能是唯一来源
        assert blk.count('result.get("resultMsg")') <= 1

    def test_uses_hint_table_fallback(self):
        blk = _failure_block()
        assert "RESULT_CODE_HINTS.get(rc_err)" in blk, \
            "服务端没给 msg 时应回落到已知错误码的人话"

    def test_message_contains_server_text(self):
        """★ 端到端语义：消息里必须能看到服务端的中文。"""
        blk = _failure_block()
        # 消息拼接用的是 _msg 变量
        assert "msg={_msg}" in blk or 'msg={_msg}' in blk, "应把取到的 msg 拼进消息"


class TestResultCodeHints:
    def _table(self) -> dict:
        src = _src()
        i = src.index("RESULT_CODE_HINTS")
        j = src.index("}", i)
        body = src[i:j]
        return {int(m.group(1)): m.group(2).strip()
                for m in re.finditer(r'(-?\d+)\s*:\s*"([^"]+)"', body)}

    def test_known_codes(self):
        t = self._table()
        # ★ 只收录实测见过的
        assert t[-4] == "车辆已启动，不支持远程控制", "缺 -4 的实测文案"
        assert t[-51] == "闭锁失败，主驾有人，请稍后再试", "缺 -51 的实测文案"
        # ★ 2026-10-12 实测：cpCtrl 关闭充电口盖时 pushState=7 resultCode=-2
        #   failReason="set signal err!"（dump 全部字段确认服务端没给中文原因）
        assert -2 in t, "缺 -2（2026-10-12 实测）"

    def test_no_guessy_codes(self):
        """未实测的错误码不应被臆测 —— 表里每条都要有实测来源。"""
        t = self._table()
        allowed = {-1, -3, -4, -51, -2}      # 实测集合（-2 于 2026-10-12 实测）
        extra = set(t) - allowed
        assert not extra, (
            f"错误码表含未实测的条目 {sorted(extra)} —— "
            "只收录实测见过的，未实测的让服务端 msg 说话")

    def test_table_is_documented(self):
        src = _src()
        i = src.index("RESULT_CODE_HINTS")
        assert "实测" in src[max(0, i - 200):i], "错误码表必须标注来源（实测）"


class TestNoFabrication:
    def test_no_fake_message_when_absent(self):
        """★ 服务端既没 msg、码也未知 → 只给前缀，**不编造原因**。"""
        blk = _failure_block()
        assert 'if _msg else _head' in blk or "if _msg else" in blk, \
            "两者都没有时必须只输出前缀（不能瞎猜原因）"

    def test_timeout_path_also_fixed(self):
        """超时那条日志也要用 msg（此前同样取错键）。"""
        src = _src()
        i = src.index("车控命令未在超时内进入终态")
        blk = src[i:i + 500]
        assert 'result.get("msg")' in blk, "超时日志也应读 msg"


class TestPreserved:
    def test_structural_fields_kept(self):
        """pushState / resultCode / requestId 仍要保留（排障要用）。"""
        blk = _failure_block()
        assert "pushState={ps}" in blk and "resultCode={rc_err}" in blk
        assert "request_id=request_id" in blk

    def test_code_compiles(self):
        import py_compile
        py_compile.compile(str(LI_API), doraise=True)

    def test_2009_path_untouched(self):
        """2009（通道不支持）的既有提示不能被改坏。"""
        src = _src()
        assert "HTTP 车控接口不支持" in src