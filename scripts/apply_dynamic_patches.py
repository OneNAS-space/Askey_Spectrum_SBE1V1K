#!/usr/bin/env python3
import os, sys, re, glob, difflib, tempfile, subprocess

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

def find_file(base_dir, filename, path_must_contain=(), parent_dir_exact=None):
    matches = []
    seen_real = set()
    for root, dirs, files in os.walk(base_dir):
        if filename in files:
            full_path = os.path.join(root, filename)
            if not all(part in full_path for part in path_must_contain):
                continue
            if parent_dir_exact is not None and os.path.basename(root) != parent_dir_exact:
                continue
            real = os.path.realpath(full_path)
            if real in seen_real:
                continue
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
    
    # ---- 优先使用系统的 git diff --no-index 或 diff -u 生成 Linux 内核级别的规范补丁 ----
    f1_path, f2_path = None, None
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f1, \
             tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f2:
            f1.write(original)
            f2.write(updated)
            f1_path, f2_path = f1.name, f2.name

        # 1. 尝试 git diff --no-index (带缩进启发算法，不会错位大括号)
        cmd = ['git', 'diff', '--no-index', '-u', f1_path, f2_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stdout:
            lines = res.stdout.splitlines(keepends=True)
            out = [f'--- a/{relpath}\n', f'+++ b/{relpath}\n']
            for line in lines:
                if line.startswith('--- ') or line.startswith('+++ ') or line.startswith('diff --git') or line.startswith('index '):
                    continue
                out.append(line)
            return ''.join(out)

        # 2. 尝试系统 diff -u
        cmd = ['diff', '-u', f1_path, f2_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stdout:
            lines = res.stdout.splitlines(keepends=True)
            out = [f'--- a/{relpath}\n', f'+++ b/{relpath}\n']
            for line in lines[2:]:
                out.append(line)
            return ''.join(out)
    except Exception:
        pass
    finally:
        if f1_path and os.path.exists(f1_path):
            os.remove(f1_path)
        if f2_path and os.path.exists(f2_path):
            os.remove(f2_path)

    # ---- 3. Python pure difflib 兜底 ----
    a = original.splitlines(keepends=True)
    b = updated.splitlines(keepends=True)
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
        'parent_dir_exact': 'ath12k',
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
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',  # 改用正则，对 backports-7.2 代码差异免疫
        'replacements': [
            # 1. 增加 status_code 局部变量（精准捕捉 total_reg_rules 声明行）
            (
                r'u32(\s+total_reg_rules\s*=\s*0\s*;)',
                r'u32 status_code __maybe_unused,\1'
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
                r'(\t)(ret\s*=\s*ath12k_pull_reg_chan_list_ext_update_ev\(ab,\s*skb,\s*reg_info\);\n)'
                r'(?:\s*if\s*\(ret\)\s*\{\n)'
                r'\s*(ath12k_warn\(ab,\s*"failed to extract regulatory info from received event\\n"\);\n)',

                r'\1\2'
                r'\1if ((!ret || ret == -ENODATA) && reg_info->phy_id < ab->num_radios)\n'
                r'\1\tpdev_idx = reg_info->phy_id;\n'
                r'\n'
                r'\1if (ret) {\n'
                r'\1\tif (ret == -ENODATA && pdev_idx != 255) {\n'
                r'\1\t\t/* Keep the last valid regdomain, but finish this update. */\n'
                r'\1\t\tret = ATH12K_REG_STATUS_VALID;\n'
                r'\1\t} else {\n'
                r'\1\t\t\3'
                r'\1\t}\n'
            ),
            # 5. 删除后面重复的 pdev_idx 赋值
            (
                r'(\t/\*\s*free old reg_info if it exist\s*\*/\n)\s*pdev_idx\s*=\s*reg_info->phy_id;\n',
                r'\1'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '108-wifi-ath12k-use-WSI-index-for-hardware-group-order',
        'filename': 'core.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 1. 替换 ab->device_id 的赋值逻辑，增加安全校验和排壳逻辑
            (
                r'(\t)ab->device_id\s*=\s*ag->num_probed\+\+;\n'
                r'(\t)ag->ab\[ab->device_id\]\s*=\s*ab;\n'
                r'(\t)ab->ag\s*=\s*ag;',

                r'\1if (wsi->index >= ag->num_devices) {\n'
                r'\1\tath12k_warn(ab, "invalid WSI index %u for group with %d devices\\n",\n'
                r'\1\t\t    wsi->index, ag->num_devices);\n'
                r'\1\tgoto invalid_group;\n'
                r'\1}\n\n'
                r'\1if (ag->ab[wsi->index]) {\n'
                r'\1\tath12k_warn(ab, "duplicate WSI index %u in group %d\\n",\n'
                r'\1\t\t    wsi->index, ag->id);\n'
                r'\1\tgoto invalid_group;\n'
                r'\1}\n\n'
                r'\1ab->device_id = wsi->index;\n'
                r'\2ag->ab[ab->device_id] = ab;\n'
                r'\3ag->num_probed++;\n'
                r'\3ab->ag = ag;'
            ),
            # 2. 替换底部的 ath12k_dbg 打印信息 (增加了 device_id 打印，并在末尾加上 \n)
            (
                r'(\t)ath12k_dbg\(ab,\s*ATH12K_DBG_BOOT,\s*"wsi group-id %d num-devices %d index %d",\n'
                r'\t\t\s*ag->id,\s*ag->num_devices,\s*wsi->index\);',

                r'\1ath12k_dbg(ab, ATH12K_DBG_BOOT,\n'
                r'\1\t   "wsi group-id %d num-devices %d index %d device-id %d\\n",\n'
                r'\1\t   ag->id, ag->num_devices, wsi->index, ab->device_id);'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '109-wifi-ath12k-log-WMI-control-service-topology',
        'filename': 'wmi.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 1. 局部变量声明处追加 ag 与 wsi_controller 定义
            (
                r'(ath12k_connect_pdev_htc_service[^{]*?\{\n[ \t]*int status;)',
                r'\1\n\tstruct ath12k_hw_group *ag = ath12k_ab_to_ag(ab);\n\tbool wsi_controller;'
            ),
            # 2. 连接前解析 wsi-controller 节点并输出拓扑 Debug 日志
            (
                r'(\tconn_req\.service_id\s*=\s*svc_id\[pdev_idx\];\n)',
                r'\1\n'
                r'\twsi_controller = ab->dev->of_node &&\n'
                r'\t\tof_property_read_bool(ab->dev->of_node, "qcom,wsi-controller");\n\n'
                r'\tath12k_dbg(ab, ATH12K_DBG_WMI,\n'
                r'\t\t   "WMI control connect pdev %u service 0x%x endpoints %d max-radios %d qmi-radios %d group-id %d wsi-index %u device-id %d wsi-controller %d\\n",\n'
                r'\t\t   pdev_idx, conn_req.service_id, ab->htc.wmi_ep_count,\n'
                r'\t\t   ab->hw_params->max_radios, ab->qmi.num_radios,\n'
                r'\t\t   ag ? ag->id : ATH12K_INVALID_GROUP_ID, ab->wsi_info.index,\n'
                r'\t\t   ab->device_id, wsi_controller);\n'
            ),
            # 3. 替换失败时的警告日志，携带完整的 WMI/WSI 拓扑参数
            (
                r'[ \t]*ath12k_warn\(ab,\s*"failed to connect to WMI CONTROL service status:\s*%d\\n",\s*status\);',
                r'\t\tath12k_warn(ab,\n'
                r'\t\t\t   "failed to connect WMI control pdev %u service 0x%x: %d (endpoints %d max-radios %d qmi-radios %d group-id %d wsi-index %u device-id %d wsi-controller %d)\\n",\n'
                r'\t\t\t   pdev_idx, conn_req.service_id, status,\n'
                r'\t\t\t   ab->htc.wmi_ep_count, ab->hw_params->max_radios,\n'
                r'\t\t\t   ab->qmi.num_radios,\n'
                r'\t\t\t   ag ? ag->id : ATH12K_INVALID_GROUP_ID,\n'
                r'\t\t\t   ab->wsi_info.index, ab->device_id, wsi_controller);'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '110-wifi-ath12k-limit-WMI-endpoints-to-QMI-PHY-count',
        'filename': 'htc.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 限制 WMI endpoint 数量不超过 QMI 广播的 PHY 数量
            (
                r'([ \t]*htc->wmi_ep_count\s*=\s*ab->hw_params->max_radios;\s*\n'
                r'[ \t]*break;\s*\n'
                r'[ \t]*\}\n)'
                r'(\n[ \t]*/\* setup our pseudo HTC control endpoint connection \*/)',

                r'\1'
                r'\tif (ab->qmi.num_radios > 0 && ab->qmi.num_radios != U8_MAX)\n'
                r'\t\thtc->wmi_ep_count = min_t(u8, htc->wmi_ep_count,\n'
                r'\t\t\t\t\t  ab->qmi.num_radios);\n'
                r'\2'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '111-wifi-ath12k-support-Wi-Fi-radar-direct-buffer-module',
        'filename': 'wmi.h',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 在 enum wmi_direct_buffer_module 中添加 WMI_CONFIG_MODULE_WIFI_RADAR 枚举值
            (
                r'([ \t]*WMI_DIRECT_BUF_CV_UPLOAD\s*=\s*2,?\n)',
                r'\1\tWMI_CONFIG_MODULE_WIFI_RADAR = 3,\n'
            ),
        ],
    },
    # 200 - 修改 ce.h 部分
    {
        'tree': 'mac80211',
        'name': '200-Revert-wifi-ath12k-convert-tasklet-to-BH-workqueue-f',
        'filename': 'ce.h',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 还原结构体 ath12k_ce_pipe 中的 intr_tq 字段
            (
                r'([ \t]*)struct work_struct intr_wq;',
                r'\1struct tasklet_struct intr_tq;'
            ),
        ],
    },
    # 200 - 修改 pci.c 部分
    {
        'tree': 'mac80211',
        'name': '200-Revert-wifi-ath12k-convert-tasklet-to-BH-workqueue-f',
        'filename': 'pci.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 1. 还原 tasklet 处理函数声明及 from_tasklet 转换
            (
                r'static void ath12k_pci_ce_workqueue\(struct work_struct \*work\)\n'
                r'\{\n'
                r'[ \t]*struct ath12k_ce_pipe \*ce_pipe = from_work\(ce_pipe, work, intr_wq\);',

                r'static void ath12k_pci_ce_tasklet(struct tasklet_struct *t)\n'
                r'{\n'
                r'\tstruct ath12k_ce_pipe *ce_pipe = from_tasklet(ce_pipe, t, intr_tq);'
            ),
            # 2. 中断处理函数中调度 tasklet 替换队列进队
            (
                r'[ \t]*queue_work\(system_bh_wq,\s*&ce_pipe->intr_wq\);',
                r'\ttasklet_schedule(&ce_pipe->intr_tq);'
            ),
            # 3. 中断初始化处使用 tasklet_setup 替换 INIT_WORK
            (
                r'[ \t]*INIT_WORK\(&ce_pipe->intr_wq,\s*ath12k_pci_ce_workqueue\);',
                r'\ttasklet_setup(&ce_pipe->intr_tq, ath12k_pci_ce_tasklet);'
            ),
            # 4. 函数名还原：ath12k_pci_cancel_workqueue -> ath12k_pci_kill_tasklets
            (
                r'static void ath12k_pci_cancel_workqueue\(struct ath12k_base \*ab\)',
                r'static void ath12k_pci_kill_tasklets(struct ath12k_base *ab)'
            ),
            # 5. 清理函数中使用 tasklet_kill 替换 cancel_work_sync
            (
                r'[ \t]*cancel_work_sync\(&ce_pipe->intr_wq\);',
                r'\ttasklet_kill(&ce_pipe->intr_tq);'
            ),
            # 6. 还原同步禁用中断函数中的调用点
            (
                r'([ \t]*)ath12k_pci_cancel_workqueue\(ab\);',
                r'\1ath12k_pci_kill_tasklets(ab);'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '400-wifi-ath12k-set-per-radio-MAC-address-from-DT',
        'filename': 'mac.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 1. 头文件引用区引入 <linux/of_net.h>
            (
                r'(#include <linux/etherdevice\.h>\n)',
                r'\1#include <linux/of_net.h>\n'
            ),
            # 2. 在 ath12k_mac_setup_iface_combinations 中添加 struct mac_address *addresses;
            (
                r'([ \t]*struct wiphy_radio \*radio;\n)',
                r'\1\tstruct mac_address *addresses;\n'
            ),
            # 3. 增加 addresses 内存分配，并更新 radio 分配失败后的 goto 异常跳转标签
            (
                r'([ \t]*/\* there are multiple radios \*/\n\n)'
                r'([ \t]*radio = [^;\n]+;\n'
                r'[ \t]*if \(!radio\) \{\n'
                r'[ \t]*ret = -ENOMEM;\n)'
                r'[ \t]*goto err_free_combinations;',

                r'\1\taddresses = kcalloc(ah->num_radio, sizeof(*addresses), GFP_KERNEL);\n'
                r'\tif (!addresses) {\n'
                r'\t\tret = -ENOMEM;\n'
                r'\t\tgoto err_free_combinations;\n'
                r'\t}\n\n'
                r'\2\n\t\tgoto err_free_addresses;'
            ),
            # 4. 在 for_each_ar 循环末尾复制 MAC 地址到 addresses 数组
            (
                r'([ \t]*radio\[i\]\.n_iface_combinations = 1;\n)',
                r'\1\n\t\tether_addr_copy(addresses[i].addr, ar->mac_addr);\n'
            ),
            # 5. 设置 wiphy 结构体的 addresses 和 n_addresses 成员
            (
                r'([ \t]*wiphy->n_radio = ah->num_radio;\n)',
                r'\1\n\twiphy->addresses = addresses;\n\twiphy->n_addresses = ah->num_radio;\n'
            ),
            # 6. 在错误清理节点中追加 kfree(addresses)
            (
                r'(err_free_radios:\s*\n[ \t]*kfree\(radio\);\n)',
                r'\1\nerr_free_addresses:\n\tkfree(addresses);\n'
            ),
            # 7. 在 ath12k_mac_hw_register 中为单 Radio 设备从 DT 读取 MAC 地址
            (
                r'([ \t]*ar->mac_addr\[4\] \+= ar->pdev_idx;\n'
                r'[ \t]*\}\n)',

                r'\1\n'
                r'\t\t/*\n'
                r'\t\t * In the ath12k-wsi binding each radio is its own device\n'
                r'\t\t * node, so a DT "mac-address" (e.g. an nvmem cell) on the\n'
                r'\t\t * node is this radio\'s. A chip backing several radios shares\n'
                r'\t\t * one node and can\'t express a per-radio address, so read DT\n'
                r'\t\t * only for single-radio chips; the rest keep the address\n'
                r'\t\t * derived above.\n'
                r'\t\t */\n'
                r'\t\tif (ar->ab->num_radios == 1)\n'
                r'\t\t\tof_get_mac_address(dev_of_node(ar->ab->dev), ar->mac_addr);\n'
            ),
            # 8. 移除多 Radio 场景下对全局 ab->mac_addr 的覆盖设置
            (
                r'([ \t]*if \(i == 0\)\n[ \t]*mac_addr = ar->mac_addr;\n)'
                r'[ \t]*else\n[ \t]*mac_addr = ab->mac_addr;\n',

                r'\1'
            ),
        ],
    },
    {
        'tree': 'mac80211',
        'name': '701-ath12k-support-memory-type-10',
        'filename': 'qmi.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 在 QMI 内存分配 switch-case 中追加对 10 号内存区域类型的支持
            (
                r'([ \t]*)case LPASS_SHARED_V01_REGION_TYPE:\n',
                r'\1case LPASS_SHARED_V01_REGION_TYPE:\n\1case 10:\n'
            ),
        ],
    },
]

def apply_spec(content, spec, label):
    applied_count = 0
    for idx, (pat, repl) in enumerate(spec['replacements'], 1):
        if spec['kind'] == 'regex':
            new_content, n = re.subn(pat, repl, content)
        else:
            n = content.count(pat)
            new_content = content.replace(pat, repl) if n else content
        if n == 0:
            print(f"  !! [{label}] 第 {idx}/{len(spec['replacements'])} 条替换未命中，请检查该处上下文")
        else:
            if n > 1:
                print(f"  !! [{label}] 第 {idx}/{len(spec['replacements'])} 条替换命中 {n} 次(预期 1 次)，请人工核对")
            content = new_content
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
            candidates = find_file(
                base_dir,
                spec['filename'],
                spec['path_must_contain'],
                parent_dir_exact=spec.get('parent_dir_exact'),
            )
            if len(candidates) > 1:
                print(f"  !! [{name}] 警告：{spec['filename']} 找到 {len(candidates)} 个候选，可能存在残留副本：")
                for c in candidates:
                    print(f"       - {c}")
            
            if not candidates:
                print(f"  !! [{name}] 错误：未找到目标文件 {spec['filename']} (限定条件: {spec['path_must_contain']})")
                continue

            spec_matched = False
            for p in candidates:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    original = f.read()
                
                content, applied_count = apply_spec(original, spec, name)
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
