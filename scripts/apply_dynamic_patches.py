#!/usr/bin/env python3
import os, sys, re, glob, difflib

# ---- 多棵源码树的定义：env var 提供实际目录 + 补丁最终落地的相对路径 ----
TREES = {
    'kernel': {
        'dir_env': 'KERNEL_DIR',
        'patch_dir_rel': 'target/linux/qualcommbe/patches-6.18',
    },
    'mac80211': {
        'dir_env': 'MAC80211_DIR',
        'patch_dir_rel': 'package/kernel/mac80211/patches/ath12k',
    },
}

def resolve_tree_dir(tree_key):
    env_name = TREES[tree_key]['dir_env']
    d = os.environ.get(env_name)
    if not d and tree_key == 'kernel':
        matches = glob.glob('build_dir/target-*/linux-*')
        if matches:
            d = matches[0]
    if not d or not os.path.isdir(d):
        print(f"Error: {env_name} 未设置或目录不存在: {d}")
        sys.exit(1)
    return os.path.abspath(d)

def find_file(base_dir, filename, path_must_contain=()):
    matches = []
    for root, dirs, files in os.walk(base_dir, followlinks=True):
        if filename in files:
            full_path = os.path.join(root, filename)
            if all(part in full_path for part in path_must_contain):
                matches.append(full_path)
    return matches

def make_unified_diff(base_dir, path, original, updated):
    relpath = os.path.relpath(path, base_dir)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f'a/{relpath}',
        tofile=f'b/{relpath}',
    )
    return ''.join(diff)

# ---- 以后加新补丁，只需要在这里追加条目 ----
# 'tree' 不写默认是 'kernel'（原有条目全部保持不变，不用补这个字段）
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
    {
        'name': '0404-arm64-dts-qcom-ipq9574-add-sdhci-reset',
        'filename': 'ipq9574.dtsi',
        'path_must_contain': ('arch', 'arm64', 'boot', 'dts', 'qcom'),
        'kind': 'literal',
        'replacements': [
            (
                '\t\t\t <&gcc GCC_SDCC1_ICE_CORE_CLK>;\n'
                '\t\t\tclock-names = "iface", "core", "xo", "ice";\n'
                '\t\t\tnon-removable;',

                '\t\t\t <&gcc GCC_SDCC1_ICE_CORE_CLK>;\n'
                '\t\t\tclock-names = "iface", "core", "xo", "ice";\n'
                '\t\t\tresets = <&gcc GCC_SDCC_BCR>;\n'
                '\t\t\tnon-removable;'
            ),
        ],
    },
    # ---- 新增：ath12k, 位于 mac80211 backports 树 ----
    {
        'tree': 'mac80211',
        'name': '105-wifi-ath12k-support-CV-upload-direct-buffer-module',
        'filename': 'wmi.h',
        'path_must_contain': ('ath12k',),
        'kind': 'literal',
        'replacements': [
            (
                '\tWMI_DIRECT_BUF_CFR = 1,\n'
                '\n'
                '\t/* keep it last */',

                '\tWMI_DIRECT_BUF_CFR = 1,\n'
                '\tWMI_DIRECT_BUF_CV_UPLOAD = 2,\n'
                '\n'
                '\t/* keep it last */'
            ),
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
    grouped = {}
    for spec in PATCH_SPECS:
        tree_key = spec.get('tree', 'kernel')
        grouped.setdefault((tree_key, spec['name']), []).append(spec)

    tree_dirs = {}  # 每棵树只 resolve 一次
    total_patched = 0

    for (tree_key, name), specs in grouped.items():
        if tree_key not in tree_dirs:
            tree_dirs[tree_key] = resolve_tree_dir(tree_key)
            print(f"Targeting {tree_key} directory: {tree_dirs[tree_key]}")
        base_dir = tree_dirs[tree_key]

        combined_diff = ''
        for spec in specs:
            for p in find_file(base_dir, spec['filename'], spec['path_must_contain']):
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    original = f.read()
                content = apply_spec(original, spec, name)
                if content != original:
                    with open(p, 'w', encoding='utf-8') as f:
                        f.write(content)
                    combined_diff += make_unified_diff(base_dir, p, original, content)
                    total_patched += 1
                    print(f"  [{name}] 已修改: {os.path.relpath(p, base_dir)}")
                else:
                    print(f"  !! [{name}] 未找到目标文件或内容未变化: {spec['filename']}")

        if combined_diff:
            patch_dir = os.path.join(os.environ['ROOT_DIR'], TREES[tree_key]['patch_dir_rel'])
            os.makedirs(patch_dir, exist_ok=True)
            out_path = os.path.join(patch_dir, f'{name}.patch')
            with open(out_path, 'w') as f:
                f.write(combined_diff)
            print(f"✅ 已生成 {out_path}")

    if total_patched == 0:
        print("❌ 错误：没有任何文件被修改")
        sys.exit(1)

if __name__ == '__main__':
    main()
