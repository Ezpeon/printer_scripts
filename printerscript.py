"""Print a picture on a small Bluetooth thermal printer that understands ESC/POS.

    python printerscript.py --printer_name YHK-T201 --image cat.jpg

How it works:
1. The printer's name is looked up in paired_devices.txt, written by save_paired_devices.py,
   to find its Bluetooth address. Without --printer_name: the printer named on its
   "default = NAME" line, or else its first device.
2. The picture becomes black-and-white dots, as wide as the print head (384 or 576 dots).
3. The dots are sent to the printer as ESC/POS commands, over Bluetooth.

Sending works since 2026-10-20, when the printer arrived. --status only asks the printer
what it is (head width, battery, paper), without printing. --preview prints nothing either:
it saves what would be printed as a PNG.

    python printerscript.py --printer_name YHK-T201 --status
    python printerscript.py --image cat.jpg --preview cat_preview.png
    python printerscript.py --text "Shopping:\\nmilk\\neggs" --preview list.png
    python printerscript.py --text_file list.txt --preview list.png
    python printerscript.py --qr "https://example.com" --preview qr.png
    python printerscript.py --sudoku medium --preview sudoku.png
    python printerscript.py --test_page --preview test_page.png
    python printerscript.py --self_test --preview self_test.png   (QR code, sudoku, test page)

This file is only the command line: it reads the options, calls the code in src/ (its map is
in src/__init__.py), and turns problems into messages. For example, --qr calls
src/qr.py's make_qr_picture(), and if that raises "too long", this file prints that and
stops.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path

from PIL import ImageFont, UnidentifiedImageError

from src.devices import (ADDRESS_RE, DEFAULT_FILE, find_address, read_default_printer,
                         read_devices_file)
from src.escpos import DEFAULT_WIDTH, HEAD_WIDTHS, print_job
from src.pictures import (CHANNELS, make_test_page, open_colour_picture, prepare_picture, stack,
                          to_grey, turn_to)
from src.printer import ERRORS, QUESTIONS, ask, connect, error_text, send_job
from src.qr import QR_BORDER, make_qr_picture, qr_dots_per_square, qr_matrix
from src.self_test import self_test_parts
from src.sudoku import DIFFICULTIES, make_sudoku_picture, new_sudoku, parse_id, sudoku_from_id
from src.suggest import Setting, best_setting, rank_settings
from src.text import (DEFAULT_TEXT_SIZE, font_name, load_font, make_text_picture,
                      missing_characters, read_text_file)

SUDOKU_LEVELS = list(DIFFICULTIES.values())  # easy, medium, hard


def printer_address(args: argparse.Namespace) -> tuple[str, str]:
    """Return (what to call the printer, its address) from --address or --printer_name, or
    else from paired_devices.txt: its "default = NAME" line, or else its first device."""
    if args.address:
        address = args.address.strip().upper()
        if not ADDRESS_RE.match(address):
            sys.exit(f'"{args.address}" isn\'t a Bluetooth address: expected six pairs of '
                     'hexadecimal digits like AA:BB:CC:DD:EE:FF.')
        return address, address
    if not args.devices_file.exists():
        sys.exit(f"{args.devices_file} doesn't exist yet. Pair the printer in the system's "
                 "Bluetooth settings, then run save_paired_devices.py.")
    try:
        devices = read_devices_file(args.devices_file)
    except ValueError as error:
        sys.exit(str(error))
    file_name = args.devices_file.name
    name = args.printer_name or read_default_printer(args.devices_file)
    if name:
        try:
            address = find_address(devices, name)
        except LookupError as error:
            # Say where the name came from, if it wasn't typed.
            sys.exit(str(error) if args.printer_name
                     else f'{error} ("{name}" is the default printer in {file_name}.)')
        if not args.printer_name:
            print(f"No --printer_name given: using {name}, the default printer in {file_name}.")
        return name, address
    if not devices:
        sys.exit(f"{args.devices_file} has no devices. Pair the printer in the system's "
                 "Bluetooth settings, then run save_paired_devices.py again.")
    # The file is sorted by name, so with several paired devices the first one may be a phone
    # or headphones, not the printer: say which one it is, and how to choose.
    name, address = devices[0]
    print(f"No --printer_name given: using {name}, the first device in {file_name}. To choose "
          'another, write its name after "default =" in that file.')
    return name, address


def open_connection(printer: str, address: str) -> socket.socket:
    """Connect to the printer, or stop with a message if it doesn't answer."""
    try:
        sock = connect(address)
    except ConnectionError as error:
        sys.exit(str(error))
    print(f"Connected to {printer} ({address}).")
    return sock


def shown(answer: bytes) -> str:
    """The printer's answer as readable text, with the unprintable bytes in hex.
    Example: b"err:\\x00." -> 'err:\\x00.' (the code byte 0 would be invisible otherwise)."""
    return "".join(c if c.isprintable() else f"\\x{ord(c):02x}" for c in answer.decode("latin-1"))


def print_status(printer: str, address: str) -> None:
    """--status: ask the 4 questions (src/printer.py's QUESTIONS) and show the answers."""
    with open_connection(printer, address) as sock:
        for name, question in QUESTIONS.items():
            answer = ask(sock, question)
            print(f"{name}: {shown(answer) or '(no answer)'}")
            if answer:
                print(f"  hex: {answer.hex(' ').upper()}")
            if name == "paper" and error_text(answer):
                print(f"  meaning: {error_text(answer)}")


def font_for(text: str, args: argparse.Namespace) -> ImageFont.FreeTypeFont:
    """Load the font for --text or --qr_caption, say which one it is, and warn about the
    characters of `text` it can't draw. Stops with a message if --font can't be used."""
    try:
        font = load_font(args.text_size, args.font)
    except OSError as error:  # the font file is missing or isn't a font
        sys.exit(f"Can't use the font {args.font}: {error}")
    print(f"Font: {font_name(font)}, {args.text_size} dots.")
    missing = missing_characters(text, font)
    if missing:
        # A warning, not an error: the rest of the text prints fine.
        print(f"Warning: {font_name(font)} can't draw {' '.join(missing)}: they'll print "
              "as boxes. Another font may have them (--font).", file=sys.stderr)
    return font


def options_text(setting: Setting) -> str:
    """A setting as command-line options, e.g. "--channel red --contrast 1", or "no options"."""
    options = []
    if setting.channel is not None:
        options.append(f"--channel {setting.channel}")
    if setting.contrast is not None:
        options.append(f"--contrast {setting.contrast:g}")
    return " ".join(options) or "no options"


def usual_setting(settings: list[Setting]) -> Setting:
    """The setting with no options, to compare the others with."""
    return next(s for s in settings if s.channel is None and s.contrast is None)


def show_suggestions(settings: list[Setting]) -> None:
    """--suggest: the 5 best settings, the usual one (no options) to compare, and the pick."""
    print("Score: how much of the picture's colour differences stay visible on paper, from 0 "
          "to 1. Black dots: less prints faster and uses less battery.")
    print("  score  black dots  options")
    usual = usual_setting(settings)
    shown = settings[:5] + ([usual] if usual not in settings[:5] else [])
    for setting in shown:
        print(f"  {setting.score:5.2f}  {setting.black:10.0%}  {options_text(setting)}")
    print(f"Best: {options_text(best_setting(settings))}, which --auto uses. (Scores within 0.02 "
          "of the top look the same on paper: of those, the one with the fewest options.)")


def percent_option(text: str, below: float = 100) -> float:
    """Check a percentage option's value for argparse: a number from 0 up to (not including)
    `below`. That's 100 for --clean_light, and 50 for --contrast."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got '{text}'")
    if not 0 <= value < below:
        raise argparse.ArgumentTypeError(f"expected a number from 0 to {below - 1:g}, got {text}")
    return value


def sudoku_id_option(text: str) -> str:
    """Check --sudoku_solution's value for argparse: a sudoku ID like 9M-04821."""
    try:
        parse_id(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))
    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a picture, a text, a QR code or a sudoku on a small Bluetooth "
                    "thermal printer that understands ESC/POS.",
        epilog="examples:\n"
               "  printerscript.py --printer_name YHK-T201 --image cat.jpg\n"
               "  printerscript.py --printer_name YHK-T201 --status\n"
               "  printerscript.py --image cat.jpg --preview cat_preview.png\n"
               "  printerscript.py --image drawing.png --clean_light 10 --preview drawing.png\n"
               "  printerscript.py --image game.png --suggest\n"
               "  printerscript.py --image game.png --auto --preview out.png\n"
               "  printerscript.py --image game.png --channel red --contrast 1 --preview out.png\n"
               "  printerscript.py --image wide_photo.jpg --portrait --preview photo.png\n"
               '  printerscript.py --text "Shopping:\\nmilk\\neggs" --preview list.png\n'
               "  printerscript.py --text_file list.txt --preview list.png\n"
               '  printerscript.py --qr "https://example.com" --qr_caption --preview qr.png\n'
               "  printerscript.py --sudoku medium --preview sudoku.png\n"
               "  printerscript.py --sudoku_solution 9M-04821 --preview solution.png\n"
               "  printerscript.py --test_page --preview test_page.png\n"
               "  printerscript.py --self_test --preview self_test.png",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--image", type=Path, metavar="FILE", help="the jpg/png to print")
    what.add_argument("--text", metavar='"TEXT"',
                      help="print this text instead of a picture. Long lines wrap between "
                           "words; type \\n for a new line")
    what.add_argument("--text_file", type=Path, metavar="FILE",
                      help="print the text in this text file (UTF-8, e.g. a .txt), like "
                           "--text. Its line breaks are kept")
    what.add_argument("--qr", metavar='"TEXT"',
                      help="print a QR code of this text (e.g. a web address), for a phone "
                           "to scan")
    what.add_argument("--sudoku", choices=SUDOKU_LEVELS,
                      help="print a new 9 x 9 sudoku. It comes with an ID (e.g. 9M-04821) "
                           "for printing its solution later with --sudoku_solution")
    what.add_argument("--sudoku6", choices=SUDOKU_LEVELS,
                      help="the same, 6 x 6 (digits 1-6), with bigger squares")
    what.add_argument("--sudoku_solution", type=sudoku_id_option, metavar="ID",
                      help="print the solution of the sudoku with this ID")
    what.add_argument("--test_page", action="store_true",
                      help="print a built-in test picture instead")
    what.add_argument("--self_test", action="store_true",
                      help="print the self-test: a QR code, a sudoku and the test page, each "
                           "with a label saying what to look for (about 20 cm of paper, "
                           "1 minute)")
    what.add_argument("--status", action="store_true",
                      help="print nothing: ask the printer its head width, firmware, "
                           "battery, serial number and paper state, and show the answers")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--printer_name", metavar="NAME",
                       help="the printer's Bluetooth name, as in paired_devices.txt "
                            '(default: the name after "default =" in that file, or else its '
                            "first device)")
    which.add_argument("--address", metavar="AA:BB:CC:DD:EE:FF",
                       help="the printer's Bluetooth address, instead of its name")
    parser.add_argument("--preview", type=Path, metavar="PNG",
                        help="don't print: save what would be printed as a PNG instead")
    parser.add_argument("--width", type=int, choices=HEAD_WIDTHS, default=DEFAULT_WIDTH,
                        help="dots per row of the print head (default: %(default)s)")
    parser.add_argument("--clean_light", type=percent_option, default=0, metavar="PERCENT",
                        help="turn greys within PERCENT %% of white into white, so a "
                             "near-white background doesn't print as scattered dots (e.g. "
                             "10 for drawings; default 0 = off, which keeps the texture of "
                             "photos)")
    # No default (None = off): 0 is a real setting here, see stretch_contrast().
    parser.add_argument("--contrast", type=lambda text: percent_option(text, 50),
                        metavar="PERCENT",
                        help="spread the greys from black to white, so a dark or flat picture "
                             "doesn't print as one dot pattern: the darkest and lightest "
                             "PERCENT %% become pure black and white (e.g. 1; 0 stretches "
                             "from the darkest pixel to the lightest; default: off)")
    parser.add_argument("--channel", choices=list(CHANNELS),
                        help="with --image: make the greys from this colour alone, instead "
                             "of the usual mix of all three, for pictures where two "
                             "different colours print as the same grey")
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument("--suggest", action="store_true",
                      help="with --image: don't print, but try every --channel and --contrast "
                           "setting and show which keep the most of the picture's colour "
                           "differences visible on paper")
    pick.add_argument("--auto", action="store_true",
                      help="with --image: use the setting --suggest would pick, and say "
                           "which it is")
    # Mutually exclusive: argparse itself refuses "--portrait --landscape" with a message.
    shape = parser.add_mutually_exclusive_group()
    shape.add_argument("--portrait", action="store_true",
                       help="with --image: if the picture is wider than tall, turn it a "
                            "quarter turn clockwise, so its short side goes across the "
                            "paper: it prints bigger, on more paper")
    shape.add_argument("--landscape", action="store_true",
                       help="with --image: the opposite: if the picture is taller than "
                            "wide, turn it, so its long side goes across the paper: it "
                            "prints smaller, on less paper")
    parser.add_argument("--qr_caption", action="store_true",
                        help="with --qr: also print the text under the code, for people "
                             "to read")
    parser.add_argument("--text_size", type=int, default=DEFAULT_TEXT_SIZE, metavar="DOTS",
                        help="letter size for --text, --text_file and --qr_caption, in dots "
                             "(default: "
                             "%(default)s, which is 4 mm at 8 dots per mm)")
    parser.add_argument("--font", type=Path, metavar="FILE",
                        help="a .ttf/.otf font file for --text, --text_file and --qr_caption "
                             "(default: Arial on Windows, "
                             "DejaVu Sans or Liberation Sans on Linux; none of them has "
                             "emoji)")
    parser.add_argument("--devices_file", type=Path, default=DEFAULT_FILE, metavar="FILE",
                        help=f"the list of paired devices (default: {DEFAULT_FILE.name} next "
                             "to this script)")
    args = parser.parse_args()
    if args.status and args.preview is not None:
        parser.error("--status asks the printer questions: it has nothing to preview")
    if args.text is not None and not args.text.strip():
        parser.error("--text is empty")
    if args.qr is not None and not args.qr.strip():
        parser.error("--qr is empty")
    if args.qr_caption and args.qr is None:
        parser.error("--qr_caption only works together with --qr")
    if (args.portrait or args.landscape) and args.image is None:
        parser.error("--portrait and --landscape only work together with --image")
    if args.channel and args.image is None:
        parser.error("--channel only works together with --image")
    if (args.suggest or args.auto) and args.image is None:
        parser.error("--suggest and --auto only work together with --image")
    if (args.suggest or args.auto) and (args.channel or args.contrast is not None):
        parser.error("--suggest and --auto try every --channel and --contrast themselves: "
                     "leave them out")
    if args.self_test and args.clean_light:
        parser.error("--clean_light doesn't apply to --self_test: it has no photos")
    if args.self_test and args.contrast is not None:
        parser.error("--contrast doesn't apply to --self_test: it has no photos")
    if not 6 <= args.text_size <= 400:
        parser.error(f"--text_size must be between 6 and 400 dots, got {args.text_size}")

    # Look the printer up first, so a typo in its name doesn't wait for the picture.
    if args.preview is None and not args.suggest:
        printer, address = printer_address(args)
    if args.status:
        print_status(printer, address)
        return

    picture = None  # the self-test makes its parts directly; the other modes make a picture
    if args.self_test:
        try:
            parts = self_test_parts(args.width)
        except ModuleNotFoundError:
            sys.exit("--self_test needs the segno package (for its QR code). Install it with: "
                     "python -m pip install -r requirements.txt")
    elif args.test_page:
        picture = make_test_page(args.width)
    elif args.text is not None or args.text_file is not None:
        if args.text is not None:
            # "\n" typed as two characters (backslash, n) becomes a real line break. That's
            # the same in every shell, unlike each shell's own way of typing a line break.
            text = args.text.replace("\\n", "\n")
        else:
            # Checked first, because Windows calls reading a folder "Permission denied".
            if args.text_file.is_dir():
                sys.exit(f"{args.text_file} is a folder, not a text file.")
            try:
                text = read_text_file(args.text_file)
            except FileNotFoundError:
                sys.exit(f"{args.text_file} doesn't exist.")
            except UnicodeDecodeError:  # e.g. a picture, or a text saved in an old encoding
                sys.exit(f"{args.text_file} isn't a UTF-8 text file. If it is text, save it "
                         "as UTF-8 (in Notepad: File > Save as > Encoding) and try again.")
            except OSError as error:  # e.g. a file only its owner may read
                sys.exit(f"Can't read {args.text_file}: {error.strerror}.")
            if not text:
                sys.exit(f"{args.text_file} is empty.")
        picture = make_text_picture(text, args.width, font_for(text, args))
    elif args.qr is not None:
        try:
            matrix = qr_matrix(args.qr)
            picture = make_qr_picture(args.qr, args.width)
        except ModuleNotFoundError:
            sys.exit("--qr needs the segno package. Install it with: "
                     "python -m pip install -r requirements.txt")
        except ValueError as error:  # too long to be scannable
            sys.exit(str(error))
        squares = len(matrix) + 2 * QR_BORDER
        dots_per_square = qr_dots_per_square(matrix, args.width)
        print(f"QR code: {squares} x {squares} squares (with the border), "
              f"{dots_per_square} dots per square.")
        if args.qr_caption:
            picture = stack(picture, make_text_picture(args.qr, args.width,
                                                       font_for(args.qr, args)))
    elif args.sudoku or args.sudoku6:
        sudoku = new_sudoku(9 if args.sudoku else 6, args.sudoku or args.sudoku6)
        picture = make_sudoku_picture(sudoku, args.width)
        print(f"Sudoku {sudoku.id} ({sudoku.difficulty}): {sudoku.givens} of "
              f"{sudoku.size ** 2} digits given. For its solution: --sudoku_solution "
              f"{sudoku.id}")
    elif args.sudoku_solution:
        sudoku = sudoku_from_id(args.sudoku_solution)
        picture = make_sudoku_picture(sudoku, args.width, solution=True)
        print(f"Solution of sudoku {sudoku.id} ({sudoku.difficulty}).")
    else:
        try:
            colour = open_colour_picture(args.image)
        except FileNotFoundError:
            sys.exit(f"{args.image} doesn't exist.")
        except UnidentifiedImageError:
            sys.exit(f"{args.image} isn't a picture this script can open (use a jpg or png).")
        # After open_colour_picture(), so a sideways phone photo is already upright (EXIF) and
        # "wide" or "tall" means what you see on screen.
        if args.portrait or args.landscape:
            colour = turn_to(colour, "portrait" if args.portrait else "landscape")
        # After turning, which changes how much the picture is shrunk, so the scores too.
        if args.suggest or args.auto:
            settings = rank_settings(colour, args.width, args.clean_light)
            if args.suggest:
                show_suggestions(settings)
                return
            best, usual = best_setting(settings), usual_setting(settings)
            if best == usual:
                print(f"--auto: no options needed (score {best.score:.2f}).")
            else:
                print(f"--auto: {options_text(best)} (score {best.score:.2f}, against "
                      f"{usual.score:.2f} with no options).")
            # From here on, as if the user had typed them.
            args.channel, args.contrast = best.channel, best.contrast
        picture = to_grey(colour, args.channel)
    if picture is not None:
        parts = [prepare_picture(picture, args.width, args.clean_light, args.contrast)]
    try:
        job = print_job(*parts)  # the parts are printed back to back
    except ValueError as error:
        sys.exit(str(error))
    dots = stack(*parts)  # all parts in one picture, for the preview and the sizes

    size = f"{dots.width} x {dots.height} dots, {len(job)} bytes to send"
    if len(parts) > 1:
        size = f"{len(parts)} parts, " + size
    if args.width == 384:  # a 384-dot head prints 8 dots per millimetre (203 dpi)
        size += f", about {dots.height / 80:.1f} cm of paper"
    if args.preview is not None:
        # Make the folder if it doesn't exist yet, e.g. "--preview previews/cat.png". And
        # save as PNG even if the name doesn't end in .png (Pillow guesses from the ending).
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        dots.save(args.preview, format="PNG")
        print(f"Preview saved to {args.preview} ({size}).")
        return
    print(f"Picture: {size}.")
    with open_connection(printer, address) as sock:
        start = time.monotonic()
        answer = send_job(sock, job)  # waits until the printer has read the whole job
        seconds = time.monotonic() - start
    # The printer's answer to the paper question sent after the job (see send_job()).
    problem = error_text(answer) or (f"unexpected answer '{shown(answer)}'" if answer
                                     else "no answer to the paper question")
    if problem != ERRORS[0x00]:
        sys.exit(f"Sent, but the printer didn't confirm it: {problem}.")
    print(f"Sent in {seconds:.1f} s. The printer says: {problem}.")


if __name__ == "__main__":
    main()
