#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  bump.sh —— 版本号自动递增
#
#  用法：
#    ./bump.sh patch     # 1.0.0 → 1.0.1（修 bug）
#    ./bump.sh minor     # 1.0.0 → 1.1.0（加功能）
#    ./bump.sh major     # 1.0.0 → 2.0.0（不兼容变更）
#    ./bump.sh 1.2.3     # 指定版本
#    ./bump.sh show      # 只看当前版本
#
#  做三件事：
#    ① 更新 manifest.json 的 version
#    ② 校验格式
#    ③ 提示后续操作（打 tag / 推送）
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

MANIFEST="custom_components/lixiang_auto/manifest.json"
GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; RST=$'\033[0m'

[[ -f "$MANIFEST" ]] || { echo "${RED}✗ 找不到 $MANIFEST（请在仓库根目录运行）${RST}"; exit 1; }

current=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['version'])")
IFS='.' read -r major minor patch <<< "$current"

case "${1:-show}" in
  show)
    echo "当前版本: ${GRN}$current${RST}"
    exit 0
    ;;
  patch) new="$major.$minor.$((patch + 1))" ;;
  minor) new="$major.$((minor + 1)).0" ;;
  major) new="$((major + 1)).0.0" ;;
  [0-9]*.[0-9]*.[0-9]*) new="$1" ;;
  *)
    echo "${RED}✗ 用法: $0 [show|patch|minor|major|X.Y.Z]${RST}"
    exit 1
    ;;
esac

# 格式校验
if ! [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "${RED}✗ 版本格式无效: $new${RST}"
  exit 1
fi

python3 - "$MANIFEST" "$new" <<'PY'
import json, sys
path, new = sys.argv[1], sys.argv[2]
m = json.load(open(path, encoding="utf-8"))
m["version"] = new
with open(path, "w", encoding="utf-8") as f:
    json.dump(m, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY

echo "${GRN}✓${RST} 版本: $current → ${GRN}$new${RST}"
echo
echo "  下一步："
echo "    git add $MANIFEST"
echo "    git commit -m \"chore(release): v$new\""
echo "    git tag v$new && git push --tags"
