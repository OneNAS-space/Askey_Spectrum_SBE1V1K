#!/usr/bin/env bash
set -uo pipefail   # 注意：这里不用 set -e，单个补丁失败不该让整个 job 崩溃

CUSTOM_PATCH_DIR="./patches"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/stdout}"

declare -a APPLIED SKIPPED_MERGED CONFLICTS

process_group () {
  local build_target="$1"      # 例如 target/linux 或 package/kernel/mac80211
  local baseline_dir="$2"      # make prepare 后的真实源码目录
  local overlay_dir="$3"       # patches/target/linux/qualcommbe/patches-6.18 等
  local dest_dir="$4"          # openwrt-src 里真正的落地目录

  find "$overlay_dir" -type f -name "*.patch" | sort | while read -r p; do
    name="$(basename "$p")"

    # 1) 已合并检测：反向打补丁
    if (cd "$baseline_dir" && patch -R -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      echo "⏭️  跳过（上游已合并）：$name" | tee -a "$SUMMARY"
      SKIPPED_MERGED+=("$name")
      continue
    fi

    # 2) 正向测试，先精确后模糊
    if (cd "$baseline_dir" && patch -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="精确"
    elif (cd "$baseline_dir" && patch -p1 --fuzz=3 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="模糊(fuzz=3，建议人工复核)"
    else
      echo "❌ 冲突，需要人工处理：$name" | tee -a "$SUMMARY"
      CONFLICTS+=("$name")
      continue
    fi

    # 3) 编号映射（写死你自己的重编号规则，或维护一张映射表）
    final_name="$(remap_number "$name")"
    dest="$dest_dir/$final_name"
    mkdir -p "$dest_dir"
    cp "$p" "$dest"
    echo "✅ 应用（$mode）：$name → $final_name" | tee -a "$SUMMARY"
    APPLIED+=("$final_name")
  done
}
