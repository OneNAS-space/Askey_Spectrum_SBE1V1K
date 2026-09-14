#!/usr/bin/env python3
import os

def modify_file(filepath, replacements):
    if not os.path.exists(filepath):
        print(f"[-] File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            modified = True
        else:
            print(f"[!] Warning: Pattern not found in {filepath}: {old}")
            
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully updated: {filepath}")
    return True

# 定义你需要修改的目标和替换规则
edma_c = "openwrt-src/target/linux/qualcommbe/patches-6.18/../../../../../build_dir/target-aarch64_cortex-a53+neon-vfpv4_musl/linux-ipq95xx/linux-6.18/drivers/net/ethernet/qualcomm/ppe/edma.c"
# 注意：由于在 kernel 源码解压前或解压后路径可能不同，
# 最稳妥的做法是在 Makefile prepare 之后，直接去内核解压目录里改！
