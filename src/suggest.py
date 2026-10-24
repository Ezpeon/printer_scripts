"""Which --channel and --contrast print a colour picture most clearly: try them all, score each.

The score says how much of the picture's colour differences stay visible on paper. It's the
measure of Lu, Xu and Jia ("Contrast Preserving Decolorization", 2012, and "... with
Perception-Based Quality Metrics", 2014), made for judging colour -> grey conversions:

1. Take pairs of pixels: neighbours 3 dots apart (they cross edges), and pixels half a
   picture apart (big areas, like a background and a floor).
2. Of the pairs whose colours look different, how many still look different on paper? That's
   their CCPR. Like recall: is what was there still there?
3. Of the pairs that look different on paper, how many really differed in colour, and aren't
   dither noise or invented edges? That's their CCFR. Like precision: is what we print real?
4. The score is the harmonic mean of the two, like the F1 score: high only when both are.
   0 = nothing survives, 1 = everything does and nothing is invented.

"Look different" is measured in CIELAB, a colour space made so that equal distances look
equally different to people: about 2 is just visible, 15 is obvious. Both are averaged over
those thresholds. The paper side is the real print: prepare_picture()'s black-and-white dots,
blurred a little the way the eye blurs them.

What the score can't see: the paper (dense dot patterns print darker than the preview), and
which parts of the picture matter to you. Example, a dark game screenshot whose pale red
background and blue-grey stone have the same grey: the usual settings score 0.70, and
--channel red --contrast 1 scores 0.85.
"""

from __future__ import annotations

from typing import NamedTuple

from PIL import Image, ImageChops, ImageCms, ImageFilter, ImageMath

from .pictures import fit_to_width, prepare_picture, stack, to_grey

CHANNEL_CHOICES = (None, "red", "green", "blue")  # None = the usual mix of all three
CONTRAST_CHOICES = (None, 0, 1, 3)  # None = off
THRESHOLDS = range(2, 16)  # "looks different", in CIELAB units: from just visible to obvious
# How the eye blurs the dots: each dot is spread over its neighbours, 1.5 dots on each side
# (a Gaussian blur). The colour picture gets the same blur, so both have the same detail.
EYE = ImageFilter.GaussianBlur(1.5)
# Scores closer than this count as the same: 0.84 and 0.83 don't look different on paper.
# A guess, to check with real prints.
SAME = 0.02


class Setting(NamedTuple):
    """One combination of options, its score (0-1) and its share of black dots (0-1)."""
    channel: str | None
    contrast: float | None
    score: float
    black: float


def rank_settings(colour: Image.Image, width: int, light_to_clean: float = 0) -> list[Setting]:
    """Score every --channel / --contrast combination for this colour picture, highest first.

    `light_to_clean` is --clean_light, which stays as the user set it.
    """
    # Shrink once, first: much faster than shrinking a big photo for each setting, and the
    # greys come out the same as in the real print to within 1.
    colour = fit_to_width(colour, width)
    shifts = [(3, 0), (0, 3), (colour.width // 2, colour.height // 2)]
    to_lab = ImageCms.buildTransform(ImageCms.createProfile("sRGB"),
                                     ImageCms.createProfile("LAB"), "RGB", "LAB")
    colour_differences = _colour_differences(
        *_pairs(ImageCms.applyTransform(colour.filter(EYE), to_lab), shifts))
    # The CIELAB lightness of each grey 0-255, to compare the print with the colours.
    greys = Image.frombytes("L", (256, 1), bytes(range(256))).convert("RGB")
    lightness = list(ImageCms.applyTransform(greys, to_lab).getchannel("L").tobytes())

    settings = []
    for channel in CHANNEL_CHOICES:
        grey = to_grey(colour, channel)
        for contrast in CONTRAST_CHOICES:
            dots = prepare_picture(grey, width, light_to_clean, contrast)
            seen = dots.convert("L").filter(EYE).point(lightness)
            score = _score(colour_differences, _lightness_differences(*_pairs(seen, shifts)))
            black = dots.histogram()[0] / (dots.width * dots.height)
            settings.append(Setting(channel, contrast, score, black))
    return sorted(settings, key=lambda setting: setting.score, reverse=True)


def best_setting(settings: list[Setting]) -> Setting:
    """The setting to use: of those within SAME of the top score, the one with the fewest
    options (then the highest score). An option that changes nothing visible is only in the
    way, so a picture where nothing helps gets no options at all.

    Example: 0.907 for --channel green --contrast 0, 0.904 for --contrast 0 alone and 0.889
    for no options: all three count as the same, so no options.
    """
    top = max(setting.score for setting in settings)
    close = [setting for setting in settings if setting.score >= top - SAME]
    return min(close, key=lambda setting: (
        (setting.channel is not None) + (setting.contrast is not None), -setting.score))


def _pairs(picture: Image.Image, shifts: list[tuple[int, int]]) -> tuple[Image.Image, Image.Image]:
    """Two pictures whose pixels at the same place are the pairs: `picture` once per shift,
    one under the other, and the same with each copy shifted (right, down), wrapping around
    the edges. Example with shift (3, 0): each pixel is paired with the one 3 dots left of it."""
    return (stack(*[picture] * len(shifts)),
            stack(*[ImageChops.offset(picture, right, down) for right, down in shifts]))


def _colour_differences(lab: Image.Image, partners: Image.Image) -> Image.Image:
    """How different each pair of colours looks: their distance in CIELAB, rounded down, as an
    "L" picture (0-255)."""
    l1, a1, b1 = lab.split()
    l2, a2, b2 = partners.split()
    # Pillow stores the lightness L (0-100) as 0-255, so its difference is divided by 2.55.
    # It stores a and b with 128 added, which the subtraction removes again.
    return ImageMath.lambda_eval(
        lambda m: m["convert"]((((m["float"](m["l1"]) - m["l2"]) / 2.55) ** 2
                                + (m["float"](m["a1"]) - m["a2"]) ** 2
                                + (m["float"](m["b1"]) - m["b2"]) ** 2) ** 0.5, "L"),
        l1=l1, l2=l2, a1=a1, a2=a2, b1=b1, b2=b2)


def _lightness_differences(seen: Image.Image, partners: Image.Image) -> Image.Image:
    """The same for the print, where only the lightness (0-255 for 0-100) can differ."""
    return ImageChops.difference(seen, partners).point(lambda value: int(value / 2.55))


def _score(colour_differences: Image.Image, print_differences: Image.Image) -> float:
    """CCPR and CCFR (see the top of this file), averaged over THRESHOLDS, then combined."""
    # histogram() counts the pairs per difference: [5] = how many pairs differ by 5. darker()
    # is the smaller of the two differences: a pair differs by at least 5 both in colour and
    # on paper exactly when the smaller of its differences is at least 5.
    in_colour = colour_differences.histogram()
    on_paper = print_differences.histogram()
    in_both = ImageChops.darker(colour_differences, print_differences).histogram()
    kept, real = [], []
    for threshold in THRESHOLDS:
        both = sum(in_both[threshold:])
        colour_pairs, paper_pairs = sum(in_colour[threshold:]), sum(on_paper[threshold:])
        # No pair differs that much (e.g. a blank picture): nothing lost, nothing invented.
        kept.append(both / colour_pairs if colour_pairs else 1.0)
        real.append(both / paper_pairs if paper_pairs else 1.0)
    ccpr, ccfr = sum(kept) / len(kept), sum(real) / len(real)
    return 2 * ccpr * ccfr / (ccpr + ccfr) if ccpr + ccfr else 0.0
