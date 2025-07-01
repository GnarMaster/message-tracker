from keep_alive import keep_alive

import re
import discord
import traceback
import random
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord import app_commands
from pytz import timezone
from gspread.utils import rowcol_to_a1
import aiohttp
from bs4 import BeautifulSoup
from apscheduler.triggers.cron import CronTrigger

# ✅ .env 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# ✅ 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

SPECIAL_CHANNEL_ID = 1192514064035885118  # 릴스 채널 ID
channel_special_log = {}  # {userID-YYYY-M: count}

def safe_int(val):
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return 0

# ✅ Google Sheets 클라이언트 및 워크시트 객체 전역으로 관리 (효율성 향상)
_sheet_client = None
_main_sheet = None
_settings_sheet = None
_menu_sheet = None
_birthday_sheet = None

def get_sheet_client():
    global _sheet_client
    if _sheet_client is None:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        _sheet_client = gspread.authorize(creds)
    return _sheet_client

def get_main_sheet():
    global _main_sheet
    if _main_sheet is None:
        _main_sheet = get_sheet_client().open("Discord_Message_Log").sheet1
    return _main_sheet

def get_settings_sheet():
    global _settings_sheet
    if _settings_sheet is None:
        _settings_sheet = get_sheet_client().open("Discord_Message_Log").worksheet("Settings")
    return _settings_sheet

def get_menu_sheet():
    global _menu_sheet
    if _menu_sheet is None:
        _menu_sheet = get_sheet_client().open("Discord_Message_Log").worksheet("Menu_List")
    return _menu_sheet

def get_birthday_sheet():
    global _birthday_sheet
    if _birthday_sheet is None:
        _birthday_sheet = get_sheet_client().open("Discord_Message_Log").worksheet("Dictionary_Birth_SAVE")
    return _birthday_sheet

# 이번달랭킹 실행했는지 확인하는 함수
def get_last_run_date_from_sheet():
    try:
        sheet = get_settings_sheet()
        key_cell = sheet.acell("A1")
        if key_cell and key_cell.value and key_cell.value.strip().lower() == "last_run":
            return sheet.acell("B1").value.strip()
    except Exception as e:
        print(f"❗ get_last_run_date_from_sheet 에러: {e}")
    return ""

def set_last_run_date_to_sheet(date_str):
    try:
        sheet = get_settings_sheet()
        sheet.update_acell("A1", "last_run")
        sheet.update_acell("B1", date_str)
        print(f"✅ Google 시트에 last_run = {date_str} 기록됨")
    except Exception as e:
        print(f"❗ set_last_run_date_to_sheet 에러: {e}")

# 생일축하했는지 확인하는 함수
def get_last_birthday_run():
    try:
        sheet = get_settings_sheet()
        key_cell = sheet.acell("A2")
        if key_cell and key_cell.value and key_cell.value.strip().lower() == "last_birthday_run":
            return sheet.acell("B2").value.strip()
    except Exception as e:
        print(f"❗ get_last_birthday_run 에러: {e}")
    return ""

def set_last_birthday_run(date_str):
    try:
        sheet = get_settings_sheet()
        sheet.update_acell("A2", "last_birthday_run")
        sheet.update_acell("B2", date_str)
        print(f"✅ 생일 축하 실행일 기록됨: {date_str}")
    except Exception as e:
        print(f"❗ set_last_birthday_run 에러: {e}")

# ✅ 로컬 캐시
DATA_FILE = "message_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# ✅ message_log 초기화
message_log = {}
detail_log = {}

# --- 서버 시작시 ---
@bot.event
async def on_ready():
    global message_log
    message_log = load_data()
    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    # Google Sheets 클라이언트 초기화 (여기서 한 번만 수행)
    get_sheet_client()

    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Seoul"))

    # ✅ 매월 1일 0시 0분 랭킹 정산 (KST 기준)
    scheduler.add_job(
        try_send_monthly_stats,
        CronTrigger(day=1, hour=0, minute=0, timezone=timezone("Asia/Seoul"))
    )

    # ✅ 매일 0시 0분 생일 축하 (KST 기준)
    scheduler.add_job(
        send_birthday_congrats,
        CronTrigger(hour=0, minute=0, timezone=timezone("Asia/Seoul"))
    )

    # ✅ 1분마다 캐시 동기화
    scheduler.add_job(
        sync_cache_to_sheet,
        'interval', minutes=1
    )

    scheduler.start()

    print("🕛 현재 시간 (KST):", datetime.now(timezone("Asia/Seoul")))

    # 봇이 재시작됐을 때, 만약 1일이고 아직 랭킹 정산이 안됐다면 바로 실행 (KST 기준)
    now = datetime.now(timezone("Asia/Seoul"))
    today_str = now.strftime("%Y-%m-%d")
    last_run = get_last_run_date_from_sheet()

    if now.day == 1 and today_str != last_run:
        print("🕒 봇 재시작 시 1일, Google Sheets 기준 미실행 → send_monthly_stats()")
        await send_monthly_stats()
        set_last_run_date_to_sheet(today_str)


# --- 채팅 감지 ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now(timezone("Asia/Seoul"))
    year_month = f"{message.author.id}-{now.year}-{now.month}"

    if year_month not in detail_log:
        detail_log[year_month] = {"mention": 0, "link": 0, "image": 0}

    detail_log[year_month]["mention"] += message.content.count("@")
    if "http://" in message.content or "https://" in message.content:
        detail_log[year_month]["link"] += 1
    if message.attachments:
        for att in message.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ["jpg", "jpeg", "png", "gif", "webp"]):
                detail_log[year_month]["image"] += 1

    if year_month not in message_log:
        message_log[year_month] = {"total": 0}
    message_log[year_month]["total"] += 1

    if message.channel.id == SPECIAL_CHANNEL_ID:
        special_key = f"{message.author.id}-{now.year}-{now.month}"
        if special_key not in channel_special_log:
            channel_special_log[special_key] = 0
        channel_special_log[special_key] += 1

    save_data(message_log)
    await bot.process_commands(message)


# --- 캐시를 구글시트에 합산 저장 ---
async def sync_cache_to_sheet():
    try:
        sheet = get_main_sheet()
        now = datetime.now(timezone("Asia/Seoul"))
        year, month = now.year, now.month

        records = sheet.get_all_records()
        existing_data = {}  # {user_id: {row_num: ..., "누적메시지수": ..., ...}}

        for idx, row in enumerate(records, start=2):
            user_id_raw = str(row.get("유저 ID", "")).strip()
            if not user_id_raw:
                continue

            try:
                user_id = str(int(float(user_id_raw)))
            except (ValueError, TypeError):
                print(f"⚠️ 유효하지 않은 유저 ID: {user_id_raw} (row {idx})")
                continue

            existing_data[user_id] = {
                "row_num": idx,
                "누적메시지수": safe_int(row.get("누적메시지수", 0)),
                "멘션수": safe_int(row.get("멘션수", 0)),
                "링크수": safe_int(row.get("링크수", 0)),
                "이미지수": safe_int(row.get("이미지수", 0)),
                "릴스": safe_int(row.get("릴스", 0))
            }

        update_cells = []
        keys_to_remove_from_message_log = []

        # message_log 처리
        for key, value in list(message_log.items()): # list()로 복사하여 순회 중 수정 가능하게 함
            user_id, y, m = key.split('-')
            if int(y) == year and int(m) == month: # 현재 월의 데이터만 처리
                total_count = value["total"]
                stats = detail_log.get(key, {})

                if user_id in existing_data:
                    data = existing_data[user_id]
                    row_num = data["row_num"]

                    new_total = data["누적메시지수"] + total_count
                    new_mention = data["멘션수"] + stats.get("mention", 0)
                    new_link = data["링크수"] + stats.get("link", 0)
                    new_image = data["이미지수"] + stats.get("image", 0)

                    update_cells.extend([
                        {"range": f"C{row_num}", "values": [[new_total]]},
                        {"range": f"D{row_num}", "values": [[new_mention]]},
                        {"range": f"E{row_num}", "values": [[new_link]]},
                        {"range": f"F{row_num}", "values": [[new_image]]},
                    ])
                    # 업데이트된 데이터는 캐시에서 삭제
                    keys_to_remove_from_message_log.append(key)
                else:
                    # 신규 유저 처리
                    try:
                        user = await bot.fetch_user(int(user_id))
                        new_row_data = [
                            user_id,
                            user.name,
                            total_count,
                            stats.get("mention", 0),
                            stats.get("link", 0),
                            stats.get("image", 0),
                            0 # 릴스 초기값
                        ]
                        sheet.append_row(new_row_data, value_input_option="USER_ENTERED", table_range="A1")
                        # 신규 유저는 기존 데이터에 바로 추가하여 다음 갱신 때 처리되도록 함 (정확한 row_num은 다시 읽어야 알 수 있으나, 임시 처리)
                        # 이 부분은 즉시 정확한 row_num을 얻기 어려우므로, 다음 sync_cache_to_sheet 때 반영될 것임
                        keys_to_remove_from_message_log.append(key)
                    except discord.NotFound:
                        print(f"⚠️ Discord에서 유저 ID {user_id}를 찾을 수 없습니다. (메시지 로그)")
                        continue
                    except Exception as e:
                        print(f"❗ 신규 유저 처리 중 에러: {e}")
                        traceback.print_exc()
                        continue

        # message_log와 detail_log에서 처리된 키 삭제
        for key in keys_to_remove_from_message_log:
            if key in message_log:
                del message_log[key]
            if key in detail_log:
                del detail_log[key]
        save_data(message_log)

        # channel_special_log 처리 (릴스 채널 누적 저장)
        keys_to_remove_from_special_log = []
        for key, count in list(channel_special_log.items()):
            user_id, y, m = key.split('-')
            if int(y) == year and int(m) == month: # 현재 월의 데이터만 처리
                if user_id in existing_data:
                    row_num = existing_data[user_id]["row_num"]
                    current_val = existing_data[user_id]["릴스"]
                    update_cells.append({
                        "range": f"I{row_num}",
                        "values": [[current_val + count]],
                    })
                    keys_to_remove_from_special_log.append(key)
                else:
                    # 릴스 데이터만 있는 신규 유저 처리 (매우 드물게 발생)
                    try:
                        user = await bot.fetch_user(int(user_id))
                        new_row_data = [
                            user_id,
                            user.name,
                            0, 0, 0, 0, # 메시지, 멘션, 링크, 이미지 초기값
                            count # 릴스 값
                        ]
                        sheet.append_row(new_row_data, value_input_option="USER_ENTERED", table_range="A1")
                        keys_to_remove_from_special_log.append(key)
                    except discord.NotFound:
                        print(f"⚠️ Discord에서 유저 ID {user_id}를 찾을 수 없습니다. (릴스 로그)")
                        continue
                    except Exception as e:
                        print(f"❗ 신규 릴스 유저 처리 중 에러: {e}")
                        traceback.print_exc()
                        continue

        for key in keys_to_remove_from_special_log:
            if key in channel_special_log:
                del channel_special_log[key]

        # 모든 업데이트를 한 번에 실행
        if update_cells:
            sheet.batch_update(update_cells, value_input_option="USER_ENTERED")

    except Exception as e:
        print(f"❗ sync_cache_to_sheet 에러: {e}")
        traceback.print_exc()


# --- 이번달메시지 명령어 ---
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        await sync_cache_to_sheet() # 최신 캐시를 시트에 반영

        sheet = get_main_sheet()
        records = sheet.get_all_records()

        now = datetime.now(timezone("Asia/Seoul"))
        year, month = now.year, now.month

        results = []

        for row in records:
            uid_raw = row.get("유저 ID", "0")
            try:
                uid = int(float(uid_raw))
            except (ValueError, TypeError):
                continue

            count = safe_int(row.get("누적메시지수", 0))
            username = row.get("닉네임", f"(ID:{uid})")

            results.append((uid, count, username))

        if not results or all(r[1] == 0 for r in results): # 모든 메시지 수가 0이면 빈 기록으로 간주
            await interaction.followup.send("이번 달에는 아직 메시지 기록이 없어요 😢")
            return

        sorted_results = sorted(results, key=lambda x: -x[1])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

        for i, (uid, cnt, username) in enumerate(sorted_results, 1):
            if cnt > 0: # 메시지 수가 0보다 큰 경우만 표시
                msg += f"{i}. {username} - {cnt}개\n"
            else: # 0개인 유저는 더이상 표시하지 않음 (정렬된 결과이므로)
                break


        await interaction.followup.send(msg)

    except Exception as e:
        print("❗ /이번달메시지 에러:")
        traceback.print_exc()
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except Exception:
            pass


# --- 매달 1일 자동실행 ---
async def try_send_monthly_stats():
    now = datetime.now(timezone("Asia/Seoul"))
    today_str = now.strftime("%Y-%m-%d")
    last_run = get_last_run_date_from_sheet()

    if today_str == last_run:
        print(f"✅ {now.strftime('%H:%M')} - 랭킹 정산 이미 실행됨 ({last_run}), 생략")
        return

    print(f"🕒 {now.strftime('%H:%M')} → send_monthly_stats() 실행 시도")
    await send_monthly_stats()
    set_last_run_date_to_sheet(today_str)


# --- 매달 1일 1등 축하 (핵심 수정 부분) ---
async def send_monthly_stats():
    try:
        # 1. 랭킹 정산 직전, 현재까지의 모든 캐시 데이터를 시트에 반영
        await sync_cache_to_sheet()

        sheet = get_main_sheet()
        spreadsheet = sheet.spreadsheet
        records = sheet.get_all_records()

        now = datetime.now(timezone("Asia/Seoul"))
        # 지난 달의 연도와 월 계산
        last_month_date = (now.replace(day=1) - timedelta(days=1))
        year, month = last_month_date.year, last_month_date.month

        # 랭킹 계산을 위한 데이터 준비 (지난 달 기준이므로 현재 Sheet1에 있는 데이터 사용)
        results = []
        for row in records:
            try:
                uid = int(float(row.get("유저 ID", "0")))
                count = safe_int(row.get("누적메시지수", 0))
                username = row.get("닉네임", f"(ID:{uid})")
                results.append((uid, count, username))
            except (ValueError, TypeError):
                continue

        # 랭킹 메시지 구성
        msg_parts = []
        msg_parts.append(f"📊 {year}년 {month}월 메시지 랭킹\n")

        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"❗ 채널을 찾을 수 없음: {CHANNEL_ID}")
            # 채널이 없더라도 시트 초기화 등의 후속 작업은 진행해야 합니다.

        sorted_results = sorted(results, key=lambda x: -x[1])
        valid_rank_results = [r for r in sorted_results if r[1] > 0] # 메시지 수가 0보다 큰 유저만 랭킹에 포함

        if valid_rank_results:
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, count, username) in enumerate(valid_rank_results[:3]):
                display = f"<@{uid}>" if i == 0 else username
                msg_parts.append(f"{medals[i]} {display} - {count}개")

            top_id = valid_rank_results[0][0]
            msg_parts.append(f"\n🎉 지난달 1등은 <@{top_id}>님입니다! 모두 축하해주세요 🎉")
        else:
            msg_parts.append("지난달 활동 기록이 없어요 😢")

        # ✅ 히든 랭킹 출력
        hidden_scores = {"mention": [], "link": [], "image": []}
        for row in records:
            try:
                uid = int(float(row.get("유저 ID", 0)))
                mention = safe_int(row.get("멘션수", 0))
                link = safe_int(row.get("링크수", 0))
                image = safe_int(row.get("이미지수", 0))

                hidden_scores["mention"].append((uid, mention))
                hidden_scores["link"].append((uid, link))
                hidden_scores["image"].append((uid, image))
            except (ValueError, TypeError):
                continue

        hidden_msg_parts = ["\n\n💡 히든 랭킹 🕵️"]
        names = {"mention": "📣 멘션왕", "link": "🔗 링크왕", "image": "🖼️ 사진왕"}
        for cat, entries in hidden_scores.items():
            valid_entries = [(uid, count) for uid, count in entries if count > 0]
            if valid_entries:
                top_uid, top_count = sorted(valid_entries, key=lambda x: -x[1])[0]
                try:
                    user = await bot.fetch_user(top_uid)
                    hidden_msg_parts.append(f"{names[cat]}: {user.name} ({top_count}회)")
                except discord.NotFound:
                    hidden_msg_parts.append(f"{names[cat]}: 알 수 없는 유저 ({top_count}회)")
                except Exception as e:
                    print(f"❗ 히든 랭킹 유저 fetch 에러: {e}")
                    hidden_msg_parts.append(f"{names[cat]}: 알 수 없는 유저 ({top_count}회)")
        if len(hidden_msg_parts) > 1:
            msg_parts.extend(hidden_msg_parts)

        # ✅ 릴스 채널에서 가장 많이 채팅한 사람 찾기
        try:
            top_special_list = sorted(records, key=lambda row: -safe_int(row.get("릴스", 0)))
            if top_special_list and safe_int(top_special_list[0].get("릴스", 0)) > 0:
                top_special = top_special_list[0]
                top_special_count = safe_int(top_special.get("릴스", 0))
                special_uid = int(float(top_special.get("유저 ID", 0)))
                special_user = await bot.fetch_user(special_uid)
                msg_parts.append(f"\n\n✨ 릴스파인더: {special_user.name} ({top_special_count}회)")
        except Exception as e:
            print(f"❗ 릴스 랭킹 생성 중 에러: {e}")
            traceback.print_exc()

        if channel:
            await channel.send("\n".join(msg_parts))

        # 2. 백업 시트 생성 (지난 달 이름으로)
        backup_title = f"{year}년 {month}월"
        try:
            for ws in spreadsheet.worksheets():
                if ws.title == backup_title:
                    spreadsheet.del_worksheet(ws)
                    print(f"✅ 기존 백업 시트 삭제됨: {backup_title}")
                    break
        except Exception as e:
            print(f"❗ 기존 백업 시트 삭제 실패: {e}")
            traceback.print_exc()

        sheet.duplicate(new_sheet_name=backup_title)
        print(f"✅ 시트 백업 완료: {backup_title}")

        try:
            worksheets = spreadsheet.worksheets()
            backup_ws = None
            for ws in worksheets:
                if ws.title == backup_title:
                    backup_ws = ws
                    break
            if backup_ws:
                new_order = [ws for ws in worksheets if ws.title != backup_title] + [backup_ws]
                spreadsheet.reorder_worksheets(new_order)
                print(f"✅ 백업 시트를 맨 뒤로 이동 완료: {backup_title}")
        except Exception as e:
            print(f"❗ 백업 시트 이동 실패: {e}")
            traceback.print_exc()

        # 3. Sheet1의 모든 유저 데이터 초기화 (ID와 닉네임 제외)
        if records: # 데이터가 있을 때만 업데이트 시도
            update_ranges = []
            for idx, row in enumerate(records, start=2):
                update_ranges.extend([
                    {"range": f"C{idx}", "values": [[0]]}, # 누적메시지수
                    {"range": f"D{idx}", "values": [[0]]}, # 멘션수
                    {"range": f"E{idx}", "values": [[0]]}, # 링크수
                    {"range": f"F{idx}", "values": [[0]]}, # 이미지수
                    {"range": f"I{idx}", "values": [[0]]}, # 릴스
                ])
            if update_ranges:
                # RAW 입력 모드를 사용하여 0을 정확히 숫자로 입력
                sheet.batch_update(update_ranges, value_input_option="RAW")
                print("✅ Sheet1의 모든 유저 데이터 초기화 완료 (메시지, 멘션, 링크, 이미지, 릴스 0으로)")
        else:
            # records가 비어있다면, 헤더만 남기고 시트 크기 재조정 (선택적)
            # 만약 Sheet1이 완전히 비어있다면, resize(rows=1)은 이미 헤더만 남깁니다.
            # 이 로직은 records가 비어있을 때 (즉, 유저가 한 명도 없을 때)는 특별히 할 일이 없습니다.
            # 하지만 혹시 모를 경우를 위해 아래와 같이 추가할 수 있습니다.
            try:
                current_rows = sheet.row_count
                if current_rows > 1: # 헤더만 있는 상태가 아니라면
                    sheet.resize(rows=1) # 헤더만 남기고 전부 삭제
                    print("✅ Sheet1이 비어있어 전체 초기화 진행 (헤더만 남김)")
            except Exception as e:
                print(f"❗ Sheet1 초기화 중 에러 (유저 없음): {e}")


        # 4. 로컬 캐시 (message_log, detail_log, channel_special_log) 완전히 초기화
        global message_log, detail_log, channel_special_log
        message_log = {}
        detail_log = {}
        channel_special_log = {}
        save_data(message_log) # 빈 데이터 상태를 파일에 저장
        print("✅ 로컬 캐시 (message_log, detail_log, channel_special_log) 완전 초기화 완료")


    except Exception as e:
        print(f"❗ send_monthly_stats 에러 발생: {e}")
        traceback.print_exc()


# --- 공익근무표 기능 ---
duty_cycle = ["주간", "야간", "비번", "휴무"]
start_dates = {
    "임현수": datetime(2025, 4, 14, tzinfo=timezone("Asia/Seoul")), # KST 명시
    "정재선": datetime(2025, 4, 12, tzinfo=timezone("Asia/Seoul")), # KST 명시
    "김 혁": datetime(2025, 4, 13, tzinfo=timezone("Asia/Seoul")), # KST 명시
}

@tree.command(name="공익근무표", description="오늘의 공익 근무표를 확인합니다.")
async def duty_chart(interaction: discord.Interaction):
    today = datetime.now(timezone("Asia/Seoul")).date()
    result = [f"[{today} 공익근무표]"]

    for name, start_date in start_dates.items():
        days_passed = (today - start_date.date()).days
        duty = duty_cycle[days_passed % len(duty_cycle)]
        result.append(f"{name} - {duty}")

    await interaction.response.send_message("\n".join(result))

# --- 점메추 기능 ---
def load_menu():
    sheet = get_menu_sheet()
    menus = sheet.col_values(1)[1:]
    return menus

@tree.command(name="점메추", description="오늘의 점심 메뉴를 추천해줘요.")
async def 점메추(interaction: discord.Interaction):
    menu_list = load_menu()
    if not menu_list:
        await interaction.response.send_message("📭 메뉴 리스트가 비어있어요. 메뉴를 추가해주세요!")
        return
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🥢 오늘의 점심 추천은... **{choice}**!")

@tree.command(name="저메추", description="오늘의 저녁 메뉴를 추천해줘요. (점메추와 동일)")
async def 저메추(interaction: discord.Interaction):
    menu_list = load_menu()
    if not menu_list:
        await interaction.response.send_message("📭 메뉴 리스트가 비어있어요. 메뉴를 추가해주세요!")
        return
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🍽️ 오늘의 저녁 추천은... **{choice}**!")

@tree.command(name="메뉴추가", description="메뉴에 새로운 항목을 추가합니다.")
async def 메뉴추가(interaction: discord.Interaction, menu_name: str):
    try:
        await interaction.response.defer()

        sheet = get_menu_sheet()
        menus = sheet.col_values(1)[1:]

        if menu_name in menus:
            await interaction.followup.send(f"❌ 이미 '{menu_name}' 메뉴가 있어요!")
            return

        sheet.append_row([menu_name])
        await interaction.followup.send(f"✅ '{menu_name}' 메뉴가 추가됐어요!")

    except Exception as e:
        print(f"❗ /메뉴추가 에러 발생: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 메뉴 추가에 실패했습니다.")


@tree.command(name="메뉴삭제", description="메뉴에서 항목을 삭제합니다.")
async def 메뉴삭제(interaction: discord.Interaction, menu_name: str):
    try:
        await interaction.response.defer()

        sheet = get_menu_sheet()
        menus = sheet.col_values(1)[1:]

        if menu_name not in menus:
            await interaction.followup.send(f"❌ '{menu_name}' 메뉴는 목록에 없어요!")
            return

        cell = sheet.find(menu_name, in_column=1)
        if cell:
            sheet.delete_rows(cell.row)
            await interaction.followup.send(f"🗑️ '{menu_name}' 메뉴가 삭제됐어요!")
        else:
            await interaction.followup.send(f"❌ '{menu_name}' 메뉴를 시트에서 찾을 수 없어요. (재확인 필요)")

    except Exception as e:
        print(f"❗ /메뉴삭제 에러 발생: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 메뉴 삭제에 실패했습니다.")


@tree.command(name="메뉴판", description="현재 등록된 메뉴를 보여줍니다.")
async def 메뉴판(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        sheet = get_menu_sheet()
        menus = sheet.col_col_values(1)[1:]

        if not menus:
            await interaction.followup.send("📭 등록된 메뉴가 없어요!")
            return

        message = "📋 현재 등록된 메뉴\n\n"
        for idx, menu in enumerate(menus, start=1):
            message += f"{idx}. {menu}\n"

        await interaction.followup.send(message)

    except Exception as e:
        print(f"❗ /메뉴판 에러 발생: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 메뉴판을 불러오는 데 실패했습니다.")

# --- 생일추가 기능 ---
@tree.command(name="생일추가", description="당신의 생일을 추가합니다. (형식: MMDD)")
@app_commands.describe(birthday="생일을 MMDD 형식으로 입력해주세요. 예: 0402")
async def 생일추가(interaction: discord.Interaction, birthday: str):
    try:
        await interaction.response.defer()

        if not (birthday.isdigit() and len(birthday) == 4):
            await interaction.followup.send("⚠️ 생일은 MMDD 형식의 숫자 4자리로 입력해주세요! 예: 0402")
            return

        month = birthday[:2]
        day = birthday[2:]
        formatted_birthday = f"{month}-{day}"

        try:
            datetime.strptime(formatted_birthday, "%m-%d")
        except ValueError:
            await interaction.followup.send("⚠️ 존재하지 않는 날짜예요! (예: 0231은 안돼요)")
            return

        user_id = str(interaction.user.id)
        nickname = interaction.user.name

        sheet = get_birthday_sheet()
        records = sheet.get_all_records()

        updated = False

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")).strip() == user_id:
                sheet.update_cell(idx, 3, formatted_birthday)
                updated = True
                break

        if not updated:
            sheet.append_row([user_id, nickname, formatted_birthday])

        await interaction.followup.send(f"🎉 생일이 `{formatted_birthday}`로 저장됐어요!")

    except Exception as e:
        print(f"❗ /생일추가 에러 발생: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 생일 저장 중 오류가 발생했어요.")

# --- 생일축하 기능 ---
async def send_birthday_congrats():
    try:
        today_kst = datetime.now(timezone("Asia/Seoul"))
        today_str = today_kst.strftime("%Y-%m-%d")
        last_run = get_last_birthday_run()

        if last_run == today_str:
            print("✅ 오늘 생일 축하 이미 완료됨")
            return

        sheet = get_birthday_sheet()
        records = sheet.get_all_records()
        today_md = today_kst.strftime("%m-%d")
        birthday_users = []

        for row in records:
            if row.get("생일", "").strip() == today_md:
                uid = str(row.get("유저 ID", "")).strip()
                birthday_users.append(uid)

        if birthday_users:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                mentions = "\n".join([f"🎂 <@{uid}> 님" for uid in birthday_users])
                msg = f"🎉 오늘은 생일인 친구들이 있어요!\n{mentions}\n🎉 다 함께 축하해주세요! 🎈"
                await channel.send(msg)

            set_last_birthday_run(today_str)
        else:
            print("ℹ️ 오늘 생일인 유저 없음. 실행 기록은 하지 않음.")

    except Exception as e:
        print(f"❗ 생일 축하 에러 발생: {e}")
        traceback.print_exc()

# --- 랭킹정산 명령어 (관리자용) ---
@tree.command(name="랭킹정산", description="이번 달 메시지 랭킹을 수동으로 정산합니다. (관리자용)")
@app_commands.default_permissions(administrator=True)
async def 랭킹정산(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        today_str = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d")
        last_run = get_last_run_date_from_sheet()

        if today_str == last_run:
            await interaction.followup.send(f"✅ 이미 오늘({today_str}) 실행되었습니다.")
            return

        await send_monthly_stats()
        set_last_run_date_to_sheet(today_str)
        await interaction.followup.send("📊 랭킹 정산이 완료되었습니다.")

    except Exception as e:
        print(f"❗ /랭킹정산 에러 발생: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 랭킹 정산 중 오류가 발생했습니다.")


# ✅ Render용 Flask 서버
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
