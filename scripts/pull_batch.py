"""
Pull a batch of sites from the Tackle Hunger API for AI validation.

This script replaces the inline Python in the GitHub Actions workflow,
making the pull step testable and runnable locally.

Usage
-----
  # Pull 50 sites (default)
  python scripts/pull_batch.py

  # Pull specific count
  python scripts/pull_batch.py --limit 100

  # Use a specific seed (for reproducible rotation)
  python scripts/pull_batch.py --limit 50 --seed "2026-06-17-run1"

  # Use coverage ledger for deterministic next-batch selection
  python scripts/pull_batch.py --limit 50 --use-coverage

Environment
-----------
Requires: AI_SCRAPING_TOKEN, ENVIRONMENT (dev|staging|production)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("pull_batch")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Coverage ledger
# ---------------------------------------------------------------------------
COVERAGE_LEDGER_PATH = REPO_ROOT / "coverage_ledger.json"


def _load_coverage_ledger() -> Dict[str, str]:
    """Load {site_id: last_validated_date} mapping."""
    if not COVERAGE_LEDGER_PATH.exists():
        return {}
    try:
        with open(COVERAGE_LEDGER_PATH, "r", encoding="utf-8") as f:
            raw: Any = json.load(f)
        if isinstance(raw, dict):
            return dict(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _save_coverage_ledger(ledger: Dict[str, str]) -> None:
    """Persist coverage ledger atomically."""
    tmp = COVERAGE_LEDGER_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    tmp.replace(COVERAGE_LEDGER_PATH)


def _select_by_coverage(
    sites: List[Dict[str, Any]],
    ledger: Dict[str, str],
    limit: int,
) -> List[Dict[str, Any]]:
    """Select the `limit` sites that were least recently validated.

    Sites never validated sort first, then oldest validated date.
    """
    def sort_key(site: Dict[str, Any]) -> str:
        sid = site.get("id", "")
        return ledger.get(sid, "0000-00-00")

    sorted_sites = sorted(sites, key=sort_key)
    return sorted_sites[:limit]


def _update_coverage_ledger(
    sites: List[Dict[str, Any]],
    ledger: Dict[str, str],
) -> Dict[str, str]:
    """Mark sites as validated today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for site in sites:
        sid = site.get("id")
        if sid:
            ledger[sid] = today
    return ledger


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def pull_batch(
    limit: int = 50,
    seed: Optional[str] = None,
    use_coverage: bool = False,
    actor: str = "unknown",
    trigger: str = "manual",
) -> Path:
    """Pull a batch of sites and write sites_batch.json.

    Args:
        limit: Number of sites to pull.
        seed: Rotation seed (ignored if use_coverage=True).
        use_coverage: Use coverage ledger instead of random rotation.
        actor: Who triggered (GitHub actor or local username).
        trigger: 'manual', 'scheduled', or 'local'.

    Returns:
        Path to the generated sites_batch.json.
    """
    from tackle_hunger.graphql_client import TackleHungerClient
    from tackle_hunger.site_operations import SiteOperations

    client = TackleHungerClient()
    ops = SiteOperations(client)

    if use_coverage:
        # Pull all sites (minimal for speed), then select by coverage
        logger.info("Fetching full site list for coverage-based selection...")
        all_sites = ops.get_sites_for_ai(limit=None, seed=None)
        logger.info("API returned %d total sites", len(all_sites))

        ledger = _load_coverage_ledger()
        selected = _select_by_coverage(all_sites, ledger, limit)

        # Now fetch full details for the selected sites if we used minimal
        # (In current implementation get_sites_for_ai returns full details,
        # so selected already has them.)
        sites = selected

        # Update ledger
        ledger = _update_coverage_ledger(sites, ledger)
        _save_coverage_ledger(ledger)
        logger.info("Coverage ledger updated (%d total sites tracked)", len(ledger))
    else:
        # Use seed-based rotation (original behavior)
        sites = ops.get_sites_for_ai(limit=limit, seed=seed)

    # Build batch payload
    batch_seed = seed or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    batch: Dict[str, Any] = {
        "batch_id": batch_seed,
        "pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pulled_by": actor,
        "trigger": trigger,
        "limit": limit,
        "site_count": len(sites),
        "selection_method": "coverage_ledger" if use_coverage else "seed_rotation",
        "sites": sites,
    }

    out_path = REPO_ROOT / "sites_batch.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    logger.info("Pulled %d sites → %s (method: %s)",
                len(sites), out_path.name, batch["selection_method"])
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull a batch of sites from the Tackle Hunger API.",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Number of sites to pull (default: 50).",
    )
    parser.add_argument(
        "--seed", type=str, default=None,
        help="Rotation seed for reproducibility (ignored with --use-coverage).",
    )
    parser.add_argument(
        "--use-coverage", action="store_true", default=False,
        help="Use coverage ledger to select least-recently-validated sites.",
    )
    parser.add_argument(
        "--actor", type=str, default=os.getenv("ACTOR", os.getenv("USERNAME", "local")),
        help="Who triggered this pull.",
    )
    parser.add_argument(
        "--trigger", type=str, default="local",
        choices=["manual", "scheduled", "local"],
        help="How this pull was triggered.",
    )
    args = parser.parse_args()

    pull_batch(
        limit=args.limit,
        seed=args.seed,
        use_coverage=args.use_coverage,
        actor=args.actor,
        trigger=args.trigger,
    )


if __name__ == "__main__":
    main()
