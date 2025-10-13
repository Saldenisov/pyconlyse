# app.py
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from routes import routes        # Your additional API endpoints
from folder_api import folder_api  # Folder-related endpoints
from auth import auth            # Authentication endpoints
from device_api import device_api  # Device control API endpoints
from websocket_handler import init_socketio  # WebSocket support

app = Flask(__name__, static_folder='../frontend/build', static_url_path='')
CORS(app)

# Configure JWT settings
app.config["JWT_SECRET_KEY"] = "your_jwt_secret_key"  # Change this for production!
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_CSRF_PROTECT"] = False  # For demo only. Enable CSRF protection in production.
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(routes)
app.register_blueprint(folder_api)
app.register_blueprint(auth)
app.register_blueprint(device_api)  # Add device API

# Initialize WebSocket support
socketio = init_socketio(app)

# Catch-all route to serve your React app.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Optionally, block API paths that didn't match a defined endpoint.
    if path.startswith("api"):
        return jsonify({"msg": "API endpoint not found"}), 404

    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    # Use socketio.run instead of app.run for WebSocket support
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
