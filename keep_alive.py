from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
from utils import get_sheet, safe_int  # ✅ 네 util 함수 가져오기

app = Flask('')
CORS(app)

@app.route('/')
def home():
    return "I'm alive!"

# ✅ 레벨 랭킹 API
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

    # ✅ 레벨 높은 순 → 경험치 많은 순 정렬
    results.sort(key=lambda x: (-x["level"], -x["exp"]))
    return jsonify(results)

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
