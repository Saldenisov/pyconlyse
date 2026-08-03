import os
import secrets
from pathlib import Path


def _load_project_env(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                if "=" not in text:
                    continue
                key, value = text.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key.startswith("export "):
                    key = key[len("export "):].strip()
                if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError:
        return


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _env_origins(name, default):
    value = os.environ.get(name)
    if value is None:
        return list(default)
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError(f"{name} must not contain '*'")
    return origins


def configure_security(flask_app):
    """Configure security-sensitive web settings from the environment."""
    production = _env_bool("PYCONLYSE_PRODUCTION", False)
    if production and not _env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH", True):
        raise RuntimeError("PYCONLYSE_ENFORCE_DEVICE_AUTH must be true in production")
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "").strip()
    if not jwt_secret:
        if production:
            raise RuntimeError("JWT_SECRET_KEY must be set in production")
        jwt_secret = secrets.token_urlsafe(48)

    cookie_secure = _env_bool("PYCONLYSE_JWT_COOKIE_SECURE", production)
    if production and not cookie_secure:
        raise RuntimeError("PYCONLYSE_JWT_COOKIE_SECURE must be true in production")
    csrf_protect = _env_bool("PYCONLYSE_JWT_COOKIE_CSRF_PROTECT", production)
    if production and not csrf_protect:
        raise RuntimeError(
            "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT must be true in production"
        )

    same_site = os.environ.get("PYCONLYSE_JWT_COOKIE_SAMESITE", "Lax").strip().lower()
    same_site_values = {"lax": "Lax", "strict": "Strict", "none": "None"}
    if same_site not in same_site_values:
        raise RuntimeError("PYCONLYSE_JWT_COOKIE_SAMESITE must be Lax, Strict, or None")
    if same_site == "none" and not cookie_secure:
        raise RuntimeError("PYCONLYSE_JWT_COOKIE_SAMESITE=None requires secure cookies")

    origins = _env_origins(
        "PYCONLYSE_CORS_ORIGINS",
        () if production else ("http://localhost:3000", "http://127.0.0.1:3000"),
    )
    flask_app.config.update(
        JWT_SECRET_KEY=jwt_secret,
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_SECURE=cookie_secure,
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_SAMESITE=same_site_values[same_site],
        JWT_COOKIE_CSRF_PROTECT=csrf_protect,
        PYCONLYSE_CORS_ORIGINS=origins,
    )
    CORS(
        flask_app,
        resources={r"/api/*": {"origins": origins}},
        supports_credentials=True,
    )


# Default to the lab Tango DB, but never overwrite an explicit shell setting.
_load_project_env(str(Path(__file__).resolve().parents[1] / ".env"))
os.environ.setdefault(
    "TANGO_HOST",
    os.environ.get("PYCONLYSE_TANGO_HOST", "10.20.30.202:10000"),
)

from flask import Flask, jsonify, send_from_directory  # noqa: I001
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from routes import routes        # Your additional API endpoints
from folder_api import folder_api  # Folder-related endpoints
from device_api import device_api  # Device control API endpoints
from treatment_api import treatment_api  # Treatment workflow API
from pump_probe_v0_api import pump_probe_v0_api  # Pump-probe V0 emulator API
from pump_probe_vd2_api import pump_probe_vd2_api  # VD2 streak-camera control API
from auth import auth, configured_users  # Authentication endpoints
from websocket_handler import init_socketio  # WebSocket support

app = Flask(__name__, static_folder='../frontend/build', static_url_path='')
configure_security(app)
if _env_bool("PYCONLYSE_PRODUCTION", False):
    configured_users(required=True)
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(routes)
app.register_blueprint(folder_api)
app.register_blueprint(device_api)  # Add device API
app.register_blueprint(treatment_api)  # Add treatment API
app.register_blueprint(pump_probe_v0_api)  # Add pump-probe V0 emulator API
app.register_blueprint(pump_probe_vd2_api)
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

# Route for OWIS PS90 page
@app.route('/owis_ps90.html')
@app.route('/test_owis_ps90.html')  # backward compatibility
def owis_ps90_page():
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
