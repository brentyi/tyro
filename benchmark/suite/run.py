"""Run the tyro benchmark suite.

Examples:

    # Run everything and write results to disk.
    python benchmark/suite/run.py --out new.json

    # Compare against another checkout. Samples are interleaved, which makes ratios much
    # more robust to noisy machines.
    python benchmark/suite/run.py --baseline ~/old_tyro/src

Two numbers are recorded for each case:

- `cold`: the first call in a fresh process. This is what users of a CLI experience.
  It includes any imports that tyro defers.
- `warm`: the steady state cost of repeated calls in the same process.

Both are measured in a subprocess, after importing `tyro` and constructing the inputs. We
additionally measure `startup/*`, which are end-to-end subprocess timings with the
interpreter's own startup time subtracted. We always report the minimum across samples.

`argparse` is used intentionally, so that the runner doesn't depend on tyro.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import platform
import subprocess
import sys
import time
from typing import Any, Dict, List

_HERE = pathlib.Path(__file__).resolve().parent

_STARTUP_SCRIPTS = {
    "import_typing_extensions": "import typing_extensions, dataclasses",
    "import_tyro": "import tyro",
    "hello_world": (
        "import dataclasses, tyro\n"
        "@dataclasses.dataclass\n"
        "class A:\n"
        "    x: int = 3\n"
        "tyro.cli(A, args=['--x', '5'])\n"
    ),
    "hello_world_help": (
        "import dataclasses, tyro\n"
        "@dataclasses.dataclass\n"
        "class A:\n"
        "    x: int = 3\n"
        "tyro.cli(A, args=['--help'])\n"
    ),
}


_CASE_SCRIPT = """
import gc, io, sys, time, warnings
warnings.simplefilter("ignore")
import cases
thunk = cases.CASES[sys.argv[1]]()
min_seconds = float(sys.argv[2])
gc.collect()
gc.freeze()

def measure():
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    start = time.perf_counter()
    try:
        thunk()
    except SystemExit:
        pass
    return time.perf_counter() - start

stdout = sys.stdout
cold = measure()
warm = [measure()]
while sum(warm) < min_seconds or (len(warm) < 3 and sum(warm) < min_seconds * 5):
    warm.append(measure())
sys.stdout = stdout
print(cold, min(warm))
"""


def _run(src: str, *args: str) -> str:
    return subprocess.run(
        [sys.executable, "-c", *args],
        env=dict(
            os.environ,
            PYTHONPATH=os.pathsep.join([src, str(_HERE)]),
            COLUMNS="100",
        ),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout


def _time_script(src: str, script: str) -> float:
    start = time.perf_counter()
    _run(src, script)
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--src", default=str(_HERE.parent.parent / "src"))
    parser.add_argument("--baseline", default=None, help="Another src/ directory.")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--baseline-out", type=pathlib.Path, default=None)
    parser.add_argument("--filter", default="", help="Substring to filter cases by.")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--warm-seconds", type=float, default=0.1)
    args = parser.parse_args()

    sources: List[str] = [str(pathlib.Path(args.src).resolve())]
    if args.baseline is not None:
        sources.append(str(pathlib.Path(args.baseline).resolve()))
    results: List[Dict[str, Dict[str, float]]] = [{} for _ in sources]

    def report(name: str) -> None:
        line = f"{name:46s}"
        for mode in ("cold", "warm"):
            if mode not in results[0][name]:
                continue
            line += f" | {mode} {results[0][name][mode] * 1e3:8.2f}ms"
            if len(results) > 1:
                ratio = results[1][name][mode] / results[0][name][mode]
                line += f" ({ratio:6.2f}x)"
        print(line, flush=True)

    # Check that we're importing from the right place.
    for src in sources:
        tyro_file = _run(src, "import tyro; print(tyro.__file__)")
        assert tyro_file.startswith(src), (tyro_file, src)

    case_names = _run(
        sources[0], "import cases; print('\\n'.join(cases.CASES.keys()))"
    ).split()

    for name, script in _STARTUP_SCRIPTS.items():
        name = f"startup/{name}"
        if args.filter not in name:
            continue
        interpreter = math.inf
        elapsed = [math.inf for _ in sources]
        for _ in range(args.samples * 3):
            interpreter = min(interpreter, _time_script(sources[0], "pass"))
            for i, src in enumerate(sources):
                elapsed[i] = min(elapsed[i], _time_script(src, script))
        for i in range(len(sources)):
            results[i][name] = {"cold": elapsed[i] - interpreter}
        report(name)

    for name in case_names:
        if args.filter not in name:
            continue
        samples: List[List[List[float]]] = [[] for _ in sources]
        for _ in range(args.samples):
            for i, src in enumerate(sources):
                stdout = _run(src, _CASE_SCRIPT, name, str(args.warm_seconds))
                samples[i].append([float(x) for x in stdout.split()])
        for i in range(len(sources)):
            cold, warm = map(min, zip(*samples[i]))
            results[i][name] = {"cold": cold, "warm": warm}
        report(name)

    for i, out in enumerate((args.out, args.baseline_out)):
        if out is not None:
            contents: Dict[str, Any] = {
                "python": platform.python_version(),
                "src": sources[i],
                "results": results[i],
            }
            out.write_text(json.dumps(contents, indent=2))

    if len(results) > 1:
        from compare import print_comparison  # type: ignore

        print()
        print_comparison(results[1], results[0])


if __name__ == "__main__":
    main()
