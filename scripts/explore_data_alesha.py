#!/usr/bin/env python3
"""
Data exploration script for Alesha - Explore missing data in organizations and charities.

This script analyzes the GraphQL data to identify organizations and charities 
that are missing essential data elements.
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tackle_hunger.graphql_client import TackleHungerClient, TackleHungerConfig
from tackle_hunger.data_explorer import DataExplorer


def setup_environment():
    """Setup environment variables from .env file if available."""
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"✓ Loaded environment from {env_file}")
        else:
            print("⚠ No .env file found, using defaults/environment variables")
    except ImportError:
        print("⚠ python-dotenv not available, relying on environment variables")


def main():
    """Main exploration function."""
    parser = argparse.ArgumentParser(
        description="Explore Tackle Hunger data to identify missing elements"
    )
    parser.add_argument(
        "--sites-limit", 
        type=int, 
        default=50,
        help="Number of sites to analyze (default: 50)"
    )
    parser.add_argument(
        "--orgs-limit", 
        type=int, 
        default=50,
        help="Number of organizations to analyze (default: 50)"
    )
    parser.add_argument(
        "--output-file", 
        type=str,
        help="Output file for detailed JSON report (optional)"
    )
    parser.add_argument(
        "--environment",
        type=str,
        choices=["dev", "staging", "production"],
        default="dev",
        help="GraphQL API environment to use (default: dev)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Show only summary (don't save detailed report)"
    )
    
    args = parser.parse_args()
    
    print("Tackle Hunger Data Exploration - Missing Data Analysis")
    print("=" * 60)
    
    # Setup environment
    setup_environment()
    
    # Configure client
    try:
        config = TackleHungerConfig(environment=args.environment)
        client = TackleHungerClient(config)
        print(f"✓ Connected to {args.environment} environment: {config.graphql_endpoint}")
    except Exception as e:
        print(f"✗ Failed to create GraphQL client: {e}")
        print("\nPlease ensure you have:")
        print("1. Set AI_SCRAPING_TOKEN in your environment or .env file")
        print("2. Valid network access to the GraphQL endpoint")
        return 1
    
    # Create data explorer
    explorer = DataExplorer(client)
    
    try:
        # Generate comprehensive report
        print(f"\nAnalyzing up to {args.sites_limit} sites and {args.orgs_limit} organizations...")
        report = explorer.generate_comprehensive_report(
            sites_limit=args.sites_limit,
            orgs_limit=args.orgs_limit
        )
        
        # Print summary
        explorer.print_summary(report)
        
        # Save detailed report if requested
        if not args.summary_only:
            output_file = args.output_file
            saved_file = explorer.save_report(report, output_file)
            print(f"\n✓ Detailed report saved to: {saved_file}")
            
            # Show most problematic entries
            print("\nMOST PROBLEMATIC SITES (Top 5):")
            for i, site in enumerate(report['sites_analysis']['most_problematic_sites'][:5], 1):
                print(f"{i}. {site['name']} (ID: {site['site_id']})")
                print(f"   Completeness: {site['completeness_score']}, Missing: {site['total_missing']} fields")
                if site['missing_essential']:
                    print(f"   Essential missing: {', '.join(site['missing_essential'])}")
            
            print("\nMOST PROBLEMATIC ORGANIZATIONS (Top 5):")
            for i, org in enumerate(report['organizations_analysis']['most_problematic_organizations'][:5], 1):
                print(f"{i}. {org['name']} (ID: {org['org_id']})")
                print(f"   Completeness: {org['completeness_score']}, Missing: {org['total_missing']} fields")
                print(f"   Sites: {org['site_count']}")
                if org['missing_essential']:
                    print(f"   Essential missing: {', '.join(org['missing_essential'])}")
        
        print(f"\n✓ Data exploration completed successfully!")
        print(f"Analyzed {report['executive_summary']['total_entities_analyzed']} total entities")
        print(f"Found {report['executive_summary']['total_with_essential_data_gaps']} entities with essential data gaps")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error during data exploration: {e}")
        print("\nThis might be due to:")
        print("1. Network connectivity issues")
        print("2. Invalid API credentials") 
        print("3. GraphQL schema changes")
        print("4. API rate limiting")
        return 1


if __name__ == "__main__":
    sys.exit(main())