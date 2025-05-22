# routes/files.py
from flask import Blueprint, request, jsonify
from auth import token_required
import traceback, datetime


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

    if not file_path or new_hash is None:
        return jsonify({"error": "file_path and new_hash are required"}), 400

    result_from_db = None

    try:
        # database.py의 handle_file_report 호출
        result_from_db = db.handle_file_report(
            user_id=user_id,
            file_path=file_path,
            new_hash=new_hash,
            detection_source=detection_source
        )
        
        # 튜플로 반환되는 경우 처리
        if isinstance(result_from_db, tuple):
            # 로그를 위해 결과 출력
            print(f"[DEBUG] handle_file_report 반환 값: {result_from_db}")
            
            # HTTP 상태 코드가 첫 번째 요소인 경우
            if len(result_from_db) >= 1 and isinstance(result_from_db[0], int):
                status_code = result_from_db[0]
                
                # 성공 상태 코드인 경우 (200대)
                if 200 <= status_code < 300:
                    message = "Hash updated successfully"
                    file_id = None
                    
                    # 응답에 메시지와 file_id가 포함된 경우
                    if len(result_from_db) > 1 and result_from_db[1]:
                        if isinstance(result_from_db[1], dict):
                            message = result_from_db[1].get("message", message)
                            file_id = result_from_db[1].get("file_id")
                        elif isinstance(result_from_db[1], str):
                            message = result_from_db[1]
                    
                    return jsonify({
                        "message": message,
                        "file_id": file_id
                    }), status_code
                else:
                    # 오류 상태 코드
                    error_message = "Failed to update hash"
                    if len(result_from_db) > 1 and result_from_db[1]:
                        if isinstance(result_from_db[1], dict) and "error" in result_from_db[1]:
                            error_message = result_from_db[1]["error"]
                        elif isinstance(result_from_db[1], str):
                            error_message = result_from_db[1]
                    
                    print(f"❌ Error from db.handle_file_report for {file_path} (user {user_id}): {error_message}")
                    return jsonify({"error": error_message}), status_code
            
            # 첫 번째 요소가 상태 문자열인 경우 (예: "success", "error")
            elif len(result_from_db) >= 2 and isinstance(result_from_db[0], str):
                status = result_from_db[0]
                message = result_from_db[1] if len(result_from_db) > 1 else ""
                file_id = result_from_db[2] if len(result_from_db) > 2 else None
                
                if status == "success":
                    return jsonify({
                        "message": message,
                        "file_id": file_id
                    }), 200
                else:
                    print(f"❌ Error from db.handle_file_report for {file_path} (user {user_id}): {message}")
                    return jsonify({"error": message}), 500
            # 추가된 부분: 첫 번째 요소가 딕셔너리이고, 두 번째 요소가 정수(상태 코드)인 경우
            elif len(result_from_db) == 2 and isinstance(result_from_db[0], dict) and isinstance(result_from_db[1], int):
                response_data = result_from_db[0]
                status_code = result_from_db[1]
                
                if response_data.get("status") == "success":
                    return jsonify({
                        "message": response_data.get("message", "Operation successful."),
                        "file_id": response_data.get("file_id")
                    }), status_code
                else: # 딕셔너리 내 'status'가 'success'가 아닌 경우 (오류 등)
                    error_message = response_data.get("message", response_data.get("error", "Operation failed."))
                    print(f"❌ Error from db.handle_file_report (tuple: dict, int) for {file_path} (user {user_id}): {error_message}")
                    return jsonify({"error": error_message}), status_code
            else: # 그 외 처리되지 않은 튜플 구조
                print(f"❌ Unhandled tuple structure from db.handle_file_report for {file_path} (user {user_id}): {result_from_db}")
                return jsonify({"error": "Internal server error: Unhandled DB response format in tuple"}), 500
        
        # 딕셔너리로 반환되는 경우 처리 (기존 코드)
        elif result_from_db and isinstance(result_from_db, dict):
            if result_from_db.get("status") == "success":
                status_code = result_from_db.get("status_code", 200)
                return jsonify({
                    "message": result_from_db.get("message", "Hash updated successfully"),
                    "file_id": result_from_db.get("file_id")
                }), status_code
            else:
                status_code = result_from_db.get("status_code", 500)
                error_message = result_from_db.get("message", "Failed to update hash")
                print(f"❌ Error from db.handle_file_report for {file_path} (user {user_id}): {error_message}")
                return jsonify({"error": error_message}), status_code
        else:
            # 성공 응답이라고 가정 (200 상태 코드)
            if result_from_db == 200: # db.handle_file_report가 단순 정수 200을 반환하는 경우가 있는지 확인 필요
                return jsonify({"message": "Hash updated successfully"}), 200
            
            print(f"❌ Unexpected result type from handle_file_report for {file_path} (user {user_id}): {type(result_from_db)}, value: {result_from_db}")
            return jsonify({"error": "Failed to update hash (unexpected result type)"}), 500

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
                    return jsonify({"error": response_data.get("message", "Failed to process file deletion")}), status_code

        elif isinstance(result_from_db, dict):  # dict 단독으로 반환된 경우
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
            print(f"❌ Unexpected result from db.handle_file_deletion_report for {file_path} (user {user_id}): {result_from_db}")
            return jsonify({"error": "Internal server error processing DB response for deletion."}), 500

    except Exception as e:
        print(f"❌ Exception in handle_delete_report_api for {file_path} (user {user_id}): {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred in delete API handler."}), 500