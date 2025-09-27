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

    def get_sites_for_ai(self, limit: Optional[int] = None, minimal: bool = False) -> List[Dict[str, Any]]:
        """Fetch sites for AI processing.
        
        Args:
            limit: Maximum number of sites to return (applied client-side)
            minimal: If True, returns only essential fields to avoid large payloads
            
        Note: The GraphQL API doesn't support server-side limiting on sitesForAI field.
        For large datasets, consider using minimal=True to reduce network load.
        """
        
        if minimal:
            # Minimal query for better performance with large datasets
            query = '''
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
        else:
            # Full query with all available fields
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
                    contactEmail
                    contactPhone
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
            # If full query fails due to size, automatically retry with minimal fields
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_sites_for_ai(limit=limit, minimal=True)
            else:
                raise

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
