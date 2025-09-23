"""
Tests for data exploration functionality.
"""

import pytest
from unittest.mock import Mock, patch
from src.tackle_hunger.data_explorer import DataExplorer
from src.tackle_hunger.graphql_client import TackleHungerClient


@pytest.fixture
def mock_client():
    """Mock GraphQL client."""
    return Mock(spec=TackleHungerClient)


@pytest.fixture
def sample_sites():
    """Sample sites data for testing."""
    return [
        {
            "id": "site1",
            "organizationId": "org1",
            "name": "Complete Site",
            "streetAddress": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
            "publicEmail": "info@charity1.org",
            "publicPhone": "555-1234",
            "website": "https://charity1.org",
            "description": "Full service food bank",
            "serviceArea": "City-wide",
            "acceptsFoodDonations": True,
            "ein": "12-3456789"
        },
        {
            "id": "site2",
            "organizationId": "org2",
            "name": "Incomplete Site",
            "streetAddress": "456 Oak Ave",
            "city": "Somewhere",
            "state": "TX",
            "zip": "67890",
            "publicEmail": None,  # Missing
            "publicPhone": "",    # Empty
            "website": None,      # Missing
            "description": "",    # Empty
            "serviceArea": None,
            "acceptsFoodDonations": None,
            "ein": None
        }
    ]


@pytest.fixture
def sample_organizations():
    """Sample organizations data for testing."""
    return [
        {
            "id": "org1",
            "name": "Complete Organization",
            "streetAddress": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
            "publicEmail": "contact@charity1.org",
            "publicPhone": "555-1234",
            "email": "admin@charity1.org",
            "phone": "555-5678",
            "website": "https://charity1.org",
            "description": "Complete charity organization",
            "ein": "12-3456789",
            "nonProfitStatus": "501c3",
            "sites": [{"id": "site1"}]
        },
        {
            "id": "org2",
            "name": "Incomplete Organization",
            "streetAddress": None,  # Missing
            "city": "",            # Empty
            "state": None,         # Missing
            "zip": "",             # Empty
            "publicEmail": None,   # Missing
            "publicPhone": "",     # Empty
            "email": None,
            "phone": None,
            "website": None,
            "description": None,
            "ein": None,
            "nonProfitStatus": None,
            "sites": [{"id": "site2"}]
        }
    ]


def test_data_explorer_init(mock_client):
    """Test DataExplorer initialization."""
    explorer = DataExplorer(mock_client)
    assert explorer.client == mock_client
    assert explorer.site_ops is not None
    assert explorer.org_ops is not None


@patch('src.tackle_hunger.data_explorer.SiteOperations')
@patch('src.tackle_hunger.data_explorer.OrganizationOperations')
def test_get_missing_data_analysis(mock_org_ops, mock_site_ops, mock_client, sample_sites, sample_organizations):
    """Test comprehensive missing data analysis."""
    # Setup mocks
    mock_site_ops.return_value.get_sites_for_ai.return_value = sample_sites
    mock_org_ops.return_value.get_organizations_for_ai.return_value = sample_organizations
    
    explorer = DataExplorer(mock_client)
    result = explorer.get_missing_data_analysis(site_limit=10, org_limit=10)
    
    # Check structure
    assert "summary" in result
    assert "sites" in result
    assert "organizations" in result
    assert "combined" in result
    
    # Check summary
    assert result["summary"]["total_sites"] == 2
    assert result["summary"]["total_organizations"] == 2
    
    # Check sites analysis
    sites_analysis = result["sites"]
    assert sites_analysis["total_sites"] == 2
    assert "field_statistics" in sites_analysis
    assert "sites_with_critical_missing" in sites_analysis


def test_analyze_missing_site_data(mock_client, sample_sites):
    """Test site data analysis."""
    explorer = DataExplorer(mock_client)
    result = explorer._analyze_missing_site_data(sample_sites)
    
    assert result["total_sites"] == 2
    assert "field_statistics" in result
    
    # Check field statistics
    stats = result["field_statistics"]
    
    # publicEmail should show 50% missing (1 out of 2 sites)
    assert stats["publicEmail"]["missing_count"] == 1
    assert stats["publicEmail"]["missing_percentage"] == 50.0
    assert stats["publicEmail"]["is_critical"] == True
    
    # name should show 0% missing (both sites have names)
    assert stats["name"]["missing_count"] == 0
    assert stats["name"]["missing_percentage"] == 0.0


def test_analyze_missing_organization_data(mock_client, sample_organizations):
    """Test organization data analysis."""
    explorer = DataExplorer(mock_client)
    result = explorer._analyze_missing_organization_data(sample_organizations)
    
    assert result["total_organizations"] == 2
    assert "field_statistics" in result
    
    # Check field statistics
    stats = result["field_statistics"]
    
    # streetAddress should show 50% missing (1 out of 2 orgs)
    assert stats["streetAddress"]["missing_count"] == 1
    assert stats["streetAddress"]["missing_percentage"] == 50.0
    assert stats["streetAddress"]["is_critical"] == True


def test_analyze_combined_missing_data(mock_client, sample_sites, sample_organizations):
    """Test combined data analysis."""
    explorer = DataExplorer(mock_client)
    result = explorer._analyze_combined_missing_data(sample_sites, sample_organizations)
    
    assert "orphaned_sites" in result
    assert "sites_with_incomplete_organizations" in result
    assert "data_integrity" in result
    
    # Check data integrity stats
    integrity = result["data_integrity"]
    assert integrity["total_sites"] == 2
    assert integrity["total_organizations"] == 2
    assert integrity["sites_per_org_ratio"] == 1.0


def test_is_missing_value(mock_client):
    """Test missing value detection."""
    explorer = DataExplorer(mock_client)
    
    # Test various missing values
    assert explorer._is_missing_value(None) == True
    assert explorer._is_missing_value("") == True
    assert explorer._is_missing_value("null") == True
    assert explorer._is_missing_value("   ") == True
    
    # Test non-missing values
    assert explorer._is_missing_value("valid") == False
    assert explorer._is_missing_value("0") == False
    assert explorer._is_missing_value(0) == False
    assert explorer._is_missing_value(False) == False


def test_calculate_completeness_score(mock_client):
    """Test completeness score calculation."""
    explorer = DataExplorer(mock_client)
    
    # Mock field statistics
    field_stats = {
        "critical_field1": {"missing_percentage": 10, "is_critical": True},
        "critical_field2": {"missing_percentage": 20, "is_critical": True},
        "optional_field1": {"missing_percentage": 30, "is_critical": False},
        "optional_field2": {"missing_percentage": 40, "is_critical": False}
    }
    
    result = explorer._calculate_completeness_score(field_stats)
    
    assert "score" in result
    assert "grade" in result
    assert "critical_score" in result
    assert "optional_score" in result
    
    # Critical score should be 85% (100 - 15% average missing)
    assert result["critical_score"] == 85.0
    
    # Optional score should be 65% (100 - 35% average missing)  
    assert result["optional_score"] == 65.0
    
    # Overall score should be weighted average: 85*0.7 + 65*0.3 = 79%
    expected_score = 85 * 0.7 + 65 * 0.3
    assert result["score"] == expected_score


def test_generate_recommendations(mock_client):
    """Test recommendation generation."""
    explorer = DataExplorer(mock_client)
    
    # Mock analysis with issues
    analysis = {
        "sites": {
            "field_statistics": {
                "name": {"missing_percentage": 25, "is_critical": True},
                "description": {"missing_percentage": 10, "is_critical": False}
            }
        },
        "organizations": {
            "field_statistics": {
                "streetAddress": {"missing_percentage": 30, "is_critical": True}
            }
        },
        "combined": {
            "orphaned_sites": {"count": 5},
            "sites_with_incomplete_organizations": {"count": 3}
        }
    }
    
    recommendations = explorer._generate_recommendations(analysis)
    
    assert len(recommendations) > 0
    assert any("25%" in rec and "name" in rec for rec in recommendations)
    assert any("30%" in rec and "streetAddress" in rec for rec in recommendations)
    assert any("5 sites" in rec for rec in recommendations)


@patch('src.tackle_hunger.data_explorer.SiteOperations')
@patch('src.tackle_hunger.data_explorer.OrganizationOperations')
def test_export_missing_data_report(mock_org_ops, mock_site_ops, mock_client, sample_sites, sample_organizations, tmp_path):
    """Test exporting missing data report."""
    # Setup mocks
    mock_site_ops.return_value.get_sites_for_ai.return_value = sample_sites
    mock_org_ops.return_value.get_organizations_for_ai.return_value = sample_organizations
    
    explorer = DataExplorer(mock_client)
    output_file = tmp_path / "test_report.json"
    
    result = explorer.export_missing_data_report(str(output_file))
    
    assert "exported to" in result
    assert output_file.exists()
    
    # Verify file contents
    import json
    with open(output_file) as f:
        data = json.load(f)
    
    assert "summary" in data
    assert "sites" in data
    assert "organizations" in data