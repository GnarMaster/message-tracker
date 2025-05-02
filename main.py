from keep_alive import keep_alive

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

LAST_RUN_FILE = "last_run.json"

def get_last_run_date_from_sheet():
    try:
        sheet = get_sheet().spreadsheet.worksheet("Settings")
        key = sheet.acell("A1").value.strip().lower()
        if key == "last_run":
            return sheet.acell("B1").value.strip()
    except Exception as e:
        print(f"❗ get_last_run_date_from_sheet 에러: {e}")
    return ""

def set_last_run_date_to_sheet(date_str):
    try:
        sheet = get_sheet().spreadsheet.worksheet("Settings")
        sheet.update_acell("A1", "last_run")
        sheet.update_acell("B1", date_str)
        print(f"✅ Google 시트에 last_run = {date_str} 기록됨")
    except Exception as e:
        print(f"❗ set_last_run_date_to_sheet 에러: {e}")

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

# ✅ Google Sheets 연결 함수
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").sheet1

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

# ✅ 서버 시작시
@bot.event
async def on_ready():
    global message_log
    message_log = load_data()
    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Seoul"))
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=0, minute=0)
    scheduler.start()
    print("🕛 현재 시간 (KST):", datetime.now(timezone("Asia/Seoul")))


    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    last_run = get_last_run_date_from_sheet()

    if now.day == 1 and now.hour >= 15 and today_str != last_run:
        print("🕒 Google Sheets 기준 1일 15시 이후 실행 → send_monthly_stats()")
        await send_monthly_stats()
        set_last_run_date_to_sheet(today_str)



# ✅ 채팅 감지
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        existing_data = {}

        for idx, row in enumerate(records, start=2):
            user_id = str(row.get("유저 ID", "")).strip()
            try:
                count = int(str(row.get("누적메시지수", 0)).strip())
            except:
                count = 0
            if user_id:
                existing_data[user_id] = (idx, count)

        user_id_str = str(message.author.id)

        if user_id_str in existing_data:
            row_num, current_count = existing_data[user_id_str]
            new_total = current_count + 1  # 새로 1개 추가
            sheet.update_cell(row_num, 3, new_total)
        else:
            user = message.author
            sheet.append_row([user_id_str, user.name, 1])

    except Exception as e:
        print(f"❗ on_message 업데이트 에러: {e}")
        
    await bot.process_commands(message)

# ✅ 캐시를 구글시트에 합산 저장
async def sync_cache_to_sheet():
    try:
        sheet = get_sheet()
        now = datetime.now()
        year, month = now.year, now.month

        records = sheet.get_all_records()
        existing_data = {}  # {user_id: (row_num, current_count)}

        for idx, row in enumerate(records, start=2):  # 헤더 빼고
            user_id = str(row.get("유저 ID", "")).strip()
            try:
                count = int(str(row.get("누적메시지수", 0)).strip())
            except:
                count = 0
            if user_id:
                existing_data[user_id] = (idx, count)

        for key, value in message_log.items():
            user_id, y, m = key.split('-')
            if int(y) != year or int(m) != month:
                continue

            if user_id in existing_data:
                row_num, current_count = existing_data[user_id]
                new_total = current_count + value  # 기존 누적 + 캐시값
                sheet.update_cell(row_num, 3, new_total)
            else:
                user = await bot.fetch_user(int(user_id))
                sheet.append_row([user_id, user.name, value])

            del message_log[key]

        save_data(message_log)
    except Exception as e:
        print(f"❗ sync_cache_to_sheet 에러: {e}")

# ✅ 이번달메시지 명령어
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        sheet = get_sheet()
        records = sheet.get_all_records()

        now = datetime.now()
        year, month = now.year, now.month

        results = []

        for row in records:
            uid_raw = row.get("유저 ID", "0")
            try:
                uid = int(float(uid_raw))
            except Exception:
                continue

            count = int(str(row.get("누적메시지수", 0)).strip())
            username = row.get("닉네임", f"(ID:{uid})")
            results.append((uid, count, username))

        if not results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        sorted_results = sorted(results, key=lambda x: -x[1])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

        for i, (uid, cnt, username) in enumerate(sorted_results, 1):
            msg += f"{i}. {username} - {cnt}개\n"

        await interaction.followup.send(msg)

    except Exception as e:
        print("❗ /이번달메시지 에러:")
        import traceback
        traceback.print_exc()
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except:
            pass

# ✅ 매달 1일 1등 축하
async def send_monthly_stats():
    try:
        await sync_cache_to_sheet()  # ✅ 캐시 먼저 업로드
        sheet = get_sheet()
        records = sheet.get_all_records()

        now = datetime.now()
        last_month = now.replace(day=1) - timedelta(days=1)
        year, month = last_month.year, last_month.month

        results = []

        for row in records:
            uid_raw = row.get("유저 ID", "0")
            try:
                uid = int(float(uid_raw))
            except Exception:
                continue

            count = int(str(row.get("누적메시지수", 0)).strip())
            username = row.get("닉네임", f"(ID:{uid})")
            results.append((uid, count, username))

        if not results:
            return

        sorted_results = sorted(results, key=lambda x: -x[1])

        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("❗ 채널을 찾을 수 없음")
            return

        medals = ["🥇", "🥈", "🥉"]
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n\n"

        for i, (uid, count, username) in enumerate(sorted_results[:3]):
            msg += f"{medals[i]} <@{uid}> - {count}개\n"

        if sorted_results:
            top_name = sorted_results[0][2]
            top_id = sorted_results[0][0]
            msg += f"\n🎉 지난달 1등은 <@{top_id}>님입니다! 모두 축하해주세요 🎉"

        await channel.send(msg)

        # ✅ 로컬 캐시 초기화
        for key in list(message_log.keys()):
            if f"-{year}-{month}" in key:
                del message_log[key]
        save_data(message_log)

        # ✅ Google Sheets 누적메시지수 초기화 (batch update 방식)
        cell_list = sheet.range(f"C2:C{len(records)+1}")  # C열 = 누적메시지수
        for cell in cell_list:
            cell.value = 0
        sheet.update_cells(cell_list)
        print("✅ 시트 메시지수 전체 초기화 완료")

    except Exception as e:
        print(f"❗ send_monthly_stats 에러 발생: {e}")
        traceback.print_exc()



# ✅ 공익근무표 기능
duty_cycle = ["주간", "야간", "비번", "휴무"]
start_dates = {
    "우재민": datetime(2025, 4, 15),
    "임현수": datetime(2025, 4, 14),
    "정재선": datetime(2025, 4, 12),
    "김 혁": datetime(2025, 4, 13),
}

@tree.command(name="공익근무표", description="오늘의 공익 근무표를 확인합니다.")
async def duty_chart(interaction: discord.Interaction):
    today = (datetime.utcnow() + timedelta(hours=9)).date()
    result = [f"[{today} 공익근무표]"]

    for name, start_date in start_dates.items():
        days_passed = (today - start_date.date()).days
        duty = duty_cycle[days_passed % len(duty_cycle)]
        result.append(f"{name} - {duty}")

    await interaction.response.send_message("\n".join(result))

# ✅ 점메추 기능

def load_menu():
    sheet = get_sheet()
    menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
    menus = menu_sheet.col_values(1)[1:]  # 첫 번째 열에서 헤더 빼고 메뉴만
    return menus

@tree.command(name="점메추", description="오늘의 점심 메뉴를 추천해줘요.")
async def 점메추(interaction: discord.Interaction):
    menu_list = load_menu()
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🥢 오늘의 점심 추천은... **{choice}**!")

@tree.command(name="저메추", description="오늘의 저녁 메뉴를 추천해줘요. (점메추와 동일)")
async def 저메추(interaction: discord.Interaction):
    menu_list = load_menu()
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🍽️ 오늘의 저녁 추천은... **{choice}**!")

@tree.command(name="메뉴추가", description="메뉴에 새로운 항목을 추가합니다.")
async def 메뉴추가(interaction: discord.Interaction, menu_name: str):
    try:
        await interaction.response.defer()

        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]  # 헤더 제외 메뉴만 읽기

        # 이미 있는 메뉴인지 확인
        if menu_name in menus:
            await interaction.followup.send(f"❌ 이미 '{menu_name}' 메뉴가 있어요!")
            return

        # 맨 아래에 추가
        menu_sheet.append_row([menu_name])
        await interaction.followup.send(f"✅ '{menu_name}' 메뉴가 추가됐어요!")

    except Exception as e:
        print(f"❗ /메뉴추가 에러 발생: {e}")
        await interaction.followup.send("⚠️ 메뉴 추가에 실패했습니다.")


@tree.command(name="메뉴삭제", description="메뉴에서 항목을 삭제합니다.")
async def 메뉴삭제(interaction: discord.Interaction, menu_name: str):
    try:
        await interaction.response.defer()

        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]  # 헤더 제외 읽기

        if menu_name not in menus:
            await interaction.followup.send(f"❌ '{menu_name}' 메뉴는 목록에 없어요!")
            return

        # 찾은 행 삭제
        index = menus.index(menu_name) + 2  # 2부터 시작(헤더 포함하니까)
        menu_sheet.delete_rows(index)
        await interaction.followup.send(f"🗑️ '{menu_name}' 메뉴가 삭제됐어요!")

    except Exception as e:
        print(f"❗ /메뉴삭제 에러 발생: {e}")
        await interaction.followup.send("⚠️ 메뉴 삭제에 실패했습니다.")


@tree.command(name="메뉴판", description="현재 등록된 메뉴를 보여줍니다.")
async def 메뉴판(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        # 구글시트 Menu_List 시트 읽기
        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]  # 첫 줄(헤더) 제외하고 가져오기

        if not menus:
            await interaction.followup.send("📭 등록된 메뉴가 없어요!")
            return

        # 번호 매겨서 출력
        message = "📋 현재 등록된 메뉴\n\n"
        for idx, menu in enumerate(menus, start=1):
            message += f"{idx}. {menu}\n"

        await interaction.followup.send(message)

    except Exception as e:
        print(f"❗ /메뉴판 에러 발생: {e}")
        await interaction.followup.send("⚠️ 메뉴판을 불러오는 데 실패했습니다.")
        
@tree.command(name="json확인", description="last_run.json 내용을 콘솔에 출력합니다.")
async def json확인(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("📂 last_run.json 내용을 콘솔에 출력했어요!", ephemeral=True)

        if os.path.exists("last_run.json"):
            with open("last_run.json", "r", encoding="utf-8") as f:
                last_data = json.load(f)
                print("📂 [last_run.json]", last_data)
        else:
            print("📂 [last_run.json] 파일 없음")

    except Exception as e:
        print(f"❗ /json확인 에러: {e}")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 오류가 발생했습니다.", ephemeral=True)

# ✅ Render용 Flask 서버
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
