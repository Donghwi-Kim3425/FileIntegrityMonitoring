# 기본 설정
import os, sys
from dotenv import load_dotenv

load_dotenv()

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
}

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')


# DLL 경로를 실행 환경에 맞게 처리 (PyInstaller 대응)
def resource_path(relative_path):
    """개발 환경과 PyInstaller 환경 모두에서 동작하는 경로 반환"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

DLL_PATH = resource_path("lib/calc_hash.dll")


def USE_WATCHDOG():
    return None