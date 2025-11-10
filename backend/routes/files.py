# routes/files.py
from flask import Blueprint, request, jsonify, send_file
from auth import token_required
from database import DatabaseManager, DatabaseError, NotFoundError
from drive_utils import get_google_drive_service_for_user, download_file_from_google_drive
import traceback, datetime
import io
import os

files_bp = Blueprint('files', __name__)
db: DatabaseManager | None = None  # 타입 힌트 명시

def init_files_bp(database_manager):
    global db
    db = database_manager

@files_bp.route("/api/files", methods=["GET"])
@token_required
def get_user_files(user_id):
    """
    클라이언트가 사용자 파일 목록을 요청하는 엔드포인트 (딕셔너리)

    :param user_id: 사용자 ID
    :return: 사용자의 파일 목록을 JSON 형식으로 반환
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

            # 필요한 필드만 추출하여 딕셔너리 구성
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
        - 파일 경로와 해시값을 받아 DB에 변경 여부를 기록

    :param user_id: 사용자 ID

    :return: 처리 결과 메시지 및 파일 ID (성공시) or 에러 메시지
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

        return jsonify({
            "message": result_from_db.get("message", "Hash updated successfully"),
            "file_id": result_from_db.get("file_id")
        }), 200

    except DatabaseError as e:
        print(f"❌ Error from db.handle_file_report for {file_path} (user {user_id}): {e}")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        error_msg_for_log = f"❌ Exception in report_hash API for {file_path} (user {user_id}): {e}"
        print(error_msg_for_log)
        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred in API handler."}), 500

@files_bp.route("/api/file_deleted", methods=["POST"])
@token_required
def handle_delete_report_api(user_id):
    """
    클라이언트가 특정 파일의 삭제를 보고하는 엔드포인트
        - 파일 경로와 감지 출처를 받아 DB에 삭제 상태로 기록
        
    :param user_id: 사용자 ID
     
    :return: 처리 결과 메시지 및 파일 ID or 에러 메시지 
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    file_path = data.get("file_path") # 삭제 대상 파일 경로
    detection_source = data.get("detection_source", "unknown")

    # 필수 값 누락시 에러 반환
    if not file_path:
        return jsonify({"error": "File path is missing"}), 400

    try:
        # DB에 삭제 보고 처리 요청
        result_from_db = db.handle_file_deletion_report(user_id, file_path, detection_source)

        return jsonify({
            "message": result_from_db.get("message"),
            "file_id": result_from_db.get("file_id")
        }), 200

    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404

    except DatabaseError as e:
        print(f"❌ Error from db.handle_file_deletion_report for {file_path} (user {user_id}): {e}")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        print(f"❌ Exception in handle_delete_report_api for {file_path} (user {user_id}): {e}")
        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred in delete API handler."}), 500


@files_bp.route("/api/files/logs", methods=["GET"])
@token_required
def get_file_logs(user_id):
    """
    사용자 파일 변경 로그를 조회하는 API 엔드포인트
        - 로그에는 파일 상태 변화, 해시 변경, 검사 주기 등이 포함
        
    :param user_id: 사용자 ID
     
    :return: 로그 목록을 JSON 형식으로 반환
    """

    try:
        # DB에서 사용자 로그 목록 조회 (튜플 리스트)
        logs_from_db = db.get_file_logs_for_user(user_id)

        formatted_logs = []
        column_names = ["id", "file_id", "file", "status", "time", "oldHash", "newHash", "checkInterval"]

        for log_tuple in logs_from_db:
            log_dict = dict(zip(column_names, log_tuple))

            # 검사 주기 포맷팅 (timedelta → "24h" 형식)
            interval = log_dict.get("checkInterval")
            if isinstance(interval, datetime.timedelta):
                hours = interval.total_seconds() / 3600
                log_dict['checkInterval'] = f"{int(hours)}h"

            # 로그 시간 포맷팅 (datetime → 문자열)
            log_time = log_dict.get('time')
            if isinstance(log_time, datetime.datetime):
                log_dict['time'] = log_time.strftime('%Y-%m-%d %H:%M:%S')

            formatted_logs.append(log_dict) # 포맷된 로그 추가

        return jsonify(formatted_logs), 200

    except Exception as e:
        print(f"❌ Error in get_file_logs API for user {user_id}: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to retrieve file logs."}), 500


@files_bp.route("/api/files/status", methods=["PUT"])
@token_required
def update_file_status(user_id):
    """
    쿨라이언트가 틀정 파일의 상태를 변경 요청하는 API 엔드포인트

    :param user_id: 사용자 ID

    :return: 상태 변경 성공 여부에 따른 JSON 응답
    """

    # 요청이 JSON 형식이면 JSON으로 파싱, 아니면 form 데이터로 처리
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    file_id = data.get("id")
    new_status = data.get("status")

    if not file_id:
        return jsonify({"error": "Missing 'file' key in request"}), 400
    if not new_status:
        return jsonify({"error": "Missing 'status' key in request"}), 400

    try:
        file_id = int(file_id)
        db.update_file_status(user_id, file_id, new_status)
        return jsonify({"message": "File status updated successfully"}), 200
    except DatabaseError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/api/files/interval", methods=["PUT"])
@token_required
def update_check_interval(user_id):
    """
    쿨라이언트가 특정 파일의 검사 주기를 변경 요청하는 API 엔드포인트

    :param user_id: 사용자 ID

    :return: 변경 성공 여부에 따른 JSON 응답
    """

    # 요청이 JSON 형식이면 JSON으로 파싱, 아니면 form 데이터로 처리
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

    # 문자열에서 숫자만 추출 (예: "24h" → "24")
    interval_hours_str = ''.join([char for char in interval_str if char.isdigit()])
    if not interval_hours_str:
        return jsonify({"error": f"Invalid interval format: '{interval_str}'"}), 400

    interval_hours = int(interval_hours_str) # 문자열을 정수로 변환
    # DB에 검사 주기 변경 요청
    file_id = int(file_id)
    success = db.update_check_interval(user_id, file_id, interval_hours)

    if success:
        return jsonify({"message": f"Interval for '{file_id}' updated to {interval_hours}h."}), 200
    else:
        return jsonify({"error": f"Failed to update interval for '{file_id}'."}), 500


@files_bp.route("/api/files/<int:file_id>/backups", methods=["GET"])
@token_required
def get_file_backups(user_id, file_id):
    """
    특정 파일의 백업 목록을 반환하는 API 엔드포인트

    :param user_id: 사용자 ID
    :param file_id: 백업 목록을 조회할 파일의 ID

    :return: 백업 목록 JSON or error message
    """

    if not db:
        return jsonify({"error": "Database is not initialized"}), 500

    try:
        backups = db.get_backups_for_file(user_id, file_id)
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
    Google Drive에서 특정 백업 파일을 다운로드하여 사용자에게 스트리밍

    :param user_id: 사용자 ID
    :param backup_id: 다운로드할 백업 파일의 ID

    :return: file stream or error message
    """

    try:
        # 1. DB에서 백업 정보 조회
        backup_details = db.get_backup_details_by_id(user_id, backup_id)
        if not backup_details:
            return jsonify({"error": "Backup not found"}), 404

        backup_path = backup_details["backup_path"]

        original_file_path = backup_details.get("original_file_path")
        if original_file_path:
            download_name = os.path.basename(original_file_path)
        else:
            download_name = f"rollback_{backup_id}.bin"

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
            io.BytesIO(file_bytes),                         # 바이트 스트림으로 변환
            as_attachment=True,                             # 다운로드 형식으로 응답
            download_name=download_name,                    # 다운로드 파일 이름 지정
            mimetype="application/octet-stream"             # MIME 타입 지정
        )

    except Exception as e:
        print(f"❌ Error in download_backup_file for backup_id {backup_id}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": "Internal server error while downloading backup"}), 500


@files_bp.route("/api/files/<int:file_id>", methods=["DELETE"])
@token_required
def delete_file_monitoring(user_id, file_id):
    """
    특정 파일에 대한 모니터링을 중단하는 API 엔드포인트
        - 실제 파일을 삭제하지 않고, 모니터링 상태만 Deleted로 변경

    :param user_id: 사용자 ID
    :param file_id: 모니터링을 중단할 파일의 ID

    :return: json message or error message
    """

    if not file_id:
        return jsonify({"error": "File ID is required"}), 400

    # DB에 소프트 삭제 요청 (파일 상태를 Unmonitor 변경)
    try:
        db.soft_delete_file_by_id(user_id, file_id)
        return jsonify({"message": "File monitoring stopped successfully"}), 200
    except DatabaseError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500