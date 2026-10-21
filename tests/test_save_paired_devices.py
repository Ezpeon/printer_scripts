"""Tests for save_paired_devices.py, the command line.

Running it for real would read this computer's real devices, so only --help is run here: it
shows that the script starts and finds its code in src/. What that code does is tested in
test_devices.py, test_paired_windows.py and test_paired_linux.py.

Run all the tests with tests\\run_all.py, or only these with tests\\test_save_paired_devices.py.
"""

from runner import run_tests
from helpers import run_script


def test_command_line_help():
    result = run_script("--help", script="save_paired_devices.py")
    assert result.returncode == 0 and "--output" in result.stdout, result.stderr


if __name__ == "__main__":
    run_tests(globals())
