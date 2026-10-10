"""集成日志可见性守卫（2026-10-10）。

真事故（实测）
--------------
`const.LOGGER_NAME` 原来是裸名 `"lixiang_auto"`。HA 的默认日志级别只把
`homeassistant.*` 与 `custom_components.*` 记为 INFO，**裸 logger 名继承
root（WARNING）** → 集成的 INFO 日志用户一条都看不到：

    实测：日志里 `INFO ...[lixiang_auto]` 出现 0 次；
          而 `[custom_components.lixiang_auto.li_api]` 的 INFO 正常出现
          （那 4 个模块用 logging.getLogger(__name__)）。

后果：用户排障时「什么都没看到」，也看不到「身份来源=」「已派生签名身份」
这类关键信息；反而只有 WARNING/ERROR 才可见 —— 正好把最需要的前因藏起来。

本文件守卫两件事：
  ① `LOGGER_NAME` 必须在 `custom_components.` 命名空间下（HA 默认可达 INFO）
  ② 模块里不得再硬编码裸 logger 名（要么用 LOGGER_NAME，要么用 __name__）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"

#: HA 默认按 INFO 记录的命名空间前缀
HA_INFO_NAMESPACES = ("custom_components.", "homeassistant.")


def _const_src() -> str:
    return (CC / "const.py").read_text(encoding="utf-8")


class TestLoggerNamespace:
    def test_logger_name_is_under_ha_namespace(self):
        """★ LOGGER_NAME 必须在 custom_components.* 下，否则 INFO 默认不可见。"""
        m = re.search(r'^LOGGER_NAME\s*=\s*"([^"]+)"', _const_src(), re.M)
        assert m, "const.py 里找不到 LOGGER_NAME 定义"
        name = m.group(1)
        assert name.startswith(HA_INFO_NAMESPACES), (
            f"LOGGER_NAME={name!r} 不在 HA 默认 INFO 命名空间内 —— "
            "裸 logger 名继承 root(WARNING)，集成的 INFO 日志用户看不到")

    def test_no_module_hardcodes_bare_logger_name(self):
        """★ 每个模块的 logger 必须来自 LOGGER_NAME 或 __name__。

        两者都在 custom_components.* 下；任何硬编码的裸名都会让该模块的
        INFO 日志静默消失（历史事故：policy.py / secrets.py 写死 "lixiang_auto"）。
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
