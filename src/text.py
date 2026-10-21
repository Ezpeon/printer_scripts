"""Text: typed or from a file, drawn as a picture, since the printer only prints pictures."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Default letter size for --text, in dots: 32 dots = 4 mm on a 384-dot printer (8 dots per mm).
DEFAULT_TEXT_SIZE = 32
# Fonts that come with the system, tried in this order for --text when --font isn't given.
# They all have accented letters (è, é, ß, ...). Pillow's built-in font, the last resort,
# has only basic English letters (checked 2026-10-12): "Caffè" printed as "Caff" + a box.
SYSTEM_FONTS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",  # Windows
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),      # Debian, Ubuntu
    Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),    # Fedora
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),                  # Arch
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]


def load_font(size: int, font_file: Path | None = None) -> ImageFont.FreeTypeFont:
    """The font to draw text with, `size` dots tall.

    With a font file (any TrueType/OpenType file), that one. Raises OSError if it can't be
    read as a font. Without one, the first font of SYSTEM_FONTS this computer has, and only
    if there's none, Pillow's built-in font.
    """
    if font_file is not None:
        return ImageFont.truetype(str(font_file), size)
    for candidate in SYSTEM_FONTS:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue  # damaged or not really a font: try the next one
    return ImageFont.load_default(size=size)


def font_name(font: ImageFont.FreeTypeFont) -> str:
    """The font's file name, e.g. "arial.ttf", or "Pillow's built-in font"."""
    path = getattr(font, "path", None)
    return Path(path).name if isinstance(path, (str, Path)) else "Pillow's built-in font"


def missing_characters(text: str, font: ImageFont.FreeTypeFont) -> list[str]:
    """The characters of `text` that `font` can't draw, each listed once.

    Pillow can't ask a font directly whether it has a letter. But a font draws every letter
    it lacks as the same "missing" box. So a letter drawn exactly like a character that no
    font has (a private-use one) is missing. Spaces are skipped: they draw nothing anyway.
    Example with Pillow's built-in font: "Caffè 👋" -> ["è", "👋"].
    """
    def drawing(character: str) -> tuple:
        mask = font.getmask(character)  # the character's black-and-white shape
        return mask.size, bytes(mask)

    missing_box = drawing("\U0010fffd")
    return [character for character in dict.fromkeys(text)  # dict: unique, in order
            if not character.isspace() and drawing(character) == missing_box]


def wrap_text(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Split `text` into lines that fit in `width` dots, breaking between words.

    A line break in the text ("\\n") always starts a new line, and an empty line stays
    empty. A word too long for a whole line (e.g. a long web address) is cut into pieces.
    Example, if about 10 letters fit: "Buy milk and eggs\\nthanks" -> ["Buy milk", "and eggs",
    "thanks"].
    """
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if font.getlength(candidate) <= width:  # getlength(): the text's width in dots
                line = candidate
                continue
            if line:
                lines.append(line)
            # The word doesn't fit on a line of its own either: cut off pieces that do.
            while font.getlength(word) > width:
                cut = len(word) - 1
                while cut > 1 and font.getlength(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return lines


def make_text_picture(text: str, width: int,
                      font: ImageFont.FreeTypeFont | None = None) -> Image.Image:
    """Draw `text` as black letters on white, `width` dots wide (a greyscale picture).

    `font` comes from load_font(); without one, the default font at the default size.
    The picture is as tall as the text needs, so a long text makes a long print. The letters
    are drawn smooth (with grey edges) and then cut off at mid-grey into pure black and
    white. Dithering those grey edges would make them fuzzy; the cut-off keeps the curves
    smooth and the edges sharp.
    """
    if font is None:
        font = load_font(DEFAULT_TEXT_SIZE)
    margin = round(8 * width / 384)  # 1 mm of white on each side, at 8 dots per mm
    lines = wrap_text(text, font, width - 2 * margin)
    # getmetrics(): how far letters go above the line (ascent) and below it (descent, like
    # the tail of a "g"). One line takes both, plus a small gap to the next line.
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + round(font.size * 0.15)
    page = Image.new("L", (width, 2 * margin + len(lines) * line_height), 255)
    draw = ImageDraw.Draw(page)
    for number, line in enumerate(lines):
        draw.text((margin, margin + number * line_height), line, fill=0, font=font)
    return page.point(lambda grey: 0 if grey < 128 else 255)


def read_text_file(path: Path) -> str:
    """The text of a text file, for --text_file.

    The file is read as UTF-8, the usual encoding today, which has every accent and alphabet.
    "utf-8-sig" also drops the invisible mark (a "BOM") that some Windows programs put at the
    start of UTF-8 files, so it isn't taken for a character. Line breaks come out as "\\n"
    whatever wrote the file (Windows ends lines with "\\r\\n").
    The spaces and line breaks at the very end are removed: most files end with a line break,
    which would otherwise print as an empty line, wasting paper.
    Unlike --text, a backslash followed by "n" stays as it is, since the file has real line
    breaks: "C:\\notes\\new" prints as typed.
    Raises OSError if the file can't be read, UnicodeDecodeError if it isn't UTF-8.
    """
    return path.read_text(encoding="utf-8-sig").rstrip()
