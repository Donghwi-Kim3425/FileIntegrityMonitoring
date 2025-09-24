# routes/files.py
from flask import Blueprint, request, jsonify, send_file
from auth import token_required
from drive_utils import get_google_drive_service_for_user, download_file_from_google_drive
import traceback, datetime
import io

files_bp = Blueprint('files', __name__)
db: 'DatabaseManager | None' = None  # 타입 힌트 명시

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
    files_from_db = db.get_files_for_user(user_id)

    result = []
    if files_from_db:
        for f_db_item in files_from_db:
            check_interval_value = f_db_item.get('check_interval')
            updated_at_from_db = f_db_item.get('updated_at')

            check_interval_seconds = None
            if isinstance(check_interval_value, datetime.timedelta):
                check_interval_seconds = check_interval_value.total_seconds()
            elif isinstance(check_interval_value, (int, float)):
                check_interval_seconds = float(check_interval_value)

            result.append({
                "file_path": f_db_item['file_path'],
                "check_interval": check_interval_seconds,
                "current_hash": f_db_item.get('current_hash'),
                "updated_at": updated_at_from_db
            })

    return jsonify(result)


@files_bp.route("/api/report_hash", methods=["POST"])
@token_required
def report_hash(user_id):
    """
    클라이언트가 특정 파일의 새로운 해시값을 보고하는 엔드포인트
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    file_path = data.get("file_path")
    new_hash = data.get("new_hash")
    detection_source = data.get("detection_source", "unknown_api_report")

    try:
        result_from_db = db.handle_file_report(
            user_id=user_id,
            file_path=file_path,
            new_hash=new_hash,
            detection_source=detection_source
        )

        result_dict, status_code = {}, 500
        if isinstance(result_from_db, tuple) and len(result_from_db) == 2:
            result_dict, status_code = result_from_db
        elif isinstance(result_from_db, dict):
            result_dict = result_from_db
            status_code = result_dict.get("status_code", 500)

        if result_dict.get("status") == "success":
            return jsonify({
                "message": result_dict.get("message", "Hash updated successfully"),
                "file_id": result_dict.get("file_id")
            }), status_code
        else:
            error_message = result_dict.get("message", "Failed to update hash")
            print(f"❌ Error from db.handle_file_report for {file_path} (user {user_id}): {error_message}")
            return jsonify({"error": error_message}), status_code

    except Exception as e:
        error_msg_for_log = f"❌ Exception in report_hash API for {file_path} (user {user_id}): {e}"
        print(error_msg_for_log)
        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred in API handler."}), 500

@files_bp.route("/api/file_deleted", methods=["POST"])
@token_required
def handle_delete_report_api(user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    file_path = data.get("file_path")
    detection_source = data.get("detection_source", "unknown")

    if not file_path:
        return jsonify({"error": "File path is missing"}), 400

    try:
        result_from_db = db.handle_file_deletion_report(user_id, file_path, detection_source)

        if isinstance(result_from_db, tuple) and len(result_from_db) == 2:
            response_data, status_code = result_from_db
            if isinstance(response_data, dict):
                if response_data.get("status") == "success":
                    return jsonify({
                        "message": response_data.get("message"),
                        "file_id": response_data.get("file_id")
                    }), status_code
                else:
                    return jsonify(
                        {"error": response_data.get("message", "Failed to process file deletion")}), status_code

        elif isinstance(result_from_db, dict):
            status_code = result_from_db.get("status_code", 500)
            if result_from_db.get("status") == "success":
                return jsonify({
                    "message": result_from_db.get("message", "File deletion processed"),
                    "file_id": result_from_db.get("file_id")
                }), status_code
            elif result_from_db.get("status") == "not_found":
                return jsonify({"error": result_from_db.get("message", "File not found")}), 404
            else:
                return jsonify({"error": result_from_db.get("message", "Failed to delete file")}), status_code
        else:
            print(
                f"❌ Unexpected result from db.handle_file_deletion_report for {file_path} (user {user_id}): {result_from_db}")
            return jsonify({"error": "Internal server error processing DB response for deletion."}), 500

    except Exception as e:
        print(f"❌ Exception in handle_delete_report_api for {file_path} (user {user_id}): {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred in delete API handler."}), 500


@files_bp.route("/api/files/logs", methods=["GET"])
@token_required
def get_file_logs(user_id):
    try:
        logs_from_db = db.get_file_logs_for_user(user_id)

        formatted_logs = []
        column_names = ["id", "file_id", "file", "status", "time", "oldHash", "newHash", "checkInterval"]

        for log_tuple in logs_from_db:
            log_dict = dict(zip(column_names, log_tuple))

            interval = log_dict.get("checkInterval")
            if isinstance(interval, datetime.timedelta):
                hours = interval.total_seconds() / 3600
                log_dict['checkInterval'] = f"{int(hours)}h"

            log_time = log_dict.get('time')
            if isinstance(log_time, datetime.datetime):
                log_dict['time'] = log_time.strftime('%Y-%m-%d %H:%M:%S')

            formatted_logs.append(log_dict)

        return jsonify(formatted_logs), 200

    except Exception as e:
        print(f"❌ Error in get_file_logs API for user {user_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to retrieve file logs."}), 500


@files_bp.route("/api/files/status", methods=["PUT"])
@token_required
def update_file_status(user_id):
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    print("[DEBUG] /api/files/status data:", data)

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    file_id = data.get("id")
    new_status = data.get("status")

    if not file_id:
        return jsonify({"error": "Missing 'file' key in request"}), 400
    if not new_status:
        return jsonify({"error": "Missing 'status' key in request"}), 400

    success = db.update_file_status(user_id, file_id, new_status)
    if success:
        return jsonify({"message": "File status updated successfully"}), 200
    else:
        return jsonify({"error": "Failed to update file status"}), 500


@files_bp.route("/api/files/interval", methods=["PUT"])
@token_required
def update_check_interval(user_id):
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    if not data:
        return jsonify({"error": "Request body is missing or not in a valid format"}), 400

    file_id = data.get("file")
    interval_str = data.get("interval", "")

    if not file_id:
        return jsonify({"error": "Missing 'file' key in request"}), 400
    if not interval_str:
        return jsonify({"error": "Missing 'interval' key in request"}), 400

    interval_hours_str = ''.join(filter(str.isdigit, interval_str))
    if not interval_hours_str:
        return jsonify({"error": f"Invalid interval format: '{interval_str}'"}), 400

    interval_hours = int(interval_hours_str)
    success = db.update_check_interval(user_id, file_id, interval_hours)

    if success:
        return jsonify({"message": f"Interval for '{file_id}' updated to {interval_hours}h."}), 200
    else:
        return jsonify({"error": f"Failed to update interval for '{file_id}'."}), 500

@files_bp.route("/api/files/<int:file_id>/backups", methods=["GET"])
@token_required
def get_file_backups(user_id, file_id):
    """
    특정 파일의 백업 목록을 반환
    :param user_id:
    :param file_id:
    :return:
    """

    if not db:
        return jsonify({"error": "Database is not initialized"}), 500

    try:
        backups = db.get_backups_for_file(file_id)
        if backups is None:
            return jsonify({"error": "File not found"}), 404
        return jsonify(backups), 200

    except Exception as e:
        print(f"❌ Error in get_backups_for_file for file_id {file_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred while fetching backups."}), 500


@files_bp.route("/api/backups/<int:backup_id>/download", methods=["GET"])
@token_required
def download_backup_file(user_id, backup_id):
    """
    Google Drive에서 특정 백업 파일을 다운로드하여 사용자에게 스트리밍합니다.
    """
    try:
        # 1. DB에서 백업 정보 조회
        query = "SELECT backup_path FROM backups WHERE id = %s"
        result = db.execute_query(query, (backup_id,), fetch_all=False)
        if not result:
            return jsonify({"error": "Backup not found"}), 404

        backup_path = result[0]

        # 2. Google Drive 서비스 가져오기
        service = get_google_drive_service_for_user(user_id)
        if not service:
            return jsonify({"error": "Google Drive service not available"}), 500

        # 3. 파일 다운로드
        file_bytes = download_file_from_google_drive(service, backup_path)
        if not file_bytes:
            return jsonify({"error": "Failed to download file from Google Drive"}), 500

        # 4. 파일 스트리밍 응답
        return send_file(
            io.BytesIO(file_bytes),
            as_attachment=True,
            download_name=f"rollback_{backup_id}.bin",
            mimetype="application/octet-stream"
        )

    except Exception as e:
        print(f"❌ Error in download_backup_file for backup_id {backup_id}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": "Internal server error while downloading backup"}), 500


@files_bp.route("/api/files/<int:file_id>", methods=["DELETE"])
@token_required
def delete_file_monitoring(user_id, file_id):
    if not file_id:
        return jsonify({"error": "File ID is required"}), 400

    success = db.soft_delete_file_by_id(user_id, file_id)

    if success:
        return jsonify({"message": f"File monitoring for file ID {file_id} has been stopped."}), 200
    else:
        return jsonify({"error": f"Failed to stop monitoring for file ID {file_id}. It may not exist or you may not have permission."}), 404

