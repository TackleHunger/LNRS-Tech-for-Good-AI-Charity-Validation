#!/usr/bin/env python3
"""
Data exploration script for Tackle Hunger charity validation.

This script analyzes organizations and sites to identify missing data elements
and generates comprehensive reports.
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.data_explorer import DataExplorer


def setup_environment():
    """Set up environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return True
    except ImportError:
        print("Warning: python-dotenv not available. Make sure environment variables are set manually.")
        return True


def validate_environment():
    """Validate that required environment variables are set."""
    required_vars = ["AI_SCRAPING_TOKEN", "TKH_GRAPHQL_API_URL"]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please update your .env file with the required values")
        return False
    
    return True


def print_summary_report(summary):
    """Print a formatted summary report to console."""
    print("\n" + "="*80)
    print("TACKLE HUNGER DATA EXPLORATION SUMMARY")
    print("="*80)
    
    # Basic stats
    basic_stats = summary.get('summary', {})
    print(f"\nData Overview:")
    print(f"  • Total Sites: {basic_stats.get('total_sites', 0)}")
    print(f"  • Total Organizations: {basic_stats.get('total_organizations', 0)}")
    print(f"  • Analysis Timestamp: {basic_stats.get('timestamp', 'Unknown')}")
    
    # Completeness scores
    site_comp = summary.get('site_completeness', {})
    org_comp = summary.get('organization_completeness', {})
    
    print(f"\nData Completeness Scores:")
    print(f"  • Sites: {site_comp.get('score', 0)}/100 (Grade: {site_comp.get('grade', 'N/A')})")
    print(f"    - Critical fields: {site_comp.get('critical_score', 0)}/100")
    print(f"    - Optional fields: {site_comp.get('optional_score', 0)}/100")
    print(f"  • Organizations: {org_comp.get('score', 0)}/100 (Grade: {org_comp.get('grade', 'N/A')})")
    print(f"    - Critical fields: {org_comp.get('critical_score', 0)}/100")
    print(f"    - Optional fields: {org_comp.get('optional_score', 0)}/100")
    
    # Data integrity
    combined = summary.get('combined_insights', {})
    orphaned = combined.get('orphaned_sites', {})
    incomplete = combined.get('sites_with_incomplete_organizations', {})
    
    print(f"\nData Integrity Issues:")
    print(f"  • Orphaned Sites: {orphaned.get('count', 0)} ({orphaned.get('percentage', 0)}%)")
    print(f"  • Sites w/ Incomplete Organizations: {incomplete.get('count', 0)} ({incomplete.get('percentage', 0)}%)")
    
    # Recommendations
    recommendations = summary.get('recommendations', [])
    if recommendations:
        print(f"\nKey Recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):  # Show top 5
            print(f"  {i}. {rec}")
    
    print("\n" + "="*80)


def main():
    """Main exploration function."""
    parser = argparse.ArgumentParser(description="Explore Tackle Hunger charity data for missing elements")
    parser.add_argument(
        "--sites", type=int, default=100,
        help="Number of sites to analyze (default: 100)"
    )
    parser.add_argument(
        "--organizations", type=int, default=100,
        help="Number of organizations to analyze (default: 100)"
    )
    parser.add_argument(
        "--output", type=str,
        help="Output file for detailed JSON report (optional)"
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Show only summary report (faster)"
    )
    parser.add_argument(
        "--environment", type=str, default="dev",
        choices=["dev", "staging", "production"],
        help="Environment to connect to (default: dev)"
    )
    
    args = parser.parse_args()
    
    print("Tackle Hunger Data Exploration Tool")
    print("="*50)
    
    # Setup environment
    if not setup_environment():
        return 1
    
    if not validate_environment():
        return 1
    
    try:
        # Initialize client
        print(f"\nConnecting to {args.environment} environment...")
        
        # Set environment variable for the client
        os.environ["ENVIRONMENT"] = args.environment
        
        client = TackleHungerClient()
        explorer = DataExplorer(client)
        
        print(f"Analyzing up to {args.sites} sites and {args.organizations} organizations...")
        
        if args.summary_only:
            # Get just the summary
            summary = explorer.get_data_completeness_summary(
                site_limit=args.sites,
                org_limit=args.organizations
            )
            print_summary_report(summary)
        else:
            # Get full analysis
            analysis = explorer.get_missing_data_analysis(
                site_limit=args.sites,
                org_limit=args.organizations
            )
            
            # Print summary
            summary = explorer.get_data_completeness_summary(
                site_limit=args.sites,
                org_limit=args.organizations
            )
            print_summary_report(summary)
            
            # Export detailed report if requested
            if args.output:
                print(f"\nExporting detailed analysis to {args.output}...")
                with open(args.output, 'w') as f:
                    json.dump(analysis, f, indent=2)
                print(f"✓ Detailed report saved to {args.output}")
        
        print(f"\nData exploration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\nError during data exploration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())