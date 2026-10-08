#!/usr/bin/env bash
# ============================================================================
#  理想汽车 HA 集成 —— 技能文档同步脚本
# ============================================================================
#
#  背景
#  ----
#  技能文档需要同时存在于两处：
#
#    仓库（版本化、随 PR 评审）          本机（AI 助手真正加载的位置）
#    <repo>/docs/skills/<name>/         ${DSH_HOME:-~/.dsh}/skills/<name>/
#
#  · 只改仓库、不装到本机 → AI 助手加载的是旧版（出现内容漂移）
#  · 只改本机、不提交仓库 → 下次同步即丢失
#
#  用法
#  ----
#    ./scripts/li-skills.sh status    # 对比两边差异（默认动作）
#    ./scripts/li-skills.sh install   # 仓库 → 本机（安装 / 更新）
#    ./scripts/li-skills.sh check     # 一致性校验（不一致退出 1，可用于自检）
#    ./scripts/li-skills.sh list      # 列出仓库内的技能与 frontmatter
#
#  环境变量
#  --------
#    DSH_HOME         DSH 主目录（默认 ~/.dsh）
#    LI_SKILLS_DIR    直接覆盖本机技能目录（默认 $DSH_HOME/skills）
#
#  退出码
#  ------
#    0  成功 / 一致
#    1  不一致（check）或用法错误
# ============================================================================

set -euo pipefail

_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$_SELF_DIR/../.git/config" && "$_SELF_DIR" == */scripts ]]; then
  REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
else
  REPO_ROOT="$_SELF_DIR"
fi
SRC_DIR="$REPO_ROOT/docs/skills"
DST_DIR="${LI_SKILLS_DIR:-${DSH_HOME:-$HOME/.dsh}/skills}"

_ok()   { printf '  \033[32m✅\033[0m %s\n' "$*"; }
_warn() { printf '  \033[33m⚠️\033[0m %s\n' "$*"; }
_err()  { printf '  \033[31m❌\033[0m %s\n' "$*" >&2; }
_hdr()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

_skills() {
  # 列出仓库内所有含 SKILL.md 的技能目录名
  local d
  for d in "$SRC_DIR"/*/; do
    [[ -f "$d/SKILL.md" ]] && basename "$d"
  done
}

_frontmatter_name() {
  # 读取 SKILL.md frontmatter 的 name 字段
  sed -n '2,/^---$/p' "$1" 2>/dev/null | sed -n 's/^name:[[:space:]]*//p' | head -1
}

cmd_list() {
  _hdr "仓库技能（$SRC_DIR）"
  local s n count=0
  for s in $(_skills); do
    n="$(_frontmatter_name "$SRC_DIR/$s/SKILL.md")"
    if [[ -n "$n" ]]; then
      _ok "$s  (frontmatter name: $n)"
    else
      _err "$s  (缺少 frontmatter name —— AI 助手无法识别)"
    fi
    count=$((count + 1))
  done
  [[ $count -eq 0 ]] && _warn "未找到任何技能" || true
}

cmd_status() {
  _hdr "技能同步状态"
  printf '  仓库: %s\n' "$SRC_DIR"
  printf '  本机: %s\n\n' "$DST_DIR"

  if [[ ! -d "$DST_DIR" ]]; then
    _warn "本机技能目录不存在（尚未安装过技能）"
  fi

  local s found=0
  for s in $(_skills); do
    found=1
    if [[ ! -d "$DST_DIR/$s" ]]; then
      _err "$s —— 本机未安装（AI 助手看不到）"
    elif diff -rq "$SRC_DIR/$s" "$DST_DIR/$s" >/dev/null 2>&1; then
      _ok "$s —— 一致"
    else
      _warn "$s —— 有差异："
      diff -rq "$SRC_DIR/$s" "$DST_DIR/$s" 2>/dev/null | sed 's/^/       /' || true
    fi
  done
  [[ $found -eq 1 ]] || _warn "仓库内没有技能"
}

cmd_install() {
  _hdr "安装技能到本机"
  mkdir -p "$DST_DIR"
  local s found=0
  for s in $(_skills); do
    found=1
    mkdir -p "$DST_DIR/$s"
    # --delete 语义：先清空再复制，确保本机不会残留已从仓库删除的文件
    rm -rf "${DST_DIR:?}/$s"
    cp -r "$SRC_DIR/$s" "$DST_DIR/$s"
    _ok "$s → $DST_DIR/$s"
  done
  [[ $found -eq 1 ]] || _warn "仓库内没有技能，未做任何改动"
  printf '\n'
  cmd_status
}

cmd_check() {
  _hdr "技能一致性校验"
  if [[ ! -d "$DST_DIR" ]]; then
    _warn "本机技能目录不存在（$DST_DIR）—— 跳过校验"
    _warn "（CI 环境属正常；本机请执行：./scripts/li-skills.sh install）"
    exit 0
  fi

  local s rc=0 found=0
  for s in $(_skills); do
    found=1
    if [[ ! -d "$DST_DIR/$s" ]]; then
      _err "$s 未安装到本机"
      rc=1
    elif ! diff -rq "$SRC_DIR/$s" "$DST_DIR/$s" >/dev/null 2>&1; then
      _err "$s 与本机不一致"
      diff -rq "$SRC_DIR/$s" "$DST_DIR/$s" 2>/dev/null | sed 's/^/     /' || true
      rc=1
    else
      _ok "$s 一致"
    fi
  done

  if [[ $found -eq 0 ]]; then
    _warn "仓库内没有技能"
    exit 0
  fi

  if [[ $rc -eq 0 ]]; then
    printf '\n'
    _ok "全部一致"
  else
    printf '\n'
    _err "存在不一致 —— 执行 ./scripts/li-skills.sh install 修复"
  fi
  return $rc
}

case "${1:-status}" in
  status)  cmd_status ;;
  install) cmd_install ;;
  check)   cmd_check ;;
  list)    cmd_list ;;
  -h|--help|help)
    sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *)
    _err "未知动作：$1"
    printf '  可用：status | install | check | list\n' >&2
    exit 1
    ;;
esac
