"""Sudoku puzzles: made up at random, each with exactly one solution that logic can reach.

Two sizes:
- 9 x 9, the classic: digits 1-9, boxes of 3 x 3 cells.
- 6 x 6, for bigger squares on narrow paper: digits 1-6, boxes of 2 rows x 3 columns.

Every puzzle has an ID like "9M-04821": the size, the difficulty (E, M or H) and a number.
The ID alone rebuilds the same puzzle, so its solution can be printed later
(--sudoku_solution 9M-04821) without saving anything.

How a puzzle is made:
1. Fill a whole grid at random, following the rules (random_full_grid).
2. Erase its digits one by one, in random order. After each erasure, a solver that works
   like a person (solve_logically) must still be able to finish the grid using only the
   techniques allowed for the difficulty. If it can't, the digit goes back.
Since the solver only makes deductions that are certain, finishing the grid proves the
solution is the only one. count_solutions() checks that again, independently, by trying
every possibility.

The grid is a list of size x size numbers, row after row, 0 = empty. Cell number
row * size + column. Example for 6 x 6: cell 7 is row 1, column 1 (counting from 0).
"""

from __future__ import annotations

import functools
import itertools
import random
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw

from .pictures import stack
from .text import load_font, make_text_picture

# size -> (box height, box width) in cells
BOX_SHAPES = {9: (3, 3), 6: (2, 3)}
DIFFICULTIES = {"E": "easy", "M": "medium", "H": "hard"}

# The solving techniques, from simplest to hardest. A level allows its own and the ones
# before it.
HIDDEN_SINGLES = 1  # a digit fits in only one cell of a row, column or box
SINGLES = 2         # also: a cell where only one digit fits
ADVANCED = 3        # also: locked candidates and naked pairs (see solve_logically)

# For each difficulty: the techniques the solver may use, and the fewest digits to leave
# in the grid for each size (0 = erase as many as possible).
# - Easy: about half the digits given, and spotting where a digit must go is enough.
# - Medium: about a third given (28 of 81, 13 of 36), and a cell where only one digit fits
#   may be needed too. Without that floor, medium erased more than hard (23 vs 25 digits
#   left, measured 2026-10-12): the simple techniques allow very sparse grids.
# - Hard: as few digits as possible, and the simple techniques must NOT be enough.
RECIPES = {
    "E": (HIDDEN_SINGLES, {9: 38, 6: 18}),
    "M": (SINGLES, {9: 28, 6: 13}),
    "H": (ADVANCED, {9: 0, 6: 0}),
}

ID_RE = re.compile(r"^([69])([EMH])-?(\d{1,5})$", re.IGNORECASE)


# ------------------------------------------------------------------------------------------
# Rows, columns and boxes
# ------------------------------------------------------------------------------------------

@functools.cache  # computed once per size, then remembered
def units(size: int) -> tuple[tuple[int, ...], ...]:
    """Every row, column and box, each as the numbers of its cells. Each must hold every
    digit once. Example for 6 x 6: the first box is (0, 1, 2, 6, 7, 8)."""
    box_height, box_width = BOX_SHAPES[size]
    rows = [tuple(row * size + column for column in range(size)) for row in range(size)]
    columns = [tuple(row * size + column for row in range(size)) for column in range(size)]
    boxes = [tuple((top + row) * size + left + column
                   for row in range(box_height) for column in range(box_width))
             for top in range(0, size, box_height) for left in range(0, size, box_width)]
    return tuple(rows + columns + boxes)


@functools.cache
def peers(size: int) -> tuple[tuple[int, ...], ...]:
    """For each cell, the other cells that share its row, column or box: none of them may
    hold the same digit. In a 9 x 9 grid every cell has 20 peers."""
    linked = [set() for _ in range(size * size)]
    for unit in units(size):
        for cell in unit:
            linked[cell].update(unit)
    return tuple(tuple(sorted(cells - {cell})) for cell, cells in enumerate(linked))


def allowed_digits(grid: list[int], size: int, cell: int) -> list[int]:
    """The digits that could go in `cell` without repeating one of its peers."""
    used = {grid[peer] for peer in peers(size)[cell]}
    return [digit for digit in range(1, size + 1) if digit not in used]


# ------------------------------------------------------------------------------------------
# Randomness that stays the same everywhere
# ------------------------------------------------------------------------------------------

def shuffle(items: list, rng: random.Random) -> None:
    """Shuffle a list in place (Fisher-Yates), using only rng.random().

    Why not random.shuffle(): Python only promises that random() gives the same numbers for
    the same seed in every version. shuffle() and randrange() have changed between versions,
    and an ID must give the same puzzle on every computer and every Python, or a solution
    printed later wouldn't match the puzzle.
    """
    for last in range(len(items) - 1, 0, -1):
        other = int(rng.random() * (last + 1))  # a position from 0 to last
        items[last], items[other] = items[other], items[last]


# ------------------------------------------------------------------------------------------
# Making and solving grids
# ------------------------------------------------------------------------------------------

def random_full_grid(size: int, rng: random.Random) -> list[int]:
    """A completely filled grid that follows the rules, made at random.

    Fills the cells in order, trying the allowed digits in random order. When a cell has no
    allowed digit left, it goes back to the previous cell and tries its next digit
    ("backtracking"). That's rare, so it takes a few milliseconds.
    """
    grid = [0] * (size * size)

    def fill(cell: int) -> bool:
        if cell == len(grid):
            return True
        digits = allowed_digits(grid, size, cell)
        shuffle(digits, rng)
        for digit in digits:
            grid[cell] = digit
            if fill(cell + 1):
                return True
        grid[cell] = 0
        return False

    fill(0)
    return grid


def count_solutions(grid: list[int], size: int, limit: int = 2) -> int:
    """How many ways there are to finish the grid, counting up to `limit`.

    Tries every possibility (backtracking), always at the empty cell with the fewest allowed
    digits, which keeps the search small. With the default limit, the answer is 0 (no
    solution), 1 (exactly one: a proper sudoku) or 2 (two or more).
    """
    grid = list(grid)

    def search() -> int:
        best_cell, best_digits = None, None
        for cell, value in enumerate(grid):
            if value == 0:
                digits = allowed_digits(grid, size, cell)
                if best_digits is None or len(digits) < len(best_digits):
                    best_cell, best_digits = cell, digits
                    if len(digits) <= 1:
                        break  # can't do better than this
        if best_cell is None:
            return 1  # no empty cell left: one solution found
        found = 0
        for digit in best_digits:
            grid[best_cell] = digit
            found += search()
            if found >= limit:
                break
        grid[best_cell] = 0
        return found

    return search()


def solve_logically(grid: list[int], size: int, level: int) -> list[int] | None:
    """Solve the grid like a person, using only the techniques up to `level`.

    Returns the finished grid, or None if those techniques get stuck. Every empty cell keeps
    a list of the digits that could still go there (its "candidates"). The techniques:
    - Hidden single (HIDDEN_SINGLES): in a row, column or box, a digit fits in only one
      cell, so it goes there.
    - Naked single (SINGLES): a cell has only one candidate left.
    - Locked candidates (ADVANCED): if a box's only cells for a digit all lie in one row,
      the digit must be in that row inside the box, so the rest of the row can't have it.
      (And the same the other way round, and for columns.)
    - Naked pair (ADVANCED): two cells of a row, column or box with the same two candidates,
      e.g. both {4, 7}: those two digits go in those two cells, so the other cells of that
      row, column or box can't have them.
    """
    cells = list(grid)
    candidates = [set() if cells[cell] else set(allowed_digits(cells, size, cell))
                  for cell in range(size * size)]

    def place(cell: int, digit: int) -> None:
        cells[cell] = digit
        candidates[cell] = set()
        for peer in peers(size)[cell]:
            candidates[peer].discard(digit)

    while 0 in cells:
        progress = False
        for unit in units(size):
            for digit in range(1, size + 1):
                spots = [cell for cell in unit if digit in candidates[cell]]
                if len(spots) == 1:
                    place(spots[0], digit)
                    progress = True
        if level >= SINGLES:
            for cell in range(size * size):
                if len(candidates[cell]) == 1:
                    place(cell, min(candidates[cell]))
                    progress = True
        if not progress and level >= ADVANCED:
            progress = locked_candidates(candidates, size) or naked_pairs(candidates, size)
        if not progress:
            return None  # stuck
    return cells


@functools.cache
def box_line_overlaps(size: int) -> tuple:
    """Each (box, row or column, the cells they share), for the pairs that share cells."""
    all_units = units(size)
    boxes, lines = all_units[2 * size:], all_units[:2 * size]
    return tuple((box, line, frozenset(box) & frozenset(line))
                 for box in boxes for line in lines if frozenset(box) & frozenset(line))


def locked_candidates(candidates: list[set], size: int) -> bool:
    """Remove the candidates ruled out by "locked candidates" (see solve_logically).
    Returns True if it removed any."""
    removed = False
    for box, line, shared in box_line_overlaps(size):
        for digit in range(1, size + 1):
            in_box = [cell for cell in box if digit in candidates[cell]]
            in_line = [cell for cell in line if digit in candidates[cell]]
            if in_box and shared.issuperset(in_box):  # the box's spots are all in the line
                for cell in in_line:
                    if cell not in shared:
                        candidates[cell].discard(digit)
                        removed = True
            if in_line and shared.issuperset(in_line):  # the line's spots are all in the box
                for cell in in_box:
                    if cell not in shared:
                        candidates[cell].discard(digit)
                        removed = True
    return removed


def naked_pairs(candidates: list[set], size: int) -> bool:
    """Remove the candidates ruled out by "naked pairs" (see solve_logically).
    Returns True if it removed any."""
    removed = False
    for unit in units(size):
        two_left = [cell for cell in unit if len(candidates[cell]) == 2]
        for first, second in itertools.combinations(two_left, 2):
            pair = candidates[first]
            if candidates[second] != pair:
                continue
            for cell in unit:
                if cell not in (first, second) and candidates[cell] & pair:
                    candidates[cell] -= pair
                    removed = True
    return removed


# ------------------------------------------------------------------------------------------
# Puzzles and their IDs
# ------------------------------------------------------------------------------------------

@dataclass
class Sudoku:
    id: str               # e.g. "9M-04821"
    size: int             # 9 or 6
    difficulty: str       # "easy", "medium" or "hard"
    puzzle: list[int]     # 0 = an empty cell to fill in
    solution: list[int]

    @property
    def givens(self) -> int:
        """How many digits the puzzle starts with."""
        return sum(1 for digit in self.puzzle if digit)


def parse_id(text: str) -> tuple[int, str, int]:
    """ "9m-4821" -> (9, "M", 4821). Raises ValueError with a message if it isn't an ID."""
    match = ID_RE.match(text.strip())
    if not match:
        raise ValueError(f'"{text}" isn\'t a sudoku ID: expected the size (9 or 6), the '
                         "difficulty (E, M or H), a dash and a number, like 9M-04821")
    return int(match.group(1)), match.group(2).upper(), int(match.group(3))


def sudoku_from_id(text: str) -> Sudoku:
    """Rebuild the sudoku with this ID: the same ID always gives the same puzzle.

    Raises ValueError if it isn't an ID. Changing anything in how puzzles are made changes
    which puzzle an ID gives, and IDs printed before would then show the wrong solution.
    The tests pin a few IDs to their puzzles to catch that.
    """
    size, letter, number = parse_id(text)
    # One seed per ID: different sizes and difficulties with the same number differ too.
    rng = random.Random(number * 100 + size * 10 + "EMH".index(letter))
    level, min_givens = RECIPES[letter]
    while True:
        solution = random_full_grid(size, rng)
        puzzle = list(solution)
        order = list(range(size * size))
        shuffle(order, rng)
        for cell in order:
            if sum(1 for digit in puzzle if digit) <= min_givens[size]:
                break
            digit, puzzle[cell] = puzzle[cell], 0
            if solve_logically(puzzle, size, level) is None:
                puzzle[cell] = digit  # without it, the techniques get stuck: put it back
        if letter == "H" and solve_logically(puzzle, size, SINGLES) is not None:
            continue  # the simple techniques are enough, so it isn't hard: next grid
        break
    # A second, independent proof that the solution is the only one (cheap, done once).
    if count_solutions(puzzle, size) != 1:
        raise AssertionError(f"{text}: the puzzle doesn't have exactly one solution")
    return Sudoku(f"{size}{letter}-{number:05d}", size, DIFFICULTIES[letter], puzzle,
                  solution)


def new_sudoku(size: int, difficulty: str) -> Sudoku:
    """A new sudoku with a random ID. `difficulty`: "easy", "medium" or "hard"."""
    letter = difficulty[0].upper()
    # Plain random, not reproducible: this only picks the number. The puzzle then comes
    # from the ID alone.
    return sudoku_from_id(f"{size}{letter}-{random.randrange(100000):05d}")


# ------------------------------------------------------------------------------------------
# Drawing
# ------------------------------------------------------------------------------------------

def grid_lines(size: int, box: int, width: int) -> list[int]:
    """The thickness of each of the size + 1 lines across the grid, in dots: thick around
    the boxes (`box` cells apart), thin inside them. At 384 dots: 4 and 2."""
    thick, thin = round(4 * width / 384), max(1, round(2 * width / 384))
    return [thick if line % box == 0 else thin for line in range(size + 1)]


def make_grid_picture(grid: list[int], size: int, width: int) -> Image.Image:
    """Draw the grid with its digits, as wide as fits in `width` dots (a greyscale picture).

    At 384 dots, each cell of a 9 x 9 grid is 37 dots (4.6 mm) wide, and 58 dots (7.3 mm)
    in a 6 x 6 grid. Like text, the digits are drawn smooth and then cut off at mid-grey,
    so they print sharp.
    """
    box_height, box_width = BOX_SHAPES[size]
    margin = round(8 * width / 384)  # 1 mm of white around the grid
    across = grid_lines(size, box_width, width)  # the lines between columns
    down = grid_lines(size, box_height, width)   # the lines between rows
    cell = (width - 2 * margin - sum(across)) // size  # only the width is limited
    grid_width = size * cell + sum(across)
    grid_height = size * cell + sum(down)
    left = (width - grid_width) // 2
    page = Image.new("L", (width, grid_height + 2 * margin), 255)
    draw = ImageDraw.Draw(page)

    def starts(lines: list[int], start: int) -> list[int]:
        """Where each line starts: a line, then a cell, then a line, and so on."""
        positions = []
        for thickness in lines:
            positions.append(start)
            start += thickness + cell
        return positions

    xs, ys = starts(across, left), starts(down, margin)
    for x, thickness in zip(xs, across):
        draw.rectangle([x, margin, x + thickness - 1, margin + grid_height - 1], fill=0)
    for y, thickness in zip(ys, down):
        draw.rectangle([left, y, left + grid_width - 1, y + thickness - 1], fill=0)

    font = load_font(round(cell * 0.7))
    for index, digit in enumerate(grid):
        if digit:
            row, column = divmod(index, size)
            # The middle of the cell: after its line, half a cell further.
            x = xs[column] + across[column] + cell / 2
            y = ys[row] + down[row] + cell / 2
            draw.text((x, y), str(digit), fill=0, font=font, anchor="mm")  # "mm" = centred
    return page.point(lambda grey: 0 if grey < 128 else 255)


def make_sudoku_picture(sudoku: Sudoku, width: int, solution: bool = False) -> Image.Image:
    """The puzzle (or its solution) with a title, ready to print (a greyscale picture).

    The puzzle says how to get its solution later; the solution says which puzzle it's for.
    """
    # 3 mm letters. Each text fits on one line at 384 dots (measured), so that a line break
    # never separates the option from the ID.
    font = load_font(round(24 * width / 384))
    if solution:
        title = f"Solution of {sudoku.id} ({sudoku.difficulty})"
        return stack(make_text_picture(title, width, font),
                     make_grid_picture(sudoku.solution, sudoku.size, width))
    title = f"Sudoku {sudoku.id} ({sudoku.difficulty})"
    footer = f"For the solution, print:\n--sudoku_solution {sudoku.id}"
    return stack(make_text_picture(title, width, font),
                 make_grid_picture(sudoku.puzzle, sudoku.size, width),
                 make_text_picture(footer, width, font))
