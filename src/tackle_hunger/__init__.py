"""
Tackle Hunger Charity Validation Package

This package provides tools for validating and updating charity information
through the Tackle Hunger GraphQL API.
"""

__version__ = "1.0.0"
__author__ = "LNRS Tech for Good Volunteers"

# Import main classes for easy access
from .graphql_client import TackleHungerClient, TackleHungerConfig
from .site_operations import SiteOperations
from .organization_operations import OrganizationOperations
from .data_explorer import DataExplorer

__all__ = [
    'TackleHungerClient',
    'TackleHungerConfig',
    'SiteOperations',
    'OrganizationOperations', 
    'DataExplorer'
]
