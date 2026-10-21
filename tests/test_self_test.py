"""Tests for src/self_test.py: the parts of the self-test print.

Skipped if segno isn't installed.

Run all the tests with tests\\run_all.py, or only these with tests\\test_self_test.py.
"""

from runner import run_tests
from helpers import needs_segno, same_dots  # helpers also makes src/ importable
from src import pictures, qr, self_test, sudoku


def test_self_test_parts():
    needs_segno()
    parts = self_test.self_test_parts(384)
    # label + QR code, label + sudoku, label + test page; the footer.
    assert len(parts) == 7
    assert all(part.mode == "1" and part.width == 384 for part in parts)
    qr_code = pictures.prepare_picture(qr.make_qr_picture(self_test.SELF_TEST_QR, 384), 384)
    assert same_dots(parts[1], qr_code)
    made = sudoku.sudoku_from_id(self_test.SELF_TEST_SUDOKU)
    puzzle = pictures.prepare_picture(sudoku.make_sudoku_picture(made, 384), 384)
    assert same_dots(parts[3], puzzle)
    test_page = pictures.prepare_picture(pictures.make_test_page(384), 384)
    assert same_dots(parts[5], test_page)


if __name__ == "__main__":
    run_tests(globals())
