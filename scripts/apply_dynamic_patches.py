#!/usr/bin/env python3
import os, sys, re, glob, difflib

def find_kernel_dir():
    kernel_dir = os.environ.get('KERNEL_DIR')
    if not kernel_dir:
        matches = glob.glob('build_dir/target-*/linux-*')
        if matches:
            kernel_dir = matches[0]
    if not kernel_dir or not os.path.isdir(kernel_dir):
        print(f"Error: Invalid or missing kernel directory: {kernel_dir}")
        sys.exit(1)
    return os.path.abspath(kernel_dir)

def find_file(kernel_dir, filename, path_must_contain=()):
    matches = []
    for root, dirs, files in os.walk(kernel_dir, followlinks=True):
        if filename in files:
            full_path = os.path.join(root, filename)
            if all(part in full_path for part in path_must_contain):
                matches.append(full_path)
    return matches

def make_unified_diff(kernel_dir, path, original, updated):
    relpath = os.path.relpath(path, kernel_dir)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f'a/{relpath}',
        tofile=f'b/{relpath}',
    )
    return ''.join(diff)

# ---- 以后加新补丁，只需要在这里追加条目 ----
PATCH_SPECS = [
    {
        'name': '0362-regulator-qcom_smd-fix-MP5496-supply-names',
        'filename': 'qcom_smd-regulator.c',
        'path_must_contain': ('regulator',),
        'kind': 'literal',
        'replacements': [
            ('{ "s1", QCOM_SMD_RPM_SMPA, 1, &mp5496_smps, "s1" },',
             '{ "s1", QCOM_SMD_RPM_SMPA, 1, &mp5496_smps, "vin1" },'),
            ('{ "s2", QCOM_SMD_RPM_SMPA, 2, &mp5496_smps, "s2" },',
             '{ "s2", QCOM_SMD_RPM_SMPA, 2, &mp5496_smps, "vin2" },'),
            ('{ "l2", QCOM_SMD_RPM_LDOA, 2, &mp5496_ldoa2, "l2" },',
             '{ "l2", QCOM_SMD_RPM_LDOA, 2, &mp5496_ldoa2, "vin2" },'),
            ('{ "l5", QCOM_SMD_RPM_LDOA, 5, &mp5496_ldoa2, "l5" },',
             '{ "l5", QCOM_SMD_RPM_LDOA, 5, &mp5496_ldoa2, "vin5" },'),
        ],
    },
    {
        'name': '0363-net-ethernet-qualcomm-honor-safe-NAPI-budgets',
        'filename': 'edma.c',
        'path_must_contain': ('ethernet', 'qualcomm', 'ppe'),
        'kind': 'regex',
        'replacements': [
            (r'MODULE_PARM_DESC\(\s*edma_rx_napi_budget\s*,\s*".*?"\s*\)',
             'MODULE_PARM_DESC(edma_rx_napi_budget, "Rx NAPI budget (default:64, min:16, max:64)")'),
            (r'MODULE_PARM_DESC\(\s*edma_tx_napi_budget\s*,\s*".*?"\s*\)',
             'MODULE_PARM_DESC(edma_tx_napi_budget, "Tx NAPI budget (default:64, min:16, max:64)")'),
            (r'\.napi_budget_tx\s*=\s*\d+\s*,', '.napi_budget_tx = 64,'),
        ],
    },
    {
        'name': '0363-net-ethernet-qualcomm-honor-safe-NAPI-budgets',
        'filename': 'edma_cfg_rx.c',
        'path_must_contain': ('ethernet', 'qualcomm', 'ppe'),
        'kind': 'regex',
        'replacements': [(r'(edma_rx_napi_poll,\s*)hw_info->napi_budget_rx', r'\1edma_rx_napi_budget')],
    },
    {
        'name': '0363-net-ethernet-qualcomm-honor-safe-NAPI-budgets',
        'filename': 'edma_cfg_rx.h',
        'path_must_contain': ('ethernet', 'qualcomm', 'ppe'),
        'kind': 'regex',
        'replacements': [
            (r'#define\s+EDMA_RX_NAPI_WORK_DEF\s+\d+', '#define EDMA_RX_NAPI_WORK_DEF\t\t64'),
            (r'#define\s+EDMA_RX_NAPI_WORK_MAX\s+\d+', '#define EDMA_RX_NAPI_WORK_MAX\t\t64'),
        ],
    },
    {
        'name': '0363-net-ethernet-qualcomm-honor-safe-NAPI-budgets',
        'filename': 'edma_cfg_tx.c',
        'path_must_contain': ('ethernet', 'qualcomm', 'ppe'),
        'kind': 'regex',
        'replacements': [(r'(edma_tx_napi_poll,\s*)hw_info->napi_budget_tx', r'\1edma_tx_napi_budget')],
    },
    {
        'name': '0363-net-ethernet-qualcomm-honor-safe-NAPI-budgets',
        'filename': 'edma_cfg_tx.h',
        'path_must_contain': ('ethernet', 'qualcomm', 'ppe'),
        'kind': 'regex',
        'replacements': [
            (r'#define\s+EDMA_TX_NAPI_WORK_DEF\s+\d+', '#define EDMA_TX_NAPI_WORK_DEF\t64'),
            (r'#define\s+EDMA_TX_NAPI_WORK_MAX\s+\d+', '#define EDMA_TX_NAPI_WORK_MAX\t64'),
        ],
    },
]

def apply_spec(content, spec, label):
    if spec['kind'] == 'regex':
        for pat, repl in spec['replacements']:
            content = re.sub(pat, repl, content)
        return content
    for old, new in spec['replacements']:
        n = content.count(old)
        if n == 0:
            print(f"  !! [{label}] 警告：未找到预期字符串，上游代码可能已变化: {old!r}")
            continue
        if n > 1:
            print(f"  !! [{label}] 警告：字符串出现 {n} 次(预期1次)，已全部替换，请人工核对: {old!r}")
        content = content.replace(old, new)
    return content

def main():
    kernel_dir = find_kernel_dir()
    print(f"Targeting kernel directory: {kernel_dir}")
    patch_dir = os.path.join(os.environ['ROOT_DIR'], 'target/linux/qualcommbe/patches-6.18')
    os.makedirs(patch_dir, exist_ok=True)

    grouped = {}
    for spec in PATCH_SPECS:
        grouped.setdefault(spec['name'], []).append(spec)

    total_patched = 0
    for name, specs in grouped.items():
        combined_diff = ''
        for spec in specs:
            for p in find_file(kernel_dir, spec['filename'], spec['path_must_contain']):
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    original = f.read()
                content = apply_spec(original, spec, name)
                if content != original:
                    with open(p, 'w', encoding='utf-8') as f:
                        f.write(content)
                    combined_diff += make_unified_diff(kernel_dir, p, original, content)
                    total_patched += 1
                    print(f"  [{name}] 已修改: {os.path.relpath(p, kernel_dir)}")
                else:
                    print(f"  !! [{name}] 未找到目标文件或内容未变化: {spec['filename']}")

        if combined_diff:
            out_path = os.path.join(patch_dir, f'{name}.patch')
            with open(out_path, 'w') as f:
                f.write(combined_diff)
            print(f"✅ 已生成 {out_path}")

    if total_patched == 0:
        print("❌ 错误：没有任何文件被修改")
        sys.exit(1)

if __name__ == '__main__':
    main()
