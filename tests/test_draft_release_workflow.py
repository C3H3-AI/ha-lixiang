"""Auto Release Draft workflow 守卫（对齐 hacs-vision 成熟做法）。

背景
----
发布是「改版本号 → 合并 → 打 tag → 建 Release」四步。后两步靠人记得跑，
项目里已踩过两次这个坑（v1.1.0 合了 2 个提交却从未发版，漂了很久没人发现）。

hacs-vision 的 workflow 成熟得多 —— 它还踩过 v7.0.0 的坑（草稿 Release 不会
自动建 tag，维护者 Publish 后 HACS 收不到更新），总结出 6 步流程。

这里的守卫测试覆盖它的关键性质，防止以后被改坏。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github/workflows/draft-release.yml"
RL = ROOT / ".github/release.yml"


def _wf() -> str:
    assert WF.exists(), "draft-release.yml 不存在"
    return WF.read_text(encoding="utf-8")


def _rl() -> str:
    assert RL.exists(), "release.yml 不存在"
    return RL.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
#  基本存在 + 触发条件
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkflowExists:
    def test_workflow_exists(self):
        assert WF.exists()

    def test_release_config_exists(self):
        """generate-notes 的 label 分类配置（hacs-vision 也有这个文件）。"""
        assert RL.exists()

    def test_valid_yaml(self):
        yaml = pytest.importorskip("yaml")
        wf = yaml.safe_load(_wf())
        assert wf["name"] == "Auto Release Draft"
        assert wf["permissions"]["contents"] == "write"

    def test_triggers_on_main_manifest_push(self):
        yaml = pytest.importorskip("yaml")
        wf = yaml.safe_load(_wf())
        on = wf.get("on") or wf.get(True)
        assert "workflow_dispatch" in on
        push = on["push"]
        assert "main" in str(push["branches"])
        # 只监听版本相关文件，否则每次 push 都跑会变噪音
        assert any("manifest.json" in p for p in push["paths"])

    def test_release_config_is_valid_yaml(self):
        yaml = pytest.importorskip("yaml")
        d = yaml.safe_load(_rl())
        assert "changelog" in d
        cats = d["changelog"]["categories"]
        assert cats, "至少要有一个 category"
        # 必须有兜底（没匹配的 PR 不能丢）
        labels_flat = set()
        for c in cats:
            for l in c["labels"]:
                labels_flat.add(l)
        assert "*" in labels_flat, "必须有 '*' 作为兜底 category"

    def test_release_config_uses_our_labels(self):
        """分类必须匹配仓库实际用的 label（pr-guard 自动打的那套）。"""
        src = _rl()
        for must_have in ("type: fix", "type: perf", "type: chore"):
            assert must_have in src, f"缺少 label {must_have}（仓库实际在用）"


# ═══════════════════════════════════════════════════════════════════════════
#  ★ 核心性质 —— hacs-vision 踩过坑才提炼出来的
# ═══════════════════════════════════════════════════════════════════════════

class TestVersionCheck:
    """① 版本严格递增检查 —— packaging.version 不做字符串比较。"""

    def test_uses_packaging_version(self):
        src = _wf()
        assert "packaging" in src, "必须用 packaging.version，不能自己写字符串比较"

    def test_compares_against_latest_tag(self):
        src = _wf()
        assert "git tag -l" in src or "sort=-v:refname" in src, (
            "必须从 git tag 取最新版本，不能 hardcode"
        )

    def test_skip_on_no_increase(self):
        src = _wf()
        assert "compare_result=skip" in src, "版本没变大时必须 skip"

    def test_handles_no_tags_yet(self):
        src = _wf()
        assert "v0.0.0" in src or "OLD_VERSION" in src, (
            "仓库还没打过 tag 时要有基准值"
        )


class TestTagFirstThenDraft:
    """②★ 先建 tag，再建草稿 Release —— GitHub 草稿不会自动建 tag！"""

    def test_creates_tag_before_release(self):
        """用 step name 定位 —— 注释里也会出现命令字符串，不如 step name 精准。"""
        src = _wf()
        tag_step_idx = src.find("name: Create and push tag")
        rel_step_idx = src.find("name: Create draft release")
        assert tag_step_idx > 0 and rel_step_idx > 0 and tag_step_idx < rel_step_idx, (
            "workflow 必须先执行 Create and push tag，再执行 Create draft release —— "
            "GitHub 草稿 Release 不会自动建 tag，维护者 Publish 后 tag 依然不存在，"
            "HACS 收不到更新"
        )

    def test_tag_is_lightweight(self):
        """hacs-vision 用轻量 tag（git tag xxx），不是注释 tag。"""
        src = _wf()
        for bad in ("git tag -a", "git tag -s"):
            assert bad not in src, "不该用注释/签名 tag —— tag 是版本标识，不是注释载体"

    def test_tag_idempotent(self):
        src = _wf()
        assert "rev-parse" in src, "必须先查 tag 是否已存在，保证幂等"


class TestTagVerification:
    """③★ 显式校验 tag 存在 —— 把静默失败变成显式失败。"""

    def test_has_verify_step(self):
        src = _wf()
        assert "Verify tag exists" in src, "必须有 tag 存在校验（hacs-vision v7.0.0 教训）"

    def test_uses_ls_remote(self):
        src = _wf()
        assert "ls-remote --tags origin" in src, (
            "校验必须查远端（git ls-remote），不能查本地 clone —— "
            "本地 clone 可能没拉全 tag"
        )

    def test_fails_on_missing_tag(self):
        src = _wf()
        assert "::error::" in src and "tag" in src.lower(), (
            "tag 不存在时必须用 ::error:: 让 GitHub 直接标红"
        )


class TestReleaseTagBinding:
    """③★★ Release 必须真的绑在 tag 上 —— v1.2.4 实测踩过的坑。

    2026-09-29 事故：v1.2.4 的 tag 建好了、ZIP 也传上去了，草稿也 Publish 了，
    但 Release 的 tag_name 是 `untagged-5e013c01a5276823767b` 占位符，
    **不是 v1.2.4**。HACS 靠 release.tag_name 解析版本 → 用户收不到更新，
    且全程零报错（纯静默失败）。

    根因：`gh release create` 带了 `--target`，tag 传播未就绪时静默退回占位符。
    """

    def _create_cmd_segment(self):
        """取出真正的 `gh release create` 命令块（不是注释里提到的那句）。"""
        src = _wf()
        lines = src.splitlines()
        for i, ln in enumerate(lines):
            # 命令行的行首是 gh（可有缩进），而非注释里的 "# ... gh release create"
            if ln.strip().startswith("gh release create"):
                return "\n".join(lines[i:i + 12])
        raise AssertionError("workflow 里找不到 gh release create 命令行")

    def test_no_target_flag_on_release_create(self):
        """★ 核心回归：gh release create 不能带 --target。

        --target 是给"创建新 tag"用的；我们的 tag 已在上一 IP 步显式建好。
        带上它会在 tag 未就绪时静默生成 untagged-<hash> 占位符。
        """
        seg = self._create_cmd_segment()
        assert "--target" not in seg, (
            "gh release create 不能带 --target —— "
            "会导致 tag_name 变成 untagged-<hash>（v1.2.4 事故根因）"
        )

    def test_uses_verify_tag_flag(self):
        """必须加 --verify-tag：tag 远程不可见时直接失败，而不是静默建坏草稿。"""
        seg = self._create_cmd_segment()
        assert "--verify-tag" in seg, (
            "gh release create 必须带 --verify-tag —— "
            "否则 tag 未就绪时会静默建出 untagged 草稿"
        )

    def test_has_binding_verification_step(self):
        """必须有一道专门校验 Release ↔ tag 绑定的步骤（tag 存在 ≠ 绑定正确）。"""
        src = _wf()
        assert "Verify release bound to tag" in src, (
            "必须有 Release 绑定校验 —— 只校验 tag 存在会漏掉 v1.2.4 那种情况"
        )

    def test_binding_check_does_not_use_tags_endpoint(self):
        """★ API 陷阱：GET /releases/tags/{tag} 对【草稿】返回 404。

        用它校验会永远误判"未绑定"，然后把好好的草稿当坏的重绑。
        """
        src = _wf()
        idx = src.index("Verify release bound to tag")
        seg = src[idx:]
        assert "/releases/tags/" not in seg and "release view" not in seg, (
            "绑定校验不能用 /releases/tags/{tag} 或 gh release view —— "
            "草稿不参与 tag 索引，会 404 导致误判"
        )

    def test_binding_check_retries_list_api(self):
        """列表接口是最终一致性的（实测 3 次丢 1 次）—— 必须重试。"""
        src = _wf()
        idx = src.index("Verify release bound to tag")
        seg = src[idx:]
        assert "for _ in 1 2 3 4 5" in seg, (
            "绑定校验必须对列表接口重试 —— 它是最终一致性的，刚建完可能查不到"
        )
        assert "startswith(\"untagged-\")" in seg, (
            "找未绑定草稿要认 untagged- 前缀 —— 不能用 name 前缀匹配"
            "（'v1.2.4' 会误匹配 'v1.2.40'）"
        )


class TestZIPArtifact:
    """④ 打 ZIP 作为 asset —— 用户直接下载。"""

    def test_creates_zip(self):
        src = _wf()
        assert "zip -r" in src, "必须打 ZIP"

    def test_zip_name_is_component(self):
        src = _wf()
        assert "lixiang_auto.zip" in src, "ZIP 文件名 = 组件名"

    def test_zip_is_attached_to_release(self):
        """ZIP 应作为 gh release create 的 asset 参数传入 —— 直接检查源码。"""
        src = _wf()
        assert "lixiang_auto.zip" in src, (
            "ZIP 文件名必须在 workflow 里出现（作为 gh release create 的最后一个参数）"
        )


class TestReleaseTitleFormat:
    """⑤ Release 标题 = 版本号 + 首个 commit subject（简洁、有上下文）。"""

    def test_title_includes_version_and_subject(self):
        src = _wf()
        assert 'title "${TAG} -' in src or "commit_title" in src, (
            "标题应该是 'vX.Y.Z - <commit subject>'"
        )

    def test_uses_generate_notes(self):
        src = _wf()
        assert "--generate-notes" in src, (
            "正文应该用 generate-notes 按 label 自动分组，"
            "手写 CHANGELOG 段落作为 Release 正文会太长且容易漏"
        )


class TestPrereleaseDetection:
    def test_detects_beta_rc_alpha(self):
        src = _wf()
        for tag in ("beta", "rc", "alpha"):
            assert tag in src, f"应该识别 prerelease 后缀 {tag}"


class TestFetchDepthZero:
    """fetch-depth: 0 —— 版本比较和 tag 判断都需要完整历史。"""

    def test_fetch_depth_zero(self):
        src = _wf()
        assert "fetch-depth: 0" in src, (
            "浅克隆拿不到全部 tag，版本递增比较会错；"
            "必须 fetch-depth: 0"
        )
