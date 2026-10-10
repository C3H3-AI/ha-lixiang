"""集成日志可见性守卫（2026-10-10）。

真事故（实测）
--------------
`const.LOGGER_NAME` 原来是裸名 `"lixiang_auto"`。

★ 事实澄清：HA 的 root logger 默认是 WARNING
  （`bootstrap.py`: `logger.setLevel(INFO if verbose else WARNING)`），
  所以 **`custom_components.*` 也默认不输出 INFO** —— 不要以为进了命名空间
  就自动可见。用户开日志靠 HA 的标准入口：集成页「启用调试日志」按钮，
  或 `logger.logs.custom_components.lixiang_auto: info`。

★ 真正的缺陷（实测）：HA 那个入口正是按 `custom_components.<domain>` 写的。
  改名之前，本集成 50+ 个模块用裸名，只有 4 个用
  `logging.getLogger(__name__)` 的模块会出日志
  → **一键「启用调试日志」是半残的**（coordinator / config_flow 等全都不出）。
  改名后同一行配置覆盖全部模块（实测 16 条 INFO 正常输出）。

本文件守卫两件事：
  ① `LOGGER_NAME` 必须在 `custom_components.` 命名空间下
     （这样 HA 的标准调试入口 / 一行配置才能覆盖全部模块）
  ② 模块里不得再硬编码裸 logger 名（要么用 LOGGER_NAME，要么用 __name__）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"

#: HA 标准调试入口（集成页按钮 / logger.logs）使用的命名空间前缀
HA_INFO_NAMESPACES = ("custom_components.", "homeassistant.")


def _const_src() -> str:
    return (CC / "const.py").read_text(encoding="utf-8")


class TestLoggerNamespace:
    def test_logger_name_is_under_ha_namespace(self):
        """★ LOGGER_NAME 必须在 custom_components.* 下。

        否则 HA 的标准调试入口（集成页「启用调试日志」写的就是
        `custom_components.<domain>`）覆盖不到本集成，用户按标准做法开了日志
        也看不到（历史事故：50+ 模块裸名，只有 4 个模块出日志）。
        """
        m = re.search(r'^LOGGER_NAME\s*=\s*"([^"]+)"', _const_src(), re.M)
        assert m, "const.py 里找不到 LOGGER_NAME 定义"
        name = m.group(1)
        assert name.startswith(HA_INFO_NAMESPACES), (
            f"LOGGER_NAME={name!r} 不在 HA 标准调试命名空间内 —— "
            "用户按 HA 的「启用调试日志」入口开了也覆盖不到本集成")

    def test_no_module_hardcodes_bare_logger_name(self):
        """★ 每个模块的 logger 必须来自 LOGGER_NAME 或 __name__。

        两者都在 custom_components.* 下 → HA 标准调试入口能覆盖到；
        任何硬编码的裸名都会让该模块的日志在标准配置下静默消失
        （历史事故：policy.py / secrets.py 写死 "lixiang_auto"）。
        """
        bad = []
        for f in sorted(CC.glob("*.py")):
            for i, line in enumerate(
                    f.read_text(encoding="utf-8").splitlines(), 1):
                for m in re.finditer(
                        r'getLogger\(\s*(["\'])([^"\']+)\1\s*\)', line):
                    if not m.group(2).startswith(HA_INFO_NAMESPACES):
                        bad.append(f"{f.name}:{i}  {line.strip()[:90]}")
        assert not bad, (
            "发现硬编码的裸 logger 名（其 INFO 日志默认不可见）：\n  "
            + "\n  ".join(bad))

    def test_all_modules_have_a_logger(self):
        """哨兵：确认扫描确实扫到了模块（防止 glob 写错导致守卫空转）。"""
        files = [f for f in CC.glob("*.py")
                 if "getLogger(" in f.read_text(encoding="utf-8")]
        assert len(files) >= 20, f"只扫到 {len(files)} 个带 logger 的模块，疑似扫描失效"
