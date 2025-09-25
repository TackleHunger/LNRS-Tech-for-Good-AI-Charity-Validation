"""
Tests for the sites export functionality.
"""

import pytest
import csv
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Import the export functions
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from export_sites_to_csv import write_sites_to_csv, export_sites_to_csv


def test_write_sites_to_csv():
    """Test writing sites data to CSV file."""
    # Sample sites data
    sites_data = [
        {
            'id': '1',
            'name': 'Test Food Bank',
            'city': 'Test City',
            'state': 'TS',
            'zip': '12345',
            'publicEmail': 'test@example.com',
            'status': 'ACTIVE'
        },
        {
            'id': '2', 
            'name': 'Another Food Pantry',
            'city': 'Another City',
            'state': 'AC',
            'zip': '67890',
            'publicEmail': None,  # Test None handling
            'status': 'PENDING'
        }
    ]
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp_file:
        temp_path = tmp_file.name
    
    try:
        write_sites_to_csv(sites_data, temp_path)
        
        # Verify file was created
        assert os.path.exists(temp_path)
        
        # Read back and verify content
        with open(temp_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Should have 2 rows
            assert len(rows) == 2
            
            # Verify first row
            assert rows[0]['id'] == '1'
            assert rows[0]['name'] == 'Test Food Bank'
            assert rows[0]['city'] == 'Test City'
            assert rows[0]['publicEmail'] == 'test@example.com'
            
            # Verify second row and None handling
            assert rows[1]['id'] == '2'
            assert rows[1]['name'] == 'Another Food Pantry'
            assert rows[1]['publicEmail'] == ''  # None should become empty string
            
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_write_sites_to_csv_empty():
    """Test that empty sites data raises error."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp_file:
        temp_path = tmp_file.name
    
    try:
        with pytest.raises(ValueError, match="No sites data to write"):
            write_sites_to_csv([], temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@patch('export_sites_to_csv.SiteOperations')
@patch('export_sites_to_csv.TackleHungerClient')
def test_export_sites_to_csv_mock(mock_client_class, mock_site_ops_class):
    """Test the full export function with mocked API calls."""
    # Mock the API response
    mock_sites_data = [
        {'id': '1', 'name': 'Mock Food Bank', 'city': 'Mock City'},
        {'id': '2', 'name': 'Mock Pantry', 'city': 'Mock Town'}
    ]
    
    # Setup mocks
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    
    mock_site_ops = Mock()
    mock_site_ops.get_sites_for_ai.return_value = mock_sites_data
    mock_site_ops_class.return_value = mock_site_ops
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = os.path.join(temp_dir, 'test_output.csv')
        
        # Call the function
        result = export_sites_to_csv(limit=10, output_file=output_file)
        
        # Verify function calls
        mock_client_class.assert_called_once()
        mock_site_ops_class.assert_called_once_with(mock_client)
        mock_site_ops.get_sites_for_ai.assert_called_once_with(limit=10)
        
        # Verify return value
        assert result == output_file
        
        # Verify file was created
        assert os.path.exists(output_file)
        
        # Verify content
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]['name'] == 'Mock Food Bank'
            assert rows[1]['name'] == 'Mock Pantry'


@patch('export_sites_to_csv.SiteOperations')
@patch('export_sites_to_csv.TackleHungerClient')
def test_export_sites_to_csv_no_data(mock_client_class, mock_site_ops_class):
    """Test export function when no data is returned from API."""
    # Mock empty API response
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    
    mock_site_ops = Mock()
    mock_site_ops.get_sites_for_ai.return_value = []  # Empty response
    mock_site_ops_class.return_value = mock_site_ops
    
    # Call the function
    result = export_sites_to_csv(limit=10)
    
    # Should return None when no data
    assert result is None