#!/usr/bin/env python3
"""Compare benchmark performance between baseline and migration."""

import subprocess
import statistics
import sys

def run_benchmark(num_runs=10):
    """Run benchmark multiple times and return timing results."""
    times = []
    for i in range(num_runs):
        result = subprocess.run(
            [sys.executable, "benchmark/benchmark_wide_loop.py"],
            capture_output=True,
            text=True,
            cwd="/home/brent/tyro"
        )
        # Extract times from output
        for line in result.stdout.split('\n'):
            if "Total time taken:" in line:
                time_str = line.split(":")[1].strip().split()[0]
                times.append(float(time_str))

    return times

def compare_versions():
    """Compare baseline vs migration."""
    print("Testing BEFORE migration (commit 864e0972)...")
    subprocess.run(["git", "checkout", "864e0972"], cwd="/home/brent/tyro", capture_output=True)
    before_times = run_benchmark(10)
    before_mean = statistics.mean(before_times)
    before_stdev = statistics.stdev(before_times) if len(before_times) > 1 else 0

    print(f"BEFORE: {before_mean:.4f}s ± {before_stdev:.4f}s (n={len(before_times)})")

    print("\nTesting AFTER migration (current HEAD)...")
    subprocess.run(["git", "checkout", "brent/20251031_avoid_recreating_types"], cwd="/home/brent/tyro", capture_output=True)
    after_times = run_benchmark(10)
    after_mean = statistics.mean(after_times)
    after_stdev = statistics.stdev(after_times) if len(after_times) > 1 else 0

    print(f"AFTER:  {after_mean:.4f}s ± {after_stdev:.4f}s (n={len(after_times)})")

    diff = after_mean - before_mean
    diff_pct = (diff / before_mean) * 100

    print(f"\nDifference: {diff:+.4f}s ({diff_pct:+.1f}%)")

    if abs(diff_pct) < 2:
        print("Result: NO SIGNIFICANT DIFFERENCE (within noise)")
    elif diff_pct > 0:
        print(f"Result: SLOWER by {diff_pct:.1f}%")
    else:
        print(f"Result: FASTER by {abs(diff_pct):.1f}%")

if __name__ == "__main__":
    compare_versions()
