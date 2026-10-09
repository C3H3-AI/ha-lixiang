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

list_id_by_tag() {
  local out=""
  for _ in $(seq 1 "$RETRIES"); do
    out="$(gh api "repos/${REPO}/releases?per_page=100" \
             --jq "[.[] | select(.tag_name == \"${TAG}\")][0].id" 2>/dev/null || true)"
    if [[ -n "$out" && "$out" != "null" ]]; then printf '%s' "$out"; return 0; fi
    sleep "$SLEEP"
  done
  printf ''
}

tag_of_id() {
  local id="$1" out=""
  for _ in $(seq 1 "$RETRIES"); do
    out="$(gh api "repos/${REPO}/releases/${id}" --jq '.tag_name' 2>/dev/null || true)"
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
if ! gh api -X PATCH "repos/${REPO}/releases/${REL_ID}" -f tag_name="$TAG" >/dev/null; then
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
