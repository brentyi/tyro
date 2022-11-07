import sys

collect_ignore_glob = []
if sys.version_info.major == 3 and sys.version_info.minor == 7:
    collect_ignore_glob.append("*_ignore_py37.py")

if sys.version_info.major == 3 and sys.version_info.minor == 10:
    collect_ignore_glob.append("*_ignore_py310.py")

if not (sys.version_info.major == 3 and sys.version_info.minor >= 9):
    collect_ignore_glob.append("*_above_py39.py")

if not (sys.version_info.major == 3 and sys.version_info.minor == 10):
    collect_ignore_glob.append("*_only_py310.py")
