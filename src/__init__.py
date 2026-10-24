"""The code behind the two scripts.

The scripts in the folder above, printerscript.py and save_paired_devices.py, are only the
command line: they read the options, call the code here, and turn problems into messages and
exit codes. Everything else lives here, one module per topic:

    escpos.py          the bytes the printer understands: picture commands, the whole print job
    printer.py         the Bluetooth connection: asking the printer questions, sending a job
    pictures.py        a jpg/png -> black-and-white dots; the test page
    suggest.py         which --channel and --contrast print a colour picture most clearly
    text.py            text (typed or from a file) -> a picture; fonts
    qr.py              text -> a QR code picture (with the segno library)
    sudoku.py          sudoku puzzles (9 x 9 and 6 x 6) with IDs, their solutions, drawing
    self_test.py       the parts of the self-test print
    devices.py         paired_devices.txt: writing it, reading it, finding a printer's address
    paired_windows.py  which devices are paired, on Windows (the registry)
    paired_linux.py    which devices are paired, on Linux (bluetoothctl)

Why this split: each part can be read and tested on its own, and a new feature (like a
sudoku) gets its own module instead of making one script ever longer.

The code here never calls sys.exit() and never prints: it returns results or raises an
error with a message, and the scripts decide what to show.

How the scripts find this folder: Python looks for imports in the folder of the script it
runs, so "from src import pictures" works from printerscript.py with nothing to install.
Inside src/, the modules import each other with a dot: "from .pictures import stack" means
pictures.py in this same folder.
"""
