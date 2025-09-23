#!/usr/bin/env python3
"""
Example script to run the siteForAI query as requested.

This script demonstrates how to:
1. Execute the exact query: query { siteForAI(siteId: 455) { name } }
2. Use the convenient method to get site name
3. Get full site data for a specific site ID
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations


def main():
    """Demonstrate GraphQL query execution for siteForAI."""
    try:
        # Initialize client and operations
        client = TackleHungerClient()
        site_ops = SiteOperations(client)
        
        # Site ID as requested in the issue
        site_id = 455
        
        print(f"🔍 Querying site data for site ID: {site_id}")
        print("=" * 50)
        
        # Method 1: Get just the name (matches exact query requested)
        print("\n📝 Method 1: Get site name only")
        try:
            site_name = site_ops.get_site_name_for_ai(site_id)
            if site_name:
                print(f"Site Name: {site_name}")
            else:
                print(f"No site found with ID {site_id}")
        except Exception as e:
            print(f"Error fetching site name: {e}")
        
        # Method 2: Get full site data
        print("\n📊 Method 2: Get full site data")
        try:
            site_data = site_ops.get_site_for_ai(site_id)
            if site_data:
                print("Site Data:")
                for key, value in site_data.items():
                    print(f"  {key}: {value}")
            else:
                print(f"No site found with ID {site_id}")
        except Exception as e:
            print(f"Error fetching site data: {e}")
        
        # Method 3: Raw query execution (most flexible)
        print("\n⚡ Method 3: Raw GraphQL query execution")
        try:
            query = '''
            query {
                siteForAI(siteId: 455) {
                    name
                }
            }
            '''
            result = client.execute_query(query)
            print("Raw Query Result:")
            print(result)
        except Exception as e:
            print(f"Error executing raw query: {e}")

    except Exception as e:
        print(f"❌ Error initializing client: {e}")
        print("💡 Make sure you have:")
        print("   1. Set up your .env file with AI_SCRAPING_TOKEN")
        print("   2. Network access to the GraphQL endpoint")
        sys.exit(1)


if __name__ == "__main__":
    main()