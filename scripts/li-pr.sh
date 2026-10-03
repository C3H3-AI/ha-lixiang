#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  li-pr.sh —— 提 PR 脚本（所有改动走 PR，由人类合并）
# ═══════════════════════════════════════════════════════════════════════════
#
#  工作流
#  ------
#    ① 从 main 拉新分支
#    ② 改代码（测试机）
#    ③ ./li-pr.sh new <类型> <简述>   ← 提交 + 推送 + 开 PR
#    ④ 人在 GitHub 上 review + 合并
#
#  用法
#  ----
#    ./li-pr.sh start feat 优化登录流程     # 开始：建分支
#    （改代码...）
#    ./li-pr.sh submit                      # 提交 + 推送 + 开 PR
#    ./li-pr.sh status                      # 看当前分支/PR 状态
#    ./li-pr.sh list                        # 列出所有 open PR
#    ./li-pr.sh clean                       # 清理已合并的本地分支
#
#  一次性（建分支 + 提交 + 开 PR）
#    ./li-pr.sh one "feat: 优化登录流程"
# ═══════════════════════════════════════════════════════════════════════════

set -uo pipefail

REPO_DIR="${LI_REPO_DIR:-}"
if [[ -z "$REPO_DIR" ]]; then
  if [[ -f "$(dirname "$(readlink -f "$0")")/custom_components/lixiang_auto/manifest.json" ]]; then
    REPO_DIR="$(dirname "$(readlink -f "$0")")"
  else
    REPO_DIR="/media/duola/devdata/AI-workspace/ha-lixiang"
  fi
fi
TEST_DIR="${LI_TEST_DIR:-/media/duola/devdata/AI-workspace/home-assistant-nas/ha-test/config/custom_components/lixiang_auto}"
REPO_SUB="custom_components/lixiang_auto"
GH_REPO="${LI_GH_REPO:-c3h3-ci/ha-lixiang}"
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

GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; BLU=$'\033[34m'; RST=$'\033[0m'
log()  { echo "${BLU}▸${RST} $*"; }
ok()   { echo "${GRN}✓${RST} $*"; }
warn() { echo "${YEL}!${RST} $*"; }
err()  { echo "${RED}✗${RST} $*" >&2; }

cd "$REPO_DIR" || { err "仓库目录不存在: $REPO_DIR"; exit 1; }

token() {
  # ① 显式环境变量  ② /tmp/ghtoken  ③ ~/.git-credentials（git push 用的同一个 token）
  if [[ -n "${GH_TOKEN:-}" ]]; then echo "$GH_TOKEN"; return; fi
  if [[ -s /tmp/ghtoken ]]; then cat /tmp/ghtoken; return; fi
  sed -n 's|https://[^:]*:\([^@]*\)@github.com|\1|p' ~/.git-credentials 2>/dev/null | head -1
}

gh_api() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-s -X "$method" -H "Authorization: token $(token)"
              -H "Accept: application/vnd.github+json"
              "https://api.github.com$path")
  [[ -n "$data" ]] && args+=(-d "$data")
  local px=()
  px=("${PROXY_ARGS[@]}")
  curl "${args[@]}" "${px[@]}" --max-time 25 2>/dev/null
}

# ───────────────────────────────────────────────────────────────────────────
# 同步测试机 → 仓库（PR 前的必要步骤）
# ───────────────────────────────────────────────────────────────────────────
# ───────────────────────────────────────────────────────────────────────────
# 部署 仓库 → 测试机（CONTRIBUTING 说这才是「部署」的正确方向）
#
#  为什么补这个方向（2026-09-28 实测）
#    li-pr.sh 原先【只支持 test-first 工作流】：
#      在测试机上改 → submit 把测试机同步回仓库（带漂移检测）。
#    但实际更常见的是 repo-first：
#      在仓库里改 → 部署到测试机验证 → 提交。
#    此时 submit 会走 sync_test_to_repo → 检测到「仓库领先测试机」
#    → 中止：「测试机代码落后于仓库，同步会用旧代码覆盖已合并的改动」。
#
#    这个中止【在它自己的假设下是对的】，但它没有提供 repo-first 的出口，
#    于是只能绕过脚本手工 docker cp + 手工建 PR —— 脚本内置的
#    安全检查、强制验证、提交信息规范全部失效。
#
#    规则没错，缺的是另一条路。
# ───────────────────────────────────────────────────────────────────────────
deploy_repo_to_test() {
  log "部署 仓库 → 测试机"
  if [[ ! -d "$TEST_DIR" ]]; then
    warn "测试机目录不存在，跳过部署：$TEST_DIR"
    return 0
  fi
  local excl=(--exclude='__pycache__' --exclude='*.pyc' --exclude='.identity.json')
  echo "  以下文件将被更新到测试机："
  rsync -a --delete --dry-run --itemize-changes "${excl[@]}" \
    "$REPO_DIR/$REPO_SUB/" "$TEST_DIR/" 2>/dev/null \
    | grep -E '^[<>]f|^\*deleting' | sed 's/^/      /' || echo "      （无变化）"
  echo
  if ! rsync -a --delete "${excl[@]}" "$REPO_DIR/$REPO_SUB/" "$TEST_DIR/"; then
    err "部署失败"
    return 1
  fi
  ok "已部署到测试机"
  echo "      ⚠️ HA 需要重启才加载新代码："
  echo "         docker restart <容器名>"
  return 0
}

# ── 方向自动判定 ──────────────────────────────────────────────────────────
#  判定顺序（三分支，都不会静默丢改动）：
#    ① 仓库有未提交改动            → 仓库是事实源 → deploy（仓库 → 测试机）
#    ② 两侧一致                    → 什么都不做
#    ③ 有差异，且测试机内容【全部】等于仓库历史版本 → 测试机只是落后 → deploy 对齐
#    ④ 有差异，且测试机有【非历史版本】的内容      → 测试机上有新工作 → 同步回来
#  可用 LI_SYNC_MODE=deploy|from-test 强制；submit --from-test / --deploy 亦可。
sync_or_deploy() {
  case "${LI_SYNC_MODE:-auto}" in
    deploy)    deploy_repo_to_test; return $? ;;
    from-test) sync_test_to_repo;   return $? ;;
  esac

  # ① 仓库有未提交的组件改动 → repo-first
  if [[ -n "$(git status --porcelain -- "$REPO_SUB" 2>/dev/null)" ]]; then
    log "仓库有未提交改动 → repo-first（部署 仓库 → 测试机）"
    deploy_repo_to_test
    return $?
  fi

  [[ -d "$TEST_DIR" ]] || { ok "测试机目录不存在，跳过"; return 0; }

  local excl=(--exclude='__pycache__' --exclude='*.pyc' --exclude='.identity.json')
  local drift
  drift=$(rsync -a --delete --dry-run --itemize-changes "${excl[@]}" \
            "$TEST_DIR/" "$REPO_DIR/$REPO_SUB/" 2>/dev/null \
          | grep -E '^[<>]f|^\*deleting' || true)

  # ② 一致
  if [[ -z "$drift" ]]; then
    ok "测试机与仓库一致，无需同步"
    return 0
  fi

  # ③/④ 逐文件判断：测试机版本是否只是仓库的某个历史版本
  local has_new_work=0
  while read -r line; do
    local f; f=$(echo "$line" | awk '{print $NF}')
    [[ -z "$f" ]] && continue
    [[ "$line" == *deleting* ]] && continue      # 测试机多出的文件 → 视为落后
    [[ -f "$TEST_DIR/$f" ]] || continue
    local found=0
    while read -r h; do
      [[ -z "$h" ]] && continue
      if git show "$h:$REPO_SUB/$f" 2>/dev/null | cmp -s - "$TEST_DIR/$f"; then
        found=1; break
      fi
    done < <(git log --all --format=%H -- "$REPO_SUB/$f" 2>/dev/null | head -30)
    if [[ "$found" -eq 0 ]]; then
      has_new_work=1
      warn "  测试机 $f 的内容不属于任何历史版本 → 视为测试机上的新工作"
    fi
  done <<< "$drift"

  if [[ "$has_new_work" -eq 1 ]]; then
    log "测试机有新工作 → test-first（同步 测试机 → 仓库）"
    sync_test_to_repo
  else
    log "测试机内容均为仓库历史版本（只是落后）→ 部署 仓库 → 测试机"
    deploy_repo_to_test
  fi
}

sync_test_to_repo() {
  # ★ 2026-09-27 重写：原实现无条件 `rsync -a --delete 测试机 → 仓库`，
  #   会把仓库里【已提交、但测试机还没部署】的改动直接覆盖掉。
  #
  #   实测（PR #5~#9 合并后）：测试机落后仓库，直接同步会覆盖 12 个文件，
  #   其中 fan.py 的 wheel_heat 会消失 = 已合并的功能被静默回退。
  #
  #   现在：先做 dry-run 漂移检测，发现「仓库领先测试机」就中止并说明。
  log "同步测试机 → 仓库（带漂移检测）"

  if [[ ! -d "$TEST_DIR" ]]; then
    warn "测试机目录不存在，跳过同步：$TEST_DIR"
    return 0
  fi

  local excl=(--exclude='__pycache__' --exclude='*.pyc' --exclude='.identity.json')

  # dry-run：哪些文件会被覆盖
  local changes
  changes=$(rsync -a --delete --dry-run --itemize-changes "${excl[@]}" \
              "$TEST_DIR/" "$REPO_DIR/$REPO_SUB/" 2>/dev/null \
            | grep -E '^[<>]f|^\*deleting' || true)

  if [[ -z "$changes" ]]; then
    ok "测试机与仓库一致，无需同步"
    return 0
  fi

  echo "  将被覆盖/删除："
  echo "$changes" | sed 's/^/      /'
  echo

  # 若仓库工作区/HEAD 有这些文件的更新版本 → 覆盖会丢失改动
  local risky=0
  while read -r line; do
    local f; f=$(echo "$line" | awk '{print $NF}')
    [[ -z "$f" ]] && continue
    # 仓库里该文件相对 HEAD 有未提交改动 → 绝对不能被覆盖
    if ! git diff --quiet HEAD -- "$REPO_SUB/$f" 2>/dev/null; then
      risky=1
      warn "  仓库中 $f 有未提交改动 —— 同步会丢失"
    fi
  done <<< "$changes"

  if [[ "$risky" -eq 1 ]]; then
    err "检测到仓库有未提交改动会被覆盖，已中止同步"
    echo "      → 请先提交/暂存仓库改动，或手动确认后再同步"
    return 1
  fi

  # ★ 更危险的情形：测试机文件是【历史旧版本】（已合并的改动还没部署过去）。
  #   此时同步 = 用旧代码覆盖新代码 = 静默回退已发布的功能。
  #   判据：该文件内容恰好等于 HEAD 历史上某个提交的版本（而非 HEAD 本身）。
  local stale=0
  while read -r line; do
    local f; f=$(echo "$line" | awk '{print $NF}')
    [[ -z "$f" || "$f" == */* && ! -f "$TEST_DIR/$f" ]] && continue
    [[ -f "$TEST_DIR/$f" ]] || continue
    local th rh
    th=$(git hash-object "$TEST_DIR/$f" 2>/dev/null)
    rh=$(git rev-parse "HEAD:$REPO_SUB/$f" 2>/dev/null)
    [[ "$th" == "$rh" ]] && continue          # 与 HEAD 相同 → 不陈旧
    local hit=""
    while read -r c; do
      [[ "$(git rev-parse "$c:$REPO_SUB/$f" 2>/dev/null)" == "$th" ]] && { hit=$c; break; }
    done < <(git rev-list HEAD -- "$REPO_SUB/$f" 2>/dev/null | head -50)
    if [[ -n "$hit" ]]; then
      stale=1
      warn "  $f 是历史旧版本（对应 $(git log -1 --format='%h %s' "$hit" | cut -c1-50)）"
    fi
  done <<< "$changes"

  if [[ "$stale" -eq 1 ]]; then
    err "★ 测试机代码【落后于仓库】—— 同步会用旧代码覆盖已合并的改动，已中止"
    echo "      → 正确做法：先把仓库部署到测试机，再改代码"
    echo "        rsync -a --delete '$REPO_DIR/$REPO_SUB/' '$TEST_DIR/'"
    echo "      → 或确认确实要用测试机版本覆盖（会回退上述提交）："
    echo "        LI_ALLOW_STALE_SYNC=1 $0 submit"
    [[ "${LI_ALLOW_STALE_SYNC:-}" == "1" ]] || return 1
    warn "LI_ALLOW_STALE_SYNC=1，已允许覆盖（请自行确认）"
  fi

  mkdir -p /tmp/li-sync-backups
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  cp -a "$REPO_DIR/$REPO_SUB" "/tmp/li-sync-backups/repo-$ts" 2>/dev/null || true

  rsync -a --delete "${excl[@]}" "$TEST_DIR/" "$REPO_DIR/$REPO_SUB/"
  ok "已同步（备份在 /tmp/li-sync-backups/repo-$ts）"
  warn "注意：以上文件已用测试机版本覆盖 —— 提交前请 git diff 确认"
}

# ───────────────────────────────────────────────────────────────────────────
# 安全检查
# ───────────────────────────────────────────────────────────────────────────
security_check() {
  log "敏感信息扫描"
  local fail=0
  # ★ 2026-09-27：不再硬编码真实凭据（原值已从历史清除）。
  #   方式：环境变量 SENSITIVE_PATTERNS（JSON，与 CI 一致），
  #   或本机忽略文件 ~/.li-sensitive.json
  declare -A P=()
  local src="${SENSITIVE_PATTERNS:-}"
  if [[ -z "$src" && -f "$HOME/.li-sensitive.json" ]]; then
    src=$(cat "$HOME/.li-sensitive.json")
  fi
  if [[ -z "$src" ]]; then
    warn "未配置敏感信息模式（SENSITIVE_PATTERNS 或 ~/.li-sensitive.json）"
    echo "      跳过扫描。配置示例："
    echo "        export SENSITIVE_PATTERNS='{\"手机号\":\"138.*\",\"VIN\":\"LSV.*\"}'"
    return 0
  fi
  # ★ fail-closed：配置写了却解析不了 → 报错退出，绝不静默放过。
  #   （原来异常被 2>/dev/null 吞掉 → 配置非法看起来像「通过」，
  #     安全扫描 fail-open 是危险的。）
  local parsed rc
  parsed=$(printf '%s' "$src" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('PARSE_ERROR: ' + str(e), file=sys.stdout); sys.exit(3)
if not isinstance(d, dict):
    print('PARSE_ERROR: 顶层必须是 JSON 对象', file=sys.stdout); sys.exit(3)
for k, v in d.items():
    print(f'{k}\t{v}')
")
  rc=$?
  if [[ $rc -ne 0 ]]; then
    err "SENSITIVE_PATTERNS 解析失败（JSON 非法）—— 已中止，避免漏检"
    echo "      $parsed"
    echo "      → 注意 JSON 里正则的转义：字面反斜杠要写 \\\\"
    echo "        例如：{\"域名\":\"a\\\\.example\\.com\"}"
    return 1
  fi
  while IFS=$'\t' read -r k v; do
    [[ -n "$k" ]] && P["$k"]="$v"
  done <<< "$parsed"
  for name in "${!P[@]}"; do
    local hits
    hits=$(grep -rlE --exclude-dir=__pycache__ --exclude='*.pyc' \
             "${P[$name]}" "$REPO_DIR/$REPO_SUB" "$REPO_DIR/README.md" 2>/dev/null || true)
    if [[ -n "$hits" ]]; then
      err "发现 $name:"
      echo "$hits" | sed 's/^/      /'
      fail=1
    fi
  done
  [[ $fail -eq 0 ]] && ok "通过" || return 1
}

# ───────────────────────────────────────────────────────────────────────────
# 命令：start —— 建分支
# ───────────────────────────────────────────────────────────────────────────
cmd_start() {
  local type="${1:-}" desc="${2:-}"
  if [[ -z "$type" || -z "$desc" ]]; then
    err "用法: $0 start <类型> <简述>"
    echo "  类型: feat / fix / refactor / docs / chore / ci"
    exit 1
  fi

  # 确保在 main 且干净
  local cur; cur=$(git branch --show-current)
  if [[ "$cur" != "main" ]]; then
    warn "当前在 $cur，切回 main"
    git checkout main 2>&1 | tail -1
  fi
  if [[ -n "$(git status --short)" ]]; then
    err "工作区有未提交改动，请先处理"
    git status --short | head -10 | sed 's/^/    /'
    exit 1
  fi

  git fetch origin main -q 2>/dev/null
  git pull origin main -q 2>/dev/null || warn "拉取失败（可能无网络），继续"

  # 生成分支名
  local slug; slug=$(echo "$desc" | tr '[:upper:]' '[:lower:]' \
                     | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$//' | cut -c1-40)
  local branch="${type}/${slug}"

  git checkout -b "$branch" 2>&1 | tail -1
  ok "已创建分支: ${GRN}$branch${RST}"
  echo
  echo "  下一步："
  echo "    1. 改代码（在测试机: $TEST_DIR）"
  echo "    2. 跑 $0 submit       （同步 + 提交 + 开 PR）"
}

# ───────────────────────────────────────────────────────────────────────────
# 命令：submit —— 提交 + 推送 + 开 PR
# ───────────────────────────────────────────────────────────────────────────
cmd_submit() {
  # --from-test 强制旧方向（test-first）；--deploy 强制部署出去（repo-first）
  while [[ "${1:-}" == --* ]]; do
    case "$1" in
      --from-test) LI_SYNC_MODE=from-test ;;
      --deploy)    LI_SYNC_MODE=deploy ;;
    esac
    shift
  done

  local cur; cur=$(git branch --show-current)
  if [[ "$cur" == "main" ]]; then
    err "当前在 main —— 不能直接提交，请先 ./li-pr.sh start <类型> <简述>"
    exit 1
  fi

  sync_or_deploy || exit 1
  echo
  security_check || { err "安全检查未通过，已中止"; exit 1; }
  echo

  # ★ 强制验证（2026-09-24 新增：修复"改完不验证"的流程缺陷）
  log "强制验证（7 项检查）"
  if ! "$(dirname "$0")/li-verify.sh" quiet; then
    err "验证未通过，已中止 —— 修复后重试"
    exit 1
  fi
  echo

  if [[ -z "$(git status --short)" ]]; then
    warn "无改动可提交"
    exit 0
  fi

  log "变更文件"
  git status --short | sed 's/^/    /'
  echo

  # 生成提交信息
  local type="${cur%%/*}"
  local desc="${cur#*/}"
  local msg
  case "$type" in
    feat)     msg="feat: ${desc//-/ }" ;;
    fix)      msg="fix: ${desc//-/ }" ;;
    refactor) msg="refactor: ${desc//-/ }" ;;
    docs)     msg="docs: ${desc//-/ }" ;;
    ci)       msg="ci: ${desc//-/ }" ;;
    *)        msg="chore: ${desc//-/ }" ;;
  esac

  git add -A
  git commit -q -m "$msg" || { err "提交失败（可能 pre-commit 未通过）"; exit 1; }
  ok "已提交: $(git log --oneline -1)"

  log "推送到 origin"
  if ! git push -u origin "$cur" 2>&1 | tail -2; then
    warn "直连失败，用代理重试"
    git -c http.proxy="$PROXY" push -u origin "$cur" 2>&1 | tail -2
  fi

  # 开 PR
  log "创建 Pull Request"
  local body
  body=$(cat <<EOF
## 变更说明

${msg}

## 变更文件

$(git diff --stat origin/main...HEAD | tail -20)

## 检查清单

- [ ] 已在测试机验证（HA 重启无错误）
- [ ] 敏感信息扫描通过
- [ ] CI 通过

---
*由 li-pr.sh 自动创建*
EOF
)

  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({
    'title': '''$msg''',
    'head': '''$cur''',
    'base': 'main',
    'body': '''$body''',
    'draft': False,
}, ensure_ascii=False))
")

  local resp
  resp=$(gh_api POST "/repos/$GH_REPO/pulls" "$payload")
  echo "$resp" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d.get('html_url'):
    print(f\"  ✅ PR 已创建: {d['html_url']}\")
    print(f\"     #{d['number']}  {d['title']}\")
else:
    msg = d.get('message', '')
    if 'already exists' in str(d.get('errors', '')):
        print('  ⚠️ 该分支已有 PR')
    else:
        print(f\"  ❌ {msg}\")
        for e in d.get('errors', []): print(f'     {e}')
"
}

# ───────────────────────────────────────────────────────────────────────────
# 命令：one —— 一步到位（建分支 + 提交 + PR）
# ───────────────────────────────────────────────────────────────────────────
cmd_one() {
  local msg="${1:-}"
  [[ -z "$msg" ]] && { err "用法: $0 one \"feat: 说明\""; exit 1; }

  local type="${msg%%:*}"
  local desc="${msg#*:}"
  cmd_start "$type" "$desc" || exit 1
  echo
  cmd_submit
}

# ───────────────────────────────────────────────────────────────────────────
# 命令：status / list / clean
# ───────────────────────────────────────────────────────────────────────────
cmd_status() {
  local cur; cur=$(git branch --show-current)
  echo "  当前分支: ${GRN}$cur${RST}"
  echo "  未提交改动: $(git status --short | wc -l) 项"
  echo
  if [[ "$cur" != "main" ]]; then
    echo "  与 main 的差异:"
    git diff --stat origin/main...HEAD 2>/dev/null | tail -10 | sed 's/^/    /'
    echo
    local pr
    pr=$(gh_api GET "/repos/$GH_REPO/pulls?head=c3h3-bi:$cur&state=open" \
         | python3 -c "
import json,sys
d = json.load(sys.stdin)
if d: print(f\"#{d[0]['number']} {d[0]['html_url']}  {d[0]['state']}\")
" 2>/dev/null)
    [[ -n "$pr" ]] && echo "  关联 PR: ${GRN}$pr${RST}" || echo "  关联 PR: （未创建）"
  fi
}

cmd_list() {
  log "Open PRs"
  gh_api GET "/repos/$GH_REPO/pulls?state=open" | python3 -c "
import json,sys
d = json.load(sys.stdin)
if not d: print('  （无）')
for p in d:
    print(f\"  #{p['number']:<4} {p['title']}\")
    print(f\"        {p['html_url']}\")
    print(f\"        分支: {p['head']['ref']}  可合并: {p.get('mergeable_state','?')}\")
"
}

cmd_clean() {
  # --dry-run 只列不删；--remote 一并删除【远端】已合并分支
  local dry=0 do_remote=0
  for a in "$@"; do
    [[ "$a" == "--dry-run" ]] && dry=1
    [[ "$a" == "--remote" ]] && do_remote=1
  done
  [[ $dry -eq 1 ]] && log "清理已合并分支（DRY-RUN，不实际删除）" \
                   || log "清理已合并分支"

  # ★ dry-run 绝不能改变工作区状态。
  #   实测踩坑：原先这里无条件 `git checkout main`，于是一次
  #   `clean --dry-run` 把我从工作分支悄悄切回了 main ——
  #   紧接着的提交就落到了 main 上（本地 main 领先 origin 1 个提交，
  #   而 main 有分支保护，根本推不上去）。
  #   「只看看会删什么」的操作不该有副作用。
  git fetch origin -q --prune 2>/dev/null
  if [[ $dry -eq 0 ]]; then
    git checkout main -q 2>/dev/null
  fi

  local n=0
  for b in $(git branch --format='%(refname:short)' | grep -v '^main$'); do
    if git branch -r --merged origin/main 2>/dev/null | grep -q "origin/$b"; then
      if [[ $dry -eq 1 ]]; then
        echo "  [dry-run] 将删除本地 $b"
      else
        git branch -D "$b" -q 2>/dev/null && { ok "已删除本地 $b"; ((n++)); }
      fi
      ((n++)) || true
    fi
  done

  # 远端：GitHub 合并时通常会自动删，但没开那个选项时分支会一直留着
  if [[ $do_remote -eq 1 ]]; then
    for rb in $(git branch -r --merged origin/main 2>/dev/null \
                | grep -vE 'origin/(HEAD|main)$' | sed 's|origin/||' | tr -d ' '); do
      [[ -z "$rb" ]] && continue
      if [[ $dry -eq 1 ]]; then
        echo "  [dry-run] 将删除远端 origin/$rb"
      else
        git push origin --delete "$rb" -q 2>/dev/null \
          && { ok "已删除远端 origin/$rb"; ((n++)) || true; } \
          || warn "删除远端 origin/$rb 失败（权限/网络？）"
      fi
    done
  else
    local remote_merged
    remote_merged=$(git branch -r --merged origin/main 2>/dev/null \
                    | grep -vE 'origin/(HEAD|main)$' | tr -d ' ')
    [[ -n "$remote_merged" ]] && \
      echo "  ℹ 远端还有已合并分支可清理（加 --remote）：$(echo $remote_merged | tr '\n' ' ')"
  fi

  [[ $n -eq 0 ]] && echo "  （无已合并分支）"
  return 0
}

# ───────────────────────────────────────────────────────────────────────────
case "${1:-status}" in
  start)  shift; cmd_start "$@" ;;
  submit) shift; cmd_submit "$@" ;;
  deploy) deploy_repo_to_test ;;
  one)    shift; cmd_one "$@" ;;
  status) cmd_status ;;
  list)   cmd_list ;;
  clean)  shift; cmd_clean "$@" ;;
  *)
    cat <<USAGE
用法: $0 <命令>

  start <类型> <简述>   从 main 建分支（类型: feat/fix/refactor/docs/ci/chore）
  submit [--deploy|--from-test]
                       同步/部署 + 安全检查 + 验证 + 提交 + 推送 + 开 PR
                       方向【自动判定】：仓库有未提交改动 → 部署出去（repo-first）；
                       否则 → 把测试机改动收回（test-first）。
                       可用 --deploy / --from-test 或 LI_SYNC_MODE 强制。
  deploy               只把仓库代码部署到测试机（不含提交；HA 需重启生效）
  one "类型: 简述"      一步到位（start + submit）
  status               看当前分支/改动/关联 PR
  list                 列出所有 open PR
  clean [--dry-run] [--remote]
                       清理已合并的本地分支；--remote 一并删远端；
                       --dry-run 只列不删

典型流程：
  $0 start feat 优化登录流程
  # 改代码...
  $0 submit              → 生成 PR，等人类合并

USAGE
    exit 1
    ;;
esac
