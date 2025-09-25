# Volunteer Quick Start Guide

Welcome to the Tackle Hunger Charity Validation project! This guide will get you productive in minutes.

## 🚀 Quick Setup (5 minutes)

1. **Run the automated setup:**
   ```bash
   python scripts/setup_dev_environment.py
   ```

2. **Configure your environment:**
   - Edit `.env` file with API credentials (get from GitHub secrets/team lead)
   - Test connectivity: `python scripts/test_connectivity.py`

3. **Verify everything works:**
   ```bash
   python -m pytest tests/
   ```

## 📋 What You'll Be Working On

**Charity Validation Operations:**
- Validating charity site information (addresses, contacts, services)
- Updating charity organization details
- Ensuring data quality for food distribution network

**Key APIs:**
- GraphQL API for charity data (dev/staging/production)

## 🛠 Development Workflow

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

## 🔒 Security & API Keys

- **Never commit API keys** - they're in `.env` (git-ignored)
- Use **dev environment** for development
- Mark all operations with `createdMethod="AI_Copilot_Assistant"`

## 🆘 Need Help?

- **Connectivity issues:** Check `docs/firewall-setup.md`
- **API questions:** See GraphQL schema in the [API playground](https://devapi.sboc.us/graphql)
- **Code questions:** All modules have detailed docstrings

## 📊 Impact

Your work helps ensure accurate charity information reaches people who need food assistance. Every validated charity site helps connect families with resources!

**Ready to start? Run the setup script and begin making a difference! 🎯**
