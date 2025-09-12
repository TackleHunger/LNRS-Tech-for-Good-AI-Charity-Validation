"""
Site operations for Tackle Hunger charity validation.

Provides functionality to fetch, validate, and update charity sites,
including fixing non-food-service addresses like PO boxes.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
from dataclasses import dataclass

from .graphql_client import TackleHungerClient
from .address_validator import AddressValidator


logger = logging.getLogger(__name__)


@dataclass
class AddressFix:
    """Represents an address fix operation."""

    site_id: str
    site_name: str
    original_address: str
    organization_id: str
    action: str  # "move_to_org", "update_from_org", "no_action"
    new_site_address: Optional[str] = None
    new_org_address: Optional[str] = None
    reason: str = ""


class SiteOperations:
    """Operations for managing charity sites and fixing address issues."""

    def __init__(self, client: TackleHungerClient):
        """
        Initialize site operations with a GraphQL client.

        Args:
            client: Authenticated TackleHungerClient instance
        """
        self.client = client
        self.address_validator = AddressValidator()

    def get_sites_for_ai(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch sites for AI processing.

        Args:
            limit: Maximum number of sites to return
            offset: Number of sites to skip

        Returns:
            List of site dictionaries
        """
        query = """
        query getSitesForAI($limit: Int!, $offset: Int!) {
            sitesForAI(limit: $limit, offset: $offset) {
                id
                name
                streetAddress
                addressLine2
                city
                state
                zip
                country
                organizationId
                organization {
                    id
                    name
                    streetAddress
                    addressLine2
                    city
                    state
                    zip
                }
            }
        }
        """

        variables = {"limit": limit, "offset": offset}

        try:
            result = self.client.execute_query(query, variables)
            return result.get("sitesForAI", [])
        except Exception as e:
            logger.error(f"Error fetching sites: {e}")
            return []

    def get_organization_for_ai(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch organization details for AI processing.

        Args:
            organization_id: Organization ID to fetch

        Returns:
            Organization dictionary or None if not found
        """
        query = """
        query getOrganizationForAI($organizationId: ID!) {
            organizationForAI(id: $organizationId) {
                id
                name
                streetAddress
                addressLine2
                city
                state
                zip
                sites {
                    id
                    name
                    streetAddress
                    addressLine2
                    city
                    state
                    zip
                }
            }
        }
        """

        variables = {"organizationId": organization_id}

        try:
            result = self.client.execute_query(query, variables)
            return result.get("organizationForAI")
        except Exception as e:
            logger.error(f"Error fetching organization {organization_id}: {e}")
            return None

    def analyze_site_addresses(self, sites: List[Dict[str, Any]]) -> List[AddressFix]:
        """
        Analyze sites to identify address fixes needed.

        Args:
            sites: List of site dictionaries

        Returns:
            List of AddressFix objects describing needed changes
        """
        fixes = []

        for site in sites:
            try:
                site_id = site.get("id")
                site_name = site.get("name", "Unknown Site")
                street_address = site.get("streetAddress")
                address_line2 = site.get("addressLine2")
                organization_id = site.get("organizationId")

                if not street_address or not organization_id:
                    continue

                # Check if the site address is suitable
                is_suitable = self.address_validator.is_suitable_for_site(street_address, address_line2)

                if not is_suitable:
                    # This address should be moved to the organization
                    classification = self.address_validator.classify_address(street_address, address_line2)

                    fix = AddressFix(
                        site_id=site_id,
                        site_name=site_name,
                        original_address=f"{street_address} {address_line2 or ''}".strip(),
                        organization_id=organization_id,
                        action="move_to_org",
                        new_org_address=f"{street_address} {address_line2 or ''}".strip(),
                        reason=f"Non-physical address detected: {classification.reason}",
                    )
                    fixes.append(fix)

            except Exception as e:
                logger.error(f"Error analyzing site {site.get('id', 'unknown')}: {e}")

        return fixes

    def update_site_from_ai(self, site_id: str, site_input: Dict[str, Any]) -> bool:
        """
        Update a site using the updateSiteFromAI mutation.

        Args:
            site_id: Site ID to update
            site_input: Site input data matching siteInputForAIUpdate schema

        Returns:
            True if successful, False otherwise
        """
        mutation = """
        mutation updateSiteFromAI($siteId: String!, $input: siteInputForAIUpdate!) {
            updateSiteFromAI(siteId: $siteId, input: $input) {
                id
                name
                streetAddress
                addressLine2
                city
                state
                zip
            }
        }
        """

        variables = {"siteId": site_id, "input": site_input}

        try:
            result = self.client.execute_query(mutation, variables)
            updated_site = result.get("updateSiteFromAI")
            if updated_site:
                logger.info(f"Successfully updated site {site_id}")
                return True
            else:
                logger.error(f"Failed to update site {site_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating site {site_id}: {e}")
            return False

    def update_organization_from_ai(self, organization_id: str, org_input: Dict[str, Any]) -> bool:
        """
        Update an organization using the updateOrganizationFromAI mutation.

        Args:
            organization_id: Organization ID to update
            org_input: Organization input data matching organizationInputUpdate schema

        Returns:
            True if successful, False otherwise
        """
        mutation = """
        mutation updateOrganizationFromAI($organizationId: String!, $input: organizationInputUpdate!) {
            updateOrganizationFromAI(organizationId: $organizationId, input: $input) {
                id
                name
                streetAddress
                addressLine2
                city
                state
                zip
            }
        }
        """

        variables = {"organizationId": organization_id, "input": org_input}

        try:
            result = self.client.execute_query(mutation, variables)
            updated_org = result.get("updateOrganizationFromAI")
            if updated_org:
                logger.info(f"Successfully updated organization {organization_id}")
                return True
            else:
                logger.error(f"Failed to update organization {organization_id}")
                return False
        except Exception as e:
            logger.error(f"Error updating organization {organization_id}: {e}")
            return False

    def apply_address_fix(self, fix: AddressFix) -> bool:
        """
        Apply an address fix to move PO box from site to organization.

        Args:
            fix: AddressFix object describing the change to make

        Returns:
            True if successful, False otherwise
        """
        success = True

        try:
            if fix.action == "move_to_org":
                # First, update the organization with the PO box address
                org_input = {"streetAddress": fix.new_org_address, "modifiedBy": "AI_Copilot_Assistant"}

                org_success = self.update_organization_from_ai(fix.organization_id, org_input)

                if org_success:
                    # Now get organization's physical address to update the site
                    org_data = self.get_organization_for_ai(fix.organization_id)

                    if org_data and org_data.get("sites"):
                        # Find a physical address from other sites in the organization
                        physical_address = self._find_physical_address_from_org_sites(org_data["sites"], fix.site_id)

                        if physical_address:
                            site_input = {
                                "streetAddress": physical_address["streetAddress"],
                                "city": physical_address["city"],
                                "state": physical_address["state"],
                                "zip": physical_address["zip"],
                                "modifiedBy": "AI_Copilot_Assistant",
                            }

                            if physical_address.get("addressLine2"):
                                site_input["addressLine2"] = physical_address["addressLine2"]

                            site_success = self.update_site_from_ai(fix.site_id, site_input)
                            success = success and site_success
                        else:
                            # Clear the site address since we don't have a physical replacement
                            site_input = {"streetAddress": "", "modifiedBy": "AI_Copilot_Assistant"}
                            site_success = self.update_site_from_ai(fix.site_id, site_input)
                            success = success and site_success
                            logger.warning(f"No physical address found for site {fix.site_id}, cleared address")

                    success = success and org_success
                else:
                    success = False

        except Exception as e:
            logger.error(f"Error applying address fix for site {fix.site_id}: {e}")
            success = False

        return success

    def _find_physical_address_from_org_sites(
        self, sites: List[Dict[str, Any]], exclude_site_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a physical address from other sites in the organization.

        Args:
            sites: List of sites belonging to the organization
            exclude_site_id: Site ID to exclude from search

        Returns:
            Dictionary with address components or None if no physical address found
        """
        for site in sites:
            if site.get("id") == exclude_site_id:
                continue

            street_address = site.get("streetAddress")
            address_line2 = site.get("addressLine2")

            if street_address and self.address_validator.is_suitable_for_site(street_address, address_line2):
                return {
                    "streetAddress": street_address,
                    "addressLine2": address_line2,
                    "city": site.get("city"),
                    "state": site.get("state"),
                    "zip": site.get("zip"),
                }

        return None

    def fix_non_food_service_addresses(self, limit: int = 50) -> Tuple[int, int]:
        """
        Main function to fix non-food-service addresses in sites.

        Identifies sites with PO boxes or other non-physical addresses,
        moves those addresses to the parent organization, and updates
        the site with a physical address if available.

        Args:
            limit: Maximum number of sites to process

        Returns:
            Tuple of (sites_processed, fixes_applied)
        """
        logger.info(f"Starting to fix non-food-service addresses for up to {limit} sites")

        # Fetch sites for processing
        sites = self.get_sites_for_ai(limit=limit)
        logger.info(f"Fetched {len(sites)} sites for analysis")

        # Analyze sites to identify needed fixes
        fixes = self.analyze_site_addresses(sites)
        logger.info(f"Identified {len(fixes)} sites requiring address fixes")

        # Apply fixes
        fixes_applied = 0
        for fix in fixes:
            logger.info(f"Applying fix for site {fix.site_id} ({fix.site_name}): {fix.reason}")

            if self.apply_address_fix(fix):
                fixes_applied += 1
                logger.info(f"Successfully applied fix for site {fix.site_id}")
            else:
                logger.error(f"Failed to apply fix for site {fix.site_id}")

        logger.info(f"Completed processing. Sites analyzed: {len(sites)}, Fixes applied: {fixes_applied}")
        return len(sites), fixes_applied
