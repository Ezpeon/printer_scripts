"""Tests for src/devices.py: paired_devices.txt, and finding a printer's address in it.

Names and addresses here are made up: no real device's address belongs in this repo.

Run all the tests with tests\\run_all.py, or only these with tests\\test_devices.py.
"""

import tempfile
from pathlib import Path

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import devices


# --- the file --------------------------------------------------------------------------------

def test_file_round_trip():
    """Writing a list and reading it back gives the same list, even with odd names."""
    listed = [
        ("Example phone", "11:22:33:44:55:66"),
        ("A=B printer", "AA:BB:CC:DD:EE:FF"),    # "=" inside the name
        ("Café ☕ printer", "01:23:45:67:89:AB"),  # accents and emoji
        ("Someone's printer", "0A:0B:0C:0D:0E:0F"),
    ]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "paired_devices.txt"
        devices.write_devices_file(path, listed)
        assert sorted(devices.read_devices_file(path)) == sorted(listed)


def test_read_skips_comments_and_tidies_up():
    """Comments and empty lines are skipped, spaces trimmed, addresses made upper case."""
    text = ("# a comment\n"
            "\n"
            "   My printer   =   aa:bb:cc:dd:ee:ff   \n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "paired_devices.txt"
        path.write_text(text, encoding="utf-8")
        assert devices.read_devices_file(path) == [("My printer", "AA:BB:CC:DD:EE:FF")]


def test_read_rejects_bad_lines():
    """A broken line gives an error that says which line it is."""
    for bad_line in ["no equals sign here",
                     "My printer = 12:34",              # not a whole address
                     " = AA:BB:CC:DD:EE:FF"]:           # no name
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "paired_devices.txt"
            path.write_text("# comment\n" + bad_line + "\n", encoding="utf-8")
            try:
                devices.read_devices_file(path)
            except ValueError as error:
                assert "line 2" in str(error), error
            else:
                raise AssertionError(f"no error for {bad_line!r}")


def test_clean_name():
    assert devices.clean_name("Bad\nname") == "Bad name"
    assert devices.clean_name("  spaces  ") == "spaces"
    assert devices.clean_name("") == "(no name)"


# --- finding the printer -----------------------------------------------------------------------

DEVICES = [("YHK-T201", "AA:BB:CC:DD:EE:01"), ("Example phone", "11:22:33:44:55:66")]


def lookup_error(listed, name) -> str:
    try:
        devices.find_address(listed, name)
    except LookupError as error:
        return str(error)
    raise AssertionError(f"no error for {name!r}")


def test_find_address():
    assert devices.find_address(DEVICES, "YHK-T201") == "AA:BB:CC:DD:EE:01"
    assert devices.find_address(DEVICES, "  yhk-t201 ") == "AA:BB:CC:DD:EE:01"  # case, spaces


def test_find_address_messages():
    two_printers = DEVICES + [("YHK-T201", "AA:BB:CC:DD:EE:02")]
    message = lookup_error(two_printers, "YHK-T201")
    assert "--address" in message and "AA:BB:CC:DD:EE:02" in message, message
    assert "Did you mean: YHK-T201?" in lookup_error(DEVICES, "YHK-T210")
    assert "The paired devices are: YHK-T201, Example phone." in lookup_error(DEVICES, "zzz")


if __name__ == "__main__":
    run_tests(globals())
