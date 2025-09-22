# GitHub Codespaces Configuration

This directory contains the configuration for GitHub Codespaces, providing a cloud-based development environment for the Tackle Hunger Charity Validation project.

## What's Included

### `devcontainer.json`
Main configuration file that defines:
- **Base Image**: Security-optimized Python 3.13 Alpine Linux container
- **VS Code Extensions**: Pre-installed Python development tools, linters, formatters
- **Port Forwarding**: Automatic forwarding of port 8000 for development server
- **Environment Variables**: Pre-configured Python path and logging settings
- **User Configuration**: Non-root user setup for security

### `Dockerfile`
Custom Docker image based on the existing security-optimized setup:
- **Alpine Linux**: Minimal attack surface with only essential packages
- **Python 3.13**: Latest Python with all required dependencies
- **Development Tools**: Git, curl, bash for enhanced development experience
- **Security**: Non-root user with sudo access for development tasks

### `post-create.sh`
Automatic setup script that runs after container creation:
- **Environment Setup**: Creates `.env` from template
- **Connectivity Testing**: Verifies API endpoints accessibility
- **Git Configuration**: Sets up basic git configuration
- **Dependency Validation**: Confirms all Python packages are working

## How to Use

### Starting a Codespace

1. **From GitHub Web Interface:**
   - Navigate to the repository
   - Click "Code" → "Codespaces" → "Create codespace on main"
   - Wait 2-3 minutes for automatic setup

2. **From VS Code:**
   - Install "GitHub Codespaces" extension
   - Command Palette → "Codespaces: Create New Codespace"
   - Select this repository

3. **From GitHub CLI:**
   ```bash
   gh codespace create --repo TackleHunger/LNRS-Tech-for-Good-AI-Charity-Validation
   ```

### After Codespace Starts

1. **Configure Environment:**
   ```bash
   # Edit .env with your API credentials
   code .env
   ```

2. **Test Setup:**
   ```bash
   # Test connectivity
   python scripts/test_connectivity.py
   
   # Run tests
   python -m pytest
   ```

3. **Start Development:**
   ```bash
   # Interactive Python
   python
   
   # Format code
   python -m black src/
   
   # Lint code
   python -m flake8 src/
   ```

## Features

### Pre-installed Extensions
- **Python Support**: Full Python language server, debugging, testing
- **Code Quality**: Black formatter, Flake8 linter, Pylint
- **Development**: Docker support, YAML/JSON editing
- **AI Assistance**: GitHub Copilot and Copilot Chat
- **Data Science**: Jupyter notebook support

### Security Features
- **Alpine Linux**: 96% fewer vulnerabilities than standard containers
- **Non-root User**: All operations run as `tacklehunger` user
- **Minimal Dependencies**: Only essential packages installed
- **Isolated Environment**: Complete isolation from host system

### Development Benefits
- **Zero Setup**: No local installation required
- **Consistent Environment**: Same setup for all contributors
- **Cloud Compute**: Access to GitHub's cloud resources
- **Automatic Updates**: Container updates managed automatically
- **Cross-platform**: Works from any device with web browser

## Troubleshooting

### Common Issues

**Codespace won't start:**
- Check GitHub Codespaces status page
- Try creating a new codespace
- Contact GitHub support if persistent

**Extensions not loading:**
- Reload VS Code window: `Ctrl+Shift+P` → "Developer: Reload Window"
- Check Extensions tab for any errors
- Restart codespace if needed

**Environment variables missing:**
- Run post-create script manually: `.devcontainer/post-create.sh`
- Check if `.env` file was created properly
- Verify `.env.example` exists in repository

**API connectivity issues:**
- Some endpoints may be blocked from GitHub infrastructure
- This is expected for development - local testing will work
- Use dev environment for external API testing

### Performance Tips

- **Close unused tabs** to save memory
- **Use terminal efficiently** - prefer single terminal session
- **Commit frequently** to save work in cloud
- **Use port forwarding** for web services

## Comparison with Other Options

| Feature | Codespaces | Docker | Local Python |
|---------|------------|---------|--------------|
| Setup Time | 2-3 minutes | 5-10 minutes | 10-30 minutes |
| Dependencies | Automatic | Isolated | Manual |
| Consistency | Guaranteed | High | Variable |
| Resource Usage | Cloud | Local | Local |
| Offline Access | No | Yes | Yes |
| Cost | GitHub hours | Free | Free |

## Contributing

To modify the Codespaces configuration:

1. **Update `devcontainer.json`** for VS Code settings, extensions, or features
2. **Modify `Dockerfile`** for system dependencies or base image changes
3. **Edit `post-create.sh`** for setup automation
4. **Test changes** by creating a new codespace
5. **Document updates** in this README

The configuration follows the existing security-optimized Docker setup to ensure consistency across all development environments.