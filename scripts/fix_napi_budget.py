#!/usr/bin/env python3
import os
import sys

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

    def find_file(filename, subpath_hint=None):
        matches = []
        for root, dirs, files in os.walk(kernel_dir):
            if filename in files:
                full_path = os.path.join(root, filename)
                # 增加路径提示过滤，避免误伤其他驱动（如 ti/edma.c）
                if subpath_hint and subpath_hint not in full_path:
                    continue
                matches.append(full_path)
        return matches

    # 1. 修复 edma.c (严格限定在 qualcomm/ppe 路径下)
    for p in find_file('edma.c', subpath_hint='qualcomm/ppe'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        content = content.replace('MODULE_PARM_DESC(edma_rx_napi_budget, "Rx NAPI budget (default:128, min:16, max:512)")', 'MODULE_PARM_DESC(edma_rx_napi_budget, "Rx NAPI budget (default:64, min:16, max:64)")')
        content = content.replace('MODULE_PARM_DESC(edma_tx_napi_budget, "Tx NAPI budget (default:512 for ipq95xx, min:16, max:512)")', 'MODULE_PARM_DESC(edma_tx_napi_budget, "Tx NAPI budget (default:64, min:16, max:64)")')
        content = content.replace('.napi_budget_tx = 512,', '.napi_budget_tx = 64,')
        with open(p, 'w', encoding='utf-8') as f: f.write(content)

    # 2. 修复 edma_cfg_rx.c
    for p in find_file('edma_cfg_rx.c', subpath_hint='qualcomm/ppe'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        content = content.replace('hw_info->napi_budget_rx', 'edma_rx_napi_budget')
        with open(p, 'w', encoding='utf-8') as f: f.write(content)

    # 3. 修复 edma_cfg_rx.h
    for p in find_file('edma_cfg_rx.h', subpath_hint='qualcomm/ppe'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        content = content.replace('#define EDMA_RX_NAPI_WORK_DEF\t\t128', '#define EDMA_RX_NAPI_WORK_DEF\t\t64')
        content = content.replace('#define EDMA_RX_NAPI_WORK_MAX\t\t512', '#define EDMA_RX_NAPI_WORK_MAX\t\t64')
        with open(p, 'w', encoding='utf-8') as f: f.write(content)

    # 4. 修复 edma_cfg_tx.c
    for p in find_file('edma_cfg_tx.c', subpath_hint='qualcomm/ppe'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        content = content.replace('hw_info->napi_budget_tx', 'edma_tx_napi_budget')
        with open(p, 'w', encoding='utf-8') as f: f.write(content)

    # 5. 修复 edma_cfg_tx.h
    for p in find_file('edma_cfg_tx.h', subpath_hint='qualcomm/ppe'):
        print(f'Patching {p}...')
        with open(p, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        content = content.replace('#define EDMA_TX_NAPI_WORK_DEF\t512', '#define EDMA_TX_NAPI_WORK_DEF\t64')
        content = content.replace('#define EDMA_TX_NAPI_WORK_MAX\t512', '#define EDMA_TX_NAPI_WORK_MAX\t64')
        with open(p, 'w', encoding='utf-8') as f: f.write(content)

    print('Successfully applied recursive dynamic kernel patches via external script.')

if __name__ == '__main__':
    main()
