from flask import Blueprint, jsonify, send_from_directory, current_app, g
try:
    import sqlite3
except Exception:  # pragma: no cover - fallback for broken stdlib sqlite bindings
    try:
        import pysqlite3 as sqlite3
    except Exception:
        sqlite3 = None
import socket
import tango
import os
from datetime import datetime

# Respect the caller's TANGO_HOST if already set. Otherwise, fall back to the
# same lab default used by the local Mac dev launcher.
os.environ.setdefault(
    "TANGO_HOST",
    os.environ.get("PYCONLYSE_TANGO_HOST", "10.20.30.202:10000"),
)

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
    if sqlite3 is None:
        raise RuntimeError("sqlite3 module is not available in this runtime")
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


def _normalize_state_label(state):
    if isinstance(state, str):
        return state

    label = str(state)
    if "." in label:
        label = label.split(".")[-1]
    return label


def _starter_host_name(starter_name):
    parts = str(starter_name).split("/")
    return parts[-1] if parts else str(starter_name)


def _starter_server_lists(starter_name):
    try:
        starter = tango.DeviceProxy(starter_name)
        running = list(starter.command_inout('DevGetRunningServers', False))
        stopped = list(starter.command_inout('DevGetStopServers', False))
    except Exception as e:
        print(f"Error retrieving starter server lists for {starter_name}: {e}")
        return [], []
    return running, stopped

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
    starters_payload = []
    for starter in starters:
        state = check_tango_device(starter)
        state_label = _normalize_state_label(state)
        is_running = state in (tango.DevState.ON, tango.DevState.MOVING, tango.DevState.STANDBY)
        if is_running:
            downtime['tango'][starter] = {'status': True, 'last_checked': now, 'downtime_start': None}
        else:
            if starter not in downtime['tango'] or downtime['tango'][starter]['downtime_start'] is None:
                downtime['tango'][starter] = {'status': False, 'last_checked': now, 'downtime_start': now}
            else:
                downtime['tango'][starter]['last_checked'] = now
        downtime_seconds = 0
        if downtime['tango'][starter]['downtime_start']:
            downtime_seconds = (now - downtime['tango'][starter]['downtime_start']).total_seconds()
        starter_host = _starter_host_name(starter)
        running_servers, stopped_servers = _starter_server_lists(starter)
        tango_statuses.append((starter, starter_host, state_label, downtime_seconds))
        starters_payload.append({
            'name': starter,
            'host': starter_host,
            'state': state_label,
            'healthy': is_running,
            'downtime_seconds': downtime_seconds,
            'running_servers': running_servers,
            'running_count': len(running_servers),
            'stopped_servers': stopped_servers,
            'stopped_count': len(stopped_servers),
        })

    return jsonify(
        mysql_status=tango_db_status,
        mysql_downtime_seconds=tango_db_downtime_seconds,
        tango_statuses=tango_statuses,
        starters=starters_payload,
        tango_host=os.environ.get("TANGO_HOST", ""),
    )

@routes.route('/api/jive/classes')
def jive_classes():
    """Get list of device classes from Tango database"""
    global db
    if db is None:
        return jsonify({'error': 'Tango Database not available'}), 503
    
    try:
        # Get all device classes
        class_list = db.get_class_list('*')
        classes = []
        for i in range(0, len(class_list), 2):
            server_name = class_list[i]
            class_name = class_list[i + 1]
            classes.append({
                'server': server_name,
                'class': class_name
            })
        return jsonify(classes=classes)
    except Exception as e:
        print(f"Error getting class list: {e}")
        return jsonify({'error': str(e)}), 500

@routes.route('/api/jive/servers')
def jive_servers():
    """Get list of device servers from Tango database"""
    global db
    if db is None:
        return jsonify({'error': 'Tango Database not available'}), 503
    
    try:
        # Get all server instances
        server_list = db.get_server_list('*')
        servers = []
        for server in server_list:
            try:
                # Get devices for this server
                devices = db.get_device_class_list(server)
                server_devices = []
                for i in range(0, len(devices), 2):
                    device_name = devices[i]
                    device_class = devices[i + 1]
                    server_devices.append({
                        'name': device_name,
                        'class': device_class
                    })
                servers.append({
                    'name': server,
                    'devices': server_devices
                })
            except Exception as e:
                print(f"Error getting devices for server {server}: {e}")
                servers.append({
                    'name': server,
                    'devices': []
                })
        return jsonify(servers=servers)
    except Exception as e:
        print(f"Error getting server list: {e}")
        return jsonify({'error': str(e)}), 500

@routes.route('/api/jive/devices')
def jive_devices():
    """Get list of all devices from Tango database"""
    global db
    if db is None:
        return jsonify({'error': 'Tango Database not available'}), 503
    
    try:
        # Get all exported devices
        device_list = db.get_device_exported('*')
        devices = []
        for device_name in device_list:
            try:
                # Get device info
                info = db.get_device_info(device_name)
                devices.append({
                    'name': device_name,
                    'class': info.class_name,
                    'server': info.ds_full_name,
                    'exported': True
                })
            except Exception as e:
                print(f"Error getting info for device {device_name}: {e}")
                devices.append({
                    'name': device_name,
                    'class': 'Unknown',
                    'server': 'Unknown',
                    'exported': True
                })
        return jsonify(devices=devices)
    except Exception as e:
        print(f"Error getting device list: {e}")
        return jsonify({'error': str(e)}), 500

@routes.route('/api/jive/device/<path:device_name>')
def jive_device_details(device_name):
    """Get detailed information about a specific device"""
    global db
    if db is None:
        return jsonify({'error': 'Tango Database not available'}), 503
    
    try:
        # Get device info
        info = db.get_device_info(device_name)
        
        # Get device properties
        properties = {}
        try:
            prop_list = db.get_device_property_list(device_name, '*')
            for prop_name in prop_list:
                prop_value = db.get_device_property(device_name, prop_name)
                if prop_name in prop_value:
                    properties[prop_name] = prop_value[prop_name]
        except Exception as e:
            print(f"Error getting properties for {device_name}: {e}")
        
        # Try to get device state
        state = 'UNKNOWN'
        try:
            device_proxy = tango.DeviceProxy(device_name)
            state = str(device_proxy.state())
        except Exception as e:
            print(f"Could not get state for {device_name}: {e}")
        
        return jsonify(
            name=device_name,
            device_class=info.class_name,
            server=info.ds_full_name,
            host=info.host,
            state=state,
            exported=info.exported,
            properties=properties
        )
    except Exception as e:
        print(f"Error getting device details for {device_name}: {e}")
        return jsonify({'error': str(e)}), 500

# Other API endpoints can be defined here if needed
# For example, if you want to have an API for data treatment or other features,
# you can add additional /api/ endpoints.

# Catch-all route handling is done in app.py
