# drive_utils.py
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from database import get_google_tokens_by_user_id, save_or_update_google_tokens
from core.app_instance import app

def get_google_drive_service_for_user(user_id: int):
    user_google_tokens = get_google_tokens_by_user_id(user_id)
    if not user_google_tokens or not user_google_tokens.get("google_access_token"):
        print(f"No Google OAuth token found for user {user_id}")
        return None

    creds = Credentials(
        token=user_google_tokens['google_access_token'],
        refresh_token=user_google_tokens.get('google_refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=app.config["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=app.config["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )

    if creds.expired:
        if creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
                save_or_update_google_tokens(
                    user_id,
                    creds.token,
                    user_google_tokens.get("google_refresh_token"),  # DB 값 유지
                    creds.expiry
                )
            except Exception as e:
                print(f"❌ Failed to refresh token for user {user_id}: {e}")
                return None
        else:
            print(f"⚠️ No refresh token for user {user_id}, re-authentication required.")
            return None

    return build('drive', 'v3', credentials=creds)

def download_file_from_google_drive(service, file_id: str):
    try:
        request = service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")
        file_io.seek(0)
        return file_io.read()
    except Exception as e:
        print(f"Error downloading file from Google Drive: {e}")
        return None