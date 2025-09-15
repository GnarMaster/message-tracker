import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def safe_int(val):
    try:
        return int(str(val).strip())
    except:
        return 0

def get_job_icon(job: str) -> str:
    icons = {
        "백수": "🎖️",
        "전사": "⚔️",
        "마법사": "🔮",
        "도적": "🥷",
        "특수": "🎭",
        "궁수": "🏹"
    }
    return icons.get(job, "🎖️")


def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").sheet1

from datetime import datetime

# ✅ 카피닌자가 복사한 스킬 저장
def save_copied_skill(user_id: str, skill_name: str):
    sheet = get_sheet().spreadsheet
    try:
        ws = sheet.worksheet("Copied_Skill")
    except:
        ws = sheet.add_worksheet(title="Copied_Skill", rows=1000, cols=3)
        ws.append_row(["유저 ID", "복사한 스킬명", "저장시간"])

    # 기존 기록 있으면 삭제
    records = ws.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID")) == user_id:
            ws.delete_rows(idx)
            break

    # 새 기록 추가
    ws.append_row([user_id, skill_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


# ✅ 카피닌자가 현재 복사해둔 스킬 조회
def get_copied_skill(user_id: str) -> str | None:
    sheet = get_sheet().spreadsheet
    try:
        ws = sheet.worksheet("Copied_Skill")
    except:
        return None

    records = ws.get_all_records()
    for row in records:
        if str(row.get("유저 ID")) == user_id:
            return row.get("복사한 스킬명")
    return None


# ✅ 카피닌자 복사 스킬 초기화 (사용 후 삭제)
def clear_copied_skill(user_id: str):
    sheet = get_sheet().spreadsheet
    try:
        ws = sheet.worksheet("Copied_Skill")
    except:
        return

    records = ws.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID")) == user_id:
            ws.delete_rows(idx)
            break
