# GitHub Copilot Instructions for Tackle Hunger Charity Validation

## Project Overview

This repository supports LexisNexis Risk Solutions' "Tech for Good" initiative for Tackle Hunger charity validation. The project involves validating and updating charity information through GraphQL API operations.

## Key Systems and APIs

### GraphQL API
- **Staging Environment**: Used for development and testing
- **Production Environment**: Live charity data operations
- **Operations**: Site and Organization CRUD operations for charity validation

### Google Maps Integration
- Geocoding API for address standardization
- Place Details API for location verification

## Development Focus Areas

### Core Operations
1. **Site Management**: Charity service locations with address, contact, and service details
2. **Organization Management**: Parent charity organizations
3. **Data Validation**: AI/API/ETL operations for charity information verification
4. **Location Standardization**: Address verification and geocoding

### Key Data Structures
- Sites (service locations) - 1-to-many relationship with Organizations
- Organizations (parent charity entities)
- Contact information (public and internal)
- Service details (eligibility, place types, service types)

## Environment Configuration

The project uses GitHub Environment secrets stored in the "copilot" environment for:
- GraphQL API endpoints and authentication
- Google Maps API keys
- Other backend system credentials

## Development Language

**Primary Language**: Python 3.13
- Focus on GraphQL client operations
- Data validation and transformation
- API integration and error handling

## Volunteer Guidelines

This codebase is designed for volunteers with limited time who need to be immediately productive. Code should be:
- Well-documented and self-explanatory
- Modular and reusable
- Error-resistant with clear failure modes
- Aligned with charity validation workflows

## Data Quality Standards

When working with charity data:
- Validate all address information
- Ensure contact details are properly formatted
- Handle missing or incomplete data gracefully
- Maintain data provenance tracking (createdMethod, modifiedBy fields)
- Respect pending status workflows for data approval