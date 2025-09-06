# LNRS-Tech-for-Good-AI-Charity-Validation

LexisNexis Risk Solutions (LNRS)'s "Tech for Good" AI Charity Validation project. At the bottom are the Project Target Goals / Deliverables.

## Relevant Charity Fields

Charities are stored as an Organization & a Site (location). Charities can have more than 1 service location so Org -< Site is a 1-to-many relation (however, the vast majority have just 1 Site). Most information is on Sites - charities that haven't interacted with our app yet typically have mostly blank Organization fields.

The only other relevant joined relations (EligiblePopulations, PlaceTypes, & ServiceTypes) are handled internally so all you need to interact with them is Schema Scalar definition for each.

The full Schema is visible on the Staging API GraphQL Playground.

### Fields to Pull

#### Sites

Relevant Sites fields to Pull are a subset of the GraphQL Schema `type Site`.

Here they are ordered for clarity & explained:

```gql
type Site {
  ### CORE
  #
  # IDs & Important Direct Joined Relations
  id: ID! # string, primary key
  organizationId: ID! # string, foreign key
  organization: Organization # M-to-1
  ###

  ### LOCATION DETAILS (food pickup/dropoff/distribution address, avoid PO Boxes)
  #
  # Any of these 4 changed triggers internal Location-Standardizing w/ Google Maps Geocode & Place Details APIs
  streetAddress: String # required for creation
  city: String # required for creation
  state: String # required for creation
  zip: String # required for creation
  #
  name: String # required for creation, only updated on first Location-Standardizing triggered
  addressLine2: String # only updated if blank when Location-Standardizing is triggered
  country: Country # defaults to 'US', see scalar options, updated if Location-Standardizing triggered
  county: String # updated if Location-Standardizing triggered, not very important
  neighborhood: String # updated if Location-Standardizing triggered, not very important
  lat: Float # updated if Location-Standardizing triggered
  lng: Float # updated if Location-Standardizing triggered
  gmapsUrl: String # updated if Location-Standardizing triggered
  placeId: String # updated if Location-Standardizing triggered
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
  description: String # multiline text, max 500 char, Ideally around 50-word public & donor-facing summary
  serviceArea: String # multiline text, max 250 char, geographic limits: Do you have a specific service area? (counties, neighborhoods, zip codes, etc.)
  requiredDocuments: String # multiline text, max 250 char, Are first-time clients required to bring any documents? (State ID, Proof of Residence, etc.)
  hoursText: String # multiline text, max 250 char, When is food available at your site?
  accessInfoText: String # multiline text, max 500 char, Are there any other specifics someone seeking assistance at this site needs to know about, such as a separate entrance? (do not repeat info in other fields)
  #
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  #
  disasterPrepared: YesNoEnum # current food-availability, see scalar options, unlikely found by AI, maintained by charity representatives
  stockStatus: Int # (0, 1, 2, 3, 4), current food-availability, unlikely found by AI, maintained by staff & charity representatives
  ###

  ### BACKEND FIELDS (system provenance & workflow)
  #
  pendingStatus: PendingStatus # approval workflow state, see scalar options
  lastUserModifiedAt: Date # when a charity representative last modified this site
  staffConfirmedAt: Date # when a Tackle Hunger staff member last confirmed this site is valid
  #
  createdMethod: String # scraping AI must add this, human-readable partner/service/run identifier if created by AI/API/ETL, consistent per service or run
  modifiedBy: String # scraping AI must add this, human-readable partner/service/run identifier if modified by AI/API/ETL, consistent per service or run
  #
  dataSource: String # URI or human-readable if found on foreign source with IDs (a list or DB)
  dataSourceId: ID # id from the foreign source (if from one with IDs)
  #
  createdAt: Date!
  updatedAt: Date!
  ###

  ### IGNORE FIELDS (not relevant for LNRS work)
  #
  # # Split
  # currentClaim: ID
  # externalId: String
  # lastUserModifiedBy: ID
  # loginLastSentTo: String
  # remindedAt: Date
  # reminderMethod: String
  # stockForecast1: Int
  # stockForecast2: Int
  #
  # benefitingFrom: [Campaign!]!
  # campaigns: [Campaign!]!
  # donations: [Donation!]!
  # donationsPendingPayout: [Donation!]!
  # payouts: [Payout!]!
  # siteHistories: [SiteHistory!]!
  # #
  #
  # # Alphabetized
  # benefitingFrom: [Campaign!]!
  # campaigns: [Campaign!]!
  # currentClaim: ID
  # donations: [Donation!]!
  # donationsPendingPayout: [Donation!]!
  # externalId: String
  # lastUserModifiedBy: ID
  # loginLastSentTo: String
  # payouts: [Payout!]!
  # remindedAt: Date
  # reminderMethod: String
  # siteHistories: [SiteHistory!]!
  # stockForecast1: Int
  # stockForecast2: Int
  ###
}
```

#### Organizations

Relevant Organization fields to Pull are a subset of the GraphQL Schema `type Organization`.

Only certain Organization fields really need to be updated. Whenever a Financial Controller gets automatically invited upon update of `site.financialControllerEmail`, then most Organization fields get filled copied from the Site to the Organization. All below are welcome if they differ from their Site(s), the Charity is being newly created, or the fields were previously blank.

Here they are ordered for clarity & explained:

```gql
type Organization {
  ### CORE
  #
  # IDs & Important Direct Joined Relations
  id: ID! # string, primary key
  sites: [Site!]! # 1-to-M
  ###

  ### LOCATION DETAILS
  #
  # Parent Organization Mailing Address, PO box is fine, public but not pins on the Map
  name: String
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
  # Especially include these if they differ from it's Site(s)
  description: String # multiline text, max 500 char, Ideally around 50-word public & donor-facing summary
  ein: String # US Employer Identification Number (EIN), Government Tax ID if outside USA
  isFeedingAmericaAffiliate: YesNoEnum
  banner: String # large rectangular image at top of page, unnecessary but nice to have
  logo: String # small square-ish icon, unnecessary but nice to have
  ###

  ### BACKEND FIELDS (timestamps)
  #
  updatedAt: Date!
  createdAt: Date!
  ###

  ### IGNORE FIELDS (not relevant for LNRS work)
  #
  # epicId: String
  # financialController: EntityUser
  # benefitingFrom: [Campaign!]!
  # campaigns: [Campaign!]!
  # incomingAccessRequests: [AccessRequest!]!
  # invitesSent: [Invitation!]!
  # invitesReceived: [Invitation!]!
  # outgoingAccessRequests: [AccessRequest!]!
  # pastUsers: [EntityUser!]!
  # payouts: [Payout!]!
  # users: [EntityUser!]!
}
```

### Fields to Push

Relevant Site fields to push are a subset of `input siteInput` from the GraphQL Schema (fully visible on the Staging API GraphQL Playground).

`siteId: String` is a separate variable on `addCharity` & `updateSite` mutations

```gql
input siteInput {
  acceptsFoodDonations: YesNoEnum
  accessInfoText: String
  addressLine2: String
  banner: String
  city: String!
  contactEmail: String
  contactName: String
  contactPhone: String
  country: Country
  county: String
  createdMethod: String
  dataSource: String
  dataSourceId: ID
  description: String
  disasterPrepared: YesNoEnum
  efroid: String
  ein: String
  eligiblePopulations: [EligiblePopulation!]
  financialControllerEmail: String
  financialControllerPhone: String
  gmapsUrl: String
  hoursText: String
  lat: Float
  lng: Float
  # loginLastSentTo: String  # ignore this field
  logo: String
  modifiedBy: String
  name: String!
  neighborhood: String
  organizationId: ID
  pendingStatus: PendingStatus
  placeId: String
  placeTypes: [PlaceType!]
  publicContactMethod: String
  publicEmail: String
  publicPhone: String
  reminderMethod: String
  requiredDocuments: String
  serviceArea: String
  serviceTypes: [ServiceType!]
  socialMedia: String
  state: String!
  status: BusinessStatus
  stockForecast1: Int
  stockForecast2: Int
  stockStatus: Int
  streetAddress: String!
  website: String
  zip: String!
}
```

## Potential Projects / Target Goals / Deliverables

- Common to each:

  - store mailing address separately if it differs from the food pickup/dropoff address
  - ensure they're open year-round (as opposed to seasonal, like school or summer programs)
  - potentially have the AI give a data-reliability score for each result
    - i.e. higher if verified from multiple sources, favored sources, conforms to key phrases
    - _in our current setup, new Charities submitted are tagged as Pending until a human does a quick check - this could help with that review_
    - could also potentially push very good ones to our API to immediately go live (i.e. not Pending)
  - automate it - deliver some amount of infrastructure-as-code that'd run it automatically (i.e. github actions, crons, webhook triggers, etc.)

1. Find existing charity's missing fields & verify their status

   - push fields that were previously empty to our API (if you think they're good enough we can save them immediately)
   - store the links to our original & the new source as well as our original data & the new data at that moment in time _(potentially in a new app or DB)_

2. Scrape Facebook for Charities _(added to any of these other projects)_

   - would probably be best as a helper-function to run within any of these other automated-scraping goals
   - _many of our Charities don't have main websites and use social media as their only up-to-date source on hours, status, & contact info_
   - _we don't have experience automating this yet, would love help_

3. Find new charities we don't already have filling in fields

   - pushed to our API _(new additions are Pending until a member of the Tackle Hunger team approves them)_
   - potentially, if the AI gives a data-reliability score, push very good ones to our API to immediately go live _(i.e. not Pending)_

4. Re-check Charities to find newer data & flag ones that might have changed

   - store the links to our original & the new source as well as our original data & the new data at that moment in time _(potentially in a new app or DB)_
