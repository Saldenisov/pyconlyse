#!/usr/bin/env python3
"""
PYCONLYSE Web Server - Production Startup Script

This script starts the PYCONLYSE web server in production mode.
It uses eventlet for proper Socket.IO WebSocket support.

Requirements:
    pip install eventlet

Usage:
    python start_production.py
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
original_cwd = os.getcwd()
try:
    os.chdir(str(backend_dir))
    from app import socketio, app
finally:
    os.chdir(original_cwd)

if __name__ == '__main__':
    web_host = os.environ.get('PYCONLYSE_WEB_HOST', '127.0.0.1')
    web_port = int(os.environ.get('PYCONLYSE_WEB_PORT', '5000'))
    print("=" * 60)
    print("PYCONLYSE Web Server - PRODUCTION MODE")
    print("=" * 60)
    print(f"Server starting on: http://{web_host}:{web_port}")
    print(f"Main page:        http://{web_host}:{web_port}/")
    print(f"iTest PSU page:   http://{web_host}:{web_port}/test_ds_itest_psu.html")
    print(f"API devices:      http://{web_host}:{web_port}/api/devices")
    print(f"TANGO_HOST:       {os.environ.get('TANGO_HOST', os.environ.get('PYCONLYSE_TANGO_HOST', '10.20.30.202:10000'))}")
    print("=" * 60)
    print("Production settings:")
    print("  - Debug mode: OFF")
    print("  - WebSocket: eventlet")
    print("  - Auto-reload: OFF")
    print("=" * 60)

    try:
        # Run the server in production mode
        # eventlet is required for proper Socket.IO WebSocket support
        socketio.run(
            app,
            debug=False,          # PRODUCTION: Debug mode OFF
            port=web_port,
            host=web_host,
            use_reloader=False    # PRODUCTION: No auto-reload
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
    except ImportError as e:
        if 'eventlet' in str(e):
            print("\n\nERROR: eventlet is not installed!")
            print("Please install it with: pip install eventlet")
            print("\neventlet is required for Socket.IO WebSocket support in production.")
        else:
            raise
    except Exception as e:
        print(f"\nError starting server: {e}")
        print("\nTroubleshooting:")
        print("1. Check if port 5000 is available")
        print("2. Verify IP address 10.20.30.202 is correct")
        print("3. Ensure Tango database is accessible")
        print("4. Check devices are registered and running")
        print("5. Ensure eventlet is installed: pip install eventlet")
