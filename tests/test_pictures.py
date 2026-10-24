"""Tests for src/pictures.py: from a jpg/png to black-and-white dots, and the test page.

The tests make their own pictures.

Run all the tests with tests\\run_all.py, or only these with tests\\test_pictures.py.
"""

import tempfile
from pathlib import Path

from PIL import Image

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import escpos, pictures


def black_share(dots: Image.Image) -> float:
    """How much of a black-and-white picture is black, from 0.0 to 1.0.

    histogram() counts the pixels of each value: [0] is the number of black ones.
    """
    return dots.histogram()[0] / (dots.width * dots.height)


# --- preparing the picture -------------------------------------------------------------------

def test_fit_to_width_keeps_proportions():
    assert pictures.fit_to_width(Image.new("L", (1000, 500)), 384).size == (384, 192)
    assert pictures.fit_to_width(Image.new("L", (100, 300)), 576).size == (576, 1728)


def test_turn_to():
    """--portrait turns only wide pictures, --landscape only tall ones, neither a square."""
    wide, tall, square = Image.new("L", (40, 20)), Image.new("L", (20, 40)), Image.new("L", (9, 9))
    assert pictures.turn_to(wide, "portrait").size == (20, 40)
    assert pictures.turn_to(tall, "portrait").size == (20, 40)
    assert pictures.turn_to(tall, "landscape").size == (40, 20)
    assert pictures.turn_to(wide, "landscape").size == (40, 20)
    for shape in ("portrait", "landscape"):
        assert pictures.turn_to(square, shape).size == (9, 9)
    # Clockwise: the top-left corner ends up top right.
    wide = Image.new("L", (40, 20), 255)
    wide.putpixel((0, 0), 0)
    assert pictures.turn_to(wide, "portrait").getpixel((19, 0)) == 0


def test_dithering_makes_grey_from_dots():
    """White stays white, black stays black, and mid-grey becomes about half black dots."""
    assert black_share(pictures.prepare_picture(Image.new("L", (384, 50), 255), 384)) == 0.0
    assert black_share(pictures.prepare_picture(Image.new("L", (384, 50), 0), 384)) == 1.0
    grey = black_share(pictures.prepare_picture(Image.new("L", (384, 50), 128), 384))
    assert 0.4 < grey < 0.6, grey


def test_transparent_png_prints_white():
    """Without putting it on white first, a transparent area could come out black."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "transparent.png"
        Image.new("RGBA", (16, 8), (0, 0, 0, 0)).save(path)  # black, but fully transparent
        # getextrema() gives (darkest, lightest) pixel: (255, 255) means everything is white.
        assert pictures.open_picture(path).getextrema() == (255, 255)
        assert pictures.open_picture(path, "red").getextrema() == (255, 255)  # also with --channel


def test_channel_separates_colours_of_the_same_brightness():
    """open_picture()'s example: a pale red and a blue-grey from a game screenshot get almost
    the same grey in the usual mix, but clearly different ones in the red channel."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "two_colours.png"
        colours = Image.new("RGB", (2, 1))
        colours.putpixel((0, 0), (96, 64, 64))
        colours.putpixel((1, 0), (68, 71, 85))
        colours.save(path)
        assert list(pictures.open_picture(path).tobytes()) == [74, 72]
        assert list(pictures.open_picture(path, "red").tobytes()) == [96, 68]
        assert list(pictures.open_picture(path, "green").tobytes()) == [64, 71]
        assert list(pictures.open_picture(path, "blue").tobytes()) == [64, 85]


def test_16_bit_png_keeps_its_greys():
    """A 16-bit grey PNG used to print white: Pillow cut its values off instead of scaling."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "grey16.png"
        greys = Image.new("I;16", (3, 1))
        for x, grey in enumerate((0, 128, 255)):
            greys.putpixel((x, 0), grey * 257)  # the 16-bit version of 0, 128 and 255
        greys.save(path)
        assert list(pictures.open_picture(path).tobytes()) == [0, 128, 255]
        # A grey picture has the same value in every channel.
        assert list(pictures.open_picture(path, "blue").tobytes()) == [0, 128, 255]


def test_sideways_phone_photo_is_turned():
    """A photo stored sideways with an EXIF note "turn 90 degrees" comes out turned."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "sideways.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6  # the EXIF "Orientation" tag; 6 = turn 90 degrees clockwise
        Image.new("RGB", (40, 20), "white").save(path, exif=exif.tobytes())
        assert pictures.open_picture(path).size == (20, 40)


# --- cleaning light greys (--clean_light) ------------------------------------------------------

def test_clean_light_values():
    """The example in clean_light()'s docstring: with 10 %, 128 -> 142, 200 -> 222, 235 -> 255."""
    greys = Image.frombytes("L", (5, 1), bytes([0, 128, 200, 235, 255]))
    assert list(pictures.clean_light(greys, 10).tobytes()) == [0, 142, 222, 255, 255]
    assert pictures.clean_light(greys, 0).tobytes() == greys.tobytes()  # 0 = off: no change


def test_clean_light_keeps_dark_darker():
    """A darker grey never ends up lighter than a lighter one: shading keeps its order."""
    all_greys = Image.frombytes("L", (256, 1), bytes(range(256)))
    for percent in (1, 5, 10, 30, 99):
        values = list(pictures.clean_light(all_greys, percent).tobytes())
        assert values == sorted(values), percent


def test_clean_light_refuses_bad_values():
    for bad in (-1, 100, 150):
        try:
            pictures.clean_light(Image.new("L", (1, 1)), bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no error for {bad}")


def test_clean_light_removes_background_speckle():
    """A flat grey-235 background (like a drawing's) prints as scattered dots unless cleaned."""
    background = Image.new("L", (384, 100), 235)
    assert black_share(pictures.prepare_picture(background, 384)) > 0.03
    assert black_share(pictures.prepare_picture(background, 384, 10)) == 0.0


# --- stretching the contrast (--contrast) ----------------------------------------------------

def test_stretch_contrast_values():
    """The example in stretch_contrast()'s docstring: greys 30-115 spread over 0-255."""
    greys = Image.frombytes("L", (3, 1), bytes([30, 72, 115]))
    assert list(pictures.stretch_contrast(greys, 0).tobytes()) == [0, 126, 255]


def test_stretch_contrast_cuts_off_the_ends():
    """One black and one white pixel stop the stretch at 0 %, but not at 1 %.

    200 pixels: one black, 99 of grey 40, 99 of grey 80, one white. 1 % is 2 pixels at each
    end: the black one and a 40 at the dark end, the white one and an 80 at the light end. So
    the stretch goes from 40 (-> black) to 80 (-> white).
    """
    picture = Image.frombytes("L", (200, 1), bytes([0] + [40] * 99 + [80] * 99 + [255]))
    # At 0 %, the greys already go from 0 to 255: nothing changes.
    assert pictures.stretch_contrast(picture, 0).tobytes() == picture.tobytes()
    assert list(pictures.stretch_contrast(picture, 1).tobytes()) == [0] * 100 + [255] * 100


def test_stretch_contrast_refuses_bad_values():
    for bad in (-1, 50, 60):
        try:
            pictures.stretch_contrast(Image.new("L", (1, 1)), bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no error for {bad}")


def test_contrast_separates_dark_greys():
    """Greys 40 and 80 both print as mostly black dots; stretched, one half is black and the
    other white. Without the option, prepare_picture() leaves the greys alone."""
    dark = Image.new("L", (384, 100), 40)
    dark.paste(80, (0, 50, 384, 100))
    assert black_share(pictures.prepare_picture(dark, 384)) > 0.7
    assert black_share(pictures.prepare_picture(dark, 384, contrast=0)) == 0.5


# --- the test page ---------------------------------------------------------------------------

def test_test_page():
    for width in escpos.HEAD_WIDTHS:
        page = pictures.make_test_page(width)
        height = width * 3 // 4
        assert page.size == (width, height) and page.mode == "L"
        # The frame reaches all four corners.
        for corner in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
            assert page.getpixel(corner) == 0, (width, corner)
        # "TOP LEFT" is written in the top-left area, inside the frame.
        scale = width / 384
        text_area = page.crop((round(8 * scale), round(8 * scale),
                               round(130 * scale), round(36 * scale)))
        assert text_area.getextrema()[0] == 0, width  # its darkest pixel is black
        # The arrow points right: its tip is near the right, not near the left.
        middle = round(height * 0.38)
        assert page.getpixel((round(width * 0.85) - 2, middle)) == 0
        assert page.getpixel((round(width * 0.15) - 3, middle)) == 255
        # The ramp has real greys (not only black and white) before dithering...
        ramp_row = round(height * 0.70)
        greys = {page.getpixel((x, ramp_row)) for x in range(width)}
        assert any(0 < grey < 255 for grey in greys), width
        # ...and the prepared dots are the right width.
        assert pictures.prepare_picture(page, width).width == width


if __name__ == "__main__":
    run_tests(globals())
