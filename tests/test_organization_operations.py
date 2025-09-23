"""
Tests for organization operations functionality.
"""

import pytest
from unittest.mock import Mock, patch
from src.tackle_hunger.organization_operations import OrganizationOperations
from src.tackle_hunger.graphql_client import TackleHungerClient


def test_organization_operations_init():
    """Test OrganizationOperations initialization."""
    client = Mock(spec=TackleHungerClient)
    ops = OrganizationOperations(client)
    assert ops.client == client


def test_get_organizations_for_ai():
    """Test fetching organizations for AI processing."""
    client = Mock(spec=TackleHungerClient)
    client.execute_query.return_value = {
        "organizationsForAI": [
            {
                "id": "org1",
                "name": "Test Charity",
                "streetAddress": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip": "12345",
                "sites": [{"id": "site1", "name": "Main Site"}]
            }
        ]
    }
    
    ops = OrganizationOperations(client)
    result = ops.get_organizations_for_ai(limit=10)
    
    assert len(result) == 1
    assert result[0]["id"] == "org1"
    assert result[0]["name"] == "Test Charity"
    assert len(result[0]["sites"]) == 1
    
    # Verify query was called with correct parameters
    client.execute_query.assert_called_once()
    call_args = client.execute_query.call_args
    assert "organizationsForAI" in call_args[0][0]
    assert call_args[0][1]["limit"] == 10


def test_update_organization():
    """Test updating an organization."""
    client = Mock(spec=TackleHungerClient)
    client.execute_query.return_value = {
        "updateOrganizationFromAI": {
            "id": "org1",
            "name": "Updated Charity",
            "status": "ACTIVE",
            "pendingStatus": None
        }
    }
    
    ops = OrganizationOperations(client)
    update_data = {
        "name": "Updated Charity",
        "streetAddress": "456 New St"
    }
    
    result = ops.update_organization("org1", update_data)
    
    assert result["updateOrganizationFromAI"]["id"] == "org1"
    assert result["updateOrganizationFromAI"]["name"] == "Updated Charity"
    
    # Verify mutation was called with correct parameters
    client.execute_query.assert_called_once()
    call_args = client.execute_query.call_args
    assert "updateOrganizationFromAI" in call_args[0][0]
    assert call_args[0][1]["organizationId"] == "org1"
    assert call_args[0][1]["input"] == update_data


def test_get_organizations_empty_response():
    """Test handling empty response from organizations query."""
    client = Mock(spec=TackleHungerClient)
    client.execute_query.return_value = {}
    
    ops = OrganizationOperations(client)
    result = ops.get_organizations_for_ai()
    
    assert result == []