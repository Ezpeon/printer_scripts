"""Tests for src/qr.py: QR code pictures. Skipped if segno isn't installed.

Run all the tests with tests\\run_all.py, or only these with tests\\test_qr.py.
"""

from PIL import Image

from runner import run_tests
from helpers import needs_segno, same_dots  # helpers also makes src/ importable
from src import pictures, qr


def test_qr_picture_matches_the_qr_code():
    """Every square of segno's code is a solid block of dots of the right colour, inside a
    white border, and no pixel is grey. So the picture is exactly the code, sharp."""
    needs_segno()
    text = "https://example.com/some/page"
    matrix = qr.qr_matrix(text)
    size = len(matrix)
    dots = qr.qr_dots_per_square(matrix, 384)
    squares = size + 2 * qr.QR_BORDER
    picture = qr.make_qr_picture(text, 384)
    assert picture.size == (384, squares * dots)
    assert not any(picture.histogram()[1:255]), "grey pixels: the squares aren't sharp"
    left = (384 - squares * dots) // 2 + qr.QR_BORDER * dots
    top = qr.QR_BORDER * dots
    for row in range(size):
        for column in range(size):
            block = picture.crop((left + column * dots, top + row * dots,
                                  left + (column + 1) * dots, top + (row + 1) * dots))
            colour = 0 if matrix[row][column] else 255
            assert block.getextrema() == (colour, colour), (row, column)
    # Everything around the code is white: the strips above, below, left and right of it.
    right, bottom = left + size * dots, top + size * dots
    for strip in [(0, 0, 384, top), (0, bottom, 384, picture.height),
                  (0, 0, left, picture.height), (right, 0, 384, picture.height)]:
        assert picture.crop(strip).getextrema() == (255, 255), strip
    # Dithering has nothing to change: the dots are exactly the black pixels.
    plain_cut = picture.convert("1", dither=Image.Dither.NONE)
    assert same_dots(pictures.prepare_picture(picture, 384), plain_cut)


def test_qr_docstring_example():
    """qr_dots_per_square()'s example: a 29-character link -> 29 x 29 squares -> 10 dots."""
    needs_segno()
    matrix = qr.qr_matrix("https://example.com/some/page")  # 29 characters
    assert len(matrix) == 29
    assert qr.qr_dots_per_square(matrix, 384) == 10


def test_qr_short_text_is_a_normal_qr_code():
    """A short text mustn't become a "Micro QR" code (17 x 17 squares or fewer), which phone
    cameras often can't read. The smallest normal QR code has 21 x 21 squares."""
    needs_segno()
    assert len(qr.qr_matrix("hi")) >= 21


def test_qr_too_long():
    needs_segno()
    try:
        qr.make_qr_picture("x" * 1500, 384)
    except ValueError as error:
        assert "too long" in str(error), error
    else:
        raise AssertionError("no error for a text too long to scan")


if __name__ == "__main__":
    run_tests(globals())
