import argparse
import json
import os
import matplotlib
# Force Matplotlib to use the non-interactive 'Agg' backend before importing pyplot
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import truncnorm

DEFAULT_VERSION_LABELS = [
    "V1 (Baseline)",
    "V2 (Hardware Pulse)",
    "V3 (Hardware Timing)",
    "V4 (Hybrid)",
]

DEFAULT_NORMAL_FILES = [
    "../metrics/metrics_V1.json",
    "../metrics/metrics_V2.json",
    "../metrics/metrics_V3.json",
    "../metrics/metrics_V4.json",
]

DEFAULT_LOAD_FILES = [
    "../metrics/metrics_load_V1.json",
    "../metrics/metrics_load_V2.json",
    "../metrics/metrics_load_V3.json",
    "../metrics/metrics_load_V4.json",
]

DEFAULT_LOAD_HEADING = (
    "Under Load: CONFIG_SYNTHETIC_LOAD_TEST=1, STACKSIZE=4096, PRIORITY=0, "
    "LOOP_ITERS=1000000, BUSY_WAIT_US=10"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate precision boxplot comparing no-load and under-load scenarios "
            "across implementation versions."
        )
    )
    parser.add_argument(
        "--version-labels",
        nargs=4,
        default=DEFAULT_VERSION_LABELS,
        metavar=("V1_LABEL", "V2_LABEL", "V3_LABEL", "V4_LABEL"),
        help="Display labels for versions in plotting order (4 values).",
    )
    parser.add_argument(
        "--normal-metrics",
        nargs=4,
        default=DEFAULT_NORMAL_FILES,
        metavar=("V1_FILE", "V2_FILE", "V3_FILE", "V4_FILE"),
        help="No-load metrics JSON files in V1..V4 order (4 values).",
    )
    parser.add_argument(
        "--load-metrics",
        nargs=4,
        default=DEFAULT_LOAD_FILES,
        metavar=("V1_FILE", "V2_FILE", "V3_FILE", "V4_FILE"),
        help="Under-load metrics JSON files in V1..V4 order (4 values).",
    )
    parser.add_argument(
        "--load-heading",
        type=str,
        default=DEFAULT_LOAD_HEADING,
        help="Custom under-load heading text shown in the title.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Optional single output path (extension decides format, e.g. .svg/.pdf/.png).",
    )
    parser.add_argument(
        "--output-stem",
        type=str,
        default="precision_load_comparison_boxplot",
        help="Output basename (without extension) used when --output-file is not provided.",
    )
    return parser.parse_args()


def build_file_mapping(version_labels, file_paths):
    return dict(zip(version_labels, file_paths))


def load_precision_stats(json_files):
    stats = {}
    for version, file_path in json_files.items():
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            continue

        with open(file_path, "r") as f:
            data = json.load(f)

        precision = data.get("precision", {})
        n = precision.get("cycles_evaluated")
        mean_us = precision.get("precision_us_mean")
        std_us = precision.get("precision_us_stddev")
        max_us = precision.get("precision_us_max")

        if n is None or mean_us is None or std_us is None or max_us is None:
            print(f"Warning: Missing precision fields in: {file_path}")
            continue

        stats[version] = {
            "n": int(n),
            "mean_us": float(mean_us),
            "std_us": float(std_us),
            "max_us": float(max_us),
        }

    return stats


def recreate_precision_samples(precision_stats, seed):
    n = precision_stats["n"]
    mean = precision_stats["mean_us"]
    std = precision_stats["std_us"]
    max_val = precision_stats["max_us"]

    if n <= 0:
        return np.array([])

    if std == 0 or max_val == 0:
        return np.full(n, mean)

    lower = 0.0
    upper = max_val
    a = (lower - mean) / std
    b = (upper - mean) / std

    rng = np.random.default_rng(seed)
    return truncnorm.rvs(a, b, loc=mean, scale=std, size=n, random_state=rng)


def build_dataframe(normal_stats, load_stats):
    rows = []

    for idx, (version, stats) in enumerate(normal_stats.items()):
        samples = recreate_precision_samples(stats, seed=100 + idx)
        for sample in samples:
            rows.append(
                {
                    "Version": version,
                    "Scenario": "No Load",
                    "Precision_ms": sample / 1000.0,
                }
            )

    for idx, (version, stats) in enumerate(load_stats.items()):
        samples = recreate_precision_samples(stats, seed=200 + idx)
        for sample in samples:
            rows.append(
                {
                    "Version": version,
                    "Scenario": "Under Load",
                    "Precision_ms": sample / 1000.0,
                }
            )

    return pd.DataFrame(rows)


def format_sample_summary(normal_stats, load_stats):
    counts = [
        stats["n"]
        for stats in list(normal_stats.values()) + list(load_stats.values())
        if stats["n"] > 0
    ]

    if not counts:
        return "n=unknown"

    unique_counts = sorted(set(counts))
    if len(unique_counts) == 1:
        return f"n={unique_counts[0]} cycles per group"
    return f"n={min(unique_counts)}-{max(unique_counts)} cycles per group"


def main():
    args = parse_args()

    normal_files = build_file_mapping(args.version_labels, args.normal_metrics)
    load_files = build_file_mapping(args.version_labels, args.load_metrics)

    normal_stats = load_precision_stats(normal_files)
    load_stats = load_precision_stats(load_files)

    if not normal_stats:
        raise SystemExit("error: no valid no-load precision metrics found")
    if not load_stats:
        raise SystemExit("error: no valid under-load precision metrics found")

    df = build_dataframe(normal_stats, load_stats)
    if df.empty:
        raise SystemExit("error: no data points produced for plotting")

    n_summary = format_sample_summary(normal_stats, load_stats)

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(12, 6))

    sns.boxplot(
        data=df,
        x="Version",
        y="Precision_ms",
        hue="Scenario",
        palette={"No Load": "#2b5c8f", "Under Load": "#d95f02"},
        showmeans=True,
        meanprops={
            "marker": "o",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": "6",
        },
        ax=ax,
    )

    ax.set_title(
        "Precision ($\\Pi$) Comparison: No Load vs Under Load Across Implementations"
        f"\n{args.load_heading}"
        "\nValue: Reconstructed distribution from metrics mean/std/max; "
        f"Sample Size: {n_summary}",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Implementation Version", fontsize=12, fontweight="bold")
    ax.set_ylabel(r"Precision $\Pi$ (ms)", fontsize=12, fontweight="bold")
    ax.legend(title="Scenario", loc="upper right")

    plt.tight_layout()

    if args.output_file:
        plt.savefig(args.output_file, bbox_inches="tight")
        print(f"Exported precision comparison chart: '{args.output_file}'")
    else:
        svg_out = f"{args.output_stem}.svg"
        pdf_out = f"{args.output_stem}.pdf"

        plt.savefig(svg_out, format="svg", bbox_inches="tight")
        plt.savefig(pdf_out, format="pdf", bbox_inches="tight")

        print(f"Exported precision comparison vector graphics: '{svg_out}' and '{pdf_out}'")


if __name__ == "__main__":
    main()
