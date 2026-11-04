"""li-release.sh 的发布行为测试（2026-11-05）。

背景（真事故，第三次同类）
--------------------------
2026-11-03 发 v1.7.0 时，发布动作被拆成**两次** PATCH：
    ① {body, name}      ← 改正文/标题
    ② {draft, prerelease} ← 真正发布
结果 Release 的 tag_name 变成 `untagged-640294d359182fa43447`，
而 tag `v1.7.0` 明明存在。HACS 靠 release.tag_name 识别版本
→ **用户静默收不到更新，零报错**。

对照：v1.6.2-beta.3 / beta.4 只 PATCH 一次（仅 draft/pre）→ 正常。
历史：v1.2.4、v1.4.6 也踩过同一类问题（当时归类为 --target 的锅）。

本测试锁住两件事：
  ① 发布必须只有**一次** PATCH —— 分多次会破坏 tag 绑定
  ② 发布后必须**校验绑定** —— tag 存在 ≠ Release 绑在它上面

用假 git + 假 curl 跑真实脚本，不触网。
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "li-release.sh"
VERSION = "9.9.9"
TAG = f"v{VERSION}"
REL_ID = 424242

#: 假 curl 的实现：GET 列列表/单体，PATCH 记录并对 state 应用变更
_CURL = r'''#!/usr/bin/env bash
set -uo pipefail
STATE="__STATE__"
LOG="__LOG__"
METHOD="GET"; DATA_FILE=""; DATA_INLINE=""; URL=""; OUT_FILE=""; WRITE_FMT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -X) METHOD="$2"; shift 2 ;;
    --data-binary) DATA_FILE="${2#@}"; shift 2 ;;
    -d) DATA_INLINE="$2"; shift 2 ;;
    -o) OUT_FILE="$2"; shift 2 ;;
    -w) WRITE_FMT="$2"; shift 2 ;;
    -H) shift 2 ;;
    -s|-sS|-fsS|-sSo) shift ;;
    --noproxy) shift 2 ;;
    *) URL="$1"; shift ;;
  esac
done
PATH_ARG="${URL#https://api.github.com/}"
echo "$METHOD $PATH_ARG" >> "$LOG"

_emit() {  # $1 = 响应体；按 -o / -w 语义归还
  if [[ -n "$OUT_FILE" ]]; then printf "%s" "$1" > "$OUT_FILE"; else printf "%s" "$1"; fi
  if [[ -n "$WRITE_FMT" ]]; then printf "200"; fi
}

if [[ "$METHOD" == "PATCH" ]]; then
  if [[ -n "$DATA_FILE" ]]; then BODY="$(cat "$DATA_FILE")"; else BODY="$DATA_INLINE"; fi
  printf "%s\n" "$BODY" > "__BODYDIR__/last_patch.json"
  RESP="$(python3 - "$STATE" "$PATH_ARG" "$BODY" <<'PYBODY'
import json, re, sys
state, path, body = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(state))
payload = json.loads(body)
m = re.search(r"/releases/([0-9]+)$", path)
rid = m.group(1) if m else None
import os
for r in d:
    if str(r["id"]) == rid:
        r.update(payload)
        # 模拟 GitHub 事故：发布动作把绑定退化成 untagged
        if os.path.exists(os.path.join(os.path.dirname(state), "break_binding")):
            r["tag_name"] = "untagged-640294d359182fa43447"
json.dump(d, open(state, "w"))
hit = [r for r in d if str(r["id"]) == rid]
print(json.dumps(hit[0] if hit else {"message": "Not Found"}))
PYBODY
)"
  _emit "$RESP"
  exit 0
fi

RESP="$(python3 - "$STATE" "$PATH_ARG" <<'PYGET'
import json, re, sys
state, path = sys.argv[1], sys.argv[2]
d = json.load(open(state))
m = re.search(r"/releases/([0-9]+)$", path)
if m:
    hit = [r for r in d if str(r["id"]) == m.group(1)]
    print(json.dumps(hit[0]) if hit else '{"message":"Not Found"}')
else:
    print(json.dumps(d))
PYGET
)"
_emit "$RESP"
exit 0
'''

#: 假 git：分支固定 main，ls-remote 报告 tag 存在
_GIT = r'''#!/usr/bin/env bash
set -uo pipefail
case "${1:-}" in
  branch) echo main; exit 0 ;;
  ls-remote)
    echo "deadbeef	refs/tags/__TAG__"; exit 0 ;;
  fetch|rev-parse|describe|tag) exit 0 ;;
  *) exit 0 ;;
esac
'''


def _setup(tmp_path: Path, *, draft_tag: str = TAG,
           patch_breaks_binding: bool = False) -> dict:
    """造一个假仓库 + 假 curl/git，返回运行所需路径。"""
    repo = tmp_path / "repo"
    (repo / "custom_components" / "lixiang_auto").mkdir(parents=True)
    (repo / "custom_components" / "lixiang_auto" / "manifest.json").write_text(
        json.dumps({"version": VERSION}), encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(
        f"# 更新日志\n\n## [{VERSION}] — 2026-11-05\n\n内容\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    # 用仓库里真的绑定脚本，保证测的是真链路
    real_bind = ROOT / "scripts" / "gh-release-bind.sh"
    (repo / "scripts" / "gh-release-bind.sh").write_text(
        real_bind.read_text(encoding="utf-8"), encoding="utf-8")

    if patch_breaks_binding:
        (tmp_path / "break_binding").write_text("1", encoding="utf-8")
    state = tmp_path / "releases.json"
    state.write_text(json.dumps([{
        "id": REL_ID, "tag_name": draft_tag, "draft": True,
        "prerelease": True, "name": f"{TAG} - 草稿",
        "body": "CI 生成的正文", "assets": [{"name": "x.zip"}],
        "html_url": "https://example/untagged-deadbeef",
    }]), encoding="utf-8")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    bodydir = tmp_path
    for name, tmpl in (("curl", _CURL), ("git", _GIT)):
        p = bindir / name
        p.write_text(
            tmpl.replace("__STATE__", str(state))
                .replace("__LOG__", str(log))
                .replace("__BODYDIR__", str(bodydir))
                .replace("__TAG__", TAG),
            encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return {"repo": repo, "state": state, "log": log, "bindir": bindir,
            "patch_body": tmp_path / "last_patch.json"}


def _run(tmp_path: Path, args: list[str], **kw) -> tuple[int, str, str, dict]:
    env_paths = _setup(tmp_path, **kw)
    env = dict(os.environ)
    env["PATH"] = f"{env_paths['bindir']}:{env['PATH']}"
    env["LI_REPO_DIR"] = str(env_paths["repo"])
    env["GH_BIND_RETRIES"] = "1"
    env["GH_BIND_SLEEP"] = "0"
    env["GH_BIND_TRANSPORT"] = "curl"
    env["GH_TOKEN"] = "fake-token"
    env["LI_GH_REPO"] = "owner/repo"
    p = subprocess.run(
        ["bash", str(SCRIPT), VERSION, "--yes", *args],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(env_paths["repo"]),
    )
    return p.returncode, p.stdout, p.stderr, env_paths


# ── ① 核心回归：只能 PATCH 一次 ─────────────────────────────────────────────

def test_publish_issues_exactly_one_patch(tmp_path):
    """发布必须只有一次 PATCH —— 分两次是 v1.7.0 绑错 tag 的直接原因。

    变异验证：把脚本改成先 PATCH body 再 PATCH draft（两次），本测试立即变红。
    """
    rc, out, err, paths = _run(tmp_path, [])
    calls = paths["log"].read_text(encoding="utf-8").splitlines()
    patches = [c for c in calls if c.startswith("PATCH")]
    assert len(patches) == 1, (
        f"发布应对 Release 只发一次 PATCH，实际 {len(patches)} 次：{patches}\n"
        f"分多次 PATCH 会让 tag 绑定退化成 untagged-<hash>（v1.7.0 事故）"
    )
    assert rc == 0, f"发布应成功，rc={rc}\nstdout:\n{out}\nstderr:\n{err}"


def test_body_and_name_merge_into_same_patch(tmp_path):
    """--body-file / --name 必须并进那一次 PATCH，而不是额外再发一次。"""
    body = tmp_path / "body.md"
    body.write_text("## 升级前必读\n\n正文内容\n", encoding="utf-8")
    rc, out, err, paths = _run(
        tmp_path, ["--body-file", str(body), "--name", f"{TAG} 自定义标题"])
    patches = [c for c in paths["log"].read_text(encoding="utf-8").splitlines()
               if c.startswith("PATCH")]
    assert len(patches) == 1, f"改了正文也仍只应一次 PATCH，实际 {len(patches)} 次"
    payload = json.loads(paths["patch_body"].read_text(encoding="utf-8"))
    assert payload.get("draft") is False, "payload 缺 draft:false"
    assert "正文内容" in payload.get("body", ""), "payload 未带上 body"
    assert payload.get("name") == f"{TAG} 自定义标题", "payload 未带上 name"
    assert rc == 0, f"rc={rc}\n{out}\n{err}"


def test_patch_uses_file_not_inline_dash_d(tmp_path):
    """body 必须走 --data-binary @file，不能 -d 内联。

    -d 会走 shell 转义：正文里的引号/换行/反斜杠会被吃坏，
    而成败都不报错 —— 正文静默被改烂是最难发现的一类。
    """
    src = SCRIPT.read_text(encoding="utf-8")
    seg = src[src.index("PATCH_JSON="):]
    seg = seg[:seg.index("if [[ \"$CODE\" != \"200\" ]]")]
    assert "--data-binary @\"$PATCH_JSON\"" in seg, \
        "PATCH 必须用 --data-binary @file 传 JSON（-d 内联会被 shell 转义破坏）"


# ── ② 绑定校验必须存在且会失败 ─────────────────────────────────────────────

def test_verifies_binding_after_publish(tmp_path):
    """发布后必须校验 tag 绑定（tag 存在 ≠ 绑在它上面）。"""
    rc, out, err, paths = _run(tmp_path, [])
    assert "校验 tag 绑定" in out, "发布后没有绑定校验步骤"
    assert rc == 0, f"绑定正常时不该失败\n{out}\n{err}"


def test_fails_loudly_when_binding_broken(tmp_path):
    """若 Release 绑在 untagged 上，脚本必须**失败退出**并给出修法。

    这是 HACS 静默失效的守门：宁可发布报错，也不能静默发出一个
    用户收不到的版本。
    """
    rc, out, err, paths = _run(tmp_path, [], patch_breaks_binding=True)
    combined = out + err
    assert rc != 0, (
        "发布动作把绑定退化成 untagged 时，脚本必须非零退出 —— "
        f"否则会静默发出 HACS 收不到的版本\n{combined}"
    )
    assert "untagged" in combined or "tag_name" in combined or "绑定" in combined, \
        f"失败信息应指出绑定问题\n{combined}"


# ── ③ 静态结构：不容许"再补一次 PATCH"回归 ────────────────────────────────

def test_no_second_patch_to_same_release_in_source():
    """源码里对 /releases/$DRAFT_ID 的 PATCH 只应出现一次。

    变异验证：把 `--data-binary` 那段拆成两次 curl PATCH，本测试变红。
    """
    src = SCRIPT.read_text(encoding="utf-8")
    hits = re.findall(r'curl_gh\s+"/releases/\$DRAFT_ID"\s+-X\s+PATCH', src)
    assert len(hits) == 1, (
        f"对同一个 Release 的 PATCH 应只出现 1 处，源码里有 {len(hits)} 处："
        "分多次 PATCH 会破坏 tag 绑定"
    )
