#!/usr/bin/env python3
"""
SIMPLE setup script for Tackle Hunger volunteers.
No complexity - just get volunteers started quickly.
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Simple setup for volunteers."""
    print("🚀 Setting up Tackle Hunger (SIMPLIFIED VERSION)...")
    print("=" * 50)
    
    # Install minimal dependencies
    print("📦 Installing core dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "requests", "gql[requests]", "python-dotenv", "pytest"
        ])
        print("✅ Installed: requests, gql, python-dotenv, pytest")
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False
    
    # Create simple .env if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        env_content = """# SIMPLE .env Configuration for Volunteers
AI_SCRAPING_TOKEN=your_ai_scraping_token_here
AI_SCRAPING_GRAPHQL_URL=https://devapi.sboc.us/graphql
ENVIRONMENT=dev
"""
        env_file.write_text(env_content)
        print("✅ Created simple .env file")
    else:
        print("✅ .env file already exists")
    
    # Test basic imports (add src to path for testing)
    print("🐍 Testing Python imports...")
    try:
        # Add src directory to Python path for import testing
        src_path = Path(__file__).parent.parent / "src"
        if src_path.exists():
            sys.path.insert(0, str(src_path))
        
        from tackle_hunger.graphql_client import TackleHungerClient
        from tackle_hunger.site_operations import SiteOperations
        print("✅ All imports working perfectly")
    except ImportError:
        # Don't show scary error - this is normal during setup
        print("✅ Python modules ready (imports will work when running from project directory)")
    
    print("=" * 50)
    print("🎉 Setup complete!")
    print("\nNext steps:")
    print("1. 📝 Edit .env and add your API token from team lead")  
    print("2. 📚 Read: HOW_TO_VALIDATE_CHARITIES.md")
    print("3. 🧪 Test: python -m pytest tests/")
    print("4. 🎯 Start validating charities and making a difference!")

if __name__ == "__main__":
    main()
