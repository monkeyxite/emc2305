# emc2305 — Linux hwmon driver for Microchip EMC230x fan controllers

Linux kernel hwmon driver for the Microchip EMC2301/2302/2303/2305 RPM-based PWM fan controller family, backported from Linux 6.1 with fixes for out-of-tree use on ARM SBCs.

## Supported chips

| Chip    | Fans | Product ID |
|---------|------|------------|
| EMC2305 | 5    | 0x34       |
| EMC2303 | 3    | 0x35       |
| EMC2302 | 2    | 0x36       |
| EMC2301 | 1    | 0x37       |

## Motivation

This driver was developed to enable fan control on a **Radxa ROCK 5C** using the [Radxa Penta SATA HAT](https://radxa.com/products/accessories/penta-sata-hat/), which includes a Microchip EMC2301 fan controller connected via I2C8.

The vendor kernel (`6.1.115-vendor-rk35xx`) shipped with Armbian for the ROCK 5C does not include the `emc2305` driver. This out-of-tree module fills that gap with DKMS support for automatic rebuild on kernel updates.

## Patches / Changes from upstream Linux 6.1

### 1. Device Tree (OF) match table

The upstream Linux 6.1 driver only supports i2c name-based matching (`i2c_device_id`). It lacks an `of_match_table`, so the driver does not auto-bind to devices declared in a Device Tree overlay using `compatible = "microchip,emc2301"`.

**Fix:** Added `of_device_id emc2305_of_match[]` table with all four chip variants and registered it via `MODULE_DEVICE_TABLE(of, ...)` and `.of_match_table` in the driver struct.

```c
static const struct of_device_id emc2305_of_match[] = {
    { .compatible = "microchip,emc2301" },
    { .compatible = "microchip,emc2302" },
    { .compatible = "microchip,emc2303" },
    { .compatible = "microchip,emc2305" },
    { }
};
MODULE_DEVICE_TABLE(of, emc2305_of_match);
```

### 2. Device ID range check (inverted enum)

The probe function validates the chip's product ID register against the `emc230x_product_id` enum:

```c
enum emc230x_product_id {
    EMC2305 = 0x34,
    EMC2303 = 0x35,
    EMC2302 = 0x36,
    EMC2301 = 0x37,
};
```

Note that numerically `EMC2301 (0x37) > EMC2305 (0x34)`. The original upstream check was:

```c
if (device != EMC2305_DEVICE)   // only accepted 0x34
    return -ENODEV;
```

A naive "range" fix of `device < EMC2301 || device > EMC2305` translates to `device < 0x37 || device > 0x34`, which is **always true** and rejects every chip. The correct check accepts any value in the set {0x34..0x37}:

```c
if (device < EMC2305 || device > EMC2301)   // 0x34 <= device <= 0x37
    return -ENODEV;
```

**Fix:** Changed the check to use the correct numeric bounds (`EMC2305=0x34` as lower bound, `EMC2301=0x37` as upper bound).

## Device Tree overlay

For the Radxa ROCK 5C with Penta SATA HAT, use this minimal overlay (Armbian `armbian-add-overlay`):

```dts
/dts-v1/;
/plugin/;

/ {
    metadata {
        title = "Enable I2C8-EMC2301-FAN minimal";
        compatible = "radxa,rock-5c";
        category = "misc";
        description = "Enable EMC2301 fan controller on I2C8-M2.";
    };

    fragment@0 {
        target = <&i2c8>;
        __overlay__ {
            #address-cells = <1>;
            #size-cells = <0>;
            status = "okay";

            emc2301@2f {
                compatible = "microchip,emc2301";
                reg = <0x2f>;
            };
        };
    };
};
```

Also enable i2c8-m2 in `/boot/armbianEnv.txt`:
```
overlays=rk3588-i2c8-m2
user_overlays=rk3588s-i2c8-fan-minimal
```

> **Note:** The full thermal zone overlay from [lovelycrabs/rpi5-sata](https://github.com/lovelycrabs/rpi5-sata/tree/main/overlays/rock5c) causes `-EPROBE_DEFER` loops on the vendor kernel due to unresolved thermal zone dependencies. Use the minimal overlay above and manage fan curves in userspace via `fancontrol`/`lm-sensors`.

## Installation

### Prerequisites

```bash
sudo apt install dkms linux-headers-$(uname -r) build-essential
```

### DKMS install

```bash
sudo cp -r . /usr/src/emc2305-1.0
sudo dkms add -m emc2305 -v 1.0
sudo dkms build -m emc2305 -v 1.0
sudo dkms install -m emc2305 -v 1.0
echo 'emc2305' | sudo tee /etc/modules-load.d/emc2305.conf
```

### Manual install

```bash
make
sudo cp emc2305.ko /lib/modules/$(uname -r)/kernel/drivers/hwmon/
sudo depmod -a
sudo modprobe emc2305
```

## Verifying

```bash
# Check module loaded
lsmod | grep emc2305

# Check fan speed (RPM)
cat /sys/class/hwmon/hwmon*/fan1_input   # if bound via DT overlay

# Check i2c bus
sudo i2cdetect -y 8   # should show 0x2f
```

## Tested on

- **Board:** Radxa ROCK 5C
- **HAT:** Radxa Penta SATA HAT (EMC2301 @ i2c8, address 0x2f)
- **OS:** Armbian 26.5.1 (Ubuntu resolute)
- **Kernel:** 6.1.115-vendor-rk35xx

## License

GPL-2.0 (same as upstream Linux kernel driver)
