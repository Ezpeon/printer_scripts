"""Which Bluetooth devices are paired, on Linux: asked to bluetoothctl.

bluetoothctl is the command-line tool of BlueZ, the standard Linux Bluetooth software. It
works as a normal user. NOT TESTED on a real Linux machine yet.
"""

from __future__ import annotations

import re
import subprocess

from .devices import clean_name

# Some bluetoothctl versions colour their output with codes like "\x1b[0;94m".
COLOUR_CODE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class BluetoothctlError(Exception):
    """bluetoothctl couldn't be used. The message says why and what to do about it."""


def run_bluetoothctl(*args: str) -> str:
    """Run `bluetoothctl <args>` and return what it printed, without colour codes.

    Raises BluetoothctlError if it isn't installed or doesn't answer.
    """
    try:
        result = subprocess.run(["bluetoothctl", *args], capture_output=True, text=True,
                                timeout=10)
    except FileNotFoundError:
        raise BluetoothctlError("bluetoothctl wasn't found. Install BlueZ, e.g. "
                                "'sudo apt install bluez'.")
    except subprocess.TimeoutExpired:
        # bluetoothctl waits forever if the Bluetooth service isn't running.
        raise BluetoothctlError("bluetoothctl didn't answer within 10 seconds. Is the "
                                "Bluetooth service running? Try 'sudo systemctl start "
                                "bluetooth'.")
    return COLOUR_CODE_RE.sub("", result.stdout)


def parse_bluetoothctl_devices(text: str) -> list[str]:
    """Get the addresses from `bluetoothctl devices`.

    Its lines look like "Device A1:B2:C3:D4:E5:F6 My phone". Other lines are ignored.
    """
    addresses = []
    for line in text.splitlines():
        match = re.match(r"\s*Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\b", line)
        if match:
            addresses.append(match.group(1).upper())
    return addresses


def parse_bluetoothctl_info(text: str) -> dict:
    """Read `bluetoothctl info <address>` into a dict.

    It prints a first line like "Device A1:B2:C3:D4:E5:F6 (public)", then lines like
    "\\tName: My phone" and "\\tPaired: yes". Returns e.g. {"Name": "My phone", "Paired": "yes",
    ...}, plus "random address": True when the first line says "(random)".
    """
    info: dict = {}
    lines = text.splitlines()
    for line in lines:
        key, colon, value = line.strip().partition(": ")
        if colon and key and " " not in key:
            info.setdefault(key, value.strip())  # keep the first one ("UUID" repeats)
    info["random address"] = any(line.startswith("Device ") and "(random)" in line
                                 for line in lines)
    return info


def paired_devices_linux() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (classic devices, skipped low-energy entries), each a list of (name, address).

    Lists all known devices, then asks for each one's details. BlueZ 5.65 renamed the command
    that lists only the paired ones ("paired-devices" became "devices Paired"), while
    "devices" and "info" work the same in every version.
    Raises BluetoothctlError if bluetoothctl can't be used.
    """
    devices, skipped = [], []
    for address in parse_bluetoothctl_devices(run_bluetoothctl("devices")):
        info = parse_bluetoothctl_info(run_bluetoothctl("info", address))
        if info.get("Paired") != "yes":
            continue  # seen nearby, but not paired
        # "Alias" is the name the desktop's Bluetooth settings show: the device's own name
        # ("Name") unless you renamed it.
        name = clean_name(info.get("Alias") or info.get("Name") or "")
        # A random address means Bluetooth Low Energy, which the printer can't use.
        (skipped if info["random address"] else devices).append((name, address))
    return devices, skipped
