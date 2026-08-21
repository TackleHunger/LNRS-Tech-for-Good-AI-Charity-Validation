#!/usr/bin/env python3
"""Reconstruct ``charity-data.json`` from local pipeline artifacts.

``charity-data.json`` is the single, git-ignored, canonical store of charity
contact data used by :mod:`tackle_hunger.charity_data`. Because charity data
originates from the Tackle Hunger API (it is a *pull-based* pipeline), the file
is a **derived** artifact: this script aggregates the contact fields from the
most recent pipeline outputs into that one consolidated file.

Primary source: ``sites_batch.json`` (the batch of sites pulled from the API).
Optional enrichment: ``ai_validation_report.json`` (accepted proposed values).

Usage
-----
    python scripts/build_charity_data.py
    python scripts/build_charity_data.py --sites sites_batch.json --out charity-data.json

The script degrades gracefully: if no source artifact is found it still writes a
valid, empty ``charity-data.json`` and exits 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Contact-oriented fields we persist into charity-data.json.
_CONTACT_FIELDS = (
    "id",
    "organizationId",
    "name",
    "streetAddress",
    "addressLine2",
    "city",
    "state",
    "zip",
    "country",
    "publicEmail",
    "publicPhone",
    "contactEmail",
    "contactName",
    "contactPhone",
    "website",
    "socialMedia",
)


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] could not read {path}: {exc}", file=sys.stderr)
        return None


def _extract_site(record: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only contact-oriented fields, dropping null/empty values."""
    out: Dict[str, Any] = {}
    for field in _CONTACT_FIELDS:
        value = record.get(field)
        if value not in (None, ""):
            out[field] = value
    return out


def build_dataset(sites_path: Path, report_path: Optional[Path]) -> Dict[str, Any]:
    sites_doc = _load_json(sites_path)
    raw_sites: List[Dict[str, Any]] = []
    if isinstance(sites_doc, dict):
        sites_doc_dict = cast(Dict[str, Any], sites_doc)
        sites_value = sites_doc_dict.get("sites")
        if isinstance(sites_value, list):
            raw_sites = [
                cast(Dict[str, Any], s)
                for s in cast(List[Any], sites_value)
                if isinstance(s, dict)
            ]
        else:
            print(
                f"[warn] {sites_path.name} has no 'sites' list — writing an empty dataset.",
                file=sys.stderr,
            )
    elif sites_doc is None:
        print(
            f"[warn] {sites_path.name} not found — writing an empty dataset.",
            file=sys.stderr,
        )
    else:
        print(
            f"[warn] {sites_path.name} is not a JSON object — writing an empty dataset.",
            file=sys.stderr,
        )

    sites = [_extract_site(s) for s in raw_sites]
    sites = [s for s in sites if s]  # drop any that had no contact fields

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": f"reconstructed from {sites_path.name}",
        "site_count": len(sites),
        "sites": sites,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sites",
        default=str(_REPO_ROOT / "sites_batch.json"),
        help="Path to the pulled sites batch (default: sites_batch.json).",
    )
    parser.add_argument(
        "--report",
        default=str(_REPO_ROOT / "ai_validation_report.json"),
        help="Optional AI validation report for enrichment (default: ai_validation_report.json).",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "charity-data.json"),
        help="Output path (default: charity-data.json).",
    )
    args = parser.parse_args(argv)

    sites_path = Path(args.sites)
    report_path = Path(args.report) if args.report else None
    out_path = Path(args.out)

    dataset = build_dataset(sites_path, report_path)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Wrote {dataset['site_count']} site record(s) to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
