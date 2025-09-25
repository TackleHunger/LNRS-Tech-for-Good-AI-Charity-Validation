"""
Simplified GraphQL Client for Tackle Hunger API

Easy-to-understand GraphQL operations for charity validation volunteers.
No Pydantic complexity - just simple Python that works.
"""

import os
from typing import Optional, Dict, Any
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class TackleHungerConfig:
    """Simple configuration class - no validation complexity."""
    
    def __init__(self, 
                 ai_scraping_token: Optional[str] = None,
                 environment: Optional[str] = None):
        # Load environment variables if .env file exists
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # dotenv is optional - fallback to os.getenv
            pass
        
        # Allow override via constructor or fall back to environment
        self.ai_scraping_token = ai_scraping_token or os.getenv("AI_SCRAPING_TOKEN", "dummy_token_for_testing")
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        
        # Simple defaults - no validation needed for volunteer work
        timeout_str = os.getenv("API_TIMEOUT", "30")
        try:
            self.timeout = int(timeout_str)
        except (ValueError, TypeError):
            self.timeout = 30
        
        # Endpoint URLs - clear and simple
        self.endpoints = {
            "production": "https://api.sboc.us/graphql",
            "staging": "https://stagingapi.sboc.us/graphql", 
            "dev": os.getenv("AI_SCRAPING_GRAPHQL_URL", "https://devapi.sboc.us/graphql")
        }
    
    @property
    def graphql_endpoint(self) -> str:
        """Get the GraphQL endpoint based on environment."""
        return self.endpoints.get(self.environment, self.endpoints["dev"])


class TackleHungerClient:
    """Simple GraphQL client for charity validation - no Pydantic complexity."""

    def __init__(self, config: Optional[TackleHungerConfig] = None):
        self.config = config or TackleHungerConfig()
        self._client = self._create_client()

    def _create_client(self) -> Client:
        """Create authenticated GraphQL client."""
        transport = RequestsHTTPTransport(
            url=self.config.graphql_endpoint,
            headers={
                "ai-scraping-token": self.config.ai_scraping_token,
            },
            timeout=self.config.timeout,
        )
        return Client(transport=transport, fetch_schema_from_transport=True)

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        gql_query = gql(query)
        return self._client.execute(gql_query, variable_values=variables)
