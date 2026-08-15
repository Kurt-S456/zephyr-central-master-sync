import argparse
import pathlib

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for file generation
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def load_tek_csv(filename):
    """Parses Tektronix oscilloscope CSV files, automatically identifying time and voltage columns."""
    try:
        df = pd.read_csv(filename, header=None, on_bad_lines='skip')
    except Exception as e:
        raise ValueError(f"Could not read CSV file '{filename}': {e}")

    df_num = df.apply(pd.to_numeric, errors='coerce')
    valid_cols = [col for col in df_num.columns if df_num[col].notna().sum() > 0]

    if len(valid_cols) < 2:
        raise ValueError(f"CSV file '{filename}' does not contain at least two numeric columns.")

    best_pair = None
    max_valid_count = 0

    for i in range(len(valid_cols) - 1):
        c1, c2 = valid_cols[i], valid_cols[i + 1]
        valid_rows_count = len(df_num[[c1, c2]].dropna())
        if valid_rows_count > max_valid_count:
            max_valid_count = valid_rows_count
            best_pair = (c1, c2)

    if best_pair is None or max_valid_count == 0:
        raise ValueError(f"No valid numeric time/voltage data rows found in '{filename}'.")

    time_col, volt_col = best_pair
    clean_data = df_num[[time_col, volt_col]].dropna()

    time = clean_data[time_col].to_numpy(dtype=float)
    voltage = clean_data[volt_col].to_numpy(dtype=float)

    return time, voltage


def compute_edge_crossings(time, voltage, threshold_v=None):
    """Find precise sub-sample rising edge timestamps via linear interpolation."""
    if len(voltage) == 0 or len(time) == 0:
        raise ValueError("Cannot compute edge crossings on empty time/voltage arrays.")

    if threshold_v is None:
        threshold_v = (np.min(voltage) + np.max(voltage)) / 2.0

    above = voltage >= threshold_v
    rising_indices = np.where(~above[:-1] & above[1:])[0]

    edge_times = []
    for idx in rising_indices:
        t1, t2 = time[idx], time[idx + 1]
        v1, v2 = voltage[idx], voltage[idx + 1]
        denom = v2 - v1
        t_exact = t1 if denom == 0 else t1 + (threshold_v - v1) * (t2 - t1) / denom
        edge_times.append(t_exact)

    return np.array(edge_times), threshold_v


def analyze_tie(csv_filename, output_file=None, target_freq_hz=1e6, hist_bins=500):
    time, voltage = load_tek_csv(csv_filename)
    edge_times, threshold_v = compute_edge_crossings(time, voltage)

    if len(edge_times) < 2:
        raise ValueError("Not enough clock edges found in CSV file!")

    # 1. Measured Clock Periods
    periods = np.diff(edge_times)
    mean_period = np.mean(periods)
    measured_freq = 1.0 / mean_period

    # 2. Calculate Ideal Reference Clock Grid
    T_ideal = mean_period
    edge_indices = np.arange(len(edge_times))
    ideal_edge_times = edge_times[0] + edge_indices * T_ideal

    # 3. Time Interval Error (TIE)
    tie = edge_times - ideal_edge_times
    tie_ns = tie * 1e9
    tie_mean_ns = np.mean(tie_ns)
    tie_std_ps = np.std(tie) * 1e12

    # 4. Jitter Metrics
    tie_p2p = (np.max(tie) - np.min(tie)) * 1e9
    tie_rms = np.std(tie) * 1e9
    c2c_jitter = np.diff(periods) * 1e9

    # Print Results
    print("=" * 45)
    print("        SPI CLOCK TIE & JITTER ANALYSIS      ")
    print("=" * 45)
    print(f"Detected Edges     : {len(edge_times)}")
    print(f"50% Threshold      : {threshold_v:.3f} V")
    print(f"Mean Clock Period  : {mean_period * 1e6:.3f} µs")
    print(f"Measured Frequency : {measured_freq / 1e3:.3f} kHz")
    print("-" * 45)
    print(f"Peak-to-Peak TIE   : {tie_p2p:.3f} ns")
    print(f"RMS TIE (Jitter)   : {tie_rms:.3f} ns")
    print(f"Mean TIE           : {tie_mean_ns:.6f} ns")
    print(f"TIE Std Dev        : {tie_std_ps:.3f} ps")
    print(f"Max C2C Jitter     : {np.max(np.abs(c2c_jitter)):.3f} ns")
    print("=" * 45)

    # Plotting Results
    fig = plt.figure(figsize=(10, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 2, 2])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0])

    # Plot 1: Waveform & Crossings
    ax1.plot(time * 1e6, voltage, label="CH1 Clock Waveform", color="goldenrod")
    ax1.axhline(threshold_v, color="red", linestyle="--", alpha=0.5, label=f"50% Thresh ({threshold_v:.2f}V)")
    ax1.plot(edge_times * 1e6, np.full_like(edge_times, threshold_v), "rx", label="Detected Edges")
    ax1.set_ylabel("Voltage (V)")
    ax1.set_title(f"Tektronix TDS 2001C — SPI Clock Waveform ({measured_freq / 1e3:.3f} kHz)")
    ax1.grid(True)
    ax1.legend(loc="upper right")

    # Plot 2: TIE Track
    ax2.plot(edge_times * 1e6, tie_ns, "o-", color="purple")
    ax2.axhline(0, color="black", linestyle="--", alpha=0.3)
    ax2.set_xlabel("Time (µs)")
    ax2.set_ylabel("TIE (ns)")
    ax2.set_title(f"Time Interval Error (TIE Track) — P2P Jitter: {tie_p2p:.2f} ns")
    ax2.grid(True)

    # Plot 3: TIE Histogram
    effective_bins = hist_bins if len(tie_ns) >= hist_bins else max(1, len(tie_ns))
    ax3.hist(tie_ns, bins=effective_bins, color="steelblue", alpha=0.85, edgecolor="white")
    ax3.set_xlabel("TIE (ns)")
    ax3.set_ylabel("Count")
    ax3.set_title(
        f"TIE Jitter Histogram — N={len(tie_ns)}, Bins={effective_bins}, Mean={tie_mean_ns:.6f} ns, Std={tie_std_ps:.3f} ps"
    )
    ax3.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()

    # Default output filename if not specified
    if not output_file:
        output_file = str(pathlib.Path(csv_filename).with_suffix(".svg"))

    # Export vector graphic (SVG, PDF, EPS depending on output_file extension)
    plt.savefig(output_file, bbox_inches="tight")
    print(f"Vector graphic exported to: {output_file}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze TIE and jitter from a Tektronix CSV waveform file."
    )
    parser.add_argument(
        "csv_filename",
        nargs="?",
        default="TEK0000.CSV",
        help="Path to the Tektronix CSV file",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Path for vector output file (e.g. plot.svg, plot.pdf, plot.eps). Defaults to <input_name>.svg",
    )
    parser.add_argument(
        "--target-freq-hz",
        type=float,
        default=1e6,
        help="Nominal target frequency in Hz (default: 1e6)",
    )
    parser.add_argument(
        "--hist-bins",
        type=int,
        default=500,
        help="Number of bins for TIE histogram (default: 500)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    analyze_tie(
        args.csv_filename,
        output_file=args.output,
        target_freq_hz=args.target_freq_hz,
        hist_bins=args.hist_bins,
    )