"""
Tackle Hunger - ai_validate.py (rule-based + web-evidence merge)

What it does:
- Reads sites_batch.json (from repo root, scripts/, or src/tackle_hunger/)
- Runs rule-based validation + "AI-style" enrichment
- Merges in web_evidence_report.json when present (now produced with
  controlled web search enrichment - see `web_evidence.ENABLE_WEB_SEARCH`)
- Writes ai_validation_report.json to repo root

Why:
- Keeps validation safe (read-only) while surfacing enrichment candidates
- Produces a structured report that reviewers can use immediately
- Bing / Serper / DuckDuckGo backends are pluggable via env vars in
  `web_evidence.py` (no API key required for the DDG fallback)

The `mode` field in the output report reflects whether the merged web
evidence was gathered with web search enabled. The overall report
structure, scoring thresholds, and normalization rules are unchanged.

Designed to match the intended workflow described in the AI Validate Setup Guide:
src/tackle_hunger/ai_validate.py reads sites_batch.json and outputs ai_validation_report.json
[1](https://reedelsevier-my.sharepoint.com/personal/jonero01_risk_regn_net/_layouts/15/Doc.aspx?sourcedoc=%7B70530E92-D166-458B-9EDF-2B4F56123D35%7D&file=Tackle_Hunger_AI_Validate_Setup_Guide.docx&action=default&mobileredirect=true&DefaultItemOpen=1)
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, cast

# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("ai_validate")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# -----------------------------
# Configuration / Rules
# -----------------------------

SUSPICIOUS_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "yelp.com",
    "business.site",
    "linktr.ee",
    "goo.gl",
    "bit.ly",
    "tinyurl.com",
]

PHONE_DIGITS_RE = re.compile(r"\D+")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
URL_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


# -----------------------------
# Confidence-based Validation Model
# -----------------------------

class FieldValidation:
    """
    Represents the validation result for a single field.
    """
    def __init__(self, field_name: str, original_value: Any):
        self.field_name = field_name
        self.original_value = original_value
        self.proposed_value: Optional[Any] = None
        self.status: str = "not_evaluable"  # confirmed, proposed_update, proposed_update_low_confidence, possible_update, uncertain, not_evaluable
        self.confidence: float = 0.0
        self.reasons: List[str] = []
        self.evidence_source_type: Optional[str] = None
        # Web-detected value from web_evidence_report (always stored,
        # regardless of whether it was promoted to proposed_value).
        self.detected_value: Optional[Any] = None
        self.evidence_urls: List[str] = []
        # Name Confidence Explainer fields (populated only for name field
        # when status == "possible_update" and confidence >= 0.70).
        self.name_confidence_explanation: Optional[str] = None
        self.name_signal_breakdown: Optional[Dict[str, Any]] = None
        # Change type: "fill_gap" (original missing, proposed exists),
        # "correction" (both exist but differ), or None (no change).
        self.change_type: Optional[str] = None
        # Source tag: classifies WHERE a proposed value came from.
        # Values: "platform_email", "third_party_domain", "official_domain",
        # or None. Labelling only — does not affect scoring or gating.
        self.source_tag: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "field": self.field_name,
            "status": self.status,
            "confidence": self.confidence,
            "original_value": self.original_value,
            "proposed_value": self.proposed_value,
            "detected_value": self.detected_value,
            "evidence_urls": self.evidence_urls if self.evidence_urls else [],
            "reasons": self.reasons,
            "evidence_source_type": self.evidence_source_type,
            "change_type": self.change_type,
            "source_tag": self.source_tag,
        }
        # Attach name explainer fields only when populated (additive;
        # never emitted for other fields or for non-update statuses).
        if self.name_signal_breakdown is not None:
            d["name_signal_breakdown"] = self.name_signal_breakdown
        if self.name_confidence_explanation is not None:
            d["name_confidence_explanation"] = self.name_confidence_explanation
        return d

    def set_confirmed(self, value: Any, reason: str = "value_is_valid_and_unchanged"):
        # A confirmed field has no change to propose. We intentionally leave
        # `proposed_value` as None so downstream consumers (CSV export,
        # Detected Changes, etc.) never see a duplicate of `original_value`
        # in the Proposed column. The `value` argument is retained in the
        # signature for backward compatibility and is otherwise unused.
        del value  # explicit: not stored; original_value is the source of truth
        self.status = "confirmed"
        self.confidence = 1.0
        self.reasons.append(reason)

    def set_proposed_update(self, proposed: Any, confidence: float, reason: str):
        self.status = "proposed_update"
        self.confidence = confidence
        self.proposed_value = proposed
        self.reasons.append(reason)

    def set_uncertain(self, confidence: float, reason: str):
        self.status = "uncertain"
        self.confidence = confidence
        self.reasons.append(reason)

    def set_not_evaluable(self, reason: str = "value_is_missing_or_blank"):
        self.status = "not_evaluable"
        self.confidence = 0.1
        self.reasons.append(reason)


# -----------------------------
# Helpers
# -----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"null", "none", "not provided"}


def normalize_phone(raw: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validate and normalize a US phone number.

    Returns (normalized_phone, extension, note) where `note` is one of:
      - None                  : already in canonical (XXX) XXX-XXXX form, valid
      - "normalized_format"   : digits matched, reformatted to canonical form
      - "missing_area_code"   : exactly 7 digits (missing 3-digit area code)
      - "invalid_phone_format": malformed / wrong digit count / unparseable
    `extension` is the trailing extension digits if present (e.g. "x123"),
    or None if no extension was supplied.
    """
    if is_blank(raw):
        return None, None, None

    s = str(raw).strip()

    # Pull out an extension first so it does not skew the digit count.
    ext = None
    ext_match = re.search(r"(?:ext\.?|extension|x|#)\s*([0-9]{1,6})\b", s, flags=re.IGNORECASE)
    if ext_match:
        ext = ext_match.group(1)
        s = s[:ext_match.start()] + s[ext_match.end():]

    digits = PHONE_DIGITS_RE.sub("", s)

    # handle +1 prefix
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    # 7 digits => missing area code
    if len(digits) == 7:
        local = f"{digits[0:3]}-{digits[3:7]}"
        return local, ext, "missing_area_code"

    if len(digits) != 10:
        return None, ext, "invalid_phone_format"

    norm = f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    raw_no_ext = str(raw).strip()
    if ext is not None:
        # strip the original ext marker from raw for comparison
        raw_no_ext = re.sub(r"(?:ext\.?|extension|x|#)\s*[0-9]{1,6}\b", "", raw_no_ext, flags=re.IGNORECASE).strip()
    if raw_no_ext == norm and ext is None:
        return norm, ext, None
    return norm, ext, "normalized_format"


def normalize_string(raw: Any) -> Optional[str]:
    if is_blank(raw):
        return None
    return str(raw).strip()


def validate_email(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (email, note)
    """
    if is_blank(raw):
        return None, None
    s = str(raw).strip()
    if EMAIL_RE.match(s):
        return s, None
    return s, "invalid_email_format"


def normalize_website(raw: Any) -> Tuple[Optional[str], List[str], Optional[str]]:
    """
    Returns (website, flags, suggested_value)
    - Flags suspicious domains
    - Suggests https:// if missing
    """
    if is_blank(raw):
        return None, [], None

    s = str(raw).strip()
    lower = s.lower()

    flags: List[str] = []
    if any(d in lower for d in SUSPICIOUS_DOMAINS):
        flags.append("suspicious_website_domain")

    if not URL_SCHEME_RE.match(s):
        # suggest adding https scheme
        return s, flags, f"https://{s}"

    return s, flags, None


def build_manual_lookup_query(site: Dict[str, Any]) -> str:
    """
    A suggested manual search query reviewers can paste into their browser
    (no web calls performed by this script).
    """
    name: str = (site.get("name") or "").strip()
    city: str = (site.get("city") or "").strip()
    state: str = (site.get("state") or "").strip()
    parts: list[str] = [p for p in [name, city, state, "food pantry", "charity"] if p]
    return " ".join(parts).strip()


def _repo_root() -> Path:
    # this file: .../tackle-hunger/src/tackle_hunger/ai_validate.py
    here = Path(__file__).resolve().parent           # .../src/tackle_hunger
    return here.parent.parent                        # .../tackle-hunger


def _resolve_input_path(input_path: str) -> Path:
    """
    Robustly resolves sites_batch.json regardless of where the user saved it.

    Tries (in order):
    1) input_path as provided
    2) repo_root / input_path
    3) repo_root / sites_batch.json
    4) repo_root / scripts / sites_batch.json
    5) repo_root / src / tackle_hunger / sites_batch.json
    """
    repo = _repo_root()
    candidates = [
        Path(input_path),
        repo / input_path,
        repo / "sites_batch.json",
        repo / "scripts" / "sites_batch.json",
        repo / "src" / "tackle_hunger" / "sites_batch.json",
    ]

    for p in candidates:
        if p.exists():
            return p.resolve()

    attempted = "\n".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "Could not find sites_batch.json. Tried:\n"
        f"{attempted}\n\n"
        f"Current working directory: {Path.cwd()}\n"
        "Fix: Put sites_batch.json in repo root or scripts/ or src/tackle_hunger/, "
        "or run with an explicit path argument."
    )


# -----------------------------
# Name Confidence Explainer
# -----------------------------
#
# Adds explanatory context to suggested name updates (status == "possible_update")
# without modifying scoring, classification, or normalization logic.
# Only produces output when confidence >= 0.70 and strong signals exist.
#
# Signals used:
#   address_match           - the site's address fields align with the evidence source
#   organization_token_match - a recognizable org identity token is shared
#   official_source_detected - evidence came from an official website (web_request / web_scrape)
#   domain_match            - the org's website domain contains org name tokens
#   source_count            - number of distinct evidence source types that contributed

# Well-known organization identity tokens. When both the original and
# proposed names share one of these, it's a strong signal the org is the
# same entity and only the sub-name changed.
_ORG_IDENTITY_TOKENS = {
    "ymca", "ywca", "salvation", "goodwill", "habitat", "redcross",
    "unitedway", "catholiccharities", "feedingamerica", "stvincentdepaul",
    "knights", "rotary", "kiwanis", "elks", "moose", "lions",
    "methodist", "baptist", "lutheran", "presbyterian", "episcopal",
    "adventist", "pentecostal", "catholic", "jewish", "islamic",
}


def _name_tokens(value: Any) -> set[str]:
    """Return a set of lowercased alphanumeric tokens (len >= 2) from a string."""
    if not value:
        return set()
    return {t for t in re.findall(r"[a-z0-9]+", str(value).lower()) if len(t) >= 2}


def _compute_name_signals(
    site: Dict[str, Any],
    original_name: Any,
    proposed_name: Any,
    evidence_source_type: Optional[str],
    web_evidence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute the signal breakdown for a name possible_update.

    Returns:
      {
        "address_match": bool,
        "organization_token_match": bool,
        "official_source_detected": bool,
        "domain_match": bool,
        "source_count": int,
      }
    """
    orig_tokens = _name_tokens(original_name)
    prop_tokens = _name_tokens(proposed_name)

    # --- address_match ---
    # If the web evidence confirms the address fields (streetAddress, city,
    # state) with status == "confirmed", the proposed name is associated
    # with the same physical location.
    address_match = False
    if web_evidence and "fields" in web_evidence:
        addr_fields = ("streetAddress", "city", "state")
        confirmed_addr = 0
        for af in addr_fields:
            ev = web_evidence["fields"].get(af)
            if ev and ev.get("status") == "confirmed":
                confirmed_addr += 1
        address_match = confirmed_addr >= 2  # at least 2 of 3

    # --- organization_token_match ---
    # Check if original and proposed names share a well-known org identity
    # token (e.g. "YMCA"). Also match joined bigrams ("unitedway").
    shared_org_token: Optional[str] = None
    all_tokens = orig_tokens & prop_tokens  # common tokens
    # Try single tokens first.
    for t in all_tokens:
        if t in _ORG_IDENTITY_TOKENS:
            shared_org_token = t.upper()
            break
    # Try joined bigrams from original that also appear in proposed.
    if not shared_org_token:
        orig_list = re.findall(r"[a-z0-9]+", (str(original_name) if original_name else "").lower())
        for i in range(len(orig_list) - 1):
            bigram = orig_list[i] + orig_list[i + 1]
            if bigram in _ORG_IDENTITY_TOKENS:
                # Also must appear in the proposed name tokens.
                prop_joined = "".join(re.findall(r"[a-z0-9]+", (str(proposed_name) if proposed_name else "").lower()))
                if bigram in prop_joined:
                    shared_org_token = bigram.title()
                    break

    organization_token_match = shared_org_token is not None

    # --- official_source_detected ---
    official_sources = {"web_request", "web_scrape", "email_domain"}
    official_source_detected = evidence_source_type in official_sources

    # --- domain_match ---
    # Check whether the site's website domain contains tokens from the org name.
    domain_match = False
    website = site.get("website") or ""
    if website:
        canon = _canonical_url(website)
        if canon:
            domain_core = canon.split("/")[0]  # just the host
            domain_clean = re.sub(r"[^a-z0-9]", "", domain_core)
            if domain_clean:
                # At least 2 name tokens appear in the domain.
                hits = sum(1 for t in (orig_tokens | prop_tokens) if t in domain_clean)
                domain_match = hits >= 2

    # --- source_count ---
    source_types: set[str] = set()
    if web_evidence and "fields" in web_evidence:
        for _fname, fdata in web_evidence["fields"].items():
            if isinstance(fdata, dict):
                src_val = cast(Dict[str, Any], fdata).get("evidence_source_type")
                if isinstance(src_val, str):
                    source_types.add(src_val)
    source_count = len(source_types)

    return {
        "address_match": address_match,
        "organization_token_match": organization_token_match,
        "official_source_detected": official_source_detected,
        "domain_match": domain_match,
        "source_count": source_count,
        # Internal-only: used by the explanation builder, stripped before output.
        "_shared_org_token": shared_org_token,
    }


def _build_name_explanation(
    signals: Dict[str, Any],
    confidence: float,
) -> Optional[str]:
    """
    Construct a human-readable explanation from the signal breakdown.

    Returns None if confidence < 0.70 (guardrail: no explanation for
    weak matches).
    """
    if confidence < 0.70:
        return None

    # Confidence-tier prefix.
    if confidence >= 0.85:
        prefix = "This is a high confidence name update"
    else:
        prefix = "This is likely a name update"

    phrases: List[str] = []
    if signals.get("address_match"):
        phrases.append("a strong address match")
    token = signals.get("_shared_org_token")
    if signals.get("organization_token_match") and token:
        phrases.append(f"shared organization identity ('{token}')")
    if signals.get("official_source_detected"):
        phrases.append("confirmation from an official website source")
    if signals.get("domain_match"):
        phrases.append("domain alignment with organization")
    if (signals.get("source_count") or 0) >= 2:
        phrases.append("support across multiple sources")

    if not phrases:
        return f"{prefix}."

    # Join with commas and 'and' for the last element.
    if len(phrases) == 1:
        detail = phrases[0]
    elif len(phrases) == 2:
        detail = f"{phrases[0]} and {phrases[1]}"
    else:
        detail = ", ".join(phrases[:-1]) + f", and {phrases[-1]}"

    return f"{prefix} based on {detail}."


def _apply_name_explainer(
    name_validation: FieldValidation,
    site: Dict[str, Any],
    web_evidence: Optional[Dict[str, Any]],
) -> None:
    """
    Post-process the name FieldValidation to add the Name Confidence
    Explainer. Only applies when:
      - field is 'name'
      - status is 'proposed_update' (will be changed to 'possible_update')
      - confidence >= 0.70

    Mutates `name_validation` in-place: sets status to 'possible_update'
    and populates `name_signal_breakdown` and `name_confidence_explanation`.

    Does NOT modify scoring, classification, or normalization logic.
    """
    if name_validation.field_name != "name":
        return
    if name_validation.status != "proposed_update":
        return
    if name_validation.confidence < 0.70:
        return

    signals = _compute_name_signals(
        site=site,
        original_name=name_validation.original_value,
        proposed_name=name_validation.proposed_value,
        evidence_source_type=name_validation.evidence_source_type,
        web_evidence=web_evidence,
    )
    explanation = _build_name_explanation(signals, name_validation.confidence)

    if explanation is None:
        return

    # Re-classify from proposed_update -> possible_update (name-specific;
    # more conservative label that signals manual review is expected).
    name_validation.status = "possible_update"

    # Strip internal-only keys before attaching to output.
    public_signals = {k: v for k, v in signals.items() if not k.startswith("_")}
    name_validation.name_signal_breakdown = public_signals
    name_validation.name_confidence_explanation = explanation


# -----------------------------
# Core Validation Logic
# -----------------------------

def _validate_text_field(field_name: str, original_value: Any) -> FieldValidation:
    result = FieldValidation(field_name, original_value)
    normalized = normalize_string(original_value)
    if normalized is None:
        result.set_not_evaluable()
    elif normalized == original_value:
        result.set_confirmed(normalized)
    else:
        result.set_proposed_update(normalized, 0.9, "normalized_whitespace")
    return result


def _validate_phone(original_value: Any) -> FieldValidation:
    result = FieldValidation("publicPhone", original_value)
    if is_blank(original_value):
        result.set_not_evaluable("value_is_missing_or_blank")
        result.confidence = 0.5 # Less penalty for missing phone
        return result

    _norm, _ext, note = normalize_phone(original_value)

    if note == "invalid_phone_format":
        # Malformed numbers should land in Needs Attention with a clear reason.
        # We intentionally mark this `uncertain` (not `proposed_update`) so it
        # is NOT surfaced as a detected change, but IS counted as a quality
        # issue via the `invalid_phone_format` reason.
        result.set_uncertain(0.2, "invalid_phone_format")
        return result

    if note == "missing_area_code":
        # A 7-digit local number is incomplete - there is no canonical full
        # number we can propose without inventing an area code. Mark it as
        # uncertain and leave proposed_value as None so it never surfaces
        # as a duplicate value in Detected Changes / CSV export. The
        # `missing_area_code` reason still flows into Top Issues.
        result.set_uncertain(0.3, "missing_area_code")
        return result

    if note == "normalized_format":
        # Digit-equivalent value; only formatting differs. Treat as confirmed
        # and DO NOT populate proposed_value - a format-only difference is
        # not a real change and must never appear as a proposed update or in
        # Detected Changes. The `normalized_format` reason is still appended
        # so this case continues to be tracked in Top Issues.
        result.status = "confirmed"
        result.confidence = 1.0
        result.reasons.append("normalized_format")
        # Leave proposed_value as None; original_value carries the canonical
        # display value (downstream renderers should show original_value).
        return result

    # note is None => already canonical and valid. Digits match the original,
    # so there is no change to propose. Leave proposed_value as None.
    result.status = "confirmed"
    result.confidence = 1.0
    result.reasons.append("value_is_valid_and_unchanged")
    return result


def _validate_email(original_value: Any) -> FieldValidation:
    result = FieldValidation("publicEmail", original_value)
    if is_blank(original_value):
        result.set_not_evaluable("value_is_missing_or_blank")
        result.confidence = 0.8 # Treat missing email as normal
        return result

    val, note = validate_email(original_value)
    if note == "invalid_email_format":
        result.set_uncertain(0.2, "invalid_email_format")
    else:
        result.set_confirmed(val)
    return result


# Shared helpers (canonical forms for equivalence checks)
try:
    from .utils import canonical_url as _canonical_url, phone_digits as _phone_digits
except ImportError:
    from utils import canonical_url as _canonical_url, phone_digits as _phone_digits  # type: ignore[no-redef]


def _values_equivalent(field_name: str, a: Any, b: Any) -> bool:
    """
    Field-aware equivalence check used for change detection.

    - publicPhone: digit-only comparison (formatting differences ignored)
    - website:    canonical-URL comparison (scheme/www/trailing-slash ignored)
    - other:      strict equality
    """
    if field_name == "publicPhone":
        return _phone_digits(a) == _phone_digits(b)
    if field_name == "website":
        return _canonical_url(a) == _canonical_url(b)
    return a == b


def _validate_website(original_value: Any) -> FieldValidation:
    result = FieldValidation("website", original_value)
    if is_blank(original_value):
        result.set_not_evaluable()
        return result

    val, flags, suggestion = normalize_website(original_value)
    if suggestion:
        # A scheme/www/trailing-slash difference is NOT a real content
        # change. If the canonical forms match, mark confirmed with NO
        # proposed_value (the original is the source of truth). If the
        # canonical forms truly differ, surface the suggestion as an
        # update.
        if _canonical_url(suggestion) == _canonical_url(original_value):
            result.set_confirmed(val, "website_format_equivalent")
        else:
            result.set_proposed_update(suggestion, 0.9, "added_https_scheme")
    else:
        result.set_confirmed(val)

    if "suspicious_website_domain" in flags:
        # Lower confidence if domain is suspicious, even if format is ok
        result.status = "uncertain"
        result.confidence = 0.4
        result.reasons.append("suspicious_website_domain")

    return result


def validate_site(site: Dict[str, Any], web_evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Confidence-based validation for one site (NO web search).
    Produces a detailed report with per-field analysis and an overall classification.
    """
    field_validations: List[FieldValidation] = [
        _validate_text_field("name", site.get("name")),
        _validate_text_field("streetAddress", site.get("streetAddress")),
        _validate_text_field("city", site.get("city")),
        _validate_text_field("state", site.get("state")),
        _validate_text_field("zip", site.get("zip")),
        _validate_phone(site.get("publicPhone")),
        _validate_email(site.get("publicEmail")),
        _validate_website(site.get("website")),
    ]

    # --- Merge Web Evidence ---
    if web_evidence:
        for v in field_validations:
            evidence_field = web_evidence["fields"].get(v.field_name)
            if not evidence_field:
                # Map validation field names to web evidence field names
                if v.field_name == "publicPhone":
                    evidence_field = web_evidence["fields"].get("phone")
                elif v.field_name == "publicEmail":
                    evidence_field = web_evidence["fields"].get("email")
                elif v.field_name == "name":
                    evidence_field = web_evidence["fields"].get("organization_name")

            if evidence_field:
                v.evidence_source_type = evidence_field.get("evidence_source_type")
                v.source_tag = evidence_field.get("source_tag")
                evidence_confidence = evidence_field.get("confidence", 0)
                proposed_value = evidence_field.get("proposed_value")

                # --- Persist web-detected value & evidence URLs ---
                # Store detected_value from whichever key the evidence uses.
                v.detected_value = (
                    evidence_field.get("proposed_value")
                    or evidence_field.get("detected_value")
                    or evidence_field.get("ai_value")
                )
                # Collect evidence URLs from candidates / discovery blocks.
                ev_urls: List[str] = []
                for cand in evidence_field.get("candidates", []):
                    u = cand.get("url")
                    if u:
                        ev_urls.append(u)
                disc = evidence_field.get("discovery")
                if isinstance(disc, dict):
                    disc_typed = cast(Dict[str, Any], disc)
                    for dc in disc_typed.get("candidates", []):
                        u = dc.get("url")
                        if u and u not in ev_urls:
                            ev_urls.append(u)
                v.evidence_urls = ev_urls

                # --- Always propagate web evidence proposed_value ---
                # Web evidence is the single source of truth for changes.
                # Status communicates trust level; the value is NEVER
                # suppressed based on confidence.  Field-aware equivalence
                # still prevents formatting-only duplicates.
                if proposed_value is not None and not _values_equivalent(v.field_name, v.original_value, proposed_value):
                    v.proposed_value = proposed_value
                    v.confidence = evidence_confidence
                    # Prefer the web evidence status when it's meaningful
                    web_ev_status = evidence_field.get("status", "")
                    if web_ev_status in ("proposed_update", "proposed_update_low_confidence"):
                        v.status = web_ev_status
                    elif evidence_confidence > 0.90:
                        v.status = "proposed_update"
                    elif evidence_confidence >= 0.60:
                        v.status = "review"
                    else:
                        v.status = "detected_only"
                    # Append reason with confidence band for traceability
                    if evidence_confidence > 0.90:
                        v.reasons.append(f"web_evidence_high_confidence ({v.evidence_source_type})")
                    elif evidence_confidence >= 0.60:
                        v.reasons.append(f"web_evidence_medium_confidence ({v.evidence_source_type})")
                    else:
                        v.reasons.append(f"web_evidence_low_confidence ({v.evidence_source_type})")
                else:
                    # Value matches original (field-aware) or no proposed
                    # value in evidence → confirm.
                    v.set_confirmed(v.original_value, f"web_evidence_confirmed ({v.evidence_source_type})")
                    v.confidence = evidence_confidence

    # --- Promote Detected Values into Proposed Values ---
    # Ensure detected differences surface in Detected Changes even when
    # the original confidence-based merge was too conservative.  This pass
    # only fills gaps — fields already carrying a proposed_value or already
    # confirmed are left untouched.
    for v in field_validations:
        detected = v.detected_value
        original = v.original_value

        # Nothing to promote if there is no detected value.
        if detected is None:
            continue

        # If detected matches original, confirm (leave proposed_value empty).
        if _values_equivalent(v.field_name, original, detected):
            # Only upgrade status when the field wasn't already confirmed or
            # carrying a stronger status from the merge pass above.
            if v.status in ("uncertain", "not_evaluable"):
                v.status = "confirmed"
                v.reasons.append("detected_value_matches_original")
            continue

        # Detected differs from original → ensure proposed_value is set.
        # Skip if the merge pass already populated a proposed_value.
        if v.proposed_value is not None:
            continue

        v.proposed_value = detected

        if v.confidence >= 0.70:
            v.status = "mismatch"
            v.reasons.append("detected_value_differs_high_confidence")
        elif v.confidence >= 0.40:
            v.status = "review"
            v.reasons.append("detected_value_differs_medium_confidence")
        else:
            v.status = "detected_only"
            v.reasons.append("detected_value_differs_low_confidence")

    # --- Name Confidence Explainer ---
    # After evidence merge, check the name field for a proposed update and
    # attach explanatory context. This does NOT change scoring or
    # classification; it only adds `name_signal_breakdown` and
    # `name_confidence_explanation` when the name has a qualifying update.
    name_validation = next((v for v in field_validations if v.field_name == "name"), None)
    if name_validation is not None:
        _apply_name_explainer(name_validation, site, web_evidence)

    # --- Classify Change Type (Fill Gap vs Correction) ---
    # Computed AFTER all merge + promotion passes so it reflects the
    # final proposed_value.  Does NOT alter scoring / status / confidence.
    for v in field_validations:
        original = v.original_value
        proposed = v.proposed_value
        if proposed is not None and not _values_equivalent(v.field_name, original, proposed):
            if is_blank(original):
                v.change_type = "fill_gap"
            else:
                v.change_type = "correction"
        else:
            v.change_type = None

    # --- Overall Classification ---
    num_fields = len(field_validations)
    if num_fields == 0:
        return {
            "id": site.get("id"),
            "organizationId": site.get("organizationId"),
            "name": site.get("name"),
            "classification": "deferred_low_confidence",
            "overall_confidence": 0,
            "manual_lookup_query": build_manual_lookup_query(site),
            "fields": [],
        }

    confirmed_fields = [v for v in field_validations if v.status == "confirmed"]
    proposed_updates = [v for v in field_validations if v.status in ("proposed_update", "possible_update", "proposed_update_low_confidence", "mismatch", "review", "detected_only")]
    
    percent_confirmed = len(confirmed_fields) / num_fields
    avg_confidence = sum(v.confidence for v in field_validations) / num_fields

    # --- Field-level checks ---
    website_validation = next((v for v in field_validations if v.field_name == "website"), None)
    
    # --- Classification Logic ---
    classification = "deferred_low_confidence" # Default to most restrictive

    # Rule: deferred_low_confidence
    if percent_confirmed < 0.40 or (website_validation and website_validation.confidence < 0.5) or not website_validation:
        classification = "deferred_low_confidence"
    
    # Rule: needs_exception_review
    elif (percent_confirmed >= 0.40 and percent_confirmed < 0.70) or \
         (website_validation and website_validation.status == 'confirmed' and 0.6 <= website_validation.confidence < 0.85):
        classification = "needs_exception_review"

    # Rule: candidate_approved
    elif percent_confirmed >= 0.70 and (website_validation and website_validation.status == 'confirmed' and website_validation.confidence >= 0.85):
        classification = "candidate_approved"

    # Final check: if a site is approved but has proposed updates on critical fields, it should be reviewed.
    if classification == "candidate_approved":
        critical_proposed_updates = [
            p for p in proposed_updates 
            if p.field_name in ["name", "streetAddress", "city", "website", "publicPhone"]
        ]
        if critical_proposed_updates:
            classification = "needs_exception_review"

    # --- Closure Detection ---
    # If web evidence flagged the site as potentially closed, surface it
    # as a site-level flag so downstream (dashboard, export) can alert.
    closure_detected = False
    closure_reason = None
    if web_evidence:
        status_ev = web_evidence.get("fields", {}).get("status") or web_evidence.get("status")
        if isinstance(status_ev, dict):
            status_typed = cast(Dict[str, Any], status_ev)
            if status_typed.get("status") == "closure_detected":
                closure_detected = True
                closure_reason = str(status_typed.get("reason", "Possible closure detected."))

    return {
        "id": site.get("id"),
        "organizationId": site.get("organizationId"),
        "name": site.get("name"),
        "classification": classification,
        "overall_confidence": round(avg_confidence, 3),
        "debug_percent_confirmed": percent_confirmed,
        "manual_lookup_query": build_manual_lookup_query(site),
        "fields": [v.to_dict() for v in field_validations],
        "closure_detected": closure_detected,
        "closure_reason": closure_reason,
    }


def generate_report(batch: Dict[str, Any], site_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates the final structured report.
    """
    classification_counts: Dict[str, int] = {}
    field_status_counts: Dict[str, Dict[str, int]] = {}

    for r in site_results:
        cls = r.get("classification", "Unknown")
        classification_counts[cls] = classification_counts.get(cls, 0) + 1
        for f in r.get("fields", []):
            field_name = f["field"]
            status = f["status"]
            if field_name not in field_status_counts:
                field_status_counts[field_name] = {}
            field_status_counts[field_name][status] = field_status_counts[field_name].get(status, 0) + 1

    # Reflect whether the evidence pipeline ran with web search enrichment
    # enabled. The report structure itself is unchanged - only the value of
    # the existing `mode` string is updated.
    web_search_enabled = False
    try:
        from tackle_hunger.web_evidence import ENABLE_WEB_SEARCH as _ws_flag  # type: ignore
        web_search_enabled = bool(_ws_flag)
    except Exception:
        try:
            from .web_evidence import ENABLE_WEB_SEARCH as _ws_flag  # type: ignore
            web_search_enabled = bool(_ws_flag)
        except Exception:
            web_search_enabled = False
    mode_value = "web_search_enrichment" if web_search_enabled else "no_web_search"

    return {
        "batch_id": batch.get("batch_id", "unknown"),
        "pulled_at": batch.get("pulled_at"),
        "pulled_by": batch.get("pulled_by"),
        "limit": batch.get("limit"),
        "site_count": batch.get("site_count"),
        "validated_at": utc_now_iso(),
        "validated_by": "ai_validate_confidence_v2",
        "mode": mode_value,
        "notes": [
            "This is a confidence-based validation report.",
            "Classification is determined by field-level confidence scores and statuses.",
            "Use manual_lookup_query + trusted sources for final confirmation."
        ],
        "summary": {
            "classification_counts": classification_counts,
            "field_status_counts": field_status_counts,
        },
        "sites": site_results,
    }


# -----------------------------
# Main Entry
# -----------------------------

def validate_batch(input_path: str = "sites_batch.json",
                   output_path: str = "ai_validation_report.json",
                   evidence_path: str = "web_evidence_report.json") -> Dict[str, Any]:
    """
    Main entry point:
    - reads sites_batch.json
    - reads web_evidence_report.json
    - validates each site, merging evidence
    - writes ai_validation_report.json
    """
    input_file = _resolve_input_path(input_path)
    repo = _repo_root()
    output_file = (repo / output_path).resolve()
    evidence_file = (repo / evidence_path).resolve()

    with open(input_file, "r", encoding="utf-8") as f:
        batch = json.load(f)

    web_evidence_map: Dict[str, Dict[str, Any]] = {}
    if evidence_file.exists():
        logger.info("Loading web evidence from: %s", evidence_file)
        with open(evidence_file, "r", encoding="utf-8") as f:
            evidence_data = json.load(f)
            for item in evidence_data:
                web_evidence_map[item["site_id"]] = item
    else:
        logger.warning("Web evidence file not found at: %s. Proceeding without it.", evidence_file)


    sites = batch.get("sites", [])
    logger.info("Using batch file: %s", input_file)
    logger.info("Validating %d sites from batch %s", len(sites), batch.get('batch_id', 'unknown'))

    site_results: List[Dict[str, Any]] = []
    for i, site in enumerate(sites, 1):
        name = site.get("name", "Unknown")
        site_evidence: Optional[Dict[str, Any]] = web_evidence_map.get(str(site.get("id")))
        result = validate_site(site, site_evidence)
        site_results.append(result)
        
        # Structured debug output
        logger.info("[%d/%d] %s", i, len(sites), name)
        logger.debug("  Percent Confirmed: %.2f", result.get('debug_percent_confirmed', 0))
        logger.debug("  Avg Confidence: %.2f", result.get('overall_confidence', 0))
        logger.info("  Classification: %s", result.get('classification', 'N/A'))
        # Evidence alignment debug
        if site_evidence:
            proposed_fields = [f for f in result.get("fields", []) if f.get("proposed_value") is not None]
            ev_fields: Dict[str, Any] = site_evidence.get('fields', {})
            logger.info("  Web Evidence: MATCHED (%d evidence fields)", len(ev_fields))
            if proposed_fields:
                for pf in proposed_fields:
                    logger.debug("    %s: %r -> %r [%s]", pf['field'], pf.get('original_value'), pf.get('proposed_value'), pf.get('status'))
            else:
                logger.debug("  No proposed changes (all confirmed)")
        else:
            logger.info("  Web Evidence: NOT MATCHED")


    report = generate_report(batch, site_results)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Validation complete. Report saved to: %s", output_file)
    logger.info("Summary: %s", report["summary"]["classification_counts"])
    return report


if __name__ == "__main__":
    # Usage:
    #   python src/tackle_hunger/ai_validate.py [input] [output] [evidence]
    #   python src/tackle_hunger/ai_validate.py input output --evidence-path evidence
    import argparse

    parser = argparse.ArgumentParser(description="AI Validate sites batch")
    parser.add_argument("input_path", nargs="?", default="sites_batch.json",
                        help="Path to sites_batch.json")
    parser.add_argument("output_path", nargs="?", default="ai_validation_report.json",
                        help="Path to write ai_validation_report.json")
    parser.add_argument("evidence_path", nargs="?", default="web_evidence_report.json",
                        help="Path to web_evidence_report.json (positional)")
    parser.add_argument("--evidence-path", dest="evidence_path_flag", default=None,
                        help="Path to web_evidence_report.json (named flag)")
    args = parser.parse_args()

    # Named flag takes priority over positional
    evidence = args.evidence_path_flag or args.evidence_path
    validate_batch(args.input_path, args.output_path, evidence)