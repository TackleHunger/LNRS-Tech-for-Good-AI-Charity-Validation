"""
Tests for site operations functionality.
"""

import pytest
from unittest.mock import Mock, patch
from src.tackle_hunger.site_operations import SiteOperations, AddressFix
from src.tackle_hunger.graphql_client import TackleHungerClient


class TestSiteOperations:
    """Test cases for SiteOperations class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=TackleHungerClient)
        self.site_ops = SiteOperations(self.mock_client)
    
    def test_analyze_site_addresses_with_po_box(self):
        """Test analysis identifies sites with PO box addresses."""
        sites = [
            {
                "id": "site1",
                "name": "Test Food Bank",
                "streetAddress": "P.O. Box 123",
                "addressLine2": None,
                "city": "Anytown",
                "state": "NY",
                "zip": "12345",
                "organizationId": "org1"
            },
            {
                "id": "site2", 
                "name": "Regular Food Bank",
                "streetAddress": "456 Main Street",
                "addressLine2": None,
                "city": "Anytown",
                "state": "NY", 
                "zip": "12345",
                "organizationId": "org2"
            }
        ]
        
        fixes = self.site_ops.analyze_site_addresses(sites)
        
        # Should identify 1 fix for the PO box address
        assert len(fixes) == 1
        assert fixes[0].site_id == "site1"
        assert fixes[0].action == "move_to_org"
        assert "P.O. Box 123" in fixes[0].new_org_address
        assert "Non-physical address detected" in fixes[0].reason
    
    def test_analyze_site_addresses_no_issues(self):
        """Test analysis with sites that have no address issues."""
        sites = [
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
                "addressLine2": "Suite 200",
                "city": "Anytown",
                "state": "NY",
                "zip": "12345", 
                "organizationId": "org2"
            }
        ]
        
        fixes = self.site_ops.analyze_site_addresses(sites)
        
        # Should identify no fixes needed
        assert len(fixes) == 0
    
    def test_analyze_site_addresses_missing_data(self):
        """Test analysis handles sites with missing data gracefully."""
        sites = [
            {
                "id": "site1",
                "name": "Incomplete Site",
                # Missing streetAddress
                "city": "Anytown",
                "state": "NY",
                "organizationId": "org1"
            },
            {
                "id": "site2",
                "name": "Another Incomplete Site",
                "streetAddress": "123 Main Street",
                # Missing organizationId
                "city": "Anytown",
                "state": "NY"
            }
        ]
        
        fixes = self.site_ops.analyze_site_addresses(sites)
        
        # Should handle missing data and not crash
        assert len(fixes) == 0
    
    def test_get_sites_for_ai_success(self):
        """Test successful fetching of sites."""
        mock_response = {
            "sitesForAI": [
                {
                    "id": "site1",
                    "name": "Test Site",
                    "streetAddress": "123 Main St",
                    "organizationId": "org1"
                }
            ]
        }
        self.mock_client.execute_query.return_value = mock_response
        
        sites = self.site_ops.get_sites_for_ai(limit=10)
        
        assert len(sites) == 1
        assert sites[0]["id"] == "site1"
        self.mock_client.execute_query.assert_called_once()
    
    def test_get_sites_for_ai_error(self):
        """Test handling of errors when fetching sites."""
        self.mock_client.execute_query.side_effect = Exception("GraphQL Error")
        
        sites = self.site_ops.get_sites_for_ai(limit=10)
        
        assert sites == []
    
    def test_update_site_from_ai_success(self):
        """Test successful site update."""
        mock_response = {
            "updateSiteFromAI": {
                "id": "site1",
                "name": "Updated Site",
                "streetAddress": "123 Updated St"
            }
        }
        self.mock_client.execute_query.return_value = mock_response
        
        site_input = {
            "streetAddress": "123 Updated St",
            "modifiedBy": "AI_Copilot_Assistant"
        }
        
        result = self.site_ops.update_site_from_ai("site1", site_input)
        
        assert result is True
        self.mock_client.execute_query.assert_called_once()
    
    def test_update_site_from_ai_failure(self):
        """Test handling of site update failure."""
        mock_response = {"updateSiteFromAI": None}
        self.mock_client.execute_query.return_value = mock_response
        
        site_input = {
            "streetAddress": "123 Updated St", 
            "modifiedBy": "AI_Copilot_Assistant"
        }
        
        result = self.site_ops.update_site_from_ai("site1", site_input)
        
        assert result is False
    
    def test_update_organization_from_ai_success(self):
        """Test successful organization update."""
        mock_response = {
            "updateOrganizationFromAI": {
                "id": "org1",
                "name": "Updated Org",
                "streetAddress": "P.O. Box 123"
            }
        }
        self.mock_client.execute_query.return_value = mock_response
        
        org_input = {
            "streetAddress": "P.O. Box 123",
            "modifiedBy": "AI_Copilot_Assistant"
        }
        
        result = self.site_ops.update_organization_from_ai("org1", org_input)
        
        assert result is True
        self.mock_client.execute_query.assert_called_once()
    
    def test_find_physical_address_from_org_sites(self):
        """Test finding physical address from organization sites."""
        sites = [
            {
                "id": "site1",
                "streetAddress": "P.O. Box 123",  # PO box - should skip
                "city": "Anytown",
                "state": "NY",
                "zip": "12345"
            },
            {
                "id": "site2", 
                "streetAddress": "456 Main Street",  # Physical - should use
                "addressLine2": "Suite 200",
                "city": "Anytown",
                "state": "NY",
                "zip": "12345"
            },
            {
                "id": "site3",
                "streetAddress": "789 Oak Avenue",  # Physical - could use
                "city": "Anytown", 
                "state": "NY",
                "zip": "12345"
            }
        ]
        
        # Exclude site2, should find site3
        result = self.site_ops._find_physical_address_from_org_sites(sites, "site2")
        
        assert result is not None
        assert result["streetAddress"] == "789 Oak Avenue"
        assert result["city"] == "Anytown"
        assert result["state"] == "NY"
        assert result["zip"] == "12345"
    
    def test_find_physical_address_no_physical_sites(self):
        """Test when no physical addresses are found in organization sites."""
        sites = [
            {
                "id": "site1",
                "streetAddress": "P.O. Box 123",
                "city": "Anytown",
                "state": "NY", 
                "zip": "12345"
            },
            {
                "id": "site2",
                "streetAddress": "PMB 456",
                "city": "Anytown",
                "state": "NY",
                "zip": "12345"
            }
        ]
        
        result = self.site_ops._find_physical_address_from_org_sites(sites, "site3")
        
        assert result is None
    
    @patch('src.tackle_hunger.site_operations.logger')
    def test_apply_address_fix_success(self, mock_logger):
        """Test successful application of address fix."""
        fix = AddressFix(
            site_id="site1",
            site_name="Test Site",
            original_address="P.O. Box 123",
            organization_id="org1", 
            action="move_to_org",
            new_org_address="P.O. Box 123",
            reason="PO Box detected"
        )
        
        # Mock organization data with physical address
        org_data = {
            "id": "org1",
            "sites": [
                {
                    "id": "site1",
                    "streetAddress": "P.O. Box 123"
                },
                {
                    "id": "site2",
                    "streetAddress": "456 Main Street",
                    "city": "Anytown",
                    "state": "NY",
                    "zip": "12345"
                }
            ]
        }
        
        # Mock the methods
        self.site_ops.update_organization_from_ai = Mock(return_value=True)
        self.site_ops.get_organization_for_ai = Mock(return_value=org_data)
        self.site_ops.update_site_from_ai = Mock(return_value=True)
        
        result = self.site_ops.apply_address_fix(fix)
        
        assert result is True
        self.site_ops.update_organization_from_ai.assert_called_once()
        self.site_ops.get_organization_for_ai.assert_called_once()
        self.site_ops.update_site_from_ai.assert_called_once()


class TestAddressFix:
    """Test cases for AddressFix dataclass."""
    
    def test_address_fix_creation(self):
        """Test creation of AddressFix object."""
        fix = AddressFix(
            site_id="site1",
            site_name="Test Site",
            original_address="P.O. Box 123",
            organization_id="org1",
            action="move_to_org",
            new_org_address="P.O. Box 123",
            reason="PO Box detected"
        )
        
        assert fix.site_id == "site1"
        assert fix.site_name == "Test Site"
        assert fix.original_address == "P.O. Box 123"
        assert fix.organization_id == "org1"
        assert fix.action == "move_to_org"
        assert fix.new_org_address == "P.O. Box 123"
        assert fix.reason == "PO Box detected"
        assert fix.new_site_address is None  # Default value


if __name__ == "__main__":
    pytest.main([__file__])