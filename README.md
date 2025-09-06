# LNRS-Tech-for-Good-AI-Charity-Validation

LexisNexis Risk Solutions (LNRS)'s "Tech for Good" AI Charity Validation project

## Charity Fields 

Relevant Charity Site fields are a subset of the GraphQL `siteInput` type:
```gql
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
