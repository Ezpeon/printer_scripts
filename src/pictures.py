"""Pictures: from a jpg/png file to black-and-white dots, plus the built-in test page.

The pictures here are Pillow pictures in one of two modes:
- "L", greyscale: one byte per pixel, 0 = black, 255 = white. Everything starts as this.
- "1", black-and-white dots: what the printer prints. prepare_picture() makes them.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def open_picture(path: Path) -> Image.Image:
    """Open a jpg/png as a greyscale picture: mode "L", one byte per pixel, 0 = black.

    Raises FileNotFoundError, or PIL.UnidentifiedImageError if it isn't a picture.
    """
    with Image.open(path) as original:
        # Phones often store photos sideways, with a note ("EXIF orientation") saying how to
        # turn them for viewing. exif_transpose() applies that note, so the print isn't
        # sideways either. It returns a new picture, so the file can be closed after this.
        picture = ImageOps.exif_transpose(original)
    # 16-bit greys (e.g. some PNGs) go from 0 to 65535. Pillow's conversion to normal 8-bit
    # grey cuts them off at 255 instead of scaling them, so a mid-grey (128 x 257 = 32896)
    # would print white. Dividing by 257 maps 0..65535 exactly onto 0..255 (65535 / 257 = 255).
    if picture.mode.startswith("I"):  # "I;16", "I;16B", ... and "I" (integer greys)
        picture = picture.convert("I").point(lambda value: value / 257)
    # Transparent parts of a PNG have no colour of their own: put the picture on white paper
    # first, or they could come out black.
    if picture.mode in ("RGBA", "LA", "PA") or "transparency" in picture.info:
        picture = picture.convert("RGBA")
        paper = Image.new("RGBA", picture.size, "white")
        picture = Image.alpha_composite(paper, picture)
    # Pillow's greyscale is 29.9 % red + 58.7 % green + 11.4 % blue, the usual mix: our eyes
    # are most sensitive to green.
    return picture.convert("L")


def turn_to(picture: Image.Image, shape: str) -> Image.Image:
    """Turn the picture a quarter turn if that gives it `shape` on paper, else keep it.

    The paper's width is fixed (384 dots), so the side that goes across decides the size:
    - "portrait": taller than wide, short side across. A wide picture gets turned, and
      prints bigger, on more paper. Example: 1600 x 900 -> 900 x 1600, which prints as
      384 x 683 dots instead of 384 x 216.
    - "landscape": the opposite, long side across. A tall picture gets turned, and prints
      smaller, on less paper. Example: 900 x 1600 -> 1600 x 900, 384 x 216 dots.
    A picture that already has that shape, or is square, stays as it is.
    """
    wide, tall = picture.width > picture.height, picture.height > picture.width
    if (shape == "portrait" and wide) or (shape == "landscape" and tall):
        # Pillow's ROTATE_270 turns 270 degrees anticlockwise, which is a quarter turn
        # clockwise: the picture's top ends up along the right edge of the paper.
        return picture.transpose(Image.Transpose.ROTATE_270)
    return picture


def fit_to_width(picture: Image.Image, width: int) -> Image.Image:
    """Scale the picture to `width` dots, keeping its proportions.

    Example: 1344 x 1344 pixels at width 384 -> 384 x 384 dots.
    """
    height = max(1, round(picture.height * width / picture.width))
    # LANCZOS is a resampling filter that keeps edges sharp when shrinking a picture.
    return picture.resize((width, height), Image.Resampling.LANCZOS)


def clean_light(picture: Image.Image, percent: float) -> Image.Image:
    """Turn every grey within `percent` % of white into pure white, for clean backgrounds.

    Why: dithering turns a light grey background (e.g. 235 instead of 255) into scattered
    black dots. In a photo those dots can be real texture (a white wall), but in a flat
    drawing they're just noise, so how much to clean is left to the user.

    The greys below that limit are stretched evenly up to white, so shading stays smooth
    instead of getting a hard edge. Example with percent = 10: the limit is 255 x 0.9 = 229.5,
    so 235 -> 255 (white), 200 -> 222, 128 -> 142, 0 -> 0. With percent = 0, nothing changes.
    """
    if not 0 <= percent < 100:
        raise ValueError(f"clean_light must be at least 0 and less than 100, got {percent}")
    if percent == 0:
        return picture
    white_limit = 255 * (1 - percent / 100)
    # point() replaces each grey value (0-255) with table[value]: one table for all pixels.
    table = [min(255, round(value * 255 / white_limit)) for value in range(256)]
    return picture.point(table)


def stretch_contrast(picture: Image.Image, percent: float) -> Image.Image:
    """Spread the greys from black to white, for dark or flat pictures.

    Why: when all the greys sit close together (a dark game screenshot, a beige coin on a
    beige wall), they all become similar dot patterns on paper. Stretching them apart makes
    the differences visible. Example: greys from 30 to 115 are spread over 0 to 255, so each
    step of 1 becomes 3: 30 -> 0, 72 -> 126, 115 -> 255.

    `percent` % of the pixels at each end are allowed to turn pure black or pure white, and
    the stretch starts from the next ones. Why: a few pixels that are already black or white
    (like white text on a dark screenshot) would otherwise make the range 0 to 255 already,
    and nothing would change. 1 is a good start; 0 stretches from the darkest pixel to the
    lightest. 50 or more would cut off everything from both ends, so it's refused.
    """
    if not 0 <= percent < 50:
        raise ValueError(f"contrast must be at least 0 and less than 50, got {percent}")
    return ImageOps.autocontrast(picture, cutoff=percent)


def to_dots(picture: Image.Image) -> Image.Image:
    """Turn a greyscale picture into black-and-white dots (mode "1") by dithering.

    Floyd-Steinberg dithering: each pixel becomes black
    or white, and the rounding error is passed on to the neighbours not done yet. So grey
    areas become a mix of black and white dots that looks grey from a distance.
    """
    return picture.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def prepare_picture(picture: Image.Image, width: int, light_to_clean: float = 0,
                    contrast: float | None = None) -> Image.Image:
    """Greyscale picture -> black-and-white dots, `width` dots wide.

    `contrast` is stretch_contrast()'s percent. None (the default) leaves the greys as they
    are; 0 can't mean "off" here, because 0 % is a real stretch.

    The order:
    1. Resize first: shrinking averages neighbouring pixels, which already smooths out some
       of the JPEG noise in light areas, and single stray pixels that would hold back the
       contrast stretch.
    2. Then the contrast stretch, then the cleaning: "within N % of white" should mean white
       on paper, so the cleaning looks at the stretched greys.
    """
    picture = fit_to_width(picture, width)
    if contrast is not None:
        picture = stretch_contrast(picture, contrast)
    return to_dots(clean_light(picture, light_to_clean))


def stack(*pictures: Image.Image) -> Image.Image:
    """Put pictures of the same width and mode one under the other, e.g. a caption under a
    QR code, or all the parts of the self-test in one preview."""
    stacked = Image.new(pictures[0].mode, (pictures[0].width, sum(p.height for p in pictures)),
                        255)  # 255 = white, in both greyscale ("L") and black-and-white ("1")
    top = 0
    for picture in pictures:
        stacked.paste(picture, (0, top))
        top += picture.height
    return stacked


def make_test_page(width: int) -> Image.Image:
    """A greyscale test picture for checking a print.

    - A frame along all four edges: the print is complete and not shifted.
    - "TOP LEFT" in that corner and an arrow pointing right: not mirrored or upside down.
    - A grey ramp in 8 steps, from white to black: the dithering makes greys.
    - The width in dots: the right head width was used.
    """
    height = width * 3 // 4
    page = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(page)
    draw.fontmode = "1"  # text without grey anti-aliased edges, so it prints crisply
    scale = width / 384  # everything grows with the width, so a 576 page looks the same
    font = ImageFont.load_default(size=round(22 * scale))
    small_font = ImageFont.load_default(size=round(15 * scale))
    margin = round(10 * scale)

    # The frame, 3 dots thick (at 384).
    draw.rectangle([0, 0, width - 1, height - 1], outline=0, width=round(3 * scale))
    draw.text((margin, margin), "TOP LEFT", fill=0, font=font)

    # An arrow pointing right: a bar and a triangle.
    middle = round(height * 0.38)
    left, right = round(width * 0.15), round(width * 0.85)
    half_bar, head = round(5 * scale), round(28 * scale)
    draw.rectangle([left, middle - half_bar, right - head, middle + half_bar], fill=0)
    draw.polygon([(right - head, middle - head), (right, middle), (right - head, middle + head)],
                 fill=0)

    # The grey ramp: 8 boxes from white (255) to black (0), with a thin outline so the white
    # box shows.
    top, bottom = round(height * 0.60), round(height * 0.80)
    box_width = (width - 2 * margin) / 8
    for step in range(8):
        grey = round(255 * (7 - step) / 7)
        box_left = margin + round(step * box_width)
        box_right = margin + round((step + 1) * box_width) - 1
        draw.rectangle([box_left, top, box_right, bottom], fill=grey, outline=0)

    draw.text((margin, bottom + round(8 * scale)), f"{width} dots wide - printerscript test page",
              fill=0, font=small_font)
    return page
