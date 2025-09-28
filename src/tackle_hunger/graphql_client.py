"""
GraphQL Client for Tackle Hunger API

GraphQL operations for charity validation volunteers.
"""

import os
import time
from typing import Optional, Dict, Any
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class TackleHungerConfig:
    """
    Configuration class for Tackle Hunger API client with environment-based settings.

    Loads API tokens, environment, timeout, and endpoint URLs from environment variables or constructor arguments.

    Attributes:
        ai_scraping_token (str): API token for authentication.
        environment (str): Current environment ('production', 'staging', 'dev').
        timeout (int): Timeout for API requests in seconds.
        endpoints (dict): Mapping of environment names to GraphQL endpoint URLs.

    Property:
        graphql_endpoint (str): Returns the GraphQL endpoint URL for the current environment.
    """
    
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
    """GraphQL client for charity validation with comprehensive logging"""

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

    def _log_api_call(self, operation_name: str, start_time: float, end_time: float, data_size: int = 0, record_count: int = 0):
        """Log API call with comprehensive telemetry."""
        execution_time = end_time - start_time
        
        print(f"🚀 API Call Started: {operation_name}")
        print(f"📡 Endpoint: {self.config.graphql_endpoint}")
        print(f"📊 Environment: {self.config.environment}")
        print(f"⏱️  Execution Time: {execution_time:.3f}s")
        if record_count > 0:
            print(f"📈 Data Retrieved: {record_count:,} records")
        if data_size > 0:
            print(f"📦 Response Size: {data_size:,} bytes")
        print(f"✅ API Call Completed: {operation_name}")
        print()

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query with logging."""
        # Extract operation name from query for logging
        operation_name = "GraphQLQuery"
        if "query" in query:
            lines = query.strip().split('\n')
            for line in lines:
                if line.strip().startswith('query '):
                    operation_name = line.strip().split('query ')[1].split('(')[0].split('{')[0].strip()
                    break
        
        start_time = time.time()
        try:
            gql_query = gql(query)
            result = self._client.execute(gql_query, variable_values=variables)
            end_time = time.time()
            
            # Calculate data metrics
            result_str = str(result)
            data_size = len(result_str.encode('utf-8'))
            
            # Estimate record count
            record_count = 0
            if isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, list):
                        record_count += len(value)
            
            self._log_api_call(operation_name, start_time, end_time, data_size, record_count)
            return result
            
        except Exception as e:
            end_time = time.time()
            print(f"❌ API Call Failed: {operation_name}")
            print(f"📡 Endpoint: {self.config.graphql_endpoint}")
            print(f"⏱️  Execution Time: {end_time - start_time:.3f}s")
            print(f"🚫 Error: {str(e)}")
            print()
            raise
