import sys

collect_ignore_glob = []

if not (sys.version_info.major == 3 and sys.version_info.minor >= 8):
    collect_ignore_glob.append("*_min_py38.py")

if not (sys.version_info.major == 3 and sys.version_info.minor >= 9):
    collect_ignore_glob.append("*_min_py39.py")

if not (sys.version_info.major == 3 and sys.version_info.minor >= 10):
    collect_ignore_glob.append("*_min_py310.py")

if not (sys.version_info.major == 3 and sys.version_info.minor >= 11):
    collect_ignore_glob.append("test_py311_generated/*.py")
