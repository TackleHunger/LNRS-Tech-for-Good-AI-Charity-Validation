# LNRS-Tech-for-Good-AI-Charity-Validation

LexisNexis Risk Solutions (LNRS)'s "Tech for Good" Tackle Hunger AI Charity Validation project.

## Quick Start

**Security-Optimized Development Environment**: Uses Alpine Linux Docker containers with 96% fewer vulnerabilities than standard setups.

See [VOLUNTEER_QUICK_START.md](VOLUNTEER_QUICK_START.md) for complete setup instructions.

## Table of Contents

- [Relevant Charity Fields](#relevant-charity-fields)
  - [Fields to Pull](#fields-to-pull)
    - [Fetching Sites](#fetching-sites)
    - [Fetching Organizations](#fetching-organizations)
  - [Fields to Push](#fields-to-push)
    - [Create Site](#create-site)
    - [Update Site](#update-site)
    - [Create Organization](#create-organization)
    - [Update Organization](#update-organization)
- [Potential Projects / Target Goals / Deliverables](#potential-projects--target-goals--deliverables)

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

## Potential Projects / Target Goals / Deliverables

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
