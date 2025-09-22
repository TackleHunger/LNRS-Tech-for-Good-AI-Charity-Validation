"""
Tests for GraphQL client functionality.
"""

import pytest
from unittest.mock import Mock, patch
from src.tackle_hunger.graphql_client import TackleHungerConfig, TackleHungerClient


def test_config_defaults():
    """Test configuration defaults."""
    config = TackleHungerConfig(ai_scraping_token="test")
    assert config.environment == "dev"
    assert config.timeout == 30
    assert config.rate_limit == 10


def test_tkh_graphql_endpoint():
    """Test dev endpoint selection."""
    config = TackleHungerConfig(
        ai_scraping_token="test",
        environment="dev"
    )
    assert "dev" in config.graphql_endpoint


def test_production_endpoint():
    """Test production endpoint selection."""
    config = TackleHungerConfig(
        ai_scraping_token="test",
        environment="production"
    )
    assert "staging" not in config.graphql_endpoint
