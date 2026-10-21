"""Which Bluetooth devices are paired, on Windows: read from the registry.

No admin rights needed. Only works on Windows: winreg, Python's module for the registry, only
exists there.
"""

from __future__ import annotations

import re

from .devices import clean_name

# Two places in the registry are used, both readable without admin rights (checked
# 2026-10-12):
#
# 1. WHICH devices are paired: Windows' device list (what Device Manager shows). It has one
#    sub-key "Dev_<address>" per paired device, e.g. "Dev_A1B2C3D4E5F6": classic Bluetooth
#    devices under BTHENUM, Bluetooth Low Energy ones under BTHLE. Removing a device in
#    Settings deletes its sub-key, and the whole BTHENUM or BTHLE key disappears when no
#    device of that kind is left. ("Uninstall device" in Device Manager isn't unpairing: it
#    deletes the sub-key but keeps the pairing, so the device comes back when Bluetooth
#    restarts. The file then shows what Windows shows at that moment.)
# 2. Their NAMES: one sub-key per device, named after its address ("a1b2c3d4e5f6"). This key
#    keeps every device Windows has EVER seen, even after unpairing. So it's only used to
#    look up names, never to decide what's paired.
WINDOWS_PAIRED_KEYS = {
    "classic": r"SYSTEM\CurrentControlSet\Enum\BTHENUM",
    "low energy": r"SYSTEM\CurrentControlSet\Enum\BTHLE",
}
WINDOWS_NAMES_KEY = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"


def format_address(hex12: str) -> str | None:
    """"a1b2c3d4e5f6" -> "A1:B2:C3:D4:E5:F6". None if it isn't 12 hexadecimal digits."""
    if not re.fullmatch(r"[0-9a-fA-F]{12}", hex12):
        return None
    upper = hex12.upper()
    return ":".join(upper[i:i + 2] for i in range(0, 12, 2))


def registry_text(value: object) -> str:
    """Turn a name stored in the registry into text.

    Windows stores device names as bytes: UTF-8 text that ends with a 0 byte.
    Example: b"My phone\\x00" -> "My phone". A missing or empty value -> "".
    """
    if not isinstance(value, bytes):
        return ""
    return value.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def device_list_address(sub_key_name: str) -> str | None:
    """Get the address from a sub-key name in Windows' device list.

    "Dev_A1B2C3D4E5F6" -> "A1:B2:C3:D4:E5:F6". The other sub-keys there, one per service a
    device offers (e.g. "{0000110c-0000-1000-8000-00805f9b34fb}_VID&..."), -> None. Those
    can stay behind without the Dev_ sub-key (seen after "Uninstall device" in Device
    Manager), so they don't count.
    """
    match = re.fullmatch(r"(?i)dev_([0-9a-f]{12})", sub_key_name)
    return format_address(match.group(1)) if match else None


def windows_name(values: dict) -> str:
    """Pick a device's name from the values of its sub-key in WINDOWS_NAMES_KEY.

    "FriendlyName" is probably the name you gave the device in Windows (it's just a 0 byte if
    you never renamed it). "Name" is the name the device announces itself.
    """
    return clean_name(registry_text(values.get("FriendlyName"))
                      or registry_text(values.get("Name")))


def registry_sub_keys(winreg, path: str) -> list[str]:
    """The names of the sub-keys of HKEY_LOCAL_MACHINE\\<path>. A missing key -> []."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except FileNotFoundError:
        return []
    names = []
    with key:
        while True:
            try:
                names.append(winreg.EnumKey(key, len(names)))
            except OSError:  # winreg's way of saying "no more sub-keys"
                return names


def registry_values(winreg, path: str) -> dict:
    """All the values of HKEY_LOCAL_MACHINE\\<path>, as {name: data}. A missing key -> {}."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except FileNotFoundError:
        return {}
    values = {}
    with key:
        while True:
            try:
                name, data, _kind = winreg.EnumValue(key, len(values))
            except OSError:  # no more values
                return values
            values[name] = data


def paired_devices_windows() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (classic devices, skipped low-energy devices), each a list of (name, address)."""
    import winreg  # only exists on Windows, so it's imported here instead of at the top

    found: dict = {}
    for kind, path in WINDOWS_PAIRED_KEYS.items():
        found[kind] = []
        for sub_key_name in registry_sub_keys(winreg, path):
            address = device_list_address(sub_key_name)
            if address is None:
                continue
            names_path = WINDOWS_NAMES_KEY + "\\" + address.replace(":", "").lower()
            found[kind].append((windows_name(registry_values(winreg, names_path)), address))
    return found["classic"], found["low energy"]
