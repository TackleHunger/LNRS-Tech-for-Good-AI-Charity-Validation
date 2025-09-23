"""
Organization operations for charity validation.

Provides operations for fetching and analyzing charity organizations through GraphQL.
"""

from typing import Dict, Any, List, Optional
from .graphql_client import TackleHungerClient


class OrganizationOperations:
    """Operations for managing charity organizations."""

    def __init__(self, client: TackleHungerClient):
        self.client = client

    def get_organizations_for_ai(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch organizations for AI processing."""
        query = '''
        query GetOrganizationsForAI($limit: Int) {
            organizationsForAI(limit: $limit) {
                id
                sites {
                    id
                    name
                }
                name
                streetAddress
                addressLine2
                city
                state
                zip
                publicEmail
                publicPhone
                email
                phone
                isFeedingAmericaAffiliate
                description
                ein
                banner
                logo
                updatedAt
                createdAt
            }
        }
        '''

        result = self.client.execute_query(query, {"limit": limit})
        return result.get("organizationsForAI", [])

    def get_organization_by_id(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific organization by ID."""
        query = '''
        query GetOrganizationForAI($orgId: ID!) {
            organizationForAI(id: $orgId) {
                id
                sites {
                    id
                    name
                    streetAddress
                    city
                    state
                    zip
                    publicEmail
                    publicPhone
                    website
                    description
                    serviceArea
                    acceptsFoodDonations
                    status
                    ein
                }
                name
                streetAddress
                addressLine2
                city
                state
                zip
                publicEmail
                publicPhone
                email
                phone
                isFeedingAmericaAffiliate
                description
                ein
                banner
                logo
                updatedAt
                createdAt
            }
        }
        '''

        try:
            result = self.client.execute_query(query, {"orgId": org_id})
            return result.get("organizationForAI")
        except Exception:
            return None

    def update_organization(self, org_id: str, org_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing organization."""
        mutation = '''
        mutation UpdateOrganizationFromAI($organizationId: String!, $input: organizationInputUpdate!) {
            updateOrganizationFromAI(organizationId: $organizationId, input: $input) {
                id
                name
                updatedAt
            }
        }
        '''

        return self.client.execute_query(
            mutation,
            {"organizationId": org_id, "input": org_data}
        )