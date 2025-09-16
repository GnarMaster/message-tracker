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


# ============================
# 🛡️ 검투사 반격 버프 관련 함수
# ============================

def add_counter_buff(user_id: str, username: str):
    """검투사 반격 버프를 Buff_Log에 기록 (1회성)"""
    sheet = get_sheet().spreadsheet
    try:
        buff_sheet = sheet.worksheet("Buff_Log")
    except:
        buff_sheet = sheet.add_worksheet(title="Buff_Log", rows=1000, cols=6)
        buff_sheet.append_row(["사용일시", "유저 ID", "닉네임", "상태", "시전자 ID", "시전자 닉네임"])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    buff_sheet.append_row([now_str, user_id, username, "반격", user_id, username])


def check_counter(attacker_id: str, attacker_name: str, target_id: str, target_name: str, damage: int):
    """공격 시 반격 여부를 확인하고 발동 시 메시지를 반환"""
    sheet = get_sheet().spreadsheet
    try:
        buff_sheet = sheet.worksheet("Buff_Log")
    except:
        return None

    records = buff_sheet.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID", "")) == str(target_id) and row.get("상태") == "반격":
            # 버프는 1회성이므로 삭제
            buff_sheet.delete_rows(idx)

            # 공격자 피해 반사
            main_sheet = get_sheet()
            all_records = main_sheet.get_all_records()
            for a_idx, a_row in enumerate(all_records, start=2):
                if str(a_row.get("유저 ID", "")) == str(attacker_id):
                    new_exp = safe_int(a_row.get("현재레벨경험치", 0)) - damage
                    main_sheet.update_cell(a_idx, 11, new_exp)

            # 공개 로그 메시지 반환
            return f"⚡ 앗! {target_name} 님은 반격 상태였다! → {attacker_name} 님이 {damage} 피해를 반사당했다!"
    return None


















