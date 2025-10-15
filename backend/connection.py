import os, psycopg
from dotenv import load_dotenv
from flask_dance.contrib.google import make_google_blueprint
from core.app_instance import app

# .env 설정
load_dotenv()

# OAuth 설정
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

google_bp = make_google_blueprint(
    scope=[
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid",
        "https://www.googleapis.com/auth/drive.file"
    ],
    offline=True,
    reprompt_consent=True,
)
app.register_blueprint(google_bp, url_prefix="/login")

def get_db_connection():
    conn = psycopg.connect(
        dbname=app.config["DB_NAME"],
        user=app.config["DB_USER"],
        password=app.config["DB_PASSWORD"],
        host=app.config["DB_HOST"],
        port=app.config["DB_PORT"]
    )
    return conn