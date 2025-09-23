#!/usr/bin/env python3
"""
Example: Data exploration for missing charity information.

This example demonstrates how to use the data exploration functionality
to identify charities and organizations with missing data elements.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tackle_hunger import TackleHungerClient, DataExplorer


def main():
    """Demonstrate data exploration functionality."""
    
    print("Tackle Hunger Data Exploration Example")
    print("=" * 50)
    
    # Note: This example requires valid API credentials
    if not os.getenv("AI_SCRAPING_TOKEN"):
        print("\nNote: This example requires API credentials to run.")
        print("Set AI_SCRAPING_TOKEN and TKH_GRAPHQL_API_URL environment variables.")
        print("\nShowing example output structure instead...")
        show_example_output()
        return
    
    try:
        # Initialize client and explorer
        client = TackleHungerClient()
        explorer = DataExplorer(client)
        
        print("\nConnecting to Tackle Hunger API...")
        
        # Get summary analysis
        print("Fetching data completeness summary...")
        summary = explorer.get_data_completeness_summary(site_limit=10, org_limit=10)
        
        # Display results
        print_summary(summary)
        
        # Demonstrate detailed analysis
        print("\nFetching detailed missing data analysis...")
        analysis = explorer.get_missing_data_analysis(site_limit=10, org_limit=10)
        
        print_detailed_insights(analysis)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("This is expected if API credentials are not configured.")
        show_example_output()


def print_summary(summary):
    """Print summary analysis results."""
    print("\n" + "="*50)
    print("DATA COMPLETENESS SUMMARY")
    print("="*50)
    
    # Basic stats
    basic_stats = summary.get('summary', {})
    print(f"\nAnalyzed Data:")
    print(f"  • Sites: {basic_stats.get('total_sites', 0)}")
    print(f"  • Organizations: {basic_stats.get('total_organizations', 0)}")
    
    # Completeness scores
    site_comp = summary.get('site_completeness', {})
    org_comp = summary.get('organization_completeness', {})
    
    print(f"\nCompleteness Scores:")
    print(f"  • Sites: {site_comp.get('score', 0):.1f}/100 (Grade: {site_comp.get('grade', 'N/A')})")
    print(f"  • Organizations: {org_comp.get('score', 0):.1f}/100 (Grade: {org_comp.get('grade', 'N/A')})")
    
    # Recommendations
    recommendations = summary.get('recommendations', [])
    if recommendations:
        print(f"\nTop Recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"  {i}. {rec}")


def print_detailed_insights(analysis):
    """Print detailed analysis insights."""
    print("\n" + "="*50)
    print("DETAILED ANALYSIS INSIGHTS")
    print("="*50)
    
    # Sites with missing critical data
    sites_analysis = analysis.get('sites', {})
    sites_missing = sites_analysis.get('sites_with_critical_missing', [])
    
    if sites_missing:
        print(f"\nSites with Critical Missing Data ({len(sites_missing)} found):")
        for site in sites_missing[:3]:  # Show first 3
            print(f"  • {site.get('name', 'Unknown')} (ID: {site.get('id')})")
            print(f"    Missing: {', '.join(site.get('missing_fields', []))}")
    
    # Organizations with missing critical data
    orgs_analysis = analysis.get('organizations', {})
    orgs_missing = orgs_analysis.get('organizations_with_critical_missing', [])
    
    if orgs_missing:
        print(f"\nOrganizations with Critical Missing Data ({len(orgs_missing)} found):")
        for org in orgs_missing[:3]:  # Show first 3
            print(f"  • {org.get('name', 'Unknown')} (ID: {org.get('id')})")
            print(f"    Missing: {', '.join(org.get('missing_fields', []))}")
    
    # Data integrity issues
    combined = analysis.get('combined', {})
    orphaned = combined.get('orphaned_sites', {})
    
    if orphaned.get('count', 0) > 0:
        print(f"\nData Integrity Issues:")
        print(f"  • {orphaned.get('count')} orphaned sites found")


def show_example_output():
    """Show example output when API is not available."""
    print("\n" + "="*50)
    print("EXAMPLE OUTPUT (API not available)")
    print("="*50)
    
    print("""
Data Overview:
  • Total Sites: 150
  • Total Organizations: 75
  • Analysis Timestamp: 2024-12-19T10:30:00

Data Completeness Scores:
  • Sites: 78.5/100 (Grade: C)
    - Critical fields: 85.2/100
    - Optional fields: 65.8/100
  • Organizations: 82.1/100 (Grade: B)
    - Critical fields: 88.4/100
    - Optional fields: 70.3/100

Data Integrity Issues:
  • Orphaned Sites: 3 (2.0%)
  • Sites w/ Incomplete Organizations: 12 (8.0%)

Key Recommendations:
  1. Priority: 25% of sites missing critical field 'publicEmail'
  2. Priority: 18% of organizations missing critical field 'streetAddress'
  3. Data integrity issue: 3 sites have missing or invalid organization references
""")
    
    print("\nExample Missing Data Fields:")
    print("  Sites commonly missing:")
    print("    • publicEmail (25% missing)")
    print("    • website (35% missing)")
    print("    • description (40% missing)")
    print("  ")
    print("  Organizations commonly missing:")
    print("    • streetAddress (18% missing)")
    print("    • publicPhone (22% missing)")
    print("    • ein (45% missing)")


if __name__ == "__main__":
    main()