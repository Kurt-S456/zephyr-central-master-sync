import json
import os
import argparse
import matplotlib
# Force Matplotlib to use the non-interactive 'Agg' backend before importing pyplot
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import truncnorm

# 1. File mapping for the 4 implementation versions
JSON_FILES_NORMAL = {
    "V1 (Baseline)": "../metrics/metrics_V1.json",
    "V2 (Hardware Pulse)": "../metrics/metrics_V2.json",
    "V3 (Hardware Timing)": "../metrics/metrics_V3.json",
    "V4 (Hybrid)": "../metrics/metrics_V4.json"
}

JSON_FILES_LOAD = {
    "V1 (Baseline)": "../metrics/metrics_load_V1.json",
    "V2 (Hardware Pulse)": "../metrics/metrics_load_V2.json",
    "V3 (Hardware Timing)": "../metrics/metrics_load_V3.json",
    "V4 (Hybrid)": "../metrics/metrics_load_V4.json"
}

DEFAULT_LOAD_HEADING = (
    "Under Load: CONFIG_SYNTHETIC_LOAD_TEST=1, STACKSIZE=4096, PRIORITY=0, "
    "LOOP_ITERS=1000000, BUSY_WAIT_US=10"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate drift offset boxplot chart.")
    parser.add_argument(
        "--under-load",
        action="store_true",
        help="Append an under-load heading with synthetic load parameters.",
    )
    parser.add_argument(
        "--load-heading",
        type=str,
        default=DEFAULT_LOAD_HEADING,
        help="Custom under-load heading text (used only with --under-load).",
    )
    parser.add_argument(
        "--output-stem",
        type=str,
        default=None,
        help="Optional output basename (without extension).",
    )
    return parser.parse_args()

def load_metrics(json_files):
    parsed_data = {}
    for version, file_path in json_files.items():
        with open(file_path, 'r') as f:
            data = json.load(f)
            parsed_data[version] = data["drift_offset"]["per_child"]
    return parsed_data

def recreate_samples(child, seed=42):
    mean = child["theta_us_mean"]
    std = child["theta_us_stddev"]
    mn = child["theta_us_min"]
    mx = child["theta_us_max"]
    n = child["samples"]
    c_id = child["child_id"]
    
    if std == 0 or mn == mx:
        return np.full(n, mean)
    a, b = (mn - mean) / std, (mx - mean) / std
    np.random.seed(seed + c_id)
    return truncnorm.rvs(a, b, loc=mean, scale=std, size=n)

# 2. Build DataFrame
args = parse_args()
json_files = JSON_FILES_LOAD if args.under_load else JSON_FILES_NORMAL
metrics = load_metrics(json_files)
rows = []
for version, children_list in metrics.items():
    for child in children_list:
        c_id = child["child_id"]
        samples_us = recreate_samples(child)
        for s in samples_us:
            rows.append({
                "Version": version,
                "Child": f"Child {c_id}",
                "Drift_us": s,
                "Drift_ms": s / 1000.0
            })

df = pd.DataFrame(rows)

group_sizes = df.groupby(["Version", "Child"]).size()
unique_sizes = sorted(group_sizes.unique())
if len(unique_sizes) == 1:
    n_summary = f"n={unique_sizes[0]} per child"
else:
    n_summary = f"n={min(unique_sizes)}-{max(unique_sizes)} per child"

# 3. Plotting Setup
sns.set_theme(style="whitegrid")
fig, ax = plt.subplots(figsize=(12, 6))

sns.boxplot(
    data=df,
    x="Version",
    y="Drift_ms",
    hue="Child",
    palette=["#2b5c8f", "#d95f02"],
    showmeans=True,
    meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": "6"},
    ax=ax
)

title_main = "Drift Offset ($\\theta$) Comparison Across Implementations (V1 - V4)"
if args.under_load:
    title_main = f"{title_main}\n{args.load_heading}"

ax.set_title(
    f"{title_main}\nValue: Distribution (median/IQR/whiskers) with mean marker; Sample Size: {n_summary}",
    fontsize=14,
    fontweight='bold',
    pad=15,
)
ax.set_xlabel("Implementation Version", fontsize=12, fontweight='bold')
ax.set_ylabel(r"Drift Offset $\theta$ (ms)", fontsize=12, fontweight='bold')

ax.set_ylim(-2.0, 3.0)
ax.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.7)
ax.legend(title="Child Node", loc="upper right")

plt.tight_layout()

# 4. Export as Vector Graphic (.svg or .pdf)
default_stem = "drift_offset_boxplot_load" if args.under_load else "drift_offset_boxplot"
output_stem = args.output_stem or default_stem
svg_out = f"{output_stem}.svg"
pdf_out = f"{output_stem}.pdf"

plt.savefig(svg_out, format="svg", bbox_inches="tight")
plt.savefig(pdf_out, format="pdf", bbox_inches="tight")

print(f"Exported vector graphics successfully: '{svg_out}' and '{pdf_out}'")