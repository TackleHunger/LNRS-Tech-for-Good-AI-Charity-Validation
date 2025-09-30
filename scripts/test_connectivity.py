#!/usr/bin/env python3
"""
Connectivity test script for Tackle Hunger development environment.

Tests network access to required APIs and services.
This script replaces the original test_connectivity.py with enhanced functionality.
"""

import os
import sys
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Tuple, List
from urllib.parse import urlparse

# Load environment variables if available
try:
    from dotenv import load_dotenv
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not available - using system environment only")

# Required endpoints for development
REQUIRED_ENDPOINTS: List[Tuple[str, str]] = [
    ("GraphQL API", ""),  # Will be set from environment
    ("PyPI (Python packages)", "https://pypi.org/simple/requests/"),
    ("GitHub", "https://github.com"),
    ("GitHub API", "https://api.github.com")
]

def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_success(message: str) -> None:
    """Print a success message."""
    print(f"✅ {message}")

def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"⚠️  {message}")

def print_error(message: str) -> None:
    """Print an error message."""
    print(f"❌ {message}")

def print_info(message: str) -> None:
    """Print an info message."""
    print(f"ℹ️  {message}")

async def test_http_endpoint(name: str, url: str, timeout: int = 10) -> bool:
    """Test connectivity to a simple HTTP endpoint."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        
        print(f"Testing {name} ({host})...", end=" ")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status < 400:
                    print("✅ OK")
                    return True
                else:
                    print(f"⚠️  HTTP {response.status}")
                    return False
                    
    except asyncio.TimeoutError:
        print("⚠️  Timeout")
        return False
    except aiohttp.ClientConnectorError:
        print("❌ Connection Error")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def test_graphql_api(endpoint: str, api_key: str) -> bool:
    """Test GraphQL API connectivity with authentication."""
    try:
        parsed = urlparse(endpoint)
        host = parsed.netloc
        
        print(f"Testing GraphQL API ({host})...", end=" ")
        
        # Simple test query
        test_query = """
        query TestConnection {
            __typename
        }
        """
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {"query": test_query}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if 'data' in result:
                        print("✅ OK (Authenticated)")
                        return True
                    else:
                        print(f"⚠️  Invalid response: {result}")
                        return False
                elif response.status == 401:
                    print("❌ Authentication Failed (Check API key)")
                    return False
                else:
                    print(f"⚠️  HTTP {response.status}")
                    return False
                    
    except asyncio.TimeoutError:
        print("⚠️  Timeout")
        return False
    except aiohttp.ClientConnectorError:
        print("❌ Connection Error")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_environment_variables() -> Tuple[bool, Dict[str, str]]:
    """Check if required environment variables are set."""
    print_info("Checking environment variables...")
    
    config = {
        "api_key": os.getenv("API_KEY", ""),
        "graphql_endpoint": os.getenv("GRAPHQL_ENDPOINT", "https://devapi.sboc.us/graphql"),
        "environment": os.getenv("ENVIRONMENT", "dev")
    }
    
    issues: List[str] = []
    
    if not config["api_key"] or config["api_key"] == "your_api_key_here":
        issues.append("API_KEY not set or placeholder value")
    
    if not config["graphql_endpoint"]:
        issues.append("GRAPHQL_ENDPOINT not set")
    
    if issues:
        print_error("Environment configuration issues:")
        for issue in issues:
            print(f"   • {issue}")
        print()
        print_info("To fix:")
        print("   1. Copy env.template to .env: cp env.template .env")
        print("   2. Edit .env with your API key")
        print("   3. Run this test again")
        return False, config
    
    print_success(f"Environment: {config['environment']}")
    print_success(f"GraphQL endpoint: {config['graphql_endpoint']}")
    print_success(f"API key: {'Set' if config['api_key'] else 'Missing'}")
    
    return True, config

async def run_connectivity_tests() -> bool:
    """Run all connectivity tests."""
    print_header("TACKLE HUNGER CONNECTIVITY TESTS")
    
    # Check environment variables
    env_ok, config = check_environment_variables()
    
    if not env_ok:
        return False
    
    print_header("NETWORK CONNECTIVITY TESTS")
    
    # Prepare endpoints list
    endpoints: List[Tuple[str, str]] = []
    
    # Add GraphQL API with authentication
    graphql_endpoint = config["graphql_endpoint"]
    api_key = config["api_key"]
    
    # Add other HTTP endpoints
    for name, url in REQUIRED_ENDPOINTS:
        if name == "GraphQL API":
            continue  # Handle separately
        endpoints.append((name, url))
    
    # Test HTTP endpoints
    success_count = 0
    total_count = len(endpoints) + 1  # +1 for GraphQL API
    
    for name, url in endpoints:
        if await test_http_endpoint(name, url):
            success_count += 1
    
    # Test GraphQL API with authentication
    if await test_graphql_api(graphql_endpoint, api_key):
        success_count += 1
    
    print_header("CONNECTIVITY TEST RESULTS")
    print(f"Successful connections: {success_count}/{total_count}")
    
    if success_count == total_count:
        print_success("All connectivity tests passed!")
        print_info("Your development environment is ready for charity validation work.")
        return True
    else:
        print_warning("Some connectivity tests failed.")
        print()
        print_info("Troubleshooting:")
        print("   • Check your internet connection")
        print("   • Verify firewall settings allow HTTPS traffic")
        print("   • Confirm API key is correct")
        print("   • Try running tests from a different network")
        print()
        print_info("For corporate networks:")
        print("   • Contact IT about firewall rules for external APIs")
        print("   • Check if a proxy is required")
        print("   • Verify DNS resolution works")
        return False

def main():
    """Main function."""
    try:
        success = asyncio.run(run_connectivity_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
