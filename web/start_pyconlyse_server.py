#!/usr/bin/env python3
"""
PYCONLYSE Web Server Startup Script - DEVELOPMENT MODE

This script runs the server in DEVELOPMENT mode with debug=True.
For PRODUCTION use, run: python start_production.py

The server will be accessible at http://10.20.30.202:5001
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Add backend directory to Python path
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

# Import and run the Flask application from backend directory
# Note: We don't change working directory to avoid issues with reloader
original_cwd = os.getcwd()
try:
    os.chdir(backend_dir)
    from app import socketio, app
    from device_api import start_device_snapshot_monitor
finally:
    os.chdir(original_cwd)

if __name__ == '__main__':
    web_host = os.environ.get('PYCONLYSE_WEB_HOST', '127.0.0.1')
    web_port = int(os.environ.get('PYCONLYSE_WEB_PORT', '5001'))
    print("=" * 60)
    print("PYCONLYSE Web Server - DEVELOPMENT MODE")
    print("=" * 60)
    print(f"Server will start on: http://{web_host}:{web_port}")
    print(f"Main page:        http://{web_host}:{web_port}/")
    print(f"iTest PSU page:   http://{web_host}:{web_port}/test_ds_itest_psu.html")
    print(f"API devices:      http://{web_host}:{web_port}/api/devices")
    print(f"TANGO_HOST:       {os.environ.get('TANGO_HOST', os.environ.get('PYCONLYSE_TANGO_HOST', '10.20.30.202:10000'))}")
    print("=" * 60)
    print("WARNING: Running in DEVELOPMENT mode (debug=True)")
    print("For production, use: python start_production.py")
    print("=" * 60)

    start_device_snapshot_monitor()

    try:
        # Run the server
        socketio.run(
            app, 
            debug=True,   # Enable auto-reload on file changes
            port=web_port, 
            host=web_host,
            allow_unsafe_werkzeug=True  # For development only
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
    except Exception as e:
        print(f"\nError starting server: {e}")
        print("\nTroubleshooting:")
        print("1. Check if port 5001 is available")
        print("2. Verify IP address 10.20.30.202 is correct")
        print("3. Ensure Tango database is accessible")
        print("4. Check devices are registered and running")
