# Tackle Hunger Data Explorer

A Streamlit-based data visualization and exploration tool for charity validation data. This tool provides interactive visualizations for exploring organization and site data from the Tackle Hunger charity validation system.

## Features

### 🌳 Tree Structure Browsing
- Hierarchical view of organizations and their associated sites
- Expandable sections showing detailed site information
- Quality scores for organizations and sites
- Empty field highlighting

### 📊 Data Tables
- Tabular view of sites and organizations
- Interactive filtering by quality score, state, and status
- Download capability (CSV export)
- Search and pagination

### 📈 Data Quality Analytics
- Quality score distribution histograms
- Empty fields analysis with bar charts
- Category-based scoring (location, contact, service info)
- Visual data quality indicators

### 🗺️ Map Visualization
- Geographic visualization of site locations
- Interactive map with popups showing site details
- Color-coded markers based on quality scores
- Folium-powered mapping

### 🕸️ Network Graph
- Network visualization showing site relationships
- Distance-based connections between sites with coordinates
- Sites without location data connect to "Unknown Location" node
- Interactive Plotly-based graph

### 🎨 Design Features
- **Dark Mode**: Professional dark theme optimized for data exploration
- **Pastel Color Palette**: Sticky note inspired colors (pink, yellow, light green, blue)
- **Empty Field Highlighting**: Visual indicators for missing data
- **Quality Scoring**: Comprehensive data quality assessment

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables (optional):**
   Create a `.env` file with your API credentials:
   ```
   AI_SCRAPING_TOKEN=your_token_here
   ENVIRONMENT=dev
   ```

## Usage

### Running the Data Explorer

```bash
streamlit run data_explorer.py
```

The application will start on `http://localhost:8501` by default.

### Testing the Installation

Run the test script to verify all components work:

```bash
python test_data_explorer.py
```

### Sample Data Mode

If API credentials are not available or the connection fails, the app automatically falls back to sample data for demonstration purposes.

## Data Quality Scoring

The application includes a comprehensive data quality scoring system:

### Scoring Categories
- **Core Required** (ID, Name): Weight 1.0
- **Location** (Address, City, State, Zip, Coordinates): Weight 0.7-0.9
- **Contact** (Phone, Email, Website): Weight 0.7-0.8
- **Service Info** (Description, Status, Service Area): Weight 0.4-0.8
- **Additional** (EIN, Internal Contacts): Weight 0.5-0.6

### Quality Grades
- **A**: 0.9-1.0 (Excellent)
- **B**: 0.8-0.9 (Good)
- **C**: 0.7-0.8 (Fair)
- **D**: 0.6-0.7 (Poor)
- **F**: 0.0-0.6 (Very Poor)

### Validation Rules
- Email format validation
- Phone number format validation
- Website URL validation
- EIN format validation (US Tax ID)
- Penalties for placeholder values ("N/A", "Unknown", etc.)

## API Integration

The Data Explorer integrates with the Tackle Hunger GraphQL API:

- **Sites**: Fetches site data using `sitesForAI` query
- **Organizations**: Fetches organization data using `organizationsForAI` query
- **Fallback**: Automatic fallback to sample data if API is unavailable

## File Structure

```
data_explorer.py              # Main Streamlit application
test_data_explorer.py         # Test script for validation
src/tackle_hunger/
├── data_quality.py          # Data quality scoring utilities
├── organization_operations.py # Organization API operations
├── site_operations.py       # Site API operations (enhanced)
└── graphql_client.py        # GraphQL client (fixed schema fetching)
```

## Technical Details

### Dependencies
- **Streamlit**: Web application framework
- **Plotly**: Interactive visualizations
- **NetworkX**: Graph analysis and visualization
- **Folium**: Map visualization
- **Pandas**: Data manipulation
- **NumPy**: Numerical computations

### Performance Features
- **Caching**: 5-minute data caching for improved performance
- **Minimal Queries**: Option to fetch only essential fields
- **Client-side Filtering**: Efficient data filtering without API calls
- **Graceful Degradation**: Automatic fallback to minimal fields on query failures

### Geographic Features
- **Distance Calculation**: Haversine formula for accurate distances
- **Interactive Maps**: Zoom, pan, and popup functionality
- **Coordinate Handling**: Graceful handling of missing location data
- **Network Analysis**: Distance-based site relationships

## Usage Examples

### For Data Quality Analysts
1. Use **Quality Analytics** to identify common missing fields
2. Filter **Data Tables** to find sites needing attention
3. Export data for offline analysis

### For Geographic Analysis
1. Use **Map Visualization** to see geographic distribution
2. Use **Network Graph** to understand site relationships
3. Identify coverage gaps and clustering patterns

### for Validation Teams
1. Use **Tree Structure** to navigate organization hierarchies
2. Identify empty fields highlighted in red
3. Focus on low-quality scores for validation priority

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check your `AI_SCRAPING_TOKEN` environment variable
   - Verify network connectivity
   - App will automatically use sample data

2. **Slow Performance**
   - Try using minimal query mode
   - Clear Streamlit cache (`Ctrl+R` to rerun)
   - Reduce data filters if needed

3. **Map Not Loading**
   - Check internet connection (requires tile servers)
   - Verify coordinate data is valid
   - Try refreshing the page

### Getting Help

- Check the GraphQL API documentation
- Review error messages in the app
- Use sample data mode for testing features

---

**Built with ❤️ for the Tackle Hunger charity validation project**  
*Helping connect families in need with food assistance resources*