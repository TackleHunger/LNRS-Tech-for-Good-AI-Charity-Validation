# Volunteer Quick Start Guide

Welcome to the Tackle Hunger Charity Validation project! This guide will get you productive in minutes.

## 🚀 Quick Setup Options

### Option 1: GitHub Codespaces Setup (Recommended for Instant Setup)

**Prerequisites**: GitHub account with Codespaces access

```bash
# 1. Click the green "Code" button on the GitHub repository
# 2. Select "Codespaces" tab
# 3. Click "Create codespace on main" or "Create codespace on staging"
# 4. Wait for the container to build and start (usually 2-3 minutes)
# 5. The environment will auto-configure with all dependencies
```

**Benefits**: Zero local setup, fully configured environment, integrated with GitHub, automatic dependency management, VS Code in browser with extensions pre-installed.

### Option 2: Docker Setup (Recommended for Local Consistency)

**Prerequisites**: Docker Desktop installed ([Download here](https://www.docker.com/products/docker-desktop/))

```bash
# 1. Clone the repository
git clone <repository-url>
cd LNRS-Tech-for-Good-AI-Charity-Validation

# 2. Set up environment
cp .env.example .env
# Edit .env with your API credentials

# 3. Start with Docker Compose
docker-compose up -d

# 4. Access the container
docker exec -it tackle-hunger-charity-validation bash

# 5. Run tests inside container
python -m pytest
```

**Benefits**: Security-optimized environment (Alpine Linux), minimal vulnerabilities, no Python version conflicts, isolated dependencies, 84% smaller image size.

### Option 3: Local Python Setup

**Prerequisites**: Python 3.13 installed

```bash
# 1. Clone the repository
git clone <repository-url>
cd LNRS-Tech-for-Good-AI-Charity-Validation

# 2. Run the automated setup
python scripts/setup_dev_environment.py

# 3. Configure your environment
cp .env.example .env
# Edit .env with API credentials (get from GitHub secrets/team lead)

# 4. Test connectivity
python scripts/test_connectivity.py

# 5. Verify everything works
python -m pytest
```

**Benefits**: Direct access to files, familiar local development, faster iteration for some developers.

## 📋 What You'll Be Working On

**Charity Validation Operations:**
- Validating charity site information (addresses, contacts, services)
- Updating charity organization details
- Ensuring data quality for food distribution network

**Key APIs:**
- GraphQL API for charity data (dev/staging/production)

## 🛠 Development Workflow

### Codespaces Workflow

```bash
# Environment is automatically set up when Codespace starts
# All dependencies are pre-installed

# Work with live-reloaded code (edit files in VS Code)
python -c "
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
site_ops = SiteOperations(client)
sites = site_ops.get_sites_for_ai(limit=10)
print(f'Found {len(sites)} sites for validation')
"

# Run tests
python -m pytest

# Interactive Python shell
python
# or
ipython
```

### Docker Workflow

```bash
# Start development environment
docker-compose up -d

# Work with live-reloaded code (edit files locally, they're mounted in container)
docker exec -it tackle-hunger-charity-validation python -c "
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
site_ops = SiteOperations(client)
sites = site_ops.get_sites_for_ai(limit=10)
print(f'Found {len(sites)} sites for validation')
"

# Run tests
docker exec -it tackle-hunger-charity-validation python -m pytest

# Interactive Python shell
docker exec -it tackle-hunger-charity-validation python
```

### Local Python Workflow

**For charity validation tasks:**
```python
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

# Initialize client
client = TackleHungerClient()
site_ops = SiteOperations(client)

# Get sites needing validation
sites = site_ops.get_sites_for_ai(limit=10)

# Process and update sites
# (Your validation logic here)
```

## 🔄 Quick Commands Reference

### Codespaces Commands

```bash
# Environment setup (automatic when Codespace starts)
# All dependencies are pre-installed

# Run tests
python -m pytest

# Test connectivity
python scripts/test_connectivity.py

# Interactive shell
python
# or
ipython

# Format code
python -m black src tests

# Lint code
python -m flake8 src tests
```

### Docker Commands

```bash
# Start environment
docker-compose up -d

# Run tests
docker exec -it tackle-hunger-charity-validation python -m pytest

# Test connectivity
docker exec -it tackle-hunger-charity-validation python scripts/test_connectivity.py

# Interactive shell
docker exec -it tackle-hunger-charity-validation bash

# Stop environment
docker-compose down
```

### Local Commands

```bash
# Set up environment
python scripts/setup_dev_environment.py

# Run tests
python -m pytest

# Test connectivity
python scripts/test_connectivity.py
```

## 🔒 Security & API Keys

- **Security-optimized environment** - Codespaces and Docker use Alpine Linux with minimal vulnerabilities (only 2 low-severity)
- **Never commit API keys** - they're in `.env` (git-ignored)
- Use **dev environment** for development
- Mark all operations with `createdMethod="AI_Copilot_Assistant"`

## 🆘 Need Help?

### Codespaces Issues

- **Setup problems:** Rebuild the Codespace from the Command Palette
- **Container issues:** Check the devcontainer logs in VS Code
- **Extensions not working:** Reload the window or rebuild the container

### Docker Issues

- **Setup problems:** See `docs/docker-setup.md`
- **Container won't start:** `docker-compose logs tackle-hunger-dev`
- **Environment variables:** `docker exec -it tackle-hunger-charity-validation cat /app/.env`

### General Issues

- **Connectivity issues:** Check `docs/firewall-setup.md`
- **API questions:** See GraphQL schema in staging playground
- **Code questions:** All modules have detailed docstrings

## 📊 Impact

Your work helps ensure accurate charity information reaches people who need food assistance. Every validated charity site helps connect families with resources!

## 🎯 Ready to Start?

**Choose your setup method:**

- **Want instant setup with zero configuration?** → Use GitHub Codespaces
- **New to development or want consistency?** → Use Docker setup
- **Prefer local development?** → Use Python setup

**All methods give you the same powerful development environment for charity validation work!**
