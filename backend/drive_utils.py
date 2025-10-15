import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from database import get_google_tokens_by_user_id, save_or_update_google_tokens
from core.app_instance import app

def get_google_drive_service_for_user(user_id: int):
    """
    특정 사용자에 대한 Google Drive API 서비스 객체를 생성
        - 액세스 토큰이 만료되었을 경우 자동으로 리프레시 처리
        - 유호한 자격 증명이 있으면 Google Drive 서비스 객체를 반환

    :param user_id: 사용자 ID

    :return: Google Drive 서비스 객체 or None
    """
    
    # 1. 사용자 토큰 정보 조히
    user_google_tokens = get_google_tokens_by_user_id(user_id)
    if not user_google_tokens or not user_google_tokens.get("google_access_token"):
        print(f"No Google OAuth token found for user {user_id}")
        return None
    
    # 2. Google API 자격 증명 객체 생성
    creds = Credentials(
        token=user_google_tokens['google_access_token'],                # 액세스 토큰
        refresh_token=user_google_tokens.get('google_refresh_token'),   # 리프레시 토큰
        token_uri='https://oauth2.googleapis.com/token',                # 토큰 갱신 URL
        client_id=app.config["GOOGLE_OAUTH_CLIENT_ID"],                 # 클라이언트 ID
        client_secret=app.config["GOOGLE_OAUTH_CLIENT_SECRET"],         # 클라이언트 시크릿
        scopes=["https://www.googleapis.com/auth/drive.file"]           # 필요한 권한 범위
    )
    
    # 3. 토큰이 만료되었을 경우 리프레시 처리
    if creds.expired:
        if creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest()) # Google 서버에 요청하여 토큰 갱신
                # 갱신된 토큰 정보를 DB에 업데이트
                save_or_update_google_tokens(
                    user_id,
                    creds.token,
                    user_google_tokens.get("google_refresh_token"),  # DB 값 유지
                    creds.expiry                                     # 새 만료 시간
                )
            except Exception as e:
                print(f"❌ Failed to refresh token for user {user_id}: {e}")
                return None
        else:
            print(f"⚠️ No refresh token for user {user_id}, re-authentication required.")
            return None
    
    # 4. Google Drive API 서비스 객체 생성 및 반환
    return build('drive', 'v3', credentials=creds)

def download_file_from_google_drive(service, file_id: str):
    """
    Google Drive에서 지정된 파일을 다운로드하여 바이트 형태로 변환

    :param service: 인증된 Google Drive API 서비스 객체
    :param file_id: 다운로드할 파일의 Google Drive ID

    :return: file content in bytes or None
    """

    try:
        request = service.files().get_media(fileId=file_id) # 1. 다운로드 요청 객체 생성
        file_io = io.BytesIO()                              # 2. 다운로드 데이터를 저장할 메모리 버퍼 생성
        downloader = MediaIoBaseDownload(file_io, request)  # 3. Google API의 다운로드 도우미 객체 생성
        # 4. 다운로드 진행 (chunk 단위로 반복)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")
        file_io.seek(0)
        return file_io.read()
    except Exception as e:
        print(f"Error downloading file from Google Drive: {e}")
        return None