"""A tiny test runner, so the tests need nothing but Python (no pytest).

Each test file ends with `run_tests(globals())`. That runs every function whose name starts
with "test_", prints ok / SKIP / FAIL for each one, and exits with code 1 if any failed.
"""

import sys
import traceback


class Skip(Exception):
    """Raise Skip("why") in a test that can't run here, e.g. because a picture is missing."""


def run_tests(namespace: dict) -> None:
    tests = [(name, function) for name, function in sorted(namespace.items())
             if name.startswith("test_") and callable(function)]
    failed = skipped = 0
    for name, test in tests:
        try:
            test()
        except Skip as reason:
            skipped += 1
            print(f"SKIP  {name}: {reason}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)
