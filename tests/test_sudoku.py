"""Tests for src/sudoku.py: making, solving and drawing sudokus.

Run all the tests with tests\\run_all.py, or only these with tests\\test_sudoku.py.
"""

import random

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import sudoku

# Puzzles pinned to their IDs (0 = empty, row after row), written down on 2026-10-12. If
# one of these tests fails, the way puzzles are made has changed, so IDs printed before
# would now give a different puzzle and a wrong solution. Change the code back, unless
# breaking old IDs is OK.
PINNED = {
    "9M-00001": "000760050000100600890052001100040007000900000"
                "450020030000280014043000200201600000",
    "9E-00002": "900200500040000002603081407204006058100300940"
                "060470200070054620490730805002800300",
    "6H-00001": "050000003100000000040200030005002300",
}


def follows_the_rules(grid: list[int], size: int) -> bool:
    """True if the grid is full and every row, column and box has each digit once."""
    return all(sorted(grid[cell] for cell in unit) == list(range(1, size + 1))
               for unit in sudoku.units(size))


# --- rows, columns and boxes; randomness ----------------------------------------------------

def test_units_and_peers():
    for size, units, peers in [(9, 27, 20), (6, 18, 12)]:
        assert len(sudoku.units(size)) == units
        assert all(len(unit) == size for unit in sudoku.units(size))
        assert all(len(cell_peers) == peers for cell_peers in sudoku.peers(size))
    assert sudoku.units(6)[12] == (0, 1, 2, 6, 7, 8)  # the docstring's example: first box


def test_shuffle_is_the_same_everywhere():
    """Pinned: Python promises random() gives the same numbers for a seed in every version."""
    items = list(range(10))
    sudoku.shuffle(items, random.Random(1))
    assert items == [8, 0, 3, 4, 5, 2, 9, 6, 7, 1]


# --- making and solving grids ---------------------------------------------------------------

def test_random_full_grid_follows_the_rules():
    for size in (9, 6):
        for seed in range(5):
            assert follows_the_rules(sudoku.random_full_grid(size, random.Random(seed)), size)


def test_count_solutions():
    full = sudoku.random_full_grid(9, random.Random(0))
    assert sudoku.count_solutions(full, 9) == 1
    assert sudoku.count_solutions([0] * 81, 9) == 2  # empty: many, counting stops at 2
    # No solution: row 0 already has 2-9, and the 1 is taken by the cell below cell 0.
    stuck = [0] * 81
    stuck[1:9] = range(2, 10)
    stuck[9] = 1
    assert sudoku.count_solutions(stuck, 9) == 0


def test_naked_pair():
    """Cells 0 and 1 can only be 1 or 2, so cell 2 (same row and box) can't be 1 or 2."""
    candidates = [set() for _ in range(36)]
    candidates[0], candidates[1], candidates[2] = {1, 2}, {1, 2}, {1, 2, 3}
    candidates[3] = {3, 4}
    assert sudoku.naked_pairs(candidates, 6)
    assert candidates[2] == {3} and candidates[3] == {3, 4}


def test_locked_candidates():
    """In the first box, 5 can only go in row 0 (cells 0 or 1), so cell 5, further along
    row 0, can't be 5."""
    candidates = [set() for _ in range(81)]
    candidates[0], candidates[1], candidates[5] = {5, 7}, {5, 8}, {5, 6}
    assert sudoku.locked_candidates(candidates, 9)
    assert candidates[5] == {6}


# --- puzzles and IDs ------------------------------------------------------------------------

def test_ids():
    assert sudoku.parse_id(" 9m-4821 ") == (9, "M", 4821)
    assert sudoku.parse_id("6H00001") == (6, "H", 1)
    for bad in ["9X-1", "7E-1", "9E", "9E-123456", ""]:
        try:
            sudoku.parse_id(bad)
        except ValueError as error:
            assert "isn't a sudoku ID" in str(error)
        else:
            raise AssertionError(f"no error for {bad!r}")
    assert sudoku.sudoku_from_id("9m-4821").id == "9M-04821"


def test_same_id_same_sudoku():
    first, again = sudoku.sudoku_from_id("9H-00007"), sudoku.sudoku_from_id("9H-00007")
    assert first.puzzle == again.puzzle and first.solution == again.solution
    # The same number at another difficulty is another puzzle.
    assert sudoku.sudoku_from_id("9E-00007").solution != first.solution


def test_pinned_ids():
    for puzzle_id, digits in PINNED.items():
        assert "".join(map(str, sudoku.sudoku_from_id(puzzle_id).puzzle)) == digits, puzzle_id


def test_every_kind_is_a_proper_sudoku():
    """For each size and difficulty, a few puzzles: exactly one solution (proved by trying
    everything), reachable with the difficulty's techniques, and only with them for hard."""
    for size in (9, 6):
        for letter in "EMH":
            level, min_givens = sudoku.RECIPES[letter]
            for number in range(1, 4):
                made = sudoku.sudoku_from_id(f"{size}{letter}-{number}")
                assert follows_the_rules(made.solution, size)
                assert all(given in (0, solved)
                           for given, solved in zip(made.puzzle, made.solution))
                assert sudoku.count_solutions(made.puzzle, size) == 1, made.id
                assert sudoku.solve_logically(made.puzzle, size, level) == made.solution
                if letter == "E":
                    assert made.givens == min_givens[size], made.id
                elif letter == "M":
                    assert made.givens >= min_givens[size], made.id
                else:  # hard: the simple techniques get stuck
                    assert sudoku.solve_logically(made.puzzle, size, sudoku.SINGLES) is None


def test_new_sudoku():
    made = sudoku.new_sudoku(6, "easy")
    assert made.id.startswith("6E-") and made.difficulty == "easy"
    assert sudoku.sudoku_from_id(made.id).puzzle == made.puzzle


# --- drawing --------------------------------------------------------------------------------

def black(picture) -> int:
    return picture.histogram()[0]  # how many pixels are black


def test_grid_picture():
    made = sudoku.sudoku_from_id("9M-00001")
    for width in (384, 576):
        empty = sudoku.make_grid_picture([0] * 81, 9, width)
        puzzle = sudoku.make_grid_picture(made.puzzle, 9, width)
        solution = sudoku.make_grid_picture(made.solution, 9, width)
        for picture in (empty, puzzle, solution):
            assert picture.width == width and picture.mode == "L"
            assert not any(picture.histogram()[1:255]), "grey pixels: not sharp"
        # The same lines, plus more black for each digit.
        assert black(empty) < black(puzzle) < black(solution)
        # Square cells: the grid is about as tall as it is wide.
        assert abs(empty.height - empty.width) < width // 20


def test_sudoku_picture():
    made = sudoku.sudoku_from_id("6E-00001")
    puzzle = sudoku.make_sudoku_picture(made, 384)
    solution = sudoku.make_sudoku_picture(made, 384, solution=True)
    assert puzzle.width == solution.width == 384
    assert puzzle.height > solution.height  # the puzzle has the two-line footer


if __name__ == "__main__":
    run_tests(globals())
