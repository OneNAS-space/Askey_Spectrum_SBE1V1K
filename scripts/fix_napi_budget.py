#!/usr/bin/env python3
import os
import sys
import re

def main():
    kernel_dir = os.environ.get('KERNEL_DIR')
    if not kernel_dir:
        import glob
        matches = glob.glob('build_dir/target-*/linux-*')
        if matches:
            kernel_dir = matches[0]
            
    if not kernel_dir or not os.path.isdir(kernel_dir):
        print(f"Error: Invalid or missing kernel directory: {kernel_dir}")
        sys.exit(1)

    print(f"Targeting kernel directory: {kernel_dir}")
    patched_files_count = 0

    def find_file(filename):
        matches = []
        for root, dirs, files in os.walk(kernel_dir, followlinks=True):
            if filename in files:
                full_path = os.path.join(root, filename)
                # 只要路径里包含 ethernet 和 qualcomm，百分之百就是我们要找的高通网卡 edma.c
                if 'ethernet' in full_path and 'qualcomm' in full_path and 'ppe' in full_path:
                    matches.append(full_path)
        return matches

    # 1. 修复 edma.c
    for p in find_file('edma.c'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original = content
        
        content = re.sub(r'MODULE_PARM_DESC\(\s*edma_rx_napi_budget\s*,\s*".*?"\s*\)', 
                         'MODULE_PARM_DESC(edma_rx_napi_budget, "Rx NAPI budget (default:64, min:16, max:64)")', content)
        content = re.sub(r'MODULE_PARM_DESC\(\s*edma_tx_napi_budget\s*,\s*".*?"\s*\)', 
                         'MODULE_PARM_DESC(edma_tx_napi_budget, "Tx NAPI budget (default:64, min:16, max:64)")', content)
        content = re.sub(r'\.napi_budget_tx\s*=\s*\d+\s*,', '.napi_budget_tx = 64,', content)
        
        if content != original:
            with open(p, 'w', encoding='utf-8') as f: f.write(content)
            patched_files_count += 1

    # 2. 修复 edma_cfg_rx.c
    for p in find_file('edma_cfg_rx.c'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original = content
        content = content.replace('hw_info->napi_budget_rx', 'edma_rx_napi_budget')
        if content != original:
            with open(p, 'w', encoding='utf-8') as f: f.write(content)
            patched_files_count += 1

    # 3. 修复 edma_cfg_rx.h
    for p in find_file('edma_cfg_rx.h'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original = content
        content = re.sub(r'#define\s+EDMA_RX_NAPI_WORK_DEF\s+\d+', '#define EDMA_RX_NAPI_WORK_DEF\t\t64', content)
        content = re.sub(r'#define\s+EDMA_RX_NAPI_WORK_MAX\s+\d+', '#define EDMA_RX_NAPI_WORK_MAX\t\t64', content)
        if content != original:
            with open(p, 'w', encoding='utf-8') as f: f.write(content)
            patched_files_count += 1

    # 4. 修复 edma_cfg_tx.c
    for p in find_file('edma_cfg_tx.c'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original = content
        content = content.replace('hw_info->napi_budget_tx', 'edma_tx_napi_budget')
        if content != original:
            with open(p, 'w', encoding='utf-8') as f: f.write(content)
            patched_files_count += 1

    # 5. 修复 edma_cfg_tx.h
    for p in find_file('edma_cfg_tx.h'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original = content
        content = re.sub(r'#define\s+EDMA_TX_NAPI_WORK_DEF\s+\d+', '#define EDMA_TX_NAPI_WORK_DEF\t64', content)
        content = re.sub(r'#define\s+EDMA_TX_NAPI_WORK_MAX\s+\d+', '#define EDMA_TX_NAPI_WORK_MAX\t64', content)
        if content != original:
            with open(p, 'w', encoding='utf-8') as f: f.write(content)
            patched_files_count += 1

    print('Successfully applied recursive dynamic kernel patches via external script.')

if __name__ == '__main__':
    main()
