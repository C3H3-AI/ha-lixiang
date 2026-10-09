# -*- coding: utf-8
"""车主专属功能的角色守卫（2026-10-09）。

背景：服务端按【账号角色】限制两项能力（实测：家人账号拿不到）：
  · 任务大师（task-master）
  · 充电记录 / 充电量（chargeRecords / monthlyStatistics）

若不加守卫，家人账号会陷入「服务端拒绝 → 60s / 10min 重试 → 无限刷屏」，
而用户改不了（属服务端限制，不是配置问题）。

守卫要求：
  ① 不发起请求（非车主直接过滤/跳过）
  ② 给用户可读原因（不是 401 / 100105 这类"看起来可修复"的错误）
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CC = _ROOT / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (_CC / name).read_text(encoding="utf-8")


def _func_block(src: str, name: str) -> str:
    i = src.find(f"def {name}(")
    assert i > 0, f"缺少 {name}"
    j = src.find("\n    def ", i + 10)
    j2 = src.find("\n    async def ", i + 10)
    if j > 0 and (j2 < 0 or j < j2):
        return src[i:j]
    if j2 > 0:
        return src[i:j2]
    return src[i:i + 2000]


class TestOwnerOnlyGuard:
    def test_is_non_owner_helper_exists(self):
        """必须有角色判定助手，且【探测失败时放行】（不误伤车主）。"""
        s = _src("__init__.py")
        assert "def _is_non_owner(" in s, "缺少 _is_non_owner"
        blk = _func_block(s, "_is_non_owner")
        # 异常路径必须 return False（放行），不能 return True（误伤）
        tail = blk.split("_is_non_owner(")[-1] if "_is_non_owner(" in blk else blk
        assert "except Exception" in blk and "return False" in blk, (
            "_is_non_owner 异常路径必须放行（返回 False），避免角色探测失败误伤车主")
        # return False 必须出现在 except 之后（而非只在正常路径）
        exc_i = blk.find("except Exception")
        assert exc_i > 0 and "return False" in blk[exc_i:], (
            "except 分支必须 return False（放行），否则角色探测失败会误伤车主账号")
        # 必须用 vehicle_role 的角色判定
        assert "relation_of" in blk and "REL_OWNER" in blk, "未基于 relationOf/REL_OWNER 判定"

    def test_task_entries_filters_non_owner(self):
        """★ 任务大师的公共入口必须过滤非车主（覆盖 4 个服务）。"""
        blk = _func_block(_src("__init__.py"), "_li_task_entries")
        assert "_is_non_owner(" in blk, "_li_task_entries 未做角色过滤"
        assert "continue" in blk.split("_is_non_owner(")[1][:200], "过滤后应 continue 跳过"

    def test_coordinator_skips_owner_only(self):
        """★ coordinator 必须对两项车主专属能力加守卫（不再发请求）。"""
        s = _src("coordinator.py")
        assert "def _owner_only_skip(" in s, "缺少 _owner_only_skip 守卫"
        # 任务大师采集点
        i_task = s.find("get_tasks")
        assert i_task > 0
        blk_task = s[max(0, i_task-1500):i_task]
        assert "_owner_only_skip" in blk_task, "任务大师采集点未加守卫（会无限重试）"
        # 充电采集点
        i_chg = s.find("get_charge_total_kwh")
        assert i_chg > 0
        blk_chg = s[max(0, i_chg-1500):i_chg]
        assert "_owner_only_skip" in blk_chg, "充电量采集点未加守卫（会 10min 循环失败）"

    def test_services_give_readable_reason(self):
        """★ 4 个任务服务 + 充电服务，空结果必须给可读原因。"""
        s = _src("__init__.py")
        assert "_owner_only_hint" in s, "缺少 _owner_only_hint（区分非车主 vs 未配置）"
        blk = _func_block(s, "_owner_only_hint")
        assert "_OWNER_ONLY_NOTICE" in blk, "_owner_only_hint 未返回车主专属文案"
        assert "未找到 lixiang_auto 配置项" in blk, "_owner_only_hint 应保留未配置时的兜底文案"
        # 充电服务也要用
        i = s.find("async def _handle_get_charge(call)")
        j = s.find("\n    async def ", i+10)
        body = s[i:j]
        assert "_is_non_owner(" in body, "充电服务未做角色守卫"

    def test_notice_is_user_readable(self):
        """文案必须说明是服务端限制（用户改不了），而非配置错误。"""
        s = _src("__init__.py")
        assert "_OWNER_ONLY_NOTICE" in s
        m = re.search(r'_OWNER_ONLY_NOTICE\s*=\s*"([^"]+)"', s)
        assert m, "未找到 _OWNER_ONLY_NOTICE 定义"
        txt = m.group(1)
        assert "车主" in txt, "文案应说明仅车主可用"
        assert "服务端" in txt or "角色" in txt, "文案应说明是服务端限制（避免用户瞎查配置）"
        # 不得泄漏内部实现
        assert not re.search(r"scope|token|401|100105", txt), f"文案泄漏内部细节: {txt}"


class TestOwnerOnlyBehaviour:
    """行为级验证：用【App 真实字段形态】驱动 _is_non_owner。"""

    @staticmethod
    def _load():
        import ast
        import types as _t
        import sys
        cc = _CC
        pkg = _t.ModuleType("lx"); pkg.__path__ = [str(cc)]
        vr = _t.ModuleType("lx.vehicle_role")
        exec(compile(ast.parse((cc / "vehicle_role.py").read_text(encoding="utf-8")),
                 "<vr>", "exec"), vr.__dict__)
        pkg.vehicle_role = vr
        sys.modules["lx"] = pkg
        sys.modules["lx.vehicle_role"] = vr
        fn = next(n for n in ast.parse((cc / "__init__.py").read_text(encoding="utf-8")).body
                  if isinstance(n, ast.FunctionDef) and n.name == "_is_non_owner")
        ns = {"__name__": "lx", "__package__": "lx"}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<x>", "exec"), ns)
        return ns["_is_non_owner"]

    def test_owner_only_decisions(self):
        is_non = self._load()

        def veh(t="authorized", role=None, state=None):
            d = {"vehicleType": t}
            if role is not None:
                d["vehicleRoleId"] = role
            if state is not None:
                d["vehicleState"] = state
            return d

        class API:
            def __init__(self, v): self._v = v
            def get_vehicles(self):
                if self._v == "RAISE":
                    raise RuntimeError("net fail")
                return [self._v] if self._v else []

        # (说明, 车辆条目, 期望是否拦截)
        cases = [
            ("车主 owned/Active（正常车主）", veh("owned", state="Active"), False),
            # ★ 回归：车主车辆尚在 Registered → relationOf=REL_NONE，
            #   若守卫把"非 REL_OWNER"当拦截，会误伤新车车主。
            ("车主 owned/Registered（关系未确定）", veh("owned", state="Registered"), False),
            ("家人共享 authorized/15", veh("authorized", 15), True),
            ("试驾 authorized/10", veh("authorized", 10), True),
            ("试驾 authorized/13", veh("authorized", 13), True),
            ("家人邀请中 inviting", veh("inviting"), True),
            ("车辆列表为空", None, False),
            ("角色探测抛异常", "RAISE", False),
        ]
        for label, v, exp in cases:
            assert is_non(API(v)) is exp, f"{label}：期望拦截={exp}，实际={is_non(API(v))}"
