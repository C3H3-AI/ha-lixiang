"""单文件卡片包 —— 回归测试（2026-10-14）。

背景
----
车主：「不能把13个js文件合并为一个？」
开发时一页一个文件好维护，但对外发布要的是**一个资源**：
  · 用户不必理解"哪个文件对应哪页"，漏一个就空白；
  · 外壳原靠 `import.meta.url` 相对路径动态 import 13 个文件，
    文件挪位置（如放 /local/）就可能全部加载失败；
  · 首屏 14 个请求。

`scripts/build-cards.mjs` 生成 `www/lixiang-cards/lixiang-all.js`：
每个文件各自包一层 IIFE 保留模块作用域（12 张卡有 13 组同名顶层常量，
直接拼接会 `Identifier has already been declared`），有 ESM 导出的 3 个文件
把导出挂到 `window.__LXB.<模块>` 供后续文件解构。

★ 本文件最重要的一条是 `test_bundle_is_up_to_date`：单文件是**生成物**，
  改了源文件却忘记重新生成，就会出现"改了半天没生效"的诡异现象。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "custom_components" / "lixiang_auto"
CARDS = CC / "www" / "lixiang-cards"
BUNDLE = CARDS / "lixiang-all.js"
SCRIPT = ROOT / "scripts" / "build-cards.mjs"
INIT = CC / "__init__.py"
SHELL = CARDS / "lixiang-app.js"

ALL_TAGS = [
    "lixiang-app", "lixiang-app-home", "lixiang-charge-page", "lixiang-energy-page",
    "lixiang-health-page", "lixiang-setting-page", "lixiang-scene-page",
    "lixiang-climate-page", "lixiang-seat-page", "lixiang-location-page",
    "lixiang-vehicle-info-page", "lixiang-task-page", "lixiang-ad-page",
    "lixiang-bindings-card", "lixiang-overview-card",
]


def _needs_node() -> None:
    if not shutil.which("node"):
        pytest.skip("未安装 node")


class TestBundleExists:
    def test_bundle_file_present(self):
        assert BUNDLE.is_file(), f"缺单文件包：{BUNDLE}（运行 node scripts/build-cards.mjs）"

    def test_build_script_present(self):
        assert SCRIPT.is_file(), "缺生成脚本 scripts/build-cards.mjs"

    def test_bundle_defines_every_card(self):
        s = BUNDLE.read_text(encoding="utf-8")
        missing = []
        for tag in ALL_TAGS:
            if f'"{tag}"' not in s or "customElements.define" not in s:
                missing.append(tag)
        # 元素名以 `const CARD_TAG = "lixiang-xxx"` 形式声明，逐个核对
        for tag in ALL_TAGS:
            if f'"{tag}"' not in s:
                missing.append(tag)
        assert not missing, f"单文件里缺这些卡片：{missing}"
        n_define = len(re.findall(r"customElements\.define", s))
        assert n_define >= 14, f"define 调用太少（{n_define}）—— 产物可疑"

    def test_no_module_syntax_left(self):
        """单文件里不应残留顶层 import/export（否则不是"一个可直接加载的文件"）。"""
        s = BUNDLE.read_text(encoding="utf-8")
        leftover = re.findall(r"^\s*(?:import|export)\s", s, re.M)
        assert not leftover, f"单文件残留 {len(leftover)} 处 import/export"

    def test_every_source_file_embedded(self):
        s = BUNDLE.read_text(encoding="utf-8")
        for f in sorted(CARDS.glob("lixiang-*.js")):
            if f.name == BUNDLE.name:
                continue
            assert f.name in s, f"{f.name} 未被并入单文件（构建脚本 ORDER 漏了？）"

    def test_scope_wrapped(self):
        """每张卡都必须包在 IIFE 里 —— 否则 13 组同名常量会互相覆盖/报错。"""
        s = BUNDLE.read_text(encoding="utf-8")
        assert s.count("(function () {") >= 12, "IIFE 包裹数过少，模块作用域没隔离"
        # 抽查常见的冲突名确实出现在多个 IIFE 内
        assert s.count("const CARD_TAG") >= 10, "CARD_TAG 声明数异常"


class TestBundleFreshness:
    def test_bundle_is_up_to_date(self):
        """★ 生成物必须与源文件一致（改了源文件要重新跑构建脚本）。"""
        _needs_node()
        r = subprocess.run(["node", str(SCRIPT), "--stdout"],
                           capture_output=True, text=True, timeout=120, cwd=ROOT)
        assert r.returncode == 0, r.stderr[:500]
        expected = r.stdout
        actual = BUNDLE.read_text(encoding="utf-8")
        assert actual == expected, (
            "lixiang-all.js 已过期 —— 请运行 `node scripts/build-cards.mjs` 重新生成")


class TestIntegrationPrefersBundle:
    def test_init_prefers_single_file(self):
        s = INIT.read_text(encoding="utf-8")
        assert "lixiang-all.js" in s, "集成未使用单文件版"

    def test_init_falls_back_to_modules(self):
        s = INIT.read_text(encoding="utf-8")
        assert "_CARD_MODULES" in s, "缺多文件回退清单（老部署仍可用）"

    def test_shell_skips_defined_cards(self):
        s = SHELL.read_text(encoding="utf-8")
        assert "filter((name) => !customElements.get(name))" in s, (
            "外壳应跳过已被单文件定义的元素（否则重复 import 13 个文件）")


INTERNAL_CARDS = [
    "lixiang-app-home.js", "lixiang-charge-page.js", "lixiang-energy-page.js",
    "lixiang-health-page.js", "lixiang-setting-page.js", "lixiang-scene-page.js",
    "lixiang-climate-page.js", "lixiang-seat-page.js", "lixiang-location-page.js",
    "lixiang-vehicle-info-page.js", "lixiang-task-page.js", "lixiang-ad-page.js",
    "lixiang-bindings-card.js",
]
PUBLIC_CARDS = ["lixiang-app.js", "lixiang-overview-card.js"]


class TestCardPickerPolicy:
    """车主：「卡片选择器里只留两张」。

    单页卡（充电页/空调页/…）仍然是有用的自定义元素（YAML 直接写 type 即可），
    但不应占满 HA 的卡片选择器 —— 那会让新用户不知道该选哪个。
    """

    def test_public_cards_register_unconditionally(self):
        for name in PUBLIC_CARDS:
            s = (CARDS / name).read_text(encoding="utf-8")
            assert "if (!window.customCards.some" in s, (
                f"{name}: 对外卡片必须无条件注册到选择器")

    def test_internal_cards_hidden_by_default(self):
        for name in INTERNAL_CARDS:
            s = (CARDS / name).read_text(encoding="utf-8")
            assert "__LX_PICKER_ALL === true" in s, (
                f"{name}: 单页卡默认不应出现在卡片选择器（应加 __LX_PICKER_ALL 守卫）")

    def test_internal_cards_still_define_elements(self):
        """隐藏只是不列进选择器 —— 自定义元素仍要定义（YAML 可用）。"""
        for name in INTERNAL_CARDS:
            s = (CARDS / name).read_text(encoding="utf-8")
            assert "customElements.define" in s, f"{name}: 元素未被定义（YAML 用法会失效）"


class TestReleasePackaging:
    """发布包只含单文件（源 JS 不再随包提供）。"""

    def test_workflow_excludes_source_js(self):
        wf = ROOT / ".github" / "workflows" / "draft-release.yml"
        s = wf.read_text(encoding="utf-8")
        assert "lixiang-all.js" in s, "工作流未提及单文件"
        assert "-x" in s, "工作流未排除源 JS（发布包会同时含两套，体积翻倍）"

    def test_workflow_fails_if_bundle_missing(self):
        """单文件缺失要让 CI 失败 —— 否则会发布出"没有任何卡片"的包。"""
        wf = ROOT / ".github" / "workflows" / "draft-release.yml"
        s = wf.read_text(encoding="utf-8")
        assert "lixiang-all.js 缺失" in s, "缺单文件守卫（缺失时应让发布失败）"
