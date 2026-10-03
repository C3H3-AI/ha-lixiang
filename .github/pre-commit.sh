#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  ha-lixiang pre-commit hook
#  提交前自动检查：语法 / JSON / 敏感信息 / manifest 一致性
#
#  安装：cp pre-commit.sh ha-lixiang/.git/hooks/pre-commit && chmod +x
# ═══════════════════════════════════════════════════════════════════════════

set -uo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RST=$'\033[0m'
FAIL=0

echo "${YEL}▸ pre-commit 检查${RST}"

# 只检查 staged 的文件
STAGED=$(git diff --cached --name-only --diff-filter=ACM)
[[ -z "$STAGED" ]] && { echo "  无 staged 文件"; exit 0; }

# ── 1. Python 语法 ─────────────────────────────────────────────────────
echo "  [1/4] Python 语法"
for f in $(echo "$STAGED" | grep '\.py$' || true); do
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    echo "${RED}    ✗ 语法错误: $f${RST}"
    python3 -m py_compile "$f" 2>&1 | head -5 | sed 's/^/        /'
    FAIL=1
  fi
done
[[ $FAIL -eq 0 ]] && echo "${GRN}    ✓ 通过${RST}"

# ── 2. JSON 有效性 ─────────────────────────────────────────────────────
echo "  [2/4] JSON 有效性"
JFAIL=0
for f in $(echo "$STAGED" | grep '\.json$' || true); do
  if ! python3 -c "import json,sys; json.load(open('$f',encoding='utf-8'))" 2>/dev/null; then
    echo "${RED}    ✗ JSON 无效: $f${RST}"
    JFAIL=1; FAIL=1
  fi
done
[[ $JFAIL -eq 0 ]] && echo "${GRN}    ✓ 通过${RST}"

# ── 3. 敏感信息检查（本机配置，不进仓库）───────────────────────────────
echo "  [3/4] 敏感信息"
# 注意：const.py 的 hac_key/key_id/xdev/app_token 是 API 签名必需，属允许项
#
# ★ 与 CI 统一：同一种 JSON 格式，两处都能用
#   · 环境变量 SENSITIVE_PATTERNS
#   · 或本机文件 ~/.li-sensitive.json（推荐：不必每次 export，且绝不入仓库）
#   格式：{"手机号":"137[0-9]{8}","VIN":"HLX32B14XR[0-9]{5}"}
SFAIL=0
_SRC="${SENSITIVE_PATTERNS:-}"
if [[ -z "$_SRC" && -f "$HOME/.li-sensitive.json" ]]; then
  _SRC=$(cat "$HOME/.li-sensitive.json")
fi
if [[ -z "$_SRC" ]]; then
  echo "${YEL}    ! 未配置敏感信息模式，跳过${RST}"
  echo "        配置示例：echo '{\"手机号\":\"138.*\"}' > ~/.li-sensitive.json"
else
  # ★ fail-closed：配置了却解析失败 → 报错，不能静默放过
  _PARSED=$(printf '%s' "$_SRC" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('PARSE_ERROR: ' + str(e)); sys.exit(3)
if not isinstance(d, dict):
    print('PARSE_ERROR: 顶层必须是 JSON 对象'); sys.exit(3)
for k, v in d.items():
    print(f'{k}\t{v}')
" 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "${RED}    ✗ SENSITIVE_PATTERNS 解析失败（JSON 非法）—— 已阻止提交${RST}"
    echo "        $_PARSED" | head -3 | sed 's/^/        /'
    echo "        提示：JSON 里正则的字面反斜杠要写成 \\\\"
    SFAIL=1; FAIL=1
  else
    while IFS=$'\t' read -r name kw; do
      [[ -z "$name" ]] && continue
      hits=$(echo "$STAGED" | xargs grep -lE "$kw" 2>/dev/null || true)
      if [[ -n "$hits" ]]; then
        echo "${RED}    ✗ 发现 $name:${RST}"
        echo "$hits" | sed 's/^/        /'
        SFAIL=1; FAIL=1
      fi
    done <<< "$_PARSED"
  fi
fi
if [[ $SFAIL -eq 0 ]]; then
  echo "${GRN}    ✓ 通过（或未设置）${RST}"
fi

# ── 4. manifest / strings 一致性 ────────────────────────────────────────
echo "  [4/4] manifest 与 strings 一致性"
if [[ -f custom_components/lixiang_auto/manifest.json ]]; then
  MVER=$(python3 -c "import json;print(json.load(open('custom_components/lixiang_auto/manifest.json'))['version'])" 2>/dev/null || echo "?")
  echo "    manifest version: $MVER"
  # 检查 strings.json 与 translations 是否同步
  if [[ -f custom_components/lixiang_auto/strings.json && \
        -f custom_components/lixiang_auto/translations/zh-Hans.json ]]; then
    if ! diff -q custom_components/lixiang_auto/strings.json \
                 custom_components/lixiang_auto/translations/zh-Hans.json >/dev/null 2>&1; then
      echo "${YEL}    ! strings.json 与 translations/zh-Hans.json 不同步${RST}"
      echo "${YEL}      建议: cp strings.json translations/zh-Hans.json${RST}"
    else
      echo "${GRN}    ✓ 翻译文件同步${RST}"
    fi
  fi
fi

echo
if [[ $FAIL -ne 0 ]]; then
  echo "${RED}✗ 检查未通过，提交已阻止${RST}"
  echo "  修复后重试，或 git commit --no-verify 强制提交"
  exit 1
fi
echo "${GRN}✓ 全部检查通过${RST}"
exit 0
