"""后视镜折叠 / 前排通风控制 —— 回归测试（2026-10-11）。

背景
----
App 侧这两项**能力表里没有开关**（认为全系标配），但必须做**车型匹配**，
否则不支持的车会出现"点了没反应"的实体。本实现用两条依据：

  ① `__RM_FOLD__`（后视镜折叠）：**状态信号存在性**门控
     —— 车机上报 `mirror_left`/`mirror_right`（LRearMirro/RRearMirro）才创建；
        手动折叠镜的老车自然不出现。
  ② `__ABAT_VENT__`（前排通风）：用户确认**全系都有**且无状态回读 → 一律创建。

cmdData 均为 APK 反编译实证（8.27.0 `XVehicleJobHelper`）：
  · 折叠：cmdKey=`rmCtrl` `{"ctrlType":"FOLD","ctrlValue":"ON"(展开)/"OFF"(收起)}`
  · 通风：cmdKey=`ssCtrl` `{"ctrlType":"ABS","fPos":2,"rPos":1}`（App 默认档位）

★ 状态语义的关键修正（同一轮发现的另一个 bug）：
  裸值 **1 = 收起**（App 符号 `RearviewMirrorFolded` + 2026-10-11 实测），
  开关 **on = 收起**；与后视镜加热不同，别混。
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
SWITCH = CC / "switch.py"
CONST = CC / "const.py"


def _src() -> str:
    return SWITCH.read_text(encoding="utf-8")


def _no_comments(text: str) -> str:
    """去掉【整行注释】后再断言。

    ★ 为什么要这一步（技能 §19「注释替代码背书」）：
      本文件最初用 `'"ABS"' in blk` 断言 cmdData，结果把 `ctrlType=ABS` 改成
      `SENTRY` 的变异**照样通过** —— 因为上方注释里也写着 ABS。
      断言必须只落在真正的代码上。
      （用逐行剔除而非 tokenize：截取的是函数中途片段，缩进不完整会让 tokenize 报错。）
    """
    return "\n".join(
        ln for ln in text.splitlines()
        if not ln.strip().startswith("#")
    )


def _state_gate():
    """把 _state_signal_present 抽出来单测（它不依赖 HA）。"""
    tree = ast.parse(_src())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_state_signal_present":
            ns: dict = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<g>", "exec"), ns)
            return ns["_state_signal_present"]
    raise AssertionError("找不到 _state_signal_present")


class _Coord:
    def __init__(self, vss):
        self.data = {"vss": vss}


class TestMirrorFoldState:
    """★ on = 收起（folded）；裸值 1 = 收起。"""

    def test_one_is_folded(self):
        s = _src()
        i = s.index('elif self._control_type == "__RM_FOLD__":')   # is_on 里的状态分支
        blk = _no_comments(s[i:i + 1200])
        assert '== 1' in blk, "折叠判定必须按『1=收起』"
        assert 'any(_vals)' in blk or 'any(' in blk, "任一镜子收起即视为收起"

    def test_fold_switch_exists_with_right_semantics(self):
        s = _src()
        assert '("mirror_fold", "后视镜折叠"' in s, "缺少后视镜折叠开关"
        assert '"on = 收起' in s or 'on = 收起' in s, "诊断属性未标注 on=收起"

    def test_fold_cmd_data_from_apk(self):
        s = _src()
        i = s.rindex('elif self._control_type == "__RM_FOLD__":')   # _send 里的下发分支
        blk = _no_comments(s[i:i + 700])
        assert '"rmCtrl"' in blk
        assert '"FOLD"' in blk
        # on(收起) → App 的 ctrlValue 是 OFF（照抄 App 原值，不自创语义）
        assert '"ctrlValue": "OFF" if level != 0 else "ON"' in blk


class TestFrontVent:
    def test_switch_registered(self):
        assert '("front_vent", "前排通风"' in _src()

    def test_cmd_data_from_apk(self):
        s = _src()
        i = s.rindex('elif self._control_type == "__ABAT_VENT__":')  # _send 里的下发分支
        blk = _no_comments(s[i:i + 700])
        assert '"ssCtrl"' in blk
        # ★ 必须锁【两个分支】的 ctrlType：只断一处会被另一处的同名串蒙过去
        #   （2026-10-11 实测：把"开"分支改成 SENTRY 后测试仍绿，因为"关"分支里还有 ABS）
        assert blk.count('"ctrlType": "ABS"') == 2, (
            f"开/关两个分支都必须是 ctrlType=ABS，实际 {blk.count(chr(34)+'ctrlType'+chr(34)+': '+chr(34)+'ABS'+chr(34))} 处")
        assert '"fPos": 2, "rPos": 1' in blk, "App 默认档位应为 fPos=2 / rPos=1"
        assert '"fPos": 0, "rPos": 0' in blk, "关闭档位应为 fPos=0 / rPos=0"

    def test_no_state_gating(self):
        """全系都有 → 不因状态缺失而被门控掉（state_key=None → 放行）。"""
        assert '("front_vent", "前排通风", "mdi:air-conditioner",\n     None, "__ABAT_VENT__", None)' \
            in _src().replace("\r", "") or "None, \"__ABAT_VENT__\"" in _src()


class TestModelMatching:
    def test_state_presence_gate(self):
        gate = _state_gate()
        # 有值 → 该车支持
        assert gate(_Coord({"mirror_left": {"value": 1}}), "mirror_left") is True
        # 无该信号 → 不支持（手动镜老车）
        assert gate(_Coord({}), "mirror_left") is False
        # value=None 也算不支持
        assert gate(_Coord({"mirror_left": {"value": None}}), "mirror_left") is False
        # 无状态键的功能（如前排通风）→ 一律放行
        assert gate(_Coord({}), None) is True

    def test_gate_applied_in_setup(self):
        s = _src()
        i = s.index("spec for spec in SWITCHES")
        blk = s[i:i + 400]
        assert "_state_signal_present(coordinator, spec[3])" in blk, (
            "setup 必须做状态存在性门控（能力表没有该开关时的车型匹配）")


class TestCommandSafety:
    def test_rmctrl_is_long_running(self):
        """折叠与加热共用 rmCtrl → 必须走长命令通道（jobExpire 900s）。"""
        s = (CONST.parent / "li_api.py").read_text(encoding="utf-8")
        i = s.index("LONG_RUNNING_CMD_KEYS")
        blk = s[i:i + 400]
        assert "rmCtrl" in blk, "rmCtrl 应在长命令列表里（否则 30s 超时会失败）"

    def test_both_controls_marked_unverified(self):
        """未实测的控件必须显式标注（禁止让用户以为已验证）。"""
        s = _src()
        assert s.count('"实车验证": "⚠️ 待验证') >= 2, "两个新控件都要标注待实车验证"
