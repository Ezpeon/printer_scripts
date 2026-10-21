"""Run every tests/test_*.py file, one after the other.

    .venv\\Scripts\\python.exe tests\\run_all.py     (Windows)
    .venv/bin/python tests/run_all.py              (Linux)
"""

import subprocess
import sys
from pathlib import Path

failed = []
for test_file in sorted(Path(__file__).resolve().parent.glob("test_*.py")):
    # flush=True: print the heading now, before the test file prints its own lines.
    print(f"=== {test_file.name}", flush=True)
    if subprocess.run([sys.executable, str(test_file)]).returncode != 0:
        failed.append(test_file.name)
    print()
print("ALL TEST FILES PASSED" if not failed else f"FAILED: {', '.join(failed)}")
sys.exit(1 if failed else 0)
