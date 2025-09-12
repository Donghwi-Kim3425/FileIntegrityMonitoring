# app.py
import os
from flask import Flask, redirect, url_for, session
from flask_dance.contrib.google import google
from connection import app
from database import get_or_create_user

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

@app.route("/")
def index():
    # 1. 세션에 사용자 정보가 있으면 환영 메시지
    if "user" in session:
        user = session["user"]
        return f"""
            Hello, {user['username']}! Email: {user['email']}<br>
            <a href="/logout">Logout</a>
        """

    # 2. 구글 OAuth로 로그인된 상태라면 사용자 정보 fetch
    if google.authorized:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            return "Google 사용자 정보 가져오기 실패"

        user_info = resp.json()
        user = get_or_create_user(user_info['name'], user_info['email'])

        # ✅ 세션에 사용자 정보 저장
        session["user"] = user

        # index로 리디렉션 (이제 "user"가 session에 있으므로 위에서 처리됨)
        return redirect(url_for("index"))

    # 3. 로그인도 안 되어 있으면 로그인 링크 제공
    return '<a href="/login/google">Login with Google</a>'

@app.route("/login/google/authorized")
def google_authorized():
    # 이 경로는 Flask-Dance에서 자동으로 처리하지만,
    # 문제 해결을 위해 명시적으로 추가합니다
    if not google.authorized:
        return redirect(url_for("google.login"))
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
