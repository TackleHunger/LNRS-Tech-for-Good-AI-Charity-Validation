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

    def get_sites_for_ai(self, page: int = 1, per_page: int = 10, minimal: bool = False) -> Dict[str, Any]:
        """Fetch sites for AI processing with client-side pagination.
        
        Args:
            page: Page number (1-based)
            per_page: Number of items per page (default 10 as requested)
            minimal: If True, returns only essential fields to avoid large payloads
            
        Returns:
            Dict with 'data', 'page', 'per_page', 'total_pages', and 'total_count' keys
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
            all_sites = result.get("sitesForAI", [])
            
            # Implement client-side pagination
            total_count = len(all_sites)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            # Calculate start and end indices for the requested page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            # Get the sites for this page
            page_sites = all_sites[start_idx:end_idx]
            
            return {
                "data": page_sites,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_count": total_count
            }
        except Exception as e:
            # If full query fails due to size, automatically retry with minimal fields
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_sites_for_ai(page=page, per_page=per_page, minimal=True)
            else:
                raise

    def get_all_sites_for_ai(self, per_page: int = 10, minimal: bool = False) -> List[Dict[str, Any]]:
        """Fetch all sites for AI processing.
        
        Args:
            per_page: Not used for client-side implementation, kept for compatibility
            minimal: If True, returns only essential fields
            
        Returns:
            List of all sites
        """
        
        if minimal:
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
            return result.get("sitesForAI", [])
        except Exception as e:
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_all_sites_for_ai(per_page=per_page, minimal=True)
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
