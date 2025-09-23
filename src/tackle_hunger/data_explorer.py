"""
Data exploration module for charity validation.

Analyzes organizations and sites to identify missing data elements.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
import json
from .graphql_client import TackleHungerClient
from .site_operations import SiteOperations
from .organization_operations import OrganizationOperations


class DataExplorer:
    """Explores charity data to identify missing elements."""

    def __init__(self, client: TackleHungerClient):
        self.client = client
        self.site_ops = SiteOperations(client)
        self.org_ops = OrganizationOperations(client)

    def get_missing_data_analysis(self, site_limit: int = 100, org_limit: int = 100) -> Dict[str, Any]:
        """Get comprehensive analysis of missing data elements."""
        
        # Fetch data
        sites = self.site_ops.get_sites_for_ai(limit=site_limit)
        organizations = self.org_ops.get_organizations_for_ai(limit=org_limit)
        
        # Analyze missing data
        site_analysis = self._analyze_missing_site_data(sites)
        org_analysis = self._analyze_missing_organization_data(organizations)
        
        # Combined analysis
        combined_analysis = self._analyze_combined_missing_data(sites, organizations)
        
        return {
            "summary": {
                "total_sites": len(sites),
                "total_organizations": len(organizations),
                "timestamp": self._get_timestamp()
            },
            "sites": site_analysis,
            "organizations": org_analysis,
            "combined": combined_analysis
        }

    def _analyze_missing_site_data(self, sites: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze missing data in sites."""
        if not sites:
            return {"error": "No sites data available"}
        
        # Define critical fields for sites
        critical_fields = [
            'name', 'streetAddress', 'city', 'state', 'zip',
            'publicEmail', 'publicPhone', 'website', 'description'
        ]
        
        optional_fields = [
            'serviceArea', 'acceptsFoodDonations', 'ein'
        ]
        
        all_fields = critical_fields + optional_fields
        
        # Count missing data
        missing_counts = defaultdict(int)
        field_stats = {}
        sites_with_critical_missing = []
        
        for site in sites:
            site_missing = []
            for field in all_fields:
                value = site.get(field)
                if self._is_missing_value(value):
                    missing_counts[field] += 1
                    if field in critical_fields:
                        site_missing.append(field)
            
            if site_missing:
                sites_with_critical_missing.append({
                    'id': site.get('id'),
                    'name': site.get('name', 'Unknown'),
                    'organizationId': site.get('organizationId'),
                    'missing_fields': site_missing
                })
        
        # Calculate percentages
        total_sites = len(sites)
        for field in all_fields:
            missing_count = missing_counts[field]
            field_stats[field] = {
                'missing_count': missing_count,
                'missing_percentage': round((missing_count / total_sites) * 100, 2),
                'is_critical': field in critical_fields
            }
        
        return {
            "total_sites": total_sites,
            "field_statistics": field_stats,
            "sites_with_critical_missing": sites_with_critical_missing[:20],  # Top 20
            "critical_fields_missing_summary": {
                field: field_stats[field] for field in critical_fields
            }
        }

    def _analyze_missing_organization_data(self, organizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze missing data in organizations."""
        if not organizations:
            return {"error": "No organizations data available"}
        
        # Define critical fields for organizations
        critical_fields = [
            'name', 'streetAddress', 'city', 'state', 'zip',
            'publicEmail', 'publicPhone'
        ]
        
        optional_fields = [
            'addressLine2', 'email', 'phone', 'website', 'description', 
            'ein', 'nonProfitStatus'
        ]
        
        all_fields = critical_fields + optional_fields
        
        # Count missing data
        missing_counts = defaultdict(int)
        field_stats = {}
        orgs_with_critical_missing = []
        
        for org in organizations:
            org_missing = []
            for field in all_fields:
                value = org.get(field)
                if self._is_missing_value(value):
                    missing_counts[field] += 1
                    if field in critical_fields:
                        org_missing.append(field)
            
            if org_missing:
                orgs_with_critical_missing.append({
                    'id': org.get('id'),
                    'name': org.get('name', 'Unknown'),
                    'sites_count': len(org.get('sites', [])),
                    'missing_fields': org_missing
                })
        
        # Calculate percentages
        total_orgs = len(organizations)
        for field in all_fields:
            missing_count = missing_counts[field]
            field_stats[field] = {
                'missing_count': missing_count,
                'missing_percentage': round((missing_count / total_orgs) * 100, 2),
                'is_critical': field in critical_fields
            }
        
        return {
            "total_organizations": total_orgs,
            "field_statistics": field_stats,
            "organizations_with_critical_missing": orgs_with_critical_missing[:20],  # Top 20
            "critical_fields_missing_summary": {
                field: field_stats[field] for field in critical_fields
            }
        }

    def _analyze_combined_missing_data(self, sites: List[Dict[str, Any]], organizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze missing data across sites and organizations combined."""
        
        # Create mapping of organization ID to organization data
        org_map = {org['id']: org for org in organizations}
        
        # Find sites with missing organization data
        orphaned_sites = []
        sites_missing_org_data = []
        
        for site in sites:
            org_id = site.get('organizationId')
            if not org_id:
                orphaned_sites.append({
                    'id': site.get('id'),
                    'name': site.get('name', 'Unknown'),
                    'issue': 'No organizationId'
                })
            elif org_id not in org_map:
                orphaned_sites.append({
                    'id': site.get('id'),
                    'name': site.get('name', 'Unknown'),
                    'organizationId': org_id,
                    'issue': 'Organization not found'
                })
            else:
                # Check if organization has missing critical data
                org = org_map[org_id]
                org_missing = []
                for field in ['name', 'streetAddress', 'city', 'state', 'zip']:
                    if self._is_missing_value(org.get(field)):
                        org_missing.append(field)
                
                if org_missing:
                    sites_missing_org_data.append({
                        'site_id': site.get('id'),
                        'site_name': site.get('name', 'Unknown'),
                        'organization_id': org_id,
                        'organization_name': org.get('name', 'Unknown'),
                        'missing_org_fields': org_missing
                    })
        
        # Summary statistics
        total_sites = len(sites)
        total_orgs = len(organizations)
        
        return {
            "orphaned_sites": {
                "count": len(orphaned_sites),
                "percentage": round((len(orphaned_sites) / total_sites) * 100, 2) if total_sites > 0 else 0,
                "examples": orphaned_sites[:10]  # Top 10 examples
            },
            "sites_with_incomplete_organizations": {
                "count": len(sites_missing_org_data),
                "percentage": round((len(sites_missing_org_data) / total_sites) * 100, 2) if total_sites > 0 else 0,
                "examples": sites_missing_org_data[:10]  # Top 10 examples
            },
            "data_integrity": {
                "total_sites": total_sites,
                "total_organizations": total_orgs,
                "sites_per_org_ratio": round(total_sites / total_orgs, 2) if total_orgs > 0 else 0
            }
        }

    def _is_missing_value(self, value: Any) -> bool:
        """Check if a value is considered missing."""
        return value is None or value == "" or value == "null" or str(value).strip() == ""

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    def export_missing_data_report(self, output_file: str, site_limit: int = 100, org_limit: int = 100) -> str:
        """Export missing data analysis to a JSON file."""
        analysis = self.get_missing_data_analysis(site_limit, org_limit)
        
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        return f"Missing data analysis exported to {output_file}"

    def get_data_completeness_summary(self, site_limit: int = 100, org_limit: int = 100) -> Dict[str, Any]:
        """Get a high-level summary of data completeness."""
        analysis = self.get_missing_data_analysis(site_limit, org_limit)
        
        site_stats = analysis.get('sites', {}).get('field_statistics', {})
        org_stats = analysis.get('organizations', {}).get('field_statistics', {})
        
        # Calculate overall completeness scores
        site_completeness = self._calculate_completeness_score(site_stats)
        org_completeness = self._calculate_completeness_score(org_stats)
        
        return {
            "summary": analysis.get('summary', {}),
            "site_completeness": site_completeness,
            "organization_completeness": org_completeness,
            "combined_insights": analysis.get('combined', {}),
            "recommendations": self._generate_recommendations(analysis)
        }

    def _calculate_completeness_score(self, field_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate completeness score for a set of fields."""
        if not field_stats:
            return {"score": 0, "grade": "F"}
        
        critical_fields = [field for field, stats in field_stats.items() if stats.get('is_critical', False)]
        optional_fields = [field for field, stats in field_stats.items() if not stats.get('is_critical', False)]
        
        # Calculate weighted score (critical fields count more)
        critical_score = 0
        optional_score = 0
        
        if critical_fields:
            critical_missing_avg = sum(field_stats[field]['missing_percentage'] for field in critical_fields) / len(critical_fields)
            critical_score = 100 - critical_missing_avg
        
        if optional_fields:
            optional_missing_avg = sum(field_stats[field]['missing_percentage'] for field in optional_fields) / len(optional_fields)
            optional_score = 100 - optional_missing_avg
        
        # Weighted average (critical fields = 70%, optional = 30%)
        overall_score = (critical_score * 0.7) + (optional_score * 0.3)
        
        # Grade assignment
        if overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "score": round(overall_score, 2),
            "grade": grade,
            "critical_score": round(critical_score, 2),
            "optional_score": round(optional_score, 2),
            "critical_fields_count": len(critical_fields),
            "optional_fields_count": len(optional_fields)
        }

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        site_stats = analysis.get('sites', {}).get('field_statistics', {})
        org_stats = analysis.get('organizations', {}).get('field_statistics', {})
        combined = analysis.get('combined', {})
        
        # Check for high missing percentages in critical fields
        for field, stats in site_stats.items():
            if stats.get('is_critical') and stats.get('missing_percentage', 0) > 20:
                recommendations.append(f"Priority: {stats['missing_percentage']}% of sites missing critical field '{field}'")
        
        for field, stats in org_stats.items():
            if stats.get('is_critical') and stats.get('missing_percentage', 0) > 20:
                recommendations.append(f"Priority: {stats['missing_percentage']}% of organizations missing critical field '{field}'")
        
        # Check for orphaned sites
        orphaned_count = combined.get('orphaned_sites', {}).get('count', 0)
        if orphaned_count > 0:
            recommendations.append(f"Data integrity issue: {orphaned_count} sites have missing or invalid organization references")
        
        # Check for incomplete organizations
        incomplete_count = combined.get('sites_with_incomplete_organizations', {}).get('count', 0)
        if incomplete_count > 0:
            recommendations.append(f"Data quality issue: {incomplete_count} sites have organizations with missing critical data")
        
        if not recommendations:
            recommendations.append("Good news: No critical data quality issues detected")
        
        return recommendations