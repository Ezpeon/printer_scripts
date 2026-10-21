"""Tests for src/paired_linux.py: reading bluetoothctl's output. Need no Bluetooth.

The bluetoothctl examples were written by hand from BlueZ's usual output, since no Linux
machine was available, so they only show that the parsing works on that format. The real
output still has to be checked on Linux. Names and addresses are
made up.

Run all the tests with tests\\run_all.py, or only these with tests\\test_paired_linux.py.
"""

import subprocess

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import paired_linux


def test_bluetoothctl_devices():
    text = ("Device 11:22:33:44:55:66 Example phone\n"
            "Device AA:BB:CC:DD:EE:FF YHK-T201\n"
            "[CHG] Controller 00:11:22:33:44:55 Discovering: no\n")   # an unrelated line
    assert paired_linux.parse_bluetoothctl_devices(text) == ["11:22:33:44:55:66",
                                                             "AA:BB:CC:DD:EE:FF"]


def test_bluetoothctl_info_paired_classic():
    text = ("Device AA:BB:CC:DD:EE:FF (public)\n"
            "\tName: YHK-T201\n"
            "\tAlias: YHK-T201\n"
            "\tClass: 0x00040680\n"
            "\tPaired: yes\n"
            "\tTrusted: yes\n"
            "\tUUID: Serial Port               (00001101-0000-1000-8000-00805f9b34fb)\n")
    info = paired_linux.parse_bluetoothctl_info(text)
    assert info["Alias"] == "YHK-T201"
    assert info["Paired"] == "yes"
    assert info["random address"] is False


def test_bluetoothctl_info_random_and_old_format():
    random_le = ("Device 4A:2B:3C:4D:5E:6F (random)\n"
                 "\tName: Example watch\n"
                 "\tPaired: yes\n")
    assert paired_linux.parse_bluetoothctl_info(random_le)["random address"] is True
    # Older BlueZ versions don't add "(public)" / "(random)" to the first line.
    old_format = ("Device AA:BB:CC:DD:EE:FF\n"
                  "\tName: YHK-T201\n"
                  "\tPaired: no\n")
    info = paired_linux.parse_bluetoothctl_info(old_format)
    assert info["Paired"] == "no"
    assert info["random address"] is False


def test_bluetoothctl_problems():
    """bluetoothctl missing, or not answering: an error with advice, not a crash.

    Both are simulated: subprocess.run is swapped for a fake that fails like the real one
    would, and put back afterwards.
    """
    real_run = subprocess.run
    try:
        for problem, advice in [(FileNotFoundError(), "Install BlueZ"),
                                (subprocess.TimeoutExpired("bluetoothctl", 10),
                                 "sudo systemctl start bluetooth")]:
            def fake_run(*args, **kwargs):
                raise problem
            subprocess.run = fake_run
            try:
                paired_linux.run_bluetoothctl("devices")
            except paired_linux.BluetoothctlError as error:
                assert advice in str(error), error
            else:
                raise AssertionError(f"no error for {problem!r}")
    finally:
        subprocess.run = real_run


if __name__ == "__main__":
    run_tests(globals())
