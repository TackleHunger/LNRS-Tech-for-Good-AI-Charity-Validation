"""
Tackle Hunger - aggregate_summary.py

What it does:
- Reads the latest ai_validation_report.json.
- Reads the existing latest_summary.json (if it exists).
- Aggregates statistics across all validation runs.
- Writes the updated totals back to latest_summary.json.

Why:
- Provides a rolling, cumulative view of the validation pipeline's performance.
- Tracks progress and identifies trends over time without a database.
- Keeps the aggregation logic separate from the core validation script.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, cast

# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("aggregate_summary")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def utc_now_iso() -> str:
    """Returns the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_repo_root() -> Path:
    """Gets the repository root directory."""
    # Assumes this script is in /scripts/
    return Path(__file__).resolve().parent.parent


def load_json_file(path: Path) -> Dict[str, Any]:
    """Loads a JSON file, returning an empty dict if it doesn't exist or is invalid."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _load_batch_history(history_path: Path) -> List[Dict[str, Any]]:
    """Load the durable batch_history.json (append-only ledger)."""
    if not history_path.exists():
        return []
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return cast(List[Dict[str, Any]], raw) if isinstance(raw, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _append_batch_history(
    history_path: Path,
    entry: Dict[str, Any],
    all_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Append *entry* to the durable batch_history.json if its run_id is new.

    Returns the updated list (caller can use it for the in-memory summary too).
    """
    run_id = entry.get("run_id", "")
    if any(e.get("run_id") == run_id for e in all_entries):
        logger.info("Batch %s already in durable history – skipping duplicate", run_id)
        return all_entries

    all_entries.append(entry)
    tmp_path = history_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    tmp_path.replace(history_path)
    logger.info("Appended batch %s to durable history (%s)", run_id, history_path.name)
    return all_entries


def aggregate_summary(report_path: Path, summary_path: Path) -> None:
    """
    Reads a validation report and updates a cumulative summary file.

    Args:
        report_path: Path to the new ai_validation_report.json.
        summary_path: Path to the latest_summary.json to be updated.
    """
    report = load_json_file(report_path)
    if not report:
        logger.error("Could not load or parse report file at %s", report_path)
        return

    summary = load_json_file(summary_path)

    # --- Initialize or load existing summary data ---
    # NOTE on data shape:
    #   * `total_sites_processed`, `classifications`, `field_reasons`,
    #     and `batch_history` are CUMULATIVE across runs (history view).
    #   * `current_run` is REPLACED on every run and contains only the
    #     most recent batch's counts. The dashboard drives all KPI cards,
    #     percentages, detected_changes, and top_issues from `current_run`
    #     so totals reconcile: approved + review + deferred == site_count.
    new_summary: Dict[str, Any] = {
        "updated_at": utc_now_iso(),
        "total_sites_processed": summary.get("total_sites_processed", 0),
        "classifications": summary.get("classifications", {}),
        "field_reasons": summary.get("field_reasons", {}),
        "batch_history": summary.get("batch_history", []),
        "detected_changes": [],   # cumulative changes for back-compat
        "current_run": {},        # populated below
    }

    # --- Durable batch history (append-only ledger) ---
    history_path = summary_path.parent / "batch_history.json"
    durable_history = _load_batch_history(history_path)

    # Seed in-memory batch_history from the durable file when
    # latest_summary.json was reset but batch_history.json survived.
    if not new_summary["batch_history"] and durable_history:
        new_summary["batch_history"] = list(durable_history)
        logger.info("Restored %d entries from durable batch_history.json", len(durable_history))

    # --- Generate run_id for traceability ---
    # Format: YYYY-MM-DD_batchN  (N = sequential batch number)
    batch_number = max(len(new_summary["batch_history"]), len(durable_history)) + 1
    run_id = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_batch{batch_number}"
    logger.info("Run ID: %s", run_id)

    # --- Aggregate new report data ---
    report_summary = report.get("summary", {})
    site_count = report.get("site_count", 0)
    new_summary["total_sites_processed"] += site_count

    # Aggregate classification counts (cumulative)
    classification_counts = report_summary.get("classification_counts", {})
    current_classifications: Counter[str] = Counter(new_summary["classifications"])
    current_classifications.update(classification_counts)
    new_summary["classifications"] = dict(current_classifications)

    # Aggregate field reasons (cumulative, as a proxy for flags)
    current_reasons: Counter[str] = Counter(new_summary["field_reasons"])
    # Current-run-only counters
    current_run_reasons: Counter[str] = Counter()
    current_run_changes: list[Dict[str, Any]] = []
    sites_with_changes = 0
    sites_with_missing = 0  # site-level missing count for % fix
    closure_alerts: list[Dict[str, Any]] = []  # sites flagged as potentially closed

    # --- Shared helpers for equivalence checks ---
    # Import here to avoid circular deps (scripts/ imports from src/)
    _src_dir = str(summary_path.parent / "src")
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    from tackle_hunger.utils import phone_digits as _phone_digits, canonical_url as _canonical_url

    for site in report.get("sites", []):
        has_change = False
        has_missing = False

        # Check for closure detection (site-level flag from ai_validate)
        if site.get("closure_detected"):
            closure_alerts.append({
                "site_name": site.get("name"),
                "reason": site.get("closure_reason", "Possible closure detected."),
            })

            # --- Inject operational_status change entry ---
            # Surface closure as a reviewable detected change so it appears
            # in the Detected Changes table alongside field-level changes.
            # Extract closure confidence from the site's status field, if available.
            closure_confidence: float = 0.7  # default
            site_fields: list[Dict[str, Any]] = site.get("fields", [])
            for f in site_fields:
                if f.get("field") == "status":
                    closure_confidence = float(f.get("confidence", 0.7))
                    break
            closure_change: Dict[str, Any] = {
                "site_name": site.get("name"),
                "field_name": "operational_status",
                "original_value": "Active",
                "proposed_value": "Permanently Closed",
                "confidence": closure_confidence,
                "change_type": "closure",
                "source_tag": None,
                "review_outcome": None,
                "run_id": run_id,
            }
            new_summary["detected_changes"].append(closure_change)
            current_run_changes.append(closure_change)
            has_change = True

        for field in site.get("fields", []):
            for reason in field.get("reasons", []):
                current_reasons.update([reason])
                current_run_reasons.update([reason])

            original = field.get("original_value")
            proposed = field.get("proposed_value")
            status = field.get("status", "")

            # Statuses that explicitly indicate a web-evidence-driven change.
            # Used as a safety net alongside the value comparison so that
            # changes flagged by ai_validate.py always surface.
            change_statuses = {
                "proposed_update", "proposed_update_low_confidence",
                "mismatch", "review", "detected_only",
            }

            # Phone fields: ignore formatting-only differences. Two phone
            # values whose digit-stripped forms match are equivalent and
            # MUST NOT appear in Detected Changes.
            if field.get("field") == "publicPhone":
                if _phone_digits(original) == _phone_digits(proposed):
                    continue

            # Website field: ignore protocol/www/trailing-slash/case-only
            # differences. Canonical equality means no real change.
            if field.get("field") == "website":
                if _canonical_url(original) == _canonical_url(proposed):
                    continue

            # Count as change if proposed differs from original OR if the
            # field status explicitly indicates a change from web evidence.
            if (original != proposed and proposed is not None) or \
               (status in change_statuses and proposed is not None):
                has_change = True

                # Classify change type: fill_gap vs correction
                change_type = field.get("change_type")
                if change_type is None:
                    # Derive if not present (backward compat with older reports)
                    if proposed and not original:
                        change_type = "fill_gap"
                    elif proposed and original and proposed != original:
                        change_type = "correction"

                change_entry: Dict[str, Any] = {
                    "site_name": site.get("name"),
                    "field_name": field.get("field"),
                    "original_value": original,
                    "proposed_value": proposed,
                    "confidence": field.get("confidence"),
                    "change_type": change_type,
                    "source_tag": field.get("source_tag"),
                    # review_outcome is used for future confidence calibration.
                    # Once enough reviewed data is collected (300–500+ records),
                    # confidence values can be adjusted based on actual
                    # acceptance rates.  Until then this field is null.
                    "review_outcome": None,
                    # run_id links each change to its originating validation
                    # run for traceability and future calibration by batch.
                    "run_id": run_id,
                }
                new_summary["detected_changes"].append(change_entry)
                current_run_changes.append(change_entry)
            # Track site-level missing (any field missing → site counts)
            if field.get("status") == "not_evaluable" or (
                original is None or (isinstance(original, str) and original.strip() == "")
            ):
                has_missing = True

        if has_change:
            sites_with_changes += 1
        if has_missing:
            sites_with_missing += 1

    new_summary["field_reasons"] = dict(current_reasons)

    # Add to batch history with this run's classification breakdown so the
    # history view also reconciles per-batch.
    new_batch_info: Dict[str, Any] = {
        "run_id": run_id,
        "batch_id": report.get("batch_id"),
        "validated_at": report.get("validated_at"),
        "site_count": site_count,
        "sites_with_changes": sites_with_changes,
        "percent_with_changes": round((sites_with_changes / site_count) * 100, 2) if site_count > 0 else 0,
        "classification_counts": dict(classification_counts),
    }
    # Deduplicate: only append if this run_id is not already present
    if not any(b.get("run_id") == run_id for b in new_summary["batch_history"]):
        new_summary["batch_history"].append(new_batch_info)
    else:
        logger.info("Batch %s already in in-memory history – skipping duplicate", run_id)

    # Persist to the durable, append-only ledger so history survives
    # even if latest_summary.json is deleted or overwritten.
    _append_batch_history(history_path, new_batch_info, durable_history)

    # Snapshot of the most recent run - the dashboard reads from here so
    # KPI cards always reconcile with the batch size of the current run.
    missing_percent = round((sites_with_missing / site_count) * 100, 2) if site_count > 0 else 0
    new_summary["current_run"] = {
        "run_id": run_id,
        "batch_id": report.get("batch_id"),
        "validated_at": report.get("validated_at"),
        "trigger": report.get("trigger", "manual"),
        "site_count": site_count,
        "classification_counts": dict(classification_counts),
        "field_reasons": dict(current_run_reasons),
        "detected_changes": current_run_changes,
        "sites_with_changes": sites_with_changes,
        "missing_values_site_level": {
            "count": sites_with_missing,
            "percent": missing_percent,
        },
        "closure_alerts": closure_alerts,
        "top_missed_values": [],  # populated below from review_log
    }

    # --- Load review_log.json and extract top missed values ---
    review_log_path = report_path.parent / "review_log.json"
    top_missed_values: list[Dict[str, Any]] = []
    if review_log_path.exists():
        try:
            with open(review_log_path, "r", encoding="utf-8") as rlf:
                review_entries_raw = json.load(rlf)
            if not isinstance(review_entries_raw, list):
                review_entries_raw = []
            review_entries = cast(List[Dict[str, Any]], review_entries_raw)
            missed: list[Dict[str, Any]] = [
                {
                    "site_name": e.get("site_name", ""),
                    "field": e.get("field", ""),
                    "proposed_value": e.get("proposed_value"),
                    "corrected_value": e.get("corrected_value"),
                    "confidence": e.get("confidence"),
                    "run_id": e.get("run_id", ""),
                    "review_timestamp": e.get("review_timestamp", ""),
                }
                for e in review_entries
                if e.get("review_outcome") == "rejected"
                and e.get("corrected_value")
            ]
            # Sort by most recent first, cap at 10
            missed.sort(key=lambda x: str(x.get("review_timestamp", "")), reverse=True)
            top_missed_values = missed[:10]
            logger.info("Loaded %d missed values from review_log.json", len(top_missed_values))
        except Exception:
            logger.warning("Could not parse review_log.json – top_missed_values will be empty")

    new_summary["current_run"]["top_missed_values"] = top_missed_values

    # --- Write updated summary (atomic: write to temp, then rename) ---
    tmp_path = summary_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(new_summary, f, ensure_ascii=False, indent=2)
    tmp_path.replace(summary_path)

    logger.info("Aggregated summary updated. Total sites processed (cumulative): %d", new_summary['total_sites_processed'])
    logger.info("  Current run: %d sites, classifications=%s", site_count, dict(classification_counts))
    logger.info("  Saved to: %s", summary_path)


if __name__ == "__main__":
    repo_root = _get_repo_root()
    report_file = repo_root / "ai_validation_report.json"
    summary_file = repo_root / "latest_summary.json"
    aggregate_summary(report_file, summary_file)
