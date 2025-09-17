from flask import Blueprint, jsonify, send_from_directory, current_app, g
import sqlite3
import socket
import tango
import os
from datetime import datetime

# Set the Tango host environment variable
os.environ["TANGO_HOST"] = "everest:10000"

# Try to initialize the global Tango Database connection
try:
    db = tango.Database()
except Exception as e:
    print("Could not initialize Tango Database:", e)
    db = None

# Create the Blueprint
routes = Blueprint("routes", __name__)

# Initialize downtime tracking for Tango DB and Tango devices
downtime = {
    'tango_db': {'status': True, 'last_checked': datetime.now(), 'downtime_start': None},
    'tango': {}
}

# Define the SQLite database location (if needed)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, '../pyconlyse.db')

def get_db():
    """Get SQLite database connection (if needed elsewhere)"""
    db_conn = getattr(g, '_database', None)
    if db_conn is None:
        db_conn = g._database = sqlite3.connect(DATABASE)
    return db_conn

def query_db(query, args=(), one=False):
    """Run a query on SQLite (if needed elsewhere)"""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@routes.teardown_app_request
def close_connection(exception=None):
    """Close SQLite connection on teardown (if used)"""
    db_conn = getattr(g, '_database', None)
    if db_conn is not None:
        db_conn.close()

def check_tango_database():
    """Check if the Tango database is running (using PyTango)"""
    global downtime, db
    now = datetime.now()

    if db is None:
        try:
            db = tango.Database()
            print("Reinitialized Tango Database connection.")
        except Exception as e:
            print("Could not reinitialize Tango Database:", e)
            if downtime['tango_db']['downtime_start'] is None:
                downtime['tango_db']['downtime_start'] = now
            return False

    try:
        db.get_device_exported("*")
        downtime['tango_db']['downtime_start'] = None
        return True
    except Exception as err:
        print("❌ Tango DB Connection Failed:", err)
        if downtime['tango_db']['downtime_start'] is None:
            downtime['tango_db']['downtime_start'] = now
        return False

def check_tango_device(address):
    """Check the state of a Tango device and return its state as a string."""
    try:
        device = tango.DeviceProxy(address)
        state = device.state()
        print(f"Device {address} state: {state}")
        return state
    except Exception as e:
        print(f"Error checking device {address}: {e}")
        return "DOWN"

@routes.route('/api/tango_status')
def tango_status():
    """Check the status of the Tango database and Tango starter devices"""
    global downtime, db
    now = datetime.now()

    tango_db_status = check_tango_database()
    tango_db_downtime_seconds = 0
    if not tango_db_status and downtime['tango_db']['downtime_start']:
        tango_db_downtime_seconds = (now - downtime['tango_db']['downtime_start']).total_seconds()

    # Retrieve exported devices
    starters = []
    if db is not None:
        try:
            devices = db.get_device_exported("*")
            starters = [dev for dev in devices if dev.startswith("tango/admin/")]
        except Exception as e:
            print("Error retrieving exported devices:", e)
    else:
        print("No Tango Database connection available.")

    tango_statuses = []
    for starter in starters:
        state = check_tango_device(starter)
        if state in (tango.DevState.ON, tango.DevState.MOVING, tango.DevState.STANDBY):
            downtime['tango'][starter] = {'status': True, 'last_checked': now, 'downtime_start': None}
        else:
            if starter not in downtime['tango'] or downtime['tango'][starter]['downtime_start'] is None:
                downtime['tango'][starter] = {'status': False, 'last_checked': now, 'downtime_start': now}
            else:
                downtime['tango'][starter]['last_checked'] = now
        downtime_seconds = 0
        if downtime['tango'][starter]['downtime_start']:
            downtime_seconds = (now - downtime['tango'][starter]['downtime_start']).total_seconds()
        tango_statuses.append((starter, starter, state, downtime_seconds))

    return jsonify(
        mysql_status=tango_db_status,
        mysql_downtime_seconds=tango_db_downtime_seconds,
        tango_statuses=tango_statuses
    )

# Other API endpoints can be defined here if needed
# For example, if you want to have an API for data treatment or other features,
# you can add additional /api/ endpoints.

# For all non-API routes, serve the React app's index.html.
@routes.route('/', defaults={'path': ''})
@routes.route('/<path:path>')
def serve_react_app(path):
    """
    In production, after building your React app (npm run build),
    set Flask's static_folder to the React build directory.
    This route catches all non-API requests and serves index.html.
    """
    return send_from_directory(current_app.static_folder, 'index.html')
