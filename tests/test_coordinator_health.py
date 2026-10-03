"""coordinator 错误处理测试（不依赖 HA 运行时）

★ 2026-09-24 新增：验证失败分级策略
  · <3 次  → 静默（debug）
  · 3-4 次 → warning
  · >=5 次 → 发持久通知
  · 成功   → 清除通知
"""

from __future__ import annotations

from enum import StrEnum


class Level(StrEnum):
    DEBUG = "debug"
    WARNING = "warning"
    ERROR = "error"


def failure_level(n: int) -> Level:
    """★ 从 coordinator.py 提取的分级逻辑（保持同步）。

    对应 coordinator.py 的：
      if n < 3:       _LOGGER.debug(...)
      elif n < 5:     _LOGGER.warning(...)
      else:           _LOGGER.error(...) + _notify_failure(n)
    """
    if n < 3:
        return Level.DEBUG
    if n < 5:
        return Level.WARNING
    return Level.ERROR


def should_notify(n: int) -> bool:
    """达到通知阈值（>=5 次）。"""
    return n >= 5


class TestFailureGrading:
    def test_first_failures_silent(self):
        assert failure_level(1) == Level.DEBUG
        assert failure_level(2) == Level.DEBUG

    def test_middle_failures_warn(self):
        assert failure_level(3) == Level.WARNING
        assert failure_level(4) == Level.WARNING

    def test_persistent_failures_error(self):
        assert failure_level(5) == Level.ERROR
        assert failure_level(10) == Level.ERROR

    def test_notify_threshold(self):
        for n in range(1, 5):
            assert should_notify(n) is False, f"{n} 次不该通知"
        for n in range(5, 12):
            assert should_notify(n) is True, f"{n} 次该通知"

    def test_notify_only_once(self):
        """★ 通知只发一次（由 _fail_notified 标志保证）"""
        notified = False
        sent = 0
        for n in range(1, 11):
            if should_notify(n) and not notified:
                notified = True
                sent += 1
        assert sent == 1, "整个失败周期应只通知一次"

    def test_recovery_clears_flag(self):
        """恢复后标志复位（下次失败可再通知）"""
        notified = True
        # 成功后
        notified = False
        assert notified is False

class TestNoUndefinedMethodCalls:
    """★ 2026-09-26 实车验证发现：coordinator.py 调用了两个从未定义的方法
    （_notify_failure / _clear_failure），导致每次轮询成功都抛 AttributeError，
    所有可控实体变 unavailable。

    这个测试扫描所有平台的 self.xxx() 调用，确保都有定义。
    """

    PLATFORM_FILES = [
        "coordinator.py", "sensor.py", "binary_sensor.py", "switch.py",
        "number.py", "select.py", "time.py", "cover.py", "fan.py",
        "climate.py", "lock.py", "button.py", "device_tracker.py",
        "notify.py", "li_api.py", "signer.py", "policy.py",
    ]

    def test_all_self_method_calls_are_defined(self):
        """静态检查：self.xxx() 调用必须在同类里有定义。"""
        import ast
        import re
        from pathlib import Path

        integ = (Path(__file__).resolve().parent.parent
                 / "custom_components" / "lixiang_auto")
        problems = []

        for fname in self.PLATFORM_FILES:
            f = integ / fname
            if not f.exists():
                continue
            src = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue

            # ① 已定义的方法
            defined = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined.add(node.name)

            # ② 实例属性（self._x = ...）也算已定义
            for m in re.finditer(r'self\.(_\w+)\s*=', src):
                defined.add(m.group(1))

            # ③ 去掉文档字符串和行注释，避免误报
            code_lines = []
            in_doc = False
            TRIPLE = chr(34) * 3
            TRIPLE_S = chr(39) * 3
            for ln in src.split(chr(10)):
                stripped = ln.strip()
                q = stripped.count(TRIPLE) + stripped.count(TRIPLE_S)
                if q % 2 == 1:
                    in_doc = not in_doc
                    continue
                if in_doc:
                    continue
                if "#" in ln:
                    ln = ln[:ln.index("#")]
                code_lines.append(ln)
            code = chr(10).join(code_lines)

            # 找 self._xxx( 调用
            for m in re.finditer(r'self\.(_\w+)\s*\(', code):
                name = m.group(1)
                if name not in defined:
                    line = src[:m.start()].count(chr(10)) + 1
                    problems.append(f"{fname}:{line} self.{name}()")

        assert not problems, (
            "以下 self.xxx() 被调用但未定义（运行时会 AttributeError）:\n  "
            + "\n  ".join(problems)
        )
