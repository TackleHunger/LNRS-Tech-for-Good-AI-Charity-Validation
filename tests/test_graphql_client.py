"""
Tests for simplified GraphQL client - easy for volunteers to understand.
"""

import pytest
from src.tackle_hunger.graphql_client import TackleHungerConfig, TackleHungerClient


def test_config_defaults():
    """Test simple configuration defaults."""
    config = TackleHungerConfig(ai_scraping_token="test")
    assert config.environment == "dev"
    assert config.timeout == 30


def test_dev_endpoint():
    """Test dev endpoint selection."""
    config = TackleHungerConfig(ai_scraping_token="test", environment="dev")
    assert "devapi.sboc.us" in config.graphql_endpoint


def test_production_endpoint():
    """Test production endpoint selection."""
    config = TackleHungerConfig(ai_scraping_token="test", environment="production")
    assert "api.sboc.us" in config.graphql_endpoint
    assert "staging" not in config.graphql_endpoint
    assert "dev" not in config.graphql_endpoint


def test_staging_endpoint():
    """Test staging endpoint selection."""
    config = TackleHungerConfig(ai_scraping_token="test", environment="staging")
    assert "stagingapi.sboc.us" in config.graphql_endpoint


def test_client_creation():
    """Test that client can be created without errors."""
    config = TackleHungerConfig(ai_scraping_token="test")
    # Just test creation - don't actually call API in tests
    client = TackleHungerClient(config)
    assert client.config.graphql_endpoint is not None
    assert client._client is not None
