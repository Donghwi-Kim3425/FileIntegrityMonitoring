# api_token_manager.py
from connection import get_db_connection
from psycopg import connect
from flask import current_app
from dotenv import load_dotenv
import os

load_dotenv()  #



def get_token_by_user_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT token FROM api_tokens WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def save_token_to_db(user_id, token):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO api_tokens (user_id, token) VALUES (%s, %s)", (user_id, token))
    conn.commit()
    cur.close()
    conn.close()

def get_user_id_by_token(token):  # <-- 이 함수가 반드시 있어야 함
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM api_tokens WHERE token = %s",
                (token,)
            )
            result = cur.fetchone()
            if result:
                return result[0]
            return None


def get_db_connection():
    return connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"]
    )
