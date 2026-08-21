# LNRS-Tech-for-Good-AI-Charity-Validation

## Table of Contents

- [Charity Data & Local Setup](#charity-data--local-setup)
- [Target Goals / Deliverables / Potential Projects](#potential-projects--target-goals--deliverables)
- [Relevant Charity Fields](#relevant-charity-fields)
  - [Fields to Pull](#fields-to-pull)
    - [Fetching Sites](#fetching-sites)
    - [Fetching Organizations](#fetching-organizations)
  - [Fields to Push](#fields-to-push)
    - [Create Site](#create-site)
    - [Update Site](#update-site)
    - [Create Organization](#create-organization)
    - [Update Organization](#update-organization)

## Charity Data & Local Setup

> **Separation of concerns:** real charity contact data is kept **out** of this
> (public) repository. The source code, dashboard UI, and a schema-only sample
> file are all that live here. The real data is loaded at runtime from
> git-ignored files.

### What is git-ignored (never committed)

The following contain real charity contact data and are listed in
[.gitignore](.gitignore). They are produced at runtime (locally or in CI) or
distributed out-of-band:

| File | Role |
|------|------|
| `charity-data.json` | Canonical, consolidated charity contact dataset (data-access layer reads this). |
| `sites_batch.json` | Batch of sites pulled from the Tackle Hunger API. |
| `ai_validation_report.json` | Full per-field AI validation output (consumed by the dashboard). |
| `dashboard_summary.json` | Summary metrics rendered by the dashboard. |
| `latest_summary.json`, `batch_history.json`, `coverage_ledger.json`, `review_log.json`, `web_evidence_report.json`, `writeback_preview.json` | Other generated pipeline artifacts. |

Every git-ignored data file has a committed **`*.example_synthpii.json`** companion
with placeholder (non-real) records that documents the expected schema. See
[charity-data.example_synthpii.json](charity-data.example_synthpii.json). The
`_synthpii` suffix is a PII-scanner *earlySkip* marker: it tells the PII checker
these files hold only synthetic sample data and should be ignored, so they never
trip the PR PII gate.

### Centralized data-access layer

All charity data is loaded through a single module — do **not** hardcode
contact values in code:

- **Python:** [src/tackle_hunger/charity_data.py](src/tackle_hunger/charity_data.py)
  ```python
  from tackle_hunger.charity_data import load_charity_data, iter_sites, get_site

  data = load_charity_data()      # -> {schema_version, sites: [...], ...}
  sites = iter_sites()            # -> list of CharitySite dicts (empty if no data)
  site = get_site("EXAMPLE001")   # -> CharitySite | None
  ```
  If `charity-data.json` is missing or malformed, the loader logs a warning and
  returns an **empty** dataset instead of raising — callers degrade gracefully.

- **Dashboard (JS):** [dashboard.html](dashboard.html) loads each data file via a
  `loadData(name)` helper that tries `<name>.json` first and falls back to the
  committed `<name>.example_synthpii.json`, showing a "sample placeholder data"
  banner when real data is absent.

### Running the dashboard

The dashboard is a single static file that loads its data with `fetch()`.
Because browsers block `fetch()` on `file://` URLs, **opening `dashboard.html`
by double-clicking will not work** — serve it over HTTP instead:

```bash
python -m http.server 8000
# then open http://localhost:8000/dashboard.html
```

With no real data present it renders the committed `*.example_synthpii.json`
placeholders and shows a "sample placeholder data" banner. Drop real
`*.json` artifacts (e.g. `dashboard_summary.json`) next to `dashboard.html`
to see live results.

A **live demo** (placeholder data only) is published to GitHub Pages by the
[Deploy Demo Dashboard](.github/workflows/deploy-demo-dashboard.yml) workflow.
Enable it under **Settings → Pages → Source: GitHub Actions**; the deployed
site never contains real charity data.

### First-time setup

1. **Clone the repo.** With no data files present, the pipeline and dashboard
   run against the committed `*.example_synthpii.json` placeholders.
2. **Obtain the real data** by either:
   - **Reconstruct locally from the pipeline:**
     ```bash
     python scripts/pull_batch.py --limit 50      # requires AI_SCRAPING_TOKEN + ENVIRONMENT
     python scripts/build_charity_data.py         # writes charity-data.json
     ```
   - **or** drop in a `charity-data.json` distributed through your team's secure
     channel (it matches `charity-data.example_synthpii.json`'s schema).
   - Optionally point the loader elsewhere with the `CHARITY_DATA_PATH`
     environment variable.
3. **Never commit** `charity-data.json` or any of the git-ignored artifacts
   above. `.gitignore` already blocks them.

> **⚠️ Publishing note:** `.gitignore` stops *future* commits of these files, but
> if real data was committed previously it still exists in **git history**.
> Purge it with `git filter-repo` (or BFG) before making the repository public.

## Deploying in the TackleHunger org

This repository is the **sanitized code foundation** — pipeline code, dashboard
UI, tests, and *schema-only* sample data, with **no real charity data** and no
data-bearing git history. To turn it into a live, operational instance in the
TackleHunger organization, reconnect the data and automation there (none of this
needs to touch the committed history):

1. **Add repository secrets** (Settings → Secrets and variables → Actions):
   - `AI_SCRAPING_TOKEN` — auth token for the Tackle Hunger GraphQL API (required).
   - Optionally `SERPER_API_KEY` / `BING_SEARCH_API_KEY` for higher-quality web
     evidence, and set `ENVIRONMENT` (`dev` / `staging` / `production`).

2. **Re-add the operational pipeline workflow.** The public snapshot intentionally
   ships only the placeholder-only [Deploy Demo Dashboard](.github/workflows/deploy-demo-dashboard.yml)
   workflow. The original scheduled validation workflow (pull → web evidence →
   AI validate → aggregate) was removed because it committed **real** data back to
   the repo. Re-introduce it in the private/org context so it:
   - runs on a cron / manual dispatch using the secrets above, and
   - publishes its outputs as **build artifacts** (or to a private data store) —
     **never** `git add -f` of the real `*.json` artifacts into the repo.

3. **Provision `charity-data.json`** in the runtime environment via
   `python scripts/build_charity_data.py` (or your team's secure channel). It stays
   git-ignored; the loader falls back to placeholders when it's absent.

4. **Enable GitHub Pages** (Settings → Pages → Source: GitHub Actions). The demo
   dashboard workflow then deploys automatically. *(Pages is disabled on Enterprise
   Managed User accounts, so this step only works in a standard org/repo.)*

5. **Confirm the PII PR check passes.** The synthetic fixtures and sample data carry
   the scanner's `_synthpii` *earlySkip* marker, so the automated PII check skips
   them instead of flagging the fictional records on every PR.

> **Keep data and code separate.** The guiding principle is that this repo holds
> *the machine* (safe to share) and never *the fuel* (real charity data + secrets,
> kept private). Any automation added here must preserve that separation.

### Integration contract (wire it however you like)

The deployment steps above are one concrete recipe (GitHub Actions). The code
itself is **platform-neutral**: it talks to the outside world through a small,
stable contract, so you can host and orchestrate it with whatever tooling you
prefer (GitHub Actions, Azure DevOps, Airflow, a container job, a manual run —
your choice). To go live you only need to satisfy three things:

**1. Inputs — provide configuration via environment variables.** Nothing is
hardcoded; inject these from any secret store (Actions secrets, Azure Key Vault,
AWS/GCP Secrets Manager, a mounted `.env`, container env, etc.):

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `AI_SCRAPING_TOKEN` | Required (non-`dev`) | Auth token for the Tackle Hunger GraphQL API. |
| `ENVIRONMENT` | Optional | `production` / `staging` / `dev` — selects the API endpoint. |
| `SERPER_API_KEY` / `BING_SEARCH_API_KEY` | Optional | Higher-quality web-evidence enrichment. |
| `CHARITY_DATA_PATH` | Optional | Read `charity-data.json` from a custom (e.g. mounted) location. |

See [src/tackle_hunger/graphql_client.py](src/tackle_hunger/graphql_client.py)
for the exact resolution logic and endpoint map.

**2. Outputs — produce the JSON files the dashboard reads.** Run the pipeline
(`pull_batch` → `web_evidence` → `ai_validate` → `aggregate_summary` →
`build_charity_data`) on whatever schedule/trigger you want, and make its
artifacts available next to `dashboard.html`. The dashboard's `loadData()`
helper reads plain files (`dashboard_summary.json`, `charity-data.json`, …) and
falls back to the committed `*.example_synthpii.json` placeholders when they are
absent — so "going live" is simply making the real files present in the runtime
environment.

**3. The one invariant — never commit real data or secrets back into the repo.**
Publish pipeline outputs as build artifacts or to a private data store; do not
`git add` the real `*.json` files or tokens. This is the single rule that keeps
the public repository safe. Everything between the inputs and outputs — secret
storage, scheduling, hosting, whether to enable API write-back — is yours to
design.

## Target Goals / Deliverables / Potential Projects

- Common to each:

  - store mailing address separately if it differs from the food pickup/dropoff address
    - _a non-food-service address like a PO box goes on the related Organization, as opposed to the Site (see schemas)_
  - ensure they're open year-round (as opposed to seasonal, like school or summer programs)
  - potentially have the AI give a data-reliability score for each result
    - i.e. higher if verified from multiple sources, favored sources, conforms to key phrases
    - _in our current setup, new Charities submitted are marked Pending until a human does a quick check - this could help with that review_
    - could also potentially push very good ones to our API to immediately go live  (_i.e. not Pending_)
  - automate it - deliver some amount of infrastructure-as-code that'd run it automatically (i.e. github actions, crons, webhook triggers, etc.)

1. Find Info that our Current Charities are Missing & Verify their Operational Status

   - i.e. blank, missing, or really poor quality field values
   - push fields that were previously empty to our API (_`mutation updateSiteFromAI`_) - if you think they're good enough we can save them immediately
   - store a copy of our original data & the new recommended data at that moment in time, as well as links to our Site/Org & to the new source
     - _in a new storage bucket or DB for this project_

2. Scrape Facebook for Charities  (_added to any of these other projects_)

   - would probably be best as a helper-function to run within any of these other automated-scraping goals
   - _many of our Charities don't have main websites and use social media as their only up-to-date source on hours, status, & contact info_
   - _we don't have experience automating this yet, would love help_

3. Find New Charities that we don't currently have

   - requires serious & careful deduplication - _it's counter-productive if we have to manually deal with multiples of the same charity_
   - find trustworthy values for as many fields as possible & fill them in
   - push them to our API (_`mutation addCharityFromAI`_)
     - _new additions are Pending until a member of the Tackle Hunger team approves them_
   - potentially, if the AI gives a data-reliability score, push very good ones to our API to immediately go live  (_i.e. not Pending_)
     - would require an additional endpoint/mutation or changes to the current one - TBD

4. Re-check our Current Charities to Find Newer Data & Flag ones that might have changed

   - store a copy of our original data & the new recommended data at that moment in time, as well as links to our Site/Org & to the new source
     - _in a new storage bucket or DB for this project_
   - potentially, if the AI gives a data-reliability score, push very good ones to our API to immediately go live (_`mutation updateSiteFromAI`_)

## Relevant Charity Fields

In the Tackle Hunger Map app, Charities are stored as an Organization & a Site (service location). Charities can have more than 1 service location so Org--<Site is a 1-to-Many relation (however, the vast majority have just 1 Site). Most information is on Sites - charities that haven't interacted with the app yet typically have mostly blank Organization fields.

The only other relevant relations (EligiblePopulations, PlaceTypes, & ServiceTypes) are internally handled - just reference the Schema's Scalar definition for each.

The full Schema is visible on the Staging API GraphQL Playground.

### Fields to Pull

#### Fetching Sites

Relevant Sites fields to fetch are defined in the GraphQL Schema `type SiteForAI`. Request the appropriate ones for your usage in `sitesForAI` queries.

Here they are ordered for clarity & explained:

```gql
type SiteForAI {
  ### CORE (IDs & Important Direct Joined Relations)
  #
  id: ID! # string, primary key, exclude from web searches to avoid false-positive matches
  organizationId: ID! # string, foreign key, exclude from web searches to avoid false-positive matches
  organization: OrganizationForAI # M-to-1
  ###

  ### LOCATION DETAILS (Food Pickup/Dropoff/Distribution Address, avoid PO Boxes)
  #
  # Any of these 4 changed triggers internal Location-Standardizing
  streetAddress: String # required for creation
  city: String # required for creation
  state: String # required for creation
  zip: String # required for creation
  #
  name: String # required for creation, only updated on first Location-Standardizing triggered
  addressLine2: String # only updated if blank when Location-Standardizing is triggered
  country: Country # see scalar options, default can be 'US', updated if Location-Standardizing triggered
  county: String # updated if Location-Standardizing triggered, not very important
  neighborhood: String # updated if Location-Standardizing triggered, not very important
  lat: Float # updated if Location-Standardizing triggered
  lng: Float # updated if Location-Standardizing triggered
  ###

  ### CONTACT DETAILS
  #
  publicEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  publicPhone: String
  socialMedia: String
  website: String
  publicContactMethod: String # which public method is preferred? ('Email','Phone','Social Media','Website')
  #
  # Direct Internal Contact fields, not public, less likely found by AI
  contactEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  contactName: String
  contactPhone: String
  #
  # Direct Finance Manager Contact fields, not public, less likely found by AI, really valuable if available
  financialControllerEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  financialControllerPhone: String
  ###

  ### SITE SERVICE DETAILS
  #
  status: BusinessStatus # see scalar options, updated if Location-Standardizing triggered
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  efroid: String # New York State specific, not very important
  acceptsFoodDonations: YesNoEnum # see scalar options
  #
  eligiblePopulations: [EligiblePopulation!]! # see scalar options, M-to-M
  placeTypes: [PlaceType!]! # see scalar options, updated if Location-Standardizing triggered, M-to-M
  serviceTypes: [ServiceType!]! # see scalar options, M-to-M
  #
  # Multiline Text fields
  description: String # max 500 char, public & donor-facing summary, ideally around 50 words
  serviceArea: String # max 250 char, Do you have a specific service area? (counties, neighborhoods, zip codes, etc.)
  requiredDocuments: String # max 250 char, Are first-time clients required to bring any documents? (State ID, Proof of Residence, etc.)
  hoursText: String # max 250 char, When is food available at your site?
  accessInfoText: String # max 500 char, Any other specifics someone seeking assistance at this site needs to know? (like a separate entrance) do not repeat info in other fields
  #
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  #
  # Food-Availability fields, unlikely found by AI, maintained by Charity Representatives
  disasterPrepared: YesNoEnum # prepared to distribute food during a disaster, see scalar options
  stockStatus: Int # (0, 1, 2, 3, 4), current food-availability
  ###

  ### BACKEND FIELDS (system provenance & workflow)
  #
  pendingStatus: PendingStatus # approval workflow state, see scalar options
  lastUserModifiedAt: Date # when a Charity Representative last modified this site
  staffConfirmedAt: Date # when a Tackle Hunger Staff member last confirmed this site is valid
  #
  # Human-Readable Partner/Service/Run Identifiers if AI/API/ETL Operation, consistent per partner/service/run
  createdMethod: String # required when AI/API/ETL-created, AI Programs Must Push This When Creating
  modifiedBy: String # required when AI/API/ETL-modified, AI Programs Must Push This When Updating
  #
  dataSource: String # URI or human-readable identifier if found on foreign source list/table/DB with IDs
  dataSourceId: ID # id from the foreign source (if from one with IDs)
  #
  createdAt: Date!
  updatedAt: Date!
  ###
}
```

#### Fetching Organizations

Relevant Organization fields to fetch are defined in the GraphQL Schema `type OrganizationForAI`. Request the appropriate ones for your usage in `organizationsForAI` queries.

Here they are ordered for clarity & explained:

```gql
type OrganizationForAI {
  ### CORE (IDs & Important Direct Joined Relations)
  #
  id: ID! # string, primary key, exclude from web searches to avoid false-positive matches
  sites: [SiteForAI!]! # each Organization must have at least 1 Site, 1-to-M
  ###

  ### LOCATION DETAILS
  #
  # Parent Organization Mailing Address, PO box is fine, public but not shown on the Map
  name: String # Charity's Registered Name
  streetAddress: String
  addressLine2: String
  city: String
  state: String
  zip: String
  ###

  ### CONTACT DETAILS
  #
  publicEmail: String
  publicPhone: String
  #
  # Direct Internal Contact fields, not public, less likely found by AI
  email: String
  phone: String
  ###

  ### PARENT CHARITY ORGANIZATION DETAILS
  #
  isFeedingAmericaAffiliate: YesNoEnum # Does this Charity Org or any of its Sites: (1) exist in Feeding America's Network? or (2) collaborate with FA? or (3) receive support from FA? or (4) exist in the network of a Food Bank or collaborate with or receive support from a Food Bank that does (1), (2), or (3)?
  #
  # Especially include these if they differ from its Site(s)
  description: String # multiline text, max 500 char, public & donor-facing summary, ideally around 50 words
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  ###

  ### BACKEND FIELDS (Timestamps)
  #
  updatedAt: Date!
  createdAt: Date!
  ###
}
```

### Fields to Push

#### Create Site

Relevant fields to push when creating a Site are defined in the GraphQL Schema `input siteInputForAI`, a variable used in the `addCharityFromAI` mutation.

`siteId: String` is a separate variable required for the `addCharityFromAI` mutation.

Most `siteInputForAI` fields can be omitted if not intending to set with a value. The 3 Scalar arrays can be omitted, but if included they can't be empty. Only the 5 String fields marked with `!` are required.

Here they are ordered for clarity & explained:

```gql
input siteInputForAI {
  ### LOCATION DETAILS (Food Pickup/Dropoff/Distribution Address, avoid PO Boxes)
  #
  # Any of these 4 changed triggers internal Location-Standardizing
  streetAddress: String! # required for creation
  city: String! # required for creation
  state: String! # required for creation
  zip: String! # required for creation
  #
  name: String! # required for creation, only updated on first Location-Standardizing triggered
  addressLine2: String # only updated if blank when Location-Standardizing is triggered
  country: Country # see scalar options, default can be 'US', updated if Location-Standardizing triggered
  county: String # updated if Location-Standardizing triggered, not very important
  neighborhood: String # updated if Location-Standardizing triggered, not very important
  lat: Float # updated if Location-Standardizing triggered
  lng: Float # updated if Location-Standardizing triggered
  ###

  ### CONTACT DETAILS
  #
  publicEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  publicPhone: String
  socialMedia: String
  website: String
  publicContactMethod: String # which public method is preferred? ('Email','Phone','Social Media','Website')
  #
  # Direct Internal Contact fields, not public, less likely found by AI
  contactEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  contactName: String
  contactPhone: String
  #
  # Direct Finance Manager Contact fields, not public, less likely found by AI, really valuable if available
  financialControllerEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  financialControllerPhone: String
  ###

  ### SITE SERVICE DETAILS
  #
  status: BusinessStatus # see scalar options, updated if Location-Standardizing triggered
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  efroid: String # New York State specific, not very important
  acceptsFoodDonations: YesNoEnum # see scalar options
  #
  eligiblePopulations: [EligiblePopulation!] # see scalar options, M-to-M
  placeTypes: [PlaceType!] # see scalar options, updated if Location-Standardizing triggered, M-to-M
  serviceTypes: [ServiceType!] # see scalar options, M-to-M
  #
  # Multiline Text fields
  description: String # max 500 char, public & donor-facing summary, ideally around 50 words
  serviceArea: String # max 250 char, Do you have a specific service area? (counties, neighborhoods, zip codes, etc.)
  requiredDocuments: String # max 250 char, Are first-time clients required to bring any documents? (State ID, Proof of Residence, etc.)
  hoursText: String # max 250 char, When is food available at your site?
  accessInfoText: String # max 500 char, Any other specifics someone seeking assistance at this site needs to know? (like a separate entrance) do not repeat info in other fields
  #
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  #
  # Food-Availability fields, unlikely found by AI, maintained by Charity Representatives
  disasterPrepared: YesNoEnum # prepared to distribute food during a disaster, see scalar options
  stockStatus: Int # (0, 1, 2, 3, 4), current food-availability
  ###

  ### BACKEND FIELDS (system provenance & workflow)
  #
  organizationId: ID # string, foreign key, only set if grouping this Site w/ others on a preexisting Organization
  pendingStatus: PendingStatus # approval workflow state, see scalar options
  #
  # Human-Readable Partner/Service/Run Identifiers if AI/API/ETL Operation, consistent per partner/service/run
  createdMethod: String! # required when AI/API/ETL-created, AI Programs Must Push This
  modifiedBy: String # required when AI/API/ETL-modified
  #
  dataSource: String # URI or human-readable identifier if found on foreign source list/table/DB with IDs
  dataSourceId: ID # id from the foreign source (if from one with IDs)
  ###
}
```

#### Update Site

Relevant fields to push when updating a Site are defined in the GraphQL Schema `input siteInputForAIUpdate`, a variable used in the `updateSiteFromAI` mutation.

`siteId: String` is a separate variable required for the `updateSiteFromAI` mutation.

Only a few Organization fields really need to be updated. When a Financial Controller gets invited (which is automatic upon update of `site.financialControllerEmail`), then most Org fields get filled by copying them from its Site. All fields below are welcome if they differ from their Site(s), the Charity is being newly created, or the fields were previously blank.

Any fields not intended to modify can be omitted.

Here they are ordered for clarity & explained:

```gql
input siteInputForAIUpdate {
  ### LOCATION DETAILS (Food Pickup/Dropoff/Distribution Address, avoid PO Boxes)
  #
  # Any of these 4 changed triggers internal Location-Standardizing
  streetAddress: String # required for creation
  city: String # required for creation
  state: String # required for creation
  zip: String # required for creation
  #
  name: String # required for creation, only updated on first Location-Standardizing triggered
  addressLine2: String # only updated if blank when Location-Standardizing is triggered
  country: Country # see scalar options, default can be 'US', updated if Location-Standardizing triggered
  county: String # updated if Location-Standardizing triggered, not very important
  neighborhood: String # updated if Location-Standardizing triggered, not very important
  lat: Float # updated if Location-Standardizing triggered
  lng: Float # updated if Location-Standardizing triggered
  ###

  ### CONTACT DETAILS
  #
  publicEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  publicPhone: String
  socialMedia: String
  website: String
  publicContactMethod: String # which public method is preferred? ('Email','Phone','Social Media','Website')
  #
  # Direct Internal Contact fields, not public, less likely found by AI
  contactEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  contactName: String
  contactPhone: String
  #
  # Direct Finance Manager Contact fields, not public, less likely found by AI, really valuable if available
  financialControllerEmail: String # validated: (isEmail: true, isLowercase: true, notEmpty: false), allows Null
  financialControllerPhone: String
  ###

  ### SITE SERVICE DETAILS
  #
  status: BusinessStatus # see scalar options, updated if Location-Standardizing triggered
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  efroid: String # New York State specific, not very important
  acceptsFoodDonations: YesNoEnum # see scalar options
  #
  eligiblePopulations: [EligiblePopulation!] # see scalar options, M-to-M
  placeTypes: [PlaceType!] # see scalar options, updated if Location-Standardizing triggered, M-to-M
  serviceTypes: [ServiceType!] # see scalar options, M-to-M
  #
  # Multiline Text fields
  description: String # max 500 char, public & donor-facing summary, ideally around 50 words
  serviceArea: String # max 250 char, Do you have a specific service area? (counties, neighborhoods, zip codes, etc.)
  requiredDocuments: String # max 250 char, Are first-time clients required to bring any documents? (State ID, Proof of Residence, etc.)
  hoursText: String # max 250 char, When is food available at your site?
  accessInfoText: String # max 500 char, Any other specifics someone seeking assistance at this site needs to know? (like a separate entrance) do not repeat info in other fields
  #
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  #
  # Food-Availability fields, unlikely found by AI, maintained by Charity Representatives
  disasterPrepared: YesNoEnum # prepared to distribute food during a disaster, see scalar options
  stockStatus: Int # (0, 1, 2, 3, 4), current food-availability
  ###

  ### BACKEND FIELDS (system provenance & workflow)
  #
  organizationId: ID # string, foreign key, only modify if grouping this Site w/ others on a different Organization
  pendingStatus: PendingStatus # approval workflow state, see scalar options
  #
  # Human-Readable Partner/Service/Run Identifiers if AI/API/ETL Operation, consistent per partner/service/run
  modifiedBy: String! # required when AI/API/ETL-modified, AI Programs Must Push This
  #
  dataSource: String # URI or human-readable identifier if found on foreign source list/table/DB with IDs
  dataSourceId: ID # id from the foreign source (if from one with IDs)
  ###
}
```

#### Create Organization

Each Organization must have at least 1 Site to prevent them from getting orphaned  (_so ignore the `createOrganization` mutation - it is deprecated, do not try to use it_).

A new blank Organization is automatically created for each new Site that doesn't specify a preexisting `site.organizationId`.

To add fields to a newly created Organization, first create the Site (`addCharityFromAI` mutation) & request `organizationId` in the response, then use that to update Organization fields via the `updateOrganizationFromAI` mutation explained below.

#### Update Organization

Relevant fields to push when updating an Organization are defined in the GraphQL Schema `input organizationInputUpdate`, a variable used in the `updateOrganizationFromAI` mutation.

`organizationId: String` is a separate variable required for the `updateOrganizationFromAI` mutation.

Any fields not intended to modify can be omitted.

Here they are ordered for clarity & explained:

```gql
input organizationInputUpdate {
  ### LOCATION DETAILS
  #
  # Parent Organization Mailing Address, PO box is fine, public but not shown on the Map
  name: String! # Charity's Registered Name, required when updating (can't be blank)
  streetAddress: String
  addressLine2: String
  city: String
  state: String
  zip: String
  ###

  ### CONTACT DETAILS
  #
  publicEmail: String
  publicPhone: String
  #
  # Direct Internal Contact fields, not public, less likely found by AI
  email: String
  phone: String
  ###

  ### PARENT CHARITY ORGANIZATION DETAILS
  #
  isFeedingAmericaAffiliate: YesNoEnum # Does this Charity Org or any of its Sites: (1) exist in Feeding America's Network? or (2) collaborate with FA? or (3) receive support from FA? or (4) exist in the network of a Food Bank or collaborate with or receive support from a Food Bank that does (1), (2), or (3)?
  #
  # Especially include these if they differ from its Site(s)
  description: String # multiline text, max 500 char, public & donor-facing summary, ideally around 50 words
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  ###
}
```
