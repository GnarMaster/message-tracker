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
    records = sheet.get_all_records()

    now = datetime.now()
    year, month = now.year, now.month
    new_log = {}

    for row in records:
        uid = str(row.get("유저 ID", "0"))

        # 키 안전하게 추출
        count = 0
        for k in row:
            if k.strip() == "누적메시지수":
                try:
                    count = int(row[k])
                except:
                    count = 0
                break

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

    scheduler.add_job(send_birthday_congrats, 'cron', hour=15, minute=0) 
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
            except Exception as e:
                print(f"❌ UID 변환 실패: {uid_raw} -> {e}")
                continue

            # 누적메시지수 추출
            count = 0
            for k in row:
                if k.strip().replace("세", "시") == "누적메시지수":
                    try:
                        count = int(str(row[k]).strip())
                    except Exception as e:
                        print(f"⚠️ 누적메시지수 변환 실패: '{row[k]}' -> {e}")
                        count = 0
                    break

            results.append((uid, count))

        if not results:
            await interaction.followup.send("이번 달에는 메시지가 없어요 😢")
            return

        # 정렬 및 출력
        sorted_results = sorted(results, key=lambda x: -x[1])
        msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

        for i, (uid, cnt) in enumerate(sorted_results, 1):
            # 서버별 닉네임 가져오기
            member = interaction.guild.get_member(uid)
            if member:
                username = member.display_name  # 서버 닉네임
            else:
                username = f"(ID:{uid})"  # 멤버 못 찾으면 그냥 ID 표시

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



# ✅ 매달 1일 자동 랭킹 전송 + 초기화
async def send_monthly_stats():
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
        except Exception as e:
            print(f"❌ UID 변환 실패: {uid_raw} -> {e}")
            continue

        # 누적 메시지 수 추출
        count = 0
        for k in row:
            if k.strip().replace("세", "시") == "누적메시지수":
                try:
                    count = int(str(row[k]).strip())
                except:
                    count = 0
                break

        username = row.get("닉네임", f"(ID:{uid})")
        results.append((uid, count, username))

    if not results:
        print("❗ 전송할 메시지 랭킹 데이터 없음")
        return

    sorted_results = sorted(results, key=lambda x: -x[1])
    msg = f"📊 {year}년 {month}월 메시지 랭킹\n"

    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, count, username) in enumerate(sorted_results[:3]):
        msg += f"{i+1}. {medals[i]} {username} - {count}개\n"

    if sorted_results:
        top_name = sorted_results[0][2]
        msg += f"\n🎉 {top_name}님, 이번 달 1등 축하드립니다!"

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(msg)

    # ✅ 지난달 message_log 초기화 (json 캐시만)
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

@tree.command(name="저메추", description="오늘의 저녁 메뉴를 추천해줘요. (점메추와 동일)")
async def lunch_recommendation_alias(interaction: discord.Interaction):
    menu_list = load_menu()
    choice = random.choice(menu_list)
    await interaction.response.send_message(f"🥢 오늘의 저녁 추천은... **{choice}**!")

@tree.command(name="메뉴추가", description="점메추 메뉴에 새로운 항목을 추가합니다.")
async def add_menu(interaction: discord.Interaction, menu_name: str):
    menu_list = load_menu()
    if menu_name in menu_list:
        await interaction.response.send_message(f"❌ 이미 메뉴에 '{menu_name}'가 있어요!")
    else:
        menu_list.append(menu_name)
        save_menu(menu_list)
        await interaction.response.send_message(f"✅ '{menu_name}' 메뉴가 추가됐어요!")

@tree.command(name="메뉴삭제", description="점메추 메뉴에서 항목을 삭제합니다.")
async def remove_menu(interaction: discord.Interaction, menu_name: str):
    menu_list = load_menu()
    if menu_name not in menu_list:
        await interaction.response.send_message(f"❌ '{menu_name}' 메뉴는 목록에 없어요!")
    else:
        menu_list.remove(menu_name)
        save_menu(menu_list)
        await interaction.response.send_message(f"🗑️ '{menu_name}' 메뉴가 삭제됐어요.")
        
@tree.command(name="메뉴판", description="현재 등록된 점메추 메뉴를 보여줍니다.")
async def show_menu(interaction: discord.Interaction):
    menu_list = load_menu()
    if not menu_list:
        await interaction.response.send_message("📭 등록된 메뉴가 없어요!")
        return

    # 메뉴 전체를 한 번에 출력
    formatted = "\n".join(f"- {item}" for item in menu_list)
    message = f"📋 점메추 메뉴판 ({len(menu_list)}개)\n\n{formatted}"

    # 디스코드 메시지 길이 제한 대응
    if len(message) > 1900:
        await interaction.response.send_message("⚠️ 메뉴가 너무 많아서 한 번에 보여줄 수 없어요.")
    else:
        await interaction.response.send_message(message)

# ✅ 생일 저장/조회 함수
def get_birthday_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(os.getenv("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Discord_Message_Log").worksheet("Dictionary_Birth_SAVE")  # 'birthdays' 탭 이름 주의

def find_birthday(user_id):
    sheet = get_birthday_sheet()
    try:
        cell = sheet.find(str(user_id))
        if cell:
            row = sheet.row_values(cell.row)
            return row
    except:
        return None
    return None

def save_birthday(user_id, username, birthday):
    sheet = get_birthday_sheet()
    try:
        cell = sheet.find(str(user_id))
        if cell:
            # 이미 존재하면 업데이트
            sheet.update_cell(cell.row, 2, username)
            sheet.update_cell(cell.row, 3, birthday)
        else:
            # 없으면 새로 추가
            sheet.append_row([str(user_id), username, birthday])
    except Exception as e:
        print(f"❗ 생일 저장 중 에러 발생: {e}")

# ✅ 슬래시 명령어: 본인 생일 등록
@tree.command(name="생일등록", description="본인 생일을 등록합니다. (형식: MM-DD)")
async def register_birthday(interaction: discord.Interaction, birthday: str):
    await interaction.response.defer()
    try:
        datetime.strptime(birthday, "%m-%d")
    except ValueError:
        await interaction.followup.send("⚠️ 생일은 MM-DD 형식으로 입력해주세요! 예: 05-03")
        return

    save_birthday(interaction.user.id, interaction.user.name, birthday)
    await interaction.followup.send(f"✅ {interaction.user.name}님의 생일을 {birthday}로 등록했습니다!")

# ✅ 슬래시 명령어: 관리자용 남 생일 등록
@tree.command(name="생일등록_대신", description="다른 사람의 생일을 대신 등록합니다. (관리자 전용)")
@app_commands.checks.has_permissions(administrator=True)
async def register_birthday_for(interaction: discord.Interaction, member: discord.Member, birthday: str):
    await interaction.response.defer()
    try:
        datetime.strptime(birthday, "%m-%d")
    except ValueError:
        await interaction.followup.send("⚠️ 생일은 MM-DD 형식으로 입력해주세요! 예: 05-03")
        return

    save_birthday(member.id, member.name, birthday)
    await interaction.followup.send(f"✅ {member.name}님의 생일을 {birthday}로 등록했습니다!")

# ✅ 관리자 권한 오류 처리
@register_birthday_for.error
async def register_birthday_for_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("⚠️ 이 명령어는 관리자만 사용할 수 있어요.", ephemeral=True)
        
# ✅ 생일자 축하 함수
async def send_birthday_congrats():
    sheet = get_birthday_sheet()
    records = sheet.get_all_records()

    today = datetime.now().strftime("%m-%d")

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❗ 축하 보낼 채널을 찾을 수 없습니다.")
        return

    for row in records:
        user_id = str(row.get("유저 ID", ""))
        birthday = row.get("생일", "")

        if birthday == today:
            try:
                user = await bot.fetch_user(int(user_id))
                if user:
                    await channel.send(f"🎉 오늘은 <@{user.id}> 님의 생일입니다! 모두 축하해 주세요! 🎂🎉")
            except Exception as e:
                print(f"❗ 생일 축하 중 오류 발생: {e}")



# ✅ Flask 웹서버 실행 (Render용)
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
