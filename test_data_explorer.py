#!/usr/bin/env python3
"""
Test script for the Tackle Hunger Data Explorer.
This runs a basic test to ensure all imports work and data can be loaded.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Test imports
    print("Testing imports...")
    
    from tackle_hunger.graphql_client import TackleHungerClient, TackleHungerConfig
    from tackle_hunger.site_operations import SiteOperations
    from tackle_hunger.organization_operations import OrganizationOperations
    from tackle_hunger.data_quality import (
        calculate_site_quality_score, 
        calculate_organization_quality_score,
        get_quality_grade,
        get_quality_color
    )
    
    print("✅ All imports successful!")
    
    # Test sample data generation
    print("\nTesting sample data generation...")
    
    sample_sites = [
        {
            "id": "site_1",
            "organizationId": "org_1", 
            "name": "Downtown Food Bank",
            "streetAddress": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "zip": "62701",
            "lat": 39.7817,
            "lng": -89.6501,
            "publicPhone": "(555) 123-4567",
            "publicEmail": "info@downtownfood.org",
            "website": "https://downtownfoodbank.org",
            "description": "Providing food assistance to families in need",
            "status": "ACTIVE",
            "acceptsFoodDonations": "YES"
        }
    ]
    
    # Test quality scoring
    print("Testing quality scoring...")
    quality_score = calculate_site_quality_score(sample_sites[0])
    print(f"Sample site quality score: {quality_score['overall_score']:.3f}")
    print(f"Quality grade: {get_quality_grade(quality_score['overall_score'])}")
    print(f"Quality color: {get_quality_color(quality_score['overall_score'])}")
    
    print("\n✅ All tests passed! Data Explorer should work correctly.")
    print("\nTo run the Streamlit app, use:")
    print("streamlit run data_explorer.py")
    
except Exception as e:
    print(f"❌ Test failed: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)