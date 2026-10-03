"""secrets / _LazySecret 类型契约测试

★ 背景（2026-09-24 严重回归）：
  密钥外部化重构引入 secrets._LazySecret（str 子类，构造时内容为空，
  真实值靠 __str__() 延迟求值），触发两个 bug：

  bug 1: li_api._hac_key_bytes 里
           s = (hac_key or "").strip()
         走的是【底层空内容】而非 __str__() → 得到 ""
         → _hac 长度 0 → 签名错误

  bug 2: LiApiClient.__init__ 直接存对象
           self._key_id = key_id
         → 用作 HTTP 头时拿到空字符串

  表现：服务端报「缺少必要的请求参数: X-CHJ-Key,X-CHJ-Deviceid」
        → 所有签名接口失败 → VIN 取不到 → 首次配置卡住

  本测试确保：_LazySecret 传给下游后仍是【有效内容】。

注：secrets.py 本身不内置默认值（返回空），
    真正的默认值兜底在 const.py：
        DEFAULT_HAC_KEY = _S_HAC_KEY or "<内置值>"
    所以测试要针对 const.py。
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _load_const():
    """加载包内的 const 模块（避开 homeassistant 依赖）。"""
    pkg = types.ModuleType("lx_t")
    pkg.__path__ = [str(INTEG)]
    sys.modules["lx_t"] = pkg
    spec = importlib.util.spec_from_file_location("lx_t.const", INTEG / "const.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lx_t.const"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_secrets():
    spec = importlib.util.spec_from_file_location("lx_secrets", INTEG / "secrets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLazySecretType:
    """★ _LazySecret 的类型契约"""

    def test_is_str_subclass(self):
        """必须是 str 子类（兼容旧代码 isinstance 检查）"""
        sec = _load_secrets()
        assert issubclass(sec._LazySecret, str)

    def test_str_gives_real_value(self):
        """★ str() 必须给出真实值"""
        C = _load_const()
        v = C.DEFAULT_HAC_KEY
        s = str(v)
        assert len(s) == 64, f"hac_key 应 64 字符，str() 得到 {len(s)}"

    def test_all_defaults_nonempty(self):
        """★ 所有 DEFAULT_* 必须非空（否则签名失败）"""
        C = _load_const()
        expect = {
            "DEFAULT_HAC_KEY": 64,
            "DEFAULT_KEY_ID": 32,
            "DEFAULT_XDEV": 32,
            "DEFAULT_APP_TOKEN": 36,
        }
        for name, want in expect.items():
            v = getattr(C, name, None)
            assert v is not None, f"{name} 不存在"
            got = len(str(v))
            assert got == want, f"{name} 应 {want} 字符，实际 {got}"

    def test_strip_trap_documented(self):
        """★ 记录陷阱：str 子类上直接 .strip() 会丢值

        这是 bug 的根源 —— Python 的 str 方法基于【底层内容】，
        而 _LazySecret 的底层内容是空字符串。
        """
        C = _load_const()
        v = C.DEFAULT_HAC_KEY
        # 底层内容为空 → 直接 .strip() 得到空
        direct = v.strip()
        # str() 之后才正确
        converted = str(v).strip()
        assert len(converted) == 64, "str() 后 strip 必须有效"
        # 记录：直接 strip 的结果（可能是空，也可能非空取决于实现）
        # 关键是要有 str() 这一步
        assert direct != converted or len(direct) == 64

    def test_encode_after_str(self):
        """str() 后 encode 得到正确字节"""
        C = _load_const()
        assert len(str(C.DEFAULT_HAC_KEY).encode()) == 64

    def test_bool_true(self):
        """默认值 bool() 为真"""
        C = _load_const()
        assert bool(C.DEFAULT_HAC_KEY) is True


class TestLiApiForcesStr:
    """★ li_api.py 必须对 _LazySecret 显式 str() 转换"""

    @staticmethod
    def _src() -> str:
        return (INTEG / "li_api.py").read_text(encoding="utf-8")

    def test_hac_key_bytes_forces_str(self):
        """_hac_key_bytes 必须先 str() 再处理（bug 1 的修复）"""
        src = self._src()
        m = re.search(r"def _hac_key_bytes.*?(?=\n_SSL_CTX|\ndef _ssl_ctx)", src, re.S)
        assert m, "未找到 _hac_key_bytes"
        assert "str(hac_key" in m.group(0), (
            "_hac_key_bytes 没有 str() 转换 —— _LazySecret 会导致密钥为空")

    def test_init_forces_str_on_credentials(self):
        """★ LiApiClient.__init__ 必须对凭据显式 str()（bug 2 的修复）

        注意：文件里有多个 __init__（如 LiApiError），
             要定位到 LiApiClient 的那个。
        """
        src = self._src()
        # 从 class LiApiClient 开始找它的 __init__
        cls = re.search(r"class LiApiClient\b.*", src, re.S)
        assert cls, "未找到 class LiApiClient"
        m = re.search(r"def __init__\(.*?(?=\n    def )", cls.group(0), re.S)
        assert m, "未找到 LiApiClient.__init__"
        body = m.group(0)
        for field in ("key_id", "xdev", "app_token"):
            assert re.search(rf"self\._{field}\s*=\s*str\(", body), (
                f"LiApiClient.__init__ 里 self._{field} 缺 str() —— HTTP 头会为空")

    def test_init_no_or_empty_pattern(self):
        """★ 禁止 `str(x or "")` 模式 —— `or` 会触发 _LazySecret.__bool__

        这是 VIN bug 的【真正根因】：
            str(hac_key or "")   →  __bool__ 返回 False  →  取到 ""
        必须写成 `str(x) if x is not None else ""`
        """
        src = self._src()
        bad = re.findall(r'str\(\w+\s+or\s+""\)', src)
        assert not bad, (
            f"发现危险的 `str(x or \"\")` 写法 {bad} —— "
            "对 _LazySecret 会取到空值，必须改用 `str(x) if x is not None else ''`")


class TestHacKeyBytes:
    """_hac_key_bytes 的归一化行为"""

    @staticmethod
    def _fn():
        src = (INTEG / "li_api.py").read_text(encoding="utf-8")
        m = re.search(
            r"(def _hac_key_bytes.*?)(?=\n_SSL_CTX|\ndef _ssl_ctx)", src, re.S)
        assert m, "未找到 _hac_key_bytes"
        import base64 as _b64
        ns: dict = {"base64": _b64}
        exec(m.group(1), ns)
        return ns["_hac_key_bytes"]

    def test_hex_64(self):
        assert len(self._fn()("a" * 64)) == 32

    def test_real_key(self):
        key = "2020a7738b35f7d253741a88963ea2902b770ac508d89a78ae9036ee8aeb5d8a"
        assert len(self._fn()(key)) == 32

    def test_lazy_secret_like_object(self):
        """★ 模拟 _LazySecret：str 子类，底层空 + __str__ 求值

        这正是线上踩到的场景 —— 必须返回 32 字节。
        """
        fn = self._fn()

        class FakeLazy(str):
            def __new__(cls):
                return super().__new__(cls, "")

            def __str__(self):
                return ("2020a7738b35f7d253741a88963ea2902b770ac5"
                        "08d89a78ae9036ee8aeb5d8a")

        got = len(fn(FakeLazy()))
        assert got == 32, (
            f"对 _LazySecret 类对象处理失败：{got} 字节（应 32）——"
            "这是 VIN 取不到的根因")

    def test_empty_inputs(self):
        fn = self._fn()
        assert fn("") == b""
        assert fn(None) == b""
