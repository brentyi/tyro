import sys
from typing import List

collect_ignore_glob: List[str] = []

if not sys.version_info >= (3, 8):
    collect_ignore_glob.append("*_min_py38.py")
    collect_ignore_glob.append("*_min_py38_generated.py")

if not sys.version_info >= (3, 9):
    collect_ignore_glob.append("*_min_py39.py")
    collect_ignore_glob.append("*_min_py39_generated.py")

if not sys.version_info >= (3, 10):
    collect_ignore_glob.append("*_min_py310.py")
    collect_ignore_glob.append("*_min_py310_generated.py")

if not sys.version_info >= (3, 12):
    collect_ignore_glob.append("*_min_py312.py")
    collect_ignore_glob.append("*_min_py312_generated.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("test_py311_generated/*.py")
