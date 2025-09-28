"""
Data quality scoring utilities for charity validation.

Provides functions to calculate data quality scores for sites and organizations.
"""

from typing import Dict, Any, List
import re
from dataclasses import dataclass
from enum import Enum


class FieldCategory(Enum):
    """Categories for different types of fields."""
    CORE_REQUIRED = "core_required"
    LOCATION = "location"
    CONTACT = "contact"
    SERVICE_INFO = "service_info"
    ADDITIONAL = "additional"


@dataclass
class FieldDefinition:
    """Definition of a field with its quality scoring criteria."""
    name: str
    category: FieldCategory
    weight: float
    required: bool = False
    pattern: str = None  # Regex pattern for validation
    validator: callable = None  # Custom validator function


# Define field scoring criteria for sites
SITE_FIELD_DEFINITIONS = [
    # Core required fields
    FieldDefinition("id", FieldCategory.CORE_REQUIRED, 1.0, required=True),
    FieldDefinition("name", FieldCategory.CORE_REQUIRED, 1.0, required=True),
    
    # Location fields
    FieldDefinition("streetAddress", FieldCategory.LOCATION, 0.9, required=True),
    FieldDefinition("city", FieldCategory.LOCATION, 0.9, required=True),
    FieldDefinition("state", FieldCategory.LOCATION, 0.9, required=True),
    FieldDefinition("zip", FieldCategory.LOCATION, 0.8, required=True),
    FieldDefinition("lat", FieldCategory.LOCATION, 0.7),
    FieldDefinition("lng", FieldCategory.LOCATION, 0.7),
    
    # Contact fields
    FieldDefinition("publicPhone", FieldCategory.CONTACT, 0.8, 
                   pattern=r"^\+?[\d\s\-\(\)\.]+$"),
    FieldDefinition("publicEmail", FieldCategory.CONTACT, 0.8,
                   pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    FieldDefinition("website", FieldCategory.CONTACT, 0.7,
                   pattern=r"^https?://[^\s]+$"),
    
    # Service information
    FieldDefinition("description", FieldCategory.SERVICE_INFO, 0.6),
    FieldDefinition("serviceArea", FieldCategory.SERVICE_INFO, 0.5),
    FieldDefinition("status", FieldCategory.SERVICE_INFO, 0.8),
    FieldDefinition("acceptsFoodDonations", FieldCategory.SERVICE_INFO, 0.4),
    
    # Additional fields
    FieldDefinition("ein", FieldCategory.ADDITIONAL, 0.6,
                   pattern=r"^\d{2}-?\d{7}$"),
    FieldDefinition("contactEmail", FieldCategory.ADDITIONAL, 0.5),
    FieldDefinition("contactPhone", FieldCategory.ADDITIONAL, 0.5),
]

# Define field scoring criteria for organizations
ORGANIZATION_FIELD_DEFINITIONS = [
    # Core required fields
    FieldDefinition("id", FieldCategory.CORE_REQUIRED, 1.0, required=True),
    FieldDefinition("name", FieldCategory.CORE_REQUIRED, 0.9),
    
    # Location fields
    FieldDefinition("streetAddress", FieldCategory.LOCATION, 0.7),
    FieldDefinition("city", FieldCategory.LOCATION, 0.7),
    FieldDefinition("state", FieldCategory.LOCATION, 0.7),
    FieldDefinition("zip", FieldCategory.LOCATION, 0.6),
    
    # Contact fields
    FieldDefinition("publicPhone", FieldCategory.CONTACT, 0.8,
                   pattern=r"^\+?[\d\s\-\(\)\.]+$"),
    FieldDefinition("publicEmail", FieldCategory.CONTACT, 0.8,
                   pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    FieldDefinition("website", FieldCategory.CONTACT, 0.7,
                   pattern=r"^https?://[^\s]+$"),
    
    # Additional fields
    FieldDefinition("description", FieldCategory.ADDITIONAL, 0.5),
    FieldDefinition("ein", FieldCategory.ADDITIONAL, 0.8,
                   pattern=r"^\d{2}-?\d{7}$"),
]


def validate_field_value(value: Any, field_def: FieldDefinition) -> bool:
    """Validate a field value against its definition."""
    if value is None or value == "":
        return False
    
    if field_def.pattern:
        return bool(re.match(field_def.pattern, str(value)))
    
    if field_def.validator:
        return field_def.validator(value)
    
    return True


def calculate_field_score(value: Any, field_def: FieldDefinition) -> float:
    """Calculate the quality score for a single field."""
    if not validate_field_value(value, field_def):
        return 0.0
    
    # Base score for having a value
    base_score = 1.0
    
    # Apply additional scoring based on field quality
    quality_multiplier = 1.0
    
    # Bonus for longer descriptions (but cap at reasonable length)
    if field_def.name in ["description", "serviceArea"] and isinstance(value, str):
        length_bonus = min(len(value.strip()) / 100, 0.3)  # Up to 30% bonus for good descriptions
        quality_multiplier += length_bonus
    
    # Penalty for obviously bad values
    if isinstance(value, str):
        value_lower = value.lower()
        if any(bad_value in value_lower for bad_value in ["n/a", "none", "unknown", "tbd", "todo"]):
            quality_multiplier = 0.3  # Heavily penalize placeholder values
        elif len(value.strip()) < 3:  # Very short values are likely low quality
            quality_multiplier = 0.5
    
    return min(base_score * quality_multiplier, 1.0)


def calculate_data_quality_score(data: Dict[str, Any], field_definitions: List[FieldDefinition]) -> Dict[str, Any]:
    """Calculate overall data quality score for a record."""
    field_scores = {}
    category_scores = {}
    total_weighted_score = 0.0
    total_weight = 0.0
    missing_required = []
    empty_fields = []
    
    # Calculate scores by category
    for category in FieldCategory:
        category_fields = [f for f in field_definitions if f.category == category]
        if not category_fields:
            continue
            
        category_total = 0.0
        category_weight = 0.0
        
        for field_def in category_fields:
            value = data.get(field_def.name)
            field_score = calculate_field_score(value, field_def)
            field_scores[field_def.name] = field_score
            
            category_total += field_score * field_def.weight
            category_weight += field_def.weight
            total_weighted_score += field_score * field_def.weight
            total_weight += field_def.weight
            
            # Track issues
            if field_def.required and field_score == 0.0:
                missing_required.append(field_def.name)
            if field_score == 0.0:
                empty_fields.append(field_def.name)
        
        category_scores[category.value] = category_total / category_weight if category_weight > 0 else 0.0
    
    # Calculate overall score
    overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0
    
    # Apply penalties for missing required fields
    required_penalty = len(missing_required) * 0.1  # 10% penalty per missing required field
    overall_score = max(0.0, overall_score - required_penalty)
    
    return {
        "overall_score": round(overall_score, 3),
        "category_scores": {k: round(v, 3) for k, v in category_scores.items()},
        "field_scores": {k: round(v, 3) for k, v in field_scores.items()},
        "missing_required": missing_required,
        "empty_fields": empty_fields,
        "total_fields": len(field_definitions),
        "filled_fields": len([f for f in field_scores.values() if f > 0]),
        "completeness": round(len([f for f in field_scores.values() if f > 0]) / len(field_definitions), 3)
    }


def calculate_site_quality_score(site: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate data quality score for a site."""
    return calculate_data_quality_score(site, SITE_FIELD_DEFINITIONS)


def calculate_organization_quality_score(organization: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate data quality score for an organization."""
    score = calculate_data_quality_score(organization, ORGANIZATION_FIELD_DEFINITIONS)
    
    # Consider site quality as well if sites are included
    sites = organization.get("sites", [])
    if sites:
        site_scores = [calculate_site_quality_score(site)["overall_score"] for site in sites]
        avg_site_score = sum(site_scores) / len(site_scores) if site_scores else 0.0
        
        # Combine organization score with average site score (70% org, 30% sites)
        combined_score = (score["overall_score"] * 0.7) + (avg_site_score * 0.3)
        score["overall_score"] = round(combined_score, 3)
        score["avg_site_score"] = round(avg_site_score, 3)
        score["site_count"] = len(sites)
    
    return score


def get_quality_grade(score: float) -> str:
    """Convert a quality score to a letter grade."""
    if score >= 0.9:
        return "A"
    elif score >= 0.8:
        return "B"
    elif score >= 0.7:
        return "C"
    elif score >= 0.6:
        return "D"
    else:
        return "F"


def get_quality_color(score: float) -> str:
    """Get a color for quality visualization based on score."""
    if score >= 0.9:
        return "#22c55e"  # Green
    elif score >= 0.8:
        return "#84cc16"  # Light green
    elif score >= 0.7:
        return "#eab308"  # Yellow
    elif score >= 0.6:
        return "#f97316"  # Orange
    else:
        return "#ef4444"  # Red