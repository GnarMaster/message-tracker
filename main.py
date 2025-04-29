# ✅ 주요 모듈
from keep_alive import keep_alive
import discord
import random
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ✅ .env 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# ✅ 인텐트 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True  # ✅ 서버 닉네임 가져오기 위해 꼭 필요
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ✅ Google Sheets
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").sheet1

# ✅ message_data.json 캐시
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

# ✅ on_ready
@bot.event
async def on_ready():
    global message_log
    message_log = load_data()
    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=15, minute=0)  # 매달 1일 15시
    scheduler.start()

# ✅ on_message: 캐시만 업데이트
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)

    await bot.process_commands(message)

# ✅ /이번달메시지
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        # ✅ 캐시 데이터를 구글 시트로 업로드
        sheet = get_sheet()
        records = sheet.get_all_records()
        now = datetime.now()
        year, month = now.year, now.month

        # 캐시 반영
        for key, value in message_log.items():
            uid, y, m = key.split('-')
            if int(y) == year and int(m) == month:
                try:
                    cell = sheet.find(uid)
                    if cell:
                        row = cell.row
                        sheet.update_cell(row, 3, value)
                except:
                    continue

        records = sheet.get_all_records()  # 다시 불러오기

        # ✅ 랭킹 정리
        results = []
        for row in records:
            uid_raw = str(row.get("유저 ID", "0")).strip()
            nickname = row.get("닉네임", "(Unknown)").strip()
            try:
                uid = int(float(uid_raw))
            except:
                continue

            count = int(row.get("누적메시지수", 0))
            results.append((uid, count, nickname))

        sorted_results = sorted(results, key=lambda x: -x[1])

        if not sorted_results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        medals = ["🥇", "🥈", "🥉"]
        msg = f"📊 {year}년 {month}월 메시지 랭킹 (TOP 3)\n\n"

        for i, (uid, count, nickname) in enumerate(sorted_results[:3]):
            member = interaction.guild.get_member(uid)
            username = member.display_name if member else nickname
            msg += f"{medals[i]} {username} - {count}개\n"

        await interaction.followup.send(msg)

    except Exception as e:
        import traceback
        print("❗ /이번달메시지 에러 발생:")
        traceback.print_exc()
        await interaction.followup.send("⚠️ 오류가 발생했습니다.")

# ✅ send_monthly_stats: 1일에 자동으로 축하
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
            nickname = row.get("닉네임", "(Unknown)").strip()
            try:
                uid = int(float(uid_raw))
            except:
                continue

            count = int(row.get("누적메시지수", 0))
            results.append((uid, count, nickname))

        sorted_results = sorted(results, key=lambda x: -x[1])

        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("❗ 채널을 찾을 수 없습니다.")
            return

        medals = ["🥇", "🥈", "🥉"]
        msg = f"📊 {year}년 {month}월 메시지 랭킹 (TOP 3)\n\n"

        top_mentions = []
        for i, (uid, count, nickname) in enumerate(sorted_results[:3]):
            member = channel.guild.get_member(uid)
            username = member.display_name if member else nickname
            mention = member.mention if member else f"<@{uid}>"

            msg += f"{medals[i]} {username} - {count}개\n"
            top_mentions.append(mention)

        if top_mentions:
            msg += f"\n🎉 이번 달 1등은 {top_mentions[0]} 님입니다! 모두 축하해 주세요! 🎂🎉"

        await channel.send(msg)

        # ✅ 지난달 데이터 초기화
        for key in list(message_log.keys()):
            if f"-{year}-{month}" in key:
                del message_log[key]
        save_data(message_log)

    except Exception as e:
        import traceback
        print("❗ send_monthly_stats 에러 발생:")
        traceback.print_exc()

# ✅ 웹서버 시작 (Render용)
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
