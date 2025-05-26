# app.py
import configparser, io, os, secrets, zipfile
from datetime import datetime
from flask import send_file, redirect, url_for, session, jsonify, request
from flask_dance.contrib.google import google
from core.app_instance import app
from database import get_or_create_user, DatabaseManager
from db.api_token_manager import get_token_by_user_id, save_token_to_db
from routes.files import files_bp, init_files_bp
from routes.protected import protected_bp
from google.oauth2.credentials import credentials, Credentials
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename

# OAUTHLIB_INSECURE_TRANSPORT 설정
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


# 토큰 생성 함수
def generate_api_token():
    return secrets.token_hex(32)


# --- DatabaseManager 인스턴스 생성 및 file_bp 초기화 ---
db_manager = None # 초기값을 None으로 설정
try:
    # database.py의 정적 메서드를 사용하여 DB 연결 및 DatabaseManager 인스턴스 생성
    db_conn = DatabaseManager.connect()
    db_manager = DatabaseManager(db_conn)
    print("✅ DatabaseManager 인스턴스 생성 성공")
except Exception as e:
    print(f"❌ DatabaseManager 생성 오류: {e}")

if db_manager:
    # 생성된 DatabaseManager 인스턴스를 files 블루프린트에 전달
    init_files_bp(db_manager)
    print(" files_bp 초기화 성공")
else:
    print("❌ db_manager가 없어 files_bp 초기화 실패. /api/files 등 관련 엔드포인트가 작동하지 않습니다.")

# --- Google Drive ---
def get_google_drive_service():
    if not google.authorized or "google_oauth_token" not in session:
        token = google.token
        if not token:
            print("get_google_drive_service: Google token not found in session or google object.")
            return None
    else:
        token = session["google_oauth_token", google.token]

    if not token or 'access_token' not in token:
        print("get_google_drive_service: Access token not found.")
        return None

    creds = Credentials(
        token = token['access_token'],
        refresh_token = token['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=app.config["GOOGLE_OAUTH_CLIENT_ID"],  #
        client_secret=app.config["GOOGLE_OAUTH_CLIENT_SECRET"],  #
        scopes=token.get('scope', ["https://www.googleapis.com/auth/drive.file"])
    )
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error creating Google Drive service: {e}")
        return None

def get_or_create_drive_folder_id(service, folder_name="FIM_Backup"):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = response.get('files', [])
    if folders:
        return folders[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_file_to_google_drive(service, drive_folder_id, client_relative_path, file_content_bytes, is_modified=False):
    original_filename = os.path.basename(client_relative_path)
    base_name, ext = os.path.splitext(original_filename)

    if is_modified:
        timestamp = datetime.now().strftime("_%Y%m%d_%H%M%S")
        drive_filename = f"{base_name}{timestamp}{ext}"
    else:
        drive_filename = original_filename

    # 파일 이름 보안 처리
    drive_filename = secure_filename(drive_filename)

    file_metadata = {
        'name': drive_filename,
        'parents': [drive_folder_id]
    }
    media = MediaIoBaseUpload(io.BytesIO(file_content_bytes), mimetype='application/octet-stream')

    created_file = service.files().create(body=file_metadata, media_body=media, fields='id, name, webViewLink').execute()
    print(f"File uploaded to Google Drive: ID '{created_file.get('id')}', Name: '{created_file.get('name')}', Link: {created_file.get('webViewLink')}")
    return created_file.get('id')

# --- Routes ---
@app.route("/")
def index():
    if "user" in session:
        user = session["user"]
        return f"""
            Hello, {user['username']}! Email: {user['email']}<br>
            <a href="/generate_token">[📦] API 토큰 발급</a><br>
            <a href="/download_client">[📥 클라이언트 다운로드 (config.ini 포함)]</a><br> 
            <a href="/logout">Logout</a>
        """

    if google.authorized:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            return "Google 사용자 정보 가져오기 실패"

        user_info = resp.json()
        user = get_or_create_user(user_info['name'], user_info['email'])
        session["user"] = user

        # 자동 토큰 발급 로직
        user_id = user["user_id"]
        existing_token = get_token_by_user_id(user_id)
        if not existing_token:  # 기존 토큰이 없을 경우에만 새로 생성 및 저장
            try:
                new_token = generate_api_token()
                save_token_to_db(user_id, new_token)
                print(f"User {user_id} logged in, new API token generated.")  # 로그 추가 (선택 사항)
            except Exception as e:
                # 토큰 저장 실패 시 오류 처리 (로깅 등)
                print(f"Error generating/saving token for user {user_id}: {e}")

        return redirect(url_for("index"))

    return '<a href="/login/google">Login with Google</a>'

@app.route("/login/google/authorized")
def google_authorized():
    if not google.authorized:
        return redirect(url_for("google.login"))
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/generate_token", methods=["GET"])
def generate_token():
    if "user" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user"]["user_id"]
    existing_token = get_token_by_user_id(user_id)
    if existing_token:
        return jsonify({"token": existing_token})

    token = generate_api_token()
    save_token_to_db(user_id, token)
    return jsonify({"token": token})


@app.route("/download_client")
def download_client():
    if "user" not in session:
        return "로그인이 필요합니다", 401

    user = session["user"]
    user_id = user["user_id"]

    token = get_token_by_user_id(user_id)
    if not token:
        token = generate_api_token()
        save_token_to_db(user_id, token)

    # config.ini 생성
    config = configparser.ConfigParser()
    config["API"] = {
        "base_url": url_for("index", _external=True)  # 배포 시 변경
    }

    ini_io = io.StringIO()
    config.write(ini_io)
    ini_io.seek(0)

    # api_token.txt 생성
    token_io = io.StringIO()
    token_io.write(token)
    token_io.seek(0)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        # 1. 클라이런트 실행 파일 포함
        client_exe_path = os.path.join("client_dist", "file_monitor.exe")
        if os.path.exists(client_exe_path):
            zip_file.write(client_exe_path, arcname="file_monitor.exe")
        else:
            py_client_path = "file_monitor.py"
            if os.path.exists(py_client_path):
                zip_file.write(py_client_path, arcname="file_monitor.py")

        # 2. 사용자 맞춤 config.ini 포함
        zip_file.writestr("config.ini", ini_io.read())

        # 3. api_token.txt 포함
        zip_file.writestr("api_token.txt", token_io.read())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="integrity_client.zip", mimetype="application/zip")

@app.route("/api/gdrive/backup_file", methods=["POST"])
def api_gdrive_backup_file():
    if "user" not in session or not google.authorized:
        return jsonify({"error": "Not logged in"}), 401

    if 'file_content' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file_storage = request.files['file_content']
    file_content_bytes = file_storage.read()

    relative_path = request.form.get('relative_path')
    is_modified_str = request.form.get('is_modified', "false").lower()
    is_modified = is_modified_str == "true"

    if not relative_path:
        return jsonify({"error": "No relative path provided"}), 400

    drive_service = get_google_drive_service()
    if not drive_service:
        return jsonify({"error": "Google Drive service not available"}), 500

    drive_folder_id = get_or_create_drive_folder_id(drive_service)
    if not drive_folder_id:
        return jsonify({"error": "Failed to create Google Drive folder"}), 500

    try:
        fim_folder_id = get_or_create_drive_folder_id(drive_service, "FIM_Backup")
        if not fim_folder_id:
            return jsonify({"error": "Failed to create FIM_Backup folder"}), 500

        uploaded_file_info = upload_file_to_google_drive(drive_service, fim_folder_id, relative_path, file_content_bytes, is_modified)
        if not uploaded_file_info and uploaded_file_info.get("id"):
            return jsonify({
                "status": "success",
                "message": f"File '{os.path.basename(relative_path)}' backed up to Google Drive as '{uploaded_file_info.get('name')}'.",
                "drive_file_id": uploaded_file_info.get("id"),
                "drive_file_link": uploaded_file_info.get("webViewLink")
            }), 200
        else:
            return jsonify({"status": "error", "message": "Failed to upload file to Google Drive."}), 500

    except Exception as e:
        print(f"Error uploading file to Google Drive: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Failed to upload file to Google Drive."}), 500



app.register_blueprint(protected_bp)
app.register_blueprint(files_bp)

if __name__ == "__main__":
    app.run(debug=True)
