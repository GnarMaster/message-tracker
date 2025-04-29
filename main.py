from keep_alive import keep_alive

import discord
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

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=15, minute=0)  # 매달 1일 15시
    scheduler.add_job(lambda: bot.loop.create_task(sync_cache_to_sheet()), 'interval', minutes=5)  # 🔥 5분마다
    scheduler.start()

# ✅ 채팅 감지
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)

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

    except Exception as e:
        print(f"❗ sync_cache_to_sheet 에러: {e}")

# ✅ 이번달메시지 명령어
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        await sync_cache_to_sheet()  # ✅ 캐시 먼저 업로드!

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
        await sync_cache_to_sheet()  # ✅ 캐시 먼저 업로드!
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
            return

        medals = ["🥇", "🥈", "🥉"]
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n\n"

        for i, (uid, count, username) in enumerate(sorted_results[:3]):
            msg += f"{medals[i]} {username} - {count}개\n"

        if sorted_results:
            top_name = sorted_results[0][2]
            msg += f"\n🎉 이번 달 1등은 {top_name}님입니다! 모두 축하해주세요 🎉"

        await channel.send(msg)

        # ✅ 지난달 캐시 데이터 초기화
        for key in list(message_log.keys()):
            if f"-{year}-{month}" in key:
                del message_log[key]
        save_data(message_log)

    except Exception as e:
        print(f"❗ send_monthly_stats 에러 발생: {e}")

# ✅ Render용 Flask 서버
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
