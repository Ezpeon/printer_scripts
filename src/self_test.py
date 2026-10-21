"""The self-test (--self_test): one print that checks a bit of everything.

A QR code, a sudoku and the test page, each with a label saying what to look for on the
paper. All three are made by the code, so the self-test needs no picture files.
"""

from __future__ import annotations

import datetime

from PIL import Image

from .escpos import DEFAULT_DARKNESS
from .pictures import make_test_page, prepare_picture, stack
from .qr import make_qr_picture
from .sudoku import make_sudoku_picture, sudoku_from_id
from .text import load_font, make_text_picture

SELF_TEST_QR = "https://x.com/POTUS"  # the US president's account on X (Twitter)
# Always the same sudoku, so the paper can be compared with a --preview made earlier.
SELF_TEST_SUDOKU = "9M-00001"
SELF_TEST_LABEL_SIZE = 24  # dots: 3 mm, a bit smaller than --text, so the labels stay short


def self_test_parts(width: int, darkness: int = DEFAULT_DARKNESS) -> list[Image.Image]:
    """All the parts of the self-test, as black-and-white dots, in printing order.

    Each after a label saying what to look for: a QR code of SELF_TEST_QR, the sudoku
    SELF_TEST_SUDOKU and the test page. Last, a footer with the date and the settings, so a
    print can be identified later.
    Raises ModuleNotFoundError without segno.
    """
    font = load_font(SELF_TEST_LABEL_SIZE)
    gap = Image.new("L", (width, round(16 * width / 384)), 255)  # 2 mm of white above a label

    def label(text: str) -> Image.Image:
        return prepare_picture(stack(gap, make_text_picture(text, width, font)), width)

    address = SELF_TEST_QR.removeprefix("https://")
    sudoku = sudoku_from_id(SELF_TEST_SUDOKU)
    return [
        label(f"1/3 QR code: scanning it with a phone should open {address}."),
        prepare_picture(make_qr_picture(SELF_TEST_QR, width), width),
        label("2/3 Sudoku: a grid with sharp lines, thicker around the boxes, and digits "
              "centred in their squares."),
        prepare_picture(make_sudoku_picture(sudoku, width), width),
        label("3/3 Test page: the frame complete on all four sides, the arrow pointing "
              "right, 8 grey steps."),
        prepare_picture(make_test_page(width), width),
        label(f"printerscript self-test, {datetime.datetime.now():%Y-%m-%d %H:%M}, "
              f"{width} dots wide, darkness {darkness}."),
    ]
