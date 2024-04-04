import sys

collect_ignore_glob = []

if not sys.version_info >= (3, 8):
    collect_ignore_glob.append("*_min_py38.py")

if not sys.version_info >= (3, 9):
    collect_ignore_glob.append("*_min_py39.py")

if not sys.version_info >= (3, 10):
    collect_ignore_glob.append("*_min_py310.py")

if not sys.version_info >= (3, 12):
    collect_ignore_glob.append("*_min_py312.py")

if not sys.version_info >= (3, 11):
    collect_ignore_glob.append("test_py311_generated/*.py")
