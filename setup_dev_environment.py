#!/usr/bin/env python3
"""
Automated development environment setup for Tackle Hunger volunteers.

This script sets up everything needed to start contributing to charity validation work:
- Checks Python version compatibility
- Installs required dependencies
- Creates .env configuration file
- Tests connectivity to verify setup
- Provides next steps guidance

Run this script first when joining the project!
"""

import sys
import subprocess
from pathlib import Path


def print_success(message: str) -> None:
    print(f"✅ {message}")


def print_warning(message: str) -> None:
    print(f"⚠️  {message}")


def print_error(message: str) -> None:
    print(f"❌ {message}")


def print_info(message: str) -> None:
    print(f"ℹ️  {message}")


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    print_info("Checking Python version...")
    
    version = sys.version_info
    if version.major != 3 or version.minor < 8:
        print_error(f"Python {version.major}.{version.minor} detected")
        print_error("This project requires Python 3.8 or higher")
        return False
    
    print_success(f"Python {version.major}.{version.minor}.{version.micro} ✓")
    return True


def install_dependencies() -> bool:
    """Install required Python packages."""
    print_info("Installing required dependencies...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print_success("Dependencies installed successfully")
            return True
        else:
            print_error("Failed to install dependencies")
            return False
            
    except Exception as e:
        print_error(f"Error installing dependencies: {e}")
        return False


def create_env_file() -> bool:
    """Create .env file from .env.example if it doesn't exist."""
    print_info("Setting up environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_warning(".env file already exists - skipping creation")
        return True
    
    if not env_example.exists():
        print_error(".env.example file not found")
        return False
    
    try:
        env_content = env_example.read_text()
        env_file.write_text(env_content)
        print_success("Created .env file from .env.example")
        return True
    except Exception as e:
        print_error(f"Failed to create .env file: {e}")
        return False


def run_connectivity_test() -> bool:
    """Run connectivity tests."""
    print_info("Testing connectivity...")
    
    try:
        result = subprocess.run([
            sys.executable, "scripts/test_connectivity.py"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print_success("Connectivity tests passed")
        else:
            print_warning("Some connectivity tests failed (normal without API token)")
        return True
            
    except Exception:
        print_warning("Could not run connectivity tests")
        return True


def main():
    """Main setup function."""
    print("🎯 TACKLE HUNGER VOLUNTEER SETUP")
    print("="*50)
    
    steps = [
        ("Checking Python version", check_python_version),
        ("Installing dependencies", install_dependencies), 
        ("Creating environment file", create_env_file),
        ("Testing connectivity", run_connectivity_test)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print_error(f"Setup failed at: {step_name}")
            sys.exit(1)
    
    print("\n🎉 SETUP COMPLETE!")
    print("\n📋 NEXT STEPS:")
    print("1. 🔑 Get API token from your team lead")
    print("2. 📝 Edit .env file with the actual AI_SCRAPING_TOKEN")
    print("3. 🧪 Test with: python scripts/test_connectivity.py")
    print("4. 📚 Read: HOW_TO_VALIDATE_CHARITIES.md")
    print("5. 🚀 Start validating charities!")
    print("\n🍽️ Ready to help families find food assistance!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Setup interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
