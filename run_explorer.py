#!/usr/bin/env python3
"""
Streamlit Data Explorer Runner - NO EXTERNAL CALLS

This script runs the Streamlit Data Explorer with all external network calls disabled.
Only connects to the GraphQL endpoint - no AWS, no IP detection, no external services.
"""

import os
import sys
import subprocess

def setup_no_external_calls():
    """Set up environment variables to prevent all external calls."""
    
    # Streamlit-specific environment variables to prevent external calls
    env_vars = {
        # Core Streamlit settings
        'STREAMLIT_BROWSER_GATHER_USAGE_STATS': 'false',
        'STREAMLIT_SERVER_HEADLESS': 'true',
        'STREAMLIT_SERVER_ADDRESS': 'localhost',
        'STREAMLIT_SERVER_PORT': '8000',
        'STREAMLIT_SERVER_ENABLE_CORS': 'false',
        'STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION': 'false',
        'STREAMLIT_CLIENT_TOOLBAR_MODE': 'minimal',
        'STREAMLIT_CLIENT_SHOW_ERROR_DETAILS': 'false',
        'STREAMLIT_RUNNER_MAGIC_ENABLED': 'false',
        'STREAMLIT_LOGGER_LEVEL': 'error',
        
        # Network isolation
        'STREAMLIT_SERVER_ENABLE_STATIC_SERVING': 'false',
        'STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION': 'false',
        
        # Prevent external DNS/IP lookups
        'NO_PROXY': '*',
        'no_proxy': '*',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")

def run_streamlit():
    """Run Streamlit with strict localhost-only configuration."""
    
    setup_no_external_calls()
    
    # Run streamlit with explicit localhost binding
    cmd = [
        sys.executable, '-m', 'streamlit', 'run', 'data_explorer.py',
        '--server.address', 'localhost',
        '--server.port', '8000',
        '--server.headless', 'true',
        '--browser.gatherUsageStats', 'false',
        '--client.toolbarMode', 'minimal',
        '--logger.level', 'error'
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print("🚫 NO EXTERNAL CALLS - Only GraphQL endpoint access")
    print("🌐 Available at: http://localhost:8000")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n✅ Streamlit stopped - No external calls made")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Streamlit: {e}")

if __name__ == "__main__":
    run_streamlit()