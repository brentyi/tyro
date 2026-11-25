"""Run the tyro benchmark suite.

Examples:

    # Run everything and write results to disk.
    python benchmark/suite/run.py --out new.json

    # Benchmark another checkout.
    python benchmark/suite/run.py --src ~/other_tyro/src --out old.json

    # Compare.
    python benchmark/suite/compare.py old.json new.json

Two numbers are recorded for each case:

- `cold`: the first call in a fresh process. This is what users of a CLI experience.
  Each sample is measured in a forked child, after importing `tyro` and constructing the
  inputs. It includes any imports that tyro defers.
- `warm`: the steady state cost of repeated calls in the same process.

We additionally measure `startup/*`, which are end-to-end subprocess timings with the
interpreter's own startup time subtracted.

`argparse` is used intentionally, so that the runner doesn't depend on tyro.
"""

from __future__ import annotations

import argparse
import gc
import io
import json
import os
import pathlib
import pickle
import platform
import statistics
import subprocess
import sys
import time
import warnings
from typing import Any, Callable, Dict, List, Tuple

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


def _call(thunk: Callable[[], Any]) -> None:
    try:
        thunk()
    except SystemExit:
        pass


def _time_once(thunk: Callable[[], Any]) -> float:
    start = time.perf_counter()
    _call(thunk)
    return time.perf_counter() - start


class _Silence:
    """Redirect stdout and stderr to memory."""

    def __enter__(self) -> None:
        self._old = (sys.stdout, sys.stderr)
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()

    def __exit__(self, *args: Any) -> None:
        sys.stdout, sys.stderr = self._old


def _measure_cold(thunk: Callable[[], Any], samples: int) -> List[float]:
    out = []
    for _ in range(samples):
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            try:
                with _Silence():
                    elapsed = _time_once(thunk)
                os.write(write_fd, pickle.dumps(elapsed))
            finally:
                os._exit(0)
        os.close(write_fd)
        with os.fdopen(read_fd, "rb") as f:
            data = f.read()
        os.waitpid(pid, 0)
        if len(data) == 0:
            raise RuntimeError("Benchmark case failed")
        out.append(pickle.loads(data))
    return out


def _measure_warm(thunk: Callable[[], Any], min_seconds: float) -> List[float]:
    out: List[float] = []
    with _Silence():
        _call(thunk)
        while sum(out) < min_seconds or len(out) < 3:
            out.append(_time_once(thunk))
            # Very slow cases.
            if sum(out) > min_seconds * 5:
                break
            sys.stdout.seek(0)
            sys.stdout.truncate()
    return out


def _measure_startup(src: str, script: str, samples: int) -> float:
    env = dict(os.environ, PYTHONPATH=src)

    def run(code: str) -> float:
        start = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return time.perf_counter() - start

    run(script)  # Populate bytecode caches.
    baseline, actual = [], []
    for _ in range(samples):
        baseline.append(run("pass"))
        actual.append(run(script))
    return min(actual) - min(baseline)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default=str(_HERE.parent.parent / "src"))
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--filter", default="", help="Substring to filter cases by.")
    parser.add_argument("--cold-samples", type=int, default=9)
    parser.add_argument("--warm-seconds", type=float, default=0.3)
    parser.add_argument("--skip-startup", action="store_true")
    args = parser.parse_args()

    src = str(pathlib.Path(args.src).resolve())
    results: Dict[str, Dict[str, float]] = {}

    if not args.skip_startup:
        for name, script in _STARTUP_SCRIPTS.items():
            if args.filter not in f"startup/{name}":
                continue
            elapsed = _measure_startup(src, script, samples=15)
            results[f"startup/{name}"] = {"cold": elapsed}
            print(f"{'startup/' + name:48s} cold {elapsed * 1e3:9.3f}ms", flush=True)

    sys.path.insert(0, src)
    sys.path.insert(0, str(_HERE))
    # Pin sources of nondeterminism.
    os.environ["COLUMNS"] = "100"
    warnings.simplefilter("ignore")
    import cases  # type: ignore

    import tyro

    assert tyro.__file__ is not None and tyro.__file__.startswith(src), tyro.__file__

    built: List[Tuple[str, Callable[[], Any]]] = [
        (name, builder())
        for name, builder in cases.CASES.items()
        if args.filter in name
    ]
    gc.collect()
    gc.freeze()
    # Measure all cold numbers first, since warm measurements pollute the process.
    for name, thunk in built:
        cold = _measure_cold(thunk, args.cold_samples)
        results[name] = {"cold": min(cold), "cold_median": statistics.median(cold)}
    for name, thunk in built:
        warm = _measure_warm(thunk, args.warm_seconds)
        results[name].update(warm=min(warm), warm_median=statistics.median(warm))
        print(
            f"{name:48s} cold {results[name]['cold'] * 1e3:9.3f}ms"
            f"   warm {results[name]['warm'] * 1e3:9.3f}ms",
            flush=True,
        )

    if args.out is not None:
        args.out.write_text(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "src": src,
                    "results": results,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
