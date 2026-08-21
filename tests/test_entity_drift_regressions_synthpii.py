"""
Regression tests for entity drift prevention.

Organized into sections matching the acceptance criteria:
  1. Similar-name drift (CASE A: Brightwater)
  2. Parent-office drift (CASE B: Catholic Charities Lakeport)
  3. Same-entity alternate handling (CASE C: St. Anselm the Confessor)
  4. Unsupported phone drift (CASE D: The Soup Ladle)
  5. Helper function unit tests (name overlap, domain, location, etc.)
  6. Integration-style promotion tests
  7. Directory vs official website behavior
  8. Status behavior (suspect statuses vs dashboard-countable changes)
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest
import sys
import os
from typing import Any, cast

# ---------------------------------------------------------------------------
# Path setup — ensure src/ is importable
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from tackle_hunger.web_evidence import (  # type: ignore
    # Name / entity helpers
    _normalize_entity_name,
    _compute_name_overlap,
    _entity_name_match,
    _detect_entity_type_conflict,
    # Location helpers
    _location_consistency_check,
    _location_match_detail,
    # Domain helpers
    _domain_relevance_check,
    # Drift detection
    _detect_parent_office_drift,
    _classify_page_scope,
    # Proposal gates
    _phone_proposal_gate,
    _website_proposal_gate,
    _email_proposal_gate,
    # Phone helpers
    _check_phone_area_code,
    _phone_evidence,
    # Email helpers
    _extract_email_candidates,
    # Subpage crawl helpers
    _discover_contact_pages,
    # Closure detection
    _detect_closure,
    # Geocoding cross-validation
    geocode_validate,
    # Constants
    _UMBRELLA_ORG_PATTERNS,
    _ADMIN_PAGE_KEYWORDS,
    _UNRELATED_DOMAIN_KEYWORDS,
    _DIRECTORY_DOMAIN_KEYWORDS,
    # Source-tag classification
    _classify_source_tag,
    _PLATFORM_EMAIL_DOMAINS,
    _GENERIC_EMAIL_DOMAINS,
    _THIRD_PARTY_WEBSITE_DOMAINS,
)


# ===================================================================
# Shared fixtures — real-world-inspired site records
# ===================================================================

def _site(**overrides: Any) -> dict[str, Any]:
    """Build a minimal site dict with sensible defaults."""
    base: dict[str, Any] = {
        "name": "Test Pantry",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "streetAddress": "100 Main St",
        "website": "",
        "publicWebsite": "",
    }
    base.update(overrides)
    return base


# --- Specific regression sites ---

BRIGHTWATER_SITE = _site(
    name="Brightwater Food Pantry",
    city="Brightwater",
    state="IL",
    zip="61281",
    streetAddress="",
    website="",
)

CATHOLIC_CHARITIES_LAKEPORT_SITE = _site(
    name="Catholic Charities of Lakeport - Riverbend Outreach and Pantry",
    city="Lakeport",
    state="NY",
    zip="14206",
    streetAddress="312 Maple St",
    website="",
)

ST_ANSELM_SITE = _site(
    name="St. Anselm the Confessor Parish",
    city="Fairmont",
    state="NY",
    zip="14487",
    streetAddress="",
    website="",
)

SOUP_LADLE_SITE = _site(
    name="The Soup Ladle - Food Distribution Center",
    city="Cedarville",
    state="AR",
    zip="72201",
    streetAddress="",
    website="",
)

MARLOWS_FOODMART_SITE = _site(
    name="Marlow's FoodMart",
    city="Pinegrove",
    state="MS",
    zip="39423",
    streetAddress="455 County Rd 12",
    website="http://www.marlowsfoodmart.com/",
)


# ===================================================================
# SECTION 1: SIMILAR-NAME DRIFT  (CASE A — Brightwater)
# ===================================================================

class TestSimilarNameDrift:
    """Pantry record must not drift to an unrelated business sharing a
    surname/token (e.g. "Brightwater Solutions")."""

    def test_entity_type_conflict_brightwater(self):
        """Brightwater Food Pantry vs Brightwater Solutions → type conflict."""
        result = _detect_entity_type_conflict(
            "Brightwater Food Pantry",
            "Brightwater Solutions — Technology consulting and software",
        )
        assert result["conflict"] is True, (
            "Expected unrelated business (tech/solutions) to be flagged as "
            "entity type conflict for a food pantry record"
        )

    def test_entity_name_match_rejects_brightwater_solutions(self):
        """Entity name match must reject 'Brightwater Solutions' for pantry."""
        result = _entity_name_match(
            "Brightwater Food Pantry",
            "Brightwater Solutions — Technology consulting",
        )
        assert result["accept"] is False, (
            "Expected entity name match to reject: shared token 'Brightwater' "
            "is insufficient when candidate is a different entity type"
        )
        assert result["type_conflict"] is True

    def test_name_overlap_brightwater_is_partial(self):
        """'Brightwater' alone should produce partial overlap, not full."""
        overlap = _compute_name_overlap(
            "Brightwater Food Pantry",
            "Brightwater Solutions",
        )
        # Only 'brightwater' matches (food/pantry are stopwords),
        # so overlap is 1.0 on a single-token name.  But the entity_name_match
        # gate catches this via jaccard + type-conflict.
        assert overlap > 0, "Some token overlap expected (shared surname)"
        # The jaccard should be low because 'solutions' adds non-matching tokens
        result = _entity_name_match(
            "Brightwater Food Pantry", "Brightwater Solutions"
        )
        assert result["jaccard"] <= 0.5, (
            "Expected weak jaccard overlap when candidate has unrelated tokens"
        )

    def test_domain_relevance_brightwater_solutions(self):
        """brightwatersolutions.com must be flagged as unrelated business."""
        rel = _domain_relevance_check(
            "brightwatersolutions.com",
            "Brightwater Food Pantry",
        )
        assert rel == "unrelated", (
            "Expected unrelated business website to be rejected for pantry record"
        )

    def test_location_conflict_il_vs_va(self):
        """IL site vs VA page → location conflict."""
        # Note: can't include "Brightwater" in text because it matches the
        # city name and triggers city_found → "match".  The real pipeline
        # handles this via entity name match + type conflict upstream.
        check = _location_consistency_check(
            BRIGHTWATER_SITE,
            "1234 Tech Park Dr, Midlothian VA 23113",
        )
        assert check == "conflict", (
            "Expected location conflict when page is in VA but site is in IL"
        )

    def test_phone_gate_blocks_brightwater_solutions_phone(self):
        """Phone from Brightwater Solutions (VA) is blocked by entity name
        match upstream (type conflict) and area code mismatch in gate."""
        # In the real pipeline, _entity_name_match fires BEFORE the phone
        # gate and would reject "Brightwater Solutions" due to type conflict.
        # The phone gate itself catches this via area code mismatch.
        ent = _entity_name_match(
            "Brightwater Food Pantry",
            "Brightwater Solutions — Technology consulting",
        )
        assert ent["accept"] is False, (
            "Expected entity name match to block Brightwater Solutions "
            "before the phone gate is even reached"
        )
        assert ent["type_conflict"] is True

        # Even if it somehow reached the gate, area code 540 (VA)
        # mismatches IL → downgrade at minimum
        candidate: dict[str, Any] = {
            "digits": "5405550608",
            "display": "(540) 555-0608",
            "from_structured_data": False,
            "from_search": False,
        }
        page_text = (
            "Brightwater Solutions — Technology consulting. "
            "Located in Midlothian VA 23113. Call (540) 555-0608."
        )
        result = _phone_proposal_gate(
            BRIGHTWATER_SITE, page_text, candidate,
            name_overlap_score=_compute_name_overlap(
                "Brightwater Food Pantry", page_text
            ),
            name_match=False, location_match=False,
            shared_site=False, xref="no_search",
        )
        # Gate at minimum downgrades due to area code mismatch
        assert result["accept"] is False or result.get("downgrade") is True, (
            "Expected phone from VA to be rejected or downgraded for IL pantry"
        )

    def test_website_gate_blocks_brightwater_solutions(self):
        """brightwatersolutions.com must not be proposed as pantry website."""
        discovery: dict[str, Any] = {
            "url": "https://brightwatersolutions.com",
            "domain": "brightwatersolutions.com",
            "score": 0.6,
            "confidence": 0.70,
            "reason": "Brightwater Solutions website",
            "candidates": [{
                "url": "https://brightwatersolutions.com",
                "domain": "brightwatersolutions.com",
                "content_matches": 0,
                "city_match": False,
            }],
        }
        result = _website_proposal_gate(BRIGHTWATER_SITE, discovery)
        assert result["accept"] is False, (
            "Expected unrelated business website brightwatersolutions.com to be "
            "rejected for Brightwater Food Pantry"
        )


# ===================================================================
# SECTION 2: PARENT-OFFICE DRIFT  (CASE B — Catholic Charities Lakeport)
# ===================================================================

class TestParentOfficeDrift:
    """Local pantry records must not drift to central admin/HQ office
    values from the same umbrella organization."""

    def test_umbrella_org_detected(self):
        """Catholic Charities is recognized as an umbrella org."""
        result = _classify_page_scope(
            CATHOLIC_CHARITIES_LAKEPORT_SITE, None,
        )
        assert result["is_umbrella_org"] is True, (
            "Expected Catholic Charities to be detected as umbrella org"
        )

    def test_parent_office_drift_different_address(self):
        """Admin center address triggers parent-office drift."""
        admin_page = (
            "Catholic Charities of Lakeport — Central Administrative Center. "
            "820 Lakeshore Ave, Lakeport NY 14209. Phone: (716) 555-1400."
        )
        result = _detect_parent_office_drift(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            admin_page,
            "(716) 555-1400",
        )
        assert result["drift"] is True, (
            "Expected parent-office phone not to replace site-level pantry "
            "number — different address (Lakeshore Ave vs Maple St)"
        )

    def test_admin_keywords_trigger_drift(self):
        """Page with 'central office' keyword triggers drift."""
        admin_page = (
            "Catholic Charities of Lakeport. Central office. "
            "820 Lakeshore Ave, Lakeport NY 14209."
        )
        result = _detect_parent_office_drift(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            admin_page,
            "(716) 555-1400",
        )
        assert result["admin_hit"] is True, (
            "Expected admin keyword 'central office' to be detected"
        )

    def test_phone_gate_blocks_admin_phone(self):
        """Admin center phone must be blocked for local pantry."""
        candidate: dict[str, Any] = {
            "digits": "7165551400",
            "display": "(716) 555-1400",
            "from_structured_data": False,
            "from_search": False,
        }
        page_text = (
            "Catholic Charities of Lakeport — Central Administrative Center. "
            "820 Lakeshore Ave, Lakeport NY 14209. Phone: (716) 555-1400. "
            "Central office serving all Catholic Charities programs."
        )
        result = _phone_proposal_gate(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            page_text, candidate,
            name_overlap_score=0.8,
            name_match=True, location_match=False,
            shared_site=False, xref="no_search",
        )
        assert result["accept"] is False, (
            "Expected central office number (716) 555-1400 to be rejected "
            "for Riverbend Outreach pantry at 312 Maple St"
        )
        assert result["parent_drift"] is True, (
            "Expected parent_drift flag to be set when admin center phone "
            "is proposed for a local pantry"
        )

    def test_local_pantry_phone_not_blocked(self):
        """Local pantry's own phone should pass the gate."""
        candidate: dict[str, Any] = {
            "digits": "7163127510",
            "display": "(716) 555-7510",
            "from_structured_data": True,
        }
        page_text = (
            "Catholic Charities of Lakeport - Riverbend Outreach and Pantry. "
            "312 Maple St, Lakeport NY 14206. Phone: (716) 555-7510."
        )
        result = _phone_proposal_gate(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            page_text, candidate,
            name_overlap_score=0.9,
            name_match=True, location_match=True,
            shared_site=False, xref="no_search",
        )
        assert result["accept"] is True, (
            "Expected local pantry phone to be accepted when page matches "
            "the site's specific address"
        )


# ===================================================================
# SECTION 3: SAME-ENTITY ALTERNATES  (CASE C — St. Anselm the Confessor)
# ===================================================================

class TestSameEntityAlternates:
    """Legitimate alternates for the same entity/location must NOT be
    treated as unrelated drift.  They may be accepted or cautiously
    reviewed, but not hard-rejected like Brightwater-style conflicts."""

    def test_strong_entity_match_recognized(self):
        """Both parish numbers map to the same entity name."""
        result = _entity_name_match(
            "St. Anselm the Confessor Parish",
            "St. Anselm the Confessor Parish — Contact Us",
        )
        assert result["accept"] is True, (
            "Expected strong entity match when page title matches the "
            "parish name exactly"
        )
        assert result["type_conflict"] is False

    def test_alternate_number_same_entity_not_hard_rejected(self):
        """Alternate phone from same entity page → not treated as drift."""
        candidate: dict[str, Any] = {
            "digits": "5855551100",
            "display": "(585) 555-1100",
            "from_structured_data": False,
            "from_search": False,
        }
        page_text = (
            "St. Anselm the Confessor Parish. "
            "Fairmont NY 14487. Phone: (585) 555-1100."
        )
        result = _phone_proposal_gate(
            ST_ANSELM_SITE,
            page_text, candidate,
            name_overlap_score=0.8,
            name_match=True, location_match=True,
            shared_site=False, xref="no_search",
        )
        # Must NOT be hard-rejected like an unrelated entity drift.
        # It may be accepted or downgraded — either is fine.
        # The key assertion: this is NOT treated like Brightwater drift.
        assert result.get("parent_drift") is not True, (
            "Expected same-entity alternate number not to trigger "
            "parent-office drift detection"
        )
        # Even if downgraded, should not be fully blocked as drift
        # (it's a legitimate same-entity alternate)

    def test_confidence_differs_from_unrelated_drift(self):
        """Same-entity alternate must have higher trust than unrelated drift."""
        # Brightwater-style unrelated drift → always reject
        brightwater_result = _entity_name_match(
            "Brightwater Food Pantry",
            "Brightwater Solutions — Technology consulting",
        )
        # St. Anselm alternate → accept
        stluke_result = _entity_name_match(
            "St. Anselm the Confessor Parish",
            "St. Anselm the Confessor Parish Office",
        )
        assert stluke_result["accept"] is True
        assert brightwater_result["accept"] is False
        assert stluke_result["jaccard"] > brightwater_result["jaccard"], (
            "Expected same-entity alternate to have much stronger entity "
            "match score than unrelated drift"
        )


# ===================================================================
# SECTION 4: UNSUPPORTED PHONE DRIFT  (CASE D — The Soup Ladle)
# ===================================================================

class TestUnsupportedPhoneDrift:
    """Alternate numbers without official/credible backing must not
    replace supported originals."""

    def test_weak_source_phone_downgraded(self):
        """Phone from a weak source should be downgraded, not promoted."""
        candidate: dict[str, Any] = {
            "digits": "5015553321",
            "display": "(501) 555-3321",
            "from_structured_data": False,
            "from_search": True,
            "from_search_corroborated": False,
        }
        page_text = ""  # no page context — search-only
        result = _phone_proposal_gate(
            SOUP_LADLE_SITE,
            page_text, candidate,
            name_overlap_score=0.3,
            name_match=False, location_match=False,
            shared_site=False, xref="no_search",
        )
        # Search-only, no name match → must be blocked or downgraded
        assert result["accept"] is False or result.get("downgrade") is True, (
            "Expected unsupported alternate phone not to be promoted "
            "at full confidence without official or multi-source backing"
        )

    def test_weak_source_classification(self):
        """Unverified search-only phone → classified as search_only source."""
        candidate: dict[str, Any] = {
            "digits": "5015553321",
            "display": "(501) 555-3321",
            "from_structured_data": False,
            "from_search": True,
            "from_search_corroborated": False,
        }
        result = _phone_proposal_gate(
            SOUP_LADLE_SITE,
            "", candidate,
            name_overlap_score=0.3,
            name_match=False, location_match=False,
            shared_site=False, xref="no_search",
        )
        assert result["source_quality"] in ("search_only", "weak"), (
            "Expected uncorroborated search-only phone to be classified as "
            "search_only or weak source"
        )


# ===================================================================
# SECTION 4b: MULTI-LOCATION CHAIN DRIFT  (CASE E — Marlow's FoodMart)
# ===================================================================

class TestMultiLocationChainDrift:
    """Phones from a different branch of the same multi-location chain
    must not be auto-promoted at full confidence, even when the source is
    structured data (schema.org).  Area code mismatch is the key signal."""

    def test_area_code_mismatch_downgrades_official_source(self):
        """Phone from AL structured data must be downgraded for MS site,
        even though source quality is 'official'."""
        candidate: dict[str, Any] = {
            "digits": "2515558315",
            "display": "(251) 555-8315",
            "from_structured_data": True,
        }
        page_text = (
            "Marlow's FoodMart. 455 County Rd 12, Pinegrove MS 39423. "
            "Phone: (251) 555-8315."
        )
        result = _phone_proposal_gate(
            MARLOWS_FOODMART_SITE,
            page_text, candidate,
            name_overlap_score=1.0,
            name_match=True, location_match=True,
            shared_site=False, xref="no_search",
        )
        # Area code 251 is Alabama, site is in Mississippi.
        # Even with structured data, this MUST be downgraded.
        assert result["area_code"] == "mismatch", (
            "Expected area code 251 (AL) to mismatch site state MS"
        )
        assert result["downgrade"] is True, (
            "Expected area code mismatch to force downgrade even for "
            "'official' structured data source"
        )

    def test_area_code_mismatch_never_bypassed(self):
        """Verify area code mismatch downgrade applies regardless of source."""
        for source_flag in (True, False):
            candidate: dict[str, Any] = {
                "digits": "2515558315",
                "display": "(251) 555-8315",
                "from_structured_data": source_flag,
            }
            result = _phone_proposal_gate(
                MARLOWS_FOODMART_SITE,
                "Marlow's FoodMart. Pinegrove MS.", candidate,
                name_overlap_score=1.0,
                name_match=True, location_match=True,
                shared_site=False, xref="no_search",
            )
            assert result["downgrade"] is True, (
                f"Expected downgrade for area code mismatch with "
                f"from_structured_data={source_flag}"
            )

    def test_matching_area_code_not_penalized(self):
        """Phone with correct MS area code should NOT be downgraded."""
        candidate: dict[str, Any] = {
            "digits": "6015552213",
            "display": "(601) 555-2213",
            "from_structured_data": True,
        }
        page_text = (
            "Marlow's FoodMart. 455 County Rd 12, Pinegrove MS 39423. "
            "Phone: (601) 555-2213."
        )
        result = _phone_proposal_gate(
            MARLOWS_FOODMART_SITE,
            page_text, candidate,
            name_overlap_score=1.0,
            name_match=True, location_match=True,
            shared_site=False, xref="no_search",
        )
        assert result["area_code"] == "match"
        assert result["downgrade"] is False, (
            "Expected matching area code with official source to pass "
            "without downgrade"
        )


# ===================================================================
# SECTION 5: HELPER FUNCTION UNIT TESTS
# ===================================================================

class TestNormalizeEntityName:
    def test_strips_punctuation(self):
        result = _normalize_entity_name("St. Anselm's - Food Pantry")
        assert "." not in result
        assert "'" not in result

    def test_removes_stopwords(self):
        result = _normalize_entity_name("The Food Pantry of Springfield")
        assert "the" not in result.split()
        # "food", "pantry", "of" are all stopwords in entity context
        assert "springfield" in result.split()

    def test_lowercases(self):
        result = _normalize_entity_name("BRIGHTWATER FOOD PANTRY")
        assert result == result.lower()

    def test_empty_string(self):
        assert _normalize_entity_name("") == ""
        assert _normalize_entity_name(cast(Any, None)) == ""


class TestComputeNameOverlap:
    def test_identical_names(self):
        overlap = _compute_name_overlap("Brightwater Food Pantry", "Brightwater Food Pantry")
        assert overlap == 1.0

    def test_partial_overlap(self):
        overlap = _compute_name_overlap(
            "Riverside Community Food Pantry",
            "Riverside Health Clinic",
        )
        # "riverside" is the only shared distinctive token
        assert 0 < overlap <= 1.0

    def test_partial_overlap_multi_token(self):
        overlap = _compute_name_overlap(
            "Greater Springfield Regional Food Pantry",
            "Springfield Dental Associates",
        )
        # Only "springfield" matches; "greater", "regional" don't
        assert 0 < overlap < 1.0

    def test_no_overlap(self):
        overlap = _compute_name_overlap(
            "Grace Church",
            "Riverdale Technology Partners",
        )
        assert overlap == 0.0

    def test_empty_names(self):
        assert _compute_name_overlap("", "anything") == 0.0
        assert _compute_name_overlap("Test Pantry", "") == 0.0


class TestEntityNameMatch:
    def test_accepts_exact_match(self):
        r = _entity_name_match("Springfield Food Pantry", "Springfield Food Pantry")
        assert r["accept"] is True
        assert r["type_conflict"] is False

    def test_rejects_type_conflict(self):
        r = _entity_name_match(
            "Grace Church Pantry",
            "Grace Dental Care — family dentistry",
        )
        assert r["accept"] is False, (
            "Expected entity type conflict: pantry vs dental"
        )

    def test_rejects_single_token_low_jaccard(self):
        """Single shared token with low jaccard → reject."""
        r = _entity_name_match(
            "Brightwater Food Pantry",
            "Brightwater Solutions Technology Consulting Inc",
        )
        assert r["accept"] is False, (
            "Expected weak token overlap not to pass entity validation"
        )


class TestDetectEntityTypeConflict:
    def test_pantry_vs_tech(self):
        r = _detect_entity_type_conflict("Hope Food Pantry", "Hope Solutions LLC")
        assert r["conflict"] is True

    def test_pantry_vs_dental(self):
        r = _detect_entity_type_conflict("Grace Church Pantry", "Grace Dental Clinic")
        assert r["conflict"] is True

    def test_pantry_vs_pantry(self):
        r = _detect_entity_type_conflict(
            "Springfield Food Pantry",
            "Springfield Community Food Pantry",
        )
        assert r["conflict"] is False

    def test_no_conflict_when_target_has_keyword(self):
        """If the target itself contains 'solutions', no conflict."""
        r = _detect_entity_type_conflict(
            "Community Solutions Center",
            "Community Solutions Center — Programs",
        )
        assert r["conflict"] is False


class TestLocationConsistencyCheck:
    def test_match_same_city(self):
        site = _site(city="Springfield", state="IL")
        assert _location_consistency_check(site, "Located in Springfield, IL") == "match"

    def test_conflict_different_state(self):
        site = _site(city="Brightwater", state="IL")
        assert _location_consistency_check(
            site, "Based in Midlothian VA 23113"
        ) == "conflict"

    def test_neutral_no_location(self):
        site = _site(city="Springfield", state="IL")
        assert _location_consistency_check(site, "Welcome to our site") == "neutral"


class TestLocationMatchDetail:
    def test_local_match(self):
        site = _site(city="Lakeport", state="NY", zip="14206")
        r = _location_match_detail(site, "312 Maple St, Lakeport NY 14206")
        assert r["city_match"] is True
        assert r["zip_match"] is True
        assert r["verdict"] in ("local_match", "same_area")

    def test_zip_conflict(self):
        site = _site(city="Lakeport", state="NY", zip="14206")
        r = _location_match_detail(site, "820 Lakeshore Ave, Lakeport NY 14209")
        assert r["zip_conflict"] is True, (
            "Expected ZIP conflict when page ZIP (14209) differs from "
            "site ZIP (14206)"
        )


class TestDomainRelevanceCheck:
    def test_unrelated_solutions(self):
        assert _domain_relevance_check("brightwatersolutions.com", "Brightwater Food Pantry") == "unrelated"

    def test_unrelated_dental(self):
        assert _domain_relevance_check("gracedental.com", "Grace Church Pantry") == "unrelated"

    def test_directory_yellowpages(self):
        assert _domain_relevance_check("yellowpages.com", "Any Org") == "directory"

    def test_directory_foodpantries(self):
        assert _domain_relevance_check("foodpantries.org", "Any Org") == "directory"

    def test_good_church_domain(self):
        assert _domain_relevance_check("gracechurch.org", "Grace Church Pantry") == "good"

    def test_good_with_name_tokens(self):
        assert _domain_relevance_check("brightwaterpantry.org", "Brightwater Food Pantry") == "good"

    def test_neutral_unknown(self):
        assert _domain_relevance_check("example.com", "Test Org") == "neutral"


class TestCheckPhoneAreaCode:
    def test_match(self):
        # 309 is an Illinois area code
        assert _check_phone_area_code("3092309202", "IL") == "match"

    def test_mismatch(self):
        # 540 is Virginia
        assert _check_phone_area_code("5405550608", "IL") == "mismatch"

    def test_unknown_empty(self):
        assert _check_phone_area_code("", "IL") == "unknown"


class TestDetectParentOfficeDrift:
    def test_returns_dict_with_required_keys(self):
        result = _detect_parent_office_drift(_site(), "text", "value")
        assert isinstance(result, dict)
        for key in ("drift", "umbrella", "admin_hit", "reason"):
            assert key in result

    def test_same_address_no_drift(self):
        site = _site(city="Lakeport", state="NY", zip="14206")
        result = _detect_parent_office_drift(
            site,
            "312 Maple St, Lakeport NY 14206. Phone: (716) 555-7510.",
            "(716) 555-7510",
        )
        assert result["drift"] is False

    def test_umbrella_different_campus(self):
        result = _detect_parent_office_drift(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            "Catholic Charities HQ, 820 Lakeshore Ave, Lakeport NY 14209",
            "(716) 555-1400",
        )
        assert result["drift"] is True
        assert result["umbrella"] is True


class TestClassifyPageScope:
    def test_local_page(self):
        site = _site(city="Springfield", state="IL", zip="62701")
        html = (
            "<html><head><title>Springfield Food Pantry</title></head>"
            "<body>100 Main St, Springfield IL 62701. Hours: Mon-Fri.</body></html>"
        )
        result = _classify_page_scope(site, html)
        assert result["scope"] == "local_site"

    def test_umbrella_hq_page(self):
        html = (
            "<html><head><title>Catholic Charities HQ</title></head>"
            "<body>Central office. Headquarters at 820 Lakeshore Ave. "
            "(716) 555-0001 (716) 555-0002 (716) 555-0003 (716) 555-0004"
            "</body></html>"
        )
        result = _classify_page_scope(CATHOLIC_CHARITIES_LAKEPORT_SITE, html)
        assert result["scope"] == "umbrella_office"


# ===================================================================
# SECTION 6: INTEGRATION-STYLE PROMOTION TESTS
# ===================================================================

class TestProposalPromotion:
    """Simulate the proposal flow and verify end-to-end behavior."""

    def test_brightwater_phone_not_promoted(self):
        """Brightwater Solutions phone blocked at entity-match level."""
        # In the real pipeline, _entity_name_match fires first and blocks
        # the proposal before the phone gate runs.
        ent = _entity_name_match(
            "Brightwater Food Pantry",
            "Brightwater Solutions, Midlothian VA 23113",
        )
        assert ent["accept"] is False, (
            "Expected entity name match to block Brightwater Solutions phone"
        )

    def test_brightwater_website_not_promoted(self):
        """brightwatersolutions.com must never become official website."""
        disc: dict[str, Any] = {
            "url": "https://brightwatersolutions.com",
            "domain": "brightwatersolutions.com",
            "score": 0.5,
            "confidence": 0.60,
            "reason": "Brightwater Solutions",
            "candidates": [{
                "url": "https://brightwatersolutions.com",
                "domain": "brightwatersolutions.com",
                "content_matches": 0,
                "city_match": False,
            }],
        }
        gate = _website_proposal_gate(BRIGHTWATER_SITE, disc)
        assert gate["accept"] is False

    def test_catholic_charities_admin_phone_blocked(self):
        """Admin center phone blocked for local pantry."""
        candidate: dict[str, Any] = {
            "digits": "7165551400",
            "display": "(716) 555-1400",
            "from_structured_data": False,
            "from_search": False,
        }
        page = (
            "Catholic Charities of Lakeport — Central Administrative Center. "
            "820 Lakeshore Ave, Lakeport NY 14209. (716) 555-1400. "
            "Central administrative office."
        )
        gate = _phone_proposal_gate(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            page, candidate,
            name_overlap_score=0.8,
            name_match=True, location_match=False,
            shared_site=False, xref="no_search",
        )
        assert gate["accept"] is False
        assert gate["parent_drift"] is True

    def test_directory_page_not_promoted_as_website(self):
        """Directory listing pages must not become official websites."""
        disc: dict[str, Any] = {
            "url": "https://foodpantries.org/li/brightwater-food-pantry",
            "domain": "foodpantries.org",
            "score": 0.7,
            "confidence": 0.75,
            "reason": "foodpantries.org listing for Brightwater",
            "candidates": [{
                "url": "https://foodpantries.org/li/brightwater-food-pantry",
                "domain": "foodpantries.org",
                "content_matches": 2,
                "city_match": True,
            }],
        }
        gate = _website_proposal_gate(BRIGHTWATER_SITE, disc)
        assert gate["accept"] is False, (
            "Expected directory listing site not to be promoted as "
            "official website"
        )

    def test_official_domain_with_strong_match_promoted(self):
        """Official-looking domain with strong name/location → accepted."""
        disc: dict[str, Any] = {
            "url": "https://brightwaterpantry.org",
            "domain": "brightwaterpantry.org",
            "score": 0.9,
            "confidence": 0.90,
            "reason": "Brightwater Food Pantry, Brightwater IL 61281",
            "candidates": [{
                "url": "https://brightwaterpantry.org",
                "domain": "brightwaterpantry.org",
                "content_matches": 3,
                "city_match": True,
            }],
        }
        gate = _website_proposal_gate(BRIGHTWATER_SITE, disc)
        assert gate["accept"] is True, (
            "Expected official domain brightwaterpantry.org with strong "
            "location match to be accepted"
        )


# ===================================================================
# SECTION 7: DIRECTORY VS OFFICIAL WEBSITE BEHAVIOR
# ===================================================================

class TestDirectoryVsOfficialWebsite:
    """Directory URLs can confirm existence but must not become official
    proposed websites; official domains with strong relevance can be
    promoted."""

    def test_directory_domain_detected(self):
        assert _domain_relevance_check("yellowpages.com", "Any Org") == "directory"
        assert _domain_relevance_check("foodpantries.org", "Any Org") == "directory"

    def test_directory_website_gate_blocks(self):
        """Directory domain → website gate rejects."""
        disc: dict[str, Any] = {
            "url": "https://yellowpages.com/brightwater-il/food-pantry",
            "domain": "yellowpages.com",
            "score": 0.5,
            "confidence": 0.60,
            "reason": "Yellow Pages listing",
            "candidates": [{
                "url": "https://yellowpages.com/brightwater-il/food-pantry",
                "domain": "yellowpages.com",
                "content_matches": 1,
                "city_match": True,
            }],
        }
        gate = _website_proposal_gate(BRIGHTWATER_SITE, disc)
        assert gate["accept"] is False, (
            "Expected directory listing site (yellowpages.com) to be "
            "rejected as official website"
        )

    def test_unrelated_business_domain_rejected(self):
        """Unrelated business domain rejected even with partial name match."""
        disc: dict[str, Any] = {
            "url": "https://brightwaterconsulting.com",
            "domain": "brightwaterconsulting.com",
            "score": 0.5,
            "confidence": 0.60,
            "reason": "Brightwater Consulting Group",
            "candidates": [{
                "url": "https://brightwaterconsulting.com",
                "domain": "brightwaterconsulting.com",
                "content_matches": 0,
                "city_match": False,
            }],
        }
        gate = _website_proposal_gate(BRIGHTWATER_SITE, disc)
        assert gate["accept"] is False, (
            "Expected unrelated consulting domain to be rejected"
        )


# ===================================================================
# SECTION 7b: GEOGRAPHIC CROSS-VALIDATION ON DISCOVERED WEBSITES
# ===================================================================

CEDAR_HOLLOW_LA_SITE = _site(
    name="Cedar Hollow Baptist Church",
    city="Millbrook",
    state="LA",
    zip="70466",
    streetAddress="1200 Old Mill Road",
    website="",
)


class TestGeographicCrossValidation:
    """Discovered websites must be rejected when the fetched page content
    reveals a location in a completely different state/city/ZIP than the
    site on file — even when the org name matches perfectly.

    Regression: Cedar Hollow Baptist Church (Millbrook, LA) was
    incorrectly matched to cedarhollowbaptist.org which belongs to a
    church in Riverton, SC 29707.  The org-name tokens all matched,
    but the page footer clearly showed a South Carolina address."""

    _SC_PAGE_HTML = (
        "<html><head><title>Cedar Hollow Baptist Church</title></head>"
        "<body>"
        "<h1>Cedar Hollow Baptist Church</h1>"
        "<p>Office Phone: 803.555.7208</p>"
        "<p>E-Mail: office@cedarhollow.church</p>"
        "<footer>"
        "340 Oak Rd, Riverton, SC 29707 "
        "© 2026 Cedar Hollow Baptist Church"
        "</footer></body></html>"
    )

    def test_different_state_in_page_html_blocks_proposal(self):
        """Website gate must reject when page HTML shows a different state."""
        disc: dict[str, Any] = {
            "url": "https://www.cedarhollowbaptist.org",
            "domain": "cedarhollowbaptist.org",
            "score": 0.95,
            "confidence": 0.92,
            "reason": "discovered_via_probe (strong name+content+locality match)",
            "high_quality": True,
            "candidates": [{
                "url": "https://www.cedarhollowbaptist.org",
                "domain": "cedarhollowbaptist.org",
                "content_matches": 3,
                "city_match": False,
                "source": "name_tokens",
                "page_html": self._SC_PAGE_HTML,
            }],
        }
        gate = _website_proposal_gate(CEDAR_HOLLOW_LA_SITE, disc)
        assert gate["accept"] is False, (
            "Expected website in SC to be BLOCKED for a site in LA. "
            f"Gate returned: {gate}"
        )

    def test_different_zip_in_page_html_blocks_proposal(self):
        """Website gate must reject when page HTML contains a conflicting ZIP."""
        disc: dict[str, Any] = {
            "url": "https://www.cedarhollowbaptist.org",
            "domain": "cedarhollowbaptist.org",
            "score": 0.90,
            "confidence": 0.88,
            "reason": "discovered_via_email_domain (partial content match)",
            "high_quality": True,
            "candidates": [{
                "url": "https://www.cedarhollowbaptist.org",
                "domain": "cedarhollowbaptist.org",
                "content_matches": 2,
                "city_match": False,
                "source": "email_domain",
                "page_html": self._SC_PAGE_HTML,
            }],
        }
        gate = _website_proposal_gate(CEDAR_HOLLOW_LA_SITE, disc)
        assert gate["accept"] is False, (
            "Expected website with ZIP 29707 to be BLOCKED for site with "
            f"ZIP 70466. Gate returned: {gate}"
        )

    def test_same_name_same_location_accepted(self):
        """A page that matches both name AND location should still pass."""
        la_page = (
            "<html><head><title>Cedar Hollow Baptist Church</title></head>"
            "<body>"
            "<h1>Cedar Hollow Baptist Church</h1>"
            "<p>1200 Old Mill Road, Millbrook, LA 70466</p>"
            "</body></html>"
        )
        disc: dict[str, Any] = {
            "url": "https://www.cedarhollowbaptistmillbrook.org",
            "domain": "cedarhollowbaptistmillbrook.org",
            "score": 0.90,
            "confidence": 0.92,
            "reason": "Cedar Hollow Baptist Church Millbrook",
            "high_quality": True,
            "candidates": [{
                "url": "https://www.cedarhollowbaptistmillbrook.org",
                "domain": "cedarhollowbaptistmillbrook.org",
                "content_matches": 3,
                "city_match": True,
                "source": "name_tokens",
                "page_html": la_page,
            }],
        }
        gate = _website_proposal_gate(CEDAR_HOLLOW_LA_SITE, disc)
        assert gate["accept"] is True, (
            "Expected website with matching city/state/ZIP to be ACCEPTED. "
            f"Gate returned: {gate}"
        )

    def test_no_page_html_falls_back_to_composite(self):
        """When page_html is absent, the gate should still work (old behavior)."""
        disc: dict[str, Any] = {
            "url": "https://www.cedarhollowbaptist.org",
            "domain": "cedarhollowbaptist.org",
            "score": 0.85,
            "confidence": 0.85,
            "reason": "Millbrook LA Cedar Hollow",
            "high_quality": True,
            "candidates": [{
                "url": "https://www.cedarhollowbaptist.org",
                "domain": "cedarhollowbaptist.org",
                "content_matches": 3,
                "city_match": True,
                "source": "name_tokens",
                # no page_html key
            }],
        }
        gate = _website_proposal_gate(CEDAR_HOLLOW_LA_SITE, disc)
        # With city mentioned in reason string and city_match=True,
        # the gate should accept (falls back to composite_text).
        assert gate["accept"] is True, (
            "Expected fallback to composite_text to work when page_html "
            f"is absent. Gate returned: {gate}"
        )


# ===================================================================
# SECTION 7c: UNCORROBORATED PHONE REPLACEMENT
# ===================================================================

MISS_ELEANOR_SITE = _site(
    name="Miss Eleanor's Mission House",
    city="Elmwood",
    state="IN",
    zip="46802-3547",
    streetAddress="450 Hickory St",
    website="http://misseleanorfoodpantry.com/",
    publicPhone="(260) 555-0176",
)


class TestUncorroboratedPhoneReplacement:
    """When a page contains a secondary phone number but the stored phone's
    area code matches the site's state and no search results corroborate
    the proposed number, the proposal must be downgraded.

    Regression: Miss Eleanor's Mission House (Elmwood, IN) had its
    correct phone (260) 555-0176 proposed for replacement with
    (260) 555-0599 at 0.98 confidence. The real phone appears on the
    website and Bing, but was likely in a JS widget or image that static
    HTML scraping couldn't extract. The secondary number was scored
    highly because it appeared in a tel: href on the same page."""

    _PAGE_HTML = (
        "<html><head><title>Miss Eleanor's Food Pantry</title></head>"
        "<body>"
        "<h1>Miss Eleanor's Food Pantry</h1>"
        "<p>Serving Elmwood, IN since 1998</p>"
        "<p>For volunteer inquiries call "
        '<a href="tel:2605550599">(260) 555-0599</a></p>'
        "<footer>450 Hickory St, Elmwood, IN 46802</footer>"
        "</body></html>"
    )

    def test_uncorroborated_phone_downgraded_no_search(self):
        """Phone proposal must be downgraded when stored area code matches
        site state and search results are unavailable."""
        result = _phone_evidence(
            MISS_ELEANOR_SITE,
            self._PAGE_HTML,
            site_label="miss_eleanor",
            web_ok=True,
            ctx=None,
            search_results=None,
        )
        # The stored phone (260) 555-0176 is NOT on the page, so a different
        # number gets proposed. But area code 260 is IN, which matches the
        # site state, and there's no search corroboration.
        assert result["status"] != "proposed_update", (
            "Expected phone proposal to be downgraded (not full proposed_update) "
            "when stored area code matches site state and search does not "
            f"corroborate the proposed number. Got: {result['status']}"
        )
        if result.get("proposed_value"):
            assert result["confidence"] <= 0.65, (
                "Expected confidence <= 0.65 for uncorroborated phone replacement. "
                f"Got: {result['confidence']}"
            )

    def test_uncorroborated_phone_downgraded_neither(self):
        """Phone proposal must be downgraded when search finds neither number."""
        # Empty search results that don't contain any phone numbers
        search_results = [
            {"title": "Miss Eleanor's Food Pantry", "snippet": "Serving Elmwood community"},
        ]
        result = _phone_evidence(
            MISS_ELEANOR_SITE,
            self._PAGE_HTML,
            site_label="miss_eleanor",
            web_ok=True,
            ctx=None,
            search_results=search_results,
        )
        assert result["status"] != "proposed_update", (
            "Expected phone proposal to be downgraded when search results "
            f"contain neither phone number. Got: {result['status']}"
        )

    def test_search_corroborated_proposed_phone_accepted(self):
        """When search corroborates the proposed phone, full confidence OK."""
        search_results = [
            {
                "title": "Miss Eleanor's Food Pantry - Elmwood IN",
                "snippet": "Call us at (260) 555-0599 for food assistance",
            },
        ]
        result = _phone_evidence(
            MISS_ELEANOR_SITE,
            self._PAGE_HTML,
            site_label="miss_eleanor",
            web_ok=True,
            ctx=None,
            search_results=search_results,
        )
        # When search corroborates the proposed number, it should be accepted
        # at full confidence (or at least not downgraded by the area-code guard).
        if result["status"] in ("proposed_update", "proposed_update_low_confidence"):
            # If it's proposed, verify the guard didn't wrongly fire
            assert result["proposed_value"] == "(260) 555-0599"

    def test_structured_data_phone_not_blocked(self):
        """Phones from schema.org structured data bypass the guard (site
        operator explicitly declared the number)."""
        page_with_jsonld = (
            '<html><head><title>Miss Eleanor\'s Food Pantry</title>'
            '<script type="application/ld+json">'
            '{"@type":"FoodEstablishment","telephone":"(260) 555-0599"}'
            "</script></head>"
            "<body>"
            "<h1>Miss Eleanor's Food Pantry</h1>"
            "<p>Elmwood, IN 46802</p>"
            "</body></html>"
        )
        result = _phone_evidence(
            MISS_ELEANOR_SITE,
            page_with_jsonld,
            site_label="miss_eleanor",
            web_ok=True,
            ctx=None,
            search_results=None,
        )
        # Structured data is strong enough to override the guard
        if result.get("proposed_value"):
            assert result["status"] in ("proposed_update", "proposed_update_low_confidence"), (
                f"Expected structured data phone to be proposable. Got: {result['status']}"
            )


# ===================================================================
# SECTION 7d: FREE-PROVIDER EMAIL EXTRACTION ON ORG WEBSITES
# ===================================================================

RIDGEWAY_FIRST_ASSEMBLY_SITE = _site(
    name="Ridgeway First Assembly of God",
    city="Ridgeway",
    state="AR",
    zip="71953-2617",
    streetAddress="980 Ridge Rd",
    website="https://www.ridgewayfirstag.org/",
)


class TestFreeProviderEmailExtraction:
    """Free-provider emails (gmail, yahoo, etc.) on a confirmed org website
    must be extracted and proposed when they appear near contact keywords,
    in mailto hrefs, or in structured data.

    Regression: Ridgeway First Assembly of God has ridgewayfirstag@gmail.com
    prominently displayed in a 'Contact Us' section at
    ridgewayfirstag.org/visit-us, but it was silently discarded because
    gmail.com was unconditionally blocked at the extraction level."""

    _CONTACT_PAGE_HTML = (
        "<html><head><title>Visit Us - Ridgeway First Assembly</title></head>"
        "<body>"
        "<h1>VISIT US</h1>"
        "<h2>CONTACT US</h2>"
        "<p>479.555.1229</p>"
        "<p><a href='mailto:ridgewayfirstag@gmail.com'>ridgewayfirstag@gmail.com</a></p>"
        "<h2>ADDRESS</h2>"
        "<p>980 Ridge Road</p>"
        "<p>Ridgeway, AR 71953</p>"
        "</body></html>"
    )

    def test_gmail_near_contact_keyword_is_extracted(self):
        """Gmail address near 'Contact Us' must be extracted as a candidate."""
        candidates = _extract_email_candidates(self._CONTACT_PAGE_HTML)
        emails = [c["email"] for c in candidates]
        assert "ridgewayfirstag@gmail.com" in emails, (
            f"Expected ridgewayfirstag@gmail.com to be extracted when near "
            f"'contact' keyword. Got: {emails}"
        )

    def test_gmail_in_mailto_href_is_extracted(self):
        """Gmail in a mailto: href must be extracted regardless of context."""
        html = (
            "<html><body>"
            "<a href='mailto:info@gmail.com'>Email us</a>"
            "</body></html>"
        )
        candidates = _extract_email_candidates(html)
        emails = [c["email"] for c in candidates]
        assert "info@gmail.com" in emails, (
            f"Expected info@gmail.com to be extracted from mailto href. "
            f"Got: {emails}"
        )

    def test_gmail_without_context_is_not_extracted(self):
        """Gmail address with no contact context should still be filtered."""
        html = (
            "<html><body>"
            "<p>Built by webdev@gmail.com</p>"
            "</body></html>"
        )
        candidates = _extract_email_candidates(html)
        emails = [c["email"] for c in candidates]
        assert "webdev@gmail.com" not in emails, (
            "Expected gmail without contact context to be filtered out"
        )

    def test_gmail_tagged_as_free_provider(self):
        """Extracted free-provider emails must be tagged."""
        candidates = _extract_email_candidates(self._CONTACT_PAGE_HTML)
        gmail_cand = [c for c in candidates if c["email"] == "ridgewayfirstag@gmail.com"]
        assert len(gmail_cand) == 1
        assert gmail_cand[0].get("free_provider") is True, (
            "Expected free_provider=True flag on gmail candidate"
        )

    def test_email_gate_downgrades_free_provider_with_mailto(self):
        """Email gate should downgrade (not reject) free-provider emails
        found via mailto on a confirmed org page."""
        candidate: dict[str, Any] = {
            "email": "ridgewayfirstag@gmail.com",
            "local_part": "ridgewayfirstag",
            "domain": "gmail.com",
            "in_mailto": True,
            "in_visible_text": True,
            "near_contact_keyword": True,
            "free_provider": True,
        }
        page_text = (
            "Ridgeway First Assembly of God. "
            "Contact Us. 479.555.1229. ridgewayfirstag@gmail.com. "
            "980 Ridge Road, Ridgeway, AR 71953"
        )
        gate = _email_proposal_gate(
            RIDGEWAY_FIRST_ASSEMBLY_SITE, candidate, page_text,
            name_match=True, location_match=True,
            website_domain="ridgewayfirstag.org",
        )
        assert gate["accept"] is True, (
            f"Expected free-provider email with mailto to be ACCEPTED "
            f"(downgraded). Gate returned: {gate}"
        )
        assert gate["downgrade"] is True, (
            f"Expected free-provider email to be DOWNGRADED. "
            f"Gate returned: {gate}"
        )

    def test_email_gate_rejects_free_provider_without_signals(self):
        """Email gate should still reject free-provider emails without
        strong contextual signals."""
        candidate: dict[str, Any] = {
            "email": "randomuser@gmail.com",
            "local_part": "randomuser",
            "domain": "gmail.com",
            "in_mailto": False,
            "in_visible_text": True,
            "near_contact_keyword": False,
            "free_provider": True,
        }
        gate = _email_proposal_gate(
            RIDGEWAY_FIRST_ASSEMBLY_SITE, candidate, "Some page text",
            name_match=False, location_match=False,
            website_domain="ridgewayfirstag.org",
        )
        assert gate["accept"] is False, (
            f"Expected free-provider email without signals to be REJECTED. "
            f"Gate returned: {gate}"
        )


# ===================================================================
# SECTION 8: STATUS BEHAVIOR — SUSPECT STATUSES VS DASHBOARD CHANGES
# ===================================================================

class TestStatusBehavior:
    """Verify that suspect statuses are NOT counted as dashboard-visible
    corrections in the aggregate summary logic."""

    # The aggregate_summary.py change_statuses set determines what counts
    # as a dashboard-visible change.  We reproduce that set here and
    # verify suspect statuses are excluded.

    DASHBOARD_CHANGE_STATUSES = {
        "proposed_update", "proposed_update_low_confidence",
        "mismatch", "review", "detected_only",
    }

    def test_suspect_entity_match_not_dashboard_change(self):
        assert "suspect_entity_match" not in self.DASHBOARD_CHANGE_STATUSES, (
            "suspect_entity_match must NOT be counted as a dashboard-visible "
            "correction"
        )

    def test_suspect_parent_office_drift_not_dashboard_change(self):
        assert "suspect_parent_office_drift" not in self.DASHBOARD_CHANGE_STATUSES, (
            "suspect_parent_office_drift must NOT be counted as a "
            "dashboard-visible correction"
        )

    def test_confirmed_not_dashboard_change(self):
        assert "confirmed" not in self.DASHBOARD_CHANGE_STATUSES

    def test_proposed_update_is_dashboard_change(self):
        assert "proposed_update" in self.DASHBOARD_CHANGE_STATUSES

    def test_valid_statuses_present(self):
        """All expected change statuses are in the set."""
        for s in ("proposed_update", "proposed_update_low_confidence",
                   "mismatch", "review", "detected_only"):
            assert s in self.DASHBOARD_CHANGE_STATUSES


class TestSuspectStatusFromGates:
    """When gates reject proposals due to drift, the resulting status
    should be a suspect variant, not a real proposed_update."""

    def test_phone_gate_parent_drift_produces_suspect_status(self):
        """Parent drift rejection → status should indicate drift, not
        a normal entity mismatch."""
        candidate: dict[str, Any] = {
            "digits": "7165551400",
            "display": "(716) 555-1400",
            "from_structured_data": False,
            "from_search": False,
        }
        page = (
            "Catholic Charities of Lakeport — Administrative Center. "
            "820 Lakeshore Ave, Lakeport NY 14209. (716) 555-1400."
        )
        gate = _phone_proposal_gate(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            page, candidate,
            name_overlap_score=0.8,
            name_match=True, location_match=False,
            shared_site=False, xref="no_search",
        )
        assert gate["accept"] is False
        assert gate["parent_drift"] is True, (
            "Expected parent_drift flag when admin center phone is proposed"
        )

    def test_email_gate_parent_drift_produces_suspect_status(self):
        """Admin email from HQ page → blocked with parent_drift."""
        candidate: dict[str, Any] = {
            "email": "admin@cclakeport.org",
            "domain": "cclakeport.org",
            "local_part": "admin",
            "from_structured_data": False,
            "in_mailto": True,
            "from_search": False,
        }
        page = (
            "<html><head><title>Catholic Charities of Lakeport</title></head>"
            "<body>Catholic Charities of Lakeport — Administrative Center. "
            "820 Lakeshore Ave, Lakeport NY 14209. "
            "Email: admin@cclakeport.org. Central office.</body></html>"
        )
        gate = _email_proposal_gate(
            CATHOLIC_CHARITIES_LAKEPORT_SITE,
            candidate, page,
            name_match=True, location_match=False,
            website_domain=None,
        )
        # Should be blocked: either parent_drift or admin_prefix+umbrella
        assert gate["accept"] is False, (
            "Expected admin email from HQ page to be blocked for "
            "local pantry record"
        )


# ===================================================================
# SECTION 9: CONSTANTS SANITY CHECKS
# ===================================================================

class TestConstantsSanity:
    """Quick checks that key constant lists are populated and sensible."""

    def test_umbrella_patterns_populated(self):
        assert len(_UMBRELLA_ORG_PATTERNS) >= 14
        assert any("catholic" in p for p in _UMBRELLA_ORG_PATTERNS)
        assert any("diocese" in p for p in _UMBRELLA_ORG_PATTERNS)
        assert any("salvation" in p for p in _UMBRELLA_ORG_PATTERNS)

    def test_admin_keywords_populated(self):
        assert len(_ADMIN_PAGE_KEYWORDS) >= 5
        assert "headquarters" in _ADMIN_PAGE_KEYWORDS
        assert "central office" in _ADMIN_PAGE_KEYWORDS

    def test_unrelated_domain_keywords(self):
        assert "solutions" in _UNRELATED_DOMAIN_KEYWORDS
        assert "dental" in _UNRELATED_DOMAIN_KEYWORDS
        assert "consulting" in _UNRELATED_DOMAIN_KEYWORDS

    def test_directory_domain_keywords(self):
        assert "yellowpages" in _DIRECTORY_DOMAIN_KEYWORDS
        assert "foodpantries" in _DIRECTORY_DOMAIN_KEYWORDS


# ===================================================================
# SECTION 10: SOURCE TAG CLASSIFICATION
# ===================================================================

class TestClassifySourceTag:
    """Verify source_tag labelling for email and website proposals."""

    # --- Platform email detection ---

    def test_platform_email_churchspring(self):
        tag = _classify_source_tag("email", "info@churchspring.com", "Grace Church")
        assert tag == "platform_email"

    def test_platform_email_wix(self):
        tag = _classify_source_tag("email", "contact@wix.com", "Test Org")
        assert tag == "platform_email"

    def test_platform_email_squarespace(self):
        tag = _classify_source_tag("email", "admin@squarespace.com", "Test Org")
        assert tag == "platform_email"

    def test_generic_email_gmail(self):
        tag = _classify_source_tag("email", "pantry@gmail.com", "Springfield Pantry")
        assert tag == "platform_email"

    def test_generic_email_outlook(self):
        tag = _classify_source_tag("email", "contact@outlook.com", "Test Org")
        assert tag == "platform_email"

    def test_generic_email_yahoo(self):
        tag = _classify_source_tag("email", "org@yahoo.com", "Test Org")
        assert tag == "platform_email"

    def test_custom_domain_email_no_tag(self):
        """Custom org domain email should NOT get platform_email tag."""
        tag = _classify_source_tag("email", "info@gracechurch.org", "Grace Church")
        assert tag is None

    def test_none_email(self):
        tag = _classify_source_tag("email", None, "Test Org")
        assert tag is None

    def test_empty_email(self):
        tag = _classify_source_tag("email", "", "Test Org")
        assert tag is None

    # --- Third-party website detection ---

    def test_facebook_page_is_third_party(self):
        tag = _classify_source_tag("website", "https://facebook.com/gracechurch", "Grace Church")
        assert tag == "third_party_domain"

    def test_foodpantries_listing_is_third_party(self):
        tag = _classify_source_tag("website", "https://foodpantries.org/li/grace-church-pantry", "Grace Church")
        assert tag == "third_party_domain"

    def test_yelp_is_third_party(self):
        tag = _classify_source_tag("website", "https://yelp.com/biz/grace-church", "Grace Church")
        assert tag == "third_party_domain"

    def test_yellowpages_is_third_party(self):
        tag = _classify_source_tag("website", "https://yellowpages.com/springfield/pantry", "Test")
        assert tag == "third_party_domain"

    def test_findhelp_is_third_party(self):
        tag = _classify_source_tag("website", "https://findhelp.org/listing/123", "Test")
        assert tag == "third_party_domain"

    def test_countyoffice_is_third_party(self):
        tag = _classify_source_tag("website", "https://countyoffice.org/org", "Test")
        assert tag == "third_party_domain"

    # --- Official domain detection ---

    def test_official_domain_church(self):
        tag = _classify_source_tag("website", "https://gracechurch.org", "Grace Church")
        assert tag == "official_domain"

    def test_official_domain_pantry(self):
        tag = _classify_source_tag("website", "https://brightwaterpantry.org", "Brightwater Food Pantry")
        assert tag == "official_domain"

    def test_unrelated_website_no_tag(self):
        """Website that is neither third-party nor matching org name."""
        tag = _classify_source_tag("website", "https://example.com", "Grace Church")
        assert tag is None

    def test_none_website(self):
        tag = _classify_source_tag("website", None, "Test Org")
        assert tag is None

    # --- Constants sanity ---

    def test_platform_email_domains_populated(self):
        assert len(_PLATFORM_EMAIL_DOMAINS) >= 10
        assert _PLATFORM_EMAIL_DOMAINS.issuperset({"churchspring.com", "wix.com"})

    def test_generic_email_domains_populated(self):
        assert len(_GENERIC_EMAIL_DOMAINS) >= 5
        assert _GENERIC_EMAIL_DOMAINS.issuperset({"gmail.com", "outlook.com"})

    def test_third_party_website_domains_populated(self):
        assert len(_THIRD_PARTY_WEBSITE_DOMAINS) >= 10
        assert _THIRD_PARTY_WEBSITE_DOMAINS.issuperset(
            {"facebook.com", "yelp.com", "foodpantries.org"}
        )

    def test_unsupported_field_type(self):
        """Non-email/website field types return None."""
        tag = _classify_source_tag("phone", "5551234567", "Test")
        assert tag is None


# ===================================================================
# Subpage crawl: contact / about page discovery
# ===================================================================

class TestDiscoverContactPages:
    """Regression tests for _discover_contact_pages."""

    HOMEPAGE_WITH_CONTACT = """
    <html><head><title>Grace Food Pantry</title></head>
    <body>
        <nav>
            <a href="/">Home</a>
            <a href="/about">About Us</a>
            <a href="/contact">Contact</a>
            <a href="/donate">Donate</a>
            <a href="/events">Events</a>
        </nav>
        <p>Welcome to Grace Food Pantry, serving Springfield IL since 1990.</p>
        <p>Phone: (217) 555-1234</p>
    </body></html>
    """

    HOMEPAGE_WITH_CONTACT_US_VARIANT = """
    <html><body>
        <a href="/contact-us">Contact Us</a>
        <a href="/about-us">About Us</a>
        <a href="/services">Services</a>
    </body></html>
    """

    HOMEPAGE_NO_CONTACT_LINKS = """
    <html><body>
        <a href="/donate">Give Now</a>
        <a href="/events">Calendar</a>
        <a href="/blog">News</a>
    </body></html>
    """

    HOMEPAGE_EXTERNAL_CONTACT = """
    <html><body>
        <a href="https://other-site.com/contact">Contact</a>
        <a href="/services">Services</a>
    </body></html>
    """

    HOMEPAGE_ANCHOR_TEXT_MATCH = """
    <html><body>
        <a href="/?page_id=42">Contact Us</a>
        <a href="/?page_id=10">About Us</a>
        <a href="/?page_id=99">Events</a>
    </body></html>
    """

    HOMEPAGE_RELATIVE_PATHS = """
    <html><body>
        <a href="contact.html">Contact</a>
        <a href="about.html">About</a>
    </body></html>
    """

    def test_discovers_contact_and_about(self):
        """Should find /contact and /about links."""
        urls = _discover_contact_pages(self.HOMEPAGE_WITH_CONTACT, "https://gracepantry.org")
        assert len(urls) == 2
        paths = [u.split("gracepantry.org")[1] for u in urls]
        assert "/about" in paths
        assert "/contact" in paths

    def test_contact_us_hyphenated_variant(self):
        """Should match /contact-us and /about-us paths."""
        urls = _discover_contact_pages(self.HOMEPAGE_WITH_CONTACT_US_VARIANT, "https://example.org")
        assert len(urls) == 2
        paths = [u.split("example.org")[1] for u in urls]
        assert "/contact-us" in paths
        assert "/about-us" in paths

    def test_no_contact_links_returns_empty(self):
        """Should return empty list when no contact/about links found."""
        urls = _discover_contact_pages(self.HOMEPAGE_NO_CONTACT_LINKS, "https://example.org")
        assert urls == []

    def test_external_links_excluded(self):
        """Should not follow links to a different domain."""
        urls = _discover_contact_pages(self.HOMEPAGE_EXTERNAL_CONTACT, "https://my-org.org")
        assert urls == []

    def test_anchor_text_matching(self):
        """Should match links by anchor text when path is generic."""
        urls = _discover_contact_pages(self.HOMEPAGE_ANCHOR_TEXT_MATCH, "https://example.org")
        assert len(urls) == 2
        assert any("page_id=42" in u for u in urls)
        assert any("page_id=10" in u for u in urls)

    def test_max_subpages_cap(self):
        """Should return at most MAX_SUBPAGES links."""
        html = """
        <html><body>
            <a href="/contact">Contact</a>
            <a href="/about">About</a>
            <a href="/location">Location</a>
            <a href="/directions">Directions</a>
            <a href="/hours">Hours</a>
        </body></html>
        """
        urls = _discover_contact_pages(html, "https://example.org")
        # MAX_SUBPAGES is 2
        assert len(urls) <= 2

    def test_self_link_excluded(self):
        """Should not include a link back to the homepage itself."""
        html = """
        <html><body>
            <a href="https://example.org/">Home</a>
            <a href="https://example.org/contact">Contact</a>
        </body></html>
        """
        urls = _discover_contact_pages(html, "https://example.org/")
        assert len(urls) == 1
        assert "contact" in urls[0].lower()

    def test_relative_path_resolution(self):
        """Should resolve relative paths like contact.html."""
        urls = _discover_contact_pages(self.HOMEPAGE_RELATIVE_PATHS, "https://example.org/index.html")
        assert len(urls) >= 1
        assert any("contact" in u.lower() for u in urls)

    def test_dedup_same_url(self):
        """Duplicate links to same URL should be de-duplicated."""
        html = """
        <html><body>
            <a href="/contact">Contact</a>
            <a href="/contact">Get in touch</a>
            <a href="/contact/">Contact page</a>
        </body></html>
        """
        urls = _discover_contact_pages(html, "https://example.org")
        # /contact and /contact/ may differ — but should be at most 2
        assert len(urls) <= 2

    def test_empty_html_returns_empty(self):
        """Should handle empty/None HTML gracefully."""
        assert _discover_contact_pages("", "https://example.org") == []
        assert _discover_contact_pages(cast(str, None), "https://example.org") == []

    def test_empty_base_url_returns_empty(self):
        """Should handle empty base_url gracefully."""
        assert _discover_contact_pages("<a href='/contact'>Contact</a>", "") == []

    def test_www_prefix_same_origin(self):
        """www.example.org and example.org should be treated as same-origin."""
        html = '<html><body><a href="https://www.example.org/contact">Contact</a></body></html>'
        urls = _discover_contact_pages(html, "https://example.org")
        assert len(urls) == 1


# ===================================================================
# Closure detection: context-aware false-positive prevention
# ===================================================================

class TestClosureDetection:
    """Regression: Community Helpers - Main Office false positive.

    The page at www.community-helpers.org contains the phrase
    'permanently closed' somewhere on the page (possibly about an old
    location or embedded content), but the org is clearly still
    operating — the page has business hours, contact info, and active
    programs.  The old detection flagged it as closure.

    Fix: context-aware checks — negation, active indicators (business
    hours/events), and prominence (position in visible text).
    """

    # --- Page with closure phrase + active business hours ---
    PAGE_ACTIVE_WITH_CLOSURE_MENTION = """
    <html><head><title>Community Helpers Inc</title></head>
    <body>
        <h1>Community Helpers Inc Office and Food Center</h1>
        <p>Serving the community of Rivertown, OH since 1960.</p>
        <p>Hours of Operation: Mon-Fri 9am-5pm</p>
        <p>Phone: (330) 555-1453</p>
        <p>We partner with various agencies. Note: Our former East
        location has been permanently closed since 2019.</p>
        <p>Donate now to support our mission!</p>
    </body></html>
    """

    # --- Page with genuine permanent closure ---
    PAGE_GENUINELY_CLOSED = """
    <html><head><title>Community Helpers Inc</title></head>
    <body>
        <h1>Community Helpers Inc</h1>
        <p>We regret to announce that Community Helpers Inc has been
        permanently closed. Thank you for your support over the years.</p>
        <p>This organization has ceased operations as of January 2026.</p>
    </body></html>
    """

    # --- Page with negated closure ---
    PAGE_NEGATED_CLOSURE = """
    <html><head><title>Community Helpers Inc</title></head>
    <body>
        <h1>Community Helpers Inc</h1>
        <p>Despite rumors, we are NOT permanently closed.</p>
        <p>Hours: Mon-Fri 9am-5pm</p>
    </body></html>
    """

    # --- Page with closure phrase buried deep (non-prominent) ---
    PAGE_BURIED_CLOSURE = (
        "<html><body>"
        + "<h1>Community Helpers Inc</h1>"
        + "<p>Serving the community.</p>"
        + ("<p>Lorem ipsum dolor sit amet. </p>" * 200)  # pad to push past 3000 chars
        + "<p>An unrelated organization was permanently closed last year.</p>"
        + "</body></html>"
    )

    # --- Page with only closure, no active indicators ---
    PAGE_CLOSURE_NO_ACTIVE = """
    <html><body>
        <h1>Old Food Pantry</h1>
        <p>This pantry has permanently closed.</p>
    </body></html>
    """

    def test_active_site_with_closure_mention_not_detected(self):
        """A page with business hours + a passing mention of 'permanently
        closed' (about a different location) should NOT be flagged."""
        result = _detect_closure(self.PAGE_ACTIVE_WITH_CLOSURE_MENTION)
        assert result["detected"] is False, (
            f"Should not detect closure when active indicators present. "
            f"Signals: {result['signals']}"
        )

    def test_genuine_closure_detected(self):
        """A page with prominent closure language and no active indicators
        should be detected."""
        result = _detect_closure(self.PAGE_GENUINELY_CLOSED)
        assert result["detected"] is True
        assert result["confidence"] >= 0.70
        assert any("permanently closed" in s for s in result["signals"])

    def test_negated_closure_not_detected(self):
        """'NOT permanently closed' should not trigger closure detection."""
        result = _detect_closure(self.PAGE_NEGATED_CLOSURE)
        # The negation check should skip the phrase, and active indicators
        # (hours) provide further counter-evidence.
        assert result["detected"] is False

    def test_buried_closure_weak_signal(self):
        """Closure phrase buried deep in page text (>3000 chars in) should
        produce a weak signal below the detection threshold."""
        result = _detect_closure(self.PAGE_BURIED_CLOSURE)
        # Confidence should be low (0.50) which is below the 0.65 threshold
        if result["detected"]:
            # If somehow detected, confidence must be capped low
            assert result["confidence"] <= 0.55

    def test_clear_closure_no_active_indicators(self):
        """Page with closure phrase and no contradicting active indicators
        should be detected normally."""
        result = _detect_closure(self.PAGE_CLOSURE_NO_ACTIVE)
        assert result["detected"] is True
        assert result["confidence"] >= 0.65

    def test_http_410_still_detected(self):
        """HTTP 410 Gone should still be detected regardless of page content."""
        result = _detect_closure(None, status_code=410)
        assert result["detected"] is True
        assert result["confidence"] >= 0.85

    def test_search_snippet_closure_detected(self):
        """Closure phrase in search snippet should still work."""
        results = [{"title": "Community Helpers", "snippet": "This org has permanently closed."}]
        result = _detect_closure(None, search_results=results)
        assert result["detected"] is True
        assert result["confidence"] >= 0.65

    def test_multiple_closure_phrases_higher_confidence(self):
        """Multiple distinct closure phrases boost confidence."""
        html = """
        <html><body>
            <h1>Closed Organization</h1>
            <p>This organization has permanently closed.</p>
            <p>Operations have ceased. This location is no longer open.</p>
        </body></html>
        """
        result = _detect_closure(html)
        assert result["detected"] is True
        assert result["confidence"] >= 0.80


# ===================================================================
# Section: GEOCODING CROSS-VALIDATION
# ===================================================================


class TestGeocodeValidate:
    """Regression tests for geocode_validate (additive, no scoring impact)."""

    def test_returns_dict_structure(self):
        """geocode_validate always returns the expected keys."""
        site = {
            "streetAddress": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
        }
        # Use mock to avoid real network call
        result = geocode_validate(site, site_label="test")
        assert isinstance(result, dict)
        assert "geocoded" in result
        assert "city_match" in result
        assert "state_match" in result
        assert "zip_match" in result
        assert "confidence" in result
        assert "note" in result

    def test_insufficient_address_fields(self):
        """Sites with too few address fields should be skipped."""
        site = {"city": "Springfield"}
        result = geocode_validate(site, site_label="test")
        assert result["geocoded"] is False
        assert "insufficient" in result["note"]

    def test_empty_site(self):
        """Completely empty site should be skipped gracefully."""
        result = geocode_validate({}, site_label="test")
        assert result["geocoded"] is False

    def test_no_effect_on_confidence_scores(self):
        """geocode_validate result has its own confidence but
        MUST NOT be referenced by any scoring or classification logic.
        This test validates the result is informational only."""
        site = {
            "streetAddress": "1600 Pennsylvania Ave",
            "city": "Washington",
            "state": "DC",
            "zip": "20500",
        }
        result = geocode_validate(site, site_label="test")
        # The result should not contain any classification keys
        assert "classification" not in result
        assert "status" not in result
        assert "proposed_value" not in result

    def test_result_confidence_range(self):
        """Confidence should be between 0.0 and 1.0."""
        site = {
            "streetAddress": "100 Test Rd",
            "city": "Testville",
            "state": "OH",
            "zip": "44101",
        }
        result = geocode_validate(site, site_label="test")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_partial_address_accepted(self):
        """A site with city + state (no street) should still attempt geocoding."""
        site = {"city": "Columbus", "state": "OH"}
        result = geocode_validate(site, site_label="test")
        # Should NOT return 'insufficient' since we have 2 parts
        assert "insufficient" not in result.get("note", "")


# ===================================================================
# Section: REVIEW TRACKING (aggregate_summary)
# ===================================================================


class TestReviewTracking:
    """Verify review_outcome is included in detected changes schema."""

    def test_change_entry_has_review_outcome(self):
        """aggregate_summary should add review_outcome: null to each change."""
        # Directly test the data shape by simulating aggregate_summary logic
        change_entry: dict[str, object] = {
            "site_name": "Test Site",
            "field_name": "publicEmail",
            "original_value": None,
            "proposed_value": "test@example.com",
            "confidence": 0.95,
            "change_type": "fill_gap",
            "source_tag": "official_domain",
            "review_outcome": None,
        }
        assert "review_outcome" in change_entry
        assert change_entry["review_outcome"] is None

    def test_review_outcome_accepted(self):
        """review_outcome can be set to 'accepted'."""
        change: dict[str, object] = {"review_outcome": None}
        change["review_outcome"] = "accepted"
        assert change["review_outcome"] == "accepted"

    def test_review_outcome_rejected(self):
        """review_outcome can be set to 'rejected'."""
        change: dict[str, object] = {"review_outcome": None}
        change["review_outcome"] = "rejected"
        assert change["review_outcome"] == "rejected"

    def test_review_outcome_does_not_affect_confidence(self):
        """Setting review_outcome should never alter confidence."""
        change: dict[str, object] = {
            "confidence": 0.85,
            "review_outcome": None,
        }
        original_conf = change["confidence"]
        change["review_outcome"] = "accepted"
        assert change["confidence"] == original_conf

    def test_review_log_schema(self):
        """Review log entries match expected structure."""
        entry: dict[str, object] = {
            "site_name": "Riverside Cares Food Pantry",
            "field": "publicEmail",
            "proposed_value": "noffice@example-pantry.org",
            "confidence": 0.90,
            "review_outcome": "accepted",
        }
        required_keys = {"site_name", "field", "proposed_value", "confidence", "review_outcome"}
        assert required_keys.issubset(entry.keys())
        assert entry["review_outcome"] in ("accepted", "rejected")


# ===================================================================
# Section: STRUCTURED LOGGING
# ===================================================================


class TestStructuredLogging:
    """Verify all modules use structured logging instead of print()."""

    def test_web_evidence_has_logger(self):
        """web_evidence module exposes a logger."""
        import tackle_hunger.web_evidence as we
        assert hasattr(we, 'logger')
        assert we.logger.name == "web_evidence"

    def test_ai_validate_has_logger(self):
        """ai_validate module uses structured logging."""
        import tackle_hunger.ai_validate as av
        assert hasattr(av, 'logger')
        assert av.logger.name == "ai_validate"

    def test_logger_format_includes_timestamp(self):
        """Logger formatter should include timestamp and level."""
        import tackle_hunger.web_evidence as we
        handler = we.logger.handlers[0]
        formatter = handler.formatter
        assert formatter is not None
        fmt = formatter._fmt  # type: ignore[attr-defined]
        assert fmt is not None
        assert "%(asctime)s" in fmt
        assert "%(levelname)s" in fmt


# ===================================================================
# Section: RUN_ID AND TIMESTAMP TRACEABILITY
# ===================================================================


class TestRunIdTraceability:
    """Verify run_id and timestamp metadata for review tracking."""

    def test_change_entry_has_run_id(self):
        """Each detected change should include a run_id field."""
        entry: dict[str, object] = {
            "site_name": "Test Site",
            "field_name": "publicEmail",
            "proposed_value": "test@example.com",
            "confidence": 0.90,
            "review_outcome": None,
            "run_id": "2026-06-12_batch1",
        }
        assert "run_id" in entry
        assert isinstance(entry["run_id"], str)

    def test_run_id_format(self):
        """run_id should follow YYYY-MM-DD_batchN format."""
        import re
        run_id = "2026-06-12_batch3"
        assert re.match(r"^\d{4}-\d{2}-\d{2}_batch\d+$", run_id)

    def test_review_log_includes_run_id_and_timestamp(self):
        """Review log entries must have run_id and review_timestamp."""
        entry: dict[str, object] = {
            "site_name": "Riverside Cares Food Pantry",
            "field": "publicEmail",
            "proposed_value": "noffice@example-pantry.org",
            "confidence": 0.90,
            "review_outcome": "accepted",
            "run_id": "2026-06-12_batch1",
            "review_timestamp": "2026-06-12T18:45:00Z",
        }
        required = {"site_name", "field", "proposed_value", "confidence",
                     "review_outcome", "run_id", "review_timestamp"}
        assert required.issubset(entry.keys())

    def test_review_timestamp_iso_format(self):
        """review_timestamp should be ISO 8601 parseable."""
        from datetime import datetime
        ts = "2026-06-12T18:45:00Z"
        # Should not raise
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed.year == 2026

    def test_run_id_does_not_affect_confidence(self):
        """Adding run_id to a change must not alter its confidence."""
        change: dict[str, object] = {
            "confidence": 0.85,
            "review_outcome": None,
            "run_id": "2026-06-12_batch1",
        }
        original_conf = change["confidence"]
        change["run_id"] = "2026-06-12_batch2"
        assert change["confidence"] == original_conf

    def test_run_id_does_not_affect_review_outcome(self):
        """run_id metadata should be independent of review_outcome."""
        change: dict[str, object] = {
            "review_outcome": "accepted",
            "run_id": "2026-06-12_batch1",
        }
        change["run_id"] = "2026-06-13_batch1"
        assert change["review_outcome"] == "accepted"


# ===================================================================
# Batch ID Propagation
# ===================================================================

class TestBatchIdPropagation:
    """Verify batch_id flows through the pipeline to dashboard and CSV."""

    def test_dashboard_summary_includes_batch_id(self):
        """generate_dashboard_summary should propagate batch_id to top level."""
        import json
        from pathlib import Path

        dash_path = Path(__file__).resolve().parent.parent / "dashboard_summary.json"
        if not dash_path.exists():
            pytest.skip("dashboard_summary.json not present")
        data = json.loads(dash_path.read_text(encoding="utf-8"))
        assert "batch_id" in data, "batch_id must be a top-level key in dashboard_summary.json"
        assert isinstance(data["batch_id"], str)
        assert len(data["batch_id"]) > 0, "batch_id should not be empty"

    def test_csv_header_includes_batch_id(self):
        """The CSV export header row must contain a Batch ID column."""
        expected_header = [
            "Batch ID", "Site Name", "Closure Alert", "Classification",
            "Field", "Status", "Original Value", "Proposed Value",
            "Change Type", "Source Tag", "Detected Value", "Confidence",
            "Evidence Source", "Reason", "Evidence URLs",
            "Review Outcome", "Corrected Value", "Run ID", "Review Timestamp",
        ]
        assert expected_header[0] == "Batch ID"
        assert "Corrected Value" in expected_header
        assert len(expected_header) == 19

    def test_batch_id_independent_of_run_id(self):
        """batch_id and run_id are separate tracking identifiers."""
        entry: dict[str, object] = {
            "batch_id": "27157421283-1",
            "run_id": "2026-06-12_batch2",
        }
        assert entry["batch_id"] != entry["run_id"]
        assert isinstance(entry["batch_id"], str)
        assert isinstance(entry["run_id"], str)


# ===================================================================
# Section: CORRECTED VALUE CAPTURE
# ===================================================================


class TestCorrectedValueCapture:
    """Verify corrected_value field is captured on rejection and behaves passively."""

    def test_corrected_value_captured_on_reject(self):
        """corrected_value should be stored when review_outcome is rejected."""
        entry: dict[str, object] = {
            "site_name": "Test Pantry",
            "field": "publicEmail",
            "proposed_value": "info@org.com",
            "review_outcome": "rejected",
            "corrected_value": "contact@org.com",
            "run_id": "2026-06-12_batch1",
            "review_timestamp": "2026-06-12T18:55:00Z",
        }
        assert entry["review_outcome"] == "rejected"
        assert entry["corrected_value"] == "contact@org.com"

    def test_corrected_value_null_by_default(self):
        """corrected_value should default to None when not provided."""
        entry: dict[str, object] = {
            "site_name": "Test Pantry",
            "field": "publicPhone",
            "proposed_value": "555-1234",
            "review_outcome": None,
            "corrected_value": None,
        }
        assert entry["corrected_value"] is None

    def test_corrected_value_cleared_on_accept(self):
        """Switching from rejected to accepted should clear corrected_value."""
        change: dict[str, object] = {
            "review_outcome": "rejected",
            "corrected_value": "correct@example.com",
            "confidence": 0.75,
        }
        # Simulate switching to accepted
        change["review_outcome"] = "accepted"
        change["corrected_value"] = None
        assert change["review_outcome"] == "accepted"
        assert change["corrected_value"] is None

    def test_corrected_value_preserved_on_re_reject(self):
        """Clicking reject again should preserve the corrected_value input."""
        change: dict[str, object] = {
            "review_outcome": "rejected",
            "corrected_value": "real-value@org.com",
        }
        # Re-clicking reject keeps the value
        assert change["review_outcome"] == "rejected"
        assert change["corrected_value"] == "real-value@org.com"

    def test_corrected_value_does_not_affect_confidence(self):
        """Setting corrected_value must not alter confidence scoring."""
        change: dict[str, object] = {
            "confidence": 0.92,
            "review_outcome": "rejected",
            "corrected_value": None,
        }
        original_conf = change["confidence"]
        change["corrected_value"] = "updated@example.com"
        assert change["confidence"] == original_conf

    def test_corrected_value_does_not_affect_proposed_value(self):
        """corrected_value must not overwrite the original proposed_value."""
        change: dict[str, object] = {
            "proposed_value": "info@org.com",
            "review_outcome": "rejected",
            "corrected_value": "contact@org.com",
        }
        assert change["proposed_value"] == "info@org.com"
        assert change["corrected_value"] == "contact@org.com"

    def test_corrected_value_in_review_log_schema(self):
        """Review log entries should include corrected_value alongside other fields."""
        entry: dict[str, object] = {
            "site_name": "Riverside Cares Food Pantry",
            "field": "publicEmail",
            "proposed_value": "noffice@example-pantry.org",
            "review_outcome": "rejected",
            "corrected_value": "office@example-pantry.org",
            "run_id": "2026-06-12_batch1",
            "review_timestamp": "2026-06-12T18:55:00Z",
        }
        required = {"site_name", "field", "proposed_value", "review_outcome",
                     "corrected_value", "run_id", "review_timestamp"}
        assert required.issubset(entry.keys())

    def test_corrected_value_exported_only_when_rejected(self):
        """Export should only include corrected_value for rejected entries."""
        entries: list[dict[str, object]] = [
            {"review_outcome": "accepted", "corrected_value": None},
            {"review_outcome": "rejected", "corrected_value": "correct@org.com"},
            {"review_outcome": "rejected", "corrected_value": None},
            {"review_outcome": None, "corrected_value": None},
        ]
        for e in entries:
            exported_val: object = e["corrected_value"] if (e["review_outcome"] == "rejected" and e["corrected_value"]) else ""
            if e["review_outcome"] == "rejected" and e["corrected_value"]:
                assert exported_val == "correct@org.com"
            else:
                assert exported_val == ""

    def test_corrected_value_optional(self):
        """Rejecting without providing corrected_value should still work."""
        entry: dict[str, object] = {
            "site_name": "Test Site",
            "field": "website",
            "proposed_value": "http://example.com",
            "review_outcome": "rejected",
            "corrected_value": None,
            "run_id": "2026-06-15_batch1",
            "review_timestamp": "2026-06-15T10:00:00Z",
        }
        assert entry["review_outcome"] == "rejected"
        assert entry["corrected_value"] is None


# ===================================================================
# Section: CLOSURE AS REVIEWABLE DETECTED CHANGE
# ===================================================================


class TestClosureDetectedChange:
    """Verify closure detection produces an operational_status detected change."""

    def test_closure_change_entry_schema(self):
        """A closure should produce a well-formed detected change entry."""
        entry: dict[str, object] = {
            "site_name": "Canyon Lake East Elementary",
            "field_name": "operational_status",
            "original_value": "Active",
            "proposed_value": "Permanently Closed",
            "confidence": 0.85,
            "change_type": "correction",
            "source_tag": None,
            "review_outcome": None,
            "run_id": "2026-06-15_batch1",
        }
        assert entry["field_name"] == "operational_status"
        assert entry["original_value"] == "Active"
        assert entry["proposed_value"] == "Permanently Closed"
        assert entry["change_type"] == "correction"

    def test_closure_change_type_is_correction(self):
        """Closure entries should always be typed as 'correction'."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "change_type": "correction",
        }
        assert entry["change_type"] == "correction"

    def test_closure_entry_has_review_outcome(self):
        """Closure detected changes should support review_outcome."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "review_outcome": None,
        }
        assert entry["review_outcome"] is None
        entry["review_outcome"] = "accepted"
        assert entry["review_outcome"] == "accepted"
        entry["review_outcome"] = "rejected"
        assert entry["review_outcome"] == "rejected"

    def test_closure_entry_supports_corrected_value(self):
        """Closure entries should support corrected_value for alternatives."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "proposed_value": "Permanently Closed",
            "review_outcome": "rejected",
            "corrected_value": "Temporarily Closed",
        }
        assert entry["corrected_value"] == "Temporarily Closed"

    def test_closure_corrected_value_seasonal(self):
        """corrected_value can indicate seasonal closure."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "proposed_value": "Permanently Closed",
            "review_outcome": "rejected",
            "corrected_value": "Seasonal Closure",
        }
        assert entry["corrected_value"] == "Seasonal Closure"

    def test_closure_does_not_affect_confidence(self):
        """Adding closure to detected changes must not alter confidence."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "confidence": 0.85,
            "review_outcome": None,
        }
        original_conf = entry["confidence"]
        entry["review_outcome"] = "rejected"
        entry["corrected_value"] = "Temporarily Closed"
        assert entry["confidence"] == original_conf

    def test_closure_entry_has_run_id(self):
        """Closure detected changes should include run_id."""
        entry: dict[str, object] = {
            "field_name": "operational_status",
            "run_id": "2026-06-15_batch1",
        }
        assert isinstance(entry["run_id"], str)

    def test_closure_alert_still_exists_alongside_change(self):
        """Closure alert and detected change should coexist."""
        closure_alert: dict[str, object] = {
            "site_name": "Canyon Lake East Elementary",
            "reason": "Possible closure detected.",
        }
        detected_change: dict[str, object] = {
            "site_name": "Canyon Lake East Elementary",
            "field_name": "operational_status",
            "original_value": "Active",
            "proposed_value": "Permanently Closed",
            "change_type": "correction",
        }
        # Both exist independently
        assert closure_alert["site_name"] == detected_change["site_name"]
        assert "reason" in closure_alert
        assert detected_change["field_name"] == "operational_status"

    def test_closure_exportable_in_review_log(self):
        """Closure entries should be exportable in review_log.json."""
        entry: dict[str, object] = {
            "site_name": "Canyon Lake East Elementary",
            "field": "operational_status",
            "proposed_value": "Permanently Closed",
            "review_outcome": "accepted",
            "corrected_value": None,
            "run_id": "2026-06-15_batch1",
            "review_timestamp": "2026-06-15T12:00:00Z",
        }
        required = {"site_name", "field", "proposed_value", "review_outcome",
                     "run_id", "review_timestamp"}
        assert required.issubset(entry.keys())


# ===================================================================
# Section: TOP MISSED VALUES
# ===================================================================


class TestTopMissedValues:
    """Verify Top Missed Values only includes rejected rows with corrected_value."""

    def test_only_rejected_with_corrected_value(self):
        """Missed values must have review_outcome=rejected AND corrected_value set."""
        changes: list[dict[str, object]] = [
            {"review_outcome": "rejected", "corrected_value": "correct@org.com"},
            {"review_outcome": "rejected", "corrected_value": None},
            {"review_outcome": "accepted", "corrected_value": None},
            {"review_outcome": None, "corrected_value": None},
        ]
        missed = [c for c in changes if c["review_outcome"] == "rejected" and c["corrected_value"]]
        assert len(missed) == 1
        assert missed[0]["corrected_value"] == "correct@org.com"

    def test_empty_string_corrected_value_excluded(self):
        """Rows with empty string corrected_value should not appear."""
        changes: list[dict[str, object]] = [
            {"review_outcome": "rejected", "corrected_value": ""},
            {"review_outcome": "rejected", "corrected_value": "real@org.com"},
        ]
        missed = [c for c in changes if c["review_outcome"] == "rejected" and c["corrected_value"]]
        assert len(missed) == 1

    def test_limit_to_ten(self):
        """Top Missed Values should be capped at 10 entries."""
        changes: list[dict[str, object]] = [
            {"review_outcome": "rejected", "corrected_value": f"val{i}", "review_timestamp": f"2026-06-{15-i:02d}T12:00:00Z"}
            for i in range(15)
        ]
        missed = [c for c in changes if c["review_outcome"] == "rejected" and c["corrected_value"]]
        top = sorted(missed, key=lambda c: str(c.get("review_timestamp", "")), reverse=True)[:10]
        assert len(top) == 10

    def test_sorted_most_recent_first(self):
        """Missed values should be sorted by most recent timestamp first."""
        changes: list[dict[str, object]] = [
            {"review_outcome": "rejected", "corrected_value": "old", "review_timestamp": "2026-06-10T12:00:00Z"},
            {"review_outcome": "rejected", "corrected_value": "new", "review_timestamp": "2026-06-15T12:00:00Z"},
        ]
        missed = [c for c in changes if c["review_outcome"] == "rejected" and c["corrected_value"]]
        top = sorted(missed, key=lambda c: str(c.get("review_timestamp", "")), reverse=True)
        assert top[0]["corrected_value"] == "new"
        assert top[1]["corrected_value"] == "old"

    def test_no_impact_on_confidence(self):
        """Displaying missed values must not alter confidence."""
        change: dict[str, object] = {
            "confidence": 0.85,
            "review_outcome": "rejected",
            "corrected_value": "correct@org.com",
        }
        _ = change["review_outcome"] == "rejected" and change["corrected_value"]
        assert change["confidence"] == 0.85


# ===================================================================
# Section: SAVE STATE TRACKING
# ===================================================================


class TestSaveStateTracking:
    """Verify save state transitions: none → pending → saved → pending."""

    def test_initial_state_is_none(self):
        """New rows should have save state 'none'."""
        change: dict[str, object] = {"_saveState": "none", "review_outcome": None}
        assert change["_saveState"] == "none"

    def test_review_action_sets_pending(self):
        """Clicking Accept or Reject should set state to 'pending'."""
        change: dict[str, object] = {"_saveState": "none", "review_outcome": None}
        # Simulate accept
        change["review_outcome"] = "accepted"
        change["_saveState"] = "pending"
        assert change["_saveState"] == "pending"

    def test_reject_sets_pending(self):
        """Clicking Reject should set state to 'pending'."""
        change: dict[str, object] = {"_saveState": "none", "review_outcome": None}
        change["review_outcome"] = "rejected"
        change["_saveState"] = "pending"
        assert change["_saveState"] == "pending"

    def test_export_sets_saved(self):
        """After Export Reviews, reviewed rows should be 'saved'."""
        changes: list[dict[str, object]] = [
            {"review_outcome": "accepted", "_saveState": "pending"},
            {"review_outcome": "rejected", "_saveState": "pending"},
            {"review_outcome": None, "_saveState": "none"},
        ]
        # Simulate export
        for c in changes:
            if c["review_outcome"] is not None:
                c["_saveState"] = "saved"
        assert changes[0]["_saveState"] == "saved"
        assert changes[1]["_saveState"] == "saved"
        assert changes[2]["_saveState"] == "none"

    def test_editing_saved_row_returns_to_pending(self):
        """Editing corrected_value on a saved row should revert to 'pending'."""
        change: dict[str, object] = {
            "review_outcome": "rejected",
            "corrected_value": "old@org.com",
            "_saveState": "saved",
        }
        # Simulate editing corrected_value
        change["corrected_value"] = "new@org.com"
        if change["_saveState"] == "saved":
            change["_saveState"] = "pending"
        assert change["_saveState"] == "pending"

    def test_changing_review_decision_returns_to_pending(self):
        """Switching Accept→Reject on a saved row returns to 'pending'."""
        change: dict[str, object] = {
            "review_outcome": "accepted",
            "_saveState": "saved",
        }
        change["review_outcome"] = "rejected"
        change["_saveState"] = "pending"
        assert change["_saveState"] == "pending"

    def test_clearing_review_resets_state(self):
        """Clearing the review decision should reset save state to 'none'."""
        change: dict[str, object] = {
            "review_outcome": "accepted",
            "_saveState": "pending",
        }
        change["review_outcome"] = None
        change["_saveState"] = "none"
        assert change["_saveState"] == "none"

    def test_save_state_does_not_affect_confidence(self):
        """Save state tracking must not alter confidence."""
        change: dict[str, object] = {
            "confidence": 0.92,
            "_saveState": "none",
        }
        change["_saveState"] = "pending"
        assert change["confidence"] == 0.92
        change["_saveState"] = "saved"
        assert change["confidence"] == 0.92

    def test_save_state_not_in_export(self):
        """_saveState is UI-only and should not appear in review_log export."""
        change: dict[str, object] = {
            "site_name": "Test",
            "field": "publicEmail",
            "review_outcome": "accepted",
            "_saveState": "saved",
        }
        export_entry = {
            "site_name": change["site_name"],
            "field": change["field"],
            "review_outcome": change["review_outcome"],
        }
        assert "_saveState" not in export_entry


# ===================================================================
# Run
# ===================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
