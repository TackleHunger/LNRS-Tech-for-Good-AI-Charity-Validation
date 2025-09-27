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

    def get_organizations_for_ai(self, limit: Optional[int] = None, minimal: bool = False) -> List[Dict[str, Any]]:
        """Fetch organizations for AI processing.
        
        Args:
            limit: Maximum number of organizations to return (applied client-side)
            minimal: If True, returns only essential fields to avoid large payloads
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
            organizations = result.get("organizationsForAI", [])
            
            # Apply limit client-side if specified
            if limit is not None:
                organizations = organizations[:limit]
                
            return organizations
        except Exception as e:
            # If full query fails due to size, automatically retry with minimal fields
            if not minimal:
                print(f"Warning: Full query failed ({str(e)[:100]}...), retrying with minimal fields")
                return self.get_organizations_for_ai(limit=limit, minimal=True)
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