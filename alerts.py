# alerts.py
import smtplib
import os
from email.message import EmailMessage
from plyer import notification
from datetime import datetime
from dotenv import  load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_SEND_EMAIL = os.getenv("SMTP_SEND_EMAIL")
SMTP_SEND_PASSWORD = os.getenv("SMTP_SEND_PASSWORD")

# --- 이메일 알림 전송 ---
def send_notification_email(recipient_email, subject, body):
    """
        지정된 수신자에게 알림 이메일을 발송

        Args:
            recipient_email (str): 받는 사람의 이메일 주소.
            subject (str): 이메일 제목.
            body (str): 이메일 본문 내용 (Plain Text).

        Returns:
            bool: 발송 성공 시 True, 실패 시 False.
        """
    # 설정 값들이 제대로 로드되었는지 확인
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_SEND_EMAIL, SMTP_SEND_PASSWORD]):
        print("이메일 발송 실패: SMTP 설정값이 .env 파일에 제대로 설정되지 않았습니다.")
        print(f"   - SERVER: {'설정됨' if SMTP_SERVER else '누락'}")
        print(f"   - PORT: {'설정됨' if SMTP_PORT else '누락 또는 오류'}")
        print(f"   - SENDER_EMAIL: {'설정됨' if SMTP_SEND_EMAIL else '누락'}")
        print(f"   - SENDER_PASSWORD: {'설정됨' if SMTP_SEND_PASSWORD else '누락'}")
        return False

    # EmailMessage 객체 생성
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_SEND_EMAIL
    message["To"] = recipient_email
    message.set_content(body)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_SEND_EMAIL, SMTP_SEND_PASSWORD)
        server.send_message(message)


# --- windows 알림 ---
def send_windows_notification(file_path, old_hash, new_hash, change_time):
    """
        변경된 파일에 대한 Windows 시스템 알림을 plyer를 사용하여 표시

    Args:
         file_path (str): 변경된 파일의 경로.
         old_hash (str): 이전 해시값.
         new_hash (str): 새로운 해시값.
         change_time (datetime): 변경 감지 시각.

    Returns:
         bool: 알림 발송 성공 시 True, 실패 시 False
    """

    notification_title = "파일 변경 감지됨"
    message_body = (
        f"파일 경로: {file_path}\n"
        f"변경 시각: {change_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"이전 해시: {old_hash}\n"
        f"새 해시: {new_hash}"
    )
    app_name = "파일 무결성 모니터링"

    notification.notify(
        title = notification_title,
        message = message_body,
        app_name = app_name,
        timeout = 10
    )
    print(f"Windows 알림(plyer) 표시 성공: {file_path}")
    return True
