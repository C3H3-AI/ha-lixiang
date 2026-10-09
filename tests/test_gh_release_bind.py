"""gh-release-bind.sh 行为测试（2026-10-09）。

背景（真事故）
--------------
自动发布工作流的"绑定修复"步骤原来是：
    「在 Release 列表里找第一个 tag_name 以 untagged- 开头的草稿」→ PATCH 成目标 tag
而 Release 列表接口是**最终一致性**的，于是它抓错了对象：
两个草稿的 tag 绑定互相串掉（v1.4.6 变成 untagged-…，v1.4.7 也跟着变），
v1.2.4 历史上也是同一类问题。

现在改成**按 release id** 定位（谁刚建就用谁的 id 去校验/修复），
本文件用假的 `gh` 把几种情形都跑一遍 —— 尤其是
「列表里存在另一个 untagged 草稿时，绝不能去动它」这条。
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "gh-release-bind.sh"


def _fake_gh(tmp_path: Path, releases: list[dict], patch_ok: bool = True) -> Path:
    """造一个假的 gh：把 releases 写进文件，PATCH 时改文件并记录调用日志。"""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    state = tmp_path / "releases.json"
    state.write_text(json.dumps(releases), encoding="utf-8")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")

    gh = bindir / "gh"
    gh.write_text(
        f"""#!/usr/bin/env bash
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
    ID="${{PATH_ARG##*/}}"
    TAG=""
    while [[ $# -gt 0 ]]; do
      if [[ "$1" == "-f" && "$2" == tag_name=* ]]; then TAG="${{2#tag_name=}}"; fi
      shift
    done
    python3 - "$STATE" "$ID" "$TAG" <<'PYEOF'
import json, sys
state, rid, tag = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(state))
for r in d:
    if str(r["id"]) == str(rid):
        r["tag_name"] = tag
json.dump(d, open(state, "w"))
PYEOF
    echo '{{"ok":true}}'
    exit 0
  fi
  # GET 路径：repos/<repo>/releases?per_page=100  或  repos/<repo>/releases/<id>
  echo "GET $PATH_ARG" >> "$LOG"
  if [[ "$PATH_ARG" == *"/releases/"* ]]; then
    ID="${{PATH_ARG##*/}}"
    python3 - "$STATE" "$ID" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
hit = [r for r in d if str(r["id"]) == sys.argv[2]]
print(hit[0]["tag_name"] if hit else "null")
PYEOF
    exit 0
  fi
  JQ=""
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--jq" ]]; then JQ="$2"; fi
    shift
  done
  if [[ "$JQ" == *"select(.tag_name =="* ]]; then
    TAG=$(printf '%s' "$JQ" | sed -n 's/.*== \\"\\([^\\"]*\\)\\".*/\\1/p')
    python3 - "$STATE" "$TAG" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
hit = [r for r in d if r["tag_name"] == sys.argv[2]]
print(hit[0]["id"] if hit else "null")
PYEOF
  else
    python3 -c "import json,sys;print('\\n'.join(str(r['id']) for r in json.load(open(sys.argv[1]))))" "$STATE"
  fi
  exit 0
fi
echo "unsupported: $*" >&2
exit 3
""",
        encoding="utf-8",
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run(tmp_path: Path, releases: list[dict], args: list[str]) -> tuple[int, str, str]:
    bindir = _fake_gh(tmp_path, releases)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_BIND_RETRIES"] = "1"
    env["GH_BIND_SLEEP"] = "0"
    p = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def _patches(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("PATCH")]


def test_already_bound_is_noop(tmp_path):
    """已绑定 → 不发 PATCH，直接成功。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}],
                        ["o/r", "v9.9.9", "11"])
    assert rc == 0, (out, err)
    assert "已正确绑定" in out
    assert _patches(tmp_path) == [], "已绑定时不该发 PATCH"


def test_untagged_is_repaired_by_id(tmp_path):
    """绑定成 untagged-… → 按【它自己的 id】PATCH 回目标 tag。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "untagged-abc"}],
                        ["o/r", "v9.9.9", "11"])
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
    rc, out, err = _run(tmp_path, releases, ["o/r", "v9.9.9", "11"])
    assert rc == 0, (out, err)
    assert _patches(tmp_path) == [], "不该因为列表里存在别的 untagged 草稿就动手"
    after = json.loads((tmp_path / "releases.json").read_text(encoding="utf-8"))
    assert [r for r in after if r["id"] == 7][0]["tag_name"] == "untagged-other"


def test_fails_when_id_unknown(tmp_path):
    """给了个不存在的 id → 明确失败（不猜、不乱改）。"""
    rc, out, err = _run(tmp_path, [{"id": 7, "tag_name": "untagged-other"}],
                        ["o/r", "v9.9.9", "424242"])
    assert rc == 1
    assert "读不到 release id=424242" in err
    assert _patches(tmp_path) == []


def test_without_id_uses_tag_lookup(tmp_path):
    """维护者路径：不给 id 时按 tag 在列表里找（带重试），找到即校验。"""
    rc, out, err = _run(tmp_path, [{"id": 11, "tag_name": "v9.9.9"}], ["o/r", "v9.9.9"])
    assert rc == 0, (out, err)
    assert "按 tag 找到 Release id=11" in out


def test_without_id_refuses_to_guess(tmp_path):
    """不给 id 且列表里没有该 tag → 失败，绝不改任何其他 Release。"""
    rc, out, err = _run(tmp_path, [{"id": 7, "tag_name": "untagged-other"}], ["o/r", "v9.9.9"])
    assert rc == 1
    assert "列表里找不到" in err
    assert _patches(tmp_path) == []


def test_usage_error_without_args(tmp_path):
    p = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, timeout=30)
    assert p.returncode == 2
    assert "用法" in p.stderr
