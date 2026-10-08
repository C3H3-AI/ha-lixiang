# -*- coding: utf-8
"""manifest 与仓库地址一致性守卫（2026-10-09）。

背景：仓库已迁至 **C3H3-AI/ha-lixiang**，但 `manifest.json` 里仍是旧组织名
`c3h3-ci`（该地址 HTTP 404）。而 manifest 的 `documentation` / `issue_tracker`
正是 **HACS 界面「文档 / 提交 Issue」按钮的跳转目标** —— 用户点进去就是 404。

本文件守卫：集成对外暴露的仓库地址必须指向真实存在的仓库，且与 README 一致。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_INTEG = _REPO / "custom_components" / "lixiang_auto"

#: 当前唯一的真实仓库（迁移后）
EXPECTED_OWNER = "C3H3-AI"
EXPECTED_REPO = "ha-lixiang"
EXPECTED_FULL = f"{EXPECTED_OWNER}/{EXPECTED_REPO}"

#: 已知的、已失效的旧组织名（不得再出现在对外可见的位置）
DEAD_OWNERS = ("c3h3-ci",)


def _manifest() -> dict:
    return json.loads((_INTEG / "manifest.json").read_text(encoding="utf-8"))


class TestManifestRepositoryUrl:
    def test_documentation_points_to_real_repo(self):
        """★ documentation 必须是真实仓库（HACS「文档」按钮的跳转目标）。"""
        man = _manifest()
        url = man.get("documentation") or ""
        assert EXPECTED_FULL in url, (
            f"documentation 未指向真实仓库: {url}（期望含 {EXPECTED_FULL}）")
        assert not any(d in url for d in DEAD_OWNERS), f"documentation 含失效组织名: {url}"

    def test_issue_tracker_points_to_real_repo(self):
        """★ issue_tracker 必须可用（HACS「提交 Issue」按钮）。"""
        man = _manifest()
        url = man.get("issue_tracker") or ""
        assert EXPECTED_FULL in url, f"issue_tracker 未指向真实仓库: {url}"
        assert not any(d in url for d in DEAD_OWNERS), f"issue_tracker 含失效组织名: {url}"

    def test_codeowner_is_current_owner(self):
        """codeowners 应为当前组织（否则 HA 会把 issue 指派给不存在的账号）。"""
        man = _manifest()
        owners = man.get("codeowners") or []
        assert owners, "codeowners 为空"
        joined = " ".join(owners)
        assert EXPECTED_OWNER.lstrip("@") in joined, f"codeowners 未含当前 owner: {owners}"
        assert not any(d in joined for d in DEAD_OWNERS), f"codeowners 含失效组织名: {owners}"

    def test_readme_matches_manifest_owner(self):
        """README 里的仓库地址应与 manifest 同一组织（避免两处不一致）。"""
        readme = (_REPO / "README.md").read_text(encoding="utf-8")
        man = _manifest()
        doc = man.get("documentation") or ""
        m = re.search(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", doc)
        assert m, f"无法解析 documentation: {doc}"
        owner, repo = m.group(1), m.group(2)
        assert f"github.com/{owner}/{repo}" in readme, (
            f"README 未出现 manifest 中的仓库 {owner}/{repo}")

    def test_no_dead_owner_anywhere_in_integration(self):
        """集成代码/配置里不得残留失效组织名。"""
        offenders: list[str] = []
        for path in list(_INTEG.rglob("*.json")) + list(_INTEG.rglob("*.yaml")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for dead in DEAD_OWNERS:
                if dead in text:
                    offenders.append(f"{path.relative_to(_REPO)}: {dead}")
        assert not offenders, f"仍残留失效组织名: {offenders}"
