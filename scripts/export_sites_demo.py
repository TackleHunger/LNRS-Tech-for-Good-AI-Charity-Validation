#!/usr/bin/env python3
"""
Demo version of the export script with mock data.

This demonstrates the functionality when real API credentials are not available.
"""

import csv
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Mock data for demonstration
MOCK_SITES_DATA = [
    {
        'id': '123e4567-e89b-12d3-a456-426614174000',
        'organizationId': '987fcdeb-51d2-4321-9876-123456789abc', 
        'name': 'Downtown Food Bank',
        'streetAddress': '123 Main St',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62701',
        'publicEmail': 'info@downtownfoodbank.org',
        'publicPhone': '(217) 555-0123',
        'website': 'https://downtownfoodbank.org',
        'description': 'Serving families in downtown Springfield with fresh produce and pantry staples.',
        'serviceArea': 'Downtown Springfield',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '12-3456789'
    },
    {
        'id': '456e7890-e12b-34c5-d678-901234567def',
        'organizationId': '654fedcb-a987-6543-2109-876543210fed',
        'name': 'Riverside Community Pantry', 
        'streetAddress': '456 River Ave',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62702',
        'publicEmail': 'contact@riversidepantry.org',
        'publicPhone': '(217) 555-0456',
        'website': 'https://riversidepantry.org',
        'description': 'Mobile food distribution serving the riverside communities.',
        'serviceArea': 'Riverside District',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '98-7654321'
    },
    {
        'id': '789a0123-b456-78c9-d012-345678901234',
        'organizationId': '321abcdef-0987-6543-2109-fedcba987654',
        'name': 'Holy Trinity Church Food Ministry',
        'streetAddress': '789 Church St',
        'city': 'Springfield', 
        'state': 'IL',
        'zip': '62703',
        'publicEmail': 'foodministry@holytrinity.org',
        'publicPhone': '(217) 555-0789',
        'website': 'https://holytrinity.org/food-ministry',
        'description': 'Weekly food distributions and emergency assistance programs.',
        'serviceArea': 'West Springfield',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '45-6789012'
    },
    {
        'id': '012b3456-c789-01d2-e345-678901234567',
        'organizationId': '789defabc-1234-5678-9012-345678901234',
        'name': 'Springfield Mobile Meals',
        'streetAddress': '321 Service Dr',
        'city': 'Springfield',
        'state': 'IL', 
        'zip': '62704',
        'publicEmail': 'delivery@mobilemeals.org',
        'publicPhone': '(217) 555-0321',
        'website': 'https://mobilemeals.org',
        'description': 'Home delivery of meals to elderly and disabled residents.',
        'serviceArea': 'Springfield Metropolitan Area',
        'acceptsFoodDonations': 'NO',
        'status': 'ACTIVE',
        'ein': '67-8901234'
    },
    {
        'id': '345c6789-d012-34e5-f678-901234567890',
        'organizationId': '012abcdef-5678-9012-3456-789012345678',
        'name': 'Lincoln Elementary School Pantry',
        'streetAddress': '654 School Rd',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62705',
        'publicEmail': 'pantry@lincolnelem.edu',
        'publicPhone': '(217) 555-0654',
        'website': None,
        'description': 'Weekend backpack program and family food distribution.',
        'serviceArea': 'Lincoln Elementary School District',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '89-0123456'
    },
    {
        'id': '678d9012-e345-67f8-g901-234567890123',
        'organizationId': '345bcdefg-9012-3456-7890-123456789012',
        'name': 'Southside Neighborhood Center',
        'streetAddress': '987 Community Blvd',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62706',
        'publicEmail': 'info@southsidecenter.org',
        'publicPhone': '(217) 555-0987',
        'website': 'https://southsidecenter.org',
        'description': 'Comprehensive community services including food assistance and nutrition education.',
        'serviceArea': 'South Springfield',
        'acceptsFoodDonations': 'YES', 
        'status': 'PENDING',
        'ein': '01-2345678'
    },
    {
        'id': '901e2345-f678-90g1-h234-567890123456',
        'organizationId': '678cdefgh-2345-6789-0123-456789012345',
        'name': 'Veterans Support Network Food Bank',
        'streetAddress': '147 Veterans Way',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62707',
        'publicEmail': 'foodbank@veteransupport.org',
        'publicPhone': '(217) 555-0147',
        'website': 'https://veteransupport.org/food-bank',
        'description': 'Specialized food assistance program for veterans and military families.',
        'serviceArea': 'Regional Veterans Community',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '23-4567890'
    },
    {
        'id': '234f5678-g901-23h4-i567-890123456789',
        'organizationId': '901defghi-5678-9012-3456-789012345678',
        'name': 'Second Harvest Food Distribution',
        'streetAddress': '258 Distribution Center Dr',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62708',
        'publicEmail': 'operations@secondharvest.org',
        'publicPhone': '(217) 555-0258',
        'website': 'https://secondharvest.org',
        'description': 'Large-scale food recovery and distribution to partner agencies.',
        'serviceArea': 'Central Illinois',
        'acceptsFoodDonations': 'YES',
        'status': 'ACTIVE',
        'ein': '56-7890123'
    },
    {
        'id': '567g8901-h234-56i7-j890-123456789012',
        'organizationId': '234efghij-8901-2345-6789-012345678901',
        'name': 'Springfield Senior Center Meals',
        'streetAddress': '369 Elder St',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62709',
        'publicEmail': 'meals@seniorcenterspringfield.org',
        'publicPhone': '(217) 555-0369',
        'website': 'https://seniorcenterspringfield.org/meals',
        'description': 'Daily meal service and nutrition programs for seniors 60+.',
        'serviceArea': 'Springfield Senior Community',
        'acceptsFoodDonations': 'NO',
        'status': 'ACTIVE',
        'ein': '78-9012345'
    },
    {
        'id': '890h1234-i567-89j0-k123-456789012345',
        'organizationId': '567fghijk-1234-5678-9012-345678901234',
        'name': 'Fresh Start Community Garden',
        'streetAddress': '741 Garden Way',
        'city': 'Springfield',
        'state': 'IL',
        'zip': '62710',
        'publicEmail': 'harvest@freshstartgarden.org',
        'publicPhone': '(217) 555-0741',
        'website': 'https://freshstartgarden.org',
        'description': 'Community garden with fresh produce distribution and nutrition workshops.',
        'serviceArea': 'North Springfield',
        'acceptsFoodDonations': 'UNKNOWN',
        'status': 'ACTIVE',
        'ein': '90-1234567'
    }
]


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


def export_mock_sites_to_csv(limit: int = 10, output_file: str = None) -> str:
    """
    Export mock charity sites data to CSV (for demo purposes).
    
    Args:
        limit: Number of records to export (default: 10)
        output_file: Output CSV file path (default: auto-generated)
    
    Returns:
        Path to the created CSV file
    """
    print(f"📋 Using mock data - exporting first {limit} charity sites...")
    
    # Get the first 'limit' records from mock data
    sites = MOCK_SITES_DATA[:limit]
    
    print(f"✅ Retrieved {len(sites)} mock sites")
    
    # Generate output filename if not provided
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"sites_for_ai_demo_{timestamp}.csv"
    
    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to CSV file
    write_sites_to_csv(sites, str(output_path))
    
    print(f"✅ Successfully exported {len(sites)} sites to {output_path}")
    print(f"📄 CSV file created: {output_path.absolute()}")
    
    return str(output_path)


def main():
    """Main function to run the demo export."""
    print("🚀 Tackle Hunger - Export Sites to CSV (DEMO MODE)")
    print("=" * 60)
    print("📝 This demo uses mock data since API credentials are not available")
    print("")
    
    try:
        output_file = export_mock_sites_to_csv(limit=10)
        
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
                
        # Show file statistics
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"\n📊 CSV Statistics:")
        print(f"   • Total records: {len(rows)}")
        print(f"   • Total columns: {len(reader.fieldnames) if reader.fieldnames else 0}")
        print(f"   • Sample fields: {', '.join(reader.fieldnames[:5]) if reader.fieldnames else 'None'}...")
        
        print(f"\n💡 In production, this would fetch real data from: sitesForAI GraphQL endpoint")
        
    except Exception as e:
        print(f"\n❌ Export failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()