# api_client.py
import configparser, requests, os, keyring, sys

# keyring 설정
SERVICE_NAME = "FileIntergrityMonitorClient"
KEYRING_USERNAME = "fim_user_token"

# config.ini 로드
config = configparser.ConfigParser()
config_file_path = 'config.ini'

API_BASE_URL = "http://localhost:5000" # 기본값 todo 추후 수정
if os.path.exists(config_file_path):
    config.read(config_file_path)
    try:
        API_BASE_URL = config.get("API", "base_url", fallback="http://localhost:5000").rstrip('/')
    except configparser.NoSectionError:
        print(f"[API_CLIENT WARNING] config.ini 파일에 [API] 섹션에 없습니다.")
else:
    print(f"[API_CLIENT WARNING] {config_file_path} 파일을 찾을 수 없습니다.")

API_TOKEN = None
HEADERS = {}

def get_token_from_ketring():
    """ keyring에서 API 토큰을 가져옴 """

    token = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    if token:
        return token
    else:
        return None

def save_token_to_keyring(token):
    """ API 토큰을 keyring에 저장 """
    keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, token)

def initialize_api_credentials():
    """ API 자격 증명 초기화 """
    global API_TOKEN, HEADERS

    token = get_token_from_ketring()

    if not token:
        temp_token_file = "api_token.txt"
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))

        temp_token_file_path = os.path.join(application_path, temp_token_file)

        if os.path.exists(temp_token_file_path):
            try:
                with open(temp_token_file_path, "r") as f:
                    token_from_file = f.read().strip()
                if token_from_file:
                    print(f"[API_CLIENT INFO] {temp_token_file}에서 토큰을 읽었습니다. Keyring에 저장합니다.")
                    save_token_to_keyring(token_from_file)
                    token = token_from_file
                    try:
                        os.remove(temp_token_file_path)
                        print(f"[API_CLIENT INFO] 임시 토큰 파일 {temp_token_file_path}을(를) 삭제했습니다.")
                    except OSError as e:
                        print(f"[API_CLIENT WARNING] 임시 토큰 파일 {temp_token_file_path} 삭제 실패: {e}")
                else:
                    print(f"[API_CLIENT WARNING] {temp_token_file} 파일이 비어있습니다.")
            except Exception as e:
                print(f"[API_CLIENT WARNING] {temp_token_file} 파일 읽기 중 오류: {e}")
        else:
            print(f"[API_CLIENT INFO] 임시 토큰 파일 {temp_token_file_path}을(를) 찾을 수 없습니다.")

    if token:
        API_TOKEN = token
        HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
        print("[API_CLIENT INFO] API 토큰이 설정되었습니다.")
    else:
        print("[API_CLIENT WARNING] API 토큰이 설정되지 않았습니다. 서버 인증이 필요한 API 호출은 실패합니다.")

def fetch_file_list():
    """ 서버에서 검사 대상 파일 목록 받아오기"""
    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 파일 목록을 요청할 수 없습니다.")
        return None
    try:
        response = requests.get(f"{API_BASE_URL}/api/files", headers=HEADERS) # routes/files.py의 get_user_files 호출
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[API_CLIENT ERROR] 파일 목록 요청 실패: {e}")
        return None

def report_hash(file_path, new_hash, detection_source="unknown"):
    """서버에 해시 결과 보고 (파일 수정 시)"""
    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 해시를 보고할 수 없습니다. ({file_path})")
        return False
    data = {
        "file_path": file_path,
        "new_hash": new_hash,
        "detection_source": detection_source
    }
    try:
        response = requests.post(f"{API_BASE_URL}/api/report_hash", json=data, headers=HEADERS) # routes/files.py의 report_hash 호출
        response.raise_for_status()
        print(f"[API_CLIENT SUCCESS] 해시 보고 성공 ({file_path}, source: {detection_source})")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"[API_CLIENT ERROR] 해시 보고 실패 ({file_path}, source: {detection_source}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"  ㄴ 서버 응답: {e.response.status_code} / {e.response.text}")
            except: pass
        return False

def register_new_file_on_server(relative_path, initial_hash, file_content_bytes=None, detection_source="unknown"):
    """서버에 새 파일 정보 등록. report_hash 활용."""
    print(f"[API_CLIENT INFO] 새 파일 등록 요청 (report_hash API 사용): {relative_path}")
    if file_content_bytes:
        print(f"  ㄴ 파일 내용({len(file_content_bytes)} bytes)은 현재 report_hash API를 통해 직접 전송되지 않습니다.")
    # 새 파일 등록도 report_hash API로 처리. 서버의 handle_file_report가 새 파일임을 인지하고 처리.
    return report_hash(relative_path, initial_hash, detection_source)

def report_file_deleted_on_server(relative_path, detection_source="unknown"):
    """서버에 파일 삭제 보고. """
    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 파일 삭제를 보고할 수 없습니다. ({relative_path})")
        return False
    data = {
        "file_path": relative_path,
        "detection_source": detection_source
    }
    target_url = f"{API_BASE_URL}/api/file_deleted"

    try:
        print(f"[API_CLIENT INFO] 파일 삭제 보고 시도: {relative_path} to {target_url}")
        response = requests.post(target_url, json=data, headers=HEADERS)
        response.raise_for_status()
        print(f"[API_CLIENT SUCCESS] 파일 삭제 보고 성공 ({relative_path}, source: {detection_source})")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"[API_CLIENT ERROR] 파일 삭제 보고 실패 ({relative_path}, source: {detection_source}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"  ㄴ 서버 응답: {e.response.status_code} / {e.response.text}")
            except: pass
        return False

def request_gdrive_backup(relative_path, file_content_bytes, file_hash, is_modified=False):
    """ 서버에 Google Drvie 백업 요청 """
    if not API_TOKEN and not HEADERS.get("Authorization"):
        print(f"[API_CLIENT WARNING] API 토큰이 설정되지 않았습니다. Google Drive 백업은 서버 세션에 의존할 수 있습니다.")

    # 서버는 multipart/form-data 로 파일을 받는다.
    files_payload = {'file_content': (os.path.basename(relative_path),
                                      file_content_bytes, 'application/octet-stream')}
    data_payload = {
        "relative_path": relative_path,
        "is_modified": "true" if is_modified else "false",
        "file_hash": file_hash
    }

    endpoint_path = "/api/gdrive/backup_file"
    target_url = f"{API_BASE_URL}{endpoint_path}"

    try:
        print(f"[API_CLIENT INFO] Google Drive 백업 요청 시도: {relative_path} (hash: {file_hash}) to {target_url}")
        response = requests.post(target_url, files=files_payload, data=data_payload, headers=HEADERS)
        response.raise_for_status()

        response_json = response.json()
        if response_json.get("status") == "success":
            print(f"[API_CLIENT SUCCESS] Google Drive 백업 요청 성공: {relative_path}. "
                  f"Drive ID: {response_json.get('drive_file_id')}, "
                  f"Link: {response_json.get('drive_file_link')}")
            return True
        else:
            error_msg = response_json.get("message", response_json.get('error', 'Unknown Error'))
            print(f"[API_CLIENT ERROR] Google Drive 백업 요청 실패 (서버 응답): {error_msg}")
            return False

    except requests.exceptions.HTTPError as http_err:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 실패 (HTTP Error {http_err.response.status_code}): {relative_path}")
        return False

    except requests.exceptions.RequestException as req_err:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 실패 ({relative_path}): {req_err}")
        return False

    except Exception as e:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 중 예외 발생 ({relative_path}): {e}")
        return False
