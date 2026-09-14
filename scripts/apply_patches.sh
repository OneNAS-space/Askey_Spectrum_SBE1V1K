#!/usr/bin/env bash
set -uo pipefail   # 不用 -e：单个 patch 的测试失败要靠 if 自己捕获，不能让脚本半路退出

SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
declare -a APPLIED SKIPPED_MERGED CONFLICTS

# ---------- 定位真实基线源码目录（make prepare 之后才存在）----------
detect_kernel_baseline() {
  find build_dir -maxdepth 3 -type d -regextype posix-extended \
    -regex '.*/linux-[0-9]+\.[0-9.]+' 2>/dev/null | head -n1
}
detect_mac80211_baseline() {
  find build_dir -maxdepth 4 -type d \( -iname 'mac80211-*' -o -iname 'backports-*' \) \
    2>/dev/null | head -n1
}

# ---------- 冲突时的自动挪号：仅在目标文件名已被占用且内容不同才触发 ----------
remap_if_needed() {
  local dest_dir="$1" name="$2" src_file="$3"
  local dest="$dest_dir/$name"

  if [ ! -e "$dest" ]; then
    echo "$name"; return
  fi
  if diff -q "$src_file" "$dest" >/dev/null 2>&1; then
    echo "$name"; return   # 内容一样，视为已放置过
  fi

  local prefix="${name%%-*}"
  local rest="${name#*-}"
  local width=${#prefix}
  local pool_start
  [ "$width" -ge 4 ] && pool_start=9900 || pool_start=990

  local n="$pool_start"
  while [ -e "$dest_dir/$(printf "%0${width}d-%s" "$n" "$rest")" ]; do
    n=$((n + 1))
  done
  printf "%0${width}d-%s" "$n" "$rest"
}

process_group() {
  local baseline_dir="$1" overlay_dir="$2" dest_dir="$3"

  if [ -z "$baseline_dir" ] || [ ! -d "$baseline_dir" ]; then
    echo "❌ 找不到基线源码目录（$overlay_dir 对应组），make prepare 可能没有成功" | tee -a "$SUMMARY"
    CONFLICTS+=("$overlay_dir: 基线目录缺失")
    return
  fi

  mapfile -t patch_list < <(find "$overlay_dir" -type f -name "*.patch" | sort)
  for p in "${patch_list[@]}"; do
    local name; name="$(basename "$p")"

    # 1) 已合并检测：反向打补丁
    if (cd "$baseline_dir" && patch -R -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      echo "⏭️ 跳过（上游已合并）：$name" | tee -a "$SUMMARY"
      SKIPPED_MERGED+=("$name")
      continue
    fi

    # 2) 正向测试：先精确，后模糊
    local mode=""
    if (cd "$baseline_dir" && patch -p1 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="精确"
      # 【关键修复】：必须真实打入代码，为下一个互相依赖的补丁提供上下文
      (cd "$baseline_dir" && patch -p1 < "$OLDPWD/$p" >/dev/null 2>&1)
    elif (cd "$baseline_dir" && patch -p1 --fuzz=3 --dry-run < "$OLDPWD/$p" >/dev/null 2>&1); then
      mode="模糊(fuzz=3，建议复核)"
      # 【关键修复】：真实打入代码
      (cd "$baseline_dir" && patch -p1 --fuzz=3 < "$OLDPWD/$p" >/dev/null 2>&1)
    else
      echo "❌ 冲突，需人工处理：$name" | tee -a "$SUMMARY"
      CONFLICTS+=("$name")
      continue
    fi

    # 3) 落地（必要时自动挪号）
    local final_name; final_name="$(remap_if_needed "$dest_dir" "$name" "$p")"
    mkdir -p "$dest_dir"
    cp "$p" "$dest_dir/$final_name"
    echo "✅ 应用（$mode）：$name → $final_name" | tee -a "$SUMMARY"
    APPLIED+=("$final_name")
  done
}

KERNEL_BASELINE_DIR="$(detect_kernel_baseline)"
MAC80211_BASELINE_DIR="$(detect_mac80211_baseline)"

process_group "$KERNEL_BASELINE_DIR" \
  "./patches/target/linux/qualcommbe/patches-6.18" \
  "target/linux/qualcommbe/patches-6.18"

process_group "$MAC80211_BASELINE_DIR" \
  "./patches/package/kernel/mac80211/patches" \
  "package/kernel/mac80211/patches"

{
  echo "### 补丁同步汇总"
  echo "- ✅ 已应用: ${#APPLIED[@]}"
  echo "- ⏭️ 跳过(已合并): ${#SKIPPED_MERGED[@]}"
  echo "- ❌ 冲突: ${#CONFLICTS[@]}"
} | tee -a "$SUMMARY"

if [ "${#CONFLICTS[@]}" -gt 0 ]; then
  echo "存在无法自动解决的冲突，终止本次同步，不提交、不推送。" >&2
  exit 1
fi

git add .
git commit -m "Auto-sync at $(date -u +'%Y-%m-%dT%H:%M:%SZ')" || echo "无变动需要提交"
