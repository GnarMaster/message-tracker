from keep_alive import keep_alive

import discord
import random
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
import json

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

# 봇 설정 및 CommandTree 생성 (슬래시 명령어용)
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

# ✅ 시트에서 message_log 복원
def reload_message_log_from_sheet():
    sheet = get_sheet()
    records = sheet.get_all_records()  # user_id, 닉네임, 누적메시지수

    now = datetime.now()
    year, month = now.year, now.month
    new_log = {}

    for row in records:
        uid = row["유저 ID"]
        count = row["누적메시지수"]
        key = f"{uid}-{year}-{month}"
        new_log[key] = count
    return new_log

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

# ✅ 전역 메시지 로그 변수 (초기값은 비워두고 on_ready에서 세팅)
message_log = {}

# 봇 시작 시 실행되는 이벤트
@bot.event
async def on_ready():
    global message_log
    message_log = reload_message_log_from_sheet()  # ✅ 시트에서 복구

    print(f"✅ 봇 로그인 완료: {bot.user}")
    await tree.sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=15, minute=0)
    scheduler.start()

# 유저 메시지 감지 → 카운트 + 구글 시트 반영
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now()
    key = f"{message.author.id}-{now.year}-{now.month}"
    message_log[key] = message_log.get(key, 0) + 1
    save_data(message_log)

    # ✅ Google Sheets 저장
    sheet = get_sheet()
    user_id = str(message.author.id)
    username = message.author.name

    cell = sheet.find(user_id)
    if cell is not None:
        row = cell.row
        current_count = int(sheet.cell(row, 3).value)
        sheet.update_cell(row, 3, current_count + 1)
    else:
        sheet.append_row([user_id, username, 1])

    await bot.process_commands(message)

# ✅ 슬래시 명령어: 이번 달 메시지 랭킹
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
            uid = str(row.get("유저 ID", "0"))

            # 안전한 누적메시지수 추출
            count = 0
            for k in row:
                if k.strip() == "누적메시지수":
                    try:
                        count = int(row[k])
                    except:
                        count = 0
                    break

            results.append((int(uid), count))

        if not results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        sorted_results = sorted(results, key=lambda x: -x[1])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"
        for i, (uid, cnt) in enumerate(sorted_results, 1):
            try:
                user = await bot.fetch_user(uid)
                username = user.name
            except:
                username = f"(ID:{uid})"
            msg += f"{i}. {username} - {cnt}개\n"

        await interaction.followup.send(msg)

    except Exception as e:
        print(f"❗ 오류: {e}")
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except:
            pass

# ✅ 매달 1일 자동 랭킹 전송 + 초기화
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
    top_user_name = ""

    for i, (uid, cnt) in enumerate(sorted_results[:3], 1):
        user = await bot.fetch_user(uid)
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
        line = f"{i}. {medal} {user.mention} - {cnt}개\n"
        msg += line
        if i == 1:
            top_user_name = user.name

    msg += f"\n🎉 {top_user_name}님, 이번 달 1등 축하드립니다!"
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(msg)

    # 지난달 데이터 삭제
    for key in list(message_log.keys()):
        if f"-{year}-{month}" in key:
            del message_log[key]
    save_data(message_log)

# ✅ 공익근무표 명령어
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

@tree.command(name="공익", description="이름을 입력하면 해당 사람의 근무를 알려줍니다.")
async def duty_for_person(interaction: discord.Interaction, name: str):
    name = name.strip()
    if name not in start_dates:
        await interaction.response.send_message(f"{name}님의 근무 정보를 찾을 수 없습니다.")
        return

    today = datetime.now().date()
    start_date = start_dates[name]
    days_passed = (today - start_date.date()).days
    duty = duty_cycle[days_passed % len(duty_cycle)]

    await interaction.response.send_message(f"{name}님의 오늘 근무는 \"{duty}\"입니다.")

# ✅ 점메추 기능
MENU_FILE = "menu_list.json"

def load_menu():
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        "김치찌개", "굶어", "돈까스", "제육볶음", "칼국수", "국밥", "떡볶이", "맥도날드", "롯데리아", "KFC",
        "버거킹", "맘스터치", "편의점도시락", "이삭토스트", "치즈돈까스", "부리또", "짜글이", "햄부기",
        "냉면", "라멘", "치킨", "샐러드", "비빔밥", "초밥", "중국집", "쌀국수", "서브웨이", "찜닭", "카레",
        "치킨마요", "우동", "육개장", "삼계탕", "마라탕", "라면", "피자", "파스타"
    ]

def save_menu(menu):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False)

@tree.command(name="점메추", description="오늘의 점심 메뉴를 추천해줘요.")
async def lunch_recommendation(interaction: discord.Interaction):
    menu_list = load_menu()
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🥢 오늘의 점심 추천은... **{choice}**!")

@tree.command(name="메뉴추가", description="점메추 메뉴에 새로운 항목을 추가합니다.")
async def add_menu(interaction: discord.Interaction, menu_name: str):
    menu_list = load_menu()
    if menu_name in menu_list:
        await interaction.response.send_message(f"❌ 이미 메뉴에 '{menu_name}'가 있어요!")
    else:
        menu_list.append(menu_name)
        save_menu(menu_list)
        await interaction.response.send_message(f"✅ '{menu_name}' 메뉴가 추가됐어요!")

# ✅ Flask 웹서버 실행 (Render용)
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
