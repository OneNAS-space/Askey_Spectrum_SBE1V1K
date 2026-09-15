# If you don't write 'tree', the default is 'kernel' (all the original entries remain unchanged, and there is no need to fill in this field)
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
    # ---- New: ath12k, located in mac80211 backports tree ----
    {
        'tree': 'mac80211',
        'name': '105-wifi-ath12k-support-CV-upload-direct-buffer-module',
        'filename': 'wmi.h',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'literal',
        'replacements': [
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
        'kind': 'regex',
        'replacements': [
            # 1. Add status_code local variables (accurately capture the total_reg_rules declaration line)
            (
                r'u32(\s+total_reg_rules\s*=\s*0\s*;)',
                r'u32 status_code __maybe_unused,\1'
            ),
            # 2. Insert status_code parsing switch block (anchored at the beginning of reg_info assigning values to 2G rules)
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
            # 3. Empty rule processing: change -EINVAL to -ENODATA and remove the warning
            (
                r'if\s*\(!total_reg_rules\)\s*\{\n[ \t]*ath12k_warn\([^)]+\);\n[ \t]*return\s+-EINVAL;',
                "if (!total_reg_rules) {\n\t\treturn -ENODATA;"
            ),
            # 4. Assign pdev_idx in advance and distinguish -ENODATA branches
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
            # 5. Delete the repeated pdev_idx assignment
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
            # 1. Replace the assignment logic of ab->device_id and add the security checksum shelling logic
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
            # 2. Replace the ath12k_dbg print information at the bottom (add device_id printing and add \n at the end)
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
            # 1. Add ag and wsi_controller definitions to the local variable declaration
            (
                r'(ath12k_connect_pdev_htc_service[^{]*?\{\n[ \t]*int status;)',
                r'\1\n\tstruct ath12k_hw_group *ag = ath12k_ab_to_ag(ab);\n\tbool wsi_controller;'
            ),
            # 2. Parse the wsi-controller node and output the topology Debug log before connecting
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
            # 3. Warning log in case of replacement failure, carrying complete WMI/WSI topology parameters
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
            # Limit the number of WMI endpoints to no more than the number of PHY broadcasts in QMI
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
            # Add WMI_CONFIG_MODULE_WIFI_RADAR enumeration value to enum wmi_direct_buffer_module
            (
                r'([ \t]*WMI_DIRECT_BUF_CV_UPLOAD\s*=\s*2,?\n)',
                r'\1\tWMI_CONFIG_MODULE_WIFI_RADAR = 3,\n'
            ),
        ],
    },
    # 200 - Modify the ce.h part
    {
        'tree': 'mac80211',
        'name': '200-Revert-wifi-ath12k-convert-tasklet-to-BH-workqueue-f',
        'filename': 'ce.h',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # Restore the intr_tq field in the structure ath12k_ce_pipe
            (
                r'([ \t]*)struct work_struct intr_wq;',
                r'\1struct tasklet_struct intr_tq;'
            ),
        ],
    },
    # 200 - Modify the pci.c part
    {
        'tree': 'mac80211',
        'name': '200-Revert-wifi-ath12k-convert-tasklet-to-BH-workqueue-f',
        'filename': 'pci.c',
        'path_must_contain': ('mac80211', 'backports', 'drivers/net/wireless/ath/ath12k'),
        'parent_dir_exact': 'ath12k',
        'kind': 'regex',
        'replacements': [
            # 1. Restore tasklet processing function declaration and from_tasklet conversion
            (
                r'static void ath12k_pci_ce_workqueue\(struct work_struct \*work\)\n'
                r'\{\n'
                r'[ \t]*struct ath12k_ce_pipe \*ce_pipe = from_work\(ce_pipe, work, intr_wq\);',

                r'static void ath12k_pci_ce_tasklet(struct tasklet_struct *t)\n'
                r'{\n'
                r'\tstruct ath12k_ce_pipe *ce_pipe = from_tasklet(ce_pipe, t, intr_tq);'
            ),
            # 2. Dispatch tasklet in the interrupt processing function to replace the queue into the queue
            (
                r'[ \t]*queue_work\(system_bh_wq,\s*&ce_pipe->intr_wq\);',
                r'\ttasklet_schedule(&ce_pipe->intr_tq);'
            ),
            # 3. Use tasklet_setup to replace INIT_WORK at interrupt initialization
            (
                r'[ \t]*INIT_WORK\(&ce_pipe->intr_wq,\s*ath12k_pci_ce_workqueue\);',
                r'\t\ttasklet_setup(&ce_pipe->intr_tq, ath12k_pci_ce_tasklet);'
            ),
            # 4. Function name reduction:ath12k_pci_cancel_workqueue -> ath12k_pci_kill_tasklets
            (
                r'static void ath12k_pci_cancel_workqueue\(struct ath12k_base \*ab\)',
                r'static void ath12k_pci_kill_tasklets(struct ath12k_base *ab)'
            ),
            # 5. Use tasklet_kill to replace cancel_work_sync in the cleanup function
            (
                r'[ \t]*cancel_work_sync\(&ce_pipe->intr_wq\);',
                r'\t\ttasklet_kill(&ce_pipe->intr_tq);'
            ),
            # 6. Restore the call point in the synchronous disabled interrupt function
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
            # 1. Header file reference area introduction <linux/of_net.h>
            (
                r'(#include <linux/etherdevice\.h>\n)',
                r'\1#include <linux/of_net.h>\n'
            ),
            # 2. Add struct mac_address *addresses to ath12k_mac_setup_iface_combinations;
            (
                r'(struct wiphy \*wiphy = ah->hw->wiphy;\n[ \t]*struct wiphy_radio \*radio;\n)',
                r'\1\tstruct mac_address *addresses;\n'
            ),
            # 3. Increase addresses memory allocation and update the goto abnormal jump label after radio allocation failure
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
            # 4. Copy the MAC address to the addresses array at the end of the for_each_ar loop
            (
                r'([ \t]*radio\[i\]\.n_iface_combinations = 1;\n)',
                r'\1\n\t\tether_addr_copy(addresses[i].addr, ar->mac_addr);\n'
            ),
            # 5. Set the addresses and n_addresses members of the wiphy structure
            (
                r'([ \t]*wiphy->n_radio = ah->num_radio;\n)',
                r'\1\n\twiphy->addresses = addresses;\n\twiphy->n_addresses = ah->num_radio;\n'
            ),
            # 6. Add kfree(addresses) to the error cleaning node
            (
                r'([ \t]*kfree\(radio\);\n\n)(err_free_combinations:)',
                r'\1err_free_addresses:\n\tkfree(addresses);\n\n\2'
            ),
            # 7. Read the MAC address from DT for a single Radio device in ath12k_mac_hw_register
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
            # 8. Remove the override settings for global ab->mac_addr under multiple radio scenarios
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
            # Add support for No. 10 memory area type in QMI memory allocation switch-case
            (
                r'([ \t]*)case LPASS_SHARED_V01_REGION_TYPE:\n',
                r'\1case LPASS_SHARED_V01_REGION_TYPE:\n\1case 10:\n'
            ),
        ],
    },
]
