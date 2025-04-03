# app.py
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from routes import routes        # Your additional API endpoints
from folder_api import folder_api  # Folder-related endpoints
from auth import auth            # Authentication endpoints

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
    app.run(debug=True)
