#!/usr/bin/env python3
"""
PYCONLYSE Web Server Startup Script

Run this script to start the PYCONLYSE web server.
The server will be accessible at http://10.20.30.202:5000
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
finally:
    os.chdir(original_cwd)

if __name__ == '__main__':
    print("=" * 60)
    print("PYCONLYSE Web Server")
    print("=" * 60)
    print("Server will start on: http://10.20.30.202:5000")
    print("Main page:        http://10.20.30.202:5000/")
    print("iTest PSU page:   http://10.20.30.202:5000/test_ds_itest_psu.html")
    print("API devices:      http://10.20.30.202:5000/api/devices")
    print("=" * 60)

    try:
        # Run the server
        socketio.run(
            app, 
            debug=True,   # Enable auto-reload on file changes
            port=5000, 
            host='10.20.30.202',
            allow_unsafe_werkzeug=True  # For development only
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
    except Exception as e:
        print(f"\nError starting server: {e}")
        print("\nTroubleshooting:")
        print("1. Check if port 5000 is available")
        print("2. Verify IP address 10.20.30.202 is correct")
        print("3. Ensure Tango database is accessible")
        print("4. Check devices are registered and running")
