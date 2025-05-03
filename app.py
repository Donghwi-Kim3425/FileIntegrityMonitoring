# app.py
import configparser
import io
import os
import secrets
import zipfile
from flask import send_file, redirect, url_for, session, jsonify
from flask_dance.contrib.google import google
from core.app_instance import app
from database import get_or_create_user, DatabaseManager
from db.api_token_manager import get_token_by_user_id, save_token_to_db
from routes.protected import protected_bp
from routes.files import files_bp, init_files_bp

# OAUTHLIB_INSECURE_TRANSPORT 설정
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- DatabaseManager 인스턴스 생성 ---
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

# 토큰 생성 함수
def generate_api_token():
    return secrets.token_hex(32)

# --- Routes ---
@app.route("/")
def index():
    if "user" in session:
        user = session["user"]
        return f"""
            Hello, {user['username']}! Email: {user['email']}<br>
            <a href="/generate_token">[📦] API 토큰 발급</a><br>
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
        "base_url": "http://localhost:5000",  # 배포 시 변경
        "token": token
    }

    ini_io = io.StringIO()
    config.write(ini_io)
    ini_io.seek(0)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        # 1. 템플릿 파일 포함
        for file in ["file_monitor.exe"]:  # 빌드된 exe 파일 이름
            zip_file.write(os.path.join("client_dist", file), arcname=file)

        # 2. 사용자 맞춤 config.ini 포함
        zip_file.writestr("config.ini", ini_io.read())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name="integrity_client.zip", mimetype="application/zip")


app.register_blueprint(protected_bp)
app.register_blueprint(files_bp)

if __name__ == "__main__":
    app.run(debug=True)
