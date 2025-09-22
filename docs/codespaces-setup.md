# GitHub Codespaces Setup for Tackle Hunger Charity Validation

## Overview

This document explains how to use GitHub Codespaces for the Tackle Hunger charity validation system. Codespaces provides a fully configured cloud development environment that's ready to use in minutes with zero local setup required.

**Key Benefits:**

- **Zero Setup**: No local installation of Python, Docker, or dependencies required
- **Instant Environment**: Pre-configured with all tools, extensions, and dependencies
- **Consistent Experience**: Same environment for all volunteers regardless of local machine
- **VS Code Integration**: Full VS Code experience in the browser with extensions
- **GitHub Integration**: Seamless workflow with repository and GitHub features

## Getting Started

### 1. Launch a Codespace

1. **From GitHub Repository:**
   - Navigate to the repository on GitHub
   - Click the green **"Code"** button
   - Select the **"Codespaces"** tab
   - Click **"Create codespace on main"** (or another branch)

2. **Wait for Setup:**
   - Container will build (2-3 minutes first time)
   - VS Code will load in your browser
   - Post-create scripts will run automatically
   - All dependencies will be installed

### 2. Environment Configuration

The Codespace will automatically:

- Install Python 3.13 and all required packages
- Set up the proper Python path and environment variables
- Create a `.env` file from the template
- Install VS Code extensions for Python development
- Configure Git settings

**Manual Steps After Setup:**

1. **Update API Credentials:**
   ```bash
   # Edit .env file with your actual API credentials
   # Get these from GitHub environment secrets or team lead
   ```

2. **Test the Setup:**
   ```bash
   # Run connectivity test
   python scripts/test_connectivity.py
   
   # Run tests
   python -m pytest
   ```

### 3. Development Workflow

**Basic Development:**

```bash
# All commands work directly - no docker exec needed
python -m pytest                          # Run tests
python scripts/test_connectivity.py       # Test API connectivity
python -c "from src.tackle_hunger.graphql_client import TackleHungerClient; print('✅ Import successful')"
```

**Interactive Development:**

```python
# Use integrated Python REPL or Jupyter
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
site_ops = SiteOperations(client)
sites = site_ops.get_sites_for_ai(limit=10)
print(f'Found {len(sites)} sites for validation')
```

## Pre-installed Tools and Extensions

### VS Code Extensions

- **Python Support**: `ms-python.python`
- **Code Formatting**: `ms-python.black-formatter`
- **Linting**: `ms-python.flake8`, `charliermarsh.ruff`
- **Type Checking**: `ms-python.mypy-type-checker`
- **GitHub Copilot**: `GitHub.copilot`, `GitHub.copilot-chat`
- **Debugging**: `ms-python.debugpy`
- **Jupyter**: `ms-toolsai.jupyter`
- **YAML/TOML**: `redhat.vscode-yaml`, `tamasfe.even-better-toml`

### Python Packages

- **Core Dependencies**: All packages from `requirements.txt`
- **Additional Tools**: `pydantic-settings`, `ipython`, `jupyter`
- **Development Tools**: `black`, `flake8`, `mypy`, `pytest`

### System Tools

- **Git**: Pre-configured with safe directories
- **GitHub CLI**: `gh` command available
- **Text Editors**: `nano`, `vim`, `less`
- **System Tools**: `curl`, `tree`, `htop`

## Customization

### VS Code Settings

The devcontainer includes optimized VS Code settings:

- **Python Formatting**: Black formatter on save
- **Linting**: Flake8 and MyPy enabled
- **Testing**: pytest configured
- **Import Organization**: Automatic on save
- **File Exclusions**: `__pycache__`, `*.pyc` hidden

### Environment Variables

Default environment variables are set:

```bash
ENVIRONMENT=dev
LOG_LEVEL=INFO
LOG_FORMAT=json
PYTHONPATH=/app/src
```

### Port Forwarding

Port 8000 is automatically forwarded for any future web services.

## Troubleshooting

### Common Issues

**1. Codespace won't start:**

- Try creating a new Codespace
- Check if you have sufficient GitHub Codespaces quota
- Wait a few minutes and try again

**2. Environment setup fails:**

```bash
# From VS Code terminal, manually run setup
bash .devcontainer/post-create.sh
```

**3. Import errors:**

```bash
# Check Python path
echo $PYTHONPATH

# Reinstall dependencies
pip install -r requirements.txt
pip install pydantic-settings
```

**4. API connectivity issues:**

```bash
# Test network connectivity
curl -I https://devapi.sboc.us/graphql

# Check environment variables
cat .env
```

**5. VS Code extensions not working:**

- Reload the window: `Ctrl+Shift+P` → "Developer: Reload Window"
- Rebuild container: `Ctrl+Shift+P` → "Codespaces: Rebuild Container"

### Rebuild Container

If you need to completely reset your environment:

1. Open Command Palette (`Ctrl+Shift+P`)
2. Type "Codespaces: Rebuild Container"
3. Wait for rebuild to complete

### Performance Tips

- **Prebuilds**: Repository may have prebuilds enabled for faster startup
- **Stop Unused Codespaces**: Stop Codespaces when not in use to save quota
- **Local Files**: Use VS Code's file explorer for better performance than terminal commands

## Security Considerations

### Data Protection

- **No Local Storage**: Code and data stay in the cloud
- **Automatic Cleanup**: Codespaces are automatically deleted after inactivity
- **Environment Isolation**: Each Codespace is isolated from others

### API Keys

- **Never Commit**: API keys in `.env` are git-ignored
- **Environment Variables**: Use GitHub environment secrets when possible
- **Temporary Access**: API keys are only available during active sessions

### User Security

- **Non-Root User**: Container runs as `tacklehunger` user for security
- **Alpine Linux**: Security-optimized base image
- **Minimal Packages**: Only necessary tools installed

## GitHub Integration

### Seamless Workflow

- **Built-in Git**: All Git operations work normally
- **GitHub CLI**: `gh` command available for GitHub operations
- **Pull Requests**: Create and manage PRs directly from Codespace
- **Issues**: Link commits to issues automatically

### Collaboration

- **Shared Configuration**: All team members get identical environment
- **Live Share**: Share Codespace sessions with team members
- **Code Review**: Review PRs directly in Codespace environment

## Cost Management

### Codespaces Usage

- **Free Tier**: GitHub provides free Codespaces hours monthly
- **Auto-Stop**: Codespaces stop automatically after 30 minutes of inactivity
- **Manual Stop**: Stop Codespaces when finished to save quota

### Best Practices

- **Stop When Idle**: Always stop Codespaces when taking breaks
- **Use Appropriate Machine Types**: 2-core machines are sufficient for most work
- **Monitor Usage**: Check your Codespaces usage in GitHub settings

## Support

### Getting Help

1. **Documentation**: This guide and other docs in the repository
2. **GitHub Support**: For Codespaces-specific issues
3. **Team Support**: For project-specific questions
4. **Community**: GitHub Discussions for general questions

### Useful Commands

```bash
# Check Codespace info
gh codespace list

# SSH into Codespace (from local machine)
gh codespace ssh

# Forward ports
gh codespace ports forward 8000:8000
```

The GitHub Codespaces setup provides a powerful, consistent development environment for all volunteers working on the Tackle Hunger charity validation system, with zero local setup required and full GitHub integration.