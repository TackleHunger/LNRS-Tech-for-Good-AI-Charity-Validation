# Copilot Instructions for LNRS-Tech-for-Good-AI-Charity-Validation

## Repository Summary

This is a **documentation-only repository** for LexisNexis Risk Solutions (LNRS)'s "Tech for Good" Tackle Hunger AI Charity Validation project. The repository contains comprehensive GraphQL API specifications and field definitions for charity data validation and management systems.

**Key Facts:**
- **Type:** Documentation/Specification repository
- **Size:** Small (~23KB README.md + .gitignore)
- **Languages:** GraphQL schema definitions in Markdown
- **Framework:** GraphQL API specification
- **No code, build system, or tests** - purely documentation

## Build Instructions

⚠️ **IMPORTANT: This is a documentation-only repository with NO build system, tests, or executable code.**

### What Works
- **Documentation editing:** All changes are made directly to Markdown files
- **Git operations:** Standard git commands work normally
- **File validation:** Use standard Markdown linters if available in your environment

### What Doesn't Exist
- No `package.json`, `build`, `test`, or `lint` scripts
- No dependencies to install (`npm install`, `pip install`, etc.)
- No compilation or build steps required
- No test suites to run
- No continuous integration workflows
- No runtime environment or servers to start

### Validation Steps
1. **Markdown syntax:** Ensure proper Markdown formatting
2. **GraphQL schema validity:** Verify GraphQL type definitions are syntactically correct
3. **Documentation completeness:** Check that all field descriptions are clear and accurate
4. **Consistency:** Ensure field names and types match across different sections

### Making Changes
1. Edit files directly using text editor
2. Commit changes with descriptive messages
3. No additional build or validation steps required

## Project Layout and Architecture

### Repository Structure
```
/
├── .github/
│   └── copilot-instructions.md  # This file
├── .gitignore                   # Node.js/JavaScript gitignore patterns
└── README.md                    # Complete API specification (22KB)
```

### Core Architecture Elements

**README.md Structure:**
- **Table of Contents:** Navigation for large document
- **Relevant Charity Fields section:** Complete GraphQL schema definitions
- **Fields to Pull:** Query types and field descriptions for fetching data
  - `SiteForAI` type definition
  - `OrganizationForAI` type definition
- **Fields to Push:** Mutation input types for creating/updating data
  - `siteInputForAI` for creation
  - `siteInputForAIUpdate` for updates
  - `organizationInputUpdate` for organization updates
- **Potential Projects section:** Implementation guidance and goals

### Key GraphQL Schema Components

**Core Entity Types:**
- **Sites:** Physical service locations (food pickup/distribution points)
- **Organizations:** Parent charity organizations (1-to-many with Sites)
- **Relationships:** Organizations can have multiple Sites, but most have just one

**Critical Field Categories:**
1. **Location Details:** Address, coordinates, place IDs
2. **Contact Information:** Public and internal contact methods
3. **Service Details:** Eligibility, service types, operational status
4. **Backend Fields:** System provenance, workflow states, timestamps

**Important API Patterns:**
- All AI operations must include `createdMethod` and `modifiedBy` fields
- Location changes trigger automatic Google Maps geocoding
- Email fields have validation requirements (isEmail, isLowercase)
- Character limits on text fields (250-500 chars for descriptions)

### Configuration Files
- **.gitignore:** Standard Node.js patterns (indicates potential future code development)
- **No other config files:** No linting, build, or framework configuration

### Dependencies and Validation
- **No explicit dependencies** beyond GraphQL API endpoint
- **Validation occurs server-side** when data is pushed to the API
- **Google Maps integration** for location standardization (server-side)
- **Feeding America network** integration for charity verification

### Key Source Content Summary

**README.md Key Sections:**
- Lines 18-122: `SiteForAI` type (complete field definitions)
- Lines 130-177: `OrganizationForAI` type (organization fields)
- Lines 189-269: `siteInputForAI` input type (creation schema)
- Lines 283-361: `siteInputForAIUpdate` input type (update schema)  
- Lines 380-414: `organizationInputUpdate` input type (organization updates)
- Lines 416-456: Implementation goals and project deliverables

**Critical Implementation Notes:**
- New Sites automatically create blank Organizations unless `organizationId` specified
- Location fields trigger Google Maps geocoding when changed
- AI programs MUST populate `createdMethod` and `modifiedBy` fields
- Deduplication is critical for charity management
- Data reliability scoring recommended for automated approval

### Working with This Repository

**When making documentation changes:**
1. Focus on accuracy of GraphQL schema definitions
2. Maintain consistency between input/output type definitions
3. Preserve field validation requirements and character limits
4. Keep implementation guidance current with API capabilities
5. Ensure cross-references between sections remain valid

**Common tasks:**
- Updating field descriptions for clarity
- Adding new field definitions to schema types
- Modifying validation requirements or character limits
- Updating implementation examples and best practices
- Adding new project goals or deliverables

**Trust these instructions:** This repository contains only documentation. Do not search for build scripts, test files, or executable code - they do not exist. Focus on improving documentation clarity, accuracy, and completeness.