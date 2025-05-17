# api_client.py
import configparser, requests

config = configparser.ConfigParser()
config.read("config.ini")

API_BASE_URL = config["API"]["base_url"]
API_TOKEN = config["API"]["token"]
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}


def fetch_file_list():
    """서버에서 검사 대상 파일 목록 받아오기"""
    response = requests.get(f"{API_BASE_URL}/api/files", headers=HEADERS)
    if response.ok:
        return response.json()
    else:
        print(f"[ERROR] 파일 목록 요청 실패: {response.status_code}")
        return []


def report_hash(file_path, new_hash):
    """서버에 해시 결과 보고"""
    data = {"file_path": file_path, "new_hash": new_hash}
    response =\
        requests.post(f"{API_BASE_URL}/api/report_hash", json=data, headers=HEADERS)
    return response.status_code == 200
