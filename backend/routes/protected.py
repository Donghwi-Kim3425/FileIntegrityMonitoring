# routes/protected.py
from flask import Blueprint, jsonify
from auth import token_required 

protected_bp = Blueprint('protected', __name__)

@protected_bp.route("/api/protected")
@token_required
def protected_endpoint(user_id):
    return jsonify({"message": "Access granted", "user_id": user_id})