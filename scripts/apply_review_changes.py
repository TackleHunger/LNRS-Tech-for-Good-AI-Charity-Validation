"""
Write-back reviewed changes to the Tackle Hunger API.

Reads review_log.json (or imports external review log files), determines
the final value for each reviewed field, groups by site, and calls the
``updateSiteFromAI`` GraphQL mutation to persist corrections.

Usage
-----
  # Dry-run (default) — shows what WOULD be pushed, writes nothing
  python scripts/apply_review_changes.py

  # Import a downloaded review log into the repo's master file first
  python scripts/apply_review_changes.py --import "C:\\Users\\...\\review_log (8).json"

  # Actually push to the API (requires approval)
  python scripts/apply_review_changes.py --apply

  # Both at once
  python scripts/apply_review_changes.py --import "review_log (8).json" --apply

Environment
-----------
Requires the same .env / config that ``src/tackle_hunger`` uses for
GraphQL access (GRAPHQL_ENDPOINT, AUTH_TOKEN, etc.).
"""

import argparse
import json
import logging
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_LOG_PATH = REPO_ROOT / "review_log.json"
WRITEBACK_LOG_PATH = REPO_ROOT / "writeback_log.json"

# Fields the dashboard can review — mapped to the GraphQL mutation field names.
# Only these are eligible for write-back.
FIELD_MAP: Dict[str, str] = {
    "publicEmail": "publicEmail",
    "publicPhone": "publicPhone",
    "website": "website",
    # Extend as the dashboard covers more fields:
    # "streetAddress": "streetAddress",
    # "city": "city",
    # "state": "state",
    # "zip": "zip",
    # "description": "description",
    # "hoursText": "hoursText",
}

# The provenance tag sent with every write-back so Tackle Hunger can trace it.
MODIFIED_BY = "tackle-hunger-ai-validation"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("apply_review")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON file expected to contain a list."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw: Any = json.load(f)
        if isinstance(raw, list):
            return list(raw)  # type: ignore[no-any-return]
        return []
    except (json.JSONDecodeError, IOError):
        return []


def _save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    """Atomically write a JSON list to disk."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _entry_key(entry: Dict[str, Any]) -> str:
    """Unique dedup key for a review entry."""
    return (
        f"{entry.get('site_name', '')}|{entry.get('field', '')}|"
        f"{entry.get('proposed_value', '')}|{entry.get('change_type', '')}|"
        f"{entry.get('review_timestamp', '')}"
    )


def _resolve_site_ids(
    entries: List[Dict[str, Any]],
    report_path: Optional[Path] = None,
) -> None:
    """Fill in missing ``site_id`` from the validation report (in-place).

    The AI-detected entries exported from the dashboard don't always carry
    ``site_id`` because it wasn't exposed in the early dashboard versions.
    Manual entries always have it.  We fall back to matching by site name
    in the most recent ``ai_validation_report.json``.
    """
    needs_id = [e for e in entries if not e.get("site_id")]
    if not needs_id:
        return

    # Build name→id lookup from validation report
    rp = report_path or (REPO_ROOT / "ai_validation_report.json")
    name_to_id: Dict[str, str] = {}
    if rp.exists():
        try:
            with open(rp, "r", encoding="utf-8") as f:
                report = json.load(f)
            for site in report.get("sites", []):
                sid = site.get("id")
                sname = site.get("name")
                if sid and sname:
                    name_to_id[sname] = sid
        except (json.JSONDecodeError, IOError):
            pass

    resolved = 0
    for entry in needs_id:
        sid = name_to_id.get(entry.get("site_name", ""))
        if sid:
            entry["site_id"] = sid
            resolved += 1

    # Fallback: cross-reference from other entries in the same review log
    # (manual entries carry site_id; AI-detected entries for the same site
    # may not).
    if resolved < len(needs_id):
        peer_lookup: Dict[str, str] = {}
        for e in entries:
            sid = e.get("site_id")
            sname = e.get("site_name")
            if sid and sname:
                peer_lookup[sname] = sid
        for entry in needs_id:
            if entry.get("site_id"):
                continue
            sid = peer_lookup.get(entry.get("site_name", ""))
            if sid:
                entry["site_id"] = sid
                resolved += 1

    if resolved:
        logger.info("Resolved site_id for %d/%d entries via report + peer lookup", resolved, len(needs_id))
    remaining = len(needs_id) - resolved
    if remaining:
        names = sorted({e.get("site_name", "?") for e in needs_id if not e.get("site_id")})
        logger.warning(
            "%d entries still missing site_id (will be skipped): %s",
            remaining, ", ".join(names),
        )


# ---------------------------------------------------------------------------
# Import / merge
# ---------------------------------------------------------------------------

def import_review_log(source: Path, dest: Path = REVIEW_LOG_PATH) -> List[Dict[str, Any]]:
    """Merge an external review log into the repo's master file.

    De-duplicates by ``_entry_key``.  Returns the merged list.
    """
    existing = _load_json_list(dest)
    incoming = _load_json_list(source)
    if not incoming:
        logger.warning("Import source %s is empty or missing", source)
        return existing

    seen: Set[str] = {_entry_key(e) for e in existing}
    added = 0
    for entry in incoming:
        k = _entry_key(entry)
        if k not in seen:
            existing.append(entry)
            seen.add(k)
            added += 1

    _save_json_list(dest, existing)
    logger.info("Imported %d new entries from %s (%d total)", added, source.name, len(existing))
    return existing


# ---------------------------------------------------------------------------
# Build write-back payload
# ---------------------------------------------------------------------------

def build_writeback_plan(
    entries: List[Dict[str, Any]],
    already_applied: Set[str],
) -> Dict[str, Dict[str, Any]]:
    """Group actionable review entries into per-site mutation payloads.

    Returns ``{site_id: {"site_name": ..., "fields": {gql_field: value}, "sources": [...]}}``
    """
    plan: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    for entry in entries:
        # Skip entries that have already been written back
        ek = _entry_key(entry)
        if ek in already_applied:
            continue

        outcome = entry.get("review_outcome")
        field = entry.get("field", "")
        change_type = entry.get("change_type", "")

        # Determine the final value to write
        if outcome == "accepted":
            value = entry.get("proposed_value")
        elif outcome == "rejected" and entry.get("corrected_value"):
            # Reviewer rejected the AI's suggestion but provided the right value
            value = entry.get("corrected_value")
        elif change_type == "manual_entry" and outcome == "accepted":
            value = entry.get("proposed_value")
        else:
            # "rejected" with no correction → reviewer says leave it alone
            continue

        if value is None:
            continue

        # Must have a site_id to write back
        site_id = entry.get("site_id")
        if not site_id:
            continue

        # Must be a field we know how to map
        gql_field = FIELD_MAP.get(field)
        if not gql_field:
            logger.debug("Skipping unmapped field %s for %s", field, entry.get("site_name"))
            continue

        if site_id not in plan:
            plan[site_id] = {
                "site_name": entry.get("site_name", ""),
                "fields": {},
                "sources": [],
            }

        plan[site_id]["fields"][gql_field] = value
        plan[site_id]["sources"].append({
            "field": field,
            "value": value,
            "change_type": change_type,
            "outcome": outcome,
            "run_id": entry.get("run_id", ""),
            "entry_key": ek,
        })

    return plan


# ---------------------------------------------------------------------------
# Execute write-back
# ---------------------------------------------------------------------------

def execute_writeback(
    plan: Dict[str, Dict[str, Any]],
    *,
    dry_run: bool = True,
) -> List[Dict[str, Any]]:
    """Push reviewed changes to the Tackle Hunger API.

    Args:
        plan: Output of ``build_writeback_plan``.
        dry_run: If True (default), only prints what would happen.

    Returns:
        List of writeback result records (for logging).
    """
    results: List[Dict[str, Any]] = []

    if not plan:
        logger.info("Nothing to write back — no actionable entries.")
        return results

    # Only import the client when we actually need it (and only in --apply mode)
    client = None
    if not dry_run:
        try:
            sys.path.insert(0, str(REPO_ROOT / "src"))
            from tackle_hunger.site_operations import SiteOperations
            from tackle_hunger.graphql_client import TackleHungerClient
            client = SiteOperations(TackleHungerClient())
            logger.info("Connected to Tackle Hunger API")
        except Exception as exc:
            logger.error("Could not initialize API client: %s", exc)
            logger.error("Aborting write-back. Fix configuration and retry.")
            return results

    for site_id, info in plan.items():
        site_name = info["site_name"]
        fields = info["fields"]

        # Always include modifiedBy for provenance
        payload: Dict[str, Any] = {**fields, "modifiedBy": MODIFIED_BY}

        result_record: Dict[str, Any]

        if dry_run:
            logger.info(
                "[DRY-RUN]  %s (%s) → %s",
                site_name, site_id, json.dumps(payload, ensure_ascii=False),
            )
            result_record = {
                "site_id": site_id,
                "site_name": site_name,
                "payload": payload,
                "status": "dry_run",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "applied_entries": [s["entry_key"] for s in info["sources"]],
            }
        else:
            try:
                assert client is not None
                response = client.update_site(site_id, payload)
                logger.info(
                    "[APPLIED]  %s (%s) → %s  response=%s",
                    site_name, site_id, json.dumps(payload, ensure_ascii=False),
                    json.dumps(response, ensure_ascii=False),
                )
                result_record = {
                    "site_id": site_id,
                    "site_name": site_name,
                    "payload": payload,
                    "status": "applied",
                    "api_response": response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "applied_entries": [s["entry_key"] for s in info["sources"]],
                }
            except Exception as exc:
                logger.error(
                    "[FAILED]   %s (%s): %s", site_name, site_id, exc,
                )
                result_record = {
                    "site_id": site_id,
                    "site_name": site_name,
                    "payload": payload,
                    "status": "failed",
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "applied_entries": [s["entry_key"] for s in info["sources"]],
                }

        results.append(result_record)

    return results


# ---------------------------------------------------------------------------
# Persist write-back log
# ---------------------------------------------------------------------------

def save_writeback_log(results: List[Dict[str, Any]], path: Path = WRITEBACK_LOG_PATH) -> None:
    """Append write-back results to the durable log."""
    existing = _load_json_list(path)
    existing.extend(results)
    _save_json_list(path, existing)
    logger.info("Wrote %d results to %s (%d total)", len(results), path.name, len(existing))


def load_applied_keys(path: Path = WRITEBACK_LOG_PATH) -> Set[str]:
    """Load entry keys that have already been successfully applied."""
    existing = _load_json_list(path)
    keys: Set[str] = set()
    for record in existing:
        if record.get("status") == "applied":
            for k in record.get("applied_entries", []):
                keys.add(k)
    return keys


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write reviewed changes back to the Tackle Hunger API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--import", dest="import_file", type=str, default=None,
        help="Path to an external review_log JSON file to merge into the repo's master review_log.json before processing.",
    )
    parser.add_argument(
        "--apply", action="store_true", default=False,
        help="Actually push changes to the API. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="Path to ai_validation_report.json for site_id resolution (default: repo root).",
    )
    args = parser.parse_args()

    # Step 1: Import external file if provided
    if args.import_file:
        source = Path(args.import_file)
        if not source.is_absolute():
            source = Path.cwd() / source
        import_review_log(source)

    # Step 2: Load the master review log
    entries = _load_json_list(REVIEW_LOG_PATH)
    if not entries:
        logger.info("review_log.json is empty — nothing to process.")
        return
    logger.info("Loaded %d review entries from review_log.json", len(entries))

    # Step 3: Resolve missing site_ids
    report_path = Path(args.report) if args.report else None
    _resolve_site_ids(entries, report_path)

    # Step 4: Build the write-back plan (skip already-applied)
    already_applied = load_applied_keys()
    plan = build_writeback_plan(entries, already_applied)

    if not plan:
        logger.info("No new changes to write back.")
        return

    # Step 5: Summary
    total_fields = sum(len(info["fields"]) for info in plan.values())
    logger.info(
        "Write-back plan: %d sites, %d field updates",
        len(plan), total_fields,
    )

    # Step 6: Execute (dry-run or real)
    if not args.apply:
        logger.info("=== DRY-RUN MODE (use --apply to push to API) ===")

    results = execute_writeback(plan, dry_run=not args.apply)

    # Step 7: Save results
    if args.apply:
        save_writeback_log(results)
    else:
        # In dry-run, save to a preview file so user can review
        preview_path = REPO_ROOT / "writeback_preview.json"
        _save_json_list(preview_path, results)
        logger.info("Dry-run preview saved to %s", preview_path.name)

    # Step 8: Final summary
    applied = sum(1 for r in results if r["status"] == "applied")
    failed = sum(1 for r in results if r["status"] == "failed")
    dry = sum(1 for r in results if r["status"] == "dry_run")
    if dry:
        logger.info("Summary: %d site(s) would be updated (dry-run)", dry)
    if applied:
        logger.info("Summary: %d site(s) updated successfully", applied)
    if failed:
        logger.warning("Summary: %d site(s) FAILED — check writeback_log.json", failed)


if __name__ == "__main__":
    main()
