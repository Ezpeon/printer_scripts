"""Helpers shared by the test files.

Importing this file also makes the project's code importable: it puts the project folder on
Python's import path, so "from src import pictures" works. That's why the test files import
helpers before src.
"""

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

from runner import Skip

PROJECT = Path(__file__).resolve().parent.parent  # the printer_scripts folder
sys.path.insert(0, str(PROJECT))


def same_dots(a: Image.Image, b: Image.Image) -> bool:
    """True if two black-and-white pictures have the same size and the same dots.

    tobytes() packs the dots 8 per byte, so equal bytes mean equal dots. (Pillow 12.3 warns
    that getdata() will go away, and its replacement doesn't exist in older Pillows.)
    """
    return a.size == b.size and a.tobytes() == b.tobytes()


def needs_segno():
    try:
        import segno  # noqa: F401  (only checking that it's there)
    except ModuleNotFoundError:
        raise Skip("segno isn't installed (python -m pip install -r requirements.txt)")


def run_script(*args: str, script: str = "printerscript.py") -> subprocess.CompletedProcess:
    """Run one of the scripts as a user would, e.g. run_script("--test_page", "--preview",
    "x.png"), and return what happened (exit code, printed text)."""
    # UTF-8 both ways, so text like "👋" in the script's messages arrives intact (when its
    # output goes to a pipe, Windows' Python would otherwise use an older encoding).
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(PROJECT / script), *args], capture_output=True,
                          encoding="utf-8", env=environment)
