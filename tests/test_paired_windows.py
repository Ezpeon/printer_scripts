"""Tests for src/paired_windows.py: reading the registry's values. Need no Bluetooth.

They run on any system: only paired_devices_windows() itself needs Windows, and it isn't
called here. Names and addresses are made up.

Run all the tests with tests\\run_all.py, or only these with tests\\test_paired_windows.py.
"""

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import paired_windows


def test_format_address():
    assert paired_windows.format_address("a1b2c3d4e5f6") == "A1:B2:C3:D4:E5:F6"
    assert paired_windows.format_address("not-an-address") is None


def test_registry_text():
    """Names in the registry are UTF-8 bytes ending with a 0 byte."""
    assert paired_windows.registry_text(b"Example phone\x00") == "Example phone"
    assert paired_windows.registry_text(b"Caf\xc3\xa9\x00") == "Café"
    assert paired_windows.registry_text(b"\x00") == ""   # what an empty FriendlyName looks like
    assert paired_windows.registry_text(None) == ""      # value missing


def test_device_list_address():
    """Only the "Dev_<address>" sub-keys of Windows' device list mean "paired" (seen on
    2026-10-12: "Uninstall device" in Device Manager deleted a phone's Dev_ sub-key but left
    its per-service sub-keys behind)."""
    assert paired_windows.device_list_address("Dev_A1B2C3D4E5F6") == "A1:B2:C3:D4:E5:F6"
    assert paired_windows.device_list_address("DEV_a1b2c3d4e5f6") == "A1:B2:C3:D4:E5:F6"
    service = "{0000110c-0000-1000-8000-00805f9b34fb}_VID&00010075_PID&0100"
    assert paired_windows.device_list_address(service) is None
    assert paired_windows.device_list_address("Dev_123") is None


def test_windows_name():
    """The values copied from a real phone's sub-key (2026-10-12), with a made-up name."""
    values = {"COD": 5898764, "Name": b"Example phone\x00", "FriendlyName": b"\x00"}
    assert paired_windows.windows_name(values) == "Example phone"
    # A name given in Windows (FriendlyName) wins over the device's own name.
    renamed = dict(values, FriendlyName=b"Kitchen printer\x00")
    assert paired_windows.windows_name(renamed) == "Kitchen printer"
    # No sub-key for this device among the names: still a usable line in the file.
    assert paired_windows.windows_name({}) == "(no name)"


if __name__ == "__main__":
    run_tests(globals())
