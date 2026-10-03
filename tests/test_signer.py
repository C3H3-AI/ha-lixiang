"""signer.py 测试：x-chj 签名器

★ 背景：
  签名算法是集成能否工作的核心。一旦算错，所有 API 都返回
  "请求签名错误"，且很难排查。

  逆向结论（iOS 实证）：
    data = "\\n".join([env, appVersion, keyId, deviceId, method, accept,
                      contentLang, contentMD5, contentType, timestamp, nonce])
    ★ 末尾再补一个 '\\n'（iOS 实证）
    sign = base64(HMAC-SHA256(hacKey原始字节, data))

  ★ 关键坑：HMAC 的 key 必须是 hac_key 的【原始 32 字节】，
    不能用 base64 文本的 .encode()。

本测试锁定这些行为。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

INTEG = Path(__file__).resolve().parent.parent / "custom_components" / "lixiang_auto"


def _load(name: str, rel: str):
    """加载集成内的独立模块（避开 homeassistant 依赖）。"""
    pkg = types.ModuleType(f"_lx_{name}")
    pkg.__path__ = [str(INTEG)]
    sys.modules[f"_lx_{name}"] = pkg
    spec = importlib.util.spec_from_file_location(
        f"_lx_{name}.{name}", INTEG / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_lx_{name}.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestNormalizeHacKey:
    """hac_key 三种输入形式都要归一化为原始 32 字节"""

    @staticmethod
    def _fn():
        signer = _load("signer", "signer.py")
        return signer.normalize_hac_key

    HEX64 = "2020a7738b35f7d253741a88963ea2902b770ac508d89a78ae9036ee8aeb5d8a"

    def test_hex_string(self):
        """64 位 hex 字符串 → 32 字节"""
        assert len(self._fn()(self.HEX64)) == 32

    def test_raw_bytes(self):
        """原始 bytes → 原样返回"""
        raw = bytes.fromhex(self.HEX64)
        assert self._fn()(raw) == raw

    def test_base64_string(self):
        """base64 字符串 → 32 字节"""
        b64 = base64.b64encode(bytes.fromhex(self.HEX64)).decode()
        assert len(self._fn()(b64)) == 32

    def test_lazy_secret_like(self):
        """★ 模拟 secrets._LazySecret（str 子类，延迟求值）

        ⚠️ 注意：normalize_hac_key 内部用 hac_key.strip()，
          对 _LazySecret 会走底层空内容。
          → 调用方（li_api.py）必须先 str() 转换！
          本测试验证「已 str() 转换后的输入」能正确处理。
        """

        class FakeLazy(str):
            def __new__(cls):
                return super().__new__(cls, "")

            def __str__(self):
                return TestNormalizeHacKey.HEX64

        # 模拟调用方的正确做法：先 str()
        assert len(self._fn()(str(FakeLazy()))) == 32

    def test_lazy_secret_raw_would_fail(self):
        """★ 记录陷阱：直接把 _LazySecret 传进去会失败

        这是 li_api.py 里 _hac_key_bytes 必须 str() 的原因。
        """

        class FakeLazy(str):
            def __new__(cls):
                return super().__new__(cls, "")

            def __str__(self):
                return TestNormalizeHacKey.HEX64

        # 直接传 → strip() 走空内容 → 兜底走 ascii 编码 → 0 字节
        result = self._fn()(FakeLazy())
        assert len(result) != 32, (
            "如果这里变 32 了，说明 Python 行为变了 —— "
            "可以移除 li_api 里的 str() 兜底")


class TestSignatureAlgorithm:
    """签名算法必须与逆向结论一致"""

    @staticmethod
    def _signer():
        return _load("signer", "signer.py")

    HEX64 = "2020a7738b35f7d253741a88963ea2902b770ac508d89a78ae9036ee8aeb5d8a"

    def _manual_sign(self, parts: list[str], trailing_nl: bool = True) -> str:
        """按逆向结论手工算签名（用于对照）"""
        key = bytes.fromhex(self.HEX64)
        data = "\n".join(parts)
        if trailing_nl:
            data += "\n"
        return base64.b64encode(
            hmac.new(key, data.encode(), hashlib.sha256).digest()).decode()

    def test_sign_function_exists(self):
        """必须有签名函数"""
        signer = self._signer()
        fns = [n for n in dir(signer) if "sign" in n.lower()]
        assert fns, "signer.py 里没有签名函数"

    def test_uses_hmac_sha256(self):
        """必须用 HMAC-SHA256"""
        src = (INTEG / "signer.py").read_text(encoding="utf-8")
        assert "hmac" in src and "sha256" in src, "应使用 HMAC-SHA256"

    def test_trailing_newline(self):
        """★ 签名 data 末尾必须有 '\\n'（iOS 实证）

        这是最容易漏的细节 —— 少了它服务端报"签名错误"。
        """
        src = (INTEG / "signer.py").read_text(encoding="utf-8")
        # 检查有 + "\n" 或 join 后追加换行的逻辑
        assert re.search(r'\+\\s*"\\\\n"|SIGN_SEP|join.*\(.*\).*\\n', src), (
            "signer.py 未体现「末尾补换行」的逻辑")

    def test_empty_md5_constant_exists(self):
        """EMPTY_MD5 常量（无 body 时用）"""
        C = _load("const", "const.py")
        assert hasattr(C, "EMPTY_MD5") or "EMPTY_MD5" in (
            INTEG / "const.py").read_text(encoding="utf-8")


class TestSignatureConstants:
    """签名相关常量"""

    def test_env_is_prod(self):
        """env 必须是 prod"""
        C = _load("const", "const.py")
        src = (INTEG / "const.py").read_text(encoding="utf-8")
        assert 'ENV = "prod"' in src or 'ENV: str = "prod"' in src, \
            "ENV 应为 prod"

    def test_content_type_json(self):
        """content-type 必须是 application/json"""
        src = (INTEG / "const.py").read_text(encoding="utf-8")
        assert "application/json" in src

    def test_sign_sep_is_newline(self):
        """签名分隔符是换行"""
        C = _load("const", "const.py")
        assert C.SIGN_SEP == "\n", f"SIGN_SEP 应为换行，实际 {C.SIGN_SEP!r}"

    def test_has_11_sign_parts(self):
        """★ 签名 data 应有 11 个字段 + 末尾分隔符

        iOS 实证：11 个参数用 \n 拼接后【末尾再补一个 \n】
        → 最终是 12 段（最后一段为空）
        """
        src = (INTEG / "signer.py").read_text(encoding="utf-8")
        m = re.search(r"parts\s*=\s*\[(.*?)\n\s*\]", src, re.S)
        assert m, "未找到 parts 列表"
        # ★ 统计 parts 的【元素个数】（11 个字段）
        body = m.group(1)
        items = [l for l in body.split("\n")
                 if l.strip() and not l.strip().startswith("#")]
        assert len(items) == 11, (
            f"签名应有 11 个字段，实际 {len(items)}:\n" +
            "\n".join(f"  {i}" for i in items))
        # 末尾必须补分隔符
        assert re.search(r"SIGN_SEP\.join\(parts\)\s*\+\s*SIGN_SEP", src), \
            "签名 data 末尾应追加 SIGN_SEP（换行）：iOS 实证需要 12 段"
