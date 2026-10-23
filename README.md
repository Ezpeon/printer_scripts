# printer_scripts

Print pictures, text, QR codes and sudokus on a small Bluetooth thermal printer that
understands ESC/POS (the command language of most receipt printers), from Windows or Linux.
No phone needed.

> **Status (2026-10-20):** printing works on Windows, tried on the real printer. Linux is
> untested. The printer prints about 5 mm a second: a 25 cm print takes about a minute.

## Setup (once)

```
python -m venv .venv                                            (Linux: python3)
.venv\Scripts\python.exe -m pip install -r requirements.txt     (Windows)
.venv/bin/python -m pip install -r requirements.txt             (Linux)
```

Pair the printer in the system's Bluetooth settings, then save the list of paired devices
to `paired_devices.txt` (one `name = address` per line). Run this again after pairing a new
device:

```
python save_paired_devices.py
```

The examples here write `python` for short. Use `.venv\Scripts\python.exe` on Windows and
`.venv/bin/python` on Linux.

## Printing

Each command prints **one** of the things below. Add `--printer_name NAME` (the name in
`paired_devices.txt`) to print it, or `--preview out.png` to only see it.

```
python printerscript.py --printer_name YHK-T201 --image cat.jpg
python printerscript.py --image cat.jpg --preview out.png
```

**Wait until the printer stops before the next print.** The script ends as soon as the
printer has taken the print in, often before the paper is done, and a new print cuts off the
one still printing.

| Option | What it prints |
|---|---|
| `--image cat.jpg` | A jpg or png, scaled to the paper's width. Greys become patterns of black dots. |
| `--text "Shopping:\nmilk"` | Text. Long lines wrap; `\n` starts a new line. |
| `--text_file list.txt` | The text of a UTF-8 text file, with its line breaks. |
| `--qr "https://example.com"` | A QR code for a phone to scan. |
| `--sudoku medium` | A new 9 × 9 sudoku (`easy`, `medium` or `hard`), with an ID like `9M-04821`. |
| `--sudoku6 easy` | The same, 6 × 6 (digits 1–6), with bigger squares. |
| `--sudoku_solution 9M-04821` | The solution of that sudoku. The ID is enough: nothing is saved. |
| `--test_page` | A frame, an arrow and grey steps, to check that a print isn't cut, mirrored or the wrong width. |
| `--self_test` | A QR code, a sudoku and the test page in one print (about 20 cm), each labelled with what to check. |

Extra options:

| Option | What it does |
|---|---|
| `--clean_light 10` | With `--image`: turns near-white greys white, so a drawing's light background doesn't print as scattered dots. Default 0 (off), which keeps the texture of photos. |
| `--portrait` | With `--image`: turns a wide picture a quarter turn clockwise, so its short side goes across the paper. It prints bigger, on more paper. A tall or square picture stays as it is. |
| `--landscape` | With `--image`: the opposite. Turns a tall picture, so its long side goes across: smaller, on less paper. |
| `--text_size 48` | Letter size for `--text`, `--text_file` and `--qr_caption`, in dots (8 dots = 1 mm). Default 32. |
| `--font file.ttf` | Another font for text. Default: Arial (Windows), DejaVu Sans (Linux). |
| `--qr_caption` | With `--qr`: also prints the text under the code. |
| `--address AA:BB:CC:DD:EE:FF` | The printer's address, instead of `--printer_name`. |
| `--width 576` | For printers with a 576-dot head. Default 384 (48 mm wide). |
| `--devices_file my.txt` | Another list than `paired_devices.txt`. |

To ask the printer what it is, without printing (head width, firmware, battery, paper):

```
python printerscript.py --printer_name YHK-T201 --status
```

`python printerscript.py --help` lists everything.

## Files

- `printerscript.py`, `save_paired_devices.py`: the two commands.
- `src/`: the code behind them, one file per topic (the map is in `src/__init__.py`).
- `tests/`: `python tests/run_all.py` runs them all. No printer needed.

## How it works

- The printer is a classic Bluetooth serial port (SPP), on RFCOMM channel 2. Python's own
  `socket` module connects to it, on Windows and Linux.
- Everything is printed as a picture: 384 black-and-white dots per row, sent with the
  standard ESC/POS raster command `GS v 0`. Text, QR codes and sudokus are drawn first.
- Greys become patterns of black dots (Floyd–Steinberg dithering).

## License

Public domain ([the Unlicense](LICENSE)): do anything you like with it.
