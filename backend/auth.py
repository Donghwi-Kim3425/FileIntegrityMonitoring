# auth.py
from functools import wraps
from flask import request, jsonify
from db.api_token_manager import get_user_id_by_token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        if token.startswith("Bearer "):
            token = token[7:]  # 'Bearer ' 접두사 제거

        user_id = get_user_id_by_token(token)
        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 403

        # 함수에 user_id를 전달할 수도 있음
        return f(user_id=user_id, *args, **kwargs)

    return decorated
