#!/usr/bin/env python3
"""
Export the first 10 charity sites from the sitesForAI GraphQL endpoint to a CSV file.

This script fetches charity site data from the Tackle Hunger API and exports
it to a CSV file for analysis or further processing.
"""

import csv
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations


def export_sites_to_csv(limit: int = 10, output_file: str = None) -> str:
    """
    Fetch charity sites from the GraphQL API and export to CSV.
    
    Args:
        limit: Number of records to fetch (default: 10)
        output_file: Output CSV file path (default: auto-generated)
    
    Returns:
        Path to the created CSV file
    """
    print(f"🔄 Fetching first {limit} charity sites from sitesForAI endpoint...")
    
    try:
        # Initialize the GraphQL client and site operations
        client = TackleHungerClient()
        site_ops = SiteOperations(client)
        
        # Fetch the sites data
        sites = site_ops.get_sites_for_ai(limit=limit)
        
        if not sites:
            print("⚠️  No sites data retrieved from the API")
            return None
        
        print(f"✅ Successfully retrieved {len(sites)} sites")
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"sites_for_ai_{timestamp}.csv"
        
        # Ensure output directory exists
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to CSV file
        write_sites_to_csv(sites, str(output_path))
        
        print(f"✅ Successfully exported {len(sites)} sites to {output_path}")
        print(f"📄 CSV file created: {output_path.absolute()}")
        
        return str(output_path)
        
    except Exception as e:
        error_message = str(e)
        print(f"❌ Error fetching or exporting sites: {error_message}")
        
        # Provide helpful guidance based on the error type
        if "ai-scraping-token" in error_message or "authentication" in error_message.lower():
            print("💡 This appears to be an authentication issue.")
            print("   Please ensure you have valid API credentials in your .env file.")
            print("   Contact your team lead for the AI_SCRAPING_TOKEN value.")
        elif "Unknown argument" in error_message or "validation" in error_message.lower():
            print("💡 This appears to be a GraphQL schema issue.")
            print("   The API endpoint may be different than expected or unavailable.")
            print("   Try running the demo version: python scripts/export_sites_demo.py")
        elif "connection" in error_message.lower() or "network" in error_message.lower():
            print("💡 This appears to be a network connectivity issue.")
            print("   Check your internet connection and firewall settings.")
            print("   See docs/firewall-setup.md for configuration guidance.")
        
        raise


def write_sites_to_csv(sites: List[Dict[str, Any]], output_file: str) -> None:
    """
    Write sites data to a CSV file.
    
    Args:
        sites: List of site dictionaries from the API
        output_file: Path to the output CSV file
    """
    if not sites:
        raise ValueError("No sites data to write")
    
    # Get all possible field names from the sites data
    fieldnames = set()
    for site in sites:
        fieldnames.update(site.keys())
    
    # Sort fieldnames for consistent output
    fieldnames = sorted(fieldnames)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for site in sites:
            # Handle None values and convert to string representation
            cleaned_site = {}
            for key in fieldnames:
                value = site.get(key)
                if value is None:
                    cleaned_site[key] = ''
                else:
                    cleaned_site[key] = str(value)
            
            writer.writerow(cleaned_site)


def main():
    """Main function to run the export script."""
    print("🚀 Tackle Hunger - Export Sites to CSV")
    print("=" * 50)
    
    try:
        output_file = export_sites_to_csv(limit=10)
        
        if output_file:
            print("\n🎉 Export completed successfully!")
            print(f"📁 File location: {Path(output_file).absolute()}")
            
            # Display first few lines of the CSV for verification
            print("\n📋 First few lines of the CSV file:")
            with open(output_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 3:  # Show header + first 2 data rows
                        break
                    print(f"   {line.rstrip()}")
                if i >= 2:
                    print("   ...")
        else:
            print("\n⚠️  Export failed - no data retrieved")
            print("💡 Try running the demo version: python scripts/export_sites_demo.py")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Export failed with error: {e}")
        print("\n🔧 Troubleshooting suggestions:")
        print("   1. Check your .env file has valid API credentials")
        print("   2. Test connectivity: python scripts/test_connectivity.py")
        print("   3. Try the demo version: python scripts/export_sites_demo.py") 
        print("   4. Check firewall settings in docs/firewall-setup.md")
        sys.exit(1)


if __name__ == "__main__":
    main()