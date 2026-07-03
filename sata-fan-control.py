#!/usr/bin/env python3
"""
SATA HAT fan controller for Rock 5C + Radxa Penta SATA HAT
Controls EMC2301 fan via direct PWM based on SoC temperature.

Requires emc2305 driver with direct drive mode patch:
  https://github.com/monkeyxite/emc2305

Temperature -> PWM mapping:
  <40°C  -> MIN_PWM (quiet)
  40-65°C -> linear ramp
  >65°C  -> MAX_PWM (full speed)
"""

import time
import sys
import os
import signal
import glob

# Paths
TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"  # soc-thermal
INTERVAL = 10  # seconds between checks

# Temperature curve (millidegrees)
MIN_TEMP = 40000   # 40°C — fan starts ramping
MAX_TEMP = 65000   # 65°C — full speed
MIN_PWM = 60       # minimum PWM (0-255)
MAX_PWM = 255      # full speed

def read_int(path):
    with open(path) as f:
        return int(f.read().strip())

def write_int(path, value):
    with open(path, 'w') as f:
        f.write(str(value))

def find_emc2305_pwm():
    """Find emc2305 hwmon PWM path — robust to hwmon number changes."""
    for name_path in glob.glob("/sys/class/hwmon/hwmon*/name"):
        with open(name_path) as f:
            if "emc2305" in f.read():
                hwmon_dir = os.path.dirname(name_path)
                pwm_path = os.path.join(hwmon_dir, "pwm1")
                if os.path.exists(pwm_path):
                    return pwm_path
    return None

def temp_to_pwm(temp_mdeg):
    if temp_mdeg <= MIN_TEMP:
        return MIN_PWM
    if temp_mdeg >= MAX_TEMP:
        return MAX_PWM
    ratio = (temp_mdeg - MIN_TEMP) / (MAX_TEMP - MIN_TEMP)
    return int(MIN_PWM + ratio * (MAX_PWM - MIN_PWM))

def main():
    pwm_path = find_emc2305_pwm()
    if not pwm_path:
        print("ERROR: emc2305 hwmon PWM not found. Is the driver loaded?", file=sys.stderr)
        sys.exit(1)

    print(f"SATA HAT fan controller started")
    print(f"  PWM path: {pwm_path}")
    print(f"  Temp sensor: {TEMP_PATH}")
    print(f"  Curve: {MIN_TEMP//1000}°C-{MAX_TEMP//1000}°C -> PWM {MIN_PWM}-{MAX_PWM}")

    def shutdown(sig, frame):
        print("Shutting down — setting fan to full speed for safety")
        try:
            write_int(pwm_path, MAX_PWM)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    last_pwm = -1
    while True:
        try:
            temp = read_int(TEMP_PATH)
            pwm = temp_to_pwm(temp)
            if pwm != last_pwm:
                write_int(pwm_path, pwm)
                print(f"Temp: {temp/1000:.1f}°C -> PWM: {pwm}/255", flush=True)
                last_pwm = pwm
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr, flush=True)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
