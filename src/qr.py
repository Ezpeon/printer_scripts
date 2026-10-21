"""QR codes: a text (e.g. a web address) as a QR code picture, for a phone to scan."""

from __future__ import annotations

from PIL import Image, ImageDraw

# QR codes need a white border ("quiet zone") 4 squares wide around them, and squares of at
# least about 3 dots (0.4 mm), or phone cameras struggle to read them.
QR_BORDER = 4
MIN_DOTS_PER_SQUARE = 3


def qr_matrix(text: str) -> tuple:
    """The QR code for `text`, as rows of squares: 1 = black, 0 = white (without the border).

    The encoding (error correction, masks, ...) is done by the segno library. It's imported
    here, not at the top, so the rest of the code works without it. Raises
    ModuleNotFoundError if segno isn't installed.
    """
    import segno

    # make_qr(), not make(): for short texts make() picks the smaller "Micro QR" format,
    # which phone cameras often can't read. error="m": up to 15 % of the code can be
    # damaged (a smudge, a crease) and it still scans.
    return segno.make_qr(text, error="m").matrix


def qr_dots_per_square(matrix: tuple, width: int) -> int:
    """How many dots each square of the QR code gets, so that it fits in `width` dots.

    Example: a typical web address needs 29 x 29 squares, plus the white border of 4
    squares on each side that scanners need = 37 squares. 384 // 37 = 10 dots per square,
    so the code is 37 x 10 = 370 dots (4.6 cm) wide.
    """
    return width // (len(matrix) + 2 * QR_BORDER)


def make_qr_picture(text: str, width: int) -> Image.Image:
    """A QR code for `text`, as big as fits in `width` dots (a greyscale picture).

    Each square becomes a block of whole dots: no resizing and no dithering, so the edges
    stay perfectly sharp, which is what scanners need. Raises ValueError if the text is too
    long for a code that can still be scanned at this width.
    """
    matrix = qr_matrix(text)
    squares = len(matrix) + 2 * QR_BORDER
    dots = qr_dots_per_square(matrix, width)
    if dots < MIN_DOTS_PER_SQUARE:
        raise ValueError(
            f"The text is too long for a QR code that can be scanned: it needs "
            f"{squares} x {squares} squares, so at {width} dots each square would get only "
            f"{dots} dot(s) (at least {MIN_DOTS_PER_SQUARE} are needed). Use a shorter text, "
            "e.g. a shorter link.")
    page = Image.new("L", (width, squares * dots), 255)
    draw = ImageDraw.Draw(page)
    left = (width - squares * dots) // 2 + QR_BORDER * dots  # centred, after the border
    top = QR_BORDER * dots
    for row, squares_in_row in enumerate(matrix):
        for column, black in enumerate(squares_in_row):
            if black:
                x, y = left + column * dots, top + row * dots
                draw.rectangle([x, y, x + dots - 1, y + dots - 1], fill=0)
    return page
