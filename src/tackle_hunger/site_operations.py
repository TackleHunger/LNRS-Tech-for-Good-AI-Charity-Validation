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

    def get_sites_for_ai(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch sites for AI processing.
        
        Args:
            limit: Maximum number of sites to return (not supported by GraphQL API)
            
        Note: The GraphQL API doesn't support server-side limiting on sitesForAI field.
        All data is returned and client-side limiting should be applied if needed.
        """
        # Fixed query without limit argument as it's not supported by the API
        query = '''
        query GetSitesForAI {
            sitesForAI {
                id
                organizationId
                name
                streetAddress
                city
                state
                zip
                lat
                lng
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

        try:
            result = self.client.execute_query(query)
            sites = result.get("sitesForAI", [])
            
            # Apply limit client-side if specified
            if limit is not None:
                sites = sites[:limit]
                
            return sites
        except Exception as e:
            # If query fails, try a minimal version
            minimal_query = '''
            query GetSitesForAIMinimal {
                sitesForAI {
                    id
                    name
                    city
                    state
                    status
                }
            }
            '''
            try:
                result = self.client.execute_query(minimal_query)
                sites = result.get("sitesForAI", [])
                if limit is not None:
                    sites = sites[:limit]
                return sites
            except Exception as minimal_e:
                raise Exception(f"Failed to fetch sites: {str(e)}. Minimal query also failed: {str(minimal_e)}")

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
