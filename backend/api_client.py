import configparser, requests, os, keyring, sys
import traceback
from datetime import datetime

# --- 추가: 간단한 파일 로거 ---
def get_base_dir():
    """ .exe 파일이든 .py 스크립트든 현재 파일의 기준 디렉토리를 반환합니다. """
    if getattr(sys, 'frozen', False):
        # .exe로 패키징된 경우 (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # 일반 .py 스크립트로 실행된 경우
        return os.path.dirname(os.path.abspath(__file__))

# keyring 설정
SERVICE_NAME = "FileIntegrityMonitorClient"
KEYRING_USERNAME = "fim_user_token"

# config.ini 로드
config = configparser.ConfigParser()
config_file_path = 'config.ini'

API_BASE_URL = "https://fim-backend-buhbaactf2cgeugd.japaneast-01.azurewebsites.net" # 기본값
# if os.path.exists(config_file_path):
#     config.read(config_file_path)
#     try:
#         API_BASE_URL = config.get("API", "base_url", fallback="https://www.filemonitor.me").rstrip('/')
#     except configparser.NoSectionError:
#         print(f"[API_CLIENT WARNING] config.ini 파일에 [API] 섹션에 없습니다.")
# else:
#     print(f"[API_CLIENT WARNING] {config_file_path} 파일을 찾을 수 없습니다.")

API_TOKEN = None
HEADERS = {}

def get_token_from_keyring():
    """
    keyring에서 API 토큰을 가져오기

    :return: token or None
    """

    token = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    if token:
        return token
    else:
        return None

def save_token_to_keyring(token):
    """
    API 토큰을 저장

    :param token: API token
    """

    keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, token)

def initialize_api_credentials():
    """
    API 자격 증명 초기화
        - Keyring에서 토큰을 가져오고, 없으면 임시 파일에서 읽어와 저장
    """

    global API_TOKEN, HEADERS
    
    # 1. keyring에서 토큰 조회
    token = None
    try:
        token = get_token_from_keyring()
    except Exception as e:
        token = None

    # 실행 경로 설정
    temp_token_file = "api_token.txt"
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    temp_token_file_path = os.path.join(application_path, temp_token_file)


    # 2. 토큰이 이미 존재할 경우 -> 임시 파일 정리
    if token:
        if os.path.exists(temp_token_file_path):
            try:
                os.remove(temp_token_file_path)
            except Exception as e:
                print(f"[API_CLIENT WARNING] 임시 토큰 파일 삭제 중 오류: {e}")

    # 3. 토큰이 없을 경우 -> 임시 파일에서 복구 시도
    else:
        if os.path.exists(temp_token_file_path):
            try:
                with open(temp_token_file_path, "r") as f:
                    token_from_file = f.read().strip()

                if token_from_file:
                    try:
                        save_token_to_keyring(token_from_file)
                        token = token_from_file
                        os.remove(temp_token_file_path)
                    except Exception as keyring_e:
                        print(f"[API_CLIENT ERROR] Keyring 저장 실패! 토큰 설정을 건너뜁니다. 오류: {keyring_e}")
                else:
                    print(f"[API_CLIENT WARNING] {temp_token_file} 파일이 비어있습니다.")
            except Exception as e:
                print(f"[API_CLIENT WARNING] {temp_token_file} 파일 읽기 중 오류: {e}")
        else:
            print(f"[API_CLIENT INFO] 임시 토큰 파일 {temp_token_file_path}을(를) 찾을 수 없습니다.")

    # 4. 최종 토큰 설정
    if token:
        API_TOKEN = token
        HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
        print("[API_CLIENT INFO] API 토큰이 설정되었습니다.")
    else:
        print("[API_CLIENT WARNING] API 토큰이 설정되지 않았습니다. 서버 인증이 필요한 API 호출은 실패합니다.")

    print("[API_CLIENT INFO] initialize_api_credentials 종료.")

def fetch_file_list():
    """
    서버에서 검사 대상 파일 목록 받아오기

    :return: JSON or None
    """

    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 파일 목록을 요청할 수 없습니다.")
        return None

    try:
        response = requests.get(f"{API_BASE_URL}/api/files", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[API_CLIENT ERROR] 파일 목록 요청 실패: {e}")
        return None

def report_hash(file_path, new_hash, detection_source="unknown"):
    """
    서버에 파일의 새로운 해시값을 보고
        - 파일이 수정되었을 때 이를 서버에 알림

    :param file_path: 변경된 파일의 경로
    :param new_hash: 새 해시값
    :param detection_source: 변경 감지 유형

    :return: True or False
    """

    # 1. API 토큰이 없으면 보고 불가
    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 해시를 보고할 수 없습니다. ({file_path})")
        return False

    # 2. 서버에 전달할 데이터 구성
    data = {
        "file_path": file_path,
        "new_hash": new_hash,
        "detection_source": detection_source
    }
    try:
        # 3. 서버에 POST 요청 전송
        response = requests.post( # routes/files.py의 report_hash 호출
            f"{API_BASE_URL}/api/report_hash",
            json=data,
            headers=HEADERS # 인증 헤더 포함
        )
        # 4. HTTP 오류 발생 시 예외 처리
        response.raise_for_status()

        # 5. 성공 로그 출력 및 결과 반환
        print(f"[API_CLIENT SUCCESS] 해시 보고 성공 ({file_path}, source: {detection_source})")
        return response.status_code == 200

    # 6. 요청 실패 시 에러 로그 출력
    except requests.exceptions.HTTPError as e:
        # HTTP 응답 코드가 4xx 또는 5xx일 때 발생
        status_code = e.response.status_code
        error_text = e.response.text
        print(f"[API_CLIENT ERROR] HTTP 오류 발생 ({file_path}): {status_code}")
        print(f"  ㄴ 서버 응답: {error_text}")

    except requests.exceptions.ConnectionError as e:
        # DNS 조회 실패, 연결 거부 등 네트워크 문제 발생 시
        print(f"[API_CLIENT ERROR] 서버 연결 실패 ({file_path}): {e}")

    except requests.exceptions.Timeout as e:
        # 지정된 시간 내에 서버로부터 응답을 받지 못했을 때
        print(f"[API_CLIENT ERROR] 요청 시간 초과 ({file_path}): {e}")

    except requests.exceptions.RequestException as e:
        # 위에서 처리하지 못한 기타 모든 요청 관련 예외
        print(f"[API_CLIENT ERROR] 예상치 못한 요청 오류 발생 ({file_path}): {e}")

    return False

def register_new_file_on_server(relative_path, initial_hash, file_content_bytes=None, detection_source="unknown"):
    """
    서버에 새 파일 정보 등록

    :param relative_path: 새 파일의 상대 경로
    :param initial_hash: 새 파일의 초기 해시값
    :param file_content_bytes: 파일 내용
    :param detection_source: 변경 감지 유형

    :return: report_hash 함수의 리턴 값
    """

    print(f"[API_CLIENT INFO] 새 파일 등록 요청: {relative_path}")
    if file_content_bytes:
        print(f"  ㄴ 파일 내용({len(file_content_bytes)} bytes)은 현재 report_hash API를 통해 직접 전송되지 않습니다.")
    # 새 파일 등록도 report_hash API로 처리. 서버의 handle_file_report가 새 파일임을 인지하고 처리.
    return report_hash(relative_path, initial_hash, detection_source)

def report_file_deleted_on_server(relative_path, detection_source="unknown"):
    """
    서버에 파일 삭제 사실을 보고
        - 파일이 삭제됐음을 알리고, DB에 상태 반영 요청

    :param relative_path: 삭제된 파일의 상대 경로
    :param detection_source: 변경 감지 유형

    :return: 보고 성공 여부
    """

    # 1. API 토큰이 없으면 보고 불가
    if not API_TOKEN:
        print(f"[API_CLIENT ERROR] API 토큰이 없어 파일 삭제를 보고할 수 없습니다. ({relative_path})")
        return False

    # 2. 서버에 전달할 데이터 구성
    data = {
        "file_path": relative_path,
        "detection_source": detection_source
    }

    # 3. 요청 대상 URL 구성
    target_url = f"{API_BASE_URL}/api/file_deleted"

    try:
        # 4. 서버에 POST 요청 전송
        print(f"[API_CLIENT INFO] 파일 삭제 보고 시도: {relative_path} to {target_url}")
        response = requests.post(target_url, json=data, headers=HEADERS)

        # 5. HTTP 오류 발생 시 예외 처리
        response.raise_for_status()

        # 6. 성공 로그 출력 및 결과 반환
        print(f"[API_CLIENT SUCCESS] 파일 삭제 보고 성공 ({relative_path}, source: {detection_source})")
        return response.status_code == 200

    # 7. 요청 실패 시 에러 로그 출력
    except requests.exceptions.HTTPError as e:
        # HTTP 응답 코드가 4xx 또는 5xx일 때 발생
        status_code = e.response.status_code
        error_text = e.response.text
        print(f"[API_CLIENT ERROR] HTTP 오류로 삭제 보고 실패 ({relative_path}): {status_code}")
        print(f"  ㄴ 서버 응답: {error_text}")

    except requests.exceptions.ConnectionError as e:
        # DNS 조회 실패, 연결 거부 등 네트워크 문제 발생 시
        print(f"[API_CLIENT ERROR] 서버 연결 실패로 삭제 보고 실패 ({relative_path}): {e}")

    except requests.exceptions.Timeout as e:
        # 지정된 시간 내에 서버로부터 응답을 받지 못했을 때
        print(f"[API_CLIENT ERROR] 요청 시간 초과로 삭제 보고 실패 ({relative_path}): {e}")

    except requests.exceptions.RequestException as e:
        # 위에서 처리하지 못한 기타 모든 요청 관련 예외
        print(f"[API_CLIENT ERROR] 예상치 못한 요청 오류로 삭제 보고 실패 ({relative_path}): {e}")

    return False

def request_gdrive_backup(relative_path, file_content_bytes, file_hash, is_modified=False, change_time=None):
    """
    서버에 Google Drive 백업을 요청
        - 파일 내용을 multipart/form-data 형식으로 전송
        - 서버는 해당 파일을 Google Drive에 업로드하고 DB에 기록

    :param relative_path: 파일의 상대 경로
    :param file_content_bytes: 파일 내용 (바이트)
    :param file_hash: 파일의 해시값
    :param is_modified: 파일의 수정 여부 (True or False)
    :param change_time: 파일의 변경 시간

    :return: 백업 요청 성공 여부 (True or False)
    """

    # 1. 인증 토큰 확인 (없으면 경고 출력)
    if not API_TOKEN and not HEADERS.get("Authorization"):
        print(f"[API_CLIENT WARNING] API 토큰이 설정되지 않았습니다. Google Drive 백업은 서버 세션에 의존할 수 있습니다.")

    # 2. 파일과 데이터 페이로드 구성 (multipart/form-data 형식)
    files_payload = {
        'file_content': (
            os.path.basename(relative_path),        # 파일 이름
            file_content_bytes,                     # 파일 내용
            'application/octet-stream'              # MIME 타입
        )
    }

    data_payload = {
        "relative_path": relative_path,                     # 파일 경로
        "is_modified": "true" if is_modified else "false",  # 수정 여부
        "file_hash": file_hash                              # 해시 값
    }

    if change_time:
        if not isinstance(change_time, str):
            change_time_str = change_time.isoformat()
        else:
            change_time_str = change_time
        data_payload["change_time"] = change_time_str

    # 3. 요청 URL 구성
    endpoint_path = "/api/gdrive/backup_file"
    target_url = f"{API_BASE_URL}{endpoint_path}"

    try:
        # 4. 서버에 POST 요청 전송
        print(f"[API_CLIENT INFO] Google Drive 백업 요청 시도: {relative_path} (hash: {file_hash}) to {target_url}")
        response = requests.post(target_url, files=files_payload, data=data_payload, headers=HEADERS)
        # 5. HTTP 오류 발생 시 예외 처리
        response.raise_for_status()

        # 6. 응답 JSON 파싱 및 성공 여부 확인
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

    # 7. 예외 처리: HTTP 오류
    except requests.exceptions.HTTPError as http_err:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 실패 (HTTP Error {http_err.response.status_code}): {relative_path}")
        return False

    # 8. 예외 처리: 일반 요청 오류
    except requests.exceptions.RequestException as req_err:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 실패 ({relative_path}): {req_err}")
        return False

    # 9. 예외 처리: 기타 오류
    except Exception as e:
        print(f"[API_CLIENT ERROR] Google Drive 백업 요청 중 예외 발생 ({relative_path}): {e}")
        return False