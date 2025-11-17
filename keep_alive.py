from flask import Flask, jsonify, redirect, request, session
from flask_cors import CORS
from threading import Thread
from utils import get_sheet, safe_int
import os
import requests

app = Flask('')
CORS(app)

# 세션 암호키 (Render 환경변수에 SESSION_SECRET 추가)
app.secret_key = os.getenv("SESSION_SECRET", "RANDOM_SECRET_KEY")

# Discord OAuth 환경변수 (Render에 반드시 넣어야 함)
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")  # ex) https://message-tracker-1.onrender.com/callback


# ======================================
# 기존 홈 + 랭킹 API
# ======================================

@app.route('/')
def home():
    return "I'm alive!"

@app.route('/api/ranking')
def api_ranking():
    sheet = get_sheet()
    records = sheet.get_all_records()
    results = []

    for row in records:
        uid = str(row.get("유저 ID", "")).strip()
        username = row.get("닉네임", f"(ID:{uid})")
        level = safe_int(row.get("레벨", 1))
        exp   = safe_int(row.get("현재레벨경험치", 0))

        results.append({
            "user_id": uid,
            "username": username,
            "level": level,
            "exp": exp
        })

    results.sort(key=lambda x: (-x["level"], -x["exp"]))
    return jsonify(results)


# ======================================
# 🔐 Discord 로그인 페이지 이동
# ======================================
@app.route('/login')
def login():
    url = (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=identify"
    )
    return redirect(url)


# ======================================
# 🔐 Discord OAuth Callback
# ======================================
@app.route('/callback')
def callback():
    code = request.args.get("code")

    if not code:
        return "❌ 로그인 실패: code 없음", 400

    # Access Token 요청
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post(
        "https://discord.com/api/oauth2/token", 
        data=data, 
        headers=headers
    ).json()

    access_token = token_res.get("access_token")
    if not access_token:
        return f"❌ 토큰 발급 실패: {token_res}", 400

    # 사용자 정보 가져오기
    user_res = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    user_id = user_res["id"]
    username = user_res["username"]
    avatar = user_res["avatar"]

    # GitHub Pages 프론트엔드로 리다이렉트
    frontend_url = (
        "https://gnarmaster.github.io/BGBWebGame/"
        f"?id={user_id}&name={username}&avatar={avatar}"
    )

    return redirect(frontend_url)

@app.route('/api/userinfo')
def api_userinfo():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    sheet = get_sheet()
    records = sheet.get_all_records()

    # 해당 유저 데이터 찾기
    for row in records:
        if str(row.get("유저 ID", "")).strip() == str(user_id):
            level = safe_int(row.get("레벨", 1))
            exp = safe_int(row.get("현재레벨경험치", 0))
            job = row.get("직업", "무직")
            next_exp = safe_int(row.get("다음레벨경험치", 0))

            return jsonify({
                "user_id": user_id,
                "job": job,
                "level": level,
                "exp": exp,
                "next_exp": next_exp
            })

    return jsonify({"error": "user not found"}), 404

# ======================================
# Render 서버 실행
# ======================================
def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
