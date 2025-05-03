# routes/files.py
from flask import Blueprint, request, jsonify
from auth import token_required
import datetime


files_bp = Blueprint('files', __name__)
db: 'DatabaseManager | None' = None  # 타입 힌트 명시 (선택 사항)

def init_files_bp(database_manager):
    global db
    db = database_manager

@files_bp.route('/files', methods=['GET'])
def get_files():
    files = db.get_all_files()
    return jsonify(files)

@files_bp.route("/api/files", methods=["GET"])
@token_required
def get_user_files(user_id):
    """
    클라이언트가 사용자 파일 목록을 요청하는 엔드포인트 (딕셔너리)
    """
    files = db.get_files_for_user(user_id)

    result = []
    for f in files:
        check_interval_value = f['check_interval']
        updated_at = f.get('updated_at')

        check_interval_seconds = None
        if isinstance(check_interval_value, datetime.timedelta):
            check_interval_seconds = check_interval_value.total_seconds()

        result.append({
            "file_path": f['file_path'],
            "check_interval": check_interval_seconds,
            "updated_at": updated_at.isoformat() if updated_at else None
        })

    return jsonify(result)


@files_bp.route("/api/report_hash", methods=["POST"])
@token_required
def report_hash(user_id):
    """
    클라이언트가 특정 파일의 새로운 해시값을 보고하는 엔드포인트
    """
    data = request.get_json()

    file_path = data.get("file_path")
    new_hash = data.get("new_hash")

    if not file_path or not new_hash:
        return jsonify({"error": "file_path와 new_hash는 필수입니다"}), 400

    try:
        db.update_file_record(file_path, new_hash, user_id)
        return jsonify({"message": "Hash updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
