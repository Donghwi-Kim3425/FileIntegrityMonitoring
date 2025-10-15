# alerts.py
import smtplib, os
from email.message import EmailMessage
from plyer import notification
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

    :param recipient_email: 받는 사람의 이메일 주소
    :param subject: 이메일 제목
    :param body: 이메일 본문

    :return: 성공시 None
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
        return None

# --- windows 알림 (Toast) ---
def send_windows_notification(file_path, old_hash, new_hash, change_time):
    """
    변경된 파일에 대한 Windows 시스템 알림을 plyer을 사용하여 표시

    :param file_path: 변경된 파일의 경로
    :param old_hash: 이전 해시값
    :param new_hash: 새로운 해시값
    :param change_time: 변경 감지 시간

    :return: 성공시 True
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