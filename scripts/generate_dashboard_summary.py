import json
import logging
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, cast

# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("dashboard_summary")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

def main() -> None:
    # Resolve paths relative to repo root (not CWD)
    repo_root = Path(__file__).resolve().parent.parent

    # Load latest summary
    summary_path = repo_root / "latest_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    # `current_run` holds the most recent batch only and is the single
    # source of truth for KPI cards, percentages, detected_changes, and
    # top_issues so totals reconcile:
    #     approved + review + deferred == site_count
    current_run: Dict[str, Any] = data.get("current_run") or {}
    batch_history: List[Dict[str, Any]] = data.get("batch_history", [])

    # Prefer the durable, append-only batch_history.json when it has more
    # entries (survives latest_summary.json resets).
    durable_path = repo_root / "batch_history.json"
    if durable_path.exists():
        try:
            with open(durable_path, "r", encoding="utf-8") as bhf:
                durable_raw: Any = json.load(bhf)
            if isinstance(durable_raw, list):
                durable_list = cast(List[Dict[str, Any]], durable_raw)
                if len(durable_list) > len(batch_history):
                    batch_history = durable_list
                    logger.info("Using durable batch_history.json (%d entries)", len(durable_list))
        except (json.JSONDecodeError, IOError):
            pass
    # Fall back to the last batch_history entry if current_run is absent
    # (e.g., reading an older latest_summary.json).
    if not current_run and batch_history:
        last: Dict[str, Any] = batch_history[-1]
        current_run = {
            "site_count": last.get("site_count", 0),
            "classification_counts": last.get("classification_counts", {}),
            "field_reasons": {},
            "detected_changes": [],
        }

    current_run_sites: int = current_run.get("site_count", 0) or 0
    classifications: Dict[str, int] = current_run.get("classification_counts", {}) or {}
    field_reasons: Dict[str, int] = current_run.get("field_reasons", {}) or {}
    detected_changes: List[Dict[str, Any]] = current_run.get("detected_changes", []) or []

    # Calculate percentages off the CURRENT RUN size
    percentages: Dict[str, float] = {}
    for key, value in classifications.items():
        percentages[key] = round((value / current_run_sites) * 100, 2) if current_run_sites > 0 else 0

    # Top 5 issues (current run only) — filter to actual problems,
    # excluding confirmation/valid statuses that aren't actionable.
    _non_issue_prefixes = (
        "value_is_valid", "web_evidence_confirmed", "confirmed",
        "normalized_format", "website_format_equivalent",
    )
    issue_reasons: Dict[str, int] = {
        k: v for k, v in field_reasons.items()
        if not k.startswith(_non_issue_prefixes)
    }
    top_issues = sorted(issue_reasons.items(), key=lambda x: x[1], reverse=True)[:5]

    # -----------------------------------------------------------------
    # Aggregate batch runs by calendar date (one bar per day).
    # -----------------------------------------------------------------
    all_runs: List[Dict[str, Any]] = list(batch_history)

    # Ensure the current run is included even if batch_history was empty
    # or stale.
    if current_run and current_run.get("batch_id"):
        current_batch_entry: Dict[str, Any] = {
            "run_id": current_run.get("run_id", ""),
            "batch_id": current_run.get("batch_id"),
            "validated_at": current_run.get("validated_at"),
            "site_count": current_run_sites,
            "sites_with_changes": current_run.get("sites_with_changes", 0),
            "percent_with_changes": 0,
            "classification_counts": classifications,
        }
        current_rid: str = current_run.get("run_id", "")
        already_present = any(
            b.get("run_id") == current_rid
            for b in all_runs
        ) if current_rid else any(
            b.get("validated_at") == current_run.get("validated_at")
            and b.get("batch_id") == current_run.get("batch_id")
            for b in all_runs
        )
        if not already_present:
            all_runs.append(current_batch_entry)

    def _date_key(entry: Dict[str, Any]) -> str:
        """Extract a YYYY-MM-DD date string from a batch entry."""
        rid = entry.get("run_id", "")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", rid)
        if m:
            return m.group(1)
        vat = entry.get("validated_at", "")
        if vat:
            return vat[:10]
        return "unknown"

    # Group runs by date, preserving insertion order.
    daily_buckets: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
    for run in all_runs:
        dk = _date_key(run)
        daily_buckets.setdefault(dk, []).append(run)

    # Build one summary entry per day.
    recent_batches: List[Dict[str, Any]] = []
    for date_key, runs in daily_buckets.items():
        total_sites = sum(r.get("site_count", 0) for r in runs)
        total_changes = sum(r.get("sites_with_changes", 0) for r in runs)
        # Merge classification counts across runs for the day
        merged_cls: Dict[str, int] = {}
        for r in runs:
            cls_counts: Dict[str, int] = r.get("classification_counts") or {}
            for k, v in cls_counts.items():
                merged_cls[k] = merged_cls.get(k, 0) + v
        recent_batches.append({
            "date": date_key,
            "batch_runs": len(runs),
            "site_count": total_sites,
            "sites_with_changes": total_changes,
            "percent_with_changes": round((total_changes / total_sites) * 100, 2) if total_sites else 0,
            "classification_counts": merged_cls,
        })
    # Keep the last 10 days for the chart
    recent_batches = recent_batches[-10:]

    dashboard: Dict[str, Any] = {
        "run_id": current_run.get("run_id", ""),
        "batch_id": current_run.get("batch_id", ""),
        "trigger": current_run.get("trigger", data.get("trigger", "manual")),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_metrics": {
            # Cumulative figure preserved for back-compat; the dashboard
            # uses `current_run_sites` for the Sites Processed KPI.
            "total_sites_processed": data.get("total_sites_processed", 0),
            "current_run_sites": current_run_sites,
            "classifications": classifications,
        },
        "percentages": percentages,
        "top_issues": dict(top_issues),
        "recent_batches": recent_batches,
        "detected_changes": detected_changes,
        "missing_values_site_level": current_run.get("missing_values_site_level", {}),
        "closure_alerts": current_run.get("closure_alerts", []),
        "top_missed_values": current_run.get("top_missed_values", []),
        "status": "healthy" if classifications.get("deferred_low_confidence", 0) < max(current_run_sites, 1) * 0.3 else "needs_attention",
    }

    # Save output (atomic: write to temp, then rename)
    out_path = repo_root / "dashboard_summary.json"
    tmp_path = out_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)
    tmp_path.replace(out_path)

    logger.info("dashboard_summary.json created successfully")

if __name__ == "__main__":
    main()