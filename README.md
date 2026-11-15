<div align="center">

# AutoVirt

This project automates complex Linux virtualization tasks.

[![](https://dcbadge.limes.pink/api/server/https://discord.gg/hNVHChp7PX)](https://discord.gg/hNVHChp7PX)

</div>

---






## Instructions

<details>
<summary>Expand for details...</summary>

#### 1. Clone Git repository
```sh
git clone --single-branch --depth=1 https://github.com/Scrut1ny/AutoVirt
```

#### 2. Change directory
```sh
cd AutoVirt/
```

#### 3. Execute
```sh
./main.sh
```
- Experimental distro support:
```sh
EXPERIMENTAL=1 ./main.sh
```

---

### 4. Update repository
- ***Make sure you're in the `AutoVirt/` root directory when running the command below!***
```sh
git fetch --all && git reset --hard origin/main
```

</details>





---

## Supported Distros

| Distro         | Status       |
|----------------|--------------|
| Arch based     | Supported    |
| Debian based   | Experimental |
| Fedora based   | Experimental |
| openSUSE based | Experimental |

## Prerequisites

- `git` package
- Supported Linux distribution
- UEFI/BIOS Settings:
  - CPU virtualization extensions (VT-x / AMD-V)
  - IOMMU support (VT-d / AMD-Vi)
- A dGPU for passthrough (recommended)

## Troubleshooting

#### QEMU log
```
vfio 0000:01:00.0: failed to setup container for group 13: Failed to set group container: Invalid argument
```
#### dmesg log
```
vfio-pci 0000:01:00.0: Firmware has requested this device have a 1:1 IOMMU mapping, rejecting configuring the device without a 1:1 mapping. Contact your platform vendor.
```

- Disable `Pre-boot DMA Protection` (Needed for VFIO)
  - (*Change `IOMMU` from `[Auto]` to `[Enabled]` to find hidden setting*)

## 固定内核与 ACPI identity 部署配置

需要保留 CachyOS **7.0.12-1** 与 QEMU **11.0.3 ACPI identity** 构建时，使用独立入口 `setup-cachyos7012-acpi.sh`。
它固定版本和包 SHA256、保留 RTL8125，在独立目录构建/安装，不自动重启或替换运行中的虚拟机。

详见 [部署、验证与回退说明](profiles/cachyos-7.0.12-acpi/README.zh-CN.md)。原 `main.sh` 的默认流程保持不变。
