# How to Validate Charities - Volunteer Guide

Welcome! You're helping ensure people in need can find accurate information about food assistance. This guide gets you started in 10 minutes.

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install requests gql[requests] python-dotenv pytest
   ```

2. **Get your API token:**
   - Ask your team lead for the `AI_SCRAPING_TOKEN`
   - Create a `.env` file with:
     ```
     AI_SCRAPING_TOKEN=your_token_here
     ENVIRONMENT=dev
     ```

3. **Test it works:**
   ```bash
   # From the project directory, run:
   python -c "from src.tackle_hunger.graphql_client import TackleHungerClient; print('✅ Ready!')"
   
   # Or run the tests:
   python -m pytest tests/
   ```

## Basic Charity Validation Workflow

### Step 1: Get Charities Needing Validation

```python
# Always run your code from the project root directory
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

# Connect to the API
client = TackleHungerClient()
site_ops = SiteOperations(client)

# Get charities that need validation
sites = site_ops.get_sites_for_ai(limit=10)
print(f"Found {len(sites)} charities to validate")

# Look at first charity
charity = sites[0]
print(f"Name: {charity['name']}")
print(f"Address: {charity['streetAddress']}, {charity['city']}")
print(f"Phone: {charity['publicPhone']}")
print(f"Website: {charity['website']}")
```

### Step 2: Validate Information

For each charity, check:

- **Address**: Is it correct? Not a PO Box?
- **Phone**: Does it work? 
- **Website**: Is it active and relevant?
- **Name**: Is this the correct charity name?
- **Status**: Is the charity still operating?

### Step 3: Update Charity Information

```python
# Update a charity with corrected information
updated_data = {
    "publicPhone": "555-123-4567",  # Corrected phone
    "website": "https://newwebsite.org",  # Updated website
    "description": "Provides food pantry services to families in need",
    "modifiedBy": "AI_Copilot_Assistant"  # Required field
}

result = site_ops.update_site(charity['id'], updated_data)
print("✅ Updated charity information")
```

### Step 4: Create New Charity (if needed)

```python
# Add a completely new charity
new_charity = {
    "name": "Local Food Pantry",  # Required
    "streetAddress": "123 Main St",  # Required  
    "city": "Springfield",  # Required
    "state": "IL",  # Required
    "zip": "62701",  # Required
    "publicPhone": "555-987-6543",
    "website": "https://localfoodpantry.org",
    "description": "Community food pantry serving Springfield area",
    "createdMethod": "AI_Copilot_Assistant"  # Required
}

result = site_ops.create_site(new_charity)
print("✅ Created new charity")
```

## Key Fields to Focus On

### Essential Information (Always validate these)
- `name` - Charity name
- `streetAddress`, `city`, `state`, `zip` - Physical location
- `publicPhone` - Contact number
- `website` - Official website
- `status` - Is it still operating?

### Helpful but Optional
- `description` - Brief summary of services
- `publicEmail` - Email contact
- `serviceArea` - Geographic area served
- `hoursText` - When food is available

### Always Set These
- `createdMethod: "AI_Copilot_Assistant"` (when creating)
- `modifiedBy: "AI_Copilot_Assistant"` (when updating)

## Common Tasks

### Find charities missing phone numbers:
```python
sites = site_ops.get_sites_for_ai(limit=50)
no_phone = [s for s in sites if not s.get('publicPhone')]
print(f"Found {len(no_phone)} charities without phone numbers")
```

### Find charities with broken websites:
```python
import requests

for site in sites[:10]:  # Check first 10
    website = site.get('website')
    if website:
        try:
            response = requests.get(website, timeout=5)
            if response.status_code != 200:
                print(f"⚠️ {site['name']}: Website may be down")
        except:
            print(f"❌ {site['name']}: Website unreachable")
```

### Batch update charities:
```python
updates = [
    {"id": "charity_id_1", "data": {"publicPhone": "555-1111"}},
    {"id": "charity_id_2", "data": {"website": "https://example.org"}}
]

for update in updates:
    result = site_ops.update_site(update["id"], update["data"])
    print(f"✅ Updated {update['id']}")
```

## Testing Your Changes

Always test your code:

```bash
python -m pytest tests/ -v
```

## Getting Help

- **GraphQL Schema**: Available at https://devapi.sboc.us/graphql (dev environment)
- **Questions**: Ask in the project channel
- **Errors**: Check the GraphQL playground for field requirements

## Tips for Success

1. **Start Small**: Validate 5-10 charities first to get comfortable
2. **Double Check**: Always verify information before updating
3. **Be Consistent**: Use the same `modifiedBy` value for all your updates
4. **Test Often**: Run tests frequently to catch issues early
5. **Document Findings**: Note any patterns you discover

## Impact

Every charity you validate helps families find food assistance faster. Your work directly connects people in need with resources that can help them.

**Happy validating! 🎯**