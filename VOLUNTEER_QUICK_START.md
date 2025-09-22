# Volunteer Quick Start Guide

Welcome to the Tackle Hunger Charity Validation project! This guide will get you productive in minutes.

## 🚀 Quick Setup Options

### Option 1: Docker Setup (Recommended for Consistency)

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

### Option 2: Local Python Setup

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

### Option 3: GitHub Codespaces (Cloud Development)

**Prerequisites**: GitHub account with Codespaces access

```bash
# 1. Open repository in GitHub
# 2. Click "Code" → "Codespaces" → "Create codespace on main"
# 3. Wait for automatic setup (2-3 minutes)
# 4. Edit .env with your API credentials
# 5. Run tests: python -m pytest
```

**Benefits**: Zero local setup, consistent environment, browser-based or VS Code, automatic dependency installation, pre-configured extensions, cloud compute resources.

## 📋 What You'll Be Working On

**Charity Validation Operations:**

- Validating charity site information (addresses, contacts, services)
- Updating charity organization details
- Ensuring data quality for food distribution network

**Key APIs:**

- GraphQL API for charity data (dev/staging/production)

## 🛠 Development Workflow

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

### Codespaces Workflow

**Built-in cloud development environment:**

```bash
# Everything is pre-configured! Just edit and run:

# Work with charity validation
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

# Interactive development
python  # Access to full Python REPL
```

## 🔒 Security & API Keys

- **Security-optimized Docker environment** - Uses Alpine Linux with minimal vulnerabilities (only 2 low-severity)
- **Never commit API keys** - they're in `.env` (git-ignored)
- Use **dev environment** for development
- Mark all operations with `createdMethod="AI_Copilot_Assistant"`

## 🆘 Need Help?

### Docker Issues

- **Setup problems:** See `docs/docker-setup.md`
- **Container won't start:** `docker-compose logs tackle-hunger-dev`
- **Environment variables:** `docker exec -it tackle-hunger-charity-validation cat /app/.env`

### Codespaces Issues

- **Codespace won't start:** Check GitHub Codespaces status page
- **Environment setup failed:** Re-run post-create script: `.devcontainer/post-create.sh`
- **Extension issues:** Reload window (Ctrl+Shift+P → "Developer: Reload Window")
- **Port forwarding:** Check "Ports" tab in VS Code terminal panel

### General Issues

- **Connectivity issues:** Check `docs/firewall-setup.md`
- **API questions:** See GraphQL schema in staging playground
- **Code questions:** All modules have detailed docstrings

## 🔄 Quick Commands Reference

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

### Codespaces Commands

```bash
# Run tests
python -m pytest

# Test connectivity
python scripts/test_connectivity.py

# Format code
python -m black src/ tests/

# Lint code
python -m flake8 src/ tests/

# Interactive Python
python
```

## 📊 Impact

Your work helps ensure accurate charity information reaches people who need food assistance. Every validated charity site helps connect families with resources!

## 🎯 Ready to Start?

**Choose your setup method:**

- **New to development or want consistency?** → Use Docker setup
- **Prefer local development?** → Use Python setup  
- **Want zero setup and cloud development?** → Use GitHub Codespaces
- **Want to try multiple approaches?** → Start with Codespaces, then try others

**All three methods give you the same powerful development environment for charity validation work!**
