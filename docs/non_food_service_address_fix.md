# Non-Food-Service Address Fix

This module provides functionality to identify and fix non-food-service addresses (like PO boxes) in charity Sites by moving them to the parent Organization and updating the Site with a physical address if available.

## Problem Statement

According to the Tackle Hunger schema requirements:
- **Sites** should contain physical addresses for food pickup/dropoff/distribution (avoid PO boxes)
- **Organizations** can contain mailing addresses including PO boxes

Some sites may have been incorrectly created with PO boxes or other non-physical addresses that should be moved to the parent organization.

## Solution

The fix involves:

1. **Detection**: Identify sites with non-physical addresses (PO boxes, virtual addresses, etc.)
2. **Organization Update**: Move the non-physical address to the parent Organization using `updateOrganizationFromAI`
3. **Site Update**: Update the Site with a physical address from other sites in the organization, or clear it if none available, using `updateSiteFromAI`

## Components

### AddressValidator (`src/tackle_hunger/address_validator.py`)

Validates addresses and identifies non-food-service addresses:

```python
from tackle_hunger.address_validator import AddressValidator

validator = AddressValidator()

# Check if an address is suitable for a food service site
is_suitable = validator.is_suitable_for_site("P.O. Box 123")  # Returns False

# Get detailed classification
classification = validator.classify_address("123 Main Street")
print(classification.is_physical_address)  # True
print(classification.confidence)  # 0.85
```

### SiteOperations (`src/tackle_hunger/site_operations.py`)

Manages the complete workflow for fixing addresses:

```python
from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
site_ops = SiteOperations(client)

# Fix non-food-service addresses
sites_processed, fixes_applied = site_ops.fix_non_food_service_addresses(limit=50)
print(f"Processed {sites_processed} sites, applied {fixes_applied} fixes")
```

## Command Line Usage

The main script provides a convenient command-line interface:

```bash
# Analyze sites without making changes (dry run)
python scripts/fix_non_food_service_addresses.py --dry-run --limit 10

# Fix addresses for up to 50 sites
python scripts/fix_non_food_service_addresses.py --limit 50

# Enable verbose logging
python scripts/fix_non_food_service_addresses.py --verbose --limit 10
```

### Script Options

- `--limit N`: Maximum number of sites to process (default: 50)
- `--dry-run`: Analyze sites but make no changes
- `--verbose`: Enable detailed logging

## Environment Setup

Ensure your `.env` file contains:

```
AI_SCRAPING_TOKEN=your_ai_scraping_token_here
ENVIRONMENT=dev
```

## Address Detection Patterns

The system detects various non-physical address patterns:

### PO Box Patterns
- "P.O. Box 123"
- "PO Box 456"
- "Post Office Box 789"
- "Box 202" (standalone)

### Virtual Address Patterns  
- "PMB 456" (Private Mail Box)
- "Suite 123 Mail Forwarding Service"
- "Mail Drop 101"

### Physical Address Indicators
- "123 Main Street"
- "456 Oak Avenue" 
- "789 N. Washington Blvd"
- "Building 5, 303 Corporate Drive"

## GraphQL Operations

The fix uses these mutations following the schema defined in README.md:

### updateOrganizationFromAI
```graphql
mutation updateOrganizationFromAI($organizationId: String!, $input: organizationInputUpdate!) {
  updateOrganizationFromAI(organizationId: $organizationId, input: $input) {
    id
    streetAddress
  }
}
```

### updateSiteFromAI
```graphql
mutation updateSiteFromAI($siteId: String!, $input: siteInputForAIUpdate!) {
  updateSiteFromAI(siteId: $siteId, input: $input) {
    id
    streetAddress
  }
}
```

## Error Handling

The system includes comprehensive error handling:

- **Network errors**: Gracefully handles GraphQL API failures
- **Data validation**: Safely processes sites with missing or invalid data
- **Transaction safety**: Updates are atomic - if organization update fails, site is not modified
- **Logging**: Detailed logs help track what changes were made

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_address_validator.py -v
python -m pytest tests/test_site_operations.py -v
python -m pytest tests/test_integration.py -v
```

## Monitoring

The script generates detailed logs:

- **Console output**: Shows progress and summary
- **Log file**: `address_fixes.log` contains detailed operation logs
- **Error tracking**: Failed operations are logged with reasons

## Safety Features

- **Dry run mode**: Analyze without making changes
- **Incremental processing**: Process sites in batches
- **Audit trail**: All changes are logged with "AI_Copilot_Assistant" as the modifier
- **Rollback support**: Changes follow standard GraphQL patterns for potential rollback