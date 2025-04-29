from keep_alive import keep_alive

import discord
import random
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json

import requests
from bs4 import BeautifulSoup
from discord import app_commands

# ✅ Google Sheets 연동 모듈
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# .env 변수 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ✅ Google Sheets 연결
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").sheet1

# ✅ message_log 파일 I/O (로컬 캐시)
DATA_FILE = "message_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

message_log = {}

# ✅ 서버 시작
@bot.event
async def on_ready():
    global message_log
    message_log = load_data()

    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=15, minute=0)
    scheduler.add_job(send_birthday_congrats, 'cron', hour=15, minute=0)
    scheduler.add_job(save_message_log_to_sheet, 'interval', minutes=5)  # ✅ 5분마다 캐시 -> 시트 저장
    scheduler.start()

# ✅ 유저 채팅 수 저장 (캐시만)
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)

    await bot.process_commands(message)

# ✅ 캐시를 구글시트로 저장
async def save_message_log_to_sheet():
    sheet = get_sheet()
    records = sheet.get_all_records()
    user_row = {str(row["유저 ID"]): idx + 2 for idx, row in enumerate(records)}  # 2부터 데이터 시작

    now = datetime.now()
    year, month = now.year, now.month

    for key, count in message_log.items():
        uid, y, m = key.split("-")
        if int(y) == year and int(m) == month:
            if uid in user_row:
                row_num = user_row[uid]
                sheet.update_cell(row_num, 3, count)
            else:
                sheet.append_row([uid, "(Unknown)", count])

# ✅ 이번달 메시지 랭킹
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        await save_message_log_to_sheet()  # ✅ 강제 저장

        sheet = get_sheet()
        records = sheet.get_all_records()

        now = datetime.now()
        year, month = now.year, now.month

        id_to_name = {}
        for row in records:
            uid_raw = str(row.get("유저 ID", "0")).strip()
            nickname = row.get("닉네임", "(Unknown)").strip()
            id_to_name[uid_raw] = nickname

        results = []

        for row in records:
            uid_raw = row.get("유저 ID", "0")
            try:
                uid = int(float(uid_raw))
            except:
                continue

            count = 0
            for k in row:
                if k.strip().replace("세", "시") == "누적메시지수":
                    try:
                        count = int(str(row[k]).strip())
                    except:
                        count = 0
                    break

            results.append((uid, count))

        if not results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        sorted_results = sorted(results, key=lambda x: -x[1])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

        for i, (uid, cnt) in enumerate(sorted_results, 1):
            member = interaction.guild.get_member(uid)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(uid)
                except:
                    member = None

            if member:
                username = member.display_name
            else:
                username = id_to_name.get(str(uid), f"(ID:{uid})")

            msg += f"{i}. {username} - {cnt}개\n"

        await interaction.followup.send(msg)

    except Exception as e:
        import traceback
        print("❗ /이번달메시지 에러 발생:")
        traceback.print_exc()
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except:
            pass

# ✅ 월 1회 자동 랭킹 전송
async def send_monthly_stats():
    pass  # 필요하면 이어서 붙여줄게 (이건 안 바뀜)

# ✅ 생일 축하
async def send_birthday_congrats():
    pass  # 기존 유지

# ✅ Flask 웹서버 실행 (Render용)
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
