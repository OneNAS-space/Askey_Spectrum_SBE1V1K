#!/usr/bin/env bash
set -e

PATCH_DIR="./patches"

if [ -d "$PATCH_DIR" ]; then
  echo "==> 开始检查并应用自定义补丁..."
  for patch_file in "$PATCH_DIR"/*.patch; do
    [ -f "$patch_file" ] || continue
    echo "正在应用: $patch_file"
    
    # 尝试无缝精确应用
    if git apply --check "$patch_file" 2>/dev/null; then
      git apply "$patch_file"
      echo "✓ 精确应用成功"
    else
      echo "! 检测到上游源码上下文变更，开启 3-Way 模糊纠错打补丁..."
      # 使用 patch 命令容许最多 3 行的行号偏移和模糊匹配
      patch -p1 --fuzz=3 --no-backup-if-mismatch < "$patch_file"
      echo "✓ 模糊对齐打补丁完成"
    fi
  done
  
  # 提交打完补丁的代码变动
  git add .
  git commit -m "Auto-applied custom patches at $(date -u +'%Y-%m-%dT%H:%M:%SZ')" || echo "无变动需要提交"
else
  echo "未找到补丁目录 $PATCH_DIR，跳过打补丁步骤。"
fi
