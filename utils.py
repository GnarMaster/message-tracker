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

