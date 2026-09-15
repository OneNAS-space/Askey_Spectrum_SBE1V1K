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
    if not d:
        if tree_key == 'kernel':
            matches = glob.glob('build_dir/target-*/linux-*')
            if matches:
                d = matches[0]
        elif tree_key == 'mac80211':
            matches = glob.glob('build_dir/target-*/mac80211-*') or glob.glob('build_dir/target-*/backports-*')
            if matches:
                d = matches[0]

    if not d or not os.path.isdir(d):
        print(f"Error: {env_name} 未设置或目录不存在: {d}")
        sys.exit(1)
    return os.path.abspath(d)

def find_file(base_dir, filename, path_must_contain=()):
    matches = []
    seen_real = set()

    # 恢复安全的 os.walk，不跟随目录软链接，防止遍历时把真实目录提前剪枝
    for root, dirs, files in os.walk(base_dir):
        if filename in files:
            full_path = os.path.join(root, filename)
            if not all(part in full_path for part in path_must_contain):
                continue
            real = os.path.realpath(full_path)
            if real in seen_real:
                continue  # 仅做文件级别的真实路径去重
            seen_real.add(real)
            matches.append(full_path)
    return matches

def format_diff_range(start, stop):
    length = stop - start
    if length == 1:
        return f"{start + 1}"
    if length == 0:
        return f"{start},0"  # 纯插入时取插入位置前一行的行号
    return f"{start + 1},{length}"

def make_unified_diff(base_dir, path, original, updated):
    relpath = os.path.relpath(path, base_dir)
    a = original.splitlines(keepends=True)
    b = updated.splitlines(keepends=True)

    # 禁用 autojunk=False，防止高频出现的 \t} 和空行被忽略导致 diff 上下文错位
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)

    lines = [
        f'--- a/{relpath}\n',
        f'+++ b/{relpath}\n'
    ]

    for group in matcher.get_grouped_opcodes(n=3):
        first, last = group[0], group[-1]
        file1_range = format_diff_range(first[1], last[2])
        file2_range = format_diff_range(first[3], last[4])
        lines.append(f'@@ -{file1_range} +{file2_range} @@\n')

        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in a[i1:i2]:
                    lines.append(' ' + line)
            elif tag in ('replace', 'delete'):
                for line in a[i1:i2]:
                    lines.append('-' + line)
            if tag in ('replace', 'insert'):
                for line in b[j1:j2]:
                    lines.append('+' + line)

    return ''.join(lines)

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
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'kind': 'literal',
        'replacements': [
            # 仅匹配唯一标识行，不依赖后续的换行和注释
            (
                '\tWMI_DIRECT_BUF_CFR = 1,',
                '\tWMI_DIRECT_BUF_CFR = 1,\n\tWMI_DIRECT_BUF_CV_UPLOAD = 2,'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '106-wifi-ath12k-handle-empty-regulatory-events',
        'filename': 'wmi.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'kind': 'regex',  # 改用正则，对 backports-7.2 代码差异免疫
        'replacements': [
            # 1. 增加 status_code 局部变量（精准捕捉 total_reg_rules 声明行）
            (
                r'(u32\s+total_reg_rules\s*=\s*0\s*;)',
                r'u32 status_code __maybe_unused, \1'
            ),
            # 2. 插入 status_code 解析 switch 块（锚定在 reg_info 给 2G 规则赋值的开端）
            (
                r'(\t)(reg_info->num_2g_reg_rules\s*=\s*le32_to_cpu\(ev->num_2g_reg_rules\);)',
                r'\1memcpy(reg_info->alpha2, &ev->alpha2, REG_ALPHA2_LEN);\n'
                r'\1reg_info->dfs_region = le32_to_cpu(ev->dfs_region);\n'
                r'\1reg_info->phybitmap = le32_to_cpu(ev->phybitmap);\n'
                r'\1reg_info->num_phy = le32_to_cpu(ev->num_phy);\n'
                r'\1reg_info->phy_id = le32_to_cpu(ev->phy_id);\n'
                r'\1reg_info->ctry_code = le32_to_cpu(ev->country_id);\n'
                r'\1reg_info->reg_dmn_pair = le32_to_cpu(ev->domain_code);\n\n'
                r'\1status_code = le32_to_cpu(ev->status_code);\n'
                r'\1switch (status_code) {\n'
                r'\1case WMI_REG_SET_CC_STATUS_PASS:\n'
                r'\1\treg_info->status_code = REG_SET_CC_STATUS_PASS;\n'
                r'\1\tbreak;\n'
                r'\1case WMI_REG_CURRENT_ALPHA2_NOT_FOUND:\n'
                r'\1\treg_info->status_code = REG_CURRENT_ALPHA2_NOT_FOUND;\n'
                r'\1\tbreak;\n'
                r'\1case WMI_REG_INIT_ALPHA2_NOT_FOUND:\n'
                r'\1\treg_info->status_code = REG_INIT_ALPHA2_NOT_FOUND;\n'
                r'\1\tbreak;\n'
                r'\1case WMI_REG_SET_CC_CHANGE_NOT_ALLOWED:\n'
                r'\1\treg_info->status_code = REG_SET_CC_CHANGE_NOT_ALLOWED;\n'
                r'\1\tbreak;\n'
                r'\1case WMI_REG_SET_CC_STATUS_NO_MEMORY:\n'
                r'\1\treg_info->status_code = REG_SET_CC_STATUS_NO_MEMORY;\n'
                r'\1\tbreak;\n'
                r'\1case WMI_REG_SET_CC_STATUS_FAIL:\n'
                r'\1\treg_info->status_code = REG_SET_CC_STATUS_FAIL;\n'
                r'\1\tbreak;\n'
                r'\1default:\n'
                r'\1\tath12k_warn(ab, "unknown regulatory status %u\\n", status_code);\n'
                r'\1\treg_info->status_code = REG_SET_CC_STATUS_FAIL;\n'
                r'\1\tbreak;\n'
                r'\1}\n\n'
                r'\1\2'
            ),
            # 3. 空规则处理：将 -EINVAL 改为 -ENODATA 并移除警告
            (
                r'if\s*\(!total_reg_rules\)\s*\{\n[ \t]*ath12k_warn\([^)]+\);\n[ \t]*return\s+-EINVAL;',
                "if (!total_reg_rules) {\n\t\treturn -ENODATA;"
            ),
            # 4. 提前赋值 pdev_idx，并区分 -ENODATA 分支
            (
                r'(\t)(ret\s*=\s*ath12k_pull_reg_chan_list_ext_update_ev\(ab,\s*skb,\s*reg_info\);\n\s*if\s*\(ret\)\s*\{)',
                r'\1ret = ath12k_pull_reg_chan_list_ext_update_ev(ab, skb, reg_info);\n'
                r'\1if ((!ret || ret == -ENODATA) && reg_info->phy_id < ab->num_radios)\n'
                r'\1\tpdev_idx = reg_info->phy_id;\n\n'
                r'\1if (ret) {\n'
                r'\1\tif (ret == -ENODATA && pdev_idx != 255) {\n'
                r'\1\t\t/* Keep the last valid regdomain, but finish this update. */\n'
                r'\1\t\tret = ATH12K_REG_STATUS_VALID;\n'
                r'\1\t} else'
            ),
            # 5. 删除后面重复的 pdev_idx 赋值
            (
                r'(\t/\*\s*free old reg_info if it exist\s*\*/\n)\s*pdev_idx\s*=\s*reg_info->phy_id;\n',
                r'\1'
            ),
        ],
    }
]

def apply_spec(content, spec):
    applied_count = 0
    if spec['kind'] == 'regex':
        for pat, repl in spec['replacements']:
            new_content, n = re.subn(pat, repl, content)
            if n > 0:
                content = new_content
                applied_count += n
        return content, applied_count

    for old, new in spec['replacements']:
        n = content.count(old)
        if n > 0:
            content = content.replace(old, new)
            applied_count += n
    return content, applied_count

def main():
    grouped = {}
    for spec in PATCH_SPECS:
        tree_key = spec.get('tree', 'kernel')
        grouped.setdefault((tree_key, spec['name']), []).append(spec)

    tree_dirs = {}
    total_patched = 0
    root_dir = os.environ.get('ROOT_DIR', '.')

    for (tree_key, name), specs in grouped.items():
        if tree_key not in tree_dirs:
            tree_dirs[tree_key] = resolve_tree_dir(tree_key)
            print(f"Targeting {tree_key} directory: {tree_dirs[tree_key]}")
        base_dir = tree_dirs[tree_key]

        combined_diff = ''
        for spec in specs:
            candidates = find_file(base_dir, spec['filename'], spec['path_must_contain'])
            
            if not candidates:
                print(f"  !! [{name}] 错误：未找到目标文件 {spec['filename']} (限定条件: {spec['path_must_contain']})")
                continue

            spec_matched = False
            for p in candidates:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    original = f.read()
                
                content, applied_count = apply_spec(original, spec)
                if content != original:
                    spec_matched = True
                    with open(p, 'w', encoding='utf-8') as f:
                        f.write(content)
                    combined_diff += make_unified_diff(base_dir, p, original, content)
                    total_patched += 1
                    print(f"  [{name}] 已修改: {os.path.relpath(p, base_dir)}")

            if not spec_matched:
                print(f"  !! [{name}] 提示：找到了文件 {spec['filename']}，但未匹配到替换内容（代码已被修改过或上下文不一致）")

        if combined_diff:
            patch_dir = os.path.join(root_dir, TREES[tree_key]['patch_dir_rel'])
            os.makedirs(patch_dir, exist_ok=True)
            out_path = os.path.join(patch_dir, f'{name}.patch')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(combined_diff)
            print(f"✅ 已生成 {out_path}")

    if total_patched == 0:
        print("❌ 错误：没有任何文件被修改")
        sys.exit(1)

if __name__ == '__main__':
    main()
