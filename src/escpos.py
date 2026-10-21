"""The bytes to send to the printer: ESC/POS commands.

ESC/POS is the command language of most receipt printers: short byte sequences, most of them
starting with ESC (0x1B) or GS (0x1D). This printer gets every print as a picture, never as
text, so only a handful of commands are needed.
"""

from __future__ import annotations

import struct

from PIL import Image

# Dots per row of small printers' print heads. 384 (8 dots per mm, 48 mm wide) is the usual
# one, and the printer this was tested with.
HEAD_WIDTHS = (384, 576)
DEFAULT_WIDTH = 384
# Darkness: higher = darker. 15 looked right on the printer this was tested with.
DEFAULT_DARKNESS = 15
# The GS v 0 command stores the number of rows in 2 bytes, so one print can't be taller.
MAX_ROWS = 65535
# A table for bytes.translate() that flips every bit of a byte: 0x00 <-> 0xFF, 0x8D <-> 0x72.
FLIP_BITS = bytes(255 - value for value in range(256))


def raster_command(dots: Image.Image) -> bytes:
    """The ESC/POS "GS v 0" command that prints `dots`, a mode "1" picture.

    1D 76 30 00, then the bytes per row and the number of rows (2 bytes each, low byte
    first), then the rows: 8 dots per byte, the leftmost dot in the highest bit, 1 = black.
    Example: a 384 x 200 picture starts with 1D 76 30 00 30 00 C8 00 (48 bytes per row,
    200 rows), followed by 48 x 200 = 9600 bytes of dots.
    """
    if dots.mode != "1":
        raise ValueError(f'expected a black-and-white (mode "1") picture, got mode "{dots.mode}"')
    if dots.width % 8:
        raise ValueError(f"the width must be a multiple of 8 dots, got {dots.width}")
    if dots.height > MAX_ROWS:
        raise ValueError(f"The picture would be {dots.height} dots tall, but one print can be "
                         f"at most {MAX_ROWS}. Use a less tall picture.")
    # Pillow packs a mode "1" picture the same way (8 dots per byte, the leftmost in the
    # highest bit), but with 1 = WHITE. So every bit is flipped.
    rows = dots.tobytes().translate(FLIP_BITS)
    # "<HH": two 2-byte numbers, low byte first ("little-endian").
    return b"\x1d\x76\x30\x00" + struct.pack("<HH", dots.width // 8, dots.height) + rows


def print_job(*pictures: Image.Image, darkness: int = DEFAULT_DARKNESS) -> bytes:
    """All the bytes of one print: darkness, reset, the pictures, a paper feed.

    Several pictures (black-and-white dots) are printed back to back, one picture command
    each, after one darkness + reset and before one paper feed.
    """
    if not 0 <= darkness <= 255:
        raise ValueError(f"the darkness must be between 0 and 255, got {darkness}")
    return (bytes([0x1D, 0x49, 0xF0, darkness])  # darkness. Sent before the reset, which
            + b"\x1b\x40"                        # ESC @: reset; keeps the darkness
            + b"".join(raster_command(dots) for dots in pictures)  # the pictures
            + b"\x0a" * 4)                       # 4 line feeds: push the print past the edge
