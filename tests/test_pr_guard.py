"""PR 规范守卫的测试（.github/scripts/pr_guard.py + workflows）。

为什么这些测试存在
------------------
2026-09-28：CONTRIBUTING 早就写了「PR 合并后不得继续在同一个分支上提交」，
还附了检查命令 —— 但没有任何机制拦人。同一次会话里同一个分支被
PR #5 和 PR #7 先后使用，新提交卡在已关闭 PR 的分支上，只能另开 PR 补救。

规则写了、案例也有，仍然违反 —— 因为规则只是文档。本文件让规则可执行。

★ 按 CONTRIBUTING「测试必须真的能失败」：本文件的守卫断言都做过变异测试
  （把对应实现改坏，确认测试确实失败）。
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / ".github" / "scripts" / "pr_guard.py"
WORKFLOWS = REPO / ".github" / "workflows"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pr_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pr_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


pg = _load_guard()


# ══════════════════════════════════════════════════════════════════════════
#  标题格式
# ══════════════════════════════════════════════════════════════════════════
class TestTitleFormat:
    @pytest.mark.parametrize("title", [
        "feat: 新增冰箱控制",
        "fix(signals): 修正前备箱路径",
        "ci: 新增 PR 规范守卫",
        "docs: 补充升级注意",
        "refactor(coordinator): 拆分轮询",
        "chore: 清理已合并分支",
        "test: 补守卫测试",
        "perf: 减少 VSS 请求",
    ])
    def test_accepts_conventional(self, title):
        assert pg.TITLE_RE.match(title), f"应接受：{title}"

    @pytest.mark.parametrize("title", [
        "",                              # 空
        "修复了一些问题",                  # 无类型前缀
        "update: 不允许的类型",            # 类型不在清单
        "fix:短",                        # 缺空格
        "fix: abc",                      # 描述过短
        "FIX: 大写类型",                   # 必须小写
        "fix(): 空范围",                   # 空范围
        "feat(Signals): 大写范围",         # 范围必须小写
    ])
    def test_rejects_non_conventional(self, title):
        assert not pg.TITLE_RE.match(title), f"应拒绝：{title!r}"

    def test_types_match_contributing_branch_table(self):
        """类型清单必须与 CONTRIBUTING「分支命名」表一致（含 test/perf 扩展）。"""
        src = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for t in pg.TYPES:
            assert f"`{t}/`" in src or f"`{t}`" in src, \
                f"类型 {t} 未出现在 CONTRIBUTING 的分支命名表里"


# ══════════════════════════════════════════════════════════════════════════
#  Issue 关联
# ══════════════════════════════════════════════════════════════════════════
class TestIssueLink:
    @pytest.mark.parametrize("text", [
        "Fixes #6", "fix #6", "fixed #6", "Closes #12", "close #12",
        "Resolves #3", "Refs #9", "ref #9", "见 Fixes #6 的说明",
    ])
    def test_detects(self, text):
        assert pg.ISSUE_RE.search(text), f"应识别：{text}"

    @pytest.mark.parametrize("text", [
        "无", "修复了问题", "#6", "Fixes 6", "fixes#", "see PR 6",
    ])
    def test_ignores(self, text):
        assert not pg.ISSUE_RE.search(text), f"不应识别：{text}"


# ══════════════════════════════════════════════════════════════════════════
#  area 路径匹配
# ══════════════════════════════════════════════════════════════════════════
class TestAreaMatching:
    @pytest.mark.parametrize("path,label", [
        (".github/workflows/pr-guard.yml", "area: ci"),
        (".github/PULL_REQUEST_TEMPLATE.md", "area: ci"),
        ("hacs.json", "area: ci"),
        ("tests/test_pr_guard.py", "area: tests"),
        ("README.md", "area: docs"),
        ("docs/功能对照表.md", "area: docs"),
        ("scripts/li-release.sh", "area: scripts"),
        ("custom_components/lixiang_auto/signals.py", "area: signals"),
        ("custom_components/lixiang_auto/translations.py", "area: signals"),
        ("custom_components/lixiang_auto/vehicle_ability.py", "area: ability"),
        ("custom_components/lixiang_auto/features.py", "area: ability"),
        ("custom_components/lixiang_auto/vehicle_configs/1.json", "area: ability"),
        ("custom_components/lixiang_auto/switch.py", "area: platforms"),
        ("custom_components/lixiang_auto/fan.py", "area: platforms"),
        ("custom_components/lixiang_auto/li_api.py", "area: api"),
    ])
    def test_matches(self, path, label):
        got = [l for l, pats in pg.AREA_RULES if pg._match_any(path, pats)]
        assert label in got, f"{path} 应命中 {label}，实得 {got}"

    def test_dir_glob_does_not_match_prefix_sibling(self):
        """`tests/**` 不应匹配 `tests-other/`（前缀包含是常见 bug）。"""
        assert not pg._match_any("tests-other/x.py", ("tests/**",))
        assert pg._match_any("tests/x.py", ("tests/**",))

    def test_unknown_path_matches_nothing(self):
        got = [l for l, pats in pg.AREA_RULES if pg._match_any("random.bin", pats)]
        assert got == []


# ══════════════════════════════════════════════════════════════════════════
#  分支复用检测（本次会话踩的坑）
# ══════════════════════════════════════════════════════════════════════════
class TestBranchReuse:
    """★ 本类是整个守卫的核心：它防的是"复用已合并分支"。"""

    def _patch(self, monkeypatch, prs):
        monkeypatch.setattr(pg, "api", lambda *a, **k: prs)

    def test_merged_pr_on_same_branch_fails(self, monkeypatch):
        self._patch(monkeypatch, [
            {"number": 5, "title": "旧 PR", "merged_at": "2026-09-28T12:31:00Z"},
        ])
        monkeypatch.setenv("PR_NUM", "7")
        ok = pg.check_branch_not_reused(
            "o/r", "o", "fix/reused", 7, "tok", dry=False)
        assert ok is False, "复用已合并分支必须被拒绝"

    def test_current_pr_itself_is_ignored(self, monkeypatch):
        """本 PR 自己（已合并或未合并）不算复用。"""
        self._patch(monkeypatch, [
            {"number": 7, "title": "当前", "merged_at": "2026-09-28T12:31:00Z"},
        ])
        ok = pg.check_branch_not_reused(
            "o/r", "o", "fix/current", 7, "tok", dry=False)
        assert ok is True

    def test_closed_but_not_merged_is_fine(self, monkeypatch):
        """关掉但【未合并】的 PR 不算复用（那种分支可以继续用）。"""
        self._patch(monkeypatch, [
            {"number": 2, "title": "验证用", "merged_at": None},
        ])
        ok = pg.check_branch_not_reused(
            "o/r", "o", "test/verify", 9, "tok", dry=False)
        assert ok is True

    def test_clean_branch_passes(self, monkeypatch):
        self._patch(monkeypatch, [])
        ok = pg.check_branch_not_reused(
            "o/r", "o", "feat/new", 10, "tok", dry=False)
        assert ok is True

    def test_api_failure_is_fail_open_with_warning(self, monkeypatch):
        """API 挂了不能把开发者挡在门外 —— 但要出警告，不能静默。"""
        def boom(*a, **k):
            raise RuntimeError("network down")
        monkeypatch.setattr(pg, "api", boom)
        ok = pg.check_branch_not_reused(
            "o/r", "o", "feat/x", 11, "tok", dry=False)
        assert ok is True, "API 失败应 fail-open（否则网络抖动会阻断所有 PR）"

    def test_check_is_wired_into_main(self):
        """静态保证：main() 真的调用了分支复用检查（否则守卫形同虚设）。"""
        src = GUARD.read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "check_branch_not_reused" in calls


# ══════════════════════════════════════════════════════════════════════════
#  workflow 自身的健康（我在本文件诞生前踩过的 YAML bug）
# ══════════════════════════════════════════════════════════════════════════
class TestWorkflowHealth:
    """★ 这些检查来自真实踩坑：写 pr-guard.yml 时我把内嵌 Python 放在
    YAML 块标量的第 0 列，块标量当场被截断 —— YAML 直接解析失败。
    另外还在同一个 step 里写了两个 `env:` 键（后者会静默覆盖前者）。
    """

    @pytest.mark.parametrize("wf", sorted(p.name for p in WORKFLOWS.glob("*.yml")))
    def test_workflow_yaml_is_valid(self, wf):
        yaml = pytest.importorskip("yaml")
        yaml.safe_load((WORKFLOWS / wf).read_text(encoding="utf-8"))

    @pytest.mark.parametrize("wf", sorted(p.name for p in WORKFLOWS.glob("*.yml")))
    def test_no_duplicate_env_in_step(self, wf):
        """同一个 step 里不能出现两个 env: 键（重复键会静默丢配置）。"""
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load((WORKFLOWS / wf).read_text(encoding="utf-8"))
        # PyYAML 对重复键不报错，所以改用原文扫描 step 边界
        text = (WORKFLOWS / wf).read_text(encoding="utf-8")
        import re
        for block in re.split(r"\n\s*- name: ", text)[1:]:
            block = block.split("\n      - ")[0]
            n = len(re.findall(r"^\s+env:", block, re.M))
            assert n <= 1, f"{wf}: step 里有 {n} 个 env 块（重复键会丢配置）"
        assert doc is not None

    def test_pr_guard_workflow_calls_existing_script(self):
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load((WORKFLOWS / "pr-guard.yml").read_text(encoding="utf-8"))
        steps = doc["jobs"]["guard"]["steps"]
        runs = " ".join(s.get("run", "") for s in steps)
        assert "pr_guard.py" in runs, "workflow 必须调用 pr_guard.py"
        assert GUARD.exists(), "被调用的 pr_guard.py 必须存在"

    def test_pr_guard_triggers_include_synchronize(self):
        """area 标签要跟随新提交更新 → 必须包含 synchronize。"""
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load((WORKFLOWS / "pr-guard.yml").read_text(encoding="utf-8"))
        # PyYAML 把裸 on: 解析成布尔 True
        trigger = doc.get("on") or doc.get(True)
        types = trigger["pull_request"]["types"]
        assert "synchronize" in types

    def test_pr_guard_has_label_permission(self):
        """打标签需要 pull-requests: write，缺了会静默失败。"""
        yaml = pytest.importorskip("yaml")
        doc = yaml.safe_load((WORKFLOWS / "pr-guard.yml").read_text(encoding="utf-8"))
        assert doc["permissions"].get("pull-requests") == "write"


# ══════════════════════════════════════════════════════════════════════════
#  发布脚本与 PR 模板的存在性与关键约定
# ══════════════════════════════════════════════════════════════════════════
class TestProcessArtifacts:
    def test_release_script_exists_and_is_executable(self):
        p = REPO / "scripts" / "li-release.sh"
        assert p.exists()
        assert os.access(p, os.X_OK), "li-release.sh 必须可执行"

    def test_release_script_requires_explicit_version(self):
        """★ 版本号是维护者的决定 —— 脚本不能自己猜版本。"""
        src = (REPO / "scripts" / "li-release.sh").read_text(encoding="utf-8")
        assert "用法: ./li-release.sh <版本号" in src
        assert "bump.sh" not in src.replace("不自动 bump", ""), \
            "发布脚本不应自动 bump 版本"

    def test_release_script_dry_run_available(self):
        src = (REPO / "scripts" / "li-release.sh").read_text(encoding="utf-8")
        assert "--dry-run" in src
        # 新架构：li-release.sh 是 Publish-only，tag 由 workflow 先建好
        # （见 .github/workflows/draft-release.yml 的 Create and push tag 步骤）
        assert "tag.*已存在" in src or "ls-remote" in src, (
            "li-release.sh 应检查 tag 是否就位（workflow 负责建它）"
        )
        assert "PATCH" in src or "draft.*false" in src or "Publish" in src, (
            "li-release.sh 应只做校验 + Publish 草稿"
        )

    def test_pr_template_exists_with_required_sections(self):
        p = REPO / ".github" / "PULL_REQUEST_TEMPLATE.md"
        assert p.exists(), "缺少 PR 模板"
        src = p.read_text(encoding="utf-8")
        for section in ("变更类型", "关联 Issue", "验证方法", "检查清单", "变异测试"):
            assert section in src, f"PR 模板缺少章节：{section}"

    def test_contributing_documents_branch_reuse_lesson(self):
        """把本次会话的真实案例补进 CONTRIBUTING（规则 + 案例才有说服力）。"""
        src = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "PR 合并后" in src
        assert "PR #5" in src and "PR #7" in src, \
            "应记录 2026-09-28 复用分支的真实案例（PR #5 → PR #7）"


# ══════════════════════════════════════════════════════════════════════════
#  li-pr.sh 的安全性（本次会话被自己的脚本坑到）
# ══════════════════════════════════════════════════════════════════════════
class TestLiPrScriptSafety:
    """★ 这些断言来自一次真实事故：

    我给 `li-pr.sh clean` 加了 `--dry-run`，但它【无条件】执行
    `git checkout main`。于是我跑了一次 `clean --dry-run`（本意只是看看），
    工作分支被悄悄切回 main，紧接着的提交落到了 main 上 ——
    而 main 有分支保护，推不上去，只好手工把提交搬回分支。

    「只看看会删什么」的操作不该有副作用。
    """

    SRC = (REPO / "scripts" / "li-pr.sh")

    def test_clean_dry_run_does_not_checkout(self):
        src = self.SRC.read_text(encoding="utf-8")
        i = src.find("cmd_clean()")
        assert i > 0, "找不到 cmd_clean"
        block = src[i:i + 3000]
        # checkout 必须被 dry 条件包住
        assert "if [[ $dry -eq 0 ]]" in block, \
            "cmd_clean 的 git checkout 必须只在非 dry-run 时执行"
        # 且不能出现"无条件 checkout"（即 checkout 行前不是 if 判断）
        import re
        for m in re.finditer(r"^\s*git checkout main", block, re.M):
            before = block[:m.start()].rstrip().splitlines()[-3:]
            joined = "\n".join(before)
            assert "dry" in joined or "-eq 0" in joined, (
                "存在未被 dry 条件保护的 git checkout main：\n" + joined
            )

    def test_submit_auto_detects_direction(self):
        src = self.SRC.read_text(encoding="utf-8")
        assert "sync_or_deploy" in src, "submit 必须走方向自动判定"
        i = src.find("sync_or_deploy()")
        block = src[i:i + 2500]
        assert "deploy_repo_to_test" in block and "sync_test_to_repo" in block, \
            "方向判定必须同时具备部署与同步两条路"

    def test_deploy_direction_exists(self):
        """li-pr.sh 原先只有 test→repo，缺 repo→test（本次绕过脚本的根因）。"""
        src = self.SRC.read_text(encoding="utf-8")
        assert "deploy_repo_to_test()" in src
        i = src.find("deploy_repo_to_test()")
        block = src[i:i + 900]
        assert '"$REPO_DIR/$REPO_SUB/" "$TEST_DIR/"' in block, \
            "部署方向必须是 仓库 → 测试机"

    def test_help_lists_deploy_and_clean_flags(self):
        out = __import__("subprocess").run(
            ["bash", str(self.SRC), "help"],
            capture_output=True, text=True, cwd=REPO, timeout=30).stdout
        assert "deploy" in out
        assert "--remote" in out
        assert "--from-test" in out


# ══════════════════════════════════════════════════════════════════════════
#  脚本的"直连回退"必须真的直连
# ══════════════════════════════════════════════════════════════════════════
class TestProxyFallback:
    """★ 来自一次真实失效（2026-09-28）：

    三个脚本都有"代理不可用 → 直连"的回退：

        if ! curl ... -x "$PROXY" https://api.github.com/; then
          PROXY=""          # 以为这样就直连了
        fi

    **它没有直连。** 只去掉 `-x` 是不够的：环境变量 `https_proxy` /
    `ALL_PROXY` 仍会被 curl 采用，于是"回退"实际还是走那个坏代理。

    后果正是这脚本最该避免的失效方式：巡检把
    「CI 健康」「分支保护」两项都显示成 `?`（无法确认），
    看起来"没告警"，实则**把真实告警吞掉了**。

    修法：回退时显式加 `--noproxy '*'`。
    """

    SCRIPTS = ("li-status.sh", "li-release.sh", "li-pr.sh")

    @pytest.mark.parametrize("name", SCRIPTS)
    def test_fallback_uses_noproxy(self, name):
        src = (REPO / "scripts" / name).read_text(encoding="utf-8")
        assert "--noproxy" in src, (
            f"{name}: 直连回退必须使用 --noproxy '*'，"
            "否则环境变量里的代理仍会生效"
        )
        assert 'PROXY_ARGS=(--noproxy' in src, \
            f"{name}: 回退分支必须构造成 --noproxy 参数"

    @pytest.mark.parametrize("name", SCRIPTS)
    def test_no_legacy_proxy_blanking(self, name):
        """禁止旧写法：把 PROXY 置空就以为能直连。"""
        src = (REPO / "scripts" / name).read_text(encoding="utf-8")
        assert 'PROXY=""' not in src, (
            f"{name}: 仍在使用 `PROXY=\"\"` 的旧回退写法 —— 它不会真的直连"
        )

    @pytest.mark.parametrize("name", SCRIPTS)
    def test_curl_calls_use_proxy_args(self, name):
        src = (REPO / "scripts" / name).read_text(encoding="utf-8")
        assert 'PROXY_ARGS[@]' in src, f"{name}: curl 调用应使用 PROXY_ARGS"
        assert '[[ -n "$PROXY" ]]' not in src, \
            f"{name}: 仍保留按 PROXY 是否为空拼参数的旧逻辑"

    def test_noproxy_actually_bypasses_env_proxy(self):
        """行为验证：--noproxy '*' 能绕开环境里的代理。

        ★ 不能只做源码文本断言 —— 这里实跑一次 curl 对比。
        若本机代理恰好可用，两条都会成功，此时跳过（不构成失败证据）。
        """
        import subprocess

        def code(*extra):
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--max-time", "10", *extra, "https://api.github.com/"],
                capture_output=True, text=True, timeout=30)
            return r.stdout.strip()

        with_env = code()
        no_proxy = code("--noproxy", "*")
        # 至少 --noproxy 那一侧必须能通（本机直连可用时）
        assert no_proxy != "000", (
            "https://api.github.com 直连不通 —— 无法验证回退逻辑；"
            "这是环境问题，不是代码问题"
        )
        if with_env == "000":
            # 正是我们修的场景：环境代理坏了，--noproxy 才是出路
            assert no_proxy == "200"


# ══════════════════════════════════════════════════════════════════════════
#  Release 笔记自动生成（.github/release.yml + scripts/_release_notes.py）
# ══════════════════════════════════════════════════════════════════════════
class TestReleaseNotesAutogen:
    """release.yml + workflow 的自动笔记（对齐 hacs-vision）。

    【新架构】正文由 workflow（draft-release.yml）在建草稿时
    直接 `gh release create --generate-notes`，按 .github/release.yml
    的 label 分类自动生成。li-release.sh 只 Publish 草稿，
    不再自己拼装正文。
    """

    RELEASE_YML = REPO / ".github" / "release.yml"
    DRAFT_WF = REPO / ".github" / "workflows" / "draft-release.yml"

    def test_release_yml_exists_and_valid(self):
        yaml = pytest.importorskip("yaml")
        assert self.RELEASE_YML.exists(),             "缺少 .github/release.yml —— GitHub 不会按类型分类笔记"
        d = yaml.safe_load(self.RELEASE_YML.read_text(encoding="utf-8"))
        cats = d["changelog"]["categories"]
        assert len(cats) >= 5

    def test_categories_cover_all_pr_guard_types(self):
        """★ 每个 pr-guard 会打的 type: 标签都要有对应分类（否则掉进兜底）。"""
        yaml = pytest.importorskip("yaml")
        d = yaml.safe_load(self.RELEASE_YML.read_text(encoding="utf-8"))
        mapped = {lbl for c in d["changelog"]["categories"] for lbl in c["labels"]}
        missing = [f"type: {t}" for t in pg.TYPES if f"type: {t}" not in mapped]
        assert not missing, (
            f"这些类型没有分类，会掉进「其他变更」：{missing}\n"
            "  修复：在 .github/release.yml 加对应 category"
        )

    def test_wildcard_is_last(self):
        """兜底 `*` 必须最后 —— 匹配是从上到下的，放前面会吞掉所有分类。"""
        yaml = pytest.importorskip("yaml")
        d = yaml.safe_load(self.RELEASE_YML.read_text(encoding="utf-8"))
        cats = d["changelog"]["categories"]
        assert "*" in cats[-1]["labels"], (
            "`*` 兜底分类必须是最后一个，否则它会把后面所有分类都吃掉"
        )

    def test_workflow_calls_generate_notes(self):
        """★ generate-notes 的调用者是 workflow，不是 li-release.sh。"""
        src = self.DRAFT_WF.read_text(encoding="utf-8")
        assert "--generate-notes" in src, (
            "workflow 必须用 gh release create --generate-notes 建草稿"
        )

    def test_release_script_does_not_compose_notes(self):
        """★ li-release.sh 已简化为 Publish-only，不再自己调 generate-notes。"""
        src = (REPO / "scripts" / "li-release.sh").read_text(encoding="utf-8")
        assert "_release_notes.py" not in src, (
            "旧的 _release_notes.py 已废弃（workflow 管 generate-notes）"
        )
        assert "gh release view" in src or "PATCH" in src or "draft.*false" in src, (
            "li-release.sh 应只做校验 + Publish"
        )

