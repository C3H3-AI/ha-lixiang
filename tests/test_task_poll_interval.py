"""任务列表轮询间隔 —— 防止顶掉手机 App（2026-10-11）。

事故
----
用户反馈：**「App 的任务大师无法连接了，禁用集成 + 重新登录 App 才能用」**。

根因（两层叠加）
----------------
1. 任务接口用的是 **SSO 会话级 token**（`_get_scoped("taskmaster", ...)`）
2. 理想账号是**单设备登录** —— 文档
   `lixiang-reverse/docs/L6车控通道研究_20260906.md` 明确记录：
   「账号单设备登录：HA 集成/MuMu/App 会互相顶号」

而任务列表**每 120 秒**轮询一次 → 高频请求持续顶掉 App 的会话 →
App 任务大师失效 → 用户只能禁用集成 + 重登 App。

修复
----
轮询间隔 120s → `TASK_POLL_INTERVAL_SECONDS`（600s，降 5 倍压力）。
任务列表本身变化极慢（用户偶尔改任务），且写操作后会 invalidate 立即刷新。

★ 这是**缓解**而非根治 —— 根治需要"不换取 token"或"独立设备身份"，
  受服务端单设备策略限制，做不到。故同时在诊断/文档里**明确告知**该限制。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CONST = CC / "const.py"
COORD = CC / "coordinator.py"


def _const_src() -> str:
    return CONST.read_text(encoding="utf-8")


def _coord_src() -> str:
    return COORD.read_text(encoding="utf-8")


def _const_value(name: str) -> int:
    """从 const.py 读常量值（AST，不 import —— 该模块无 HA 依赖但保持统一做法）。"""
    tree = ast.parse(_const_src())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"const.py 里找不到 {name}")


class TestIntervalRelaxed:
    def test_interval_is_much_longer_than_before(self):
        """★ 核心：间隔必须远离原来的 120 秒（那是顶号的主因）。"""
        v = _const_value("TASK_POLL_INTERVAL_SECONDS")
        assert v >= 300, f"间隔 {v}s 太短 —— 又会对 App 造成顶号压力"
        assert v != 120, "不能退回 120 秒"

    def test_no_hardcoded_120_left(self):
        """轮询判断里不能再有裸 120。"""
        s = _coord_src()
        i = s.index("get_tasks")
        # 找轮询判断所在的方法体
        j = s.rindex("elif", 0, i)
        blk = s[j:j + 400]
        assert "TASK_POLL_INTERVAL_SECONDS" in blk, "轮询判断应使用常量"
        assert "> 120" not in blk, "还有裸 120 的间隔判断"

    def test_backoff_uses_constants(self):
        """失败退避也要基于常量（不能留旧的 -120+60 算式）。"""
        s = _coord_src()
        assert "_now5 - 120" not in s, "失败退避里还有裸 120"

    def test_cooldown_sane(self):
        v = _const_value("TASK_FORCE_REFRESH_COOLDOWN")
        assert 0 < v <= 300, f"冷却 {v}s 不合理"


class TestConstantsImported:
    """★ 本轮踩过的坑：常量写进了 const.py，但 coordinator 的 import 没加上
    → 运行期 NameError。py_compile 查不出来（不检查名字），只有真机才炸。"""

    def _imported_names(self) -> set[str]:
        tree = ast.parse(_coord_src())
        out: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("const"):
                out |= {a.name for a in node.names}
        return out

    def test_both_constants_imported(self):
        names = self._imported_names()
        for k in ("TASK_POLL_INTERVAL_SECONDS", "TASK_FORCE_REFRESH_COOLDOWN"):
            assert k in names, (
                f"{k} 未在 coordinator 里导入 —— 运行时会 NameError"
                "（AST 检查必要：py_compile 不校验名字）")

    def test_no_undefined_use(self):
        """更通用的守卫：coordinator 用到的 TASK_* 常量必须都已导入。"""
        src = _coord_src()
        used = set(re.findall(r"\bTASK_(?:POLL_INTERVAL_SECONDS|FORCE_REFRESH_COOLDOWN)\b", src))
        imported = self._imported_names()
        missing = used - imported
        assert not missing, f"用到但未导入: {sorted(missing)}"


class TestRationaleDocumented:
    """★ 限制必须在代码里写明 —— 否则后人会把间隔调回 120 秒。"""

    def test_const_comment_explains_why(self):
        src = _const_src()
        i = src.index("TASK_POLL_INTERVAL_SECONDS")
        blk = src[max(0, i - 900):i + 200]
        assert "单设备" in blk, "必须写明「单设备登录」这一根因"
        assert "顶" in blk, "必须写明「顶号」后果"
        # 引用了那篇文档，便于追溯
        assert "L6车控通道研究" in blk or "lixiang-reverse" in blk

    def test_docs_reference_exists(self):
        """注释里引用的文档必须真的存在（引用不能是编的）。"""
        ref = ROOT.parent / "lixiang-reverse" / "docs" / "L6车控通道研究_20260906.md"
        if not ref.exists():
            pytest.skip("外部文档不在本机（跨仓库引用）")
        body = ref.read_text(encoding="utf-8", errors="ignore")
        assert "单设备登录" in body, "被引用的文档里应确有该结论"


class TestBehaviorPreserved:
    def test_write_invalidates_cache(self):
        """写操作后仍要立即刷新（间隔放宽不能牺牲这个体验）。"""
        s = _coord_src()
        assert "def invalidate_task_cache" in s
        assert "_task_ts.clear()" in s or "pop" in s[i] if (i := s.index("invalidate_task_cache")) else True

    def test_owner_only_skip_kept(self):
        """非车主账号仍要跳过（否则 60s 重试风暴）。"""
        assert "_owner_only_skip" in _coord_src()

    def test_error_surfaced(self):
        """失败要有错误上浮（不静默）。"""
        s = _coord_src()
        assert "task_error" in s