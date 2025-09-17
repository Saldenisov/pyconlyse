# auth.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, set_access_cookies, unset_jwt_cookies,
    jwt_required, get_jwt_identity
)

auth = Blueprint('auth', __name__)

# A simple user store
users = {
    'admin': 'sad',
    'larbre': 'elyse'
}

@auth.route('/api/login', methods=['POST'])
def login():
    # Support JSON or form-data input.
    if request.is_json:
        username = request.json.get("username", None)
        password = request.json.get("password", None)
    else:
        username = request.form.get("username", None)
        password = request.form.get("password", None)

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    if username not in users or users[username] != password:
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    response = jsonify({"login": True})
    set_access_cookies(response, access_token)
    return response

@auth.route('/api/logout', methods=['POST'])
def logout():
    response = jsonify({"logout": True})
    unset_jwt_cookies(response)
    return response

@auth.route('/api/status', methods=['GET'])
@jwt_required()
def status():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Hello {current_user}, welcome to Flask!"})
