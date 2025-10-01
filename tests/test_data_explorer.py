"""
Tests for data exploration functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.tackle_hunger.data_explorer import DataExplorer
from src.tackle_hunger.graphql_client import TackleHungerClient


@pytest.fixture
def mock_client():
    """Create a mock GraphQL client."""
    return Mock(spec=TackleHungerClient)


@pytest.fixture
def data_explorer(mock_client):
    """Create a data explorer with mock client."""
    return DataExplorer(mock_client)


def test_analyze_site_completeness_complete_site(data_explorer):
    """Test analysis of a complete site."""
    complete_site = {
        'id': 'site1',
        'name': 'Complete Food Bank',
        'streetAddress': '123 Main St',
        'city': 'Anytown',
        'state': 'CA',
        'zip': '12345',
        'publicEmail': 'info@foodbank.org',
        'publicPhone': '555-1234',
        'website': 'https://foodbank.org',
        'description': 'A complete food bank',
        'serviceArea': 'City wide',
        'acceptsFoodDonations': 'Yes',
        'ein': '12-3456789',
        'contactEmail': 'contact@foodbank.org',
        'contactName': 'John Doe',
        'contactPhone': '555-5678'
    }
    
    result = data_explorer.analyze_site_completeness(complete_site)
    
    assert result['site_id'] == 'site1'
    assert result['name'] == 'Complete Food Bank'
    assert result['completeness_score'] == 1.0
    assert result['missing_essential'] == []
    assert result['missing_important'] == []
    assert result['has_essential_gaps'] == False
    assert result['total_missing'] == 0


def test_analyze_site_completeness_incomplete_site(data_explorer):
    """Test analysis of an incomplete site."""
    incomplete_site = {
        'id': 'site2',
        'name': 'Incomplete Food Bank',
        'streetAddress': '456 Oak Ave',
        'city': 'Somewhere',
        'state': 'NY',
        'zip': '',  # Missing zip
        'publicEmail': '',  # Missing email
        'publicPhone': '555-9999',
        # Missing many other fields
    }
    
    result = data_explorer.analyze_site_completeness(incomplete_site)
    
    assert result['site_id'] == 'site2'
    assert result['name'] == 'Incomplete Food Bank'
    assert result['completeness_score'] < 1.0
    assert 'zip' in result['missing_essential']
    assert 'publicEmail' in result['missing_essential']
    assert result['has_essential_gaps'] == True
    assert result['total_missing'] > 0


def test_analyze_organization_completeness_complete_org(data_explorer):
    """Test analysis of a complete organization."""
    complete_org = {
        'id': 'org1',
        'name': 'Complete Charity Org',
        'streetAddress': '789 Elm St',
        'city': 'Metropolis',
        'state': 'TX',
        'zip': '54321',
        'publicEmail': 'info@charity.org',
        'publicPhone': '555-0000',
        'description': 'A complete charity organization',
        'ein': '98-7654321',
        'isFeedingAmericaAffiliate': 'Yes',
        'sites': [{'id': 'site1', 'name': 'Site 1'}]
    }
    
    result = data_explorer.analyze_organization_completeness(complete_org)
    
    assert result['org_id'] == 'org1'
    assert result['name'] == 'Complete Charity Org'
    assert result['completeness_score'] == 1.0
    assert result['missing_essential'] == []
    assert result['missing_important'] == []
    assert result['has_essential_gaps'] == False
    assert result['total_missing'] == 0
    assert result['site_count'] == 1


def test_analyze_organization_completeness_missing_name(data_explorer):
    """Test analysis of an organization missing essential name field."""
    incomplete_org = {
        'id': 'org2',
        'name': '',  # Missing essential name
        'streetAddress': '321 Pine St',
        'city': 'Smalltown',
        'state': 'FL',
        'sites': []
    }
    
    result = data_explorer.analyze_organization_completeness(incomplete_org)
    
    assert result['org_id'] == 'org2'
    assert result['name'] == 'Unknown'  # Default for missing/empty name
    assert result['completeness_score'] < 1.0
    assert 'name' in result['missing_essential']
    assert result['has_essential_gaps'] == True
    assert result['site_count'] == 0


def test_field_definitions(data_explorer):
    """Test that field definitions are properly set."""
    assert 'name' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'streetAddress' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'city' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'state' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'zip' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'publicEmail' in data_explorer.ESSENTIAL_SITE_FIELDS
    assert 'publicPhone' in data_explorer.ESSENTIAL_SITE_FIELDS
    
    assert 'name' in data_explorer.ESSENTIAL_ORG_FIELDS
    
    assert 'website' in data_explorer.IMPORTANT_SITE_FIELDS
    assert 'description' in data_explorer.IMPORTANT_SITE_FIELDS
    
    assert 'description' in data_explorer.IMPORTANT_ORG_FIELDS
    assert 'ein' in data_explorer.IMPORTANT_ORG_FIELDS


def test_generate_recommendations_empty_data(data_explorer):
    """Test recommendation generation with empty data."""
    sites_analysis = {
        'summary': {'total_sites_analyzed': 0, 'percentage_with_essential_gaps': 0},
        'field_missing_counts': {}
    }
    
    orgs_analysis = {
        'summary': {'total_organizations_analyzed': 0, 'percentage_with_essential_gaps': 0},
        'field_missing_counts': {}
    }
    
    recommendations = data_explorer._generate_recommendations(sites_analysis, orgs_analysis)
    
    # Should return empty list for no data
    assert isinstance(recommendations, list)


def test_generate_recommendations_with_gaps(data_explorer):
    """Test recommendation generation with data gaps."""
    sites_analysis = {
        'summary': {'total_sites_analyzed': 100, 'percentage_with_essential_gaps': 60},
        'field_missing_counts': {'publicEmail': 50, 'website': 30}
    }
    
    orgs_analysis = {
        'summary': {'total_organizations_analyzed': 50, 'percentage_with_essential_gaps': 70},
        'field_missing_counts': {'description': 40, 'ein': 25}
    }
    
    recommendations = data_explorer._generate_recommendations(sites_analysis, orgs_analysis)
    
    assert isinstance(recommendations, list)
    assert len(recommendations) > 0
    
    # Should have recommendations for high gap percentages
    high_priority_recs = [r for r in recommendations if 'High priority' in r]
    assert len(high_priority_recs) >= 2  # Both sites and orgs have >50% gaps