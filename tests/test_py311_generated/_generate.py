"""Generate a Python 3.11 version of tests. This will use imports from `typing` instead
of `typing_extensions`."""

import pathlib

for test_path in pathlib.Path(__file__).absolute().parent.parent.glob("test_*.py"):
    (
        pathlib.Path(__file__).absolute().parent / (test_path.stem + "_generated.py")
    ).write_text(test_path.read_text().replace("typing_extensions", "typing"))
