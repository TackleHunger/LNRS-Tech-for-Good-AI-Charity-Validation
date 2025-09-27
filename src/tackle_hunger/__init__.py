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
from .data_quality import (
    calculate_site_quality_score,
    calculate_organization_quality_score,
    get_quality_grade,
    get_quality_color
)

__all__ = [
    "TackleHungerClient",
    "TackleHungerConfig", 
    "SiteOperations",
    "OrganizationOperations",
    "calculate_site_quality_score",
    "calculate_organization_quality_score",
    "get_quality_grade",
    "get_quality_color"
]
