"""Save the names and addresses of the paired Bluetooth devices to paired_devices.txt.

A Bluetooth connection needs the printer's address (like AA:BB:CC:DD:EE:FF), but people know
their printer by its name (like YHK-T201). This script asks the operating system which
devices are paired, and writes one "name = address" line per device. printerscript.py then
looks the name up in that file, without asking the system again.

Run it again after pairing a new device: it rewrites the whole file.

Works on:
- Windows: reads the list that Windows keeps in the registry (no admin rights needed).
- Linux: asks bluetoothctl, the command-line tool of BlueZ (the standard Linux Bluetooth
  software). NOT TESTED on a real Linux machine yet.

Only classic Bluetooth devices are saved. The printer uses classic Bluetooth (the "serial
port" profile, SPP), and a Bluetooth Low Energy address can't be used for that.

Usage:
    python save_paired_devices.py                   # writes paired_devices.txt next to this script
    python save_paired_devices.py --output my.txt   # writes it somewhere else

This file is only the command line. The code is in src/: devices.py (the file),
paired_windows.py and paired_linux.py (asking the system).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.devices import DEFAULT_FILE, write_devices_file
from src.paired_linux import BluetoothctlError, paired_devices_linux
from src.paired_windows import paired_devices_windows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save the names and addresses of the paired Bluetooth devices to a file, "
                    "for printerscript.py.")
    parser.add_argument("--output", type=Path, default=DEFAULT_FILE,
                        help=f"where to write the list (default: {DEFAULT_FILE.name} next to "
                             "this script)")
    args = parser.parse_args()
    # A device name with unusual characters must not crash the script when its output is
    # redirected to a file whose encoding can't show them.
    sys.stdout.reconfigure(errors="replace")

    if sys.platform == "win32":
        devices, skipped = paired_devices_windows()
    elif sys.platform.startswith("linux"):
        try:
            devices, skipped = paired_devices_linux()
        except BluetoothctlError as error:
            sys.exit(str(error))
    else:
        sys.exit(f"Sorry, only Windows and Linux are supported (this system is '{sys.platform}').")

    if devices:
        print(f"Paired classic Bluetooth devices ({len(devices)}):")
        for name, address in sorted(devices, key=lambda device: device[0].lower()):
            print(f"  {name} = {address}")
    else:
        print("No paired classic Bluetooth devices found. Pair the printer first, in the "
              "system's Bluetooth settings.")
    if skipped:
        print(f"Skipped (Bluetooth Low Energy, which the printer can't use): {len(skipped)}")
        for name, address in skipped:
            print(f"  {name} ({address})")
    names = [name for name, _address in devices]
    for name in sorted(set(names)):
        if names.count(name) > 1:
            print(f'Note: {names.count(name)} devices are called "{name}". To print to one of '
                  'them, give printerscript.py its address with --address.')

    write_devices_file(args.output, devices)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
