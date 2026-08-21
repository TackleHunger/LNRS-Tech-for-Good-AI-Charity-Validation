"""
Site operations for charity validation.

Provides CRUD operations for charity sites through GraphQL.
"""

import logging
from typing import Dict, Any, List, Optional
import hashlib
from .graphql_client import TackleHungerClient

logger = logging.getLogger(__name__)

def _seed_to_start_index(seed: str, n: int) -> int:
    """Convert a seed string into a stable start index in [0, n)."""
    if n <= 0:
        return 0
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % n


def _rotate_and_take(items: list, limit: int, seed=None) -> list:
    """Rotate a list based on seed and return first `limit` items."""
    if limit <= 0 or not items:
        return []
    if seed is None or len(items) <= limit:
        return items[:limit]
    items_sorted = sorted(items, key=lambda x: (x.get("id") or ""))
    start = _seed_to_start_index(seed, len(items_sorted))
    rotated = items_sorted[start:] + items_sorted[:start]
    return rotated[:limit]


class SiteOperations:
    """Operations for managing charity sites."""

    def __init__(self, client: TackleHungerClient):
        self.client = client

    def get_sites_for_ai(self, limit: Optional[int] = None, minimal: bool = False, seed: Optional[str] = None) -> List[Dict[str, Any]]:
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
            
            # Apply limit client-side with seed-based rotation
            if limit is not None:
                sites = _rotate_and_take(sites, limit=limit, seed=seed)
                
            return sites
        except (ConnectionError, TimeoutError, OSError) as e:
            # If full query fails due to size/transport, retry with minimal fields
            if not minimal:
                logger.warning("Full query failed (%s), retrying with minimal fields", str(e)[:100])
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
