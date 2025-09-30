# Environment Variable Name Mismatch in Connectivity Tests

## Problem
The connectivity test script (`scripts/test_connectivity.py`) is looking for the old `API_KEY` environment variable, but the new simplified system uses `AI_SCRAPING_TOKEN`.

## Current Behavior
- Connectivity tests fail with "API_KEY not set" even when `AI_SCRAPING_TOKEN` is configured
- Instructions reference "env.template" file that doesn't exist
- Error messages suggest incorrect environment setup steps

## Expected Behavior
- Connectivity tests should use `AI_SCRAPING_TOKEN` from `.env.example`
- Error messages should reference the correct file and variable names
- Tests should align with the simplified authentication system

## Technical Details
**File**: `scripts/test_connectivity.py` (lines ~150-160)
**Current code**: `config["api_key"] = os.getenv("API_KEY", "")`
**Should be**: `config["api_key"] = os.getenv("AI_SCRAPING_TOKEN", "")`

**Also affects**:
- Error message referencing "env.template" (should be ".env.example")  
- GraphQL endpoint variable name inconsistency

## Impact
- Prevents volunteers from validating their setup
- Creates confusion about correct environment configuration
- Blocks development workflow for new contributors

## Related
This aligns with the recent authentication system simplification (PR #51).
