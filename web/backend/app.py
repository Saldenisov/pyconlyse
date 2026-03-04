import os


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


# Default to the lab Tango DB, but never overwrite an explicit shell setting.
os.environ.setdefault(
    "TANGO_HOST",
    os.environ.get("PYCONLYSE_TANGO_HOST", "10.20.30.202:10000"),
)

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from routes import routes        # Your additional API endpoints
from folder_api import folder_api  # Folder-related endpoints
from device_api import device_api  # Device control API endpoints
from treatment_api import treatment_api  # Treatment workflow API
from auth import auth            # Authentication endpoints
from websocket_handler import init_socketio  # WebSocket support

app = Flask(__name__, static_folder='../frontend/build', static_url_path='')
CORS(app)

# JWT Configuration
# PRODUCTION: Consider using environment variable for secret key
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'Elys3!icp2025')
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = _env_bool('PYCONLYSE_JWT_COOKIE_SECURE', False)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # PRODUCTION: Consider enabling CSRF protection
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(routes)
app.register_blueprint(folder_api)
app.register_blueprint(device_api)  # Add device API
app.register_blueprint(treatment_api)  # Add treatment API
app.register_blueprint(auth)        # Add auth API

# Initialize WebSocket support
socketio = init_socketio(app)

# Route for DS iTest PSU test page
@app.route('/test_ds_itest_psu.html')
def ds_itest_psu_test():
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_ds_itest_psu.html')
    return send_from_directory(os.path.dirname(test_page_path), 'test_ds_itest_psu.html')

# Route for NETIO PDU test page
@app.route('/test_netio_pdu.html')
def netio_pdu_test():
    from flask import make_response
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_netio_pdu.html')
    response = make_response(send_from_directory(os.path.dirname(test_page_path), 'test_netio_pdu.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route for OWIS PS90 test page
@app.route('/test_owis_ps90.html')
def owis_ps90_test():
    from flask import make_response
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_owis_ps90.html')
    response = make_response(send_from_directory(os.path.dirname(test_page_path), 'test_owis_ps90.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route for Standa Motors test page
@app.route('/test_standa_motors.html')
def standa_motors_test():
    from flask import make_response
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_standa_motors.html')
    response = make_response(send_from_directory(os.path.dirname(test_page_path), 'test_standa_motors.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route for Camera API test page
@app.route('/test_camera_api.html')
def camera_api_test():
    from flask import make_response
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_camera_api.html')
    response = make_response(send_from_directory(os.path.dirname(test_page_path), 'test_camera_api.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Route for Basler Camera control page
@app.route('/basler_camera.html')
def basler_camera():
    from flask import make_response
    test_page_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'basler_camera.html')
    response = make_response(send_from_directory(os.path.dirname(test_page_path), 'basler_camera.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Catch-all route to serve your React app.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Block API paths that didn't match a defined endpoint
    if path.startswith("api/"):
        return jsonify({"msg": "API endpoint not found"}), 404
    
    # If it's a static file (has extension) and exists, serve it
    if path != "" and "." in path:
        file_path = os.path.join(app.static_folder, path)
        if os.path.exists(file_path):
            return send_from_directory(app.static_folder, path)
    
    # For all other paths (including React routes), serve index.html with no-cache headers
    from flask import make_response
    response = make_response(send_from_directory(app.static_folder, 'index.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    # DEVELOPMENT MODE ONLY
    # For production, use start_production.py which sets debug=False
    # Use socketio.run instead of app.run for WebSocket support
    socketio.run(
        app,
        debug=_env_bool('PYCONLYSE_WEB_DEBUG', True),
        port=int(os.environ.get('PYCONLYSE_WEB_PORT', '5000')),
        host=os.environ.get('PYCONLYSE_WEB_HOST', '127.0.0.1'),
        allow_unsafe_werkzeug=True,
    )
