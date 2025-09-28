"""
Tackle Hunger Data Explorer - Streamlit Application

A data visualization and exploration tool for charity validation data.
Features tree browsing, data quality analysis, and network graph visualization.
NO EXTERNAL CALLS - Only GraphQL endpoint access.
"""

import os
import sys

# Disable any external network calls before importing streamlit
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
os.environ['STREAMLIT_SERVER_ADDRESS'] = 'localhost'
os.environ['STREAMLIT_SERVER_PORT'] = '8000'

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from typing import Dict, Any, List, Optional
import numpy as np
from math import radians, cos, sin, asin, sqrt
import json
from dataclasses import asdict

# Local imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from tackle_hunger.graphql_client import TackleHungerClient
from tackle_hunger.site_operations import SiteOperations
from tackle_hunger.organization_operations import OrganizationOperations
from tackle_hunger.data_quality import (
    calculate_site_quality_score, 
    calculate_organization_quality_score,
    get_quality_grade,
    get_quality_color
)


# Pastel color palette for dark mode
PASTEL_COLORS = {
    'pink': '#FFB3BA',
    'yellow': '#FFFFBA', 
    'light_green': '#BAFFC9',
    'light_blue': '#BAE1FF',
    'lavender': '#E6E6FA',
    'peach': '#FFDFBA'
}


def set_page_config():
    """Configure Streamlit page settings with dark mode."""
    st.set_page_config(
        page_title="Tackle Hunger Data Explorer",
        page_icon="🍽️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply comprehensive dark mode with pastel colors
    st.markdown("""
    <style>
    /* Main app background */
    .stApp {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    /* Main content area */
    .main > div {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    /* Fix specific main container */
    .main .block-container {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    /* Sidebar styling */
    .css-1d391kg, .css-1y4p8pa, .sidebar .sidebar-content {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Sidebar elements */
    .stSidebar {
        background-color: #2D2D2D !important;
    }
    
    .stSidebar .stMarkdown {
        color: #FFFFFF !important;
    }
    
    .stSidebar h1, .stSidebar h2, .stSidebar h3 {
        color: #FFFFFF !important;
    }
    
    /* All text elements */
    .stMarkdown, .stText, .stCaption {
        color: #FFFFFF !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
    }
    
    /* Paragraph text */
    p {
        color: #FFFFFF !important;
    }
    
    /* Strong/bold text */
    strong, b {
        color: #FFFFFF !important;
    }
    
    /* Selectbox and dropdown styling */
    .stSelectbox > div > div {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    .stSelectbox label {
        color: #FFFFFF !important;
    }
    
    /* Selectbox dropdown options */
    .stSelectbox > div > div > div {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Dataframes */
    .stDataFrame {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Dataframe content */
    .stDataFrame table {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    .stDataFrame th, .stDataFrame td {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Metric containers */
    .metric-container {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Metric values and labels */
    .css-1xarl3l, .css-1wivap2, .css-hxt7ib {
        color: #FFFFFF !important;
    }
    
    /* Metric value styling */
    [data-testid="metric-container"] {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #444 !important;
        border-radius: 4px !important;
        padding: 10px !important;
    }
    
    [data-testid="metric-container"] > div {
        color: #FFFFFF !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Expander content */
    .streamlit-expanderContent {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #2D2D2D !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #444 !important;
        color: #FFFFFF !important;
    }
    
    /* Tab panels */
    [data-baseweb="tab-panel"] {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    /* Slider */
    .stSlider > div > div {
        background-color: #2D2D2D !important;
    }
    
    .stSlider label {
        color: #FFFFFF !important;
    }
    
    /* Multiselect */
    .stMultiSelect > div > div {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    .stMultiSelect label {
        color: #FFFFFF !important;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    .stRadio label {
        color: #FFFFFF !important;
    }
    
    /* Radio option labels */
    .stRadio div[role="radiogroup"] label {
        color: #FFFFFF !important;
    }
    
    /* Alerts and messages */
    .stAlert {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    /* Error messages */
    .stError {
        background-color: #4A2D2D !important;
        color: #FFB3B3 !important;
    }
    
    /* Success messages */
    .stSuccess {
        background-color: #2D4A2D !important;
        color: #B3FFB3 !important;
    }
    
    /* Info messages */
    .stInfo {
        background-color: #2D3D4A !important;
        color: #B3D9FF !important;
    }
    
    /* Warning messages */
    .stWarning {
        background-color: #4A452D !important;
        color: #FFFEB3 !important;
    }
    
    /* Input fields */
    .stTextInput > div > div > input {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    .stTextInput label {
        color: #FFFFFF !important;
    }
    
    /* Number input */
    .stNumberInput > div > div > input {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    .stNumberInput label {
        color: #FFFFFF !important;
    }
    
    /* Text area */
    .stTextArea > div > div > textarea {
        background-color: #2D2D2D !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }
    
    .stTextArea label {
        color: #FFFFFF !important;
    }
    
    /* Buttons */
    .stButton button {
        background-color: #444 !important;
        color: #FFFFFF !important;
        border: 1px solid #666 !important;
    }
    
    .stButton button:hover {
        background-color: #555 !important;
        color: #FFFFFF !important;
    }
    
    /* Download button */
    .stDownloadButton button {
        background-color: #444 !important;
        color: #FFFFFF !important;
        border: 1px solid #666 !important;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #FFFFFF !important;
    }
    
    /* Progress bar */
    .stProgress .st-bo {
        background-color: #444 !important;
    }
    
    /* Quality score badges */
    .quality-score-high {
        background-color: #BAFFC9;
        color: #000000;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .quality-score-medium {
        background-color: #FFFFBA;
        color: #000000;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .quality-score-low {
        background-color: #FFB3BA;
        color: #000000;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .empty-field {
        background-color: #FFB3BA;
        color: #000000;
        padding: 2px 4px;
        border-radius: 2px;
        font-style: italic;
    }
    
    /* Plotly charts - force dark background */
    .js-plotly-plot {
        background-color: #1E1E1E !important;
    }
    
    .plotly {
        background-color: #1E1E1E !important;
    }
    
    /* Additional specific selectors for stubborn elements */
    div[data-testid="stSidebar"] {
        background-color: #2D2D2D !important;
    }
    
    /* Container backgrounds */
    .element-container {
        background-color: transparent !important;
        color: #FFFFFF !important;
    }
    
    /* Block containers */
    .block-container {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    
    /* Fix for markdown text in containers */
    .element-container .stMarkdown {
        color: #FFFFFF !important;
    }
    
    /* Column containers */
    [data-testid="column"] {
        background-color: transparent !important;
        color: #FFFFFF !important;
    }
    
    /* Ensure all divs in main content are dark */
    .main div {
        color: #FFFFFF !important;
    }
    
    /* Fix for any remaining light backgrounds */
    div[style*="background-color: rgb(255, 255, 255)"] {
        background-color: #2D2D2D !important;
    }
    
    div[style*="background-color: white"] {
        background-color: #2D2D2D !important;
    }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from Tackle Hunger API with caching - REAL DATA ONLY."""
    client = TackleHungerClient()
    site_ops = SiteOperations(client)
    org_ops = OrganizationOperations(client)
    
    # Load sites and organizations using the correct staging API methods
    # The sitesForAI field does not support limit argument - limit is applied client-side
    sites = site_ops.get_sites_for_ai(limit=None, minimal=False)  # Load all sites
    organizations = org_ops.get_all_organizations_for_ai()  # Load all organizations
    
    return sites, organizations


def load_paginated_data(data_type: str = "sites", page: int = 1, per_page: int = 10):
    """Load paginated data for display with pagination controls - REAL DATA ONLY."""
    
    # Load all data first (it's cached for 5 minutes)
    sites, organizations = load_data()
    
    # Select the appropriate dataset
    if data_type == "sites":
        all_data = sites
    else:  # organizations
        all_data = organizations
    
    # Calculate pagination
    total_count = len(all_data)
    total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
    
    # Calculate start and end indices for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get paginated data
    paginated_data = all_data[start_idx:end_idx]
    
    return {
        "data": paginated_data,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_count": total_count
    }


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on earth."""
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    return c * r


def create_network_graph(sites: List[Dict[str, Any]]) -> go.Figure:
    """Create a network graph showing relationships between sites based on distance."""
    G = nx.Graph()
    
    # Add sites as nodes
    sites_with_location = []
    sites_without_location = []
    
    for site in sites:
        if site.get('lat') is not None and site.get('lng') is not None:
            sites_with_location.append(site)
            G.add_node(site['id'], 
                      name=site['name'], 
                      lat=site['lat'], 
                      lng=site['lng'],
                      city=site.get('city', ''),
                      has_location=True)
        else:
            sites_without_location.append(site)
            G.add_node(site['id'],
                      name=site['name'],
                      city=site.get('city', ''),
                      has_location=False)
    
    # Add "unknown" node for sites without location
    if sites_without_location:
        G.add_node("unknown", name="Unknown Location", has_location=False)
        
        # Connect all sites without location to unknown node
        for site in sites_without_location:
            G.add_edge(site['id'], "unknown", weight=0, distance="Unknown")
    
    # Add edges between sites with known locations based on distance
    for i, site1 in enumerate(sites_with_location):
        for site2 in sites_with_location[i+1:]:
            distance = calculate_distance(
                site1['lat'], site1['lng'],
                site2['lat'], site2['lng']
            )
            
            # Only add edge if sites are within reasonable distance (e.g., 50km)
            if distance <= 50:
                G.add_edge(site1['id'], site2['id'], weight=1/distance, distance=f"{distance:.1f}km")
    
    # Create plotly figure
    pos = nx.spring_layout(G, k=1, iterations=50)
    
    # Extract node positions
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        node_data = G.nodes[node]
        text = f"{node_data['name']}<br>{node_data.get('city', '')}"
        node_text.append(text)
        
        # Color based on whether location is known
        if node == "unknown":
            node_colors.append(PASTEL_COLORS['pink'])
        elif node_data.get('has_location', False):
            node_colors.append(PASTEL_COLORS['light_green'])
        else:
            node_colors.append(PASTEL_COLORS['yellow'])
    
    # Extract edge positions
    edge_x = []
    edge_y = []
    edge_text = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        
        edge_data = G.edges[edge]
        distance = edge_data.get('distance', 'Unknown')
        edge_text.append(f"Distance: {distance}")
    
    # Create figure
    fig = go.Figure()
    
    # Add edges
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='rgba(255,255,255,0.5)'),
        hoverinfo='none',
        mode='lines'
    ))
    
    # Add nodes
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[G.nodes[node]['name'] for node in G.nodes()],
        textposition="middle center",
        hovertext=node_text,
        marker=dict(
            size=20,
            color=node_colors,
            line=dict(width=2, color='white')
        )
    ))
    
    fig.update_layout(
        title="Site Network Graph (Distance-based Connections)",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20,l=5,r=5,t=40),
        annotations=[ dict(
            text="Sites connected by distance (≤50km). Sites without coordinates connect to 'Unknown Location'",
            showarrow=False,
            xref="paper", yref="paper",
            x=0.005, y=-0.002,
            xanchor='left', yanchor='bottom',
            font=dict(color='white', size=12)
        )],
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor='#1E1E1E',
        plot_bgcolor='#1E1E1E',
        font=dict(color='white')
    )
    
    return fig


def display_tree_structure(organizations: List[Dict[str, Any]]):
    """Display organizations and sites in a tree structure."""
    st.subheader("🌳 Organization & Site Tree Structure")
    
    selected_org = st.selectbox(
        "Select Organization to Explore:",
        options=["All Organizations"] + [org.get('name', f"Org {org['id']}") for org in organizations],
        key="tree_org_select"
    )
    
    if selected_org == "All Organizations":
        orgs_to_show = organizations
    else:
        orgs_to_show = [org for org in organizations if org.get('name') == selected_org]
    
    for org in orgs_to_show:
        org_quality = calculate_organization_quality_score(org)
        quality_class = "quality-score-high" if org_quality['overall_score'] >= 0.7 else "quality-score-medium" if org_quality['overall_score'] >= 0.5 else "quality-score-low"
        
        st.markdown(f"""
        <div style="border-left: 3px solid {PASTEL_COLORS['light_blue']}; padding-left: 10px; margin-bottom: 20px;">
        <h4>🏢 {org.get('name', f'Organization {org["id"]}')} 
        <span class="{quality_class}">Quality: {org_quality['overall_score']:.2f}</span></h4>
        <p><strong>ID:</strong> {org['id']}</p>
        <p><strong>Location:</strong> {org.get('city', 'N/A')}, {org.get('state', 'N/A')}</p>
        <p><strong>Sites:</strong> {len(org.get('sites', []))}</p>
        </div>
        """, unsafe_allow_html=True)
        
        sites = org.get('sites', [])
        for i, site in enumerate(sites):
            site_quality = calculate_site_quality_score(site)
            quality_class = "quality-score-high" if site_quality['overall_score'] >= 0.7 else "quality-score-medium" if site_quality['overall_score'] >= 0.5 else "quality-score-low"
            
            # Create expandable section for each site
            site_name = site.get('name', f'Site {site["id"]}')
            with st.expander(f"🏪 {site_name} - Quality: {site_quality['overall_score']:.2f}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Basic Info:**")
                    st.write(f"ID: {site['id']}")
                    st.write(f"Status: {site.get('status', 'Unknown')}")
                    if site.get('description'):
                        st.write(f"Description: {site['description']}")
                
                with col2:
                    st.write("**Location:**")
                    st.write(f"{site.get('streetAddress', 'N/A')}")
                    st.write(f"{site.get('city', 'N/A')}, {site.get('state', 'N/A')} {site.get('zip', '')}")
                    if site.get('lat') and site.get('lng'):
                        st.write(f"Coordinates: {site['lat']:.4f}, {site['lng']:.4f}")
                
                with col3:
                    st.write("**Contact:**")
                    phone = site.get('publicPhone', 'Not provided')
                    email = site.get('publicEmail', 'Not provided') 
                    website = site.get('website', 'Not provided')
                    
                    if phone == 'Not provided' or phone is None:
                        st.markdown('<span class="empty-field">Phone: Not provided</span>', unsafe_allow_html=True)
                    else:
                        st.write(f"Phone: {phone}")
                    
                    if email == 'Not provided' or email is None:
                        st.markdown('<span class="empty-field">Email: Not provided</span>', unsafe_allow_html=True)
                    else:
                        st.write(f"Email: {email}")
                        
                    if website == 'Not provided' or website is None:
                        st.markdown('<span class="empty-field">Website: Not provided</span>', unsafe_allow_html=True)
                    else:
                        st.write(f"Website: {website}")


def display_data_tables(sites: List[Dict[str, Any]], organizations: List[Dict[str, Any]]):
    """Display data in table format with quality scores."""
    st.subheader("📊 Data Tables")
    
    tab1, tab2 = st.tabs(["Sites", "Organizations"])
    
    with tab1:
        if sites:
            # Calculate quality scores for all sites
            sites_with_quality = []
            for site in sites:
                quality = calculate_site_quality_score(site)
                site_data = site.copy()
                site_data['quality_score'] = quality['overall_score']
                site_data['quality_grade'] = get_quality_grade(quality['overall_score'])
                site_data['completeness'] = quality['completeness']
                sites_with_quality.append(site_data)
            
            # Create DataFrame
            df_sites = pd.DataFrame(sites_with_quality)
            
            # Add filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                min_quality = st.slider("Minimum Quality Score", 0.0, 1.0, 0.0, 0.1)
            with col2:
                states = df_sites['state'].dropna().unique() if 'state' in df_sites.columns else []
                selected_states = st.multiselect("Filter by State", states, default=list(states))
            with col3:
                status_options = df_sites['status'].dropna().unique() if 'status' in df_sites.columns else []
                selected_status = st.multiselect("Filter by Status", status_options, default=list(status_options))
            
            # Apply filters
            filtered_df = df_sites[df_sites['quality_score'] >= min_quality]
            if selected_states:
                filtered_df = filtered_df[filtered_df['state'].isin(selected_states)]
            if selected_status:
                filtered_df = filtered_df[filtered_df['status'].isin(selected_status)]
            
            st.write(f"Showing {len(filtered_df)} of {len(df_sites)} sites")
            
            # Display key columns
            display_columns = ['name', 'city', 'state', 'quality_score', 'quality_grade', 'completeness', 'publicPhone', 'publicEmail', 'website']
            available_columns = [col for col in display_columns if col in filtered_df.columns]
            
            st.dataframe(
                filtered_df[available_columns],
                use_container_width=True,
                column_config={
                    "quality_score": st.column_config.NumberColumn("Quality Score", format="%.3f"),
                    "completeness": st.column_config.NumberColumn("Completeness", format="%.3f"),
                }
            )
        else:
            st.info("No sites data available")
    
    with tab2:
        if organizations:
            # Calculate quality scores for all organizations
            orgs_with_quality = []
            for org in organizations:
                quality = calculate_organization_quality_score(org)
                org_data = org.copy()
                org_data['quality_score'] = quality['overall_score']
                org_data['quality_grade'] = get_quality_grade(quality['overall_score'])
                org_data['site_count'] = len(org.get('sites', []))
                orgs_with_quality.append(org_data)
            
            df_orgs = pd.DataFrame(orgs_with_quality)
            
            # Add filters
            min_quality = st.slider("Minimum Quality Score (Orgs)", 0.0, 1.0, 0.0, 0.1, key="org_quality_filter")
            
            filtered_df = df_orgs[df_orgs['quality_score'] >= min_quality]
            st.write(f"Showing {len(filtered_df)} of {len(df_orgs)} organizations")
            
            # Display key columns
            display_columns = ['name', 'city', 'state', 'quality_score', 'quality_grade', 'site_count', 'publicPhone', 'publicEmail']
            available_columns = [col for col in display_columns if col in filtered_df.columns]
            
            st.dataframe(
                filtered_df[available_columns],
                use_container_width=True,
                column_config={
                    "quality_score": st.column_config.NumberColumn("Quality Score", format="%.3f"),
                    "site_count": st.column_config.NumberColumn("Sites", format="%d"),
                }
            )
        else:
            st.info("No organizations data available")


def display_paginated_data():
    """Display data with pagination controls (10 items per page as requested)."""
    st.subheader("📄 Paginated Data Viewer")
    st.info("This view loads data in pages of 10 items as requested, ideal for large datasets.")
    
    # Data type selector
    data_type = st.radio("Select data type:", ["Sites", "Organizations"], horizontal=True)
    data_key = data_type.lower().rstrip('s') if data_type == "Organizations" else data_type.lower()
    
    # Initialize session state for pagination
    if f"page_{data_key}" not in st.session_state:
        st.session_state[f"page_{data_key}"] = 1
    
    # Load paginated data
    with st.spinner(f"Loading {data_type.lower()} page {st.session_state[f'page_{data_key}']}..."):
        result = load_paginated_data(data_key, page=st.session_state[f"page_{data_key}"], per_page=10)
    
    data = result["data"]
    page = result["page"]
    per_page = result["per_page"]
    total_pages = result["total_pages"]
    total_count = result["total_count"]
    
    # Display pagination info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Items", total_count)
    with col2:
        st.metric("Current Page", f"{page} of {total_pages}")
    with col3:
        st.metric("Items on Page", len(data))
    
    # Pagination controls
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("⏮️ First", disabled=page <= 1):
            st.session_state[f"page_{data_key}"] = 1
            st.rerun()
    
    with col2:
        if st.button("⏪ Previous", disabled=page <= 1):
            st.session_state[f"page_{data_key}"] = page - 1
            st.rerun()
    
    with col3:
        # Page selector
        new_page = st.selectbox("Go to page:", 
                               options=list(range(1, total_pages + 1)),
                               index=page - 1,
                               key=f"page_selector_{data_key}")
        if new_page != page:
            st.session_state[f"page_{data_key}"] = new_page
            st.rerun()
    
    with col4:
        if st.button("Next ⏩", disabled=page >= total_pages):
            st.session_state[f"page_{data_key}"] = page + 1
            st.rerun()
    
    with col5:
        if st.button("Last ⏭️", disabled=page >= total_pages):
            st.session_state[f"page_{data_key}"] = total_pages
            st.rerun()
    
    # Display data
    if data:
        if data_type == "Sites":
            display_sites_table(data, f"Sites - Page {page}")
        else:
            display_organizations_table(data, f"Organizations - Page {page}")
    else:
        st.warning("No data available on this page.")


def display_sites_table(sites: List[Dict[str, Any]], title: str):
    """Display sites in a table format with quality scores."""
    st.subheader(title)
    
    # Calculate quality scores for the sites
    sites_with_quality = []
    for site in sites:
        quality = calculate_site_quality_score(site)
        site_data = site.copy()
        site_data['quality_score'] = quality['overall_score']
        site_data['quality_grade'] = get_quality_grade(quality['overall_score'])
        site_data['completeness'] = quality['completeness']
        sites_with_quality.append(site_data)
    
    # Create DataFrame
    df_sites = pd.DataFrame(sites_with_quality)
    
    # Display key columns
    display_columns = ['name', 'city', 'state', 'quality_score', 'quality_grade', 'completeness', 'publicPhone', 'publicEmail', 'website']
    available_columns = [col for col in display_columns if col in df_sites.columns]
    
    st.dataframe(
        df_sites[available_columns],
        use_container_width=True,
        column_config={
            "quality_score": st.column_config.NumberColumn("Quality Score", format="%.3f"),
            "completeness": st.column_config.NumberColumn("Completeness", format="%.3f"),
            "name": st.column_config.TextColumn("Site Name", width="large"),
        }
    )


def display_organizations_table(organizations: List[Dict[str, Any]], title: str):
    """Display organizations in a table format with quality scores."""
    st.subheader(title)
    
    # Calculate quality scores for organizations
    orgs_with_quality = []
    for org in organizations:
        quality = calculate_organization_quality_score(org)
        org_data = org.copy()
        org_data['quality_score'] = quality['overall_score']
        org_data['quality_grade'] = get_quality_grade(quality['overall_score'])
        org_data['site_count'] = len(org.get('sites', []))
        orgs_with_quality.append(org_data)
    
    df_orgs = pd.DataFrame(orgs_with_quality)
    
    # Display key columns
    display_columns = ['name', 'city', 'state', 'quality_score', 'quality_grade', 'site_count', 'publicPhone', 'publicEmail']
    available_columns = [col for col in display_columns if col in df_orgs.columns]
    
    st.dataframe(
        df_orgs[available_columns],
        use_container_width=True,
        column_config={
            "quality_score": st.column_config.NumberColumn("Quality Score", format="%.3f"),
            "site_count": st.column_config.NumberColumn("Sites", format="%d"),
            "name": st.column_config.TextColumn("Organization Name", width="large"),
        }
    )


def display_quality_analytics(sites: List[Dict[str, Any]], organizations: List[Dict[str, Any]]):
    """Display data quality analytics and visualizations."""
    st.subheader("📈 Data Quality Analytics")
    
    # Calculate quality scores
    site_qualities = [calculate_site_quality_score(site) for site in sites]
    org_qualities = [calculate_organization_quality_score(org) for org in organizations]
    
    # Quality score distribution
    col1, col2 = st.columns(2)
    
    with col1:
        if site_qualities:
            site_scores = [q['overall_score'] for q in site_qualities]
            fig_hist = px.histogram(
                x=site_scores,
                title="Site Quality Score Distribution",
                nbins=20,
                labels={'x': 'Quality Score', 'y': 'Count'}
            )
            fig_hist.update_traces(marker_color=PASTEL_COLORS['light_blue'])
            fig_hist.update_layout(
                paper_bgcolor='#1E1E1E',
                plot_bgcolor='#1E1E1E',
                font_color='white',
                title_font_color='white',
                xaxis=dict(color='white'),
                yaxis=dict(color='white')
            )
            st.plotly_chart(fig_hist, use_container_width=True)
    
    with col2:
        if org_qualities:
            org_scores = [q['overall_score'] for q in org_qualities]
            fig_hist_org = px.histogram(
                x=org_scores,
                title="Organization Quality Score Distribution", 
                nbins=20,
                labels={'x': 'Quality Score', 'y': 'Count'}
            )
            fig_hist_org.update_traces(marker_color=PASTEL_COLORS['light_green'])
            fig_hist_org.update_layout(
                paper_bgcolor='#1E1E1E',
                plot_bgcolor='#1E1E1E',
                font_color='white',
                title_font_color='white',
                xaxis=dict(color='white'),
                yaxis=dict(color='white')
            )
            st.plotly_chart(fig_hist_org, use_container_width=True)
    
    # Empty fields analysis
    if site_qualities:
        st.subheader("🔍 Empty Fields Analysis")
        
        # Collect all empty fields
        all_empty_fields = []
        for quality in site_qualities:
            all_empty_fields.extend(quality['empty_fields'])
        
        if all_empty_fields:
            from collections import Counter
            empty_field_counts = Counter(all_empty_fields)
            
            fig_empty = px.bar(
                x=list(empty_field_counts.keys()),
                y=list(empty_field_counts.values()),
                title="Most Common Empty Fields in Sites",
                labels={'x': 'Field Name', 'y': 'Number of Sites Missing This Field'}
            )
            fig_empty.update_traces(marker_color=PASTEL_COLORS['pink'])
            fig_empty.update_layout(
                paper_bgcolor='#1E1E1E',
                plot_bgcolor='#1E1E1E',
                font_color='white',
                title_font_color='white',
                xaxis_tickangle=-45,
                xaxis=dict(color='white'),
                yaxis=dict(color='white')
            )
            st.plotly_chart(fig_empty, use_container_width=True)


def main():
    """Main Streamlit application."""
    set_page_config()
    
    st.title("🍽️ Tackle Hunger Data Explorer")
    st.markdown("*Exploring charity validation data with interactive visualizations*")
    
    # Load data
    with st.spinner("Loading data from Tackle Hunger API..."):
        sites, organizations = load_data()
    
    if not sites and not organizations:
        st.error("No data could be loaded. Please check your API connection.")
        return
    
    # Sidebar for navigation
    st.sidebar.title("📋 Navigation")
    page = st.sidebar.radio(
        "Choose a view:",
        ["Tree Structure", "Data Tables", "Paginated Data", "Quality Analytics", "Network Graph"]
    )
    
    # Display data summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sites", len(sites))
    with col2:
        st.metric("Total Organizations", len(organizations))
    with col3:
        sites_with_coords = len([s for s in sites if s.get('lat') and s.get('lng')])
        st.metric("Sites with Coordinates", sites_with_coords)
    with col4:
        if sites:
            avg_quality = sum(calculate_site_quality_score(site)['overall_score'] for site in sites) / len(sites)
            st.metric("Avg Quality Score", f"{avg_quality:.3f}")
    
    # Display selected page
    if page == "Tree Structure":
        display_tree_structure(organizations)
    elif page == "Data Tables":
        display_data_tables(sites, organizations)
    elif page == "Paginated Data":
        display_paginated_data()
    elif page == "Quality Analytics":
        display_quality_analytics(sites, organizations)
    elif page == "Network Graph":
        st.subheader("🕸️ Site Network Visualization")
        if sites:
            with st.spinner("Creating network graph..."):
                fig_network = create_network_graph(sites)
                st.plotly_chart(fig_network, use_container_width=True)
        else:
            st.info("No sites data available for network graph")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align: center; color: {PASTEL_COLORS['yellow']};">
        🍽️ Tackle Hunger Data Explorer - Built with Streamlit & Python<br>
        Helping connect families in need with food assistance resources
        </div>
        """, 
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()