#!/usr/bin/env bash
set -uo pipefail   # 注意不用 -e：单个 patch 测试失败要自己 if 判断捕获，不能让脚本半路死掉

SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
declare -a APPLIED SKIPPED_MERGED CONFLICTS

process_group () {
  local baseline_dir="$1" overlay_dir="$2" dest_dir="$3"

  mapfile -t patch_list < <(find "$overlay_dir" -type f -name "*.patch" | sort)
  for p in "${patch_list[@]}"; do
    name="$(basename "$p")"

    if (cd "$baseline_dir" && patch -R -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      echo "⏭️ 跳过（上游已合并）：$name" | tee -a "$SUMMARY"
      SKIPPED_MERGED+=("$name")
      continue
    fi

    if (cd "$baseline_dir" && patch -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="精确"
    elif (cd "$baseline_dir" && patch -p1 --fuzz=3 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="模糊(fuzz=3)"
    else
      echo "❌ 冲突，需人工处理：$name" | tee -a "$SUMMARY"
      CONFLICTS+=("$name")
      continue
    fi

    final_name="$(remap_if_needed "$dest_dir" "$name")"
    dest="$dest_dir/$final_name"
    mkdir -p "$dest_dir"
    cp "$p" "$dest"
    echo "✅ 应用（$mode）：$name → $final_name" | tee -a "$SUMMARY"
    APPLIED+=("$final_name")
  done
}

process_group "$KERNEL_BASELINE_DIR"  "$CUSTOM_PATCH_DIR/target/linux/qualcommbe/patches-6.18" \
              "target/linux/qualcommbe/patches-6.18"
process_group "$MAC80211_BASELINE_DIR" "$CUSTOM_PATCH_DIR/package/kernel/mac80211/patches" \
              "package/kernel/mac80211/patches"

{
  echo "### 补丁同步汇总"
  echo "- ✅ 已应用: ${#APPLIED[@]}"
  echo "- ⏭️ 跳过(已合并): ${#SKIPPED_MERGED[@]}"
  echo "- ❌ 冲突: ${#CONFLICTS[@]}"
} | tee -a "$SUMMARY"

if [ "${#CONFLICTS[@]}" -gt 0 ]; then
  echo "存在无法自动解决的冲突，终止本次同步，不进行提交/推送。" >&2
  exit 1
fi

git add .
git commit -m "Auto-sync at $(date -u +'%Y-%m-%dT%H:%M:%SZ')" || echo "无变动需要提交"
