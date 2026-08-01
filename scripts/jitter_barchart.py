import json
import os
import matplotlib
# Force Matplotlib to use the non-interactive 'Agg' backend
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# 1. File mapping for the 4 implementation versions
json_files = {
    "V1 (Baseline)": "../metrics/metrics_V1.json",
    "V2 (Hardware Pulse)": "../metrics/metrics_V2.json",
    "V3 (Hardware Timing)": "../metrics/metrics_V3.json",
    "V4 (Hybrid)": "../metrics/metrics_V4.json"
}

def load_jitter_metrics():
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
metrics, sample_counts = load_jitter_metrics()
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

ax.set_title(
    f"SPI Transaction Jitter ($\\epsilon_i$) Comparison Across Implementations\nValue: Range per child (max - min); Sample Size: {n_summary}",
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
plt.savefig("spi_jitter_comparison.svg", format="svg", bbox_inches="tight")
plt.savefig("spi_jitter_comparison.pdf", format="pdf", bbox_inches="tight")

print("Exported jitter vector graphics successfully: 'spi_jitter_comparison.svg' and 'spi_jitter_comparison.pdf'")