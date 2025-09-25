#!/usr/bin/env python3
"""
Simple connectivity test for Tackle Hunger volunteers.
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


def main():
    """Run simple connectivity tests."""
    print("🌐 Testing connectivity for Tackle Hunger...")
    print("=" * 40)

    # Core endpoints volunteers need
    tests = [
        ("https://devapi.sboc.us/graphql", "Tackle Hunger Dev API"),
        ("https://pypi.org/simple/requests/", "Python Package Index"),
        ("https://github.com", "GitHub")
    ]

    passed = 0
    for url, name in tests:
        if test_endpoint(url, name):
            passed += 1

    print("=" * 40)
    print(f"Results: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All connectivity tests passed!")
        print("You're ready to validate charities!")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check your network connection.")
        print("Ask your team lead if you need help with firewall settings.")
        sys.exit(1)


if __name__ == "__main__":
    main()
