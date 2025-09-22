#!/usr/bin/env python3
"""
Development environment setup script for Tackle Hunger volunteers.

This script helps volunteers quickly set up their development environment
with proper configuration and validation.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Verify Python 3.13 is being used."""
    if sys.version_info[:2] != (3, 13):
        print(f"Warning: Expected Python 3.13, but found {sys.version}")
        return False
    print("✓ Python 3.13 detected")
    return True


def install_dependencies():
    """Install required dependencies."""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False


def setup_environment_file():
    """Set up environment configuration file."""
    env_example = Path(".env.example")
    env_file = Path(".env")

    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        print("✓ Created .env file from template")
        print("Please edit .env file with your actual API credentials")
        return True
    elif env_file.exists():
        print("✓ .env file already exists")
        return True
    else:
        print("Error: .env.example not found")
        return False


def validate_environment():
    """Validate that required environment variables are set."""
    required_vars = [
        "AI_SCRAPING_TOKEN",
        "TKH_GRAPHQL_API_URL"
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Please update your .env file with the required values")
        return False

    print("✓ All required environment variables are set")
    return True


def main():
    """Main setup function."""
    print("Setting up Tackle Hunger development environment...")
    print("=" * 50)

    success = True
    success &= check_python_version()
    success &= install_dependencies()
    success &= setup_environment_file()

    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        success &= validate_environment()
    except ImportError:
        print("Note: python-dotenv not available for environment validation")

    print("=" * 50)
    if success:
        print("✓ Development environment setup complete!")
        print("\nNext steps:")
        print("1. Edit .env file with your actual API credentials")
        print("2. Run tests: python -m pytest")
        print("3. Start coding charity validation operations!")
    else:
        print("⚠ Setup completed with warnings. Please address the issues above.")


if __name__ == "__main__":
    main()
