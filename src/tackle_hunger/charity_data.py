"""Centralized data-access layer for charity contact data.

This module is the **single** place the application loads charity contact
information from. Real charity contact data (organization names, addresses,
phone numbers, emails, websites) is kept out of the public source tree in a
git-ignored ``charity-data.json`` file and read through the helpers below.

Design goals
------------
* **Separation of concerns** — no charity contact values are hardcoded in
  source. Code depends on this module; the data lives in ``charity-data.json``.
* **Graceful degradation** — if ``charity-data.json`` is missing or malformed,
  loading returns an *empty* dataset (and logs a warning) instead of raising,
  so UI/scripts keep working with no data rather than crashing.
* **Reconstructable** — the data file can be rebuilt from the pipeline outputs
  with ``python scripts/build_charity_data.py`` (see the README), or dropped in
  from another distribution channel.

File resolution order
---------------------
1. Explicit ``path`` argument to :func:`load_charity_data`.
2. ``CHARITY_DATA_PATH`` environment variable.
3. ``charity-data.json`` in the repository root.

See ``charity-data.example_synthpii.json`` for the expected schema and placeholder
records.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

try:  # TypedDict is stdlib on 3.8+; fall back gracefully if unavailable.
    from typing import TypedDict
except ImportError:  # pragma: no cover - very old runtimes only
    TypedDict = None  # type: ignore[assignment,misc]

__all__ = [
    "CHARITY_DATA_FILENAME",
    "CHARITY_DATA_ENV_VAR",
    "CharitySite",
    "CharityData",
    "resolve_data_path",
    "load_charity_data",
    "data_available",
    "iter_sites",
    "get_site",
    "find_sites_by_name",
    "clear_cache",
]

logger = logging.getLogger(__name__)

#: Canonical filename for the git-ignored charity data file.
CHARITY_DATA_FILENAME = "charity-data.json"

#: Environment variable that may override the data file location.
CHARITY_DATA_ENV_VAR = "CHARITY_DATA_PATH"

#: Schema version written/expected by this project.
SCHEMA_VERSION = "1.0"

# Repository root: this file lives at ``src/tackle_hunger/charity_data.py``.
_REPO_ROOT = Path(__file__).resolve().parents[2]


if TypedDict is not None:

    class CharitySite(TypedDict, total=False):
        """A single charity service-location (Site) contact record."""

        id: str
        organizationId: str
        name: str
        streetAddress: str
        addressLine2: str
        city: str
        state: str
        zip: str
        country: str
        publicEmail: str
        publicPhone: str
        contactEmail: str
        contactName: str
        contactPhone: str
        website: str
        socialMedia: str

    class CharityData(TypedDict, total=False):
        """Top-level shape of ``charity-data.json``."""

        schema_version: str
        generated_at: Optional[str]
        source: str
        site_count: int
        sites: List["CharitySite"]

else:  # pragma: no cover - typing fallback only
    CharitySite = dict  # type: ignore[assignment,misc]
    CharityData = dict  # type: ignore[assignment,misc]


def _empty_dataset() -> "CharityData":
    """Return a valid, empty dataset used when no data is available."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": None,
        "source": "unavailable",
        "site_count": 0,
        "sites": [],
    }


# Simple per-path cache so repeated calls don't re-read from disk.
_CACHE: Dict[str, "CharityData"] = {}


def resolve_data_path(path: Optional[os.PathLike[str] | str] = None) -> Path:
    """Resolve the path to ``charity-data.json``.

    Resolution order: explicit ``path`` → ``CHARITY_DATA_PATH`` env var →
    ``charity-data.json`` in the repository root.
    """
    if path is not None:
        return Path(path).expanduser()

    env_path = os.environ.get(CHARITY_DATA_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()

    return _REPO_ROOT / CHARITY_DATA_FILENAME


def load_charity_data(
    path: Optional[os.PathLike[str] | str] = None,
    *,
    use_cache: bool = True,
) -> "CharityData":
    """Load charity contact data from ``charity-data.json``.

    Returns a :class:`CharityData` mapping. If the file is missing or cannot be
    parsed, logs a warning and returns an **empty** dataset so callers can
    degrade gracefully instead of crashing.

    Parameters
    ----------
    path:
        Optional explicit path. See :func:`resolve_data_path` for resolution.
    use_cache:
        Reuse a previously loaded dataset for the same resolved path.
    """
    resolved = resolve_data_path(path)
    cache_key = str(resolved)

    if use_cache and cache_key in _CACHE:
        return _CACHE[cache_key]

    dataset: "CharityData"
    if not resolved.exists():
        logger.warning(
            "Charity data file not found at %s. Returning empty dataset. "
            "Create %s (see charity-data.example_synthpii.json) or run "
            "'python scripts/build_charity_data.py' to reconstruct it.",
            resolved,
            CHARITY_DATA_FILENAME,
        )
        dataset = _empty_dataset()
    else:
        try:
            with resolved.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to read charity data from %s (%s). "
                "Returning empty dataset.",
                resolved,
                exc,
            )
            dataset = _empty_dataset()
        else:
            dataset = _normalize(raw)

    if use_cache:
        _CACHE[cache_key] = dataset
    return dataset


def _normalize(raw: object) -> "CharityData":
    """Coerce arbitrary parsed JSON into a valid :class:`CharityData`."""
    if not isinstance(raw, dict):
        logger.warning(
            "Charity data root is %s, expected an object. Using empty dataset.",
            type(raw).__name__,
        )
        return _empty_dataset()

    raw_dict = cast(Dict[str, Any], raw)
    sites_raw = raw_dict.get("sites")
    sites: List["CharitySite"] = []
    if isinstance(sites_raw, list):
        sites = [
            cast("CharitySite", s)
            for s in cast(List[Any], sites_raw)
            if isinstance(s, dict)
        ]
    elif sites_raw is not None:
        logger.warning(
            "Charity data 'sites' is %s, expected a list. Treating as empty.",
            type(sites_raw).__name__,
        )

    return {
        "schema_version": str(raw_dict.get("schema_version", SCHEMA_VERSION)),
        "generated_at": raw_dict.get("generated_at"),
        "source": str(raw_dict.get("source", "charity-data.json")),
        "site_count": len(sites),
        "sites": sites,
    }


def data_available(path: Optional[os.PathLike[str] | str] = None) -> bool:
    """Return ``True`` if charity data is present and contains at least one site."""
    return bool(load_charity_data(path).get("sites"))


def iter_sites(path: Optional[os.PathLike[str] | str] = None) -> List["CharitySite"]:
    """Return the list of charity site records (possibly empty)."""
    return list(load_charity_data(path).get("sites", []))


def get_site(
    site_id: str,
    path: Optional[os.PathLike[str] | str] = None,
) -> Optional["CharitySite"]:
    """Return the site record whose ``id`` matches ``site_id``, or ``None``."""
    if not site_id:
        return None
    for site in iter_sites(path):
        if site.get("id") == site_id:
            return site
    return None


def find_sites_by_name(
    name: str,
    path: Optional[os.PathLike[str] | str] = None,
) -> List["CharitySite"]:
    """Return all site records whose ``name`` matches ``name`` (case-insensitive)."""
    if not name:
        return []
    needle = name.strip().casefold()
    return [s for s in iter_sites(path) if str(s.get("name", "")).casefold() == needle]


def clear_cache() -> None:
    """Clear the in-memory dataset cache (useful in tests / after a rebuild)."""
    _CACHE.clear()
