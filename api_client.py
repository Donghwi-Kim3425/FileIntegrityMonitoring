# api_client.py
import configparser
import requests
import os

# config.ini 로드
config = configparser.ConfigParser()
config_file_path = 'config.ini'

if os.path.exists(config_file_path):
    config.read(config_file_path)
    try:
        API_BASE_URL = config.get("API", "base_url", fallback="http://localhost:5000")
        API_TOKEN = config.get("API", "token", fallback=None)
    except configparser.NoSectionError:
        print(f"[API_CLIENT WARNING] config.ini 파일에 [API] 섹션이 없습니다. 기본값을 사용합니다.")
        API_BASE_URL = "http://localhost:5000"
        API_TOKEN = None
else:
    print(f"[API_CLIENT WARNING] {config_file_path} 파일을 찾을 수 없습니다. API 호출이 실패할 수 있습니다. 기본값을 사용합니다.")
    API_BASE_URL = "http://localhost:5000"
    API_TOKEN = None

HEADERS = {}
if API_TOKEN:
    HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
else:
    print("[API_CLIENT WARNING] API 토큰이 설정되지 않았습니다. 서버 인증이 필요한 API 호출은 실패합니다.")

def fetch_file_list():
    """서버에서 검사 대상 파일 목록 받아오기"""
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