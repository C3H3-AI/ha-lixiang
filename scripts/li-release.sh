#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  li-release.sh —— 发布流程的**最后一公里**
#
#  【新分工（2026-09-29，对齐 hacs-vision）】
#
#    workflow (draft-release.yml)  自动  版本号 bump 进 main 后：
#                                         · 严格递增检查（packaging.version）
#                                         · 先建轻量 tag（GitHub 草稿不会自动建 tag！）
#                                         · 打 ZIP
#                                         · 建【草稿】Release（gh release create --draft --generate-notes）
#                                         · 校验 tag 确实存在
#
#    li-release.sh                 人工  维护者在 Releases 页面确认草稿后：
#                                         · 版本号是自己决定的 —— 脚本不猜
#                                         · 校验草稿存在且 tag 已就位
#                                         · Publish 草稿（draft=false）
#                                         · 复查 li-status.sh
#
#  ★ 为什么不自动发布（和 hacs-vision 一致）
#    · 版本号是【维护者】的决定 —— workflow 不猜、不自动 bump
#    · Release 正文可能需要人工确认
#    · 草稿是【提醒】，维护者点 Publish 才算发完
#
#  用法：
#    ./li-release.sh 1.2.3                 # 校验 + Publish（会二次确认）
#    ./li-release.sh 1.2.3 --dry-run       # 只校验，不做写操作
#    ./li-release.sh 1.2.3 --yes           # 跳过确认
# ═══════════════════════════════════════════════════════════════════════════

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO_DIR="${LI_REPO_DIR:-$(dirname "$SCRIPT_DIR")}"

PROXY="${LI_PROXY:-http://127.0.0.1:7890}"
PROXY_ARGS=(-x "$PROXY")
if ! curl -s -o /dev/null --max-time 3 -x "$PROXY" https://api.github.com/ 2>/dev/null; then
  PROXY_ARGS=(--noproxy '*')
fi
GH_REPO="${LI_GH_REPO:-C3H3-AI/ha-lixiang}"

GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; BLU=$'\033[34m'; RST=$'\033[0m'
log()  { echo "${BLU}▸${RST} $*"; }
ok()   { echo "${GRN}  ✓${RST} $*"; }
warn() { echo "${YEL}  !${RST} $*"; }
err()  { echo "${RED}  ✗${RST} $*"; }
die()  { err "$*"; exit 1; }

curl_gh() {  # curl_gh <path> [curl args...]
  local path="$1"; shift
  local args=(-sS -H "Authorization: token $(token)" -H "Accept: application/vnd.github+json")
  args+=("${PROXY_ARGS[@]}")
  curl "${args[@]}" "https://api.github.com/repos/$GH_REPO$path" "$@"
}

token() { cat /tmp/ghtoken 2>/dev/null || sed -n 's|https://[^:]*:\([^@]*\)@github.com|\1|p' ~/.git-credentials 2>/dev/null | head -1; }

# ── 参数 ──────────────────────────────────────────────────────────────────
VERSION="${1:-}"
DRY=0; ASSUME_YES=0
for a in "$@"; do
  [[ "$a" == "--dry-run" ]] && DRY=1
  [[ "$a" == "--yes" ]] && ASSUME_YES=1
done

[[ -z "$VERSION" || "$VERSION" == --* ]] && {
  err "用法: ./li-release.sh <版本号，如 1.2.3> [--dry-run|--yes]"
  exit 2
}
VERSION="${VERSION#v}"
TAG="v$VERSION"

cd "$REPO_DIR" || die "进不去仓库目录: $REPO_DIR"
echo "═══════════════════════════════════════════════════════════════════════"
echo "  发布 $TAG   （仓库: $GH_REPO）$([[ $DRY -eq 1 ]] && echo '   [DRY-RUN]')"
echo "═══════════════════════════════════════════════════════════════════════"

# ── ① 本地校验 ────────────────────────────────────────────────────────────
log "① 本地校验"

BRANCH="$(git branch --show-current)"
[[ "$BRANCH" == "main" ]] || die "建议在 main 上发布（当前在 '$BRANCH'）"
ok "当前分支 main"

MANIFEST_VERSION="$(python3 -c "import json;print(json.load(open('custom_components/lixiang_auto/manifest.json'))['version'])" 2>/dev/null)"
[[ "$MANIFEST_VERSION" == "$VERSION" ]] || die "manifest 版本是 $MANIFEST_VERSION，与目标 $TAG 不一致"
ok "manifest 版本 == $VERSION"

grep -qE "^## \[$VERSION\]" CHANGELOG.md || die "CHANGELOG.md 里没有 [${VERSION}] 段落"
ok "CHANGELOG 有 [${VERSION}] 段"

# ── ② tag 必须已存在（workflow 会建它）─────────────────────────────────────
log "② 检查 tag"
if git ls-remote --tags origin "refs/tags/$TAG" 2>/dev/null | grep -q "$TAG"; then
  ok "tag $TAG 已存在（workflow 应该已经建好）"
else
  warn "tag $TAG 在远端不存在 —— workflow 可能还没跑/失败了"
  warn "  先等 workflow 跑完，或手动: git tag $TAG && git push origin $TAG"
  die "tag 不存在，无法发布（HACS 依赖 tag 识别版本）"
fi

# ── ③ 草稿 Release 必须存在（workflow 会建它）──────────────────────────────
log "③ 检查草稿 Release"

# 取所有 release，找 tag_name==TAG 且 draft==true
DRAFT_DATA="$(curl_gh "/releases" 2>/dev/null)"
if ! echo "$DRAFT_DATA" | python3 -c "
import json,sys
releases = json.loads(sys.stdin.read())
targets = [r for r in releases if r.get('tag_name')=='$TAG']
if not targets:
    print('NONE'); sys.exit(0)
drafts = [r for r in targets if r.get('draft')]
print('DRAFT' if drafts else 'PUBLISHED')
" 2>/dev/null | grep -q "DRAFT"; then

  STATUS="$(echo "$DRAFT_DATA" | python3 -c "
import json,sys
releases = json.loads(sys.stdin.read())
targets = [r for r in releases if r.get('tag_name')=='$TAG']
if not targets: print('NONE')
elif any(r.get('draft') for r in targets): print('DRAFT')
else: print('PUBLISHED')
" 2>/dev/null)"

  if [[ "$STATUS" == "NONE" ]]; then
    die "没有 tag $TAG 的 Release —— workflow 应该已经建好草稿，检查一下？"
  elif [[ "$STATUS" == "PUBLISHED" ]]; then
    ok "tag $TAG 的 Release 已发布（不是草稿）"
    warn "  看来已经发过了 —— 检查一下 Releases 页面？"
    exit 0
  fi
fi
ok "草稿 Release 已就位（维护者可以去 Releases 页面确认正文）"

# ── ④ Publish 草稿 ────────────────────────────────────────────────────────
if [[ $DRY -eq 1 ]]; then
  echo
  warn "DRY-RUN：以下动作【未执行】——"
  echo "      PATCH /releases/<id>  {draft: false}"
  echo "      （同时会清掉 prerelease 标记）"
  exit 0
fi

if [[ $ASSUME_YES -eq 0 ]]; then
  echo
  read -r -p "  确认发布 $TAG？[y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { warn "已取消"; exit 1; }
fi

log "④ Publish 草稿"

# 先找到那个草稿的 id
DRAFT_ID="$(curl_gh "/releases" 2>/dev/null | python3 -c "
import json,sys
for r in json.loads(sys.stdin.read()):
    if r.get('tag_name')=='$TAG' and r.get('draft'):
        print(r['id']); break
" 2>/dev/null)"

if [[ -z "$DRAFT_ID" ]]; then
  die "找不到 tag $TAG 的草稿 Release —— 刚才明明说有，怎么回事？"
fi

CODE="$(curl_gh "/releases/$DRAFT_ID" -X PATCH \
  -d '{"draft": false, "prerelease": false}' \
  -o /tmp/li-release-resp.json -w '%{http_code}')"

if [[ "$CODE" != "200" ]]; then
  err "Publish 失败（HTTP $CODE）"
  python3 -c "import json;d=json.load(open('/tmp/li-release-resp.json'));print('   ',d.get('message'),str(d.get('errors'))[:300])" 2>/dev/null
  exit 1
fi

URL="$(python3 -c "import json;print(json.load(open('/tmp/li-release-resp.json')).get('html_url',''))" 2>/dev/null)"
ok "Release 已发布: $URL"

# ── ⑤ 复查 ────────────────────────────────────────────────────────────────
log "⑤ 复查"
if [[ -x scripts/li-status.sh ]]; then
  scripts/li-status.sh 2>&1 | grep -E "未发布|巡检通过|告警|tag" | sed 's/^/   /'
else
  warn "未找到 scripts/li-status.sh，跳过复查"
fi

echo "═══════════════════════════════════════════════════════════════════════"
echo "${GRN}  ✅ $TAG 发布完成${RST}"
echo "═══════════════════════════════════════════════════════════════════════"
