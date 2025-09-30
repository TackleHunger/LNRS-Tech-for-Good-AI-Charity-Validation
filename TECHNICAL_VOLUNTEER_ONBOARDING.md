# LNRS Tech for Good: Technical Volunteer Onboarding ⚡

*Quick setup guide for developers and technical contributors*

---

## 🎯 **Mission**
Validate and update charity information via GraphQL API to help families find food assistance faster.

---

## ⚡ **Quick Setup (5-10 minutes)**

### **Prerequisites** 
- [ ] Python 3.8+ installed
- [ ] Git installed
- [ ] Terminal/command line comfort

### **Environment Setup**
```bash
# Clone and setup
git clone https://github.com/TackleHunger/LNRS-Tech-for-Good-AI-Charity-Validation.git
cd LNRS-Tech-for-Good-AI-Charity-Validation

# Automated setup
python scripts/setup_dev_environment.py

# Verify installation
python -m pytest tests/
python scripts/test_connectivity.py
```

### **API Token Configuration**
1. [ ] **Request `AI_SCRAPING_TOKEN`** from LNRS team lead
2. [ ] **Update `.env` file:**
   ```bash
   # Replace placeholder in .env
   AI_SCRAPING_TOKEN=your_actual_token_here
   AI_SCRAPING_GRAPHQL_URL=https://devapi.sboc.us/graphql
   ENVIRONMENT=dev
   ```

### **Verification**
```bash
# Test API connectivity
python scripts/test_connectivity.py

# Run full test suite
python -m pytest tests/ -v

# Test GraphQL client
python -c "from src.tackle_hunger.graphql_client import TackleHungerClient; print('✅ Ready')"
```

---

## 🔧 **Technical Details**

### **Tech Stack**
- **Language**: Python 3.8+
- **API**: GraphQL (gql library)
- **Dependencies**: requests, python-dotenv, pytest, black
- **Architecture**: Simple client-server with environment-based config

### **Project Structure**
```
├── src/tackle_hunger/          # Core modules
│   ├── graphql_client.py       # GraphQL API client
│   └── site_operations.py      # Charity validation operations
├── scripts/                    # Setup and utility scripts
├── tests/                      # Test suite
├── docs/                       # Additional documentation
├── requirements.txt            # Python dependencies
└── .env.example               # Environment template
```

### **Key Operations**
```python
# Basic usage pattern
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
ops = SiteOperations(client)

# Fetch sites needing validation
sites = ops.get_sites_for_ai(limit=10)

# Update site information
ops.update_site(site_id, updated_data)
```

### **Development Workflow**
1. **Query**: Use `sitesForAI` to get charity data needing validation
2. **Validate**: Verify addresses, phones, websites, hours
3. **Update**: Push corrections via `updateSiteFromAI` mutation
4. **Mark**: Always include `modifiedBy: "AI_Copilot_Assistant"`

---

## 🚀 **Next Steps**

### **Ready to Contribute**
- [ ] Read `HOW_TO_VALIDATE_CHARITIES.md` for business rules
- [ ] Review GraphQL schema at https://devapi.sboc.us/graphql
- [ ] Start with small batch validation (5-10 charities)
- [ ] Follow commit conventions and testing practices

### **Troubleshooting**
- **403/401 errors**: Check API token in `.env`
- **Module import errors**: Ensure you're in project root
- **Network issues**: Review `docs/firewall-setup.md`
- **Rate limiting**: Built into client, respects API limits

### **Contributing**
- **Issues**: Check GitHub issues for bug reports
- **PRs**: Follow existing code style (black formatting)
- **Testing**: Add tests for new functionality
- **Documentation**: Update relevant docs with changes

---

## 📊 **Impact Metrics**
- **Primary Goal**: Validate charity contact information accuracy
- **Success Measure**: Families can successfully contact food assistance
- **Quality**: Mark all AI operations with consistent `modifiedBy` tags
- **Scale**: Help expand food assistance network coverage

---

**⚡ Questions? Check the docs/ folder or ask in the tech channel.**
