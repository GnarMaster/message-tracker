from keep_alive import keep_alive

import discord
import random
import asyncio
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from discord import app_commands

# ✅ .env 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# ✅ 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ✅ Google Sheets 연동 함수
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").sheet1

# ✅ 생일 시트
def get_birthday_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").worksheet("Dictionary_Birth_SAVE")

# ✅ 캐시 파일
DATA_FILE = "message_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# ✅ 전역 변수
message_log = {}

# ✅ on_ready
@bot.event
async def on_ready():
    global message_log
    message_log = load_data()
    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(save_data_periodically, 'interval', minutes=5)  # 5분마다 저장
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=15, minute=0)  # 매달 1일
    scheduler.add_job(send_birthday_congrats, 'cron', hour=15, minute=0)  # 매일 15시
    scheduler.start()

# ✅ 5분마다 캐시 저장
async def save_data_periodically():
    save_data(message_log)

# ✅ on_message
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1

    await bot.process_commands(message)

# ✅ 이번달메시지
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        # 1. 캐시 저장 후
        save_data(message_log)

        # 2. 구글시트 업데이트
        sheet = get_sheet()
        sheet.clear()
        sheet.append_row(["유저 ID", "닉네임", "누적메시지수"])

        for key, count in message_log.items():
            user_id, year, month = key.split("-")
            sheet.append_row([user_id, "Unknown", count])

        # 3. 다시 불러오기
        records = sheet.get_all_records()
        now = datetime.now()
        year, month = now.year, now.month

        results = []
        for row in records:
            uid_raw = str(row.get("유저 ID", "0")).strip()
            nickname = str(row.get("닉네임", "(Unknown)")).strip()
            try:
                uid = int(float(uid_raw))
            except Exception:
                continue
            count = int(row.get("누적메시지수", 0))
            results.append((uid, nickname, count))

        if not results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        sorted_results = sorted(results, key=lambda x: -x[2])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

        for i, (uid, nickname, cnt) in enumerate(sorted_results, 1):
            member = interaction.guild.get_member(uid)
            if member:
                display_name = member.display_name
            else:
                display_name = nickname

            if i == 1:
                medal = "🥇 "
            elif i == 2:
                medal = "🥈 "
            elif i == 3:
                medal = "🥉 "
            else:
                medal = ""

            msg += f"{i}. {medal}{display_name} - {cnt}개\n"

        await interaction.followup.send(msg)

    except Exception as e:
        import traceback
        print("❗ /이번달메시지 에러 발생:")
        traceback.print_exc()
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except:
            pass

# ✅ 매달 1일 1등 축하
async def send_monthly_stats():
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()

        now = datetime.now()
        last_month = now.replace(day=1) - timedelta(days=1)
        year, month = last_month.year, last_month.month

        results = []
        for row in records:
            uid_raw = str(row.get("유저 ID", "0")).strip()
            nickname = str(row.get("닉네임", "(Unknown)")).strip()
            try:
                uid = int(float(uid_raw))
            except Exception:
                continue
            count = int(row.get("누적메시지수", 0))
            results.append((uid, nickname, count))

        if not results:
            return

        sorted_results = sorted(results, key=lambda x: -x[2])

        channel = bot.get_channel(CHANNEL_ID)
        if channel and sorted_results:
            winner_id = sorted_results[0][0]
            await channel.send(f"🎉 지난달 1등 <@{winner_id}> 님 축하합니다! 🏆")

    except Exception as e:
        import traceback
        print("❗ send_monthly_stats 에러:")
        traceback.print_exc()

# ✅ 생일 축하
async def send_birthday_congrats():
    sheet = get_birthday_sheet()
    records = sheet.get_all_records()

    today = datetime.now().strftime("%m-%d")
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    for row in records:
        user_id = str(row.get("유저 ID", "")).strip()
        birthday = str(row.get("생일", "")).strip()
        if birthday == today:
            try:
                user = await bot.fetch_user(int(user_id))
                if user:
                    await channel.send(f"🎉 오늘은 <@{user.id}> 님의 생일입니다! 모두 축하해 주세요! 🎂🎉")
            except:
                continue

# ✅ Flask keep_alive
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
