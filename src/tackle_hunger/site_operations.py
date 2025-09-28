"""
Site operations for charity validation.

Provides CRUD operations for charity sites through GraphQL.
"""

from typing import Dict, Any, List, Optional
from .graphql_client import TackleHungerClient


class SiteOperations:
    """Operations for managing charity sites."""

    def __init__(self, client: TackleHungerClient):
        self.client = client

    def get_sites_for_ai(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch sites for AI processing."""
        query = '''
        query GetSitesForAI($limit: Int) {
            sitesForAI(limit: $limit) {
                id
                organizationId
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
        }
        '''

        result = self.client.execute_query(query, {"limit": limit})
        return result.get("sitesForAI", [])

    def create_site(self, site_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new charity site."""
        mutation = '''
        mutation AddCharityFromAI($input: siteInputForAI!) {
            addCharityFromAI(input: $input) {
                id
                name
                status
                pendingStatus
            }
        }
        '''

        return self.client.execute_query(mutation, {"input": site_data})

    def update_site(self, site_id: str, site_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing charity site."""
        mutation = '''
        mutation UpdateSiteFromAI($siteId: String!, $input: siteInputForAIUpdate!) {
            updateSiteFromAI(siteId: $siteId, input: $input) {
                id
                name
                status
                pendingStatus
            }
        }
        '''

        return self.client.execute_query(
            mutation,
            {"siteId": site_id, "input": site_data}
        )
