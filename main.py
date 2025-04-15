from keep_alive import keep_alive

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json

# .env 변수 로드
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

# 봇 설정
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 파일 경로
DATA_FILE = "message_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# 데이터 불러오기
message_log = load_data()

@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")

    # 매달 1일에 자동 랭킹 전송
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=0, minute=0)
    scheduler.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)

    await bot.process_commands(message)

@bot.command(name="이번달메시지")
async def 이번달메시지(ctx):
    now = datetime.now()
    year, month = now.year, now.month
    results = []

    for key, count in message_log.items():
        uid, y, m = key.split("-")
        if int(y) == year and int(m) == month:
            results.append((int(uid), count))

    if not results:
        await ctx.send("이번 달에는 메시지가 없어요 😢")
        return

    sorted_results = sorted(results, key=lambda x: -x[1])
    msg = f"📊 {year}년 {month}월 메시지 랭킹\n"
    for i, (uid, cnt) in enumerate(sorted_results, 1):
        user = await bot.fetch_user(uid)
        msg += f"{i}. {user.name} - {cnt}개\n"

    await ctx.send(msg)

async def send_monthly_stats():
    now = datetime.now()
    last_month = now.replace(day=1) - timedelta(days=1)
    year, month = last_month.year, last_month.month
    results = []

    for key, count in message_log.items():
        uid, y, m = key.split("-")
        if int(y) == year and int(m) == month:
            results.append((int(uid), count))

    if not results:
        return

    sorted_results = sorted(results, key=lambda x: -x[1])
    msg = f"📊 {year}년 {month}월 메시지 랭킹\n"
    for i, (uid, cnt) in enumerate(sorted_results, 1):
        user = await bot.fetch_user(uid)
        msg += f"{i}. {user.name} - {cnt}개\n"

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(msg)

    # 지난달 데이터 삭제
    for key in list(message_log.keys()):
        if f"-{year}-{month}" in key:
            del message_log[key]
    save_data(message_log)

# ✅ 공익근무표 기능 추가 부분

# 주야비휴 순환 배열
duty_cycle = ["주간", "야간", "비번", "휴무"]

# 각 사람의 "주간" 시작일
start_dates = {
    "우재민": datetime(2025, 4, 15),
    "임현수": datetime(2025, 4, 14),
    "정재선": datetime(2025, 4, 12),
    "김  혁": datetime(2025, 4, 13),
}

@bot.command(name='공익근무표')
async def duty_chart(ctx):
    today = datetime.now().date()
    result = [f"[{today} 공익근무표]"]

    for name, start_date in start_dates.items():
        days_passed = (today - start_date.date()).days
        duty = duty_cycle[days_passed % len(duty_cycle)]
        result.append(f"{name} - {duty}")

    await ctx.send("\n".join(result))

@bot.command(name='공익')
async def duty_for_person(ctx, *, name):
    name = name.strip()
    if name not in start_dates:
        await ctx.send(f"{name}님의 근무 정보를 찾을 수 없습니다.")
        return

    today = datetime.now().date()
    start_date = start_dates[name]
    days_passed = (today - start_date.date()).days
    duty = duty_cycle[days_passed % len(duty_cycle)]

    await ctx.send(f"{name}님의 오늘 근무는 \"{duty}\"입니다.")

# 웹서버 켜기
keep_alive()

# 봇 실행
bot.run(TOKEN)
