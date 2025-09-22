#!/bin/bash
# Post-create script for GitHub Codespaces
# Runs after the devcontainer is created to set up the development environment

set -e

echo "🚀 Setting up Tackle Hunger development environment in GitHub Codespaces..."

# Ensure .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please update it with your API credentials."
else
    echo "✅ .env file already exists"
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x scripts/*.py

# Install any additional Python packages that might be missing
echo "📦 Ensuring all Python dependencies are installed..."
pip install --user pydantic-settings ipython

# Test Python imports
echo "🐍 Testing Python environment..."
python3 -c "
import sys
print(f'Python version: {sys.version}')

try:
    from src.tackle_hunger.graphql_client import TackleHungerConfig
    print('✅ GraphQL client imports successfully')
except ImportError as e:
    print(f'⚠️  Import warning: {e}')

try:
    import pytest
    print('✅ pytest available')
except ImportError:
    print('⚠️  pytest not available')

print('✅ Python environment check complete')
"

# Run connectivity test (but don't fail if it doesn't work)
echo "🌐 Testing API connectivity..."
if python3 scripts/test_connectivity.py; then
    echo "✅ Connectivity test passed"
else
    echo "⚠️  Connectivity test failed - this is normal if API credentials are not set"
fi

# Set up git configuration for the codespace
echo "📋 Configuring git..."
git config --global init.defaultBranch main
git config --global core.editor "code --wait"

# Display helpful information
echo ""
echo "🎉 GitHub Codespaces setup complete!"
echo ""
echo "Next steps:"
echo "1. 📝 Edit .env file with your API credentials (get from GitHub environment secrets)"
echo "2. 🧪 Run tests: python -m pytest"
echo "3. 🌐 Test connectivity: python scripts/test_connectivity.py"
echo "4. 🏗️  Start developing charity validation operations!"
echo ""
echo "📚 Documentation:"
echo "- VOLUNTEER_QUICK_START.md - Quick start guide"
echo "- docs/firewall-setup.md - Network configuration"
echo "- README.md - Project overview"
echo ""
echo "🔧 Useful commands:"
echo "- Run tests: python -m pytest"
echo "- Interactive Python: python or ipython"
echo "- Format code: python -m black src tests"
echo "- Lint code: python -m flake8 src tests"
echo ""
echo "Happy coding! 🚀"