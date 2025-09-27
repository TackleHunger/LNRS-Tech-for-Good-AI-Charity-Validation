"""
GraphQL Client for Tackle Hunger API

Provides authenticated GraphQL operations for charity validation.
"""

import os
from typing import Optional, Dict, Any
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from pydantic_settings import BaseSettings


class TackleHungerConfig(BaseSettings):
    """Configuration for Tackle Hunger API client."""

    ai_scraping_token: str
    environment: str = "dev"
    tkh_graphql_endpoint: str = os.getenv("AI_SCRAPING_GRAPHQL_URL", "https://devapi.sboc.us/graphql")
    timeout: int = 30
    rate_limit: int = 10

    class Config:
        env_file = ".env"

    @property
    def graphql_endpoint(self) -> str:
        """Get the appropriate GraphQL endpoint based on environment."""
        return (
            self.production_endpoint
            if self.environment == "production"
            else self.tkh_graphql_endpoint
        )


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

        return Client(transport=transport, fetch_schema_from_transport=True)

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        gql_query = gql(query)
        return self._client.execute(gql_query, variable_values=variables)
