import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from routes import routes  # Your blueprint with API endpoints and catch-all route

app = Flask(__name__, static_folder='../frontend/build', static_url_path='')
CORS(app)

# Register the blueprint containing API endpoints, e.g. /api/tango_status
app.register_blueprint(routes)

# An example endpoint, in addition to those defined in your blueprint
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"message": "Hello from Flask!"})

# Catch-all route to serve React's index.html for all non-API routes.
# This works only if you've built your React app.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
