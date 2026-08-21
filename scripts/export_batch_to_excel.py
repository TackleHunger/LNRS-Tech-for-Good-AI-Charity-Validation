import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("export_batch")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------------------------
# Paths / File Resolution
# ---------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
REPORT_FILE = REPO_ROOT / "ai_validation_report.json"
WEB_EVIDENCE_FILE = REPO_ROOT / "web_evidence_report.json"
REVIEW_LOG_FILE = REPO_ROOT / "review_log.json"
logger.info("Using validation report: %s", REPORT_FILE.resolve())
logger.info("Using web evidence:      %s", WEB_EVIDENCE_FILE.resolve())


def resolve_file(file_name: str) -> Path:
    """
    Finds a file in common repo locations:
      - repo root
      - scripts/
      - src/tackle_hunger/
    """
    candidates = [
        REPO_ROOT / file_name,
        REPO_ROOT / "scripts" / file_name,
        REPO_ROOT / "src" / "tackle_hunger" / file_name,
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    raise FileNotFoundError(
        f"Could not find {file_name}. Tried: " + ", ".join(str(c) for c in candidates)
    )


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# Normalization / Comparison
# ---------------------------

def _digits_only(value: Any) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _normalize_website(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = s.replace("https://", "").replace("http://", "")
    if s.startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    return s


def values_equivalent(field_name: str, current_value: Any, proposed_value: Any) -> bool:
    """
    Return True if current and proposed are effectively the same for the given field.
    """
    if current_value is None and proposed_value is None:
        return True
    if current_value is None or proposed_value is None:
        return False

    if field_name == "publicPhone":
        return _digits_only(current_value) == _digits_only(proposed_value)

    if field_name == "website":
        return _normalize_website(current_value) == _normalize_website(proposed_value)

    return str(current_value).strip() == str(proposed_value).strip()


def normalize_zip_for_export(value: Any) -> Any:
    """
    Preserve ZIP codes as text in Excel (including leading zeros).
    Examples:
      7060 -> 07060
      06001 -> 06001
      08105-1712 -> 08105-1712
    """
    if value is None or value == "":
        return None

    s = str(value).strip()

    # Preserve ZIP+4 exactly if already hyphenated
    if "-" in s:
        left, sep, right = s.partition("-")
        left = left.zfill(5)
        return f"{left}-{right}"

    # Pure digits: pad to 5 when short
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        if len(digits) <= 5:
            return digits.zfill(5)
        # If someone gave 9 digits without hyphen, format as ZIP+4
        if len(digits) == 9:
            return f"{digits[:5]}-{digits[5:]}"
        return digits

    return s


# ---------------------------
# Field Handling
# ---------------------------

def iter_fields(site: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Supports both field shapes:

    1) fields = [
         {"field": "zip", "original_value": "...", ...}
       ]

    2) fields = {
         "zip": {"current_value": "...", "proposed_value": "...", ...}
       }
    """
    fields = site.get("fields", {})

    if isinstance(fields, list):
        for field_data in fields:
            field_name = field_data.get("field", "")
            yield field_name, field_data

    elif isinstance(fields, dict):
        for field_name, field_data in fields.items():
            if isinstance(field_data, dict):
                yield field_name, field_data


def get_site_name(site: Dict[str, Any]) -> str:
    return (
        site.get("site_name")
        or site.get("name")
        or site.get("organization_name")
        or site.get("organizationId")
        or site.get("site_id")
        or ""
    )


def get_classification(site: Dict[str, Any]) -> str:
    return (
        site.get("classification")
        or site.get("summary", {}).get("decision")
        or ""
    )


def get_reason(field_data: Dict[str, Any]) -> str:
    """
    Support both:
      - "reason": "..."
      - "reasons": ["...", "..."]
    """
    if "reason" in field_data and field_data.get("reason") is not None:
        return str(field_data.get("reason"))

    reasons = field_data.get("reasons")
    if isinstance(reasons, list):
        return "; ".join(str(r) for r in reasons)

    if reasons is None:
        return ""

    return str(reasons)


def get_current_value(field_data: Dict[str, Any]) -> Any:
    if "current_value" in field_data:
        return field_data.get("current_value")
    return field_data.get("original_value")


def get_proposed_value(field_name: str, field_data: Dict[str, Any], current_value: Any) -> Any:
    proposed = field_data.get("proposed_value")

    # Suppress duplicate proposed values
    if values_equivalent(field_name, current_value, proposed):
        return None

    return proposed


# ---------------------------
# Main
# ---------------------------

def main():
    try:
        ai_report = load_json(REPORT_FILE)
    except FileNotFoundError:
        logger.error("ai_validation_report.json not found. Cannot generate export.")
        return

    # Load web evidence (optional – export still works without it)
    web_evidence_sites: List[Dict[str, Any]] = []
    if WEB_EVIDENCE_FILE.exists():
        raw_evidence = load_json(WEB_EVIDENCE_FILE)
        # Handle both formats: list of sites or dict with "sites" key
        if isinstance(raw_evidence, list):
            web_evidence_sites = raw_evidence
        elif isinstance(raw_evidence, dict):
            web_evidence_sites = raw_evidence.get("sites", [])
        logger.info("Loaded web evidence with %d sites", len(web_evidence_sites))
    else:
        logger.warning("web_evidence_report.json not found – web evidence columns will be empty")

    # Load review log (optional – for corrected_value column)
    review_entries: List[Dict[str, Any]] = []
    if REVIEW_LOG_FILE.exists():
        try:
            review_entries = load_json(REVIEW_LOG_FILE)
            if not isinstance(review_entries, list):
                review_entries = []
            logger.info("Loaded review log with %d entries", len(review_entries))
        except Exception:
            logger.warning("Could not parse review_log.json – corrected_value column will be empty")
            review_entries = []

    sites = ai_report.get("sites", [])
    validation_rows: List[Dict[str, Any]] = []

    for site in sites:
        site_name = get_site_name(site)
        classification = get_classification(site)
        closure_flag = "POSSIBLE CLOSURE" if site.get("closure_detected") else ""

        # Match web evidence for this site by ID
        site_id = site.get("id")
        matching_evidence = next(
            (s for s in web_evidence_sites
             if s.get("id") == site_id or s.get("site_id") == site_id),
            {},
        )
        web_decision = matching_evidence.get("summary", {}).get("decision", "")

        for field_name, field_data in iter_fields(site):
            current_value = get_current_value(field_data)
            proposed_value = get_proposed_value(field_name, field_data, current_value)

            # ZIP handling
            if field_name == "zip":
                current_value = normalize_zip_for_export(current_value)
                proposed_value = normalize_zip_for_export(proposed_value)

            # Match web evidence for this field
            web_fields = matching_evidence.get("fields", {})
            # Handle both dict-keyed and list-of-dicts formats
            if isinstance(web_fields, dict):
                # Direct key lookup; also try mapped names (publicPhone→phone, etc.)
                field_key_map = {"publicPhone": "phone", "publicEmail": "email", "name": "organization_name"}
                web_match = web_fields.get(field_name) or web_fields.get(field_key_map.get(field_name, ""), {}) or {}
            else:
                web_match = next(
                    (wf for wf in web_fields if wf.get("field") == field_name),
                    {},
                )

            # --- Resolve web-detected value ---
            # Always show what web evidence found, even if it matches the
            # original (so reviewers can see verification vs. no-data).
            detected_web = (
                field_data.get("detected_value")
                or web_match.get("proposed_value")
                or web_match.get("value")
                or web_match.get("detected_value")
                or web_match.get("ai_value")
            )

            # Determine if the web-detected value matches or differs
            if detected_web is not None and values_equivalent(field_name, current_value, detected_web):
                web_status = "verified"
            elif detected_web is not None:
                web_status = "differs"
            else:
                web_status = ""

            # --- Use web evidence to fill gaps ---
            # If the validation report has no proposed_value but web evidence
            # found a different value, promote it into the Proposed Value column.
            web_proposed = web_match.get("proposed_value")
            if proposed_value is None and web_proposed is not None:
                if not values_equivalent(field_name, current_value, web_proposed):
                    proposed_value = web_proposed

            # Use the most informative status: prefer web evidence status
            # when it indicates an actual finding (proposed_update, etc.)
            validation_status = field_data.get("status", "")
            web_evidence_status = web_match.get("status", "")
            if web_evidence_status in ("proposed_update", "proposed_update_low_confidence") and validation_status in ("confirmed", "uncertain", "not_evaluable"):
                display_status = web_evidence_status
            else:
                display_status = validation_status

            # --- Resolve evidence source ---
            # Prefer web evidence source over validation report
            evidence_source = (
                web_match.get("evidence_source_type")
                or field_data.get("evidence_source_type")
                or web_match.get("source")
                or ""
            )

            # --- Resolve reason ---
            # Combine validation reason with web evidence reason
            validation_reason = get_reason(field_data)
            web_reason = web_match.get("reason", "")
            if web_reason and validation_reason:
                combined_reason = f"{validation_reason}; {web_reason}"
            else:
                combined_reason = web_reason or validation_reason

            # --- Resolve evidence URLs ---
            # Primary: validation report (populated by ai_validate.py)
            evidence_url_list = field_data.get("evidence_urls", [])
            # Fallback: extract from web evidence candidates / discovery
            if not evidence_url_list:
                ev_urls = []
                for cand in web_match.get("candidates", []):
                    u = cand.get("url")
                    if u and u not in ev_urls:
                        ev_urls.append(u)
                disc = web_match.get("discovery")
                if isinstance(disc, dict):
                    for dc in disc.get("candidates", []):
                        u = dc.get("url")
                        if u and u not in ev_urls:
                            ev_urls.append(u)
                evidence_url_list = ev_urls

            # --- Resolve change type ---
            change_type_raw = field_data.get("change_type")
            if change_type_raw is None and proposed_value is not None:
                # Derive for backward compat with older reports
                if current_value is None or (isinstance(current_value, str) and current_value.strip() == ""):
                    change_type_raw = "fill_gap"
                else:
                    change_type_raw = "correction"
            change_type_display = {
                "fill_gap": "Missing Value Found",
                "correction": "Data Correction",
            }.get(change_type_raw, "")

            row = {
                "Site Name": site_name,
                "Closure Alert": closure_flag,
                "Field": field_name,
                "Change Type": change_type_display,
                "Original Value": current_value,
                "Proposed Value": proposed_value,
                "Source Tag": field_data.get("source_tag") or "",
                "Confidence": field_data.get("confidence"),
                "Evidence Source": evidence_source,
                "Reason": web_reason or validation_reason,
                "Classification": classification,
                "Status": display_status,
                "Decision (Web)": web_decision,
                "Web Evidence Status": web_evidence_status,
                "Detected Value (Web)": detected_web,
                "Web Match": web_status,
                "Web Confidence": web_match.get("confidence"),
                "Evidence URLs": ", ".join(evidence_url_list),
                # review_outcome is used for future confidence calibration.
                # Once enough reviewed data is collected (300–500+ records),
                # confidence values can be adjusted based on actual
                # acceptance rates.  Blank until a reviewer marks a decision.
                "Review Outcome": field_data.get("review_outcome") or "",
                # run_id and review_timestamp link changes and reviews to
                # specific validation runs for traceability.
                "Run ID": ai_report.get("run_id") or "",
                "Review Timestamp": "",
            }

            # Look up corrected_value from review log
            # Match by site_name + field + proposed_value
            corrected_val = ""
            for rev in review_entries:
                if (rev.get("site_name") == site_name
                        and rev.get("field") == field_name
                        and rev.get("review_outcome") == "rejected"
                        and rev.get("corrected_value")):
                    corrected_val = rev.get("corrected_value", "")
                    # Also pull review_outcome, run_id, review_timestamp if available
                    row["Review Outcome"] = rev.get("review_outcome", "")
                    row["Run ID"] = rev.get("run_id") or row["Run ID"]
                    row["Review Timestamp"] = rev.get("review_timestamp", "")
                    break
            row["Corrected Value"] = corrected_val

            validation_rows.append(row)

        # --- Closure: add operational_status row for closure-detected sites ---
        if site.get("closure_detected"):
            # Extract closure confidence from site fields (status entry)
            closure_conf = 0.7
            for fn, fd in iter_fields(site):
                if fn == "status" and isinstance(fd, dict):
                    closure_conf = fd.get("confidence", 0.7)
                    break
            closure_reason_text = site.get("closure_reason", "Possible closure detected.")
            closure_row: Dict[str, Any] = {
                "Site Name": site_name,
                "Closure Alert": closure_flag,
                "Field": "operational_status",
                "Change Type": "Data Correction",
                "Original Value": "Active",
                "Proposed Value": "Permanently Closed",
                "Source Tag": "",
                "Confidence": closure_conf,
                "Evidence Source": "web_request",
                "Reason": closure_reason_text,
                "Classification": classification,
                "Status": "closure_detected",
                "Decision (Web)": web_decision,
                "Web Evidence Status": "closure_detected",
                "Detected Value (Web)": "Permanently Closed",
                "Web Match": "",
                "Web Confidence": closure_conf,
                "Evidence URLs": "",
                "Review Outcome": "",
                "Run ID": ai_report.get("run_id") or "",
                "Review Timestamp": "",
                "Corrected Value": "",
            }
            # Look up corrected_value from review log for closure
            for rev in review_entries:
                if (rev.get("site_name") == site_name
                        and rev.get("field") == "operational_status"
                        and rev.get("review_outcome") == "rejected"
                        and rev.get("corrected_value")):
                    closure_row["Corrected Value"] = rev.get("corrected_value", "")
                    closure_row["Review Outcome"] = rev.get("review_outcome", "")
                    closure_row["Run ID"] = rev.get("run_id") or closure_row["Run ID"]
                    closure_row["Review Timestamp"] = rev.get("review_timestamp", "")
                    break
            validation_rows.append(closure_row)

    df_validation = pd.DataFrame(validation_rows)

    # Force object/string behavior for ZIP rows before Excel write
    if not df_validation.empty:
        zip_mask = df_validation["Field"] == "zip"
        if zip_mask.any():
            df_validation.loc[zip_mask, "Original Value"] = (
                df_validation.loc[zip_mask, "Original Value"]
                .apply(lambda x: None if x is None else str(x))
            )
            df_validation.loc[zip_mask, "Proposed Value"] = (
                df_validation.loc[zip_mask, "Proposed Value"]
                .apply(lambda x: None if x is None else str(x))
            )

    batch_meta = {
        "batch_id": ai_report.get("batch_id"),
        "pulled_at": ai_report.get("pulled_at"),
        "validated_at": ai_report.get("validated_at"),
        "site_count": ai_report.get("site_count", len(sites)),
        "source_file": str(REPORT_FILE),
    }
    df_meta = pd.DataFrame([batch_meta])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bid = batch_meta.get("batch_id") or "batch"
    output_file = REPO_ROOT / f"{bid}_{ts}_validation_export.xlsx"

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_validation.to_excel(writer, index=False, sheet_name="validation_results")
        df_meta.to_excel(writer, index=False, sheet_name="batch_meta")

        # ---------------------------
        # Excel formatting / polish
        # ---------------------------
        ws = writer.sheets["validation_results"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # Auto-width
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    value_len = len(str(cell.value)) if cell.value is not None else 0
                    if value_len > max_length:
                        max_length = value_len
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 80)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Force ZIP rows to text format in Excel
        # Reordered columns:
        # A Site Name
        # B Closure Alert
        # C Field
        # D Change Type
        # E Original Value
        # F Proposed Value
        # G Source Tag
        # H Confidence
        # I Evidence Source
        # J Reason
        # ... (additional columns shifted by Corrected Value)
        for row_idx in range(2, ws.max_row + 1):
            field_cell = ws[f"C{row_idx}"]
            if field_cell.value == "zip":
                orig_cell = ws[f"E{row_idx}"]
                prop_cell = ws[f"F{row_idx}"]

                if orig_cell.value is not None:
                    orig_cell.value = str(orig_cell.value)
                    orig_cell.number_format = "@"

                if prop_cell.value is not None:
                    prop_cell.value = str(prop_cell.value)
                    prop_cell.number_format = "@"
        # Wrap text for Proposed Value (F) and Reason (J) columns
        from openpyxl.styles import Alignment
        wrap_alignment = Alignment(wrap_text=True, vertical="top")
        for col_letter in ("F", "J"):
            for row_idx in range(2, ws.max_row + 1):
                ws[f"{col_letter}{row_idx}"].alignment = wrap_alignment
    logger.info("Excel export created successfully: %s", output_file)
    logger.info("Source: %s", REPORT_FILE)
    logger.info("Sheets: validation_results, batch_meta")


if __name__ == "__main__":
    main()
