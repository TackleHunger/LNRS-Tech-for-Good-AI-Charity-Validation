"""
GraphQL Client for Tackle Hunger API

Provides authenticated GraphQL operations for charity validation.
"""

import os
import time
from typing import Optional, Dict, Any
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class TackleHungerConfig:
    """Configuration for Tackle Hunger API client."""

    def __init__(self):
        self.ai_scraping_token = os.getenv("AI_SCRAPING_TOKEN", "")
        self.environment = os.getenv("ENVIRONMENT", "dev")
        self.tkh_graphql_endpoint = os.getenv("AI_SCRAPING_GRAPHQL_URL", "https://devapi.sboc.us/graphql")
        self.timeout = int(os.getenv("TIMEOUT", "30"))
        self.rate_limit = int(os.getenv("RATE_LIMIT", "10"))

    @property
    def graphql_endpoint(self) -> str:
        """Get the appropriate GraphQL endpoint based on environment."""
        return self.tkh_graphql_endpoint


class TackleHungerClient:
    """GraphQL client for Tackle Hunger charity validation operations."""

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

        return Client(transport=transport, fetch_schema_from_transport=False)

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        gql_query = gql(query)
        return self._client.execute(gql_query, variable_values=variables)
