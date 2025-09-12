"""
Address validation utilities for Tackle Hunger charity validation.

Provides functionality to identify non-food-service addresses like PO boxes
that should be moved from Sites to Organizations.
"""

import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AddressClassification:
    """Classification result for an address."""

    is_po_box: bool
    is_physical_address: bool
    confidence: float
    reason: str


class AddressValidator:
    """Validates addresses and identifies non-food-service addresses."""

    # Patterns that indicate a PO Box or non-physical address
    PO_BOX_PATTERNS = [
        r"\b(p\.?\s*o\.?\s*box|post\s*office\s*box|postal\s*box)\b",
        r"\b(pob\s*\d+)\b",
        r"\b(po\s*\d+)\b",
        r"\b(p\.o\.\s*\d+)\b",
        r"^(box\s*\d+)$",  # Only match "box ###" if it's the entire address
        r"\b(po\s*box)\b",
    ]

    # Patterns that indicate a virtual/mail forwarding service
    VIRTUAL_ADDRESS_PATTERNS = [
        r"\b(suite\s*\d+)\b.*\b(mail\s*forwarding|virtual|mailbox)\b",
        r"\b(pmb|private\s*mail\s*box)\s*\d+\b",
        r"\b(mail\s*drop)\s*\d+\b",
        r"\b(c/o\s*[a-z\s]+mail)\b",
    ]

    # Patterns that strongly indicate a physical address
    PHYSICAL_ADDRESS_INDICATORS = [
        r"\d+\s+[a-z\s]+(street|st|avenue|ave|road|rd|lane|ln|drive|dr|"
        r"boulevard|blvd|way|place|pl|court|ct|circle|cir)\b",
        r"\d+\s+[nsew]\.?\s+[a-z\s]+(street|st|avenue|ave|road|rd|boulevard|blvd)\b",
        r"\b(building|bldg|floor|suite)\s*[a-z\d]+\b",
    ]

    def __init__(self):
        """Initialize the address validator with compiled regex patterns."""
        self.po_box_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.PO_BOX_PATTERNS]
        self.virtual_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.VIRTUAL_ADDRESS_PATTERNS]
        self.physical_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.PHYSICAL_ADDRESS_INDICATORS]

    def classify_address(self, street_address: str, address_line2: Optional[str] = None) -> AddressClassification:
        """
        Classify an address to determine if it's suitable for a food service Site.

        Args:
            street_address: Primary street address
            address_line2: Secondary address line (optional)

        Returns:
            AddressClassification with details about the address type
        """
        if not street_address:
            return AddressClassification(
                is_po_box=False, is_physical_address=False, confidence=0.0, reason="No address provided"
            )

        full_address = street_address.lower()
        if address_line2:
            full_address += " " + address_line2.lower()

        # Check for PO Box patterns
        po_box_matches = []
        for pattern in self.po_box_regex:
            if pattern.search(full_address):
                po_box_matches.append(pattern.pattern)

        if po_box_matches:
            return AddressClassification(
                is_po_box=True,
                is_physical_address=False,
                confidence=0.9,
                reason=f"Contains PO Box pattern: {', '.join(po_box_matches)}",
            )

        # Check for virtual address patterns
        virtual_matches = []
        for pattern in self.virtual_regex:
            if pattern.search(full_address):
                virtual_matches.append(pattern.pattern)

        if virtual_matches:
            return AddressClassification(
                is_po_box=False,
                is_physical_address=False,
                confidence=0.8,
                reason=f"Contains virtual address pattern: {', '.join(virtual_matches)}",
            )

        # Check for physical address indicators
        physical_matches = []
        for pattern in self.physical_regex:
            if pattern.search(full_address):
                physical_matches.append(pattern.pattern)

        if physical_matches:
            return AddressClassification(
                is_po_box=False,
                is_physical_address=True,
                confidence=0.85,
                reason=f"Contains physical address indicators: {', '.join(physical_matches)}",
            )

        # Default case - uncertain
        return AddressClassification(
            is_po_box=False,
            is_physical_address=False,
            confidence=0.3,
            reason="Unable to definitively classify address type",
        )

    def is_suitable_for_site(self, street_address: str, address_line2: Optional[str] = None) -> bool:
        """
        Determine if an address is suitable for a food service Site.

        Sites should have physical addresses for food pickup/dropoff/distribution.
        PO boxes and virtual addresses should be moved to the parent Organization.

        Args:
            street_address: Primary street address
            address_line2: Secondary address line (optional)

        Returns:
            True if address is suitable for a Site, False if it should be on Organization
        """
        classification = self.classify_address(street_address, address_line2)

        # If it's clearly a PO box or virtual address, not suitable for Site
        if classification.is_po_box or (not classification.is_physical_address and classification.confidence > 0.7):
            return False

        # If it's clearly a physical address, suitable for Site
        if classification.is_physical_address and classification.confidence > 0.7:
            return True

        # For uncertain cases, err on the side of keeping it on the Site
        # Human review can decide on edge cases
        return True

    def extract_address_components(self, site_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract street address and address line 2 from site data.

        Args:
            site_data: Dictionary containing site information

        Returns:
            Tuple of (street_address, address_line2)
        """
        street_address = site_data.get("streetAddress")
        address_line2 = site_data.get("addressLine2")

        return street_address, address_line2


# Convenience function for quick validation
def is_po_box_address(street_address: str, address_line2: Optional[str] = None) -> bool:
    """
    Quick check if an address is a PO box.

    Args:
        street_address: Primary street address
        address_line2: Secondary address line (optional)

    Returns:
        True if the address appears to be a PO box
    """
    validator = AddressValidator()
    classification = validator.classify_address(street_address, address_line2)
    return classification.is_po_box
