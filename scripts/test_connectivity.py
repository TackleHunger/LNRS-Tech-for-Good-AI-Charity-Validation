#!/usr/bin/env python3
"""
Connectivity test for Tackle Hunger volunteers.
Tests that you can reach the API and basic internet resources.
"""

import requests
import sys


def test_endpoint(url: str, name: str) -> bool:
    """Test connectivity to an endpoint."""
    try:
        print(f"Testing {name}...", end=" ")
        response = requests.get(url, timeout=10)
        
        if response.status_code < 400:
            print("✅ OK")
            return True
        else:
            print(f"⚠️ HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed: {str(e)[:50]}...")
        return False


def test_graphql_endpoint(url: str, name: str) -> bool:
    """Test GraphQL endpoint with proper introspection query."""
    try:
        print(f"Testing {name}...", end=" ")
        
        # Simple introspection query to test if GraphQL endpoint is working
        query = {"query": "{ __schema { queryType { name } } }"}
        response = requests.post(url, json=query, timeout=10)
        
        if response.status_code == 200:
            print("✅ OK")
            return True
        else:
            print(f"⚠️ HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed: {str(e)[:50]}...")
        return False


def main():
    """Run connectivity tests."""
    print("🌐 Testing connectivity for Tackle Hunger...")
    print("=" * 40)

    # Core endpoints volunteers need
    tests = [
        ("https://pypi.org/simple/requests/", "Python Package Index"),
        ("https://github.com", "GitHub")
    ]
    
    # GraphQL endpoints need special handling
    graphql_tests = [
        ("https://devapi.sboc.us/graphql", "Tackle Hunger Dev API")
    ]

    passed = 0
    
    # Test regular endpoints
    for url, name in tests:
        if test_endpoint(url, name):
            passed += 1
    
    # Test GraphQL endpoints
    for url, name in graphql_tests:
        if test_graphql_endpoint(url, name):
            passed += 1

    total_tests = len(tests) + len(graphql_tests)

    print("=" * 40)
    print(f"Results: {passed}/{total_tests} tests passed")

    if passed == total_tests:
        print("🎉 All connectivity tests passed!")
        print("You're ready to validate charities!")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check your network connection.")
        print("Ask your team lead if you need help with firewall settings.")
        sys.exit(1)


if __name__ == "__main__":
    main()
