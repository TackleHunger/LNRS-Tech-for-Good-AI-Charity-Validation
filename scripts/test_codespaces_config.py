#!/usr/bin/env python3
"""
Test script to validate GitHub Codespaces configuration for Tackle Hunger project.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_devcontainer_json():
    """Test that devcontainer.json is valid and contains required settings."""
    print("🔍 Testing devcontainer.json...")
    
    devcontainer_path = Path(".devcontainer/devcontainer.json")
    if not devcontainer_path.exists():
        raise FileNotFoundError("devcontainer.json not found")
    
    with open(devcontainer_path) as f:
        config = json.load(f)
    
    # Check required fields (updated for new structure)
    required_fields = ["name", "customizations", "forwardPorts"]
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
    
    # Check that we have dockerfile configuration (allowing multiple approaches)
    has_dockerfile_config = (
        "dockerfile" in config or 
        "build" in config or 
        "image" in config
    )
    if not has_dockerfile_config:
        raise ValueError("Missing dockerfile, build, or image configuration")
    
    # If build is present, check its structure
    if "build" in config:
        build_config = config["build"]
        if "context" not in build_config or "dockerfile" not in build_config:
            raise ValueError("Build configuration missing context or dockerfile")
    
    # Check VS Code extensions
    extensions = config["customizations"]["vscode"]["extensions"]
    required_extensions = ["ms-python.python", "GitHub.copilot"]
    for ext in required_extensions:
        if ext not in extensions:
            raise ValueError(f"Missing required extension: {ext}")
    
    print("✅ devcontainer.json is valid")


def test_dockerfile():
    """Test that Dockerfile exists and has basic structure."""
    print("🔍 Testing Dockerfile...")
    
    dockerfile_path = Path(".devcontainer/Dockerfile")
    if not dockerfile_path.exists():
        raise FileNotFoundError("Dockerfile not found")
    
    with open(dockerfile_path) as f:
        content = f.read()
    
    # Check for essential components
    required_content = ["FROM python:3.13-alpine", "tacklehunger", "requirements.txt"]
    for item in required_content:
        if item not in content:
            raise ValueError(f"Missing required content in Dockerfile: {item}")
    
    print("✅ Dockerfile is valid")


def test_post_create_script():
    """Test that post-create script exists and is executable."""
    print("🔍 Testing post-create script...")
    
    script_path = Path(".devcontainer/post-create.sh")
    if not script_path.exists():
        raise FileNotFoundError("post-create.sh not found")
    
    # Check if script is executable
    if not os.access(script_path, os.X_OK):
        raise PermissionError("post-create.sh is not executable")
    
    # Check for basic bash syntax
    result = subprocess.run(["bash", "-n", str(script_path)], capture_output=True)
    if result.returncode != 0:
        raise SyntaxError(f"Bash syntax error in post-create.sh: {result.stderr.decode()}")
    
    print("✅ post-create.sh is valid")


def test_vs_code_extensions():
    """Test VS Code extensions configuration."""
    print("🔍 Testing VS Code extensions...")
    
    extensions_path = Path(".vscode/extensions.json")
    if not extensions_path.exists():
        raise FileNotFoundError("VS Code extensions.json not found")
    
    with open(extensions_path) as f:
        config = json.load(f)
    
    if "recommendations" not in config:
        raise ValueError("Missing recommendations in extensions.json")
    
    # Check for essential Python extensions
    recommendations = config["recommendations"]
    required = ["ms-python.python", "GitHub.copilot"]
    for ext in required:
        if ext not in recommendations:
            raise ValueError(f"Missing recommended extension: {ext}")
    
    print("✅ VS Code extensions configuration is valid")


def test_environment_files():
    """Test that required environment files exist."""
    print("🔍 Testing environment files...")
    
    required_files = [
        ".env.example",
        "requirements.txt",
        "scripts/test_connectivity.py",
        "VOLUNTEER_QUICK_START.md",
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Required file not found: {file_path}")
    
    print("✅ Environment files are present")


def test_python_dependencies():
    """Test that Python dependencies can be imported."""
    print("🔍 Testing Python dependencies...")
    
    try:
        import requests
        import gql
        import pydantic
        print("✅ Core dependencies imported successfully")
    except ImportError as e:
        raise ImportError(f"Failed to import required dependency: {e}")


def main():
    """Run all tests."""
    print("🚀 Testing GitHub Codespaces configuration for Tackle Hunger...")
    print("=" * 60)
    
    tests = [
        test_devcontainer_json,
        test_dockerfile,
        test_post_create_script,
        test_vs_code_extensions,
        test_environment_files,
        test_python_dependencies,
    ]
    
    failed_tests = []
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed_tests.append(test.__name__)
    
    print("=" * 60)
    
    if failed_tests:
        print(f"❌ {len(failed_tests)} test(s) failed:")
        for test_name in failed_tests:
            print(f"   - {test_name}")
        sys.exit(1)
    else:
        print("🎉 All Codespaces configuration tests passed!")
        print("Ready for GitHub Codespaces deployment!")


if __name__ == "__main__":
    main()