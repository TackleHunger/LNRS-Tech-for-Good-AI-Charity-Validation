# Data Exploration Guide

This guide explains how to use the data exploration functionality to identify organizations and charities missing data elements.

## Overview

The data exploration system provides comprehensive analysis of charity data quality by:

- Fetching organizations and sites from the Tackle Hunger GraphQL API
- Analyzing missing or incomplete data fields
- Generating reports with actionable insights
- Calculating data completeness scores
- Providing recommendations for data quality improvements

## Quick Start

### Using the CLI Script

The easiest way to explore data is using the provided CLI script:

```bash
# Basic usage - analyze 100 sites and organizations
python scripts/explore_data.py

# Analyze more data
python scripts/explore_data.py --sites 500 --organizations 200

# Get only summary (faster)
python scripts/explore_data.py --summary-only

# Export detailed report
python scripts/explore_data.py --output report.json

# Use different environment
python scripts/explore_data.py --environment staging
```

### Using the Python API

For more advanced usage, you can use the Python API directly:

```python
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.data_explorer import DataExplorer

# Initialize client
client = TackleHungerClient()
explorer = DataExplorer(client)

# Get comprehensive analysis
analysis = explorer.get_missing_data_analysis(site_limit=100, org_limit=100)

# Get summary with recommendations
summary = explorer.get_data_completeness_summary(site_limit=100, org_limit=100)

# Export detailed report
explorer.export_missing_data_report("analysis.json", site_limit=100, org_limit=100)
```

## Report Structure

### Summary Report

The summary report includes:

- **Data Overview**: Total counts of sites and organizations analyzed
- **Completeness Scores**: Graded scores (A-F) for data completeness
- **Data Integrity Issues**: Orphaned sites, incomplete organizations
- **Recommendations**: Top actionable recommendations

### Detailed Analysis

The detailed analysis includes:

#### Sites Analysis
- Field-by-field missing data statistics
- List of sites with critical missing fields
- Percentage of missing data for each field

#### Organizations Analysis  
- Field-by-field missing data statistics for organizations
- List of organizations with critical missing fields
- Percentage of missing data for each field

#### Combined Analysis
- Orphaned sites (sites without valid organization references)
- Sites with incomplete organization data
- Data integrity statistics

## Field Classifications

### Critical Fields (Sites)
- `name` - Site name
- `streetAddress` - Physical address
- `city` - City location
- `state` - State location
- `zip` - ZIP code
- `publicEmail` - Public contact email
- `publicPhone` - Public contact phone
- `website` - Website URL
- `description` - Service description

### Optional Fields (Sites)
- `serviceArea` - Service coverage area
- `acceptsFoodDonations` - Food donation acceptance
- `ein` - Tax ID number

### Critical Fields (Organizations)
- `name` - Organization name
- `streetAddress` - Mailing address
- `city` - City location
- `state` - State location
- `zip` - ZIP code
- `publicEmail` - Public contact email
- `publicPhone` - Public contact phone

### Optional Fields (Organizations)
- `addressLine2` - Address line 2
- `email` - Internal contact email
- `phone` - Internal contact phone
- `website` - Website URL
- `description` - Organization description
- `ein` - Tax ID number
- `nonProfitStatus` - Non-profit status

## Completeness Scoring

The system calculates weighted completeness scores:

- **Critical Fields**: 70% weight
- **Optional Fields**: 30% weight

Grades are assigned as follows:
- **A**: 90-100% complete
- **B**: 80-89% complete
- **C**: 70-79% complete
- **D**: 60-69% complete
- **F**: Below 60% complete

## Common Use Cases

### 1. Initial Data Quality Assessment

```bash
python scripts/explore_data.py --summary-only
```

This provides a quick overview of data quality across your charity database.

### 2. Detailed Gap Analysis

```bash
python scripts/explore_data.py --sites 1000 --organizations 500 --output full_analysis.json
```

This generates a comprehensive analysis for further investigation.

### 3. Environment-Specific Analysis

```bash
python scripts/explore_data.py --environment staging --summary-only
```

This analyzes data quality in different environments.

### 4. Targeted Analysis

```python
# Focus on specific issues
analysis = explorer.get_missing_data_analysis(site_limit=50, org_limit=50)

# Find sites with missing critical contact info
sites_missing_contact = []
for site in analysis['sites']['sites_with_critical_missing']:
    missing_fields = site['missing_fields']
    if 'publicEmail' in missing_fields or 'publicPhone' in missing_fields:
        sites_missing_contact.append(site)
```

## Troubleshooting

### Authentication Issues

Ensure your `.env` file contains valid credentials:

```
AI_SCRAPING_TOKEN=your_token_here
TKH_GRAPHQL_API_URL=https://devapi.sboc.us/graphql
```

### Rate Limiting

If you encounter rate limits, reduce the number of records analyzed:

```bash
python scripts/explore_data.py --sites 50 --organizations 25
```

### Memory Issues

For large datasets, use the summary-only mode:

```bash
python scripts/explore_data.py --summary-only
```

## Contributing

When adding new data exploration features:

1. Add appropriate field classifications in `DataExplorer`
2. Update scoring algorithms if needed
3. Add comprehensive tests
4. Update this documentation

## Examples

See the test files for examples of using the data exploration API:
- `tests/test_data_explorer.py` - Comprehensive API examples
- `tests/test_organization_operations.py` - Organization data access examples