"""运行时密钥加载（★ 不硬编码进仓库）

背景
----
2026-09-24：原实现在 const.py 里硬编码了 4 个厂商签名密钥：
  DEFAULT_HAC_KEY / DEFAULT_KEY_ID / DEFAULT_XDEV / DEFAULT_APP_TOKEN

这些是【理想汽车的 API 签名密钥】，格式为高熵十六进制字符串，
会被 GitHub 的 Secret Scanning 识别为"泄露的凭据"，
也可能被判定为"绕过服务商 API 保护"（违反 ToS）。

★ 本模块改为从【本地文件】读取，不进版本库。

加载顺序（优先级从高到低）
--------------------------
  ① Home Assistant 配置项（config entry data）—— 用户在配置流程里填的
  ② 环境变量（LI_HAC_KEY / LI_KEY_ID / LI_XDEV / LI_APP_TOKEN）
  ③ 本地密钥文件（<集成目录>/.secrets.json 或 /config/.lixiang_secrets.json）

文件格式（.secrets.json）
------------------------
```json
{
  "hac_key":   "....",
  "key_id":    "....",
  "xdev":      "....",
  "app_token": "APP-...."
}
```

如何获取这些值
--------------
见 README 的「获取签名密钥」章节 —— 需要从你自己的理想 App 中提取。
本集成【不提供】这些值。

⚠️ .secrets.json 已被 .gitignore 排除，切勿提交到版本库。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger("lixiang_auto")

# 集成目录（本文件所在目录）
_INTEGRATION_DIR = Path(__file__).resolve().parent

def _ha_config_dir() -> Path:
    """HA 配置目录（动态获取，不硬编码 /config）。

    ★ 2026-09-26：原来写死 Path("/config/...")，
      但 HA 的 config 目录可被用户改（如 docker 挂载到别处）。
      优先用 HA 的 API，取不到再回退常见的 /config。
    """
    try:
        from homeassistant.core import HomeAssistant  # noqa: F401
        from homeassistant.config import get_default_config_dir
        return Path(get_default_config_dir())
    except Exception:  # noqa: BLE001
        pass
    # 回退：环境变量 → /config
    import os
    return Path(os.environ.get("HA_CONFIG_DIR") or "/config")


# 候选密钥文件位置（按顺序尝试）
def _secret_file_candidates() -> tuple[Path, ...]:
    """密钥文件候选位置（动态计算，避免硬编码路径）。"""
    home = Path.home()
    return (
        _INTEGRATION_DIR / ".secrets.json",          # 集成目录内
        _ha_config_dir() / ".lixiang_secrets.json",  # HA 配置根目录
        home / ".lixiang_secrets.json",              # 用户家目录
    )


# 兼容旧代码（模块级常量，首次导入时求值）
_SECRET_FILES = _secret_file_candidates()

# 环境变量名 → 配置键
_ENV_MAP = {
    "hac_key": "LI_HAC_KEY",
    "key_id": "LI_KEY_ID",
    "xdev": "LI_XDEV",
    "app_token": "LI_APP_TOKEN",
}

# 缓存（避免每轮轮询都读文件）
_CACHE: dict[str, str] | None = None


def _read_secret_file() -> dict[str, str]:
    """从第一个可读的密钥文件加载。"""
    for path in _SECRET_FILES:
        try:
            if not path.is_file():
                continue
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                _LOGGER.warning("密钥文件格式错误（应为对象）: %s", path)
                continue
            _LOGGER.debug("已从 %s 加载签名密钥", path)
            return {k: str(v) for k, v in data.items() if v}
        except (OSError, ValueError) as err:
            _LOGGER.warning("读取密钥文件失败 %s: %s", path, err)
    return {}


def _read_env() -> dict[str, str]:
    """从环境变量加载。"""
    out: dict[str, str] = {}
    for key, env in _ENV_MAP.items():
        val = os.environ.get(env, "").strip()
        if val:
            out[key] = val
    return out


def load_secrets(force: bool = False) -> dict[str, str]:
    """加载签名密钥（文件 + 环境变量，环境变量优先）。

    返回可能为空 dict —— 调用方需处理缺失情况。
    """
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE

    merged: dict[str, str] = {}
    merged.update(_read_secret_file())
    merged.update(_read_env())          # 环境变量覆盖文件

    if merged:
        _LOGGER.debug("签名密钥已加载 %d 项: %s",
                      len(merged), sorted(merged))
    else:
        _LOGGER.debug(
            "未找到签名密钥 —— 请通过配置流程填写，"
            "或创建 .secrets.json（见 README）")

    _CACHE = merged
    return merged


def get_secret(name: str, default: str = "") -> str:
    """取单个密钥（name: hac_key / key_id / xdev / app_token）。

    ★ 兼容旧代码的 DEFAULT_* 常量用法。
    """
    return load_secrets().get(name) or default


def has_required_secrets() -> bool:
    """是否已配置全部必需密钥。"""
    s = load_secrets()
    return all(s.get(k) for k in ("hac_key", "key_id", "xdev"))


def missing_secrets() -> list[str]:
    """返回缺失的密钥名（用于配置流程提示）。"""
    s = load_secrets()
    return [k for k in ("hac_key", "key_id", "xdev", "app_token") if not s.get(k)]


# ═══════════════════════════════════════════════════════════════════════════
#  兼容层：替代原 const.py 的 DEFAULT_* 常量
# ═══════════════════════════════════════════════════════════════════════════
# 旧代码写法：from .const import DEFAULT_HAC_KEY
# 现在改为：  from .secrets import DEFAULT_HAC_KEY
#
# ★ 这两个模块级变量在【导入时】求值一次；若用户之后创建了 .secrets.json，
#   需重启 HA（或调用 load_secrets(force=True)）。

def _lazy(name: str) -> str:
    return get_secret(name)


class _LazySecret(str):
    """延迟求值的密钥字符串。

    ★ 为什么需要这个？
      模块级常量在 import 时求值，此时 .secrets.json 可能还没创建。
      用 str 子类在【首次使用】时求值，避免顺序问题。
    """

    __slots__ = ("_name",)
    _cache: dict[str, str] = {}

    def __new__(cls, name: str):
        inst = super().__new__(cls, "")
        inst._name = name
        return inst

    def __str__(self) -> str:
        if self._name not in _LazySecret._cache:
            _LazySecret._cache[self._name] = _lazy(self._name)
        return _LazySecret._cache[self._name]

    def __bool__(self) -> bool:
        return bool(str(self))

    def __eq__(self, other: Any) -> bool:
        return str(self) == (str(other) if other is not None else "")

    def __hash__(self) -> int:
        return hash(str(self))


DEFAULT_HAC_KEY: str = _LazySecret("hac_key")
DEFAULT_KEY_ID: str = _LazySecret("key_id")
DEFAULT_XDEV: str = _LazySecret("xdev")
DEFAULT_APP_TOKEN: str = _LazySecret("app_token")

# 登录 device_id 的默认值 —— 保持空（不要硬编码他人设备号）
DEFAULT_DEVICE_ID = ""


__all__ = [
    "load_secrets", "get_secret", "has_required_secrets", "missing_secrets",
    "DEFAULT_HAC_KEY", "DEFAULT_KEY_ID", "DEFAULT_XDEV", "DEFAULT_APP_TOKEN",
    "DEFAULT_DEVICE_ID",
]
