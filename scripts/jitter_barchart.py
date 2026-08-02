import json
import os
import argparse
import matplotlib
# Force Matplotlib to use the non-interactive 'Agg' backend
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

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
    parser = argparse.ArgumentParser(description="Generate SPI jitter comparison chart.")
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

def load_jitter_metrics(json_files):
    parsed_data = {}
    sample_counts = {}
    for version, file_path in json_files.items():
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                parsed_data[version] = data["jitter"]["spi_transaction_jitter"]["per_child"]
                sample_counts[version] = {
                    child["child_id"]: child.get("samples")
                    for child in data.get("drift_offset", {}).get("per_child", [])
                }
        else:
            print(f"Warning: File not found: {file_path}")
    return parsed_data, sample_counts


def format_sample_summary(sample_counts):
    all_counts = [
        count
        for by_child in sample_counts.values()
        for count in by_child.values()
        if count is not None
    ]
    if not all_counts:
        return "n=unknown"

    unique_counts = sorted(set(all_counts))
    if len(unique_counts) == 1:
        return f"n={unique_counts[0]} per child"
    return f"n={min(unique_counts)}-{max(unique_counts)} per child"

# 2. Build DataFrame
args = parse_args()
json_files = JSON_FILES_LOAD if args.under_load else JSON_FILES_NORMAL
metrics, sample_counts = load_jitter_metrics(json_files)
n_summary = format_sample_summary(sample_counts)
rows = []
for version, children_list in metrics.items():
    for child in children_list:
        c_id = child["child_id"]
        rows.append({
            "Version": version,
            "Child": f"Child {c_id}",
            "Jitter_ms": child["epsilon_ms"]
        })

df = pd.DataFrame(rows)

# 3. Plotting Setup
sns.set_theme(style="whitegrid")
fig, ax = plt.subplots(figsize=(10, 6))

sns.barplot(
    data=df,
    x="Version",
    y="Jitter_ms",
    hue="Child",
    palette=["#2b5c8f", "#d95f02"],
    ax=ax
)

title_main = "SPI Transaction Jitter ($\\epsilon_i$) Comparison Across Implementations"
if args.under_load:
    title_main = f"{title_main}\n{args.load_heading}"

ax.set_title(
    f"{title_main}\nValue: Range per child (max - min); Sample Size: {n_summary}",
    fontsize=14,
    fontweight='bold',
    pad=15,
)
ax.set_xlabel("Implementation Version", fontsize=12, fontweight='bold')
ax.set_ylabel(r"SPI Transaction Jitter $\epsilon_i$ (ms)", fontsize=12, fontweight='bold')
ax.legend(title="Child Node", loc="upper right")

# Add exact millisecond text labels on top of each bar
for p in ax.patches:
    height = p.get_height()
    if pd.notna(height) and height > 0:
        ax.annotate(f'{height:.2f} ms',
                    (p.get_x() + p.get_width() / 2., height),
                    ha='center', va='bottom',
                    fontsize=9, fontweight='bold',
                    xytext=(0, 3), textcoords='offset points')

plt.tight_layout()

# 4. Export Vector Graphics
default_stem = "spi_jitter_comparison_load" if args.under_load else "spi_jitter_comparison"
output_stem = args.output_stem or default_stem
svg_out = f"{output_stem}.svg"
pdf_out = f"{output_stem}.pdf"

plt.savefig(svg_out, format="svg", bbox_inches="tight")
plt.savefig(pdf_out, format="pdf", bbox_inches="tight")

print(f"Exported jitter vector graphics successfully: '{svg_out}' and '{pdf_out}'")