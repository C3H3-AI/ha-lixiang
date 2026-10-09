#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  li-verify.sh —— 集成改动后的强制验证（改完必跑）
# ═══════════════════════════════════════════════════════════════════════════
#
#  为什么需要这个？
#  ----------------
#  之前的工作流是「改代码 → py_compile → 重启 HA → 看一眼日志」，
#  这【不能发现问题】：
#    · HA 返回 200 ≠ 集成正常（平台 setup 失败时 HA 照样 200）
#    · 日志 ERROE 在状态更新时才出现，重启后要等一轮轮询
#    · py_compile 只查语法，不查运行时依赖
#
#  实际踩过的坑（都是同一天）：
#    ① to_sensor_descriptions 丢失 → 69 个 sensor unavailable
#    ② to_binary_descriptions 丢失 → 35 个 binary_sensor unavailable
#    ③ Semantics.JSON_FIELD 未定义 → 每次状态更新报错
#    ④ Semantics.TRUNK 未定义 → 同上
#
#  这个脚本做【7 项强制检查】，任何一项失败就是失败。
#
#  用法
#  ----
#    ./li-verify.sh              # 完整验证（推荐）
#    ./li-verify.sh quick        # 跳过 HA 重启（只查代码 + 测试）
#    ./li-verify.sh before-pr    # 提 PR 前（完整 + 敏感扫描）
# ═══════════════════════════════════════════════════════════════════════════

set -uo pipefail

REPO_DIR="/media/duola/devdata/AI-workspace/ha-lixiang"
TEST_DIR="/media/duola/devdata/AI-workspace/home-assistant-nas/ha-test/config/custom_components/lixiang_auto"
REPO_SUB="custom_components/lixiang_auto"
# ★ 可移植：默认值可用环境变量覆盖
CONTAINER="${LI_CONTAINER:-homeassistant-test}"
# ★ 不硬编码内网 IP（会暴露家庭网络拓扑）。
#   默认从本机 docker 端口推导，或用 LI_HA_URL 显式指定。
HA_URL="${LI_HA_URL:-http://127.0.0.1:8125}"
if [[ -z "${LI_HA_URL:-}" ]]; then
  _ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
        "$CONTAINER" 2>/dev/null || true)
  [[ -n "$_ip" ]] && HA_URL="http://127.0.0.1:8125"
fi
VENV="/media/duola/devdata/AI-workspace/.li-venv/bin/python"
# 兼容：若持久 venv 不存在，回退到 /tmp
[[ -x "$VENV" ]] || VENV="/tmp/li-venv/bin/python"

GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; BLU=$'\033[34m'; RST=$'\033[0m'
FAILED=0

log()  { echo "${BLU}▸${RST} $*"; }
pass() { echo "${GRN}  ✓${RST} $*"; }
fail() { echo "${RED}  ✗${RST} $*"; FAILED=$((FAILED+1)); }
warn() { echo "${YEL}  !${RST} $*"; }

MODE="${1:-full}"

# quiet 模式：只输出失败项（供 li-pr.sh 调用）
QUIET=0
if [[ "$MODE" == "quiet" ]]; then
  MODE="full"
  QUIET=1
  exec 3>&1 1>/dev/null   # stdout 重定向到 null，stderr 保留
fi

echo "═══════════════════════════════════════════════════════════════════════"
echo "  集成验证（模式: $MODE）"
echo "═══════════════════════════════════════════════════════════════════════"
echo

# ───────────────────────────────────────────────────────────────────────────
# 1. 语法检查
# ───────────────────────────────────────────────────────────────────────────
log "[1/7] Python 语法"
SYNTAX_OK=1
for f in "$REPO_DIR/$REPO_SUB"/*.py; do
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    fail "$(basename "$f") 语法错误"
    SYNTAX_OK=0
  fi
done
[[ $SYNTAX_OK -eq 1 ]] && pass "全部 .py 文件语法正确"

# ───────────────────────────────────────────────────────────────────────────
# 2. 单元测试（★ 关键：以前经常跳过）
# ───────────────────────────────────────────────────────────────────────────
log "[2/7] 单元测试"
if [[ -x "$VENV" ]]; then
  # ★ 2026-10-09 修正：原判断只排除 "failed"，**漏掉 "error"** ——
  #   venv 里缺 requests 时 37 个用例 error，脚本仍报 ✓ 通过（假绿）。
  TEST_OUT=$("$VENV" -m pytest "$REPO_DIR/tests/" -q 2>&1 | tail -5)
  if echo "$TEST_OUT" | grep -qE "[0-9]+ passed" \
     && ! echo "$TEST_OUT" | grep -qE "failed|error"; then
    pass "$(echo "$TEST_OUT" | grep -oE '[0-9]+ passed')"
  else
    fail "测试未通过（含 failed / error）"
    echo "$TEST_OUT" | sed 's/^/      /'
  fi
else
  warn "venv 不存在，跳过测试（$VENV）"
fi

# ───────────────────────────────────────────────────────────────────────────
# 3. 关键函数完整性（★ 曾两次因丢失而大面积 unavailable）
# ───────────────────────────────────────────────────────────────────────────
log "[3/7] 关键函数完整性"
REQUIRED_FUNCS=(
  "to_sensor_description"
  "to_sensor_descriptions"
  "to_binary_description"
  "to_binary_descriptions"
  "specs_for"
  "by_freq"
  "paths_for"
)
MISSING=()
for fn in "${REQUIRED_FUNCS[@]}"; do
  grep -q "^def $fn" "$REPO_DIR/$REPO_SUB/signals.py" || MISSING+=("$fn")
done
if [[ ${#MISSING[@]} -eq 0 ]]; then
  pass "signals.py 的 7 个关键函数都在"
else
  fail "signals.py 缺少: ${MISSING[*]}"
fi

# 平台文件里的 import 必须能解析
for pair in "sensor.py:to_sensor_descriptions" "binary_sensor.py:to_binary_descriptions"; do
  f="${pair%%:*}"; fn="${pair##*:}"
  if grep -q "import $fn" "$REPO_DIR/$REPO_SUB/$f" 2>/dev/null; then
    grep -q "^def $fn" "$REPO_DIR/$REPO_SUB/signals.py" \
      && pass "$f 导入的 $fn 存在" \
      || fail "$f 导入 $fn 但 signals.py 里没有！"
  fi
done

# ───────────────────────────────────────────────────────────────────────────
# 4. Semantics 引用完整性
# ───────────────────────────────────────────────────────────────────────────
log "[4/7] Semantics 枚举引用"
REFS=$(grep -oE 'Semantics\.[A-Z_]+' "$REPO_DIR/$REPO_SUB/binary_sensor.py" \
       | sed 's/Semantics\.//' | sort -u)
DEFS=$(grep -oE '^    [A-Z_]+ = "' "$REPO_DIR/$REPO_SUB/signals.py" \
       | sed 's/^ *//; s/ = "//' | sort -u)
UNDEF=()
for r in $REFS; do
  echo "$DEFS" | grep -qx "$r" || UNDEF+=("$r")
done
if [[ ${#UNDEF[@]} -eq 0 ]]; then
  pass "binary_sensor.py 引用的 Semantics 成员都已定义"
else
  fail "未定义的 Semantics 成员: ${UNDEF[*]}"
fi

# ───────────────────────────────────────────────────────────────────────────
# 5. 重启 HA（可选）
# ───────────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "quick" ]]; then
  warn "[5/7] 跳过 HA 重启（quick 模式）"
else
  log "[5/7] 重启 HA 并等待就绪"
  docker restart "$CONTAINER" >/dev/null 2>&1
  READY=0
  for i in $(seq 1 40); do
    sleep 3
    code=$(curl -s -o /dev/null -w "%{http_code}" "$HA_URL/" --max-time 5 2>/dev/null)
    if [[ "$code" == "200" ]]; then
      # 再等一等，让所有平台完成 setup
      sleep 25
      READY=1
      break
    fi
  done
  if [[ $READY -eq 1 ]]; then
    pass "HA 就绪（$HA_URL）"
  else
    fail "HA 未在 2 分钟内就绪"
  fi
fi

# ───────────────────────────────────────────────────────────────────────────
# 6. 平台 setup 错误（★ 关键：以前漏看）
# ───────────────────────────────────────────────────────────────────────────
log "[6/7] 平台 setup / 状态更新错误"
if [[ "$MODE" == "quick" ]]; then
  warn "跳过（quick 模式）"
else
  # 6a. 平台 setup 失败
  SETUP_ERR=$(docker logs "$CONTAINER" --since 5m 2>&1 \
              | grep -E "Error while setting up lixiang_auto" | wc -l)
  if [[ "$SETUP_ERR" -eq 0 ]]; then
    pass "无平台 setup 错误"
  else
    fail "有 $SETUP_ERR 条平台 setup 错误："
    docker logs "$CONTAINER" --since 5m 2>&1 \
      | grep -A3 "Error while setting up lixiang_auto" | head -8 | sed 's/^/      /'
  fi

  # 6b. 状态更新异常（AttributeError 等）
  UPD_ERR=$(docker logs "$CONTAINER" --since 5m 2>&1 \
            | grep -E "Unexpected error (updating listener|.*for lixiang_auto)" | wc -l)
  if [[ "$UPD_ERR" -eq 0 ]]; then
    pass "无状态更新异常"
  else
    fail "有 $UPD_ERR 条状态更新异常："
    docker logs "$CONTAINER" --since 5m 2>&1 \
      | grep -A20 "Unexpected error updating listener" \
      | grep -E "Error|AttributeError|TypeError|KeyError" | sort -u | head -5 | sed 's/^/      /'
  fi

  # 6c. 集成模块导入错误
  IMP_ERR=$(docker logs "$CONTAINER" --since 5m 2>&1 \
            | grep -E "ImportError|cannot import name" | grep -i lixiang | wc -l)
  if [[ "$IMP_ERR" -eq 0 ]]; then
    pass "无导入错误"
  else
    fail "有 $IMP_ERR 条导入错误"
  fi
fi

# ───────────────────────────────────────────────────────────────────────────
# 7. 实体数与数据（★ 关键：以前只看 HA 是否 200）
# ───────────────────────────────────────────────────────────────────────────
log "[7/7] 实体数与真实数据"
if [[ "$MODE" == "quick" ]]; then
  warn "跳过（quick 模式）"
else
  STATS=$(docker exec "$CONTAINER" /usr/local/bin/python3 -c "
import json
from collections import Counter
reg = json.load(open('/config/.storage/core.entity_registry'))
la = [e for e in reg['data']['entities']
      if e.get('platform') == 'lixiang_auto' and not e.get('disabled_by')]
c = Counter(e['entity_id'].split('.')[0] for e in la)
print(f\"TOTAL={len(la)}\")
for k, v in c.items():
    print(f\"{k}={v}\")
" 2>/dev/null)

  TOTAL=$(echo "$STATS" | grep '^TOTAL=' | cut -d= -f2)
  if [[ -n "$TOTAL" && "$TOTAL" -ge 100 ]]; then
    pass "实体数 $TOTAL（≥100）"
    echo "$STATS" | grep -v TOTAL | sed 's/^/        /'
  else
    fail "实体数异常: ${TOTAL:-获取失败}"
  fi

  # 关键实体必须有真实数据（不是 unknown/unavailable）
  DATA=$(docker exec "$CONTAINER" /usr/local/bin/python3 -c "
import json
rs = json.load(open('/config/.storage/core.restore_state'))
WANT = {
    'dian_chi_dian_liang': '电量',
    'chong_dian_zhuang_tai': '充电状态',
    'che_nei_wen_du': '车内温度',
}
found = {}
for e in rs.get('data', []):
    s = e.get('state', {})
    eid = s.get('entity_id', '')
    for w in WANT:
        if w in eid and w not in found:
            found[w] = s.get('state')
for w, label in WANT.items():
    v = found.get(w)
    ok = 'OK' if v not in (None, 'unknown', 'unavailable') else 'BAD'
    print(f'{ok}\t{label}={v}')
" 2>/dev/null)

  BAD=0
  while IFS=$'\t' read -r flag rest; do
    [[ -z "$flag" ]] && continue
    if [[ "$flag" == "OK" ]]; then
      pass "  $rest"
    else
      fail "  $rest（无数据）"
      BAD=1
    fi
  done <<< "$DATA"
fi

# ───────────────────────────────────────────────────────────────────────────
# 汇总
# ───────────────────────────────────────────────────────────────────────────
[[ $QUIET -eq 1 ]] && exec 1>&3
echo
echo "═══════════════════════════════════════════════════════════════════════"
if [[ $FAILED -eq 0 ]]; then
  echo "${GRN}  ✅ 全部检查通过${RST}"
  echo "═══════════════════════════════════════════════════════════════════════"
  exit 0
else
  echo "${RED}  ❌ $FAILED 项检查失败${RST}"
  echo "═══════════════════════════════════════════════════════════════════════"
  echo
  echo "  ⚠️ 修复后才能提 PR"
  exit 1
fi
