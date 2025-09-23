"""
Tests for organization operations functionality.
"""

import pytest
from unittest.mock import Mock
from src.tackle_hunger.organization_operations import OrganizationOperations
from src.tackle_hunger.graphql_client import TackleHungerClient


@pytest.fixture
def mock_client():
    """Create a mock GraphQL client."""
    client = Mock(spec=TackleHungerClient)
    return client


@pytest.fixture
def org_operations(mock_client):
    """Create organization operations with mock client."""
    return OrganizationOperations(mock_client)


def test_init(mock_client):
    """Test OrganizationOperations initialization."""
    ops = OrganizationOperations(mock_client)
    assert ops.client == mock_client


def test_get_organizations_for_ai(org_operations, mock_client):
    """Test fetching organizations for AI processing."""
    # Mock the response
    mock_response = {
        "organizationsForAI": [
            {
                "id": "org1",
                "name": "Test Organization",
                "sites": [{"id": "site1", "name": "Test Site"}],
                "streetAddress": "123 Main St",
                "city": "Test City",
                "state": "CA",
                "zip": "12345",
                "publicEmail": "info@test.org",
                "ein": "12-3456789"
            }
        ]
    }
    
    mock_client.execute_query.return_value = mock_response
    
    result = org_operations.get_organizations_for_ai(limit=10)
    
    # Verify the query was called
    mock_client.execute_query.assert_called_once()
    call_args = mock_client.execute_query.call_args
    
    # Check that the query contains expected fields
    query = call_args[0][0]
    assert "organizationsForAI" in query
    assert "limit: $limit" in query
    assert "id" in query
    assert "name" in query
    assert "sites" in query
    
    # Check variables
    variables = call_args[0][1]
    assert variables == {"limit": 10}
    
    # Check result
    assert result == mock_response["organizationsForAI"]
    assert len(result) == 1
    assert result[0]["id"] == "org1"
    assert result[0]["name"] == "Test Organization"


def test_get_organizations_for_ai_default_limit(org_operations, mock_client):
    """Test fetching organizations with default limit."""
    mock_client.execute_query.return_value = {"organizationsForAI": []}
    
    org_operations.get_organizations_for_ai()
    
    # Check that default limit was used
    call_args = mock_client.execute_query.call_args
    variables = call_args[0][1]
    assert variables == {"limit": 50}


def test_get_organization_by_id_success(org_operations, mock_client):
    """Test fetching a specific organization by ID successfully."""
    mock_response = {
        "organizationForAI": {
            "id": "org123",
            "name": "Specific Organization",
            "sites": [
                {
                    "id": "site1",
                    "name": "Site 1",
                    "streetAddress": "456 Oak Ave",
                    "city": "Another City",
                    "state": "NY",
                    "zip": "54321"
                }
            ],
            "publicEmail": "contact@specific.org"
        }
    }
    
    mock_client.execute_query.return_value = mock_response
    
    result = org_operations.get_organization_by_id("org123")
    
    # Verify the query was called
    mock_client.execute_query.assert_called_once()
    call_args = mock_client.execute_query.call_args
    
    # Check query content
    query = call_args[0][0]
    assert "organizationForAI" in query
    assert "$orgId: ID!" in query
    
    # Check variables
    variables = call_args[0][1]
    assert variables == {"orgId": "org123"}
    
    # Check result
    assert result == mock_response["organizationForAI"]
    assert result["id"] == "org123"
    assert result["name"] == "Specific Organization"
    assert len(result["sites"]) == 1


def test_get_organization_by_id_not_found(org_operations, mock_client):
    """Test fetching a non-existent organization by ID."""
    mock_client.execute_query.return_value = {"organizationForAI": None}
    
    result = org_operations.get_organization_by_id("nonexistent")
    
    assert result is None


def test_get_organization_by_id_exception(org_operations, mock_client):
    """Test handling exception when fetching organization by ID."""
    mock_client.execute_query.side_effect = Exception("Network error")
    
    result = org_operations.get_organization_by_id("org123")
    
    assert result is None


def test_update_organization(org_operations, mock_client):
    """Test updating an organization."""
    mock_response = {
        "updateOrganizationFromAI": {
            "id": "org123",
            "name": "Updated Organization",
            "updatedAt": "2024-01-01T12:00:00Z"
        }
    }
    
    mock_client.execute_query.return_value = mock_response
    
    update_data = {
        "name": "Updated Organization",
        "publicEmail": "updated@org.com",
        "description": "Updated description"
    }
    
    result = org_operations.update_organization("org123", update_data)
    
    # Verify the mutation was called
    mock_client.execute_query.assert_called_once()
    call_args = mock_client.execute_query.call_args
    
    # Check mutation content
    mutation = call_args[0][0]
    assert "updateOrganizationFromAI" in mutation
    assert "$organizationId: String!" in mutation
    assert "$input: organizationInputUpdate!" in mutation
    
    # Check variables
    variables = call_args[0][1]
    assert variables["organizationId"] == "org123"
    assert variables["input"] == update_data
    
    # Check result
    assert result == mock_response
    assert result["updateOrganizationFromAI"]["id"] == "org123"
    assert result["updateOrganizationFromAI"]["name"] == "Updated Organization"


def test_get_organizations_for_ai_empty_response(org_operations, mock_client):
    """Test handling empty response from organizationsForAI query."""
    mock_client.execute_query.return_value = {}
    
    result = org_operations.get_organizations_for_ai()
    
    assert result == []


def test_query_contains_all_expected_fields(org_operations, mock_client):
    """Test that the organizationsForAI query contains all expected fields."""
    mock_client.execute_query.return_value = {"organizationsForAI": []}
    
    org_operations.get_organizations_for_ai()
    
    call_args = mock_client.execute_query.call_args
    query = call_args[0][0]
    
    # Check for essential fields
    expected_fields = [
        "id", "sites", "name", "streetAddress", "addressLine2", "city", "state", "zip",
        "publicEmail", "publicPhone", "email", "phone", "isFeedingAmericaAffiliate",
        "description", "ein", "banner", "logo", "updatedAt", "createdAt"
    ]
    
    for field in expected_fields:
        assert field in query, f"Field '{field}' missing from query"