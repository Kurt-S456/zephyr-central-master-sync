#!/usr/bin/env python3
"""Calculate timing metrics from child log output.

Expected child log line format:
CHILD <id> offset: <signed_us> us | synced: <ms_int>.<ms_frac_6> ms

Notes:
- In current firmware, `offset` is (worker_ts - child_local_ts) in microseconds.
- Drift offset theta in the write-up is defined as (child_local_ts - worker_ts),
  therefore theta_us = -offset_us.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

LOG_RE = re.compile(
    r"CHILD\s+(?P<child_id>\d+)\s+offset:\s+(?P<offset_us>-?\d+)\s+us\s+\|\s+"
    r"synced:\s+(?P<sync_ms_int>\d+)\.(?P<sync_ms_frac>\d{6})\s+ms"
)

SPI_ERROR_RE = re.compile(r"\bspi(?:_transceive)?\b.*\b(?:failed|error)\b", re.IGNORECASE)


@dataclass
class Sample:
    child_id: int
    sample_index: int
    offset_us: int
    theta_us: int
    abs_theta_us: int
    synced_ns: int
    source_file: str
    source_line: int


@dataclass
class ChildSummary:
    child_id: int
    samples: int
    theta_us_min: int
    theta_us_max: int
    theta_us_mean: float
    theta_us_stddev: float
    abs_theta_us_mean: float
    abs_theta_us_max: int
    spi_transaction_jitter_us: int


@dataclass
class PrecisionSummary:
    cycles_evaluated: int
    precision_us_max: Optional[int]
    precision_us_mean: Optional[float]
    precision_us_stddev: Optional[float]


def _safe_mean(values: List[float]) -> Optional[float]:
    return statistics.mean(values) if values else None


def _safe_stddev(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return 0.0 if len(values) == 1 else None
    return statistics.pstdev(values)


def parse_logs(paths: Iterable[Path]) -> List[Sample]:
    per_child_index: Dict[int, int] = defaultdict(int)
    samples: List[Sample] = []

    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, start=1):
                match = LOG_RE.search(line)
                if not match:
                    continue

                child_id = int(match.group("child_id"))
                offset_us = int(match.group("offset_us"))

                # theta_i,k = t_i,k - t_master,k, while log offset is inverse.
                theta_us = -offset_us
                abs_theta_us = abs(theta_us)

                sync_ms_int = int(match.group("sync_ms_int"))
                sync_ms_frac = int(match.group("sync_ms_frac"))
                synced_ns = (sync_ms_int * 1_000_000) + (sync_ms_frac * 1_000)

                sample_index = per_child_index[child_id]
                per_child_index[child_id] += 1

                samples.append(
                    Sample(
                        child_id=child_id,
                        sample_index=sample_index,
                        offset_us=offset_us,
                        theta_us=theta_us,
                        abs_theta_us=abs_theta_us,
                        synced_ns=synced_ns,
                        source_file=str(path),
                        source_line=line_no,
                    )
                )

    return samples


def summarize_children(samples: List[Sample]) -> List[ChildSummary]:
    grouped: Dict[int, List[Sample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.child_id].append(sample)

    summaries: List[ChildSummary] = []
    for child_id in sorted(grouped):
        group = grouped[child_id]
        theta_values = [s.theta_us for s in group]
        abs_theta_values = [s.abs_theta_us for s in group]

        theta_min = min(theta_values)
        theta_max = max(theta_values)
        jitter = theta_max - theta_min

        summaries.append(
            ChildSummary(
                child_id=child_id,
                samples=len(group),
                theta_us_min=theta_min,
                theta_us_max=theta_max,
                theta_us_mean=statistics.mean(theta_values),
                theta_us_stddev=_safe_stddev(theta_values) or 0.0,
                abs_theta_us_mean=statistics.mean(abs_theta_values),
                abs_theta_us_max=max(abs_theta_values),
                spi_transaction_jitter_us=jitter,
            )
        )

    return summaries


def summarize_precision(samples: List[Sample]) -> PrecisionSummary:
    # Precision per cycle k: Pi_k = max_i(theta_i,k) - min_i(theta_i,k)
    # (equivalent to max absolute pairwise difference across children).
    by_cycle: Dict[int, List[Sample]] = defaultdict(list)
    for sample in samples:
        by_cycle[sample.sample_index].append(sample)

    precision_values: List[int] = []
    for cycle in sorted(by_cycle):
        cycle_samples = by_cycle[cycle]
        if len(cycle_samples) < 2:
            continue
        thetas = [s.theta_us for s in cycle_samples]
        precision_values.append(max(thetas) - min(thetas))

    return PrecisionSummary(
        cycles_evaluated=len(precision_values),
        precision_us_max=max(precision_values) if precision_values else None,
        precision_us_mean=_safe_mean([float(v) for v in precision_values]),
        precision_us_stddev=_safe_stddev([float(v) for v in precision_values]),
    )


def count_spi_errors(paths: Iterable[Path]) -> dict:
    per_file: Dict[str, int] = {}
    total = 0

    for path in paths:
        count = 0
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if SPI_ERROR_RE.search(line):
                    count += 1
        per_file[str(path)] = count
        total += count

    return {
        "total": total,
        "per_file": per_file,
    }


def build_report(samples: List[Sample], spi_errors: dict) -> dict:
    child_summaries = summarize_children(samples)
    precision_summary = summarize_precision(samples)

    per_child_report = []
    for summary in child_summaries:
        row = asdict(summary)
        row.update(
            {
                "theta_ms_min": summary.theta_us_min / 1000.0,
                "theta_ms_max": summary.theta_us_max / 1000.0,
                "theta_ms_mean": summary.theta_us_mean / 1000.0,
                "theta_ms_stddev": summary.theta_us_stddev / 1000.0,
                "abs_theta_ms_mean": summary.abs_theta_us_mean / 1000.0,
                "abs_theta_ms_max": summary.abs_theta_us_max / 1000.0,
                "spi_transaction_jitter_ms": summary.spi_transaction_jitter_us / 1000.0,
            }
        )
        per_child_report.append(row)

    precision_report = asdict(precision_summary)
    if precision_summary.precision_us_max is not None:
        precision_report["precision_ms_max"] = precision_summary.precision_us_max / 1000.0
    if precision_summary.precision_us_mean is not None:
        precision_report["precision_ms_mean"] = precision_summary.precision_us_mean / 1000.0
    if precision_summary.precision_us_stddev is not None:
        precision_report["precision_ms_stddev"] = precision_summary.precision_us_stddev / 1000.0

    report = {
        "samples_total": len(samples),
        "children_detected": sorted({s.child_id for s in samples}),
        "spi_errors": spi_errors,
        "drift_offset": {
            "definition": "theta_us = child_local_ts_us - worker_ts_us = -offset_us",
            "per_child": per_child_report,
        },
        "precision": precision_report,
        "jitter": {
            "clock_line_jitter": {
                "available": False,
                "reason": "Cannot be derived from child software logs; requires oscilloscope edge timing data.",
            },
            "spi_transaction_jitter": {
                "definition": "epsilon_i = max(theta_i) - min(theta_i) over the observation window",
                "unit": "us",
                "per_child": [
                    {
                        "child_id": summary.child_id,
                        "epsilon_us": summary.spi_transaction_jitter_us,
                        "epsilon_ms": summary.spi_transaction_jitter_us / 1000.0,
                    }
                    for summary in child_summaries
                ],
            },
        },
    }
    return report


def print_report(report: dict) -> None:
    print("=== Metrics Summary ===")
    print(f"samples_total: {report['samples_total']}")
    print(f"children_detected: {report['children_detected']}")
    print(f"spi_errors_total: {report['spi_errors']['total']}")
    print()

    print("--- Drift Offset (theta) ---")
    for child in report["drift_offset"]["per_child"]:
        print(
            "child={child_id} samples={samples} theta[min,max,mean,std]={min_:.3f},{max_:.3f},{mean_:.3f},{std_:.3f} ms abs_theta[max]={amax:.3f} ms".format(
                child_id=child["child_id"],
                samples=child["samples"],
                min_=child["theta_ms_min"],
                max_=child["theta_ms_max"],
                mean_=child["theta_ms_mean"],
                std_=child["theta_ms_stddev"],
                amax=child["abs_theta_ms_max"],
            )
        )
    print()

    print("--- Precision (Pi) ---")
    prec = report["precision"]
    print(
        "cycles_evaluated={cycles} precision_ms[max,mean,std]={pmax},{pmean},{pstd}".format(
            cycles=prec["cycles_evaluated"],
            pmax=(f"{prec['precision_ms_max']:.3f}" if prec.get("precision_ms_max") is not None else "N/A"),
            pmean=(f"{prec['precision_ms_mean']:.3f}" if prec.get("precision_ms_mean") is not None else "N/A"),
            pstd=(f"{prec['precision_ms_stddev']:.3f}" if prec.get("precision_ms_stddev") is not None else "N/A"),
        )
    )
    print()

    print("--- Jitter ---")
    print("clock_line_jitter: N/A (oscilloscope data required)")
    for row in report["jitter"]["spi_transaction_jitter"]["per_child"]:
        print(
            "child={child} spi_transaction_jitter_epsilon={eps_ms:.3f} ms ({eps_us} us)".format(
                child=row["child_id"],
                eps_ms=row["epsilon_ms"],
                eps_us=row["epsilon_us"],
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate jitter, drift offset, and precision metrics from child output logs."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more log files containing CHILD output lines.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write full metrics report as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    missing = [str(path) for path in args.inputs if not path.exists()]
    if missing:
        print("error: missing input files:")
        for path in missing:
            print(f"  - {path}")
        return 2

    samples = parse_logs(args.inputs)
    if not samples:
        print("error: no matching CHILD log lines found in the provided inputs")
        return 1

    spi_errors = count_spi_errors(args.inputs)
    report = build_report(samples, spi_errors)
    print_report(report)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print()
        print(f"wrote JSON report: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())