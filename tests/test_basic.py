"""
Basic tests for the Tackle Hunger charity validation system.
"""

import pytest


def test_package_imports():
    """Test that basic package imports work."""
    from src.tackle_hunger import __version__, __author__
    assert __version__ == "1.0.0"
    assert "LNRS" in __author__


def test_basic_functionality():
    """Test basic functionality."""
    assert 1 + 1 == 2