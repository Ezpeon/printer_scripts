"""Tests for src/suggest.py: scoring the --channel and --contrast settings for a picture.

The tests make their own pictures.

Run all the tests with tests\\run_all.py, or only these with tests\\test_suggest.py.
"""

from PIL import Image

from runner import run_tests
import helpers  # noqa: F401  (makes src/ importable)
from src import suggest
from src.suggest import Setting


def game_colours() -> Image.Image:
    """Like the game screenshot: a pale red (left) and a blue-grey stone (right) that get the
    same grey in the usual mix, between a black stripe and a white one (the screenshot's
    black and white parts, which keep --contrast from separating the two greys)."""
    picture = Image.new("RGB", (384, 200), (96, 64, 64))
    picture.paste((68, 71, 85), (192, 0, 384, 200))
    picture.paste((0, 0, 0), (0, 0, 384, 20))
    picture.paste((255, 255, 255), (0, 180, 384, 200))
    return picture


def test_every_setting_is_scored():
    settings = suggest.rank_settings(game_colours(), 384)
    assert len(settings) == len(suggest.CHANNEL_CHOICES) * len(suggest.CONTRAST_CHOICES)
    scores = [setting.score for setting in settings]
    assert scores == sorted(scores, reverse=True)  # highest first
    assert all(0 <= setting.score <= 1 and 0 <= setting.black <= 1 for setting in settings)


def test_red_separates_colours_of_the_same_brightness():
    """The usual mix prints both colours as the same dots; in red they differ (96 and 68).
    --contrast changes nothing here (the black and white stripes), so it isn't suggested."""
    settings = suggest.rank_settings(game_colours(), 384)
    best = suggest.best_setting(settings)
    assert best.channel == "red" and best.contrast is None, best
    usual = next(s for s in settings if s.channel is None and s.contrast is None)
    assert best.score > usual.score + 0.2, (best, usual)


def test_blank_picture_needs_no_options():
    """Nothing to keep and nothing invented: every setting scores 1, so no options."""
    settings = suggest.rank_settings(Image.new("RGB", (384, 100), "white"), 384)
    assert all(setting.score == 1.0 for setting in settings)
    assert suggest.best_setting(settings)[:2] == (None, None)


def test_best_setting_prefers_fewer_options():
    """best_setting()'s docstring example: scores within 0.02 of the top count as the same."""
    settings = [Setting("green", 0, 0.907, 0.4), Setting(None, 0, 0.904, 0.4),
                Setting(None, None, 0.889, 0.3), Setting("red", 1, 0.80, 0.3)]
    assert suggest.best_setting(settings) == settings[2]
    # More than 0.02 below the top: the top wins, even with more options.
    settings = [Setting("red", 1, 0.85, 0.5), Setting(None, None, 0.70, 0.8)]
    assert suggest.best_setting(settings) == settings[0]


if __name__ == "__main__":
    run_tests(globals())
