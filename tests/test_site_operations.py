"""
Tests for SiteOperations functionality, specifically for single site queries.
"""

import pytest
from unittest.mock import Mock, patch
from src.tackle_hunger.site_operations import SiteOperations
from src.tackle_hunger.graphql_client import TackleHungerClient


@pytest.fixture
def mock_client():
    """Create a mock GraphQL client."""
    client = Mock(spec=TackleHungerClient)
    return client


@pytest.fixture
def site_operations(mock_client):
    """Create SiteOperations instance with mock client."""
    return SiteOperations(mock_client)


def test_get_site_for_ai_success(site_operations, mock_client):
    """Test successful single site query."""
    # Mock response data
    mock_response = {
        "siteForAI": {
            "id": "455",
            "organizationId": "123",
            "name": "Test Charity Site",
            "streetAddress": "123 Main St",
            "city": "Test City",
            "state": "CA",
            "zip": "12345",
            "publicEmail": "test@example.com",
            "publicPhone": "555-1234",
            "website": "https://example.com",
            "description": "Test charity description",
            "serviceArea": "Local community",
            "acceptsFoodDonations": True,
            "status": "ACTIVE",
            "ein": "12-3456789"
        }
    }
    
    mock_client.execute_query.return_value = mock_response
    
    # Test the method
    result = site_operations.get_site_for_ai(455)
    
    # Verify the result
    assert result is not None
    assert result["id"] == "455"
    assert result["name"] == "Test Charity Site"
    assert result["streetAddress"] == "123 Main St"
    
    # Verify the client was called correctly
    mock_client.execute_query.assert_called_once()
    call_args = mock_client.execute_query.call_args
    assert "siteForAI(siteId: $siteId)" in call_args[0][0]
    assert call_args[0][1] == {"siteId": "455"}


def test_get_site_for_ai_not_found(site_operations, mock_client):
    """Test single site query when site is not found."""
    mock_response = {"siteForAI": None}
    mock_client.execute_query.return_value = mock_response
    
    result = site_operations.get_site_for_ai(455)
    
    assert result is None


def test_get_site_name_for_ai_success(site_operations, mock_client):
    """Test successful site name query."""
    mock_response = {
        "siteForAI": {
            "name": "Test Charity Site"
        }
    }
    
    mock_client.execute_query.return_value = mock_response
    
    # Test the method
    result = site_operations.get_site_name_for_ai(455)
    
    # Verify the result
    assert result == "Test Charity Site"
    
    # Verify the client was called correctly
    mock_client.execute_query.assert_called_once()
    call_args = mock_client.execute_query.call_args
    assert "siteForAI(siteId: $siteId)" in call_args[0][0]
    assert "name" in call_args[0][0]
    assert call_args[0][1] == {"siteId": "455"}


def test_get_site_name_for_ai_not_found(site_operations, mock_client):
    """Test site name query when site is not found."""
    mock_response = {"siteForAI": None}
    mock_client.execute_query.return_value = mock_response
    
    result = site_operations.get_site_name_for_ai(455)
    
    assert result is None


def test_get_site_name_for_ai_empty_response(site_operations, mock_client):
    """Test site name query with empty GraphQL response."""
    mock_response = {}
    mock_client.execute_query.return_value = mock_response
    
    result = site_operations.get_site_name_for_ai(455)
    
    assert result is None


def test_get_sites_for_ai_existing_functionality(site_operations, mock_client):
    """Test that existing get_sites_for_ai functionality still works."""
    mock_response = {
        "sitesForAI": [
            {
                "id": "455",
                "name": "Test Site 1",
                "organizationId": "123"
            },
            {
                "id": "456", 
                "name": "Test Site 2",
                "organizationId": "124"
            }
        ]
    }
    
    mock_client.execute_query.return_value = mock_response
    
    result = site_operations.get_sites_for_ai(limit=2)
    
    assert len(result) == 2
    assert result[0]["id"] == "455"
    assert result[1]["id"] == "456"
    
    # Verify correct query was used
    call_args = mock_client.execute_query.call_args
    assert "sitesForAI(limit: $limit)" in call_args[0][0]
    assert call_args[0][1] == {"limit": 2}