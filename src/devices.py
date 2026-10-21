"""paired_devices.txt: the list of paired Bluetooth devices, one "name = address" per line.

save_paired_devices.py writes it (with the names and addresses from paired_windows.py or
paired_linux.py), and printerscript.py reads it to find the printer's address by its name.
"""

from __future__ import annotations

import datetime
import difflib
import re
from pathlib import Path

# In the project folder (the folder above this one), next to the scripts.
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "paired_devices.txt"

# A Bluetooth address: 6 bytes in hexadecimal separated by colons, e.g. "A1:B2:C3:D4:E5:F6".
ADDRESS_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def clean_name(name: str) -> str:
    """Make a device name safe to store on one line.

    A line break inside a name would split it over two lines and break the file, so control
    characters become spaces. Example: "Bad\\nname" -> "Bad name". An empty name -> "(no name)".
    """
    cleaned = "".join(c if c.isprintable() else " " for c in name).strip()
    return cleaned or "(no name)"


def write_devices_file(path: Path, devices: list[tuple[str, str]]) -> None:
    """Write one "name = address" line per device, sorted by name, after two comment lines."""
    today = datetime.date.today().isoformat()
    lines = [
        f"# Paired Bluetooth devices, written by save_paired_devices.py on {today}.",
        "# One per line: name = address. Run save_paired_devices.py again after pairing a new device.",
    ]
    for name, address in sorted(devices, key=lambda device: (device[0].lower(), device[1])):
        lines.append(f"{name} = {address}")
    # UTF-8 on purpose: names can contain accents or emoji, and Windows' default text
    # encoding can't store all of them.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_devices_file(path: Path) -> list[tuple[str, str]]:
    """Read the file back as a list of (name, address). Raises ValueError on a bad line."""
    devices = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # an empty line or a comment
        # Split at the LAST "=": a name may contain "=", an address never does.
        # Example: "A=B printer = AA:BB:CC:DD:EE:FF" -> name "A=B printer".
        name, equals, address = line.rpartition("=")
        name, address = name.strip(), address.strip().upper()
        if not equals or not name or not ADDRESS_RE.match(address):
            raise ValueError(
                f'{path}, line {number}: expected "name = AA:BB:CC:DD:EE:FF", got "{line}"')
        devices.append((name, address))
    return devices


def find_address(devices: list[tuple[str, str]], printer_name: str) -> str:
    """Find the address of `printer_name` in the (name, address) list of paired_devices.txt.

    Upper/lower case and spaces around the name don't matter. Raises LookupError, with a
    message for the user, if no device or more than one device has that name.
    """
    wanted = printer_name.strip().casefold()
    addresses = [address for name, address in devices if name.casefold() == wanted]
    if len(addresses) == 1:
        return addresses[0]
    if addresses:
        raise LookupError(f'{len(addresses)} paired devices are called "{printer_name}": '
                          f'{", ".join(addresses)}. Choose one with --address.')
    names = [name for name, _address in devices]
    message = f'No paired device is called "{printer_name}".'
    close_names = difflib.get_close_matches(printer_name, names, n=3, cutoff=0.6)
    if close_names:
        message += f" Did you mean: {', '.join(close_names)}?"
    elif names:
        message += f" The paired devices are: {', '.join(names)}."
    message += (" If the printer was paired after the list was made, run "
                "save_paired_devices.py again.")
    raise LookupError(message)
