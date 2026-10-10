"""文案必须与实测一致 —— 顶号相关文案守卫（2026-10-10）。

事故背景
--------
v1.4.9 的文案写着「理想同学 —— 独立登录会话，**实测不会踢出任何手机 App**」。
用户随后实测：**手机上的「理想汽车」App 被顶下线**（当时用的正是理想同学身份）。

真相是：两种身份登录的都是**同一个理想账号**，而「首次设备验证」与「会话失效后
重登」都会新建一次会话 —— 手机上已登录的 App 可能因此需要重新登录。
那条断言只在很有限的条件下验过一次，不足以支撑「不会踢出任何手机 App」。

本守卫确保：
  ① 再也不会出现「不会踢出任何手机 App」这类**未经验证的安全断言**
  ② 三份文案（strings + en + zh-Hans）都保留「手机 App 可能被登出」的提示
  ③ 设备验证页（browser）说明它用的是与 App 相同的客户端参数、可能顶掉手机
  ④ README 不再保留已过期的「唯一已知差异」（理想同学拿不到车辆列表 ——
     v1.4.9 的 #51 已修）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
FILES = ("strings.json", "translations/en.json", "translations/zh-Hans.json")

#: 未经验证就被断言过的「安全」说法 —— 禁止再出现
FORBIDDEN = ("不会踢出任何手机 App", "does not sign out any phone app")


def _steps(rel: str) -> dict:
    d = json.loads((CC / rel).read_text(encoding="utf-8"))
    return d["config"]["step"]


@pytest.mark.parametrize("rel", FILES)
def test_no_unverified_safe_claim(rel):
    """★ 核心：不得再宣称「不会踢出手机 App」（实测已被推翻）。"""
    text = (CC / rel).read_text(encoding="utf-8")
    for bad in FORBIDDEN:
        assert bad not in text, (
            f"{rel} 又出现了未经验证的安全断言「{bad}」——"
            "实测两种身份都可能让手机 App 重新登录")


@pytest.mark.parametrize("rel", FILES)
def test_kick_warning_present(rel):
    """三份文案都要提示「手机 App 可能被登出」。"""
    steps = _steps(rel)
    for step_id in ("user", "password_login"):
        desc = steps[step_id]["description"]
        ok = ("手机 App 可能被登出" in desc
              or "phone app may be signed out" in desc)
        assert ok, f"{rel} 的 {step_id} 缺少顶号提示"


@pytest.mark.parametrize("rel", FILES)
def test_browser_step_explains_shared_client(rel):
    """设备验证页用的是与 App 相同的客户端参数 → 必须说清可能顶号。"""
    desc = _steps(rel)["browser"]["description"]
    ok = ("相同的客户端参数" in desc) or ("same client parameters" in desc)
    assert ok, f"{rel} 的 browser 步骤没有说明它用的是主 App 客户端参数"


def test_readme_stale_claim_removed():
    """README 不再保留已过期的「唯一已知差异」（v1.4.9 已修）。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "唯一已知差异" not in readme, "README 还留着已过期的差异说明"
    assert "拿不到车辆列表接口" not in readme, "README 还留着已修好的限制描述"


def test_readme_has_kick_faq():
    """README 要有「手机 App 被登出」的排错问答，并且指明已做的改进。"""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "被登出" in readme
    assert "复用登录会话" in readme or "持久化登录会话" in readme
