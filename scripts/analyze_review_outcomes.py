# analyze_review_outcomes.py
#
# This script analyzes review outcomes to support future confidence calibration.
# Once enough data is collected (300–500+ reviewed records),
# these metrics will be used to adjust confidence scoring thresholds.
#
# Usage:
#   python scripts/analyze_review_outcomes.py
#   python scripts/analyze_review_outcomes.py --file path/to/review_log.json
#
# No external dependencies — uses Python standard library only.

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("analyze_review_outcomes")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_REVIEW_LOG = REPO_ROOT / "review_log.json"

# Confidence buckets for grouping
BUCKETS = [
    ("High",   0.90, 1.00),
    ("Medium", 0.75, 0.89),
    ("Low",    0.00, 0.74),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_review_log(path: Path) -> List[Dict[str, Any]]:
    """Load review_log.json, returning an empty list on missing/empty/invalid."""
    if not path.exists():
        logger.warning("Review log not found: %s", path)
        logger.info("Export review decisions from the dashboard first.")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data: Any = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Could not parse review log: %s", e)
        return []
    if not isinstance(data, list):
        logger.warning("Review log is not a JSON array.")
        return []
    return [dict(item) for item in data]  # type: ignore[arg-type]


def bucket_label(confidence: float) -> str:
    """Map a confidence value to its bucket label."""
    for label, lo, hi in BUCKETS:
        if lo <= confidence <= hi:
            return label
    return "Unknown"


def bucket_range(label: str) -> str:
    """Return the display range for a bucket label."""
    for name, lo, hi in BUCKETS:
        if name == label:
            return f"{lo:.2f}–{hi:.2f}"
    return "?"


def pct(numerator: int, denominator: int) -> str:
    """Format a percentage string, guarding against division by zero."""
    if denominator == 0:
        return "N/A"
    return f"{(numerator / denominator) * 100:.1f}%"


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print()
    print(f"  {title}")
    print(f"  {'─' * len(title)}")


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def analyze_by_confidence(entries: List[Dict[str, Any]]) -> None:
    """Group review outcomes by confidence bucket."""
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0})

    for e in entries:
        conf = e.get("confidence")
        if conf is None:
            continue
        label = bucket_label(float(conf))
        outcome = e.get("review_outcome", "")
        groups[label]["total"] += 1
        if outcome == "accepted":
            groups[label]["accepted"] += 1
        elif outcome == "rejected":
            groups[label]["rejected"] += 1

    print_section("Confidence Buckets")
    # Print in bucket order (High → Medium → Low)
    for label, _lo, _hi in BUCKETS:
        stats = groups.get(label)
        if not stats or stats["total"] == 0:
            continue
        print(f"    {label} ({bucket_range(label)})")
        print(f"      Total:           {stats['total']}")
        print(f"      Accepted:        {stats['accepted']}")
        print(f"      Rejected:        {stats['rejected']}")
        print(f"      Acceptance Rate: {pct(stats['accepted'], stats['total'])}")
        print()


def analyze_by_field(entries: List[Dict[str, Any]]) -> None:
    """Group review outcomes by field type."""
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0})

    for e in entries:
        field = e.get("field") or e.get("field_name") or "unknown"
        outcome = e.get("review_outcome", "")
        groups[field]["total"] += 1
        if outcome == "accepted":
            groups[field]["accepted"] += 1
        elif outcome == "rejected":
            groups[field]["rejected"] += 1

    print_section("Field Performance")
    for field in sorted(groups.keys()):
        stats = groups[field]
        print(f"    {field}")
        print(f"      Total:           {stats['total']}")
        print(f"      Accepted:        {stats['accepted']}")
        print(f"      Rejected:        {stats['rejected']}")
        print(f"      Acceptance Rate: {pct(stats['accepted'], stats['total'])}")
        print()


def analyze_by_run(entries: List[Dict[str, Any]]) -> None:
    """Group review outcomes by run_id for trend analysis."""
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0})

    for e in entries:
        run_id = e.get("run_id") or "unknown"
        outcome = e.get("review_outcome", "")
        groups[run_id]["total"] += 1
        if outcome == "accepted":
            groups[run_id]["accepted"] += 1
        elif outcome == "rejected":
            groups[run_id]["rejected"] += 1

    print_section("Run Performance (by run_id)")
    for run_id in sorted(groups.keys()):
        stats = groups[run_id]
        print(f"    {run_id}")
        print(f"      Total Reviewed:  {stats['total']}")
        print(f"      Accepted:        {stats['accepted']}")
        print(f"      Rejected:        {stats['rejected']}")
        print(f"      Acceptance Rate: {pct(stats['accepted'], stats['total'])}")
        print()


def analyze_by_source_tag(entries: List[Dict[str, Any]]) -> None:
    """Group review outcomes by source_tag (if available)."""
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0})

    has_any = False
    for e in entries:
        tag = e.get("source_tag")
        if not tag:
            continue
        has_any = True
        outcome = e.get("review_outcome", "")
        groups[tag]["total"] += 1
        if outcome == "accepted":
            groups[tag]["accepted"] += 1
        elif outcome == "rejected":
            groups[tag]["rejected"] += 1

    if not has_any:
        return

    print_section("Source Tag Insights")
    for tag in sorted(groups.keys()):
        stats = groups[tag]
        print(f"    {tag}")
        print(f"      Total:           {stats['total']}")
        print(f"      Accepted:        {stats['accepted']}")
        print(f"      Rejected:        {stats['rejected']}")
        print(f"      Acceptance Rate: {pct(stats['accepted'], stats['total'])}")
        print()


# ---------------------------------------------------------------------------
# Calibration readiness check
# ---------------------------------------------------------------------------

def calibration_readiness(total: int) -> None:
    """Print guidance on whether there's enough data for calibration."""
    print_section("Calibration Readiness")
    if total >= 500:
        print("    ✅ Strong dataset — ready for confidence calibration.")
    elif total >= 300:
        print("    🟡 Moderate dataset — calibration possible with caution.")
    elif total >= 50:
        print(f"    ⚠  {total} reviewed records — need 300+ for reliable calibration.")
    else:
        print(f"    ⚠  Only {total} reviewed records — keep reviewing to build dataset.")
    print(f"    Total reviewed records: {total}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze review outcomes for confidence calibration.",
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=DEFAULT_REVIEW_LOG,
        help="Path to review_log.json (default: %(default)s)",
    )
    args = parser.parse_args()
    review_path = args.file

    entries = load_review_log(review_path)
    if not entries:
        print("\nNo review data to analyze. Exiting.")
        sys.exit(0)

    # Filter to only entries with a review outcome
    reviewed = [e for e in entries if e.get("review_outcome") in ("accepted", "rejected")]
    if not reviewed:
        print("\nNo accepted/rejected entries found. Exiting.")
        sys.exit(0)

    # Header
    print()
    print("  ══════════════════════════════════════")
    print("   CONFIDENCE CALIBRATION REPORT")
    print("  ══════════════════════════════════════")
    print(f"  Source: {review_path}")
    print(f"  Total entries: {len(entries)}  |  Reviewed: {len(reviewed)}")

    # Run all analyses
    analyze_by_confidence(reviewed)
    analyze_by_field(reviewed)
    analyze_by_run(reviewed)
    analyze_by_source_tag(reviewed)
    calibration_readiness(len(reviewed))


if __name__ == "__main__":
    main()
