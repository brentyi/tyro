#!/usr/bin/env python3
"""Compare tyro versions (0.9.35 vs main branch) across multiple metrics."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BENCHMARK_DIR = Path(__file__).parent
TYRO_ROOT = BENCHMARK_DIR.parent

# Versions to compare
VERSIONS = {
    "0.9.35": "tyro==0.9.35",
    "1.0.0 (main)": str(TYRO_ROOT),
}


def run_command(cmd: list[str], cwd: str | None = None, capture: bool = True) -> str:
    """Run a command and return its output."""
    result = subprocess.run(
        cmd,
        check=False,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"stderr: {result.stderr}")
        return ""
    return result.stdout


def extract_time_ms(output: str) -> float | None:
    """Extract time in ms from benchmark output."""
    match = re.search(r"Total time taken: ([\d.]+)ms", output)
    if match:
        return float(match.group(1))
    return None


def measure_import_time(venv_python: str) -> float:
    """Measure import time for tyro."""
    code = """
import time
start = time.perf_counter()
import tyro
print(f"{(time.perf_counter() - start) * 1000:.2f}")
"""
    result = subprocess.run(
        [venv_python, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        print(f"Failed to parse import time: {result.stdout}")
        return 0.0


def measure_site_packages_size(venv_path: str, package_name: str) -> float:
    """Measure installed size of a package and its dependencies in MB.

    Uses pip show to get the list of packages that would be installed,
    then sums their sizes. This excludes pip/setuptools infrastructure.
    """
    if sys.platform == "win32":
        venv_python = os.path.join(venv_path, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_path, "bin", "python")

    # Get list of installed packages (excluding pip, setuptools, wheel)
    result = subprocess.run(
        [venv_python, "-m", "pip", "list", "--format=freeze"],
        check=False,
        capture_output=True,
        text=True,
    )
    packages = []
    for line in result.stdout.strip().split("\n"):
        if "==" in line:
            pkg = line.split("==")[0].lower()
            if pkg not in ("pip", "setuptools", "wheel"):
                packages.append(pkg)

    # Find site-packages directory
    site_packages = Path(venv_path) / "lib"
    if not site_packages.exists():
        site_packages = Path(venv_path) / "Lib" / "site-packages"

    for sp in site_packages.rglob("site-packages"):
        total_size = 0
        for item in sp.iterdir():
            # Match package directories and dist-info
            item_name = item.name.lower().replace("-", "_").replace(".", "_")
            for pkg in packages:
                pkg_normalized = pkg.replace("-", "_")
                if item_name.startswith(pkg_normalized):
                    if item.is_dir():
                        total_size += sum(
                            f.stat().st_size for f in item.rglob("*") if f.is_file()
                        )
                    elif item.is_file():
                        total_size += item.stat().st_size
                    break
        return total_size / (1024 * 1024)
    return 0.0


def run_benchmark(venv_python: str, script: str, args: list[str] = []) -> float | None:
    """Run a benchmark script and return time in ms."""
    # Run multiple times and take median
    times = []
    for _ in range(3):
        result = subprocess.run(
            [venv_python, script] + args,
            check=False,
            capture_output=True,
            text=True,
            cwd=BENCHMARK_DIR,
        )
        time_ms = extract_time_ms(result.stdout)
        if time_ms is not None:
            times.append(time_ms)

    if times:
        times.sort()
        return times[len(times) // 2]  # median
    return None


def main():
    print("=" * 70)
    print("Tyro Version Comparison: 0.9.35 vs 1.0.0 (main)")
    print("=" * 70)

    results = {}
    csv_rows = []  # For CSV output

    for version_name, version_spec in VERSIONS.items():
        print(f"\n{'=' * 70}")
        print(f"Testing: {version_name}")
        print("=" * 70)

        # Create temporary venv
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = os.path.join(tmpdir, "venv")

            # Create venv with standard venv module (includes pip)
            print("Creating virtual environment...")
            run_command([sys.executable, "-m", "venv", venv_path], capture=False)

            # Determine python path
            if sys.platform == "win32":
                venv_python = os.path.join(venv_path, "Scripts", "python.exe")
                venv_pip = os.path.join(venv_path, "Scripts", "pip.exe")
            else:
                venv_python = os.path.join(venv_path, "bin", "python")
                venv_pip = os.path.join(venv_path, "bin", "pip")

            # Install tyro using pip
            print(f"Installing {version_spec}...")
            run_command([venv_pip, "install", version_spec, "-q"], capture=False)

            results[version_name] = {}

            # 1. Measure dependency size (tyro + its dependencies, excluding pip/setuptools)
            print("\n--- Dependency Size ---")
            size_mb = measure_site_packages_size(venv_path, "tyro")
            results[version_name]["size_mb"] = size_mb
            print(f"tyro + dependencies size: {size_mb:.2f} MB")

            # 2. Measure import time
            print("\n--- Import Time ---")
            import_times = [measure_import_time(venv_python) for _ in range(5)]
            import_times.sort()
            import_time = import_times[len(import_times) // 2]  # median
            results[version_name]["import_time_ms"] = import_time
            print(f"Import time: {import_time:.2f} ms")

            # 3. Run benchmarks
            print("\n--- Benchmark: 0_many_args ---")
            results[version_name]["many_args"] = {}
            for n in [10, 100, 1000, 3000]:
                script = f"0_many_args_{n}.py"
                time_ms = run_benchmark(venv_python, script)
                results[version_name]["many_args"][n] = time_ms
                print(f"  n={n}: {time_ms:.1f} ms" if time_ms else f"  n={n}: FAILED")

            print("\n--- Benchmark: 1_subcommands_many ---")
            results[version_name]["subcommands_many"] = {}
            for n in [10, 100, 500, 1000]:
                time_ms = run_benchmark(
                    venv_python, "1_subcommands_many.py", [f"--n={n}"]
                )
                results[version_name]["subcommands_many"][n] = time_ms
                print(f"  n={n}: {time_ms:.1f} ms" if time_ms else f"  n={n}: FAILED")

            print("\n--- Benchmark: 2_subcommands_adversarial ---")
            results[version_name]["subcommands_adversarial"] = {}
            for n in [1, 2, 3, 4, 5]:
                time_ms = run_benchmark(
                    venv_python, "2_subcommands_adversarial.py", [f"--n={n}"]
                )
                results[version_name]["subcommands_adversarial"][n] = time_ms
                print(f"  n={n}: {time_ms:.1f} ms" if time_ms else f"  n={n}: FAILED")

    # Build CSV data
    v1, v2 = list(results.keys())

    csv_rows.append(["metric", "parameter", "0.9.35", "1.0.0", "speedup"])

    # Size (tyro + dependencies, excluding pip/setuptools)
    s1, s2 = results[v1]["size_mb"], results[v2]["size_mb"]
    csv_rows.append(
        ["tyro_dependencies_size_mb", "", f"{s1:.2f}", f"{s2:.2f}", f"{s1 / s2:.2f}"]
    )

    # Import time
    i1, i2 = results[v1]["import_time_ms"], results[v2]["import_time_ms"]
    csv_rows.append(["import_time_ms", "", f"{i1:.2f}", f"{i2:.2f}", f"{i1 / i2:.2f}"])

    # Many args
    for n in [10, 100, 1000, 3000]:
        t1 = results[v1]["many_args"].get(n)
        t2 = results[v2]["many_args"].get(n)
        if t1 and t2:
            csv_rows.append(
                ["0_many_args", str(n), f"{t1:.1f}", f"{t2:.1f}", f"{t1 / t2:.2f}"]
            )

    # Subcommands many
    for n in [10, 100, 500, 1000]:
        t1 = results[v1]["subcommands_many"].get(n)
        t2 = results[v2]["subcommands_many"].get(n)
        if t1 and t2:
            csv_rows.append(
                [
                    "1_subcommands_many",
                    str(n),
                    f"{t1:.1f}",
                    f"{t2:.1f}",
                    f"{t1 / t2:.2f}",
                ]
            )

    # Subcommands adversarial
    for n in [1, 2, 3, 4, 5]:
        t1 = results[v1]["subcommands_adversarial"].get(n)
        t2 = results[v2]["subcommands_adversarial"].get(n)
        if t1 and t2:
            csv_rows.append(
                [
                    "2_subcommands_adversarial",
                    str(n),
                    f"{t1:.1f}",
                    f"{t2:.1f}",
                    f"{t1 / t2:.2f}",
                ]
            )

    # Write CSV
    csv_path = BENCHMARK_DIR / "benchmark_results.csv"
    with open(csv_path, "w") as f:
        for row in csv_rows:
            f.write(",".join(row) + "\n")
    print(f"\nCSV results written to: {csv_path}")

    # Write Markdown
    md_path = BENCHMARK_DIR / "benchmark_results.md"
    with open(md_path, "w") as f:
        f.write("# Tyro Benchmark Results: 0.9.35 vs 1.0.0\n\n")

        f.write("## Environment Metrics\n\n")
        f.write("| Metric | 0.9.35 | 1.0.0 | Ratio |\n")
        f.write("|--------|--------|-------|-------|\n")
        f.write(
            f"| tyro + dependencies (MB) | {s1:.2f} | {s2:.2f} | {s1 / s2:.2f}x |\n"
        )
        f.write(f"| Import time (ms) | {i1:.2f} | {i2:.2f} | {i1 / i2:.2f}x |\n\n")

        f.write("## Benchmark: 0_many_args\n\n")
        f.write("| Args | 0.9.35 (ms) | 1.0.0 (ms) | Speedup |\n")
        f.write("|------|-------------|------------|--------|\n")
        for n in [10, 100, 1000, 3000]:
            t1 = results[v1]["many_args"].get(n)
            t2 = results[v2]["many_args"].get(n)
            if t1 and t2:
                f.write(f"| {n} | {t1:.1f} | {t2:.1f} | {t1 / t2:.2f}x |\n")

        f.write("\n## Benchmark: 1_subcommands_many\n\n")
        f.write("| n | 0.9.35 (ms) | 1.0.0 (ms) | Speedup |\n")
        f.write("|---|-------------|------------|--------|\n")
        for n in [10, 100, 500, 1000]:
            t1 = results[v1]["subcommands_many"].get(n)
            t2 = results[v2]["subcommands_many"].get(n)
            if t1 and t2:
                f.write(f"| {n} | {t1:.1f} | {t2:.1f} | {t1 / t2:.2f}x |\n")

        f.write("\n## Benchmark: 2_subcommands_adversarial\n\n")
        f.write("| n | 0.9.35 (ms) | 1.0.0 (ms) | Speedup |\n")
        f.write("|---|-------------|------------|--------|\n")
        for n in [1, 2, 3, 4, 5]:
            t1 = results[v1]["subcommands_adversarial"].get(n)
            t2 = results[v2]["subcommands_adversarial"].get(n)
            if t1 and t2:
                f.write(f"| {n} | {t1:.1f} | {t2:.1f} | {t1 / t2:.2f}x |\n")

    print(f"Markdown results written to: {md_path}")

    # Print summary to console
    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n{'Metric':<40} {'0.9.35':>12} {'1.0.0':>12} {'Speedup':>10}")
    print("-" * 74)

    print(f"{'tyro + dependencies (MB)':<40} {s1:>12.2f} {s2:>12.2f} {s1 / s2:>9.2f}x")
    print(f"{'Import time (ms)':<40} {i1:>12.2f} {i2:>12.2f} {i1 / i2:>9.2f}x")

    print(f"\n{'0_many_args benchmarks:':<40}")
    for n in [10, 100, 1000, 3000]:
        t1 = results[v1]["many_args"].get(n)
        t2 = results[v2]["many_args"].get(n)
        if t1 and t2:
            print(f"  {'n=' + str(n):<38} {t1:>12.1f} {t2:>12.1f} {t1 / t2:>9.2f}x")

    print(f"\n{'1_subcommands_many benchmarks:':<40}")
    for n in [10, 100, 500, 1000]:
        t1 = results[v1]["subcommands_many"].get(n)
        t2 = results[v2]["subcommands_many"].get(n)
        if t1 and t2:
            print(f"  {'n=' + str(n):<38} {t1:>12.1f} {t2:>12.1f} {t1 / t2:>9.2f}x")

    print(f"\n{'2_subcommands_adversarial benchmarks:':<40}")
    for n in [1, 2, 3, 4, 5]:
        t1 = results[v1]["subcommands_adversarial"].get(n)
        t2 = results[v2]["subcommands_adversarial"].get(n)
        if t1 and t2:
            print(f"  {'n=' + str(n):<38} {t1:>12.1f} {t2:>12.1f} {t1 / t2:>9.2f}x")


if __name__ == "__main__":
    main()
