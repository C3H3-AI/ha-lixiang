#!/usr/bin/env bash
# ============================================================================
#  理想汽车 HA 集成 —— 双副本同步脚本
# ============================================================================
#
#  背景
#  ----
#  HA 无法从软链接加载 custom_component（报 `No module named
#  'custom_components.'`），所以「单一源码 + 软链接」方案不可行。
#  最终采用「双副本 + 本脚本同步」：
#
#    测试机（HA 实际运行）          仓库（发布到 GitHub）
#    .../config/custom_components/  /media/.../ha-lixiang/
#          lixiang_auto/            custom_components/lixiang_auto/
#
#  用法
#  ----
#    ./li-sync.sh status      # 查看两边差异（默认）
#    ./li-sync.sh push-repo   # 测试机 → 仓库（改完代码后）
#    ./li-sync.sh pull-test   # 仓库 → 测试机（拉取别人改动后）
#    ./li-sync.sh check       # 安全检查（敏感信息扫描）
#    ./li-sync.sh commit "msg"  # 同步 + 提交 + 推送
#
#  安全
#  ----
#  - 脚本会在 pull 前自动备份测试机
#  - push 前会做敏感信息扫描，发现异常时终止
# ============================================================================

set -euo pipefail

# ★ 可移植：默认值可用环境变量覆盖（换机器不用改脚本）
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 脚本若在仓库内(scripts/)，workspace 是上一级；否则脚本所在目录即 workspace
if [[ -f "$_SELF_DIR/../.git/config" && "$_SELF_DIR" == */scripts ]]; then
  _WORKSPACE="${LI_WORKSPACE:-$(cd "$_SELF_DIR/.." && pwd)}"
else
  _WORKSPACE="${LI_WORKSPACE:-$_SELF_DIR}"
fi
TEST_DIR="${LI_TEST_DIR:-$_WORKSPACE/home-assistant-nas/ha-test/config/custom_components/lixiang_auto}"
REPO_DIR="${LI_REPO_DIR:-$_WORKSPACE/ha-lixiang}"
REPO_SUB="custom_components/lixiang_auto"
BACKUP_DIR="${LI_BACKUP_DIR:-/tmp/li-sync-backups}"

# 参与同步的文件类型
PATTERNS=(--include='*.py' --include='*.json' --include='*.yaml'
          --include='*.md' --include='*.png' --include='*.jpg')
EXCLUDES=(--exclude='__pycache__' --exclude='*.pyc' --exclude='.identity.json')

C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
C_BLU=$'\033[34m'; C_RST=$'\033[0m'

log()  { echo "${C_BLU}▸${C_RST} $*"; }
ok()   { echo "${C_GRN}✓${C_RST} $*"; }
warn() { echo "${C_YEL}!${C_RST} $*"; }
err()  { echo "${C_RED}✗${C_RST} $*" >&2; }

# ---------------------------------------------------------------------------
# 差异检测
# ---------------------------------------------------------------------------
do_status() {
  log "对比两边差异"
  echo "  测试机: $TEST_DIR"
  echo "  仓库:   $REPO_DIR/$REPO_SUB"
  echo

  local out
  out=$(diff -rq "${EXCLUDES[@]}" "$TEST_DIR" "$REPO_DIR/$REPO_SUB" 2>&1 || true)

  if [[ -z "$out" ]]; then
    ok "完全一致，无需同步"
    return 0
  fi

  # 过滤掉 __pycache__ 噪音
  out=$(echo "$out" | grep -v '__pycache__' || true)
  if [[ -z "$out" ]]; then
    ok "完全一致（仅 __pycache__ 差异）"
    return 0
  fi

  warn "存在差异："
  echo "$out" | sed 's/^/    /'
  echo
  echo "  ${C_YEL}下一步：${C_RST}"
  echo "    改的是测试机 → ./li-sync.sh push-repo"
  echo "    改的是仓库   → ./li-sync.sh pull-test"
  return 1
}

# ---------------------------------------------------------------------------
# 敏感信息扫描
# ---------------------------------------------------------------------------
do_check() {
  log "敏感信息扫描"
  local found=0
  # ★ 不再硬编码真实凭据（2026-09-27）。
  #   原因：脚本在仓库外，不在任何自动检查覆盖内，硬编码的凭据长期未被发现。
  #   改为从环境变量 SENSITIVE_PATTERNS（JSON，与 CI 一致）或 ~/.li-sensitive.json 读取。
  #   格式：{"手机号":"137[0-9]{8}","VIN":"HLX32B14XR[0-9]{5}"}
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
  # ★ fail-closed：配置了却解析失败 → 报错，绝不静默放过
  local parsed
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
  if [[ $? -ne 0 ]]; then
    err "SENSITIVE_PATTERNS 解析失败（JSON 非法）—— 已中止，避免漏检"
    echo "      $parsed"
    return 1
  fi
  local patterns=()
  while IFS=$'\t' read -r k v; do
    [[ -n "$k" ]] && patterns+=("$v:$k")
  done <<< "$parsed"

  for p in "${patterns[@]}"; do
    local kw="${p%%:*}" name="${p##*:}"
    local hits
    hits=$(grep -rl "$kw" "$TEST_DIR" \
             --include='*.py' --include='*.json' --include='*.yaml' \
             2>/dev/null | grep -v '__pycache__' || true)
    if [[ -n "$hits" ]]; then
      warn "$name 出现在："
      echo "$hits" | sed "s|$TEST_DIR/|      |"
      found=1
    fi
  done

  # 已知允许存在的：const.py 的签名凭据（API 必需，非个人隐私）
  if [[ $found -eq 0 ]]; then
    ok "未发现敏感信息"
    return 0
  fi
  # ★ fail-closed（2026-09-27）：原来这里只 warn 然后 `return 0`，
  #   等于扫描永远不能阻止发布 —— 一个「只提示不拦截」的检查形同虚设。
  err "发现敏感信息 —— 已中止（内容将被推到公开仓库）"
  echo "      （注：const.py 的 hac_key/key_id/xdev/app_token 是 API 签名必需，属允许项，"
  echo "        如命中属误报，请调整 SENSITIVE_PATTERNS 而不是绕过本检查）"
  return 1
}

# ---------------------------------------------------------------------------
# 测试机 → 仓库
# ---------------------------------------------------------------------------
# ★ 陈旧检测：测试机文件是否为「HEAD 历史上的旧版本」
#   命中即说明测试机落后于仓库 —— 此时同步 = 用旧代码覆盖已合并的功能。
#   2026-09-27 实测复现：会把 fan.py 的 wheel_heat 抹掉（= 回退 PR #5）、
#   manifest 版本回退。备份不能算防护：覆盖结果随后就被 commit 了。
stale_guard() {
  cd "$REPO_DIR" || return 1
  local sub="${REPO_SUB#"$REPO_DIR"/}"
  local changes stale=0
  changes=$(rsync -a --delete --dry-run --itemize-changes "${EXCLUDES[@]}" \
              "$TEST_DIR/" "$REPO_DIR/$REPO_SUB/" 2>/dev/null \
            | grep -E '^[<>]f|^\*deleting' || true)
  while read -r line; do
    local f; f=$(echo "$line" | awk '{print $NF}')
    [[ -z "$f" || ! -f "$TEST_DIR/$f" ]] && continue
    local th rh
    th=$(git hash-object "$TEST_DIR/$f" 2>/dev/null)
    rh=$(git rev-parse "HEAD:$sub/$f" 2>/dev/null)
    [[ "$th" == "$rh" ]] && continue
    local hit=""
    while read -r c; do
      [[ "$(git rev-parse "$c:$sub/$f" 2>/dev/null)" == "$th" ]] && { hit=$c; break; }
    done < <(git rev-list HEAD -- "$sub/$f" 2>/dev/null | head -50)
    if [[ -n "$hit" ]]; then
      stale=1
      warn "  $f 是历史旧版本（对应 $(git log -1 --format='%h %s' "$hit" | cut -c1-50)）"
    fi
  done <<< "$changes"

  if [[ "$stale" -eq 1 ]]; then
    err "★ 测试机代码【落后于仓库】—— 同步会用旧代码覆盖已合并的改动，已中止"
    echo "      → 正确做法：先把仓库部署到测试机，再改代码"
    echo "        $0 pull-test   # 仓库 → 测试机（部署）"
    echo "      → 或确认确实要用测试机版本覆盖（会回退上述提交）："
    echo "        LI_ALLOW_STALE_SYNC=1 $0 push-repo"
    [[ "${LI_ALLOW_STALE_SYNC:-}" == "1" ]] || return 1
    warn "LI_ALLOW_STALE_SYNC=1，已允许覆盖（请自行确认）"
  fi
  return 0
}

do_push_repo() {
  log "同步：测试机 → 仓库"
  do_check || return 1
  echo

  # ★ 方向风险检查：测试机落后时禁止覆盖仓库
  stale_guard || return 1
  echo

  # 备份仓库侧（便于回滚）
  mkdir -p "$BACKUP_DIR"
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  cp -a "$REPO_DIR/$REPO_SUB" "$BACKUP_DIR/repo-$ts" 2>/dev/null || true
  ok "已备份仓库侧 → $BACKUP_DIR/repo-$ts"

  rsync -a --delete "${EXCLUDES[@]}" \
        "$TEST_DIR/" "$REPO_DIR/$REPO_SUB/"
  ok "文件已同步"

  cd "$REPO_DIR"
  if [[ -z "$(git status --short)" ]]; then
    ok "无变更，无需提交"
  else
    echo
    git status --short | sed 's/^/    /'
    echo
    warn "请在仓库目录手动 commit："
    echo "    cd $REPO_DIR"
    echo "    git add -A && git commit -m '...' && git push"
  fi
}

# ---------------------------------------------------------------------------
# 仓库 → 测试机
# ---------------------------------------------------------------------------
do_pull_test() {
  log "同步：仓库 → 测试机"
  mkdir -p "$BACKUP_DIR"
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  sudo cp -a "$TEST_DIR" "$BACKUP_DIR/test-$ts"
  ok "已备份测试机 → $BACKUP_DIR/test-$ts"

  sudo rsync -a --delete "${EXCLUDES[@]}" \
       "$REPO_DIR/$REPO_SUB/" "$TEST_DIR/"
  sudo chown -R duola:duola "$TEST_DIR"
  ok "文件已同步（属主已修正）"

  warn "需要重启 HA 生效："
  echo "    docker restart homeassistant-test"
}

# ---------------------------------------------------------------------------
# 一键：同步 + 提交 + 推送
# ---------------------------------------------------------------------------
do_commit() {
  local msg="${1:-}"
  if [[ -z "$msg" ]]; then
    err "用法: $0 commit \"提交说明\""
    exit 1
  fi

  do_push_repo
  echo
  log "提交到 GitHub"
  cd "$REPO_DIR"
  if [[ -z "$(git status --short)" ]]; then
    ok "无变更"
    return 0
  fi
  git add -A
  git commit -q -m "$msg"
  ok "已提交: $(git log --oneline -1)"

  log "推送到 GitHub"
  if git push 2>&1 | tail -2; then
    ok "推送成功"
  else
    warn "推送失败，尝试用代理重试"
    git -c http.proxy=http://127.0.0.1:7890 push 2>&1 | tail -2
  fi
}

# ---------------------------------------------------------------------------
case "${1:-status}" in
  status)    do_status ;;
  check)     do_check ;;
  push-repo) do_push_repo ;;
  pull-test) do_pull_test ;;
  commit)    shift; do_commit "$@" ;;
  *)
    cat <<USAGE
用法: $0 <命令>

  status           查看两边差异（默认）
  check            敏感信息扫描
  push-repo        测试机 → 仓库（改完代码后）
  pull-test        仓库 → 测试机（拉取改动后，需重启 HA）
  commit "说明"    同步 + 提交 + 推送 GitHub

USAGE
    exit 1
    ;;
esac
