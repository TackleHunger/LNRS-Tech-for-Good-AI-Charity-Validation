# Devcontainer Configuration

This directory contains the GitHub Codespaces / VS Code devcontainer configuration for the Tackle Hunger charity validation project.

## Files

- **`devcontainer.json`** - Main configuration file that defines the devcontainer settings
- **`Dockerfile`** - Custom Docker image for the development environment  
- **`post-create.sh`** - Script that runs after the container is created to set up the environment

## Configuration Features

### Container Environment

- **Base Image**: Alpine Linux 3.18 (security-optimized)
- **Python**: Version 3.13 with all project dependencies
- **User**: Non-root `tacklehunger` user for security
- **Working Directory**: `/app`

### VS Code Extensions

Pre-installed extensions for optimal development experience:

- Python language support and debugging
- Code formatting (Black) and linting (Flake8, Ruff, MyPy)
- GitHub Copilot integration
- Jupyter notebook support
- YAML and TOML file support

### Environment Variables

- `ENVIRONMENT=dev` - Development environment
- `LOG_LEVEL=INFO` - Logging level
- `LOG_FORMAT=json` - JSON log format
- `PYTHONPATH=/app/src` - Python import path

### Features

- **Git**: Pre-configured with safe directories
- **GitHub CLI**: Available for GitHub operations
- **Port Forwarding**: Port 8000 forwarded for web services

## Usage

### Launch from GitHub

1. Navigate to the repository on GitHub.com
2. Click the green "Code" button
3. Select "Codespaces" tab
4. Click "Create codespace on main"

### Launch from VS Code

1. Install the "Dev Containers" extension
2. Open the repository in VS Code
3. Command Palette → "Dev Containers: Reopen in Container"

## Post-Creation Setup

The `post-create.sh` script automatically:

- Creates `.env` file from template
- Makes scripts executable
- Installs additional Python packages
- Tests the Python environment
- Configures Git settings
- Displays helpful setup information

## Manual Configuration

After the container starts, you may need to:

1. Edit `.env` file with actual API credentials
2. Run `python scripts/test_connectivity.py` to test API access
3. Run `python -m pytest` to verify tests pass

## Troubleshooting

### Rebuild Container

If you encounter issues, rebuild the container:

1. Command Palette (`Ctrl+Shift+P`)
2. "Dev Containers: Rebuild Container" or "Codespaces: Rebuild Container"

### Check Logs

- View devcontainer build logs in VS Code output panel
- Check post-creation script output in terminal

### Environment Issues

```bash
# Check environment variables
env | grep -E "(ENVIRONMENT|PYTHONPATH|LOG_)"

# Test Python imports
python -c "from src.tackle_hunger.graphql_client import TackleHungerClient; print('✅ Imports working')"

# Reinstall dependencies
pip install -r requirements.txt
```

## Customization

### Add Extensions

Edit the `extensions` array in `devcontainer.json`:

```json
"extensions": [
  "ms-python.python",
  "your-extension-id"
]
```

### Modify Environment

Edit the `containerEnv` section in `devcontainer.json`:

```json
"containerEnv": {
  "ENVIRONMENT": "dev",
  "YOUR_VAR": "value"
}
```

### Change Container Image

Modify the `build` section in `devcontainer.json` or edit the `Dockerfile`.

This devcontainer configuration provides a consistent, fully-featured development environment for all contributors to the Tackle Hunger charity validation project.