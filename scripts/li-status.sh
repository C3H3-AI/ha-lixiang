#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  li-status.sh —— 仓库健康巡检（防「改了没发 / 发完还在改 / 遗留分支」）
#
#  用法：
#    ./li-status.sh              # 完整巡检
#    ./li-status.sh --quiet      # 只在有告警时输出（适合放进日常习惯）
#
#  为什么需要它？（2026-09-27 实际踩坑）
#    v1.1.0 tag 之后 main 上又合入了 2 个提交，但从未打 tag / 发 release，
#    导致 HACS 发布版拿不到新功能。当时没有任何机制能发现这件事。
#    另外还有 1 个重构分支（VSS_PATHS 迁移）落后 116 个 commit 一直漂着。
#
#  五项检查：
#    ① 未发布的提交   —— tag 之后 main 上还有多少提交没进 release
#    ② 漂着的分支     —— 落后 main 且未合并的分支（含 CI 是否还是坏的）
#    ③ 僵尸分支       —— 已完全合并进 main 的分支，可以删
#    ④ CI 健康        —— 最近几次运行是否有失败
#    ⑤ main 保护      —— 分支保护是否真的开着（CONTRIBUTING 声称已开）
# ═══════════════════════════════════════════════════════════════════════════

set -uo pipefail

# 仓库目录：优先用参数/环境变量，其次脚本所在目录（脚本放在仓库根即可直接跑）
REPO_DIR="${LI_REPO_DIR:-}"
if [[ -z "$REPO_DIR" ]]; then
  if [[ -f "$(dirname "$(readlink -f "$0")")/custom_components/lixiang_auto/manifest.json" ]]; then
    REPO_DIR="$(dirname "$(readlink -f "$0")")"      # 脚本在仓库内
  else
    REPO_DIR="/media/duola/devdata/AI-workspace/ha-lixiang"   # 回退：原开发机布局
  fi
fi
# 代理仅在本机可达时使用（外部贡献者通常不需要）
# 代理可用 → 走代理；不可用 → 【显式】直连。
#
# ★ 只把 -x 去掉是不够的：环境变量里的 https_proxy / ALL_PROXY 仍会被
#   curl 采用，于是"回退直连"实际还是走那个坏代理 —— 脚本会静默退化成
#   "无法确认"，把真实告警吞掉。（2026-09-28 实测：代理挂掉后，
#   li-status.sh 的 CI 健康 / 分支保护两项都变成 "?"，看起来"没告警"。）
#   所以回退时必须加 --noproxy '*'。
PROXY="${LI_PROXY:-http://127.0.0.1:7890}"
PROXY_ARGS=(-x "$PROXY")
if ! curl -s -o /dev/null --max-time 3 -x "$PROXY" https://api.github.com/ 2>/dev/null; then
  PROXY_ARGS=(--noproxy '*')
fi
GH_REPO="${LI_GH_REPO:-C3H3-AI/ha-lixiang}"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; BLU=$'\033[34m'; DIM=$'\033[2m'; RST=$'\033[0m'
WARN_COUNT=0
UNK_COUNT=0

log()  { [[ $QUIET -eq 1 ]] || echo "${BLU}▸${RST} $*"; }
ok()   { [[ $QUIET -eq 1 ]] || echo "${GRN}  ✓${RST} $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); echo "${YEL}  !${RST} $*"; }
# ★ unk()：「查不到」不是「有问题」。网络抖动/API 失败不应让巡检报需要处理，
#   否则误报累积成噪音，脚本本身就被忽略了（正是要防的失效模式）。
unk()  { UNK_COUNT=$((UNK_COUNT+1)); echo "${DIM}  ? $*${RST}"; }
err()  { WARN_COUNT=$((WARN_COUNT+1)); echo "${RED}  ✗${RST} $*"; }

cd "$REPO_DIR" || { echo "仓库目录不存在: $REPO_DIR"; exit 1; }

token() { cat /tmp/ghtoken 2>/dev/null || sed -n 's|https://[^:]*:\([^@]*\)@github.com|\1|p' ~/.git-credentials 2>/dev/null | head -1; }

gh_api() {
  local path="$1"
  local px=()
  px=("${PROXY_ARGS[@]}")
  curl -s --max-time 25 "${px[@]}" \
       -H "Authorization: token $(token)" \
       -H "Accept: application/vnd.github+json" \
       "https://api.github.com/repos/$GH_REPO$path" 2>/dev/null
}

# 取最新 tag（按版本号排序，非按提交日期）
latest_tag() {
  git tag --list 'v*' --sort=-v:refname | head -1
}

echo "═══════════════════════════════════════════════════════════════════════"
[[ $QUIET -eq 1 ]] || echo "  仓库健康巡检 — $(date '+%Y-%m-%d %H:%M')"
[[ $QUIET -eq 1 ]] || echo "═══════════════════════════════════════════════════════════════════════"

git fetch -q origin --tags 2>/dev/null || true

# ── ① 未发布的提交 ──────────────────────────────────────────────────────
#  ★ 区分「影响用户的改动」与「纯文档/CI 改动」——
#    只有前者才算真正的发布缺口。否则每提交一次 README 都告警，
#    告警会被当成噪音忽略（这是巡检脚本最容易失效的方式）。
TAG=$(latest_tag)
if [[ -z "$TAG" ]]; then
  warn "没有任何 v* tag —— 尚未建立发布基线"
else
  # HACS 分发的是 custom_components/（+ hacs.json/manifest）；
  # 其余（docs/CI/README/CONTRIBUTING）不影响用户拿到的内容。
  DIST_FILES=$(git diff --name-only "$TAG"..origin/main 2>/dev/null \
               | grep -E '^custom_components/|^hacs\.json$' || true)
  N_DIST=$(echo "$DIST_FILES" | grep -c . || true)
  N_ALL=$(git rev-list --count "$TAG"..origin/main 2>/dev/null || echo 0)

  if [[ "$N_ALL" -eq 0 ]]; then
    ok "无未发布提交（$TAG == origin/main）"
  elif [[ "$N_DIST" -eq 0 ]]; then
    # 只有文档/CI 改动 → 用户拿到的内容完全相同，不算发布缺口
    ok "$TAG 之后有 $N_ALL 个提交，但未触及 custom_components/ 或 hacs.json"
    echo "        ${DIM}（纯文档/CI 改动，HACS 用户内容无变化 → 无需发版）${RST}"
  else
    warn "★ $TAG 之后 main 上有 $N_ALL 个提交【未进入任何 release】，其中 $N_DIST 个文件影响用户："
    git log --oneline "$TAG"..origin/main 2>/dev/null | head -6 | sed 's/^/        /'
    echo "$DIST_FILES" | sed 's/^/          · /'
    echo "        ${DIM}→ 处理：./bump.sh patch && 开 release PR && 打 tag && 建 Release${RST}"
  fi
fi

# ── ② 漂着的分支（落后 main 且未合并）──────────────────────────────────
log "漂着的分支（未合并 + 落后 main）"
DRIFT=0
while read -r br; do
  [[ -z "$br" ]] && continue
  ahead=$(git rev-list --count "origin/main..$br" 2>/dev/null || echo 0)
  behind=$(git rev-list --count "$br..origin/main" 2>/dev/null || echo 0)
  [[ "$ahead" -eq 0 ]] && continue          # 没独有提交 → 不算漂着
  # 判断独有提交是否已通过 patch-id 进入 main（rebase 孪生）
  real=$(git cherry origin/main "$br" 2>/dev/null | grep -c '^+' || true)
  if [[ "$real" -eq 0 ]]; then
    ok "$br —— 独有提交已全部进 main（仅 hash 不同）"
  else
    # 有开放 PR 的分支是【正常状态】（等待人类合并），不算漂着。
    # ★ 必须区分「确实没有 PR」与「查不到（网络/API 失败）」——
    #   否则一次网络抖动就会误报漂移，告警变噪音后巡检就失效了。
    short="${br#origin/}"
    pr_raw=$(gh_api "/pulls?head=${GH_REPO%%/*}:$short&state=open" 2>/dev/null)
    has_pr=$(printf '%s' "$pr_raw" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('ERR'); raise SystemExit
# 不是列表 = 错误对象（如 {'message': 'Bad credentials'}）→ 视为查不到
if not isinstance(d, list):
    print('ERR')
else:
    print(d[0]['number'] if d else '')
" 2>/dev/null)
    if [[ "$has_pr" == "ERR" || -z "$pr_raw" ]]; then
      unk "$short —— $real 个提交未合并，且无法确认 PR 状态（网络/API 失败，非漂移证据）"
    elif [[ -n "$has_pr" ]]; then
      ok "$short —— $real 个提交待合并（开放 PR #$has_pr，等合并）"
    else
      DRIFT=$((DRIFT+1))
      warn "★ $short —— $real 个提交未合并且【没有开放 PR】，落后 main $behind 个"
      git log --oneline "origin/main..$br" 2>/dev/null | head -3 | sed 's/^/        /'
      echo "        ${DIM}→ 处理：rebase 到 main 并开 PR，或确认后删除分支${RST}"
    fi
  fi
done < <(git for-each-ref --format='%(refname:short)' refs/remotes/origin \
         | grep -vE '^origin$|^origin/HEAD$|^origin/main$')
[[ $DRIFT -eq 0 ]] && ok "无漂着的分支"

# ── ③ 僵尸分支（已完全合并）────────────────────────────────────────────
log "可清理的分支（已合并进 main）"
ZOMBIE=$(git branch -r --merged origin/main 2>/dev/null | grep -v 'origin/main$' | grep -v HEAD | sed 's/^ *//' | wc -l)
if [[ "$ZOMBIE" -eq 0 ]]; then
  ok "无可清理分支"
else
  ok "$ZOMBIE 个已合并分支（可用 ./li-pr.sh clean 清理）"
fi

# ── ④ CI 健康 ───────────────────────────────────────────────────────────
log "CI 健康"
RUNS=$(gh_api "/actions/runs?per_page=5")
if [[ -z "$RUNS" ]]; then
  unk "无法获取 CI 状态（网络 / token）—— 稍后重试"
else
  echo "$RUNS" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('  ? CI 状态解析失败（响应非预期，非 CI 失败证据）'); sys.exit(0)
runs = d.get('workflow_runs', [])
if not runs:
    print('  ? 还没有任何 CI 运行'); sys.exit(0)
fails = [r for r in runs if r.get('conclusion') == 'failure']
for r in runs[:3]:
    print(f\"        run {r['run_number']:>3} {r['head_branch'][:38]:40s} {r.get('conclusion')}\")
if fails:
    # 判断是否为「jobs=0」型失败（YAML 无法解析）
    print(f'  ! 最近 {len(runs)} 次中有 {len(fails)} 次失败')
    print('        若 jobs 数为 0，说明工作流文件本身解析失败（见 PR #8）')
else:
    print('  ✓ 最近运行全部成功')
" 2>/dev/null | while IFS= read -r ln; do
    case "$ln" in
      *"  ! "*) warn "${ln#*  ! }" ;;
      *"  ? "*) unk  "${ln#*  ? }" ;;
      *"  ✓ "*) ok "${ln#*  ✓ }" ;;
      *)        echo "$ln" ;;
    esac
  done
fi

# ── ⑤ main 分支保护 ─────────────────────────────────────────────────────
log "main 分支保护"
PROT=$(gh_api "/branches/main" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('unknown'); sys.exit(0)
print('on' if d.get('protected') else 'off')
" 2>/dev/null)
case "$PROT" in
  on)  ok "已开启（直接推 main 会被拒绝）" ;;
  off) err "★ 未开启！直接推 main 不会被拒绝（规则失去强制力）"
       echo "        ${DIM}→ 处理：GitHub Settings → Branches，或用 API：${RST}"
       echo "        ${DIM}  PUT /repos/$GH_REPO/branches/main/protection${RST}"
       echo "        ${DIM}  Require status checks: lint & security / hassfest / HACS validate${RST}" ;;
  *)   unk "无法确认分支保护状态（网络 / token）—— 稍后重试" ;;
esac

# ── 汇总 ────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════════════"
UNK_NOTE=""
[[ $UNK_COUNT -gt 0 ]] && UNK_NOTE="（另有 $UNK_COUNT 项因网络/API 失败未能确认，不计入）"
if [[ $WARN_COUNT -eq 0 ]]; then
  echo "${GRN}  ✅ 巡检通过，无告警${RST}${UNK_NOTE:+ }${UNK_NOTE}"
  echo "═══════════════════════════════════════════════════════════════════════"
  exit 0
else
  echo "${YEL}  ⚠ 发现 $WARN_COUNT 项需要处理${RST}${UNK_NOTE:+ }${UNK_NOTE}"
  echo "═══════════════════════════════════════════════════════════════════════"
  exit 1
fi
