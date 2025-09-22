"""
Integration tests for the fix non-food-service addresses functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations


class TestNonFoodServiceAddressFix:
    """Integration tests for the complete address fix workflow."""
    
    def test_end_to_end_address_fix_workflow(self):
        """Test the complete workflow from detection to fix."""
        
        # Mock client and responses
        mock_client = Mock(spec=TackleHungerClient)
        
        # Mock sites data with a PO box that needs fixing
        mock_sites_response = {
            "sitesForAI": [
                {
                    "id": "site1",
                    "name": "Food Bank with PO Box",
                    "streetAddress": "P.O. Box 123",
                    "addressLine2": None,
                    "city": "Anytown",
                    "state": "NY",
                    "zip": "12345",
                    "organizationId": "org1",
                    "organization": {
                        "id": "org1",
                        "name": "Test Organization",
                        "streetAddress": None,
                        "addressLine2": None,
                        "city": None,
                        "state": None,
                        "zip": None
                    }
                },
                {
                    "id": "site2",
                    "name": "Food Bank with Physical Address",
                    "streetAddress": "456 Main Street",
                    "addressLine2": "Suite 200",
                    "city": "Anytown", 
                    "state": "NY",
                    "zip": "12345",
                    "organizationId": "org1",
                    "organization": {
                        "id": "org1",
                        "name": "Test Organization",
                        "streetAddress": None,
                        "addressLine2": None,
                        "city": None,
                        "state": None,
                        "zip": None
                    }
                }
            ]
        }
        
        # Mock organization data
        mock_org_response = {
            "organizationForAI": {
                "id": "org1",
                "name": "Test Organization",
                "streetAddress": None,
                "addressLine2": None,
                "city": None,
                "state": None,
                "zip": None,
                "sites": [
                    {
                        "id": "site1",
                        "name": "Food Bank with PO Box",
                        "streetAddress": "P.O. Box 123",
                        "addressLine2": None,
                        "city": "Anytown",
                        "state": "NY",
                        "zip": "12345"
                    },
                    {
                        "id": "site2",
                        "name": "Food Bank with Physical Address",
                        "streetAddress": "456 Main Street",
                        "addressLine2": "Suite 200",
                        "city": "Anytown",
                        "state": "NY",
                        "zip": "12345"
                    }
                ]
            }
        }
        
        # Mock update responses
        mock_update_org_response = {
            "updateOrganizationFromAI": {
                "id": "org1",
                "name": "Test Organization",
                "streetAddress": "P.O. Box 123"
            }
        }
        
        mock_update_site_response = {
            "updateSiteFromAI": {
                "id": "site1",
                "name": "Food Bank with PO Box",
                "streetAddress": "456 Main Street"
            }
        }
        
        # Configure mock responses based on query content
        def mock_execute_query(query, variables=None):
            if "sitesForAI" in query:
                return mock_sites_response
            elif "organizationForAI" in query:
                return mock_org_response
            elif "updateOrganizationFromAI" in query:
                return mock_update_org_response
            elif "updateSiteFromAI" in query:
                return mock_update_site_response
            else:
                return {}
        
        mock_client.execute_query.side_effect = mock_execute_query
        
        # Initialize site operations
        site_ops = SiteOperations(mock_client)
        
        # Test the complete workflow
        sites_processed, fixes_applied = site_ops.fix_non_food_service_addresses(limit=10)
        
        # Verify results
        assert sites_processed == 2  # Two sites were fetched
        assert fixes_applied == 1    # One fix was applied (for the PO box site)
        
        # Verify the correct GraphQL calls were made
        assert mock_client.execute_query.call_count >= 4  # Fetch sites, fetch org, update org, update site
        
        # Verify specific mutations were called
        call_queries = [call[0][0] for call in mock_client.execute_query.call_args_list]
        
        # Should have called sitesForAI query
        assert any("sitesForAI" in query for query in call_queries)
        
        # Should have called organizationForAI query  
        assert any("organizationForAI" in query for query in call_queries)
        
        # Should have called updateOrganizationFromAI mutation
        assert any("updateOrganizationFromAI" in query for query in call_queries)
        
        # Should have called updateSiteFromAI mutation
        assert any("updateSiteFromAI" in query for query in call_queries)
    
    def test_no_fixes_needed_scenario(self):
        """Test scenario where no sites need address fixes."""
        
        mock_client = Mock(spec=TackleHungerClient)
        
        # Mock sites data with only physical addresses
        mock_sites_response = {
            "sitesForAI": [
                {
                    "id": "site1",
                    "name": "Food Bank 1",
                    "streetAddress": "123 Main Street",
                    "addressLine2": None,
                    "city": "Anytown",
                    "state": "NY",
                    "zip": "12345",
                    "organizationId": "org1"
                },
                {
                    "id": "site2",
                    "name": "Food Bank 2",
                    "streetAddress": "456 Oak Avenue",
                    "addressLine2": "Building B",
                    "city": "Anytown",
                    "state": "NY",
                    "zip": "12345",
                    "organizationId": "org2"
                }
            ]
        }
        
        mock_client.execute_query.return_value = mock_sites_response
        
        # Initialize site operations
        site_ops = SiteOperations(mock_client)
        
        # Test the workflow
        sites_processed, fixes_applied = site_ops.fix_non_food_service_addresses(limit=10)
        
        # Verify results
        assert sites_processed == 2
        assert fixes_applied == 0
        
        # Verify only the sites fetch query was called
        assert mock_client.execute_query.call_count == 1
    
    @patch('tackle_hunger.site_operations.logger')
    def test_error_handling_during_fix(self, mock_logger):
        """Test error handling when fixes fail."""
        
        mock_client = Mock(spec=TackleHungerClient)
        
        # Mock sites response with PO box
        mock_sites_response = {
            "sitesForAI": [
                {
                    "id": "site1",
                    "name": "Food Bank with PO Box",
                    "streetAddress": "P.O. Box 123",
                    "addressLine2": None,
                    "city": "Anytown",
                    "state": "NY",
                    "zip": "12345",
                    "organizationId": "org1"
                }
            ]
        }
        
        # Mock organization response
        mock_org_response = {
            "organizationForAI": {
                "id": "org1",
                "sites": []
            }
        }
        
        # Mock failed update response
        mock_failed_update = {
            "updateOrganizationFromAI": None
        }
        
        def mock_execute_query(query, variables=None):
            if "sitesForAI" in query:
                return mock_sites_response
            elif "organizationForAI" in query:
                return mock_org_response
            elif "updateOrganizationFromAI" in query:
                return mock_failed_update
            else:
                return {}
        
        mock_client.execute_query.side_effect = mock_execute_query
        
        # Initialize site operations
        site_ops = SiteOperations(mock_client)
        
        # Test the workflow
        sites_processed, fixes_applied = site_ops.fix_non_food_service_addresses(limit=10)
        
        # Verify results - should process site but fail to apply fix
        assert sites_processed == 1
        assert fixes_applied == 0
        
        # Verify error was logged
        mock_logger.error.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])