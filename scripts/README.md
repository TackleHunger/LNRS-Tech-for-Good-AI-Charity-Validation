# Scripts Directory

This directory contains utility scripts for the Tackle Hunger charity validation project.

## Available Scripts

### `export_sites_to_csv.py` - Production Export Script

Fetches the first 10 charity sites from the `sitesForAI` GraphQL endpoint and exports them to a CSV file.

**Usage:**
```bash
python scripts/export_sites_to_csv.py
```

**Requirements:**
- Valid API credentials in `.env` file
- Network access to the GraphQL API endpoint
- Proper authentication token

**Output:**
- Creates a timestamped CSV file: `sites_for_ai_YYYYMMDD_HHMMSS.csv`
- Contains all fields from the GraphQL API response
- Handles missing/null values gracefully

### `export_sites_demo.py` - Demo Script with Mock Data

Demonstrates the export functionality using realistic mock data when API credentials are not available.

**Usage:**
```bash
python scripts/export_sites_demo.py
```

**Requirements:**
- No API credentials needed
- Works offline

**Output:**
- Creates a timestamped CSV file: `sites_for_ai_demo_YYYYMMDD_HHMMSS.csv`
- Contains 10 realistic charity records
- Same format as the production script

### `setup_dev_environment.py` - Environment Setup

Sets up the development environment for volunteers.

**Usage:**
```bash
python scripts/setup_dev_environment.py
```

### `test_connectivity.py` - Network Connectivity Test

Tests network access to required APIs and services.

**Usage:**
```bash
python scripts/test_connectivity.py
```

## CSV Output Format

Both export scripts generate CSV files with the following fields:

| Field | Description |
|-------|-------------|
| `id` | Unique site identifier |
| `organizationId` | Parent organization identifier |
| `name` | Site/charity name |
| `streetAddress` | Street address |
| `city` | City |
| `state` | State abbreviation |
| `zip` | ZIP/postal code |
| `publicEmail` | Public contact email |
| `publicPhone` | Public contact phone |
| `website` | Website URL |
| `description` | Site description |
| `serviceArea` | Geographic service area |
| `acceptsFoodDonations` | Whether site accepts food donations (YES/NO/UNKNOWN) |
| `status` | Site status (ACTIVE/PENDING/INACTIVE) |
| `ein` | Tax ID number |

## Error Handling and Troubleshooting

The production script includes comprehensive error handling:

- **Authentication Errors**: Prompts to check API credentials
- **GraphQL Schema Errors**: Suggests running the demo version
- **Network Errors**: Points to firewall configuration documentation
- **Generic Errors**: Provides troubleshooting steps

## Example Output

```csv
acceptsFoodDonations,city,description,ein,id,name,organizationId,publicEmail,publicPhone,serviceArea,state,status,streetAddress,website,zip
YES,Springfield,Serving families in downtown Springfield with fresh produce and pantry staples.,12-3456789,123e4567-e89b-12d3-a456-426614174000,Downtown Food Bank,987fcdeb-51d2-4321-9876-123456789abc,info@downtownfoodbank.org,(217) 555-0123,Downtown Springfield,IL,ACTIVE,123 Main St,https://downtownfoodbank.org,62701
```

## Development Notes

- Both scripts use the same CSV writing logic for consistency
- Mock data is designed to be realistic and representative
- Error messages include specific guidance for common issues
- All scripts are executable and include proper shebang lines
- CSV handling includes proper encoding (UTF-8) and null value management