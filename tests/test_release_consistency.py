"""发布一致性守卫 —— 防止「改了版本号但忘了另一处」这类静默漂移。

背景
----
发布是「改 manifest + 写 CHANGELOG + 打 tag + 建 Release」四步。
`li-release.sh` 会校验 manifest 与 CHANGELOG 一致，但那只在【发布时】跑；
平时改代码时不一致没人拦 —— 等到发布才发现，或者更糟：发出去了才发现。

这里把这层校验挪到测试里，每次 CI 都跑。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components/lixiang_auto/manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def _manifest_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def _changelog_versions() -> list[str]:
    src = CHANGELOG.read_text(encoding="utf-8")
    return re.findall(r"^## \[(\d+\.\d+\.\d+[^\]]*)\]", src, re.M)


class TestVersionConsistency:
    def test_manifest_version_in_changelog(self):
        """★ manifest 的版本必须在 CHANGELOG 里有对应段落。"""
        ver = _manifest_version()
        versions = _changelog_versions()
        assert ver in versions, (
            f"manifest 版本 {ver} 在 CHANGELOG 里没有对应段落。\n"
            f"CHANGELOG 现有版本（前 5 个）: {versions[:5]}\n"
            f"→ 发布前必须补上 CHANGELOG 段落，否则 Release 正文会是空的。"
        )

    def test_latest_changelog_matches_manifest(self):
        """CHANGELOG 最上面一段必须就是当前版本（不能落后）。"""
        ver = _manifest_version()
        versions = _changelog_versions()
        assert versions, "CHANGELOG 里没有任何版本段落"
        assert versions[0] == ver, (
            f"CHANGELOG 最新段落是 {versions[0]}，但 manifest 是 {ver}。\n"
            f"→ 两者必须一致；否则说明版本号只改了一处。"
        )

    def test_semver_format(self):
        """版本号必须是合法的 x.y.z（可带预发布后缀）。"""
        ver = _manifest_version()
        assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.\-]+)?", ver), (
            f"版本号 {ver!r} 不是合法的语义化版本"
        )

    def test_changelog_versions_are_semver(self):
        for v in _changelog_versions():
            assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.\-]+)?", v), (
                f"CHANGELOG 里的版本 {v!r} 不是合法语义化版本"
            )


class TestChangelogStructure:
    def test_has_heading(self):
        src = CHANGELOG.read_text(encoding="utf-8")
        assert src.startswith("# 更新日志"), "CHANGELOG 必须有一级标题"

    def test_versions_are_ordered_newest_first(self):
        """版本段落必须【从新到旧】排列（否则发布脚本抽正文会抽错）。"""
        versions = _changelog_versions()

        def key(v: str):
            core = v.split("-")[0]
            return tuple(int(x) for x in core.split("."))

        keys = [key(v) for v in versions]
        assert keys == sorted(keys, reverse=True), (
            f"CHANGELOG 版本段落顺序不对（应新→旧）: {versions[:6]}"
        )

    def test_each_version_has_content(self):
        """每个版本段落不能是空的（至少要有说明）。"""
        src = CHANGELOG.read_text(encoding="utf-8")
        parts = re.split(r"^## \[", src, flags=re.M)[1:]
        for p in parts:
            ver = p.split("]")[0]
            body = p.split("\n", 1)[1] if "\n" in p else ""
            body = body.split("## [")[0].strip()
            assert len(body) > 40, (
                f"版本 {ver} 的 CHANGELOG 段落内容过少（{len(body)} 字符）—— "
                "Release 正文会显得空洞"
            )


class TestReleaseScriptChecks:
    """发布脚本自身也必须有这些校验（双保险）。"""

    def test_release_script_exists(self):
        assert (ROOT / "scripts/li-release.sh").exists()

    def test_release_script_validates_manifest(self):
        src = (ROOT / "scripts/li-release.sh").read_text(encoding="utf-8")
        assert "manifest" in src, "发布脚本必须校验 manifest 版本"

    def test_release_script_validates_changelog(self):
        src = (ROOT / "scripts/li-release.sh").read_text(encoding="utf-8")
        assert "CHANGELOG" in src, "发布脚本必须校验 CHANGELOG"

    def test_release_script_does_not_guess_version(self):
        """★ 版本号是维护者的决定 —— 脚本不许自动 bump。"""
        src = (ROOT / "scripts/li-release.sh").read_text(encoding="utf-8")
        assert "不猜版本" in src or "不自动 bump" in src, (
            "脚本必须明确「不猜版本」这个设计原则"
        )
