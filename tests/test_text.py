"""Tests for src/text.py: text drawn as a picture, fonts, and text files.

Run all the tests with tests\\run_all.py, or only these with tests\\test_text.py.
"""

import tempfile
from pathlib import Path

from PIL import Image, ImageFont

from runner import Skip, run_tests
from helpers import same_dots  # helpers also makes src/ importable
from src import pictures, text


def test_wrap_text():
    font = text.load_font(32)
    width = 368
    assert text.wrap_text("Hello", font, width) == ["Hello"]
    assert text.wrap_text("a\n\nb", font, width) == ["a", "", "b"]  # an empty line stays
    sentence = "The quick brown fox jumps over the lazy dog. " * 4
    lines = text.wrap_text(sentence, font, width)
    assert len(lines) > 1
    assert all(font.getlength(line) <= width for line in lines)
    assert " ".join(lines) == sentence.strip()  # no word lost, changed or reordered
    # A word longer than a whole line is cut into pieces that each fit, losing nothing.
    address = "https://example.com/" + "x" * 80
    pieces = text.wrap_text(address, font, width)
    assert len(pieces) > 1 and "".join(pieces) == address
    assert all(font.getlength(piece) <= width for piece in pieces)


def test_text_picture_is_crisp():
    picture = text.make_text_picture("Hello", 384)
    assert picture.mode == "L" and picture.width == 384
    counts = picture.histogram()  # how many pixels have each grey value, 0 to 255
    assert counts[0] > 0, "no black letters"
    assert not any(counts[1:255]), "grey pixels left: the edges weren't cut off"
    # So dithering has nothing to do: the dots are exactly the black pixels.
    plain_cut = picture.convert("1", dither=Image.Dither.NONE)
    assert same_dots(pictures.prepare_picture(picture, 384), plain_cut)


def test_text_picture_grows_with_lines_and_size():
    one_line = text.make_text_picture("Hello", 384)
    two_lines = text.make_text_picture("Hello\nworld", 384)
    big = text.make_text_picture("Hello", 384, text.load_font(64))
    assert two_lines.height > one_line.height
    assert big.height > one_line.height


def test_text_with_a_font_file():
    candidates = [Path("C:/Windows/Fonts/arial.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    font_file = next((path for path in candidates if path.exists()), None)
    if font_file is None:
        raise Skip("no known font file on this computer")
    picture = text.make_text_picture("Hello", 384, text.load_font(32, font_file))
    assert picture.histogram()[0] > 0  # black letters


def test_missing_characters():
    """Pillow's built-in font has only basic English letters (seen 2026-10-12)."""
    built_in = ImageFont.load_default(size=32)
    assert text.font_name(built_in) == "Pillow's built-in font"
    assert text.missing_characters("Caffè 👋 ok", built_in) == ["è", "👋"]
    assert text.missing_characters("plain text", built_in) == []


def test_default_font_has_accents():
    """The default font for --text is a system font with accents, when there is one."""
    if not any(path.exists() for path in text.SYSTEM_FONTS):
        raise Skip("none of SYSTEM_FONTS is on this computer")
    font = text.load_font(32)
    assert text.font_name(font) != "Pillow's built-in font"
    assert text.missing_characters("Caffè, perché, Größe, España, Øresund, 5 €", font) == []


def test_read_text_file():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "notes.txt"
        # As a Windows program may save it: a BOM at the start, "\r\n" line ends and a line
        # break at the end. And a backslash + n that must stay as typed.
        path.write_bytes("Caffè:\r\nmilk\r\nC:\\notes\\new\r\n".encode("utf-8-sig"))
        assert text.read_text_file(path) == "Caffè:\nmilk\nC:\\notes\\new"


if __name__ == "__main__":
    run_tests(globals())
