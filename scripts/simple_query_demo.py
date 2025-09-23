#!/usr/bin/env python3
"""
Simple demonstration of the exact GraphQL query requested:
query { siteForAI(siteId: 455) { name } }
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations


def main():
    """Execute the exact query requested in the issue."""
    
    print("🎯 Executing the requested GraphQL query:")
    print("query { siteForAI(siteId: 455) { name } }")
    print("=" * 50)
    
    try:
        # Initialize the client
        client = TackleHungerClient()
        site_ops = SiteOperations(client)
        
        # Execute the exact query requested (ID 455)
        site_name = site_ops.get_site_name_for_ai(455)
        
        if site_name:
            print(f"✅ Success! Site name: {site_name}")
        else:
            print("❌ Site not found or name is empty")
            
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        if "Site not found" in str(e):
            print("💡 This is expected if site ID 455 doesn't exist in the current environment")
        else:
            print("💡 Check your .env configuration and network connectivity")


def show_usage_examples():
    """Show different ways to use the new functionality."""
    print("\n🛠️ Usage Examples:")
    print("=" * 50)
    
    print("\n1. Get site name only:")
    print("   site_name = site_ops.get_site_name_for_ai(455)")
    
    print("\n2. Get full site data:")
    print("   site_data = site_ops.get_site_for_ai(455)")
    
    print("\n3. Raw GraphQL query:")
    print("   query = 'query { siteForAI(siteId: 455) { name } }'")
    print("   result = client.execute_query(query)")


if __name__ == "__main__":
    main()
    show_usage_examples()