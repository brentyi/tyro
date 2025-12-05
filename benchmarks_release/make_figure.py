#!/usr/bin/env python3
"""Generate a polished benchmark comparison figure for tyro 0.9.35 vs 1.0.0."""

from pathlib import Path

import matplotlib.pyplot as plt

# Style configuration
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "-",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.axisbelow": True,
    }
)

# Colors
COLOR_OLD = "#888888"  # Gray for 0.9.35
COLOR_NEW = "#00897b"  # Teal for 1.0.0

# Data from benchmark results
data = {
    "environment": {
        "metrics": ["Site-packages\nsize (MB)", "Import\ntime (ms)"],
        "old": [6.41, 48.95],
        "new": [1.09, 22.17],
    },
    "0_many_args": {
        "n": [10, 100, 1000, 2000, 3000],
        "old": [2.2, 8.6, 85.0, 409.0, 694.0],
        "new": [0.4, 2.0, 17.9, 35.6, 54.9],
    },
    "1_subcommands_many": {
        "n": [10, 100, 500, 1000],
        "old": [5.5, 26.0, 112.1, 219.2],
        "new": [0.6, 1.7, 7.4, 14.2],
    },
    "2_subcommands_adversarial": {
        "n": [1, 2, 3, 4, 5],
        "old": [13.3, 45.9, 247.0, 1050.8, 3475.1],
        "new": [4.0, 4.1, 4.2, 4.2, 4.4],
    },
}


def add_speedup_annotation(ax, x, y_old, y_new, speedup):
    """Add a speedup annotation at a specific point."""
    ax.annotate(
        f"{speedup:.0f}x",
        xy=(x, y_new),
        xytext=(0, -15),
        textcoords="offset points",
        fontsize=8,
        color=COLOR_NEW,
        ha="center",
        fontweight="bold",
    )


def main():
    fig = plt.figure(figsize=(12, 5))

    # Create layout: small top row for environment metrics, main row for 3 benchmarks
    gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 2], hspace=0.4, wspace=0.3)

    # Top row: Environment metrics (bar charts side by side)
    ax_size = fig.add_subplot(gs[0, 0])
    ax_import = fig.add_subplot(gs[0, 1])

    # Site-packages size
    x = [0, 1]
    ax_size.bar(
        x,
        [data["environment"]["old"][0], data["environment"]["new"][0]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_size.set_xticks(x)
    ax_size.set_xticklabels(["0.9.35", "1.0.0"])
    ax_size.set_ylabel("MB")
    ax_size.set_title("Site-packages Size", fontsize=10)
    ax_size.bar_label(ax_size.containers[0], fmt="%.1f", fontsize=8)

    # Import time
    ax_import.bar(
        x,
        [data["environment"]["old"][1], data["environment"]["new"][1]],
        color=[COLOR_OLD, COLOR_NEW],
        alpha=0.85,
    )
    ax_import.set_xticks(x)
    ax_import.set_xticklabels(["0.9.35", "1.0.0"])
    ax_import.set_ylabel("ms")
    ax_import.set_title("Import Time", fontsize=10)
    ax_import.bar_label(ax_import.containers[0], fmt="%.0f", fontsize=8)

    # Legend in top-right cell
    ax_legend = fig.add_subplot(gs[0, 2])
    ax_legend.axis("off")
    ax_legend.plot(
        [], [], "o-", color=COLOR_OLD, label="0.9.35", linewidth=2, markersize=6
    )
    ax_legend.plot(
        [], [], "s-", color=COLOR_NEW, label="1.0.0", linewidth=2, markersize=6
    )
    ax_legend.legend(loc="center", fontsize=11, frameon=True, fancybox=True)

    # Bottom row: 3 benchmark charts
    # Panel 1: 0_many_args (line chart)
    ax2 = fig.add_subplot(gs[1, 0])
    d = data["0_many_args"]
    ax2.plot(
        d["n"],
        d["old"],
        "o-",
        color=COLOR_OLD,
        label="0.9.35",
        linewidth=2,
        markersize=6,
    )
    ax2.plot(
        d["n"],
        d["new"],
        "s-",
        color=COLOR_NEW,
        label="1.0.0",
        linewidth=2,
        markersize=6,
    )
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("Number of arguments")
    ax2.set_ylabel("Time (ms)")
    ax2.set_title("Many Arguments")

    # Add speedup annotation at largest n
    speedup = d["old"][-1] / d["new"][-1]
    ax2.annotate(
        f"{speedup:.0f}x",
        xy=(d["n"][-1], d["new"][-1]),
        xytext=(15, 15),
        textcoords="offset points",
        fontsize=10,
        color=COLOR_NEW,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=1.5),
    )

    # Panel 2: 1_subcommands_many (line chart)
    ax3 = fig.add_subplot(gs[1, 1])
    d = data["1_subcommands_many"]
    ax3.plot(
        d["n"],
        d["old"],
        "o-",
        color=COLOR_OLD,
        label="0.9.35",
        linewidth=2,
        markersize=6,
    )
    ax3.plot(
        d["n"],
        d["new"],
        "s-",
        color=COLOR_NEW,
        label="1.0.0",
        linewidth=2,
        markersize=6,
    )
    ax3.set_xscale("log")
    ax3.set_yscale("log")
    ax3.set_xlabel("Number of subcommands")
    ax3.set_ylabel("Time (ms)")
    ax3.set_title("Many Subcommands")

    # Add speedup annotation
    speedup = d["old"][-1] / d["new"][-1]
    ax3.annotate(
        f"{speedup:.0f}x",
        xy=(d["n"][-1], d["new"][-1]),
        xytext=(15, 15),
        textcoords="offset points",
        fontsize=10,
        color=COLOR_NEW,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=1.5),
    )

    # Panel 3: 2_subcommands_adversarial (line chart) - the dramatic one!
    ax4 = fig.add_subplot(gs[1, 2])
    d = data["2_subcommands_adversarial"]
    ax4.plot(
        d["n"],
        d["old"],
        "o-",
        color=COLOR_OLD,
        label="0.9.35",
        linewidth=2,
        markersize=6,
    )
    ax4.plot(
        d["n"],
        d["new"],
        "s-",
        color=COLOR_NEW,
        label="1.0.0",
        linewidth=2,
        markersize=6,
    )
    ax4.set_yscale("log")
    ax4.set_xlabel("Number of subcommand groups")
    ax4.set_ylabel("Time (ms)")
    ax4.set_title("Nested Subcommands")
    ax4.set_xticks(d["n"])

    # Add speedup annotation - this one is dramatic!
    speedup = d["old"][-1] / d["new"][-1]
    ax4.annotate(
        f"{speedup:.0f}x",
        xy=(d["n"][-1], d["new"][-1]),
        xytext=(-40, -20),
        textcoords="offset points",
        fontsize=10,
        color=COLOR_NEW,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=COLOR_NEW, lw=1.5),
    )

    # Add note about exponential vs constant
    ax4.text(
        0.95,
        0.85,
        "Exponential → Constant",
        transform=ax4.transAxes,
        fontsize=9,
        ha="right",
        va="top",
        color="#555",
        style="italic",
    )

    # Main title
    fig.suptitle(
        "tyro 1.0.0 Performance Improvements", fontsize=14, fontweight="bold", y=0.98
    )

    # Save figure
    output_dir = Path(__file__).parent
    fig.savefig(
        output_dir / "benchmark_figure.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    fig.savefig(
        output_dir / "benchmark_figure.pdf",
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )

    print("Figure saved to:")
    print(f"  {output_dir / 'benchmark_figure.png'}")
    print(f"  {output_dir / 'benchmark_figure.pdf'}")

    plt.show()


if __name__ == "__main__":
    main()
