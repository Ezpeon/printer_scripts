"""Tests for src/escpos.py: the bytes sent to the printer.

The most important one is the round trip: decode_raster() below turns the bytes we would
send back into a picture, and that picture must be identical, dot for dot, to the preview.
decode_raster() is written straight from the format (see raster_command() in src/escpos.py),
without using the project's code, so the two check each other.

Run all the tests with tests\\run_all.py, or only these with tests\\test_escpos.py.
"""

from PIL import Image, ImageDraw

from runner import run_tests
from helpers import same_dots  # helpers also makes src/ importable
from src import escpos, pictures


def decode_raster(command: bytes) -> Image.Image:
    """Turn a "GS v 0" command back into a black-and-white picture."""
    assert command[:4] == bytes.fromhex("1D 76 30 00"), command[:8].hex(" ")
    bytes_per_row = command[4] + 256 * command[5]
    rows = command[6] + 256 * command[7]
    data = command[8:]
    assert len(data) == bytes_per_row * rows, "the size in the header doesn't match the data"
    picture = Image.new("1", (bytes_per_row * 8, rows), 255)  # all white to start with
    dots = picture.load()
    for y in range(rows):
        for column in range(bytes_per_row):
            byte = data[y * bytes_per_row + column]
            for bit in range(8):                  # bit 0 = the highest bit = the leftmost dot
                if byte & (0x80 >> bit):          # 1 = black
                    dots[column * 8 + bit, y] = 0
    return picture


def generated_picture() -> Image.Image:
    """A made-up greyscale picture: a top-to-bottom gradient, a black disc and a white bar."""
    picture = Image.linear_gradient("L").resize((300, 200))
    draw = ImageDraw.Draw(picture)
    draw.ellipse([40, 40, 140, 140], fill=0)
    draw.rectangle([180, 20, 280, 60], fill=255)
    return picture


# --- the GS v 0 command --------------------------------------------------------------------

def test_bit_order_example():
    """The row ■□□□■■□■ (■ = black) is the byte 0x8D."""
    dots = Image.new("1", (8, 1), 255)
    for x in (0, 4, 5, 7):
        dots.putpixel((x, 0), 0)
    assert escpos.raster_command(dots) == bytes.fromhex("1D 76 30 00 01 00 01 00 8D")


def test_header_example():
    """raster_command()'s example: 384 x 200 -> 1D 76 30 00 30 00 C8 00, then 9600 bytes."""
    command = escpos.raster_command(Image.new("1", (384, 200), 255))
    assert command[:8] == bytes.fromhex("1D 76 30 00 30 00 C8 00")
    assert len(command) == 8 + 9600
    assert set(command[8:]) == {0}  # all white = no dot heated


def test_round_trip_generated_picture():
    for width in escpos.HEAD_WIDTHS:
        dots = pictures.prepare_picture(generated_picture(), width)
        assert same_dots(decode_raster(escpos.raster_command(dots)), dots)


def test_raster_refuses_wrong_pictures():
    for bad, why in [(Image.new("L", (8, 1)), "greyscale instead of black-and-white"),
                     (Image.new("1", (10, 1)), "width not a multiple of 8"),
                     (Image.new("1", (8, escpos.MAX_ROWS + 1)), "too tall")]:
        try:
            escpos.raster_command(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no error for a picture that is {why}")


# --- the whole print job ---------------------------------------------------------------------

def test_print_job_order():
    """Darkness, reset, picture, 4 line feeds, in that order."""
    dots = Image.new("1", (8, 1), 255)
    expected = (bytes.fromhex("1D 49 F0 0F") + bytes.fromhex("1B 40")
                + escpos.raster_command(dots) + bytes.fromhex("0A 0A 0A 0A"))
    assert escpos.print_job(dots) == expected
    assert escpos.print_job(dots, darkness=18)[3] == 18
    try:
        escpos.print_job(dots, darkness=256)
    except ValueError:
        pass
    else:
        raise AssertionError("no error for darkness 256")


def test_print_job_several_pictures():
    """Several pictures: one darkness + reset, their picture commands back to back, one feed."""
    first, second = Image.new("1", (8, 1), 255), Image.new("1", (8, 2), 0)
    assert escpos.print_job(first, second) == (
        bytes.fromhex("1D 49 F0 0F 1B 40") + escpos.raster_command(first)
        + escpos.raster_command(second) + bytes.fromhex("0A 0A 0A 0A"))


if __name__ == "__main__":
    run_tests(globals())
