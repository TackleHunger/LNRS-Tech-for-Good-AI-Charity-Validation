"""
GraphQL Client for Tackle Hunger API

Provides authenticated GraphQL operations for charity validation.
"""

import os
import time
import logging
from typing import Optional, Dict, Any
import requests
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from pydantic_settings import BaseSettings

# Configure logging for API telemetry
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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

        return Client(transport=transport, fetch_schema_from_transport=False)

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query with logging and telemetry."""
        start_time = time.time()
        
        # Log API call initiation
        operation_name = self._extract_operation_name(query)
        logger.info(f"🚀 API Call Started: {operation_name}")
        logger.info(f"📡 Endpoint: {self.config.graphql_endpoint}")
        logger.info(f"📊 Environment: {self.config.environment}")
        
        if variables:
            logger.info(f"📥 Variables: {variables}")
        
        try:
            gql_query = gql(query)
            result = self._client.execute(gql_query, variable_values=variables)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Log successful completion with telemetry
            logger.info(f"✅ API Call Completed: {operation_name}")
            logger.info(f"⏱️  Execution Time: {execution_time:.3f}s")
            
            # Log data size telemetry
            if result:
                self._log_response_telemetry(result, operation_name)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ API Call Failed: {operation_name}")
            logger.error(f"⏱️  Execution Time: {execution_time:.3f}s")
            logger.error(f"🚨 Error: {str(e)}")
            raise

    def _extract_operation_name(self, query: str) -> str:
        """Extract operation name from GraphQL query."""
        lines = query.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('query ') or line.startswith('mutation '):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1].replace('{', '').strip()
        return "UnknownOperation"

    def _log_response_telemetry(self, result: Dict[str, Any], operation_name: str):
        """Log response size and data telemetry."""
        try:
            # Log data counts for common operations
            if 'sitesForAI' in result:
                count = len(result['sitesForAI'])
                logger.info(f"📈 Data Retrieved: {count} sites")
                
            elif 'organizationsForAI' in result:
                count = len(result['organizationsForAI'])  
                logger.info(f"📈 Data Retrieved: {count} organizations")
                
            # Log response size
            response_size = len(str(result))
            logger.info(f"📦 Response Size: {response_size:,} bytes")
            
            # Log memory usage estimation
            if response_size > 1000000:  # > 1MB
                logger.info(f"💾 Large Response: Consider using pagination for {operation_name}")
                
        except Exception as e:
            logger.debug(f"Telemetry logging failed: {e}")
