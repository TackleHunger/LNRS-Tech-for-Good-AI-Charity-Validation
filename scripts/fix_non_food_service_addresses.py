#!/usr/bin/env python3
"""
Fix Non-Food-Service Addresses Script

This script identifies and fixes non-food-service addresses (like PO boxes)
in charity Sites by moving them to the parent Organization and updating
the Site with a physical address if available.

Usage:
    python scripts/fix_non_food_service_addresses.py [--limit 50] [--dry-run]
"""

import sys
import os
import logging
import argparse
from typing import Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('address_fixes.log')
        ]
    )


def validate_environment() -> bool:
    """Validate that required environment variables are set."""
    required_vars = ['AI_SCRAPING_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file or environment.")
        return False
    
    return True


def main():
    """Main script function."""
    parser = argparse.ArgumentParser(
        description="Fix non-food-service addresses in charity Sites"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of sites to process (default: 50)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze sites but do not make any changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Validate environment
    if not validate_environment():
        return 1
    
    try:
        # Initialize client and operations
        logger.info("Initializing Tackle Hunger client...")
        client = TackleHungerClient()
        site_ops = SiteOperations(client)
        
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no changes will be made")
            
            # Fetch and analyze sites
            sites = site_ops.get_sites_for_ai(limit=args.limit)
            logger.info(f"Fetched {len(sites)} sites for analysis")
            
            # Analyze addresses
            fixes = site_ops.analyze_site_addresses(sites)
            logger.info(f"Identified {len(fixes)} sites requiring address fixes")
            
            # Display results
            if fixes:
                print("\nSites requiring address fixes:")
                print("=" * 60)
                for i, fix in enumerate(fixes, 1):
                    print(f"{i}. Site: {fix.site_name} (ID: {fix.site_id})")
                    print(f"   Current Address: {fix.original_address}")
                    print(f"   Action: {fix.action}")
                    print(f"   Reason: {fix.reason}")
                    print(f"   Organization ID: {fix.organization_id}")
                    if fix.new_org_address:
                        print(f"   New Org Address: {fix.new_org_address}")
                    print()
            else:
                print("\nNo sites requiring address fixes found.")
            
        else:
            # Actually perform the fixes
            logger.info(f"Starting to fix non-food-service addresses for up to {args.limit} sites")
            sites_processed, fixes_applied = site_ops.fix_non_food_service_addresses(limit=args.limit)
            
            print(f"\nCompleted address fix operation:")
            print(f"Sites processed: {sites_processed}")
            print(f"Fixes applied: {fixes_applied}")
            
            if fixes_applied > 0:
                print(f"\nSuccessfully fixed {fixes_applied} sites with non-food-service addresses.")
                print("Check the log file 'address_fixes.log' for detailed information.")
            else:
                print("\nNo address fixes were needed or applied.")
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    sys.exit(main())