#!/usr/bin/env python3
"""Generate multiple variants of the benchmark comparison figure."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = Path(__file__).parent / "figure_variants"
OUTPUT_DIR.mkdir(exist_ok=True)

# Data from benchmark results
DATA = {
    "environment": {
        "metrics": ["Site-packages\nsize (MB)", "Import\ntime (ms)"],
        "new": [2.01, 22.17],
        "old": [11.83, 48.95],
    },
    "0_many_args": {
        "n": [10, 100, 1000, 2000, 3000],
        "new": [0.4, 2.0, 17.9, 35.6, 54.9],
        "old": [2.2, 8.6, 85.0, 409.0, 694.0],
    },
    "1_subcommands_many": {
        "n": [10, 100, 500, 1000],
        "new": [0.6, 1.7, 7.4, 14.2],
        "old": [5.5, 26.0, 112.1, 219.2],
    },
    "2_subcommands_adversarial": {
        "n": [1, 2, 3, 4, 5],
        "new": [4.0, 4.1, 4.2, 4.2, 4.4],
        "old": [13.3, 45.9, 247.0, 1050.8, 3475.1],
    },
}

# Color palettes
PALETTES = {
    "gray_teal": ("#888888", "#00897b"),
    "gray_blue": ("#9e9e9e", "#1976d2"),
    "muted_coral": ("#bdbdbd", "#e57373"),
    "purple_green": ("#9575cd", "#4db6ac"),
    "orange_navy": ("#ffb74d", "#37474f"),
    "slate_emerald": ("#78909c", "#26a69a"),
}


def reset_style():
    """Reset to clean style."""
    plt.rcdefaults()
    plt.rcParams.update(
        {
            "font.family": "Inter",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.titleweight": 600,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.axisbelow": True,
        }
    )


def variant_1_current_fixed():
    """Current layout with fixed annotation overlap."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["gray_teal"]

    fig = plt.figure(figsize=(12, 5))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 2], hspace=0.4, wspace=0.3)

    # Top row: Environment metrics
    ax_size = fig.add_subplot(gs[0, 0])
    ax_import = fig.add_subplot(gs[0, 1])

    x = [0, 1]
    ax_size.bar(
        x,
        [DATA["environment"]["old"][0], DATA["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_size.set_xticks(x)
    ax_size.set_xticklabels(["0.9.35", "1.0.0"])
    ax_size.set_ylabel("MB")
    ax_size.set_title("Site-packages Size", fontsize=10)
    ax_size.bar_label(ax_size.containers[0], fmt="%.1f", fontsize=8)

    ax_import.bar(
        x,
        [DATA["environment"]["old"][1], DATA["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_import.set_xticks(x)
    ax_import.set_xticklabels(["0.9.35", "1.0.0"])
    ax_import.set_ylabel("ms")
    ax_import.set_title("Import Time", fontsize=10)
    ax_import.bar_label(ax_import.containers[0], fmt="%.0f", fontsize=8)

    # Legend
    ax_legend = fig.add_subplot(gs[0, 2])
    ax_legend.axis("off")
    ax_legend.plot(
        [], [], "o-", color=COLOR_OLD, label="0.9.35", linewidth=2, markersize=6
    )
    ax_legend.plot(
        [], [], "s-", color=COLOR_NEW, label="1.0.0", linewidth=2, markersize=6
    )
    ax_legend.legend(loc="center", fontsize=11)

    # Bottom row: Benchmarks
    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = fig.add_subplot(gs[1, i])
        d = DATA[key]
        ax.plot(d["n"], d["old"], "o-", color=COLOR_OLD, linewidth=2, markersize=6)
        ax.plot(d["n"], d["new"], "s-", color=COLOR_NEW, linewidth=2, markersize=6)
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)")
        ax.set_title(title)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])

        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}x",
            xy=(d["n"][-1], d["new"][-1]),
            xytext=(5, 20),
            textcoords="offset points",
            fontsize=10,
            color=COLOR_NEW,
            fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=1.5),
        )

    fig.suptitle(
        "tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold", y=0.98
    )
    fig.savefig(
        OUTPUT_DIR / "variant_01_current_fixed.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_2_horizontal_speedup_bars():
    """Horizontal bar chart showing all speedups."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["gray_teal"]

    # Calculate all speedups
    speedups = [
        (
            "Site-packages size",
            DATA["environment"]["old"][0] / DATA["environment"]["new"][0],
        ),
        ("Import time", DATA["environment"]["old"][1] / DATA["environment"]["new"][1]),
        (
            "Many args (n=100)",
            DATA["0_many_args"]["old"][1] / DATA["0_many_args"]["new"][1],
        ),
        (
            "Many args (n=3000)",
            DATA["0_many_args"]["old"][4] / DATA["0_many_args"]["new"][4],
        ),
        (
            "Subcommands (n=100)",
            DATA["1_subcommands_many"]["old"][1] / DATA["1_subcommands_many"]["new"][1],
        ),
        (
            "Subcommands (n=1000)",
            DATA["1_subcommands_many"]["old"][3] / DATA["1_subcommands_many"]["new"][3],
        ),
        (
            "Nested (n=3)",
            DATA["2_subcommands_adversarial"]["old"][2]
            / DATA["2_subcommands_adversarial"]["new"][2],
        ),
        (
            "Nested (n=5)",
            DATA["2_subcommands_adversarial"]["old"][4]
            / DATA["2_subcommands_adversarial"]["new"][4],
        ),
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    labels = [s[0] for s in speedups]
    values = [s[1] for s in speedups]

    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=COLOR_NEW, alpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Speedup Factor (×)")
    ax.set_xscale("log")
    ax.axvline(x=1, color="gray", linestyle="--", alpha=0.5)

    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(
            val * 1.1,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}×",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=COLOR_NEW,
        )

    ax.set_title("tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold")
    fig.savefig(
        OUTPUT_DIR / "variant_02_speedup_bars.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_3_all_line_charts():
    """All benchmarks as line charts in a single row."""
    reset_style()
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(
        1, 5, figsize=(15, 3.5), width_ratios=[1, 1, 1.2, 1.2, 1.2]
    )

    # Dependency tree size
    ax = axes[0]
    x = [0, 1]
    ax.bar(
        x,
        [DATA["environment"]["old"][0], DATA["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["0.9.35", "1.0.0"])
    ax.set_ylabel("MB")
    ax.set_title("Dependency\ntree")
    ax.bar_label(ax.containers[0], fmt="%.1f", fontsize=8)

    # Import time
    ax = axes[1]
    ax.bar(
        x,
        [DATA["environment"]["old"][1], DATA["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["0.9.35", "1.0.0"])
    ax.set_ylabel("ms")
    ax.set_title("Import\ntime")
    ax.bar_label(ax.containers[0], fmt="%.0f", fontsize=8)

    # Benchmarks
    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Many Arguments", "Args"),
            ("1_subcommands_many", "Many Subcommands", "Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands", "Groups"),
        ]
    ):
        ax = axes[i + 2]  # Start from axes[2]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=5,
            label="0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=5,
            label="1.0.0",
        )
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])
        if i == 0:
            ax.legend(fontsize=8)

    fig.suptitle("tyro 1.0.0 Metrics", fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "variant_03_single_row.png", dpi=150, bbox_inches="tight")
    plt.close()


def figure_environment():
    """Just dependency tree and import time."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"  # Not bold
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(1, 2, figsize=(6, 4))

    # Dependency tree size
    ax = axes[0]
    x = [0, 1]
    bars1 = ax.bar(
        x,
        [DATA["environment"]["old"][0], DATA["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax.set_xticks([])
    ax.set_ylabel("MB")
    ax.set_title("Dependency tree")
    ax.bar_label(ax.containers[0], fmt="%.1f MB", fontsize=9)

    # Import time
    ax = axes[1]
    bars2 = ax.bar(
        x,
        [DATA["environment"]["old"][1], DATA["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax.set_xticks([])
    ax.set_ylabel("ms")
    ax.set_title("Import time")
    ax.bar_label(ax.containers[0], fmt="%.0f ms", fontsize=9)

    # Legend below plots
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=COLOR_OLD, label="tyro==0.9.35"),
        Patch(facecolor=COLOR_NEW, label="tyro==1.0.0"),
    ]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=2,
        fontsize=9,
        frameon=False,
        bbox_to_anchor=(0.5, 0.12),
    )

    fig.suptitle("tyro 1.0.0 Metrics", fontsize=13)
    plt.tight_layout()
    fig.subplots_adjust(bottom=0.25, top=0.80)
    fig.savefig(OUTPUT_DIR / "figure_environment.png", dpi=150, bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / "figure_environment.pdf", bbox_inches="tight")
    plt.close()


def figure_dependency_tree():
    """Just dependency tree as horizontal bar - wide and short."""
    reset_style()
    plt.rcParams["axes.titleweight"] = 600
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, ax = plt.subplots(figsize=(6, 1.75))

    y = [1, 0]
    values = [DATA["environment"]["old"][0], DATA["environment"]["new"][0]]
    colors = [COLOR_OLD, COLOR_NEW]

    bars = ax.barh(y, values, color=colors, height=0.6)
    ax.set_yticks([])
    ax.set_xlabel("MB")
    ax.set_title("Dependency tree size", fontsize=11)

    # Add value labels to the right of bars
    for bar, val in zip(bars, values):
        ax.text(
            val + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f} MB",
            va="center",
            fontsize=9,
        )

    # Legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=COLOR_OLD, label="tyro==0.9.35"),
        Patch(facecolor=COLOR_NEW, label="tyro==1.0.0"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9, frameon=False)

    ax.set_xlim(0, max(values) * 1.4)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "figure_dependency_tree.png", dpi=150, bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / "figure_dependency_tree.pdf", bbox_inches="tight")
    plt.close()


def figure_import_time():
    """Just import time as horizontal bar - wide and short."""
    reset_style()
    plt.rcParams["axes.titleweight"] = 600
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, ax = plt.subplots(figsize=(6, 1.75))

    y = [1, 0]
    values = [DATA["environment"]["old"][1], DATA["environment"]["new"][1]]
    colors = [COLOR_OLD, COLOR_NEW]

    bars = ax.barh(y, values, color=colors, height=0.6)
    ax.set_yticks([])
    ax.set_xlabel("ms")
    ax.set_title("Import time", fontsize=11)

    # Add value labels to the right of bars
    for bar, val in zip(bars, values):
        ax.text(
            val + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f} ms",
            va="center",
            fontsize=9,
        )

    # Legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=COLOR_OLD, label="tyro==0.9.35"),
        Patch(facecolor=COLOR_NEW, label="tyro==1.0.0"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9, frameon=False)

    ax.set_xlim(0, max(values) * 1.4)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "figure_import_time.png", dpi=150, bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / "figure_import_time.pdf", bbox_inches="tight")
    plt.close()


def figure_benchmarks():
    """Just the benchmark plots."""
    reset_style()
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Many Arguments", "Args"),
            ("1_subcommands_many", "Many Subcommands", "Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands", "Groups"),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("tyro 1.0.0 Benchmarks", fontsize=13)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "figure_benchmarks.png", dpi=150, bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / "figure_benchmarks.pdf", bbox_inches="tight")
    plt.close()


def figure_benchmarks_linear():
    """Benchmark plots with linear y-axis (log x-axis for first two)."""
    reset_style()
    # plt.rcParams["axes.titleweight"] = "normal"  # Not bold
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        # Linear y-axis (no set_yscale)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "figure_benchmarks_linear.png", dpi=150, bbox_inches="tight"
    )
    fig.savefig(OUTPUT_DIR / "figure_benchmarks_linear.pdf", bbox_inches="tight")
    plt.close()


def figure_benchmarks_linear_xy():
    """Benchmark plots with linear x and y axes."""
    reset_style()
    plt.rcParams["axes.titleweight"] = 600  # Not bold
    COLOR_OLD = "#cccccc"  # Light gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )
        # Linear x and y axes
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=11)
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "figure_benchmarks_linear_xy.png", dpi=150, bbox_inches="tight"
    )
    fig.savefig(OUTPUT_DIR / "figure_benchmarks_linear_xy.pdf", bbox_inches="tight")
    plt.close()


def bench_variant_a_darker_gray():
    """Darker gray for better contrast."""
    reset_style()
    # plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#999999"  # Darker gray
    COLOR_NEW = "#00bcd4"  # Cyan

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_a_darker_gray.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_b_with_speedups():
    """Add speedup annotations."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    benchmarks = [
        ("0_many_args", "Argument Count vs Runtime", "Arguments"),
        ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
        (
            "2_subcommands_adversarial",
            "Subcommand Depth vs Runtime",
            "Depth",
        ),
    ]

    for i, (key, title, xlabel) in enumerate(benchmarks):
        ax = axes[i]
        d = DATA[key]
        ax.plot(
            d["n"],
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            d["n"],
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])
        if i == 0:
            ax.legend(fontsize=9)

        # Add speedup annotation
        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}×",
            xy=(d["n"][-1], d["new"][-1]),
            xytext=(0, 15),
            textcoords="offset points",
            fontsize=11,
            color=COLOR_NEW,
            fontweight="bold",
            ha="center",
        )

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_b_with_speedups.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_c_fill_between():
    """Fill between lines to show gap."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        # Fill between
        ax.fill_between(x_plot, d["old"], d["new"], alpha=0.2, color=COLOR_NEW)
        ax.plot(
            x_plot,
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )

        ax.set_xticks(x_plot)
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_c_fill_between.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_d_linear_x():
    """Linear x-axis with clean labels."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        ax.plot(
            x_plot,
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )

        # Clean x-axis labels
        labels = []
        for n in d["n"]:
            if n >= 1000:
                labels.append(f"{n // 1000}k")
            else:
                labels.append(str(n))
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_d_linear_x.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_e_minimal():
    """Minimal style - no grid, lighter."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    plt.rcParams["axes.grid"] = False
    COLOR_OLD = "#bbbbbb"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        ax.plot(
            x_plot,
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=7,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2.5,
            markersize=7,
            label="tyro==1.0.0",
        )

        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        ax.spines["left"].set_color("#cccccc")
        ax.spines["bottom"].set_color("#cccccc")
        if i == 0:
            ax.legend(fontsize=9, frameon=False)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_e_minimal.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_f_shared_legend():
    """Shared legend outside plots."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        (line1,) = ax.plot(
            x_plot, d["old"], "o-", color=COLOR_OLD, linewidth=2, markersize=6
        )
        (line2,) = ax.plot(
            x_plot, d["new"], "s-", color=COLOR_NEW, linewidth=2, markersize=6
        )

        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)

    # Shared legend at bottom
    fig.legend(
        [line1, line2],
        ["tyro==0.9.35", "tyro==1.0.0"],
        loc="lower center",
        ncol=2,
        fontsize=10,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.subplots_adjust(bottom=0.18)
    fig.savefig(
        OUTPUT_DIR / "bench_variant_f_shared_legend.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_g_wider_adversarial():
    """Make adversarial plot wider."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(14, 3.5), width_ratios=[1, 1, 1.3])

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        ax.fill_between(x_plot, d["old"], d["new"], alpha=0.15, color=COLOR_NEW)
        ax.plot(
            x_plot,
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
            label="tyro==1.0.0",
        )

        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if i == 0:
            ax.legend(fontsize=9)

        # Add speedup
        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}×",
            xy=(x_plot[-1], d["new"][-1]),
            xytext=(0, 15),
            textcoords="offset points",
            fontsize=11,
            color=COLOR_NEW,
            fontweight="bold",
            ha="center",
        )

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_g_wider_adversarial.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.close()


def bench_variant_h_thicker_lines():
    """Thicker lines and larger markers."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        ax.plot(
            x_plot,
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=3,
            markersize=8,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=3,
            markersize=8,
            label="tyro==1.0.0",
        )

        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_h_thicker_lines.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_i_dashed_old():
    """Dashed line for old version."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#999999"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        ax.plot(
            x_plot,
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2.5,
            markersize=6,
            label="tyro==1.0.0",
        )

        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)
        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_i_dashed_old.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def bench_variant_j_combined():
    """Combined: fill, speedups, linear x, clean labels."""
    reset_style()
    plt.rcParams["axes.titleweight"] = "normal"
    COLOR_OLD = "#aaaaaa"
    COLOR_NEW = "#00bcd4"

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Argument Count vs Runtime", "Arguments"),
            ("1_subcommands_many", "Subcommand Count vs Runtime", "Options"),
            (
                "2_subcommands_adversarial",
                "Subcommand Depth vs Runtime",
                "Depth",
            ),
        ]
    ):
        ax = axes[i]
        d = DATA[key]
        x_plot = list(range(len(d["n"])))

        # Fill and lines
        ax.fill_between(x_plot, d["old"], d["new"], alpha=0.15, color=COLOR_NEW)
        ax.plot(
            x_plot,
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
            label="tyro==0.9.35",
        )
        ax.plot(
            x_plot,
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2.5,
            markersize=6,
            label="tyro==1.0.0",
        )

        # Clean labels
        labels = [f"{n // 1000}k" if n >= 1000 else str(n) for n in d["n"]]
        ax.set_xticks(x_plot)
        ax.set_xticklabels(labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontsize=10)

        # Speedup annotation
        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}×",
            xy=(x_plot[-1], d["new"][-1]),
            xytext=(5, 10),
            textcoords="offset points",
            fontsize=11,
            color=COLOR_NEW,
            fontweight="bold",
            ha="left",
        )

        if i == 0:
            ax.legend(fontsize=9)

    # fig.suptitle("Runtime Improvements in tyro 1.0.0", fontsize=13)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "bench_variant_j_combined.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_3b_single_row_clearer():
    """Single row with clearer before/after contrast."""
    reset_style()
    COLOR_OLD = "#aaaaaa"  # Light gray, more muted
    COLOR_NEW = "#00897b"  # Teal, saturated

    fig, axes = plt.subplots(1, 4, figsize=(14, 4))

    # Environment
    ax = axes[0]
    x = np.arange(2)
    width = 0.35
    bars_old = ax.bar(
        x - width / 2,
        DATA["environment"]["old"],
        width,
        color=COLOR_OLD,
        label="0.9.35",
        alpha=0.7,
    )
    bars_new = ax.bar(
        x + width / 2, DATA["environment"]["new"], width, color=COLOR_NEW, label="1.0.0"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Size (MB)", "Import (ms)"])
    ax.set_title("Environment", fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")

    # Add speedup labels
    for j, (old, new) in enumerate(
        zip(DATA["environment"]["old"], DATA["environment"]["new"])
    ):
        speedup = old / new
        ax.annotate(
            f"{speedup:.1f}×",
            xy=(j, max(old, new) + 2),
            ha="center",
            fontsize=9,
            color=COLOR_NEW,
            fontweight="bold",
        )

    # Benchmarks with fill between
    for i, (key, title, xlabel) in enumerate(
        [
            ("0_many_args", "Many Arguments", "n"),
            ("1_subcommands_many", "Many Subcommands", "n"),
            ("2_subcommands_adversarial", "Nested Subcommands", "n"),
        ]
    ):
        ax = axes[i + 1]
        d = DATA[key]

        # Fill between to show the gap
        if key == "2_subcommands_adversarial":
            x_vals = d["n"]
        else:
            x_vals = np.array(d["n"])

        # Plot with fill
        ax.fill_between(
            range(len(d["n"])), d["old"], d["new"], alpha=0.15, color=COLOR_NEW
        )
        ax.plot(
            range(len(d["n"])),
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=2,
            markersize=7,
            label="0.9.35",
            alpha=0.7,
        )
        ax.plot(
            range(len(d["n"])),
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2.5,
            markersize=7,
            label="1.0.0",
        )

        ax.set_yscale("log")
        ax.set_xticks(range(len(d["n"])))
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontweight="bold")

        # Add speedup annotation
        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}×",
            xy=(len(d["n"]) - 1, d["new"][-1]),
            xytext=(5, -10),
            textcoords="offset points",
            fontsize=11,
            color=COLOR_NEW,
            fontweight="bold",
        )

    fig.suptitle("tyro 1.0.0 Performance", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "variant_03b_single_row_clearer.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_3c_single_row_labels():
    """Single row with direct labels on lines."""
    reset_style()
    COLOR_OLD = "#999999"
    COLOR_NEW = "#00796b"

    fig, axes = plt.subplots(1, 4, figsize=(14, 4))

    # Environment
    ax = axes[0]
    x = np.arange(2)
    width = 0.3
    ax.bar(x - width / 2, DATA["environment"]["old"], width, color=COLOR_OLD, alpha=0.6)
    ax.bar(x + width / 2, DATA["environment"]["new"], width, color=COLOR_NEW)
    ax.set_xticks(x)
    ax.set_xticklabels(["Size (MB)", "Import (ms)"])
    ax.set_title("Environment", fontweight="bold")

    # Labels on bars
    for j, (old, new) in enumerate(
        zip(DATA["environment"]["old"], DATA["environment"]["new"])
    ):
        ax.text(
            j - width / 2,
            old + 1,
            f"{old:.1f}",
            ha="center",
            fontsize=8,
            color=COLOR_OLD,
        )
        ax.text(
            j + width / 2,
            new + 1,
            f"{new:.1f}",
            ha="center",
            fontsize=8,
            color=COLOR_NEW,
        )

    # Benchmarks
    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = axes[i + 1]
        d = DATA[key]
        x_range = range(len(d["n"]))

        # Old version - dashed, muted
        (line_old,) = ax.plot(
            x_range,
            d["old"],
            "o--",
            color=COLOR_OLD,
            linewidth=1.5,
            markersize=6,
            alpha=0.7,
        )
        # New version - solid, bold
        (line_new,) = ax.plot(
            x_range, d["new"], "s-", color=COLOR_NEW, linewidth=2.5, markersize=7
        )

        ax.set_yscale("log")
        ax.set_xticks(x_range)
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontweight="bold")

        # Direct labels at end of lines
        ax.text(
            len(d["n"]) - 0.7,
            d["old"][-1],
            "0.9.35",
            fontsize=8,
            color=COLOR_OLD,
            va="center",
            alpha=0.8,
        )
        ax.text(
            len(d["n"]) - 0.7,
            d["new"][-1],
            "1.0.0",
            fontsize=8,
            color=COLOR_NEW,
            va="center",
            fontweight="bold",
        )

        # Speedup
        speedup = d["old"][-1] / d["new"][-1]
        mid_y = np.sqrt(d["old"][-1] * d["new"][-1])  # geometric mean for log scale
        ax.annotate(
            f"{speedup:.0f}× faster",
            xy=(len(d["n"]) - 1.5, mid_y),
            fontsize=10,
            color=COLOR_NEW,
            fontweight="bold",
            ha="center",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor=COLOR_NEW,
                alpha=0.9,
            ),
        )

    fig.suptitle(
        "tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "variant_03c_single_row_labels.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_3d_single_row_bold():
    """Single row with bold new version, faded old version."""
    reset_style()
    COLOR_OLD = "#cccccc"  # Very light
    COLOR_NEW = "#00897b"  # Strong teal

    fig, axes = plt.subplots(1, 4, figsize=(14, 4))

    # Environment
    ax = axes[0]
    x = np.arange(2)
    width = 0.35
    ax.bar(
        x - width / 2,
        DATA["environment"]["old"],
        width,
        color=COLOR_OLD,
        edgecolor="#999999",
        linewidth=1,
    )
    ax.bar(x + width / 2, DATA["environment"]["new"], width, color=COLOR_NEW)
    ax.set_xticks(x)
    ax.set_xticklabels(["Size\n(MB)", "Import\n(ms)"], fontsize=9)
    ax.set_title("Environment", fontweight="bold")

    # Add a simple legend
    ax.bar([], [], color=COLOR_OLD, label="Before (0.9.35)")
    ax.bar([], [], color=COLOR_NEW, label="After (1.0.0)")
    ax.legend(fontsize=8, loc="upper right")

    # Benchmarks
    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = axes[i + 1]
        d = DATA[key]
        x_range = range(len(d["n"]))

        # Old: thin dashed line with hollow markers
        ax.plot(
            x_range,
            d["old"],
            "o--",
            color="#888888",
            linewidth=1.5,
            markersize=8,
            markerfacecolor="white",
            markeredgewidth=1.5,
            markeredgecolor="#888888",
        )
        # New: thick solid line with filled markers
        ax.plot(x_range, d["new"], "s-", color=COLOR_NEW, linewidth=3, markersize=8)

        ax.set_yscale("log")
        ax.set_xticks(x_range)
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)" if i == 0 else "")
        ax.set_title(title, fontweight="bold")

        # Big speedup number
        speedup = d["old"][-1] / d["new"][-1]
        ax.text(
            0.95,
            0.95,
            f"{speedup:.0f}×",
            transform=ax.transAxes,
            fontsize=16,
            fontweight="bold",
            color=COLOR_NEW,
            ha="right",
            va="top",
        )

    fig.suptitle("tyro 1.0.0 Performance", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "variant_03d_single_row_bold.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_4_dark_theme():
    """Dark theme variant."""
    plt.style.use("dark_background")
    plt.rcParams.update(
        {
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.2,
        }
    )

    COLOR_OLD = "#666666"
    COLOR_NEW = "#4dd0e1"  # Cyan

    fig = plt.figure(figsize=(12, 5))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 2], hspace=0.4, wspace=0.3)

    # Top row
    ax_size = fig.add_subplot(gs[0, 0])
    ax_import = fig.add_subplot(gs[0, 1])

    x = [0, 1]
    ax_size.bar(
        x,
        [DATA["environment"]["old"][0], DATA["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax_size.set_xticks(x)
    ax_size.set_xticklabels(["0.9.35", "1.0.0"])
    ax_size.set_ylabel("MB")
    ax_size.set_title("Site-packages Size")

    ax_import.bar(
        x,
        [DATA["environment"]["old"][1], DATA["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
    )
    ax_import.set_xticks(x)
    ax_import.set_xticklabels(["0.9.35", "1.0.0"])
    ax_import.set_ylabel("ms")
    ax_import.set_title("Import Time")

    ax_legend = fig.add_subplot(gs[0, 2])
    ax_legend.axis("off")
    ax_legend.plot([], [], "o-", color=COLOR_OLD, label="0.9.35", linewidth=2)
    ax_legend.plot([], [], "s-", color=COLOR_NEW, label="1.0.0", linewidth=2)
    ax_legend.legend(loc="center", fontsize=11)

    # Bottom row
    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = fig.add_subplot(gs[1, i])
        d = DATA[key]
        ax.plot(d["n"], d["old"], "o-", color=COLOR_OLD, linewidth=2, markersize=6)
        ax.plot(d["n"], d["new"], "s-", color=COLOR_NEW, linewidth=2, markersize=6)
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)")
        ax.set_title(title)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])

    fig.suptitle("tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold")
    fig.savefig(
        OUTPUT_DIR / "variant_04_dark_theme.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="#1a1a1a",
    )
    plt.close()


def variant_5_minimalist():
    """Clean minimalist design."""
    reset_style()
    plt.rcParams.update(
        {
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "axes.grid": False,
            "ytick.left": False,
        }
    )

    COLOR_OLD, COLOR_NEW = "#cccccc", "#00796b"

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = axes[i]
        d = DATA[key]

        ax.fill_between(
            range(len(d["n"])), d["old"], alpha=0.3, color=COLOR_OLD, label="0.9.35"
        )
        ax.fill_between(
            range(len(d["n"])), d["new"], alpha=0.5, color=COLOR_NEW, label="1.0.0"
        )
        ax.plot(
            range(len(d["n"])),
            d["old"],
            "o-",
            color=COLOR_OLD,
            linewidth=2,
            markersize=6,
        )
        ax.plot(
            range(len(d["n"])),
            d["new"],
            "s-",
            color=COLOR_NEW,
            linewidth=2,
            markersize=6,
        )

        ax.set_yscale("log")
        ax.set_xticks(range(len(d["n"])))
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_title(title, fontsize=12, fontweight="bold")

        if i == 0:
            ax.legend(loc="upper left", fontsize=9)

        speedup = d["old"][-1] / d["new"][-1]
        ax.text(
            0.95,
            0.95,
            f"{speedup:.0f}×",
            transform=ax.transAxes,
            fontsize=14,
            fontweight="bold",
            color=COLOR_NEW,
            ha="right",
            va="top",
        )

    fig.suptitle("tyro 1.0.0", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "variant_05_minimalist.png", dpi=150, bbox_inches="tight")
    plt.close()


def variant_6_grouped_bars():
    """All metrics as grouped bar charts."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["gray_blue"]

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    # Environment
    ax = axes[0, 0]
    x = np.arange(2)
    width = 0.35
    ax.bar(
        x - width / 2,
        DATA["environment"]["old"],
        width,
        label="0.9.35",
        color=COLOR_OLD,
    )
    ax.bar(
        x + width / 2, DATA["environment"]["new"], width, label="1.0.0", color=COLOR_NEW
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Size (MB)", "Import (ms)"])
    ax.set_title("Environment Metrics")
    ax.legend()

    # Each benchmark as grouped bars (last value)
    benchmarks = [
        ("0_many_args", "Many Arguments", axes[0, 1]),
        ("1_subcommands_many", "Many Subcommands", axes[1, 0]),
        ("2_subcommands_adversarial", "Nested Subcommands", axes[1, 1]),
    ]

    for key, title, ax in benchmarks:
        d = DATA[key]
        x = np.arange(len(d["n"]))
        ax.bar(x - width / 2, d["old"], width, label="0.9.35", color=COLOR_OLD)
        ax.bar(x + width / 2, d["new"], width, label="1.0.0", color=COLOR_NEW)
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in d["n"]])
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)")
        ax.set_title(title)
        ax.set_yscale("log")

    fig.suptitle("tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(
        OUTPUT_DIR / "variant_06_grouped_bars.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_7_slope_chart():
    """Slope chart showing before/after."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["gray_teal"]

    fig, ax = plt.subplots(figsize=(8, 8))

    # Collect all benchmark points at max n
    items = [
        ("Size (MB)", DATA["environment"]["old"][0], DATA["environment"]["new"][0]),
        ("Import (ms)", DATA["environment"]["old"][1], DATA["environment"]["new"][1]),
        ("Args n=3000", DATA["0_many_args"]["old"][3], DATA["0_many_args"]["new"][3]),
        (
            "Subcmds n=1000",
            DATA["1_subcommands_many"]["old"][3],
            DATA["1_subcommands_many"]["new"][3],
        ),
        (
            "Nested n=5",
            DATA["2_subcommands_adversarial"]["old"][4],
            DATA["2_subcommands_adversarial"]["new"][4],
        ),
    ]

    for i, (label, old, new) in enumerate(items):
        y_old = len(items) - i - 0.1
        y_new = len(items) - i + 0.1

        ax.scatter([0], [y_old], s=100, color=COLOR_OLD, zorder=3)
        ax.scatter([1], [y_new], s=100, color=COLOR_NEW, zorder=3)
        ax.plot([0, 1], [y_old, y_new], color="#cccccc", linewidth=1, zorder=1)

        ax.text(
            -0.05,
            y_old,
            f"{old:.1f}",
            ha="right",
            va="center",
            fontsize=9,
            color=COLOR_OLD,
        )
        ax.text(
            1.05,
            y_new,
            f"{new:.1f}",
            ha="left",
            va="center",
            fontsize=9,
            color=COLOR_NEW,
        )
        ax.text(
            0.5, (y_old + y_new) / 2 + 0.3, label, ha="center", va="bottom", fontsize=9
        )

        speedup = old / new
        ax.text(
            0.5,
            (y_old + y_new) / 2 - 0.15,
            f"{speedup:.0f}×",
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            color=COLOR_NEW,
        )

    ax.set_xlim(-0.5, 1.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["0.9.35", "1.0.0"], fontsize=12)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_title("tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold")

    fig.savefig(OUTPUT_DIR / "variant_07_slope_chart.png", dpi=150, bbox_inches="tight")
    plt.close()


def variant_8_compact_summary():
    """Compact single-panel summary."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["purple_green"]

    fig, ax = plt.subplots(figsize=(10, 5))

    # Just show the adversarial benchmark prominently with others as inset
    d = DATA["2_subcommands_adversarial"]
    ax.plot(
        d["n"],
        d["old"],
        "o-",
        color=COLOR_OLD,
        linewidth=3,
        markersize=10,
        label="0.9.35",
    )
    ax.plot(
        d["n"],
        d["new"],
        "s-",
        color=COLOR_NEW,
        linewidth=3,
        markersize=10,
        label="1.0.0",
    )
    ax.set_yscale("log")
    ax.set_xticks(d["n"])
    ax.set_xlabel("Number of subcommand groups", fontsize=12)
    ax.set_ylabel("Time (ms)", fontsize=12)
    ax.legend(fontsize=12, loc="upper left")

    speedup = d["old"][-1] / d["new"][-1]
    ax.annotate(
        f"{speedup:.0f}× faster",
        xy=(5, d["new"][-1]),
        xytext=(4, 20),
        fontsize=14,
        fontweight="bold",
        color=COLOR_NEW,
        arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=2),
    )

    ax.text(
        0.98,
        0.98,
        "Exponential → Constant time!",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        style="italic",
        color="#555",
    )

    # Inset for other benchmarks
    ax_inset = ax.inset_axes([0.55, 0.55, 0.4, 0.4])
    d2 = DATA["0_many_args"]
    ax_inset.plot(
        d2["n"], d2["old"], "o-", color=COLOR_OLD, linewidth=1.5, markersize=4
    )
    ax_inset.plot(
        d2["n"], d2["new"], "s-", color=COLOR_NEW, linewidth=1.5, markersize=4
    )
    ax_inset.set_xscale("log")
    ax_inset.set_yscale("log")
    ax_inset.set_title("Many Arguments", fontsize=9)
    ax_inset.tick_params(labelsize=7)

    ax.set_title(
        "tyro 1.0.0: Nested Subcommands Benchmark", fontsize=14, fontweight="bold"
    )
    fig.savefig(
        OUTPUT_DIR / "variant_08_compact_summary.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def variant_9_orange_navy():
    """Warm color palette variant."""
    reset_style()
    COLOR_OLD, COLOR_NEW = PALETTES["orange_navy"]

    fig = plt.figure(figsize=(12, 5))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 2], hspace=0.4, wspace=0.3)

    # Top row
    ax_size = fig.add_subplot(gs[0, 0])
    ax_import = fig.add_subplot(gs[0, 1])

    x = [0, 1]
    ax_size.bar(
        x,
        [DATA["environment"]["old"][0], DATA["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_size.set_xticks(x)
    ax_size.set_xticklabels(["0.9.35", "1.0.0"])
    ax_size.set_ylabel("MB")
    ax_size.set_title("Site-packages Size")
    ax_size.bar_label(ax_size.containers[0], fmt="%.1f", fontsize=8)

    ax_import.bar(
        x,
        [DATA["environment"]["old"][1], DATA["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_import.set_xticks(x)
    ax_import.set_xticklabels(["0.9.35", "1.0.0"])
    ax_import.set_ylabel("ms")
    ax_import.set_title("Import Time")
    ax_import.bar_label(ax_import.containers[0], fmt="%.0f", fontsize=8)

    ax_legend = fig.add_subplot(gs[0, 2])
    ax_legend.axis("off")
    ax_legend.plot([], [], "o-", color=COLOR_OLD, label="0.9.35", linewidth=2)
    ax_legend.plot([], [], "s-", color=COLOR_NEW, label="1.0.0", linewidth=2)
    ax_legend.legend(loc="center", fontsize=11)

    # Bottom row
    for i, (key, title) in enumerate(
        [
            ("0_many_args", "Many Arguments"),
            ("1_subcommands_many", "Many Subcommands"),
            ("2_subcommands_adversarial", "Nested Subcommands"),
        ]
    ):
        ax = fig.add_subplot(gs[1, i])
        d = DATA[key]
        ax.plot(d["n"], d["old"], "o-", color=COLOR_OLD, linewidth=2, markersize=6)
        ax.plot(d["n"], d["new"], "s-", color=COLOR_NEW, linewidth=2, markersize=6)
        if key != "2_subcommands_adversarial":
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("n")
        ax.set_ylabel("Time (ms)")
        ax.set_title(title)
        if key == "2_subcommands_adversarial":
            ax.set_xticks(d["n"])

        speedup = d["old"][-1] / d["new"][-1]
        ax.annotate(
            f"{speedup:.0f}×",
            xy=(d["n"][-1], d["new"][-1]),
            xytext=(5, 20),
            textcoords="offset points",
            fontsize=10,
            color=COLOR_NEW,
            fontweight="bold",
            arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=1.5),
        )

    fig.suptitle("tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold")
    fig.savefig(OUTPUT_DIR / "variant_09_orange_navy.png", dpi=150, bbox_inches="tight")
    plt.close()


def variant_10_focus_on_speedups():
    """Focus purely on speedup numbers with clean design."""
    reset_style()
    COLOR_NEW = "#00897b"

    fig, ax = plt.subplots(figsize=(8, 6))

    categories = [
        "Dependencies\n(6× smaller)",
        "Import time\n(2× faster)",
        "Many args\n(13× faster)",
        "Many subcmds\n(15× faster)",
        "Nested subcmds\n(790× faster)",
    ]

    speedups = [
        DATA["environment"]["old"][0] / DATA["environment"]["new"][0],
        DATA["environment"]["old"][1] / DATA["environment"]["new"][1],
        DATA["0_many_args"]["old"][4] / DATA["0_many_args"]["new"][4],
        DATA["1_subcommands_many"]["old"][3] / DATA["1_subcommands_many"]["new"][3],
        DATA["2_subcommands_adversarial"]["old"][4]
        / DATA["2_subcommands_adversarial"]["new"][4],
    ]

    y = np.arange(len(categories))
    bars = ax.barh(y, speedups, color=COLOR_NEW, alpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=11)
    ax.set_xlabel("Improvement Factor", fontsize=12)
    ax.set_xscale("log")
    ax.set_xlim(1, 1500)

    for bar, val in zip(bars, speedups):
        ax.text(
            val * 1.15,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}×",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=COLOR_NEW,
        )

    ax.axvline(x=1, color="gray", linestyle="--", alpha=0.3)
    ax.set_title("tyro 1.0.0 Improvements Over 0.9.35", fontsize=14, fontweight="bold")

    fig.savefig(
        OUTPUT_DIR / "variant_10_speedup_focus.png", dpi=150, bbox_inches="tight"
    )
    plt.close()


def main():
    figure_benchmarks_linear_xy()
    figure_dependency_tree()
    figure_import_time()
    # bench_variant_a_darker_gray()
    # bench_variant_b_with_speedups()
    # bench_variant_c_fill_between()
    # bench_variant_d_linear_x()
    # bench_variant_e_minimal()
    # bench_variant_f_shared_legend()
    # bench_variant_g_wider_adversarial()
    # bench_variant_h_thicker_lines()
    # bench_variant_i_dashed_old()
    # bench_variant_j_combined()
    return
    print("Generating 10 figure variants...")

    variant_1_current_fixed()
    print("  1. Current layout (fixed) - variant_01_current_fixed.png")

    variant_2_horizontal_speedup_bars()
    print("  2. Horizontal speedup bars - variant_02_speedup_bars.png")

    variant_3_all_line_charts()
    print("  3. Single row layout - variant_03_single_row.png")

    variant_3b_single_row_clearer()
    print("  3b. Single row (clearer) - variant_03b_single_row_clearer.png")

    variant_3c_single_row_labels()
    print("  3c. Single row (labels) - variant_03c_single_row_labels.png")

    variant_3d_single_row_bold()
    print("  3d. Single row (bold) - variant_03d_single_row_bold.png")

    variant_4_dark_theme()
    print("  4. Dark theme - variant_04_dark_theme.png")

    variant_5_minimalist()
    print("  5. Minimalist with fill - variant_05_minimalist.png")

    variant_6_grouped_bars()
    print("  6. Grouped bar charts - variant_06_grouped_bars.png")

    variant_7_slope_chart()
    print("  7. Slope chart - variant_07_slope_chart.png")

    variant_8_compact_summary()
    print("  8. Compact with inset - variant_08_compact_summary.png")

    variant_9_orange_navy()
    print("  9. Orange/navy palette - variant_09_orange_navy.png")

    variant_10_focus_on_speedups()
    print("  10. Speedup focus - variant_10_speedup_focus.png")

    print(f"\nAll variants saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
