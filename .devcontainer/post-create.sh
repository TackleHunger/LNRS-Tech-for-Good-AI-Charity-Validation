#!/bin/bash
# Post-creation setup script for Tackle Hunger Charity Validation Codespace
# This script runs after the devcontainer is created and sets up the development environment

set -e

echo "🚀 Setting up Tackle Hunger Charity Validation development environment..."

# Ensure we're in the workspace directory
cd /workspace

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📋 Setting up environment configuration..."
    cp .env.example .env
    echo "✅ Created .env from .env.example"
    echo "⚠️  Please edit .env with your API credentials from GitHub secrets"
else
    echo "✅ .env file already exists"
fi

# Set up git configuration for the workspace (if not already configured)
if [ -z "$(git config --global user.name)" ]; then
    echo "📝 Setting up git configuration..."
    git config --global user.name "Codespace User"
    git config --global user.email "user@codespace.local"
    echo "✅ Git configuration set up"
fi

# Test Python environment
echo "🐍 Testing Python environment..."
python -c "
import sys
print(f'Python version: {sys.version}')
print(f'Python path: {sys.path}')

# Test critical imports
try:
    import requests
    import gql
    import pydantic
    print('✅ Core dependencies imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

# Run connectivity test
echo "🌐 Testing connectivity to required endpoints..."
if python scripts/test_connectivity.py; then
    echo "✅ Connectivity test passed"
else
    echo "⚠️  Some endpoints may not be accessible from Codespaces"
    echo "    This is expected for dev API endpoints. Local development will work normally."
fi

# Set up pre-commit hooks (if available)
if command -v pre-commit &> /dev/null; then
    echo "🔧 Setting up pre-commit hooks..."
    pre-commit install || echo "⚠️  Pre-commit setup skipped"
fi

echo ""
echo "🎉 Codespace setup complete!"
echo ""
echo "📚 Next steps:"
echo "   1. Edit .env with your API credentials"
echo "   2. Run: python scripts/test_connectivity.py"
echo "   3. Run: python -m pytest"
echo "   4. Start developing charity validation features!"
echo ""
echo "📖 Documentation:"
echo "   - Quick Start: VOLUNTEER_QUICK_START.md"
echo "   - Docker Setup: docs/docker-setup.md"
echo "   - API Reference: README.md"
echo ""
echo "🆘 Need help? Check the documentation or ask in GitHub issues."