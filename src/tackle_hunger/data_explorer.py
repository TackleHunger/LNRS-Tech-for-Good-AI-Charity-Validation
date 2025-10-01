"""
Data exploration utilities for charity validation.

Analyzes organizations and sites to identify missing data elements.
"""

from typing import Dict, Any, List, Set, Optional, Tuple
import json
from datetime import datetime
from .graphql_client import TackleHungerClient
from .site_operations import SiteOperations
from .organization_operations import OrganizationOperations


class DataExplorer:
    """Analyzes charity data to identify missing information."""

    def __init__(self, client: TackleHungerClient):
        self.client = client
        self.site_ops = SiteOperations(client)
        self.org_ops = OrganizationOperations(client)

    # Field definitions for analysis
    ESSENTIAL_SITE_FIELDS = {
        'name', 'streetAddress', 'city', 'state', 'zip', 'publicEmail', 'publicPhone'
    }
    
    IMPORTANT_SITE_FIELDS = {
        'website', 'description', 'serviceArea', 'acceptsFoodDonations', 'ein',
        'contactEmail', 'contactName', 'contactPhone'
    }
    
    ESSENTIAL_ORG_FIELDS = {
        'name'
    }
    
    IMPORTANT_ORG_FIELDS = {
        'streetAddress', 'city', 'state', 'zip', 'publicEmail', 'publicPhone',
        'description', 'ein', 'isFeedingAmericaAffiliate'
    }

    def analyze_site_completeness(self, site: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze completeness of a single site."""
        missing_essential = []
        missing_important = []
        
        for field in self.ESSENTIAL_SITE_FIELDS:
            if not site.get(field) or site.get(field) == '':
                missing_essential.append(field)
        
        for field in self.IMPORTANT_SITE_FIELDS:
            if not site.get(field) or site.get(field) == '':
                missing_important.append(field)
        
        completeness_score = (
            (len(self.ESSENTIAL_SITE_FIELDS) - len(missing_essential)) * 2 +
            (len(self.IMPORTANT_SITE_FIELDS) - len(missing_important))
        ) / (len(self.ESSENTIAL_SITE_FIELDS) * 2 + len(self.IMPORTANT_SITE_FIELDS))
        
        return {
            'site_id': site.get('id'),
            'name': site.get('name') or 'Unknown',
            'completeness_score': round(completeness_score, 2),
            'missing_essential': missing_essential,
            'missing_important': missing_important,
            'has_essential_gaps': len(missing_essential) > 0,
            'total_missing': len(missing_essential) + len(missing_important)
        }

    def analyze_organization_completeness(self, org: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze completeness of a single organization."""
        missing_essential = []
        missing_important = []
        
        for field in self.ESSENTIAL_ORG_FIELDS:
            if not org.get(field) or org.get(field) == '':
                missing_essential.append(field)
        
        for field in self.IMPORTANT_ORG_FIELDS:
            if not org.get(field) or org.get(field) == '':
                missing_important.append(field)
        
        completeness_score = (
            (len(self.ESSENTIAL_ORG_FIELDS) - len(missing_essential)) * 2 +
            (len(self.IMPORTANT_ORG_FIELDS) - len(missing_important))
        ) / (len(self.ESSENTIAL_ORG_FIELDS) * 2 + len(self.IMPORTANT_ORG_FIELDS))
        
        return {
            'org_id': org.get('id'),
            'name': org.get('name') or 'Unknown',
            'completeness_score': round(completeness_score, 2),
            'missing_essential': missing_essential,
            'missing_important': missing_important,
            'has_essential_gaps': len(missing_essential) > 0,
            'total_missing': len(missing_essential) + len(missing_important),
            'site_count': len(org.get('sites', []))
        }

    def explore_sites_data(self, limit: int = 100) -> Dict[str, Any]:
        """Explore sites data and identify missing information."""
        print(f"Fetching {limit} sites for analysis...")
        sites = self.site_ops.get_sites_for_ai(limit=limit)
        
        analyses = []
        for site in sites:
            analysis = self.analyze_site_completeness(site)
            analyses.append(analysis)
        
        # Summary statistics
        total_sites = len(analyses)
        sites_with_essential_gaps = sum(1 for a in analyses if a['has_essential_gaps'])
        avg_completeness = sum(a['completeness_score'] for a in analyses) / total_sites if total_sites > 0 else 0
        
        # Field-specific missing counts
        field_missing_counts = {}
        for field in self.ESSENTIAL_SITE_FIELDS | self.IMPORTANT_SITE_FIELDS:
            count = sum(1 for a in analyses if field in (a['missing_essential'] + a['missing_important']))
            field_missing_counts[field] = count
        
        # Sort by most problematic
        most_problematic = sorted(analyses, key=lambda x: (-len(x['missing_essential']), -x['total_missing']))[:10]
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_sites_analyzed': total_sites,
                'sites_with_essential_gaps': sites_with_essential_gaps,
                'average_completeness_score': round(avg_completeness, 2),
                'percentage_with_essential_gaps': round((sites_with_essential_gaps / total_sites * 100) if total_sites > 0 else 0, 1)
            },
            'field_missing_counts': field_missing_counts,
            'most_problematic_sites': most_problematic,
            'all_site_analyses': analyses
        }

    def explore_organizations_data(self, limit: int = 100) -> Dict[str, Any]:
        """Explore organizations data and identify missing information."""
        print(f"Fetching {limit} organizations for analysis...")
        organizations = self.org_ops.get_organizations_for_ai(limit=limit)
        
        analyses = []
        for org in organizations:
            analysis = self.analyze_organization_completeness(org)
            analyses.append(analysis)
        
        # Summary statistics
        total_orgs = len(analyses)
        orgs_with_essential_gaps = sum(1 for a in analyses if a['has_essential_gaps'])
        avg_completeness = sum(a['completeness_score'] for a in analyses) / total_orgs if total_orgs > 0 else 0
        
        # Field-specific missing counts
        field_missing_counts = {}
        for field in self.ESSENTIAL_ORG_FIELDS | self.IMPORTANT_ORG_FIELDS:
            count = sum(1 for a in analyses if field in (a['missing_essential'] + a['missing_important']))
            field_missing_counts[field] = count
        
        # Sort by most problematic
        most_problematic = sorted(analyses, key=lambda x: (-len(x['missing_essential']), -x['total_missing']))[:10]
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_organizations_analyzed': total_orgs,
                'organizations_with_essential_gaps': orgs_with_essential_gaps,
                'average_completeness_score': round(avg_completeness, 2),
                'percentage_with_essential_gaps': round((orgs_with_essential_gaps / total_orgs * 100) if total_orgs > 0 else 0, 1)
            },
            'field_missing_counts': field_missing_counts,
            'most_problematic_organizations': most_problematic,
            'all_organization_analyses': analyses
        }

    def generate_comprehensive_report(self, sites_limit: int = 100, orgs_limit: int = 100) -> Dict[str, Any]:
        """Generate a comprehensive data completeness report."""
        print("Generating comprehensive data completeness report...")
        
        sites_analysis = self.explore_sites_data(limit=sites_limit)
        orgs_analysis = self.explore_organizations_data(limit=orgs_limit)
        
        # Cross-reference analysis
        total_entities = sites_analysis['summary']['total_sites_analyzed'] + orgs_analysis['summary']['total_organizations_analyzed']
        total_with_gaps = sites_analysis['summary']['sites_with_essential_gaps'] + orgs_analysis['summary']['organizations_with_essential_gaps']
        
        return {
            'report_timestamp': datetime.now().isoformat(),
            'executive_summary': {
                'total_entities_analyzed': total_entities,
                'total_with_essential_data_gaps': total_with_gaps,
                'overall_data_gap_percentage': round((total_with_gaps / total_entities * 100) if total_entities > 0 else 0, 1),
                'sites_average_completeness': sites_analysis['summary']['average_completeness_score'],
                'organizations_average_completeness': orgs_analysis['summary']['average_completeness_score']
            },
            'sites_analysis': sites_analysis,
            'organizations_analysis': orgs_analysis,
            'recommendations': self._generate_recommendations(sites_analysis, orgs_analysis)
        }

    def _generate_recommendations(self, sites_analysis: Dict[str, Any], orgs_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on the analysis."""
        recommendations = []
        
        # Site recommendations
        site_missing = sites_analysis['field_missing_counts']
        most_missing_site_field = max(site_missing.items(), key=lambda x: x[1]) if site_missing else ('', 0)
        
        if most_missing_site_field[1] > 0:
            recommendations.append(
                f"Priority: Focus on collecting '{most_missing_site_field[0]}' data for sites - "
                f"missing in {most_missing_site_field[1]} out of {sites_analysis['summary']['total_sites_analyzed']} sites "
                f"({round(most_missing_site_field[1]/sites_analysis['summary']['total_sites_analyzed']*100, 1)}%)"
            )
        
        # Organization recommendations
        org_missing = orgs_analysis['field_missing_counts']
        most_missing_org_field = max(org_missing.items(), key=lambda x: x[1]) if org_missing else ('', 0)
        
        if most_missing_org_field[1] > 0:
            recommendations.append(
                f"Priority: Focus on collecting '{most_missing_org_field[0]}' data for organizations - "
                f"missing in {most_missing_org_field[1]} out of {orgs_analysis['summary']['total_organizations_analyzed']} organizations "
                f"({round(most_missing_org_field[1]/orgs_analysis['summary']['total_organizations_analyzed']*100, 1)}%)"
            )
        
        # General recommendations
        if sites_analysis['summary']['percentage_with_essential_gaps'] > 50:
            recommendations.append(
                "High priority: More than 50% of sites have essential data gaps. Consider implementing automated data validation."
            )
        
        if orgs_analysis['summary']['percentage_with_essential_gaps'] > 50:
            recommendations.append(
                "High priority: More than 50% of organizations have essential data gaps. Consider implementing mandatory field validation."
            )
        
        return recommendations

    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save the analysis report to a JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/tmp/tackle_hunger_data_analysis_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"Report saved to: {filename}")
        return filename

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print a human-readable summary of the report."""
        print("\n" + "="*80)
        print("TACKLE HUNGER DATA COMPLETENESS ANALYSIS SUMMARY")
        print("="*80)
        
        exec_summary = report['executive_summary']
        print(f"Total Entities Analyzed: {exec_summary['total_entities_analyzed']}")
        print(f"Entities with Essential Data Gaps: {exec_summary['total_with_essential_data_gaps']}")
        print(f"Overall Data Gap Percentage: {exec_summary['overall_data_gap_percentage']}%")
        print(f"Sites Average Completeness: {exec_summary['sites_average_completeness']}")
        print(f"Organizations Average Completeness: {exec_summary['organizations_average_completeness']}")
        
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
        
        print("\nTOP MISSING FIELDS - SITES:")
        sites_missing = report['sites_analysis']['field_missing_counts']
        for field, count in sorted(sites_missing.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count > 0:
                total_sites = report['sites_analysis']['summary']['total_sites_analyzed']
                percentage = round(count/total_sites*100, 1) if total_sites > 0 else 0
                print(f"  - {field}: {count} missing ({percentage}%)")
        
        print("\nTOP MISSING FIELDS - ORGANIZATIONS:")
        orgs_missing = report['organizations_analysis']['field_missing_counts']
        for field, count in sorted(orgs_missing.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count > 0:
                total_orgs = report['organizations_analysis']['summary']['total_organizations_analyzed']
                percentage = round(count/total_orgs*100, 1) if total_orgs > 0 else 0
                print(f"  - {field}: {count} missing ({percentage}%)")
        
        print("\n" + "="*80)