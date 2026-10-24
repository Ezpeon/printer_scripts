"""Tests for printerscript.py, the command line: run as a user would, with --preview.

They check that the options reach the right code in src/, and that mistakes give clear
messages and exit codes (2 = a wrong option, 1 = another problem). What the code itself does
is tested in the other test files, one per module of src/.

Run all the tests with tests\\run_all.py, or only these with tests\\test_printerscript.py.
"""

import re
import tempfile
from pathlib import Path

from PIL import Image

from runner import run_tests
from helpers import needs_segno, run_script, same_dots  # helpers also makes src/ importable


def test_command_line_text():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # "\n" typed as backslash + n (as in a shell) becomes a line break: 3 lines are
        # taller than 1.
        one, three = folder / "one.png", folder / "three.png"
        assert run_script("--text", "milk", "--preview", str(one)).returncode == 0
        result = run_script("--text", "Shopping:\\nmilk\\neggs", "--preview", str(three))
        assert result.returncode == 0, result.stderr
        with Image.open(one) as one_line, Image.open(three) as three_lines:
            assert three_lines.height > 2 * one_line.height
        # Characters the font can't draw: printed anyway, with a warning naming them.
        result = run_script("--text", "Hi 👋", "--preview", str(folder / "emoji.png"))
        assert result.returncode == 0 and "Font:" in result.stdout, result.stderr
        assert "can't draw 👋" in result.stderr, result.stderr
        # Mistakes give a clear message.
        for args, code, message in [
                (["--text", "  "], 2, "--text is empty"),
                (["--text", "hi", "--text_size", "3"], 2, "between 6 and 400"),
                (["--text", "hi", "--image", "x.png"], 2, "not allowed with"),
                (["--text", "hi", "--font", str(folder / "missing.ttf")], 1,
                 "Can't use the font")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == code and message in result.stderr, (args, result.stderr)


def test_command_line_text_file():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # A file gives the same dots as the same text typed with --text.
        text_file = folder / "list.txt"
        text_file.write_text("Shopping:\nmilk\neggs\n", encoding="utf-8")
        from_file, typed = folder / "from_file.png", folder / "typed.png"
        result = run_script("--text_file", str(text_file), "--preview", str(from_file))
        assert result.returncode == 0 and "Font:" in result.stdout, result.stderr
        assert run_script("--text", "Shopping:\\nmilk\\neggs",
                          "--preview", str(typed)).returncode == 0
        with Image.open(from_file) as a, Image.open(typed) as b:
            assert same_dots(a, b)
        # Mistakes give a clear message.
        old_encoding = folder / "old.txt"
        old_encoding.write_bytes("Caffè".encode("cp1252"))  # what old Windows Notepad saved
        blank = folder / "blank.txt"
        blank.write_text(" \n\n", encoding="utf-8")
        for args, code, message in [
                (["--text_file", str(folder / "missing.txt")], 1, "doesn't exist"),
                (["--text_file", str(old_encoding)], 1, "isn't a UTF-8 text file"),
                (["--text_file", str(blank)], 1, "is empty"),
                (["--text_file", str(folder)], 1, "is a folder"),
                (["--text_file", str(text_file), "--text", "hi"], 2, "not allowed with")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == code and message in result.stderr, (args, result.stderr)


def test_command_line_qr():
    needs_segno()
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        plain, captioned = folder / "qr.png", folder / "qr_caption.png"
        result = run_script("--qr", "https://example.com", "--preview", str(plain))
        assert result.returncode == 0 and "QR code:" in result.stdout, result.stderr
        result = run_script("--qr", "https://example.com", "--qr_caption",
                            "--preview", str(captioned))
        assert result.returncode == 0, result.stderr
        with Image.open(plain) as code, Image.open(captioned) as code_and_text:
            assert code.width == 384 and code_and_text.height > code.height
        for args, code, message in [
                (["--qr", " "], 2, "--qr is empty"),
                (["--text", "hi", "--qr_caption"], 2, "only works together with --qr"),
                (["--qr", "x" * 1500], 1, "too long")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == code and message in result.stderr, (args, result.stderr)


def test_command_line_sudoku():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # A new puzzle says its ID; that ID then gives its solution.
        result = run_script("--sudoku", "easy", "--preview", str(folder / "puzzle.png"))
        assert result.returncode == 0, result.stderr
        match = re.search(r"--sudoku_solution (9E-\d{5})", result.stdout)
        assert match, result.stdout
        result = run_script("--sudoku_solution", match.group(1),
                            "--preview", str(folder / "solution.png"))
        assert result.returncode == 0 and match.group(1) in result.stdout, result.stderr
        result = run_script("--sudoku6", "medium", "--preview", str(folder / "six.png"))
        assert result.returncode == 0 and "6M-" in result.stdout, result.stderr
        # Mistakes give a clear message.
        for args, message in [(["--sudoku_solution", "9X-1"], "isn't a sudoku ID"),
                              (["--sudoku", "expert"], "invalid choice")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == 2 and message in result.stderr, (args, result.stderr)


def test_command_line_self_test():
    needs_segno()
    with tempfile.TemporaryDirectory() as folder:
        preview = Path(folder) / "self_test.png"
        result = run_script("--self_test", "--preview", str(preview))
        # 3 labels and their parts, and the footer.
        assert result.returncode == 0 and "7 parts" in result.stdout, result.stderr
        with Image.open(preview) as saved:
            assert saved.width == 384 and saved.height > 1500  # about 20 cm
        for option in ("--clean_light", "--contrast"):
            result = run_script("--self_test", option, "5", "--preview", str(preview))
            assert result.returncode == 2 and "doesn't apply to --self_test" in result.stderr


def test_command_line_portrait_landscape():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        wide = folder / "wide.png"
        Image.new("L", (40, 20), 255).save(wide)
        # 40 x 20 turned to 20 x 40 is 384 x 768 dots; not turned, 384 x 192.
        for option, size in [("--portrait", (384, 768)), ("--landscape", (384, 192))]:
            preview = folder / "preview.png"
            result = run_script("--image", str(wide), option, "--preview", str(preview))
            assert result.returncode == 0, result.stderr
            with Image.open(preview) as saved:
                assert saved.size == size, option
        for args, message in [(["--test_page", "--portrait"], "only work together with --image"),
                              (["--image", str(wide), "--portrait", "--landscape"],
                               "not allowed with")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == 2 and message in result.stderr, (args, result.stderr)


def test_command_line_contrast():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # Two dark greys, 40 on top and 80 below: stretched, the top prints black and the
        # bottom white.
        dark = folder / "dark.png"
        picture = Image.new("L", (384, 100), 40)
        picture.paste(80, (0, 50, 384, 100))
        picture.save(dark)
        preview = folder / "preview.png"
        result = run_script("--image", str(dark), "--contrast", "0", "--preview", str(preview))
        assert result.returncode == 0, result.stderr
        with Image.open(preview) as saved:
            assert saved.getpixel((0, 0)) == 0 and saved.getpixel((0, 99)) == 255


def test_command_line_channel():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # Pure red is all red and no blue: all white with --channel red, all black with blue.
        red = folder / "red.png"
        Image.new("RGB", (384, 20), (255, 0, 0)).save(red)
        for channel, colour in [("red", 255), ("blue", 0)]:
            preview = folder / "preview.png"
            result = run_script("--image", str(red), "--channel", channel,
                                "--preview", str(preview))
            assert result.returncode == 0, result.stderr
            with Image.open(preview) as saved:
                assert saved.getextrema() == (colour, colour), channel
        for args, message in [(["--test_page", "--channel", "red"],
                               "only works together with --image"),
                              (["--image", str(red), "--channel", "purple"], "invalid choice")]:
            result = run_script(*args, "--preview", str(folder / "x.png"))
            assert result.returncode == 2 and message in result.stderr, (args, result.stderr)


def save_game_colours(folder: Path) -> Path:
    """test_suggest.py's picture: a pale red and a blue-grey with the same grey, between a
    black and a white stripe. Its best setting is the red channel."""
    path = folder / "colours.png"
    picture = Image.new("RGB", (384, 200), (96, 64, 64))
    picture.paste((68, 71, 85), (192, 0, 384, 200))
    picture.paste((0, 0, 0), (0, 0, 384, 20))
    picture.paste((255, 255, 255), (0, 180, 384, 200))
    picture.save(path)
    return path


def test_command_line_suggest():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        colours = save_game_colours(folder)
        # Nothing is printed or saved, and no printer is needed.
        result = run_script("--image", str(colours), "--suggest")
        assert result.returncode == 0, result.stderr
        assert "Best: --channel red," in result.stdout, result.stdout
        assert list(folder.iterdir()) == [colours]
        for args, message in [(["--test_page", "--suggest"], "only work together with --image"),
                              (["--image", str(colours), "--suggest", "--channel", "red"],
                               "leave them out"),
                              (["--image", str(colours), "--suggest", "--auto"],
                               "not allowed with"),
                              (["--image", str(colours), "--suggest", "--preview", "x.png"],
                               "use --auto --preview")]:
            result = run_script(*args)
            assert result.returncode == 2 and message in result.stderr, (args, result.stderr)


def test_command_line_auto():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        colours = save_game_colours(folder)
        # --auto says what it chose, and prints the same dots as typing it.
        auto, typed = folder / "auto.png", folder / "typed.png"
        result = run_script("--image", str(colours), "--auto", "--preview", str(auto))
        assert result.returncode == 0 and "--auto: --channel red (" in result.stdout, result
        assert run_script("--image", str(colours), "--channel", "red",
                          "--preview", str(typed)).returncode == 0
        with Image.open(auto) as a, Image.open(typed) as b:
            assert same_dots(a, b)
        result = run_script("--image", str(colours), "--auto", "--contrast", "1",
                            "--preview", str(auto))
        assert result.returncode == 2 and "leave them out" in result.stderr, result.stderr


def test_command_line_messages():
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        # No paired_devices.txt yet.
        result = run_script("--printer_name", "YHK-T201", "--test_page",
                            "--devices_file", str(folder / "missing.txt"))
        assert result.returncode == 1 and "doesn't exist yet" in result.stderr, result.stderr
        # A typo in the name.
        devices = folder / "paired_devices.txt"
        devices.write_text("YHK-T201 = AA:BB:CC:DD:EE:01\n", encoding="utf-8")
        result = run_script("--printer_name", "YHK-T210", "--test_page",
                            "--devices_file", str(devices))
        assert result.returncode == 1 and "Did you mean: YHK-T201?" in result.stderr
        # A file that isn't a picture.
        not_a_picture = folder / "notes.jpg"
        not_a_picture.write_text("hello", encoding="utf-8")
        result = run_script("--image", str(not_a_picture), "--preview", str(folder / "x.png"))
        assert result.returncode == 1 and "isn't a picture" in result.stderr, result.stderr
        # No printer name, and no devices to take the first of. (A test never relies on the
        # real paired_devices.txt: it would connect to the real printer.)
        no_devices = folder / "no_devices.txt"
        no_devices.write_text("# Paired Bluetooth devices\n", encoding="utf-8")
        result = run_script("--test_page", "--devices_file", str(no_devices))
        assert result.returncode == 1 and "has no devices" in result.stderr, result.stderr
        # A default printer that isn't in the list: the message says where the name came from.
        devices.write_text("default = YHK-T999\nYHK-T201 = AA:BB:CC:DD:EE:01\n", encoding="utf-8")
        result = run_script("--test_page", "--devices_file", str(devices))
        assert result.returncode == 1 and "is the default printer in" in result.stderr, result
        # --status has nothing to preview.
        result = run_script("--status", "--preview", str(folder / "x.png"))
        assert result.returncode == 2 and "nothing to preview" in result.stderr, result.stderr
        # --clean_light outside 0-99, --contrast outside 0-49, or not a number.
        for option, bad, message in [("--clean_light", "100", "from 0 to 99"),
                                     ("--clean_light", "abc", "expected a number"),
                                     ("--contrast", "50", "from 0 to 49"),
                                     ("--contrast", "abc", "expected a number"),
                                     ("--darkness", "0", "between 1 and 40"),
                                     ("--darkness", "41", "between 1 and 40")]:
            result = run_script("--test_page", option, bad, "--preview", str(folder / "x.png"))
            assert result.returncode == 2 and message in result.stderr, result.stderr


def test_command_line_preview():
    with tempfile.TemporaryDirectory() as folder:
        # Into a folder that doesn't exist yet, and with no .png at the end of the name.
        preview = Path(folder) / "new_folder" / "page"
        result = run_script("--test_page", "--width", "576", "--preview", str(preview))
        assert result.returncode == 0, result.stderr
        with Image.open(preview) as saved:
            assert saved.mode == "1" and saved.size == (576, 432)


if __name__ == "__main__":
    run_tests(globals())
