# Data Exploration for Missing Charity Information

This document describes the data exploration functionality created to identify organizations and charities with missing data elements.

## Overview

The data exploration system analyzes both Sites (charity service locations) and Organizations (parent charity entities) to identify missing essential and important data fields. This helps prioritize data collection efforts and improve data completeness.

## Key Components

### 1. OrganizationOperations (`src/tackle_hunger/organization_operations.py`)

Provides GraphQL operations for fetching and analyzing organization data:

- `get_organizations_for_ai()` - Fetch organizations with all relevant fields
- `get_organization_by_id()` - Fetch specific organization details
- `update_organization()` - Update organization information

### 2. DataExplorer (`src/tackle_hunger/data_explorer.py`)

Analyzes data completeness and generates insights:

- **Field Classification**:
  - **Essential Site Fields**: name, streetAddress, city, state, zip, publicEmail, publicPhone
  - **Important Site Fields**: website, description, serviceArea, acceptsFoodDonations, ein, contact details
  - **Essential Org Fields**: name
  - **Important Org Fields**: address, contact, description, ein, Feeding America affiliation

- **Analysis Functions**:
  - `analyze_site_completeness()` - Analyze individual site data completeness
  - `analyze_organization_completeness()` - Analyze individual organization data completeness
  - `explore_sites_data()` - Comprehensive site data analysis
  - `explore_organizations_data()` - Comprehensive organization data analysis
  - `generate_comprehensive_report()` - Full analysis with recommendations

### 3. Exploration Script (`scripts/explore_data_alesha.py`)

Command-line tool for running data exploration:

```bash
python scripts/explore_data_alesha.py [OPTIONS]
```

#### Options:
- `--sites-limit N` - Number of sites to analyze (default: 50)
- `--orgs-limit N` - Number of organizations to analyze (default: 50)
- `--output-file FILE` - Save detailed JSON report to file
- `--environment ENV` - API environment (dev/staging/production)
- `--summary-only` - Show only summary without saving detailed report

## Usage Examples

### Basic Analysis
```bash
# Analyze 50 sites and 50 organizations, show summary
python scripts/explore_data_alesha.py --summary-only

# Analyze more data points
python scripts/explore_data_alesha.py --sites-limit 100 --orgs-limit 75
```

### Detailed Analysis with Report
```bash
# Generate full report with custom output file
python scripts/explore_data_alesha.py \
  --sites-limit 200 \
  --orgs-limit 150 \
  --output-file charity_data_analysis.json
```

### Programmatic Usage
```python
from src.tackle_hunger import TackleHungerClient, DataExplorer

# Setup client
client = TackleHungerClient()
explorer = DataExplorer(client)

# Generate comprehensive report
report = explorer.generate_comprehensive_report(
    sites_limit=100, 
    orgs_limit=100
)

# Print summary
explorer.print_summary(report)

# Save detailed report
explorer.save_report(report, "analysis_results.json")
```

## Report Structure

The analysis generates a comprehensive report with:

### Executive Summary
- Total entities analyzed
- Entities with essential data gaps
- Overall data gap percentage
- Average completeness scores

### Detailed Analysis
- **Sites Analysis**: Missing field counts, most problematic sites
- **Organizations Analysis**: Missing field counts, most problematic organizations
- **Recommendations**: Prioritized actions based on findings

### Field-Specific Insights
- Count of missing data by field
- Percentage of entities missing each field
- Priority ranking for data collection efforts

## Completeness Scoring

Each entity receives a completeness score (0.0 to 1.0) calculated as:
- Essential fields are weighted 2x
- Important fields are weighted 1x
- Score = (complete_essential × 2 + complete_important) / (total_essential × 2 + total_important)

## Key Findings Categories

### Essential Data Gaps
Entities missing critical fields required for basic functionality:
- Site: Missing address, contact information
- Organization: Missing name

### Important Data Gaps  
Entities missing valuable but not critical fields:
- Missing descriptions, websites, service details
- Missing EIN numbers, affiliation information

## Recommendations Engine

The system automatically generates prioritized recommendations:

1. **High Priority**: Focus on most commonly missing essential fields
2. **Medium Priority**: Address important fields with high miss rates
3. **System Improvements**: Suggestions for validation and data collection

## Integration with Existing Workflow

This analysis integrates with the existing charity validation workflow:

1. **Data Collection Planning**: Identify priority fields for AI/ETL operations
2. **Quality Assurance**: Monitor data completeness over time
3. **Volunteer Focus**: Direct volunteer efforts to highest-impact data gaps
4. **API Enhancement**: Inform required field validation improvements

## Error Handling

The system includes robust error handling for:
- Network connectivity issues
- API authentication problems
- Missing or malformed data
- GraphQL schema changes

## Future Enhancements

Potential improvements for the data exploration system:

1. **Historical Tracking**: Monitor data completeness trends over time
2. **Geographic Analysis**: Identify regional data quality patterns
3. **Automated Alerts**: Notify when data quality drops below thresholds
4. **Integration Testing**: Validate against different API environments
5. **Performance Optimization**: Handle larger datasets efficiently

## Testing

Comprehensive test coverage includes:
- Unit tests for all analysis functions
- Mock data scenarios for edge cases
- Integration tests for GraphQL operations
- Command-line interface testing

Run tests with:
```bash
python -m pytest tests/ -v
```