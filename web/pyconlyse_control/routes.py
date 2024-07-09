from flask import render_template, g, jsonify
from flask import current_app as app
import sqlite3
import socket
import tango
from datetime import datetime, timedelta

# Initialize downtime tracking
downtime = {
    'mysql': {'status': True, 'last_checked': datetime.now(), 'downtime_start': None},
    'tango': {}
}


DATABASE = 'pyconlyse.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def check_server(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=2):
            return True
    except Exception:
        return False


def check_tango_device(address):
    try:
        device = tango.DeviceProxy(address)
        state = device.state()
        return state == tango.DevState.ON
    except Exception:
        return False


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/pyconlyse')
def pyconlyse():
    return render_template('pyconlyse.html')


@app.route('/equipment')
def equipment():
    return render_template('equipment.html')


@app.route('/tango')
def tango():
    return render_template('tango.html')


@app.route('/tango_status')
def tango_status():
    global downtime
    now = datetime.now()

    # Check MySQL server status
    mysql_server = query_db('SELECT ip, port FROM servers WHERE type="mysql"', one=True)
    mysql_status = check_server(mysql_server[0], mysql_server[1])

    if mysql_status:
        downtime['mysql']['downtime_start'] = None
    else:
        if downtime['mysql']['downtime_start'] is None:
            downtime['mysql']['downtime_start'] = now

    # Calculate downtime for MySQL server
    mysql_downtime_seconds = 0
    if downtime['mysql']['downtime_start']:
        mysql_downtime_seconds = (now - downtime['mysql']['downtime_start']).total_seconds()

    # Check Tango starter device statuses
    tango_starters = query_db('SELECT name, tango_address FROM tango_starters')
    tango_statuses = []
    for starter in tango_starters:
        status = check_tango_device(starter[1])
        if starter[1] not in downtime['tango']:
            downtime['tango'][starter[1]] = {'status': status, 'last_checked': now, 'downtime_start': None}
        if status:
            downtime['tango'][starter[1]]['downtime_start'] = None
        else:
            if downtime['tango'][starter[1]]['downtime_start'] is None:
                downtime['tango'][starter[1]]['downtime_start'] = now
        tango_downtime_seconds = 0
        if downtime['tango'][starter[1]]['downtime_start']:
            tango_downtime_seconds = (now - downtime['tango'][starter[1]]['downtime_start']).total_seconds()
        tango_statuses.append((starter[0], starter[1], status, tango_downtime_seconds))

    return jsonify(mysql_status=mysql_status, mysql_downtime_seconds=mysql_downtime_seconds,
                   tango_statuses=tango_statuses)


@app.route('/elyse')
def elyse():
    return render_template('elyse.html')
