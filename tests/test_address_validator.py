"""
Tests for address validation functionality.
"""

import pytest
from src.tackle_hunger.address_validator import AddressValidator, AddressClassification, is_po_box_address


class TestAddressValidator:
    """Test cases for AddressValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = AddressValidator()
    
    def test_po_box_detection_various_formats(self):
        """Test detection of various PO box formats."""
        po_box_addresses = [
            "P.O. Box 123",
            "PO Box 456", 
            "Post Office Box 789",
            "P O Box 101",
            "Box 202",  # Only if it's just "Box ###"
            "POB 303",
            "PO 404",
            "P.O. 505"
        ]
        
        for address in po_box_addresses:
            classification = self.validator.classify_address(address)
            assert classification.is_po_box, f"Failed to detect PO box in: {address}"
            assert not classification.is_physical_address
            assert classification.confidence > 0.8
    
    def test_physical_address_detection(self):
        """Test detection of physical addresses."""
        physical_addresses = [
            "123 Main Street",
            "456 Oak Avenue",
            "789 First Road",
            "101 N. Washington Blvd",
            "202 South Park Lane",
            "Building 5, 303 Corporate Drive",
            "Suite 400, 505 Business Way"
        ]
        
        for address in physical_addresses:
            classification = self.validator.classify_address(address)
            assert classification.is_physical_address, f"Failed to detect physical address in: {address}"
            assert not classification.is_po_box
            assert classification.confidence > 0.7
    
    def test_virtual_address_detection(self):
        """Test detection of virtual/mail forwarding addresses."""
        virtual_addresses = [
            "Suite 123 Mail Forwarding Service",
            "PMB 456",
            "Private Mail Box 789",
            "Mail Drop 101"
        ]
        
        for address in virtual_addresses:
            classification = self.validator.classify_address(address)
            assert not classification.is_physical_address, f"Incorrectly classified virtual address as physical: {address}"
            assert not classification.is_po_box
            assert classification.confidence > 0.7
    
    def test_address_line2_handling(self):
        """Test that address line 2 is considered in classification."""
        street_address = "123 Main Street"
        address_line2 = "P.O. Box 456"
        
        classification = self.validator.classify_address(street_address, address_line2)
        assert classification.is_po_box, "Failed to detect PO box in address line 2"
    
    def test_empty_address_handling(self):
        """Test handling of empty or None addresses."""
        classification = self.validator.classify_address("")
        assert not classification.is_po_box
        assert not classification.is_physical_address
        assert classification.confidence == 0.0
        
        classification = self.validator.classify_address(None)
        assert not classification.is_po_box
        assert not classification.is_physical_address
        assert classification.confidence == 0.0
    
    def test_case_insensitive_detection(self):
        """Test that detection works regardless of case."""
        addresses = [
            "p.o. box 123",
            "POST OFFICE BOX 456",
            "Po BoX 789",
            "123 MAIN STREET",
            "456 oak avenue"
        ]
        
        for address in addresses:
            classification = self.validator.classify_address(address)
            # Should successfully classify regardless of case
            assert classification.confidence > 0.3
    
    def test_is_suitable_for_site(self):
        """Test the is_suitable_for_site method."""
        # PO boxes should not be suitable for sites
        assert not self.validator.is_suitable_for_site("P.O. Box 123")
        assert not self.validator.is_suitable_for_site("Post Office Box 456")
        
        # Physical addresses should be suitable for sites
        assert self.validator.is_suitable_for_site("123 Main Street")
        assert self.validator.is_suitable_for_site("456 Oak Avenue")
        
        # Virtual addresses should not be suitable for sites
        assert not self.validator.is_suitable_for_site("PMB 789")
    
    def test_extract_address_components(self):
        """Test extraction of address components from site data."""
        site_data = {
            "streetAddress": "123 Main Street",
            "addressLine2": "Suite 456",
            "city": "Anytown",
            "state": "NY"
        }
        
        street, line2 = self.validator.extract_address_components(site_data)
        assert street == "123 Main Street"
        assert line2 == "Suite 456"
        
        # Test with missing fields
        site_data_minimal = {
            "streetAddress": "789 Oak Avenue"
        }
        
        street, line2 = self.validator.extract_address_components(site_data_minimal)
        assert street == "789 Oak Avenue"
        assert line2 is None
    
    def test_edge_cases(self):
        """Test edge cases and potential false positives."""
        # Addresses that contain "box" but aren't PO boxes
        not_po_boxes = [
            "123 Boxwood Lane",
            "456 Box Elder Street",
            "The Box Factory, 789 Industrial Drive"
        ]
        
        for address in not_po_boxes:
            classification = self.validator.classify_address(address)
            # These should either be classified as physical or uncertain, but not PO boxes
            assert not classification.is_po_box, f"Incorrectly classified as PO box: {address}"


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_is_po_box_address_function(self):
        """Test the is_po_box_address convenience function."""
        assert is_po_box_address("P.O. Box 123")
        assert is_po_box_address("Post Office Box 456")
        assert not is_po_box_address("123 Main Street")
        assert not is_po_box_address("456 Oak Avenue")
        
        # Test with address line 2
        assert is_po_box_address("123 Main Street", "P.O. Box 456")
        assert not is_po_box_address("123 Main Street", "Suite 200")


if __name__ == "__main__":
    pytest.main([__file__])