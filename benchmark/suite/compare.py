"""Compare two result files from `run.py`: `python compare.py old.json new.json`."""

from __future__ import annotations

import argparse
import json
import math
import pathlib
from typing import Dict, List


def print_comparison(
    old: Dict[str, Dict[str, float]], new: Dict[str, Dict[str, float]]
) -> None:
    speedups: Dict[str, List[float]] = {"cold": [], "warm": []}
    header = f"{'case':46s}"
    for mode in speedups:
        header += f" | {mode + ' old':>10s} {'new':>9s} {'speedup':>8s}"
    print(header)
    print("-" * len(header))
    for name in old:
        if name not in new:
            continue
        line = f"{name:46s}"
        for mode in speedups:
            if mode not in old[name] or mode not in new[name]:
                continue
            o, n = old[name][mode], new[name][mode]
            line += f" | {o * 1e3:8.2f}ms {n * 1e3:7.2f}ms {o / n:7.2f}x"
            speedups[mode].append(o / n)
        print(line)
    print("-" * len(header))
    for mode, values in speedups.items():
        if len(values) == 0:
            continue
        geomean = math.exp(sum(map(math.log, values)) / len(values))
        print(
            f"{mode}: geomean {geomean:.2f}x, min {min(values):.2f}x, "
            f"max {max(values):.2f}x, cases >=5x: "
            f"{sum(v >= 5 for v in values)}/{len(values)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=pathlib.Path)
    parser.add_argument("new", type=pathlib.Path)
    args = parser.parse_args()
    print_comparison(
        json.loads(args.old.read_text())["results"],
        json.loads(args.new.read_text())["results"],
    )


if __name__ == "__main__":
    main()
