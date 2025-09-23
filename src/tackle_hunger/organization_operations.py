"""
Organization operations for charity validation.

Provides CRUD operations for charity organizations through GraphQL.
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
                    streetAddress
                    city
                    state
                    zip
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
                website
                description
                ein
                nonProfitStatus
                createdMethod
                modifiedBy
                status
                pendingStatus
            }
        }
        '''

        result = self.client.execute_query(query, {"limit": limit})
        return result.get("organizationsForAI", [])

    def update_organization(self, organization_id: str, organization_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing charity organization."""
        mutation = '''
        mutation UpdateOrganizationFromAI($organizationId: String!, $input: organizationInputUpdate!) {
            updateOrganizationFromAI(organizationId: $organizationId, input: $input) {
                id
                name
                status
                pendingStatus
            }
        }
        '''

        return self.client.execute_query(
            mutation,
            {"organizationId": organization_id, "input": organization_data}
        )