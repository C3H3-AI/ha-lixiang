# -*- coding: utf-8
"""充电统计口径守卫（2026-10-08）。

背景（真机实测）：集成原先统计「本月充电量 / 累计充电量」时只查
``chargingType`` 1(DC 直流) + 2(AC 交流)，**漏掉 3(SC 5C超充) 与
4(4CAnd5C 理想超充)**，导致数值少算、用户可见错误。

同一账号同一月实测：

| chargingType | 含义          | 本月 kWh | 本月次数 |
|---|---|---|---|
| 1            | DC 直流快充    | 78.65    | 6        |
| 2            | AC 交流慢充    | 41.18    | 2        |
| 3            | SC 5C超充      | 29.43    | 1        |
| 4            | 4CAnd5C 理想超充 | 23.76  | 1        |
| —            | 旧口径 1+2     | **119.83** ← 用户报告的 119.80 ❌ |
| —            | 正确 1+2+3+4   | **173.02** ✅ |

类型语义来源：App bundle（``chargingType === 1/2/3/4``）与 I18N 文案
（chargingTypeDC / chargingTypeAC / chargingTypeSC / chargingType4CAnd5C）。

本文件守卫：统计函数不得再退回到只查 1+2。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _src(name: str) -> str:
    return (_INTEG / name).read_text(encoding="utf-8")


def _func_block(src: str, name: str) -> str:
    i = src.find(f"def {name}(")
    assert i > 0, f"缺少 {name}"
    j = src.find("\n    def ", i + 10)
    return src[i:j] if j > i else src[i:i + 3000]


class TestChargeStatsScope:
    @staticmethod
    def _for_iters(fn_name: str) -> list[str]:
        """返回指定函数内所有 for 循环的迭代源（AST unparse 文本）。"""
        tree = ast.parse(_src("li_api.py"))
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"缺少函数 {fn_name}"
        return [ast.unparse(n.iter) for n in ast.walk(fn) if isinstance(n, ast.For)]

    def test_charge_type_prefix_covers_all_four(self):
        """★ 充电类型常量必须覆盖 1/2/3/4（含理想超充）。"""
        tree = ast.parse(_src("li_api.py"))
        for node in ast.walk(tree):
            tgt = getattr(node, "target", None)
            if (isinstance(node, ast.AnnAssign)
                    and getattr(tgt, "id", "") == "CHARGE_TYPE_PREFIX"):
                keys = [e.elts[0].value for e in node.value.elts]
                assert keys == [1, 2, 3, 4], f"充电类型不完整: {keys}"
                return
        raise AssertionError("缺少 CHARGE_TYPE_PREFIX 定义")

    def test_prefixes_are_distinct(self):
        """前缀不得重复（否则字段互相覆盖）。"""
        tree = ast.parse(_src("li_api.py"))
        for node in ast.walk(tree):
            tgt = getattr(node, "target", None)
            if (isinstance(node, ast.AnnAssign)
                    and getattr(tgt, "id", "") == "CHARGE_TYPE_PREFIX"):
                pfxs = [e.elts[1].value for e in node.value.elts]
                assert len(pfxs) == len(set(pfxs)), f"前缀重复: {pfxs}"
                return
        raise AssertionError("缺少 CHARGE_TYPE_PREFIX 定义")

    def test_month_kwh_uses_all_types(self):
        """本月充电量：必须按 CHARGE_TYPE_PREFIX 遍历，且不得回退到硬编码类型。

        （用 AST 取每个 for 的迭代源：既要求存在按常量遍历的循环，
          也禁止出现硬编码 (1, 2) 之类的类型元组。只搜字符串时，
          函数里任一处置有常量就能蒙混过关。）
        """
        iters = self._for_iters("get_charge_current_month_kwh")
        assert "CHARGE_TYPE_PREFIX" in iters, "未按 CHARGE_TYPE_PREFIX 遍历充电类型"
        bad = [it for it in iters if it.startswith("((1,") or it == "(1, 2)"]
        assert not bad, f"仍存在硬编码的充电类型遍历（会漏算超充）: {bad}"

    def test_total_kwh_uses_all_types(self):
        """累计充电量同样须按 CHARGE_TYPE_PREFIX 遍历。"""
        iters = self._for_iters("get_charge_total_kwh")
        assert "CHARGE_TYPE_PREFIX" in iters, "未按 CHARGE_TYPE_PREFIX 遍历充电类型"
        bad = [it for it in iters if it.startswith("((1,") or it == "(1, 2)"]
        assert not bad, f"仍存在硬编码的充电类型遍历: {bad}"

    def test_month_charge_times_includes_all(self):
        """充电次数赋值右侧必须用 total_times（精确匹配赋值表达式）。

        （不用「窗口内是否出现字符串」的写法 —— 注释里出现同名
          字符串会让断言失效。）
        """
        s = _src("coordinator.py")
        m = re.search(r'_mc\["month_charge_times"\]\s*=\s*(.+)', s)
        assert m, "未找到 _mc[month_charge_times] 赋值"
        rhs = m.group(1)
        assert "total_times" in rhs, f"次数未使用 total_times（漏算超充次数）: {rhs[:90]}"

    def test_monthly_records_doc_mentions_four_types(self):
        """取某月明细的接口文档须说明 4 种类型（避免再次误解为只有 DC/AC）。"""
        blk = _func_block(_src("li_api.py"), "get_charge_records_monthly")
        for kw in ("DC", "AC", "5C", "理想超充"):
            assert kw in blk, f"类型说明缺 {kw}"
