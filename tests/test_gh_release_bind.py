"""gh-release-bind.sh 行为测试（2026-10-09，2026-10-10 扩充）。

背景（真事故）
--------------
① 自动发布工作流的"绑定修复"步骤原来是：
       「在 Release 列表里找第一个 tag_name 以 untagged- 开头的草稿」→ PATCH 成目标 tag
   而 Release 列表接口是**最终一致性**的，于是它抓错了对象：
   两个草稿的 tag 绑定互相串掉（v1.4.6 变成 untagged-…，v1.4.7 也跟着变），
   v1.2.4 历史上也是同一类问题。
   现在改成**按 release id** 定位（谁刚建就用谁的 id 去校验/修复）。

② 2026-10-10：维护者本机没装 `gh` CLI，而旧实现直接 `gh api …` 并把错误
   丢进 /dev/null → 脚本**误报**「列表里找不到 tag_name == v1.4.7 的 Release」。
   现在传输层自适应（有 gh 用 gh，没有用 curl + GH_TOKEN），JSON 解析统一用
   python3（不再依赖 jq）。

本文件用假的 `gh` / 假的 `curl` 把两条传输路径都跑一遍 —— 尤其是
「列表里存在另一个 untagged 草稿时，绝不能去动它」这条。
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "gh-release-bind.sh"

#: 两条传输路径共用的「读 JSON」片段（假 gh / 假 curl 都返回**原始 JSON**）
_READ_PY = '''
import json, re, sys
state, path = sys.argv[1], sys.argv[2]
d = json.load(open(state))
m = re.search(r"/releases/([0-9]+)$", path)
if m:
    hit = [r for r in d if str(r["id"]) == m.group(1)]
    if not hit:
        print('{"message":"Not Found"}')
        sys.exit(1)
    print(json.dumps(hit[0]))
else:
    print(json.dumps(d))
'''

_PATCH_PY = '''
import json, re, sys
state, path, tag = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(state))
rid = re.search(r"/releases/([0-9]+)$", path).group(1)
for r in d:
    if str(r["id"]) == rid:
        r["tag_name"] = tag
json.dump(d, open(state, "w"))
'''


def _make_bin(tmp_path: Path, releases: list[dict], which: str = "gh") -> Path:
    """造一个只有 `gh` 或只有 `curl` 的 bin 目录（两者都返回原始 JSON）。"""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    state = tmp_path / "releases.json"
    state.write_text(json.dumps(releases), encoding="utf-8")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")

    if which == "gh":
        tool = bindir / "gh"
        tool.write_text(f"""#!/usr/bin/env bash
set -uo pipefail
STATE="{state}"
LOG="{log}"
if [[ "$1" == "api" ]]; then
  shift
  METHOD="GET"
  if [[ "$1" == "-X" ]]; then METHOD="$2"; shift 2; fi
  PATH_ARG="$1"; shift || true
  if [[ "$METHOD" == "PATCH" ]]; then
    echo "PATCH $PATH_ARG $*" >> "$LOG"
    TAG=""
    while [[ $# -gt 0 ]]; do
      if [[ "$1" == "-f" && "$2" == tag_name=* ]]; then TAG="${{2#tag_name=}}"; fi
      shift
    done
    python3 - "$STATE" "$PATH_ARG" "$TAG" <<'PYEOF'
{_PATCH_PY}
PYEOF
    echo '{{"ok":true}}'
    exit 0
  fi
  echo "GET $PATH_ARG" >> "$LOG"
  python3 - "$STATE" "$PATH_ARG" <<'PYEOF'
{_READ_PY}
PYEOF
  exit $?
fi
echo "unsupported: $*" >&2
exit 3
""", encoding="utf-8")
    else:
        tool = bindir / "curl"
        tool.write_text(f"""#!/usr/bin/env bash
set -uo pipefail
STATE="{state}"
LOG="{log}"
METHOD="GET"
DATA=""
URL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -X) METHOD="$2"; shift 2 ;;
    -d) DATA="$2"; shift 2 ;;
    -H) shift 2 ;;
    *) URL="$1"; shift ;;
  esac
done
PATH_ARG="${{URL#https://api.github.com/}}"
if [[ "$METHOD" == "PATCH" ]]; then
  TAG=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("tag_name",""))' "$DATA")
  echo "PATCH $PATH_ARG tag_name=$TAG" >> "$LOG"
  python3 - "$STATE" "$PATH_ARG" "$TAG" <<'PYEOF'
{_PATCH_PY}
PYEOF
  echo '{{"ok":true}}'
  exit 0
fi
echo "GET $PATH_ARG" >> "$LOG"
python3 - "$STATE" "$PATH_ARG" <<'PYEOF'
{_READ_PY}
PYEOF
exit $?
""", encoding="utf-8")

    tool.chmod(tool.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run(tmp_path: Path, releases: list[dict], args: list[str], which: str = "gh",
         transport: str | None = None, token: str | None = "fake-token",
         patch_ok: bool = True) -> tuple[int, str, str]:
    bindir = _make_bin(tmp_path, releases, which=which)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_BIND_RETRIES"] = "1"
    env["GH_BIND_SLEEP"] = "0"
    if transport:
        env["GH_BIND_TRANSPORT"] = transport
    else:
        env.pop("GH_BIND_TRANSPORT", None)
    env.pop("GITHUB_TOKEN", None)
    if token is None:
        env.pop("GH_TOKEN", None)
    else:
        env["GH_TOKEN"] = token
    p = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def _patches(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("PATCH")]


# ── gh 传输路径（原有行为）──────────────────────────────────────────────────
def test_already_bound_is_noop(tmp_path):
    """已绑定 → 不发 PATCH，直接成功。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                        ["o/r", "v9.9.9", "11"], transport="gh")
    assert rc == 0, (out, err)
    assert "已正确绑定" in out
    assert _patches(tmp_path) == [], "已绑定时不该发 PATCH"


def test_untagged_is_repaired_by_id(tmp_path):
    """绑定成 untagged-… → 按【它自己的 id】PATCH 回目标 tag。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "untagged-abc"}],
                        ["o/r", "v9.9.9", "11"], transport="gh")
    assert rc == 0, (out, err)
    patches = _patches(tmp_path)
    assert len(patches) == 1 and "/releases/11 " in patches[0], patches
    assert "tag_name=v9.9.9" in patches[0], patches


def test_does_not_touch_other_untagged_drafts(tmp_path):
    """★★ 回归核心：列表里另有 untagged 草稿时，绝不能去动它。

    旧实现正是"找第一个 untagged 草稿"→ 抓错对象 → 两个草稿绑定互串。
    """
    releases = [
        {"id": 7, "tag_name": "untagged-other"},   # 不相干的坏草稿，必须原样不动
        {"id": 11, "tag_name": "v9.9.9"},          # 本次要校验的，且已正确
    ]
    rc, out, err = _run(tmp_path, releases, ["o/r", "v9.9.9", "11"], transport="gh")
    assert rc == 0, (out, err)
    assert _patches(tmp_path) == [], "不该因为列表里存在别的 untagged 草稿就动手"
    after = json.loads((tmp_path / "releases.json").read_text(encoding="utf-8"))
    assert [r for r in after if r["id"] == 7][0]["tag_name"] == "untagged-other"


def test_fails_when_id_unknown(tmp_path):
    """给了个不存在的 id → 明确失败（不猜、不乱改）。"""
    rc, out, err = _run(tmp_path, [{"id": 7, "tag_name": "untagged-other"}],
                        ["o/r", "v9.9.9", "424242"], transport="gh")
    assert rc == 1
    assert "读不到 release id=424242" in err
    assert _patches(tmp_path) == []


def test_without_id_uses_tag_lookup(tmp_path):
    """维护者路径：不给 id 时按 tag 在列表里找（带重试），找到即校验。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                        ["o/r", "v9.9.9"], transport="gh")
    assert rc == 0, (out, err)
    assert "按 tag 找到 Release id=11" in out


def test_without_id_refuses_to_guess(tmp_path):
    """不给 id 且列表里没有该 tag → 失败，绝不改任何其他 Release。"""
    rc, out, err = _run(tmp_path, [{"id": 7, "tag_name": "untagged-other"}],
                        ["o/r", "v9.9.9"], transport="gh")
    assert rc == 1
    assert "列表里找不到" in err
    assert _patches(tmp_path) == []


def test_usage_error_without_args(tmp_path):
    p = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert "用法" in p.stderr


# ── curl 传输路径（2026-10-10 新增：本机无 gh CLI 的兜底）────────────────────
class TestCurlFallback:
    def test_curl_repairs_binding(self, tmp_path):
        """★ 无 gh CLI 时用 curl + GH_TOKEN 也能完成同样的修复。"""
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "untagged-abc"}],
                            ["o/r", "v9.9.9", "11"], which="curl", transport="curl")
        assert rc == 0, (out, err)
        patches = _patches(tmp_path)
        assert len(patches) == 1 and "/releases/11 " in patches[0], patches
        assert "tag_name=v9.9.9" in patches[0], patches
        assert "已修复绑定" in out

    def test_curl_noop_when_already_bound(self, tmp_path):
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9", "11"], which="curl", transport="curl")
        assert rc == 0, (out, err)
        assert "已正确绑定" in out
        assert _patches(tmp_path) == []

    def test_curl_without_id_uses_tag_lookup(self, tmp_path):
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9"], which="curl", transport="curl")
        assert rc == 0, (out, err)
        assert "按 tag 找到 Release id=11" in out

    def test_curl_does_not_touch_other_untagged_drafts(self, tmp_path):
        """★ 回归核心在 curl 路径上同样成立（两条路径行为必须一致）。"""
        releases = [
            {"id": 7, "tag_name": "untagged-other"},
            {"id": 11, "tag_name": "v9.9.9"},
        ]
        rc, out, err = _run(tmp_path, releases, ["o/r", "v9.9.9", "11"],
                            which="curl", transport="curl")
        assert rc == 0, (out, err)
        assert _patches(tmp_path) == []
        after = json.loads((tmp_path / "releases.json").read_text(encoding="utf-8"))
        assert [r for r in after if r["id"] == 7][0]["tag_name"] == "untagged-other"

    def test_curl_without_token_fails_with_clear_reason(self, tmp_path):
        """★★ 误报回归：没 gh 又没 token 时必须【明确报原因】。

        旧实现把 `gh: command not found` 丢进 /dev/null，最后报
        「列表里找不到 tag_name == vX.Y.Z 的 Release」—— 把人引向错误方向
        （本次 v1.4.7 发布实际踩到）。
        """
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9", "11"], which="curl",
                            transport="curl", token=None)
        assert rc == 1
        assert "GH_TOKEN" in err, err
        assert "列表里找不到" not in err, (
            "不得把「缺 token」误报成「找不到 Release」")

    def test_auto_detects_curl_when_gh_absent(self, tmp_path):
        """auto 模式：PATH 里没有 gh 时自动走 curl（无需显式配置）。"""
        if shutil.which("gh") is not None:
            pytest.skip("本机装了 gh，无法模拟「无 gh」；curl 路径已由其它用例覆盖")
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9", "11"], which="curl", transport=None)
        assert rc == 0, (out, err)
        assert "已正确绑定" in out

    def test_auto_prefers_gh_when_present(self, tmp_path):
        """auto 模式：有 gh 时必须用 gh（CI 行为不变）。"""
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9", "11"], which="gh", transport=None)
        assert rc == 0, (out, err)
        log = (tmp_path / "calls.log").read_text(encoding="utf-8")
        assert "GET" in log, "未走 gh 传输路径"
        assert not (tmp_path / "bin" / "curl").exists()

    def test_invalid_transport_rejected(self, tmp_path):
        rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                            ["o/r", "v9.9.9", "11"], which="gh", transport="banana")
        assert rc == 1
        assert "GH_BIND_TRANSPORT" in err
