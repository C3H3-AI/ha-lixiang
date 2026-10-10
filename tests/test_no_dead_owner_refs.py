"""失效旧组织名守卫（2026-10-10）。

背景
-----
仓库已迁到 **C3H3-AI/ha-lixiang**：旧名 `c3h3-ci` 与拼错的 `c3h3-bi` 都是 **404**。
但三个运维脚本的默认仓库名仍是旧名，造成两类长期静默故障：

  · `li-status.sh` 的 PR 查询 `head=c3h3-ci:<branch>` 永远查不到 →
    把「有 PR」误判成「分支未合并」→ 报出「main 分支保护未开启」假告警；
  · `li-pr.sh` 更严重：`head=c3h3-bi:<branch>`（旧名还拼错了一个字母），
    该查询从未成功过。

本文件两道守卫：
  ① **全仓库**（`git ls-files` 跟踪的文件）不得再出现失效组织名；
  ② **脚本里的 `head=` 查询**必须从 `$GH_REPO` 派生 owner，不得硬编码 ——
     这样仓库再次改名时不会再漂移。

注：本文件自己的探针字符串用拼接构造，避免自我命中。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 失效组织名（拼接构造，避免本文件自我命中）
DEAD = ("c3h3" + "-ci", "c3h3" + "-bi")

#: 有意记录失效组织名的文件 —— 它们的**测试目的**就是点名这个失效组织名：
#:   · test_manifest_urls.py    断言 manifest 不得指向它
#:   · test_no_dead_owner_refs.py 本文件（说明文字与断言消息里必然出现）
#:     注意：本文件的探针字符串用拼接构造（DEAD），所以只有文档/消息里才有字面量。
ALLOW_PATHS = {
    "tests/test_manifest_urls.py",
    "tests/test_no_dead_owner_refs.py",
    # CHANGELOG 是历史记录：修某个 bug 时会**叙述**到旧名（例如
    # 「脚本里仍是旧组织名 c3h3-ci」）。允许叙述，但**死链**照样禁止
    # —— 见下面的 test_no_dead_links。
    "CHANGELOG.md",
}

#: 死链形态：URL / API 路径 —— 任何文件都不许有（用户点进去 404）
DEAD_LINK_PATTERNS = (
    "github.com/{d}", "api.github.com/repos/{d}", "/repos/{d}/",
)
#: 脚本专属形态：查询里的 owner（head=<owner>:<branch>）—— 只在 .sh 里算死链，
#:  否则文档里解释这个 bug 时也会被误判。
DEAD_LINK_PATTERNS_SH = ("{d}:",)
#: 本文件必须能「点名」坏形态才能写守卫 → 扫描时跳过自己
LINK_SCAN_SKIP = {"tests/test_no_dead_owner_refs.py"}

#: 只扫文本类文件，跳过二进制/大文件噪音
_TEXT_SUFFIX = {
    ".py", ".sh", ".md", ".json", ".yml", ".yaml", ".txt", ".cfg",
    ".toml", ".html", ".js", ".css",
}


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    files = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        rel = Path(line)
        if rel.suffix.lower() in _TEXT_SUFFIX:
            files.append(rel)
    return files


class TestNoDeadOwnerReferences:
    def test_tracked_files_have_no_dead_owner(self):
        """★ 全仓库不得再出现失效组织名（脚本误报 / 文档死链的根因）。"""
        bad = []
        for rel in _tracked_text_files():
            if str(rel) in ALLOW_PATHS:
                continue
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                for dead in DEAD:
                    if dead in line:
                        bad.append(f"{rel}:{i}  {line.strip()[:100]}")
        assert not bad, (
            "发现失效旧组织名引用（仓库已迁至 C3H3-AI/ha-lixiang，"
            "c3h3-ci / c3h3-bi 均 404）：\n  " + "\n  ".join(bad[:20]))

    def test_no_dead_links(self):
        """★ 死链是真正伤用户的东西：任何跟踪文件都不许出现旧组织名的 URL。

        （与上一条的区别：CHANGELOG 里可以「叙述」旧名，但不能给出链接。）
        """
        bad = []
        for rel in _tracked_text_files():
            if str(rel) in LINK_SCAN_SKIP:
                continue
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
            pats = list(DEAD_LINK_PATTERNS)
            if rel.suffix == ".sh":
                pats += list(DEAD_LINK_PATTERNS_SH)
            for i, line in enumerate(text.splitlines(), 1):
                for dead in DEAD:
                    for pat in pats:
                        if pat.format(d=dead) in line:
                            bad.append(f"{rel}:{i}  {line.strip()[:100]}")
        assert not bad, (
            "发现失效组织名的死链（用户点进去 404）：\n  " + "\n  ".join(bad[:20]))

    def test_scripts_default_repo_is_current(self):
        """脚本默认仓库名必须是当前仓库，且 owner 与真实值一致。"""
        want = "C3H3-AI/ha-lixiang"
        for name in ("li-status.sh", "li-release.sh", "li-pr.sh"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            assert f'"${{LI_GH_REPO:-{want}}}"' in text, (
                f"{name} 的 LI_GH_REPO 默认值不是 {want}")

    def test_head_queries_derive_owner_from_gh_repo(self):
        """★ `head=<owner>:<branch>` 必须从 $GH_REPO 派生 owner。

        硬编码 owner 会在仓库改名/迁移后静默失效（li-pr.sh 曾写成
        `head=c3h3-bi:`，该查询从未成功）。
        """
        offenders = []
        for sh in sorted((ROOT / "scripts").glob("*.sh")):
            for i, line in enumerate(
                    sh.read_text(encoding="utf-8").splitlines(), 1):
                # 只看 PR 查询里的 head= 参数（排除 `head -n`、`ahead=` 等）
                if re.search(r"head=(?![$\{])[A-Za-z0-9_.-]+:", line):
                    offenders.append(f"{sh.name}:{i}  {line.strip()[:100]}")
        assert not offenders, (
            "head= 查询硬编码了 owner，应从 $GH_REPO 派生（${GH_REPO%%/*}）：\n  "
            + "\n  ".join(offenders))
