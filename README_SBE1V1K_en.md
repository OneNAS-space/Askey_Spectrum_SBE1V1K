There is a simpler way to boot the official OpenWrt initramfs on a stock SBE1V1K. It does not need a second router, serial access, Warehouse mode, or any permanent U-Boot environment changes.

The stock Reset recovery checks DHCP option 43. If the DHCP server returns the ASCII value askey, the bootloader downloads these two files from TFTP:

> rtq7300t_boot_auto_upgrade_fw.img \
> initramfs.itb

The first file can be a tiny FIT containing a U-Boot script. That script downloads and boots the normal official OpenWrt initramfs as the second file. Nothing is written to eMMC.

The steps below were tested with a Mac connected directly to the 2.5G LAN port.

## Download and verify the current OpenWrt initramfs

Install the required tools:

`brew install dnsmasq u-boot-tools dtc`


Use a new directory so files left by an earlier attempt cannot be mixed into this one:
```
RAMBOOT_DIR="$(mktemp -d /private/tmp/sbe1v1k-ramboot.XXXXXX)"
cd "$RAMBOOT_DIR"

curl --fail --location --retry 3 --remote-name \
  https://downloads.openwrt.org/snapshots/targets/qualcommbe/ipq95xx/openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb

curl --fail --location --retry 3 --remote-name \
  https://downloads.openwrt.org/snapshots/targets/qualcommbe/ipq95xx/sha256sums

grep -F 'askey_sbe1v1k-initramfs-uImage.itb' sha256sums | \
  shasum -a 256 -c -
```
Do not continue unless the checksum command prints:

> openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb: OK

Rename it to the filename requested by the launcher:
```
mv openwrt-qualcommbe-ipq95xx-askey_sbe1v1k-initramfs-uImage.itb initramfs.itb
ls -lh initramfs.itb
```

Snapshots are replaced regularly, so always download the image and sha256sums together. If verification fails, discard both files and download them again. Do not reuse an old hash. The stock bootloader also has an initramfs size limit of about 31 MiB.

## Build the recovery launcher

Create `boot.cmd` :
```
setenv serverip 172.16.252.252
tftpboot 0x80000000 initramfs.itb
bootm 0x80000000
```

Create `auto.its` :
```
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

Build and inspect it:
```
mkimage -f auto.its rtq7300t_boot_auto_upgrade_fw.img
dumpimage -l rtq7300t_boot_auto_upgrade_fw.img
```

`dumpimage` should list two images named `RTQ7300T` and `script`. The launcher only runs `tftpboot` and `bootm`; it contains no `saveenv`, `mmc write`, or other flash commands.

## Start DHCP and TFTP on macOS

Find the wired Ethernet interface:
`networksetup -listallhardwareports`

The interface name is not fixed. `en7` is only the name of the USB Ethernet adapter on my Mac; another Mac may call it `en4`, `en8`, or something else. Find the `Hardware Port` for the USB/Thunderbolt Ethernet adapter and use the value shown on its `Device` line. For example:

> Hardware Port: USB 10/100/1000 LAN \
> Device: en7 \
> Ethernet Address: 00:e0:4c:xx:xx:xx

In that example the correct setting is `IFACE=en7`. Do not use the Wi-Fi interface or copy en7 without checking it first.
```
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

The initramfs will later use `192.168.1.1`. Make sure Wi-Fi or another interface is not already connected to a `192.168.1.0/24` network.

Before starting dnsmasq, check that an older test instance is not still running:

`pgrep -fl "dnsmasq.*--interface=$IFACE" || true`

The command should print nothing. If it shows an old dnsmasq process, stop that foreground process with Ctrl-C first. Running a second copy will fail with `Address already in use`.

Start DHCP and TFTP. Keep this terminal open:
```
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

`--log-facility=-` is intentional. Without it, dnsmasq may stay silent in the terminal on macOS even though DHCP and TFTP are working.

The important recovery trigger is:

> --dhcp-option=43,askey

Without that value, the stock bootloader can finish DHCP but will not request the two TFTP files.

## Boot the router

Connect the Mac directly to the router's 2.5G LAN port, not the WAN port. Start dnsmasq before powering on the router.

1. Turn the router off and wait five seconds.
2. Hold the Reset button.
3. Turn the router on while still holding Reset.
4. Release Reset after about 12 seconds.

The dnsmasq terminal should show DHCP followed by two successful TFTP transfers. The exact IP may differ, but the order should look like this:

> DHCPDISCOVER(en7) ... \
> DHCPOFFER(en7) 172.16.252.x ... \
> DHCPREQUEST(en7) 172.16.252.x ... \
> DHCPACK(en7) 172.16.252.x ... \
> sent rtq7300t_boot_auto_upgrade_fw.img to 172.16.252.x \
> sent initramfs.itb to 172.16.252.x

After the second transfer finishes, wait about 60 seconds.

## Connect to the initramfs

Open another terminal and add an address for the OpenWrt management network:
```
IFACE=en7
sudo ifconfig "$IFACE" alias 192.168.1.2 netmask 255.255.255.0

route -n get 192.168.1.1
ping -c 3 192.168.1.1
nc -G 2 -vz 192.168.1.1 22
```
`route -n get` must show the wired interface. The official initramfs normally has no root password:
```
ssh -o UserKnownHostsFile=/dev/null \
  -o StrictHostKeyChecking=no \
  root@192.168.1.1
```
Check that this is the correct board and that the root filesystem is in RAM:
```
id
cat /tmp/sysinfo/board_name
. /etc/openwrt_release; echo "$DISTRIB_DESCRIPTION"
uname -r
cat /proc/cmdline
awk '$2 == "/" { print }' /proc/mounts
awk '$1 ~ /^\/dev\// { print }' /proc/mounts
```
The board name should be `askey,sbe1v1k`, the root mount should be `tmpfs`, and the last command should not list any mounted eMMC partition.

When finished, press Ctrl-C in the dnsmasq terminal and power-cycle the router normally. \
Because the launcher does not write eMMC or the U-Boot environment, the installed system is unchanged. \
A permanent installation can then be done separately with the official SBE1V1K `sysupgrade` image.

If no DHCP message appears, check that dnsmasq was already running before power-on, verify the wired interface and 2.5G LAN port, then repeat the power-off/Reset sequence. \
If DHCP appears but only the first file is transferred, check that `initramfs.itb` is present in the TFTP root with exactly that filename.
