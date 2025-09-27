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

    def get_organizations_for_ai(self, page: int = 1, per_page: int = 10, minimal: bool = False) -> Dict[str, Any]:
        """Fetch organizations for AI processing with client-side pagination.
        
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
            query GetOrganizationsForAIMinimal {
                organizationsForAI {
                    id
                    name
                    city
                    state
                    sites {
                        id
                        name
                        city
                        state
                        status
                    }
                }
            }
            '''
        else:
            # Full query with all available fields including site details
            query = '''
            query GetOrganizationsForAI {
                organizationsForAI {
                    id
                    name
                    streetAddress
                    addressLine2
                    city
                    state
                    zip
                    publicEmail
                    publicPhone
                    website
                    description
                    ein
                    sites {
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
            }
            '''

        try:
            result = self.client.execute_query(query)
            all_organizations = result.get("organizationsForAI", [])
            
            # Implement client-side pagination
            total_count = len(all_organizations)
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            
            # Calculate start and end indices for the requested page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            # Get the organizations for this page
            page_organizations = all_organizations[start_idx:end_idx]
            
            return {
                "data": page_organizations,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_count": total_count
            }
        except Exception as e:
            # If full query fails due to size, automatically retry with minimal fields
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_organizations_for_ai(page=page, per_page=per_page, minimal=True)
            else:
                raise

    def get_all_organizations_for_ai(self, per_page: int = 10, minimal: bool = False) -> List[Dict[str, Any]]:
        """Fetch all organizations for AI processing.
        
        Args:
            per_page: Not used for client-side implementation, kept for compatibility
            minimal: If True, returns only essential fields
            
        Returns:
            List of all organizations
        """
        
        if minimal:
            query = '''
            query GetOrganizationsForAIMinimal {
                organizationsForAI {
                    id
                    name
                    city
                    state
                    sites {
                        id
                        name
                        city
                        state
                        status
                    }
                }
            }
            '''
        else:
            query = '''
            query GetOrganizationsForAI {
                organizationsForAI {
                    id
                    name
                    streetAddress
                    addressLine2
                    city
                    state
                    zip
                    publicEmail
                    publicPhone
                    website
                    description
                    ein
                    sites {
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
            }
            '''

        try:
            result = self.client.execute_query(query)
            return result.get("organizationsForAI", [])
        except Exception as e:
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_all_organizations_for_ai(per_page=per_page, minimal=True)
            else:
                raise

    def create_organization(self, organization_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new charity organization."""
        mutation = '''
        mutation AddOrganizationFromAI($input: organizationInputForAI!) {
            addOrganizationFromAI(input: $input) {
                id
                name
                status
            }
        }
        '''

        return self.client.execute_query(mutation, {"input": organization_data})

    def update_organization(self, organization_id: str, organization_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing charity organization."""
        mutation = '''
        mutation UpdateOrganizationFromAI($organizationId: String!, $input: organizationInputForAIUpdate!) {
            updateOrganizationFromAI(organizationId: $organizationId, input: $input) {
                id
                name
                status
            }
        }
        '''

        return self.client.execute_query(
            mutation,
            {"organizationId": organization_id, "input": organization_data}
        )