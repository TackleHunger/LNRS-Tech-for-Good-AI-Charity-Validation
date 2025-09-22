#!/usr/bin/env python3
"""
Connectivity test script for Tackle Hunger development environment.

Tests network access to required APIs and services.
"""

import requests
import sys
from urllib.parse import urlparse


REQUIRED_ENDPOINTS = [
    "https://devapi.sboc.us/graphql",
    "https://pypi.org/simple/requests/",
    "https://github.com",
    "https://api.github.com"
]


def check_endpoint(url: str, timeout: int = 10) -> bool:
    """Test connectivity to a single endpoint."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc

        print(f"Testing {host}...", end=" ")

        response = requests.get(url, timeout=timeout, allow_redirects=True)

        if response.status_code < 400:
            print("✓ OK")
            return True
        else:
            print(f"⚠ HTTP {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        print("⚠ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("✗ Connection Error")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run connectivity tests."""
    print("Testing connectivity to required endpoints...")
    print("=" * 50)

    success_count = 0
    total_count = len(REQUIRED_ENDPOINTS)

    for endpoint in REQUIRED_ENDPOINTS:
        if check_endpoint(endpoint):
            success_count += 1

    print("=" * 50)
    print(f"Results: {success_count}/{total_count} endpoints accessible")

    if success_count == total_count:
        print("✓ All connectivity tests passed!")
        sys.exit(0)
    else:
        print("⚠ Some endpoints are not accessible.")
        print("Please check your firewall configuration or network settings.")
        sys.exit(1)


if __name__ == "__main__":
    main()
