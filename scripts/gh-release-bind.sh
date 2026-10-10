#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  gh-release-bind.sh —— 把 Release 绑定到指定 tag，**按 release id 定位**
#
#  为什么需要它
#  ------------
#  2026-10-09 实测事故：draft-release.yml 的修复步骤靠
#  「在列表里找第一个 tag_name 以 untagged- 开头的草稿」来修复绑定，
#  而 Release 列表是【最终一致性】的 —— 结果把不相干的草稿当成"刚建坏的那个"
#  去 PATCH，两个草稿的 tag 绑定互相串了（v1.4.6 被标成 untagged，
#  v1.4.7 也被标成 untagged）。历史上 v1.2.4 也是同一类问题。
#
#  正确做法：谁刚建出来，就拿它的 id 去校验/修复 —— 不全局搜索、不猜。
#
#  ★ 2026-10-10：维护者本机常常没装 gh CLI，而旧实现直接 `gh api …` 并把
#    错误丢进 /dev/null → 脚本**误报**「列表里找不到 tag_name == vX.Y.Z 的
#    Release」（本次发布 v1.4.7 时实际踩到）。现在传输层自适应：
#      auto（默认）= 有 gh 用 gh，没有就用 curl + GH_TOKEN/GITHUB_TOKEN
#      gh / curl   = 强制（测试或固定环境用，见 GH_BIND_TRANSPORT）
#    JSON 解析统一交给 python3 —— 不再依赖 jq，两种环境行为一致。
#
#  用法
#  ----
#    ./gh-release-bind.sh <owner/repo> <vX.Y.Z> <release-id>
#        # 工作流路径：对"本次新建的那个 Release"校验并（必要时）修复
#
#    ./gh-release-bind.sh <owner/repo> <vX.Y.Z>
#        # 维护者路径：按 tag_name 在列表里找（带重试）；找不到直接失败
#
#  退出码：0 = 已确认绑定；1 = 无法确认/修复（不猜、不动其他 Release）
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

REPO="${1:-}"
TAG="${2:-}"
REL_ID="${3:-}"

if [[ -z "$REPO" || -z "$TAG" ]]; then
  echo "用法: $0 <owner/repo> <vX.Y.Z> [release-id]" >&2
  exit 2
fi

# 列表接口是最终一致性的：刚建的 Release 可能还查不到 → 重试
RETRIES="${GH_BIND_RETRIES:-5}"
SLEEP="${GH_BIND_SLEEP:-3}"

# ── 传输层 ─────────────────────────────────────────────────────────────────
_token() { printf '%s' "${GH_TOKEN:-${GITHUB_TOKEN:-}}"; }

_resolve_transport() {
  case "${GH_BIND_TRANSPORT:-auto}" in
    gh|curl) printf '%s' "${GH_BIND_TRANSPORT}" ;;
    auto)
      if command -v gh >/dev/null 2>&1; then printf 'gh'; else printf 'curl'; fi ;;
    *)
      echo "::error::GH_BIND_TRANSPORT 取值非法: ${GH_BIND_TRANSPORT}（可选 auto/gh/curl）" >&2
      return 1 ;;
  esac
}

TRANSPORT="$(_resolve_transport)" || exit 1

# 前置校验：早失败 + 给明确原因（旧版正是在这里静默失败，然后误报"找不到"）
if [[ "$TRANSPORT" == "curl" && -z "$(_token)" ]]; then
  echo "::error::未安装 gh CLI，且未设置 GH_TOKEN / GITHUB_TOKEN —— 无法访问 GitHub API" >&2
  echo "  处理：安装 gh（推荐）或 export GH_TOKEN=<token> 后重试" >&2
  exit 1
fi

_api_get() {  # $1 = API 路径（不含域），输出原始 JSON
  if [[ "$TRANSPORT" == "gh" ]]; then
    gh api "$1"
  else
    curl -fsS --noproxy '*' \
      -H "Authorization: token $(_token)" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/$1"
  fi
}

_api_patch_tag() {  # $1 = release id, $2 = tag
  if [[ "$TRANSPORT" == "gh" ]]; then
    gh api -X PATCH "repos/${REPO}/releases/$1" -f tag_name="$2" >/dev/null
  else
    curl -fsS --noproxy '*' -X PATCH \
      -H "Authorization: token $(_token)" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" \
      -d "{\"tag_name\":\"$2\"}" \
      "https://api.github.com/repos/${REPO}/releases/$1" >/dev/null
  fi
}

# ── JSON 解析（python3，无需 jq）────────────────────────────────────────────
_id_of_tag() {  # stdin = releases 列表 JSON；$1 = tag → id / 空
  python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
if isinstance(data, dict):          # 404 等错误响应
    print(""); raise SystemExit
hit = [r for r in data if isinstance(r, dict) and r.get("tag_name") == sys.argv[1]]
print(hit[0].get("id", "") if hit else "")
' "$1"
}

_tag_of_release() {  # stdin = 单个 release JSON → tag_name / 空
  python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
print(d.get("tag_name", "") if isinstance(d, dict) else "")
'
}

list_id_by_tag() {
  local out=""
  for _ in $(seq 1 "$RETRIES"); do
    out="$(_api_get "repos/${REPO}/releases?per_page=100" 2>/dev/null | _id_of_tag "$TAG" || true)"
    if [[ -n "$out" && "$out" != "null" ]]; then printf '%s' "$out"; return 0; fi
    sleep "$SLEEP"
  done
  printf ''
}

tag_of_id() {
  local id="$1" out=""
  for _ in $(seq 1 "$RETRIES"); do
    out="$(_api_get "repos/${REPO}/releases/${id}" 2>/dev/null | _tag_of_release || true)"
    if [[ -n "$out" && "$out" != "null" ]]; then printf '%s' "$out"; return 0; fi
    sleep "$SLEEP"
  done
  printf ''
}

# ── 定位 Release ───────────────────────────────────────────────────────────
if [[ -z "$REL_ID" ]]; then
  REL_ID="$(list_id_by_tag)"
  if [[ -z "$REL_ID" ]]; then
    echo "::error::列表里找不到 tag_name == ${TAG} 的 Release。" >&2
    echo "  （草稿不参与 tag 索引；若这是刚创建的草稿，请显式传 release id）" >&2
    exit 1
  fi
  echo "按 tag 找到 Release id=${REL_ID}"
fi

# ── 校验并按 id 修复 ───────────────────────────────────────────────────────
CUR="$(tag_of_id "$REL_ID")"
if [[ -z "$CUR" ]]; then
  echo "::error::读不到 release id=${REL_ID} 的 tag_name（网络/权限？）" >&2
  exit 1
fi

if [[ "$CUR" == "$TAG" ]]; then
  echo "✓ Release id=${REL_ID} 已正确绑定 ${TAG}"
  exit 0
fi

echo "::warning::Release id=${REL_ID} 的 tag_name 是 ${CUR}，不是 ${TAG} —— 按 id 修复（不动任何其他 Release）"
if ! _api_patch_tag "$REL_ID" "$TAG"; then
  echo "::error::PATCH release id=${REL_ID} 失败" >&2
  exit 1
fi

sleep "$SLEEP"
CUR="$(tag_of_id "$REL_ID")"
if [[ "$CUR" != "$TAG" ]]; then
  echo "::error::修复后 id=${REL_ID} 的 tag_name 仍是 ${CUR}（期望 ${TAG}）" >&2
  exit 1
fi
echo "✓ 已修复绑定：id=${REL_ID} → ${TAG}"
