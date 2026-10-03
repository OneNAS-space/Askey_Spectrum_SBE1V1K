现在有一种更简单的方式，可以在原厂 SBE1V1K 上启动官方 OpenWrt initramfs。
不需要第二台路由器、串口访问、仓库模式，也不需要对 U-Boot 环境做任何永久性修改。

原厂的 Reset 恢复模式会检查 DHCP option 43。如果 DHCP 服务器返回 ASCII 值 `askey`，引导程序就会通过 TFTP 下载以下两个文件：

> rtq7300t_boot_auto_upgrade_fw.img \
> initramfs.itb

第一个文件可以是一个很小的、包含 U-Boot 脚本的 FIT 镜像。该脚本会下载并启动第二个文件——即正常的官方 OpenWrt initramfs。整个过程不会写入 eMMC。

以下步骤是在 Mac 直连 2.5G LAN 口的情况下测试通过的。

## 下载并校验当前的 OpenWrt initramfs

安装所需工具：
```sh
brew install dnsmasq u-boot-tools dtc
```

使用一个新目录，以免之前尝试留下的文件混入本次操作：
```sh
RAMBOOT_DIR="$(mktemp -d /private/tmp/sbe1v1k-ramboot.XXXXXX)"
cd "$RAMBOOT_DIR"

curl --fail --location --retry 3 --remote-name \
  https://downloads.openwrt.org/snapshots/targets/qualcommbe/ipq95xx/openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb

curl --fail --location --retry 3 --remote-name \
  https://downloads.openwrt.org/snapshots/targets/qualcommbe/ipq95xx/sha256sums

grep -F 'askey_sbe1v1k-initramfs-uImage.itb' sha256sums | \
  shasum -a 256 -c -
```

除非校验命令输出以下内容，否则不要继续：
> openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb: OK

将其重命名为启动程序所要求的文件名：
```sh
mv openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb initramfs.itb
ls -lh initramfs.itb
```

快照版本会定期更新替换，所以每次都要把镜像和 `sha256sums` 一起下载。如果校验失败，把两个文件都丢弃重新下载，不要沿用旧的哈希值。另外，原厂引导程序对 initramfs 有约 31 MiB 的大小限制。

## 构建恢复用的启动器（launcher）

创建 `boot.cmd`：
```sh
setenv serverip 172.16.252.252
tftpboot 0x80000000 initramfs.itb
bootm 0x80000000
```

创建 `auto.its`：
```dts
/dts-v1/;

/ {
	description = "SBE1V1K recovery launcher";
	#address-cells = <1>;

	images {
		RTQ7300T {
			description = "model marker";
			data = [00];
			type = "firmware";
			arch = "arm";
			compression = "none";
			hash-1 {
				algo = "sha256";
			};
		};

		script {
			description = "boot OpenWrt initramfs";
			data = /incbin/("boot.cmd");
			type = "script";
			arch = "arm";
			compression = "none";
			hash-1 {
				algo = "sha256";
			};
		};
	};
};
```

构建并检查它：
```sh
mkimage -f auto.its rtq7300t_boot_auto_upgrade_fw.img
dumpimage -l rtq7300t_boot_auto_upgrade_fw.img
```

`dumpimage` 应该列出两个镜像，名为 `RTQ7300T` 和 `script`。这个启动器只会执行 `tftpboot` 和 `bootm`，不包含 `saveenv`、`mmc write` 或其他任何写入 flash 的命令。

## 在 macOS 上启动 DHCP 和 TFTP

找到有线以太网接口：
```sh
networksetup -listallhardwareports
```

接口名称不是固定的。`en7` 只是我 Mac 上那个 USB 以太网适配器的名字；换一台 Mac 可能叫 `en4`、`en8` 或其他名字。找到 USB/Thunderbolt 以太网适配器对应的 `Hardware Port`，使用其 `Device` 那一行显示的值。例如：
```
Hardware Port: USB 10/100/1000 LAN
Device: en7
Ethernet Address: 00:e0:4c:xx:xx:xx
```
在这个例子中，正确的设置是 `IFACE=en7`。不要使用 Wi-Fi 接口，也不要不加检查就直接照抄 `en7`。

```sh
IFACE=en7
TFTP_ROOT=/private/tmp/sbe1v1k-tftp

sudo install -d -m 0755 "$TFTP_ROOT"
sudo install -m 0644 \
  rtq7300t_boot_auto_upgrade_fw.img \
  initramfs.itb \
  "$TFTP_ROOT/"

sudo ipconfig set "$IFACE" MANUAL 172.16.252.252 255.255.0.0
sudo ifconfig "$IFACE" inet 172.16.252.252 netmask 255.255.0.0 up
```

后面 initramfs 会使用 `192.168.1.1`。请确保 Wi-Fi 或其他接口没有已经连接到 `192.168.1.0/24` 这个网段。

在启动 dnsmasq 之前，先检查是否还有旧的测试实例在运行：
```sh
pgrep -fl "dnsmasq.*--interface=$IFACE" || true
```
该命令应该没有任何输出。如果显示有旧的 dnsmasq 进程，先用 Ctrl-C 停止那个前台进程。同时运行两份会因为 `Address already in use` 而失败。

启动 DHCP 和 TFTP。保持这个终端窗口开着：
```sh
DNSMASQ="$(brew --prefix dnsmasq)/sbin/dnsmasq"

sudo "$DNSMASQ" \
  --keep-in-foreground \
  --interface="$IFACE" \
  --bind-interfaces \
  --port=0 \
  --dhcp-authoritative \
  --dhcp-broadcast \
  --dhcp-range=172.16.252.10,172.16.252.20,255.255.0.0,5m \
  --dhcp-option=43,askey \
  --dhcp-option=3 \
  --dhcp-option=6 \
  --enable-tftp \
  --tftp-root="$TFTP_ROOT" \
  --log-facility=- \
  --log-dhcp
```
`--log-facility=-` 是故意加上的。如果不加这个参数，dnsmasq 在 macOS 上即使 DHCP 和 TFTP 都在正常工作，终端也可能不显示任何日志。

这里最关键的恢复触发条件是：
```
--dhcp-option=43,askey
```
如果没有这个值，原厂引导程序可以完成 DHCP，但不会去请求那两个 TFTP 文件。

## 启动路由器

把 Mac 直连到路由器的 2.5G LAN 口，不是 WAN 口。先启动 dnsmasq，再给路由器上电。

1. 关闭路由器电源，等待 5 秒。
2. 按住 Reset 按钮。
3. 在继续按住 Reset 的同时打开路由器电源。
4. 大约 12 秒后松开 Reset。

dnsmasq 所在的终端应该会先显示 DHCP 过程，接着是两次成功的 TFTP 传输。具体 IP 可能不同，但顺序应该类似这样：

> DHCPDISCOVER(en7) ... \
> DHCPOFFER(en7) 172.16.252.x ... \
> DHCPREQUEST(en7) 172.16.252.x ... \
> DHCPACK(en7) 172.16.252.x ... \
> sent rtq7300t_boot_auto_upgrade_fw.img to 172.16.252.x \
> sent initramfs.itb to 172.16.252.x

第二个文件传输完成后，等待大约 60 秒。

## 连接到 initramfs

打开另一个终端，给 OpenWrt 管理网络添加一个地址：
```sh
IFACE=en7
sudo ifconfig "$IFACE" alias 192.168.1.2 netmask 255.255.255.0

route -n get 192.168.1.1
ping -c 3 192.168.1.1
nc -G 2 -vz 192.168.1.1 22
```
`route -n get` 的结果必须显示走的是这个有线接口。官方 initramfs 通常没有设置 root 密码：
```sh
ssh -o UserKnownHostsFile=/dev/null \
  -o StrictHostKeyChecking=no \
  root@192.168.1.1
```

检查这确实是正确的板子，并且根文件系统在内存（RAM）中：
```sh
id
cat /tmp/sysinfo/board_name
. /etc/openwrt_release; echo "$DISTRIB_DESCRIPTION"
uname -r
cat /proc/cmdline
awk '$2 == "/" { print }' /proc/mounts
awk '$1 ~ /^\/dev\// { print }' /proc/mounts
```
板子名称应该是 `askey,sbe1v1k`，根挂载点应该是 `tmpfs`，最后一条命令不应该列出任何已挂载的 eMMC 分区。

完成测试后，在 dnsmasq 的终端里按 Ctrl-C，然后正常给路由器断电重启。由于这个启动器不会写入 eMMC 或 U-Boot 环境，设备原有系统不会被改动。之后如果要正式安装，可以再单独用官方的 SBE1V1K `sysupgrade` 镜像来完成。

如果没有出现任何 DHCP 消息，检查 dnsmasq 是否在上电前就已经启动、有线接口和 2.5G LAN 口是否正确，然后重复断电/Reset 的操作序列。如果出现了 DHCP 但只传输了第一个文件，检查 `initramfs.itb` 是否确实存在于 TFTP 根目录，且文件名完全一致。
