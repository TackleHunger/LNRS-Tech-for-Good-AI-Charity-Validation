#!/usr/bin/env python3
"""
Demo script showing data exploration functionality with mock data.

This demonstrates the DataExplorer functionality without requiring API access.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tackle_hunger.data_explorer import DataExplorer
from unittest.mock import Mock


def create_mock_data():
    """Create realistic mock data for demonstration."""
    
    # Mock sites with varying levels of completeness
    mock_sites = [
        {
            'id': 'site1',
            'name': 'Complete Community Food Bank',
            'streetAddress': '123 Main Street',
            'city': 'Anytown',
            'state': 'CA',
            'zip': '12345',
            'publicEmail': 'info@communityfood.org',
            'publicPhone': '555-0123',
            'website': 'https://communityfood.org',
            'description': 'Serving the community since 1985 with fresh food and support.',
            'serviceArea': 'City-wide, focus on downtown area',
            'acceptsFoodDonations': 'Yes',
            'ein': '12-3456789',
            'contactEmail': 'director@communityfood.org',
            'contactName': 'Jane Smith',
            'contactPhone': '555-0124'
        },
        {
            'id': 'site2', 
            'name': 'Partial Info Food Pantry',
            'streetAddress': '456 Oak Avenue',
            'city': 'Somewhere',
            'state': 'NY',
            'zip': '54321',
            'publicEmail': '',  # Missing
            'publicPhone': '555-0456',
            'website': '',  # Missing
            'description': '',  # Missing
            'acceptsFoodDonations': 'Yes',
            # Missing many other fields
        },
        {
            'id': 'site3',
            'name': 'Minimal Data Shelter',
            'streetAddress': '789 Pine Road',
            'city': 'Elsewhere',
            'state': 'TX',
            'zip': '',  # Missing essential field
            'publicEmail': '',  # Missing essential field
            'publicPhone': '',  # Missing essential field
            # Missing most fields
        }
    ]
    
    # Mock organizations with varying completeness
    mock_orgs = [
        {
            'id': 'org1',
            'name': 'Complete Charity Organization',
            'streetAddress': '100 Charity Lane',
            'city': 'Generous City',
            'state': 'CA',
            'zip': '98765',
            'publicEmail': 'contact@charity.org',
            'publicPhone': '555-9876',
            'description': 'A well-established charity serving multiple communities.',
            'ein': '98-7654321',
            'isFeedingAmericaAffiliate': 'Yes',
            'sites': [{'id': 'site1', 'name': 'Site 1'}, {'id': 'site2', 'name': 'Site 2'}]
        },
        {
            'id': 'org2',
            'name': 'Incomplete Organization',
            'streetAddress': '',  # Missing
            'city': '',  # Missing
            'publicEmail': '',  # Missing
            'description': '',  # Missing
            'ein': '',  # Missing
            'sites': [{'id': 'site3', 'name': 'Site 3'}]
        },
        {
            'id': 'org3',
            'name': '',  # Missing essential field!
            'streetAddress': '200 Hope Street',
            'city': 'Kindness',
            'state': 'FL',
            'sites': []
        }
    ]
    
    return mock_sites, mock_orgs


def main():
    """Run the demonstration."""
    print("Data Exploration Demo - Mock Data Analysis")
    print("=" * 50)
    
    # Create mock client and explorer
    mock_client = Mock()
    
    # Create mock data
    mock_sites, mock_orgs = create_mock_data()
    
    # Create data explorer
    explorer = DataExplorer(mock_client)
    
    # Mock the data fetching methods
    explorer.site_ops.get_sites_for_ai = Mock(return_value=mock_sites)
    explorer.org_ops.get_organizations_for_ai = Mock(return_value=mock_orgs)
    
    print("Analyzing mock data...")
    print(f"Sites: {len(mock_sites)}, Organizations: {len(mock_orgs)}")
    
    # Generate analysis report
    report = explorer.generate_comprehensive_report(
        sites_limit=len(mock_sites),
        orgs_limit=len(mock_orgs)
    )
    
    # Print summary
    explorer.print_summary(report)
    
    # Show detailed findings for each entity
    print("\nDETAILED FINDINGS:")
    print("-" * 40)
    
    print("\nSite Analysis Details:")
    for analysis in report['sites_analysis']['all_site_analyses']:
        print(f"• {analysis['name']} (ID: {analysis['site_id']})")
        print(f"  Completeness Score: {analysis['completeness_score']}")
        if analysis['missing_essential']:
            print(f"  Missing Essential: {', '.join(analysis['missing_essential'])}")
        if analysis['missing_important']:
            print(f"  Missing Important: {', '.join(analysis['missing_important'])}")
        print()
    
    print("Organization Analysis Details:")
    for analysis in report['organizations_analysis']['all_organization_analyses']:
        print(f"• {analysis['name']} (ID: {analysis['org_id']})")
        print(f"  Completeness Score: {analysis['completeness_score']}")
        print(f"  Sites: {analysis['site_count']}")
        if analysis['missing_essential']:
            print(f"  Missing Essential: {', '.join(analysis['missing_essential'])}")
        if analysis['missing_important']:
            print(f"  Missing Important: {', '.join(analysis['missing_important'])}")
        print()
    
    # Save report for inspection
    filename = explorer.save_report(report, "/tmp/demo_analysis_report.json")
    print(f"\n✓ Demo completed! Full report saved to: {filename}")
    print("\nThis demonstrates how the data exploration system identifies")
    print("missing data elements in both sites and organizations.")


if __name__ == "__main__":
    main()