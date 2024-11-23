import sys
from typing import List

collect_ignore_glob: List[str] = []

if not sys.version_info >= (3, 8):
    collect_ignore_glob.append("*min_py38*.py")

if not sys.version_info >= (3, 9):
    collect_ignore_glob.append("*min_py39*.py")

if not sys.version_info >= (3, 10):
    collect_ignore_glob.append("*min_py310*.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("*min_py311*.py")

if not sys.version_info >= (3, 12):
    collect_ignore_glob.append("*min_py312*.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("test_py311_generated/*.py")

if sys.version_info >= (3, 13):
    collect_ignore_glob.append("*_exclude_py313*.py")
