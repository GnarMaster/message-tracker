from keep_alive import keep_alive
import re
import discord
import traceback
import random
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio
import AsyncIOScheduler
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

LAST_RUN_FILE = "last_run.json"

# 이번달랭킹 실행했는지 확인하는 함수

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

        

#생일축하했는지 확인하는 함수

def get_last_birthday_run():

    try:

        sheet = get_sheet().spreadsheet.worksheet("Settings")

        key = sheet.acell("A2").value.strip().lower()

        if key == "last_birthday_run":

            return sheet.acell("B2").value.strip()

    except Exception as e:

        print(f"❗ get_last_birthday_run 에러: {e}")

    return ""



def set_last_birthday_run(date_str):

    try:

        sheet = get_sheet().spreadsheet.worksheet("Settings")

        sheet.update_acell("A2", "last_birthday_run")

        sheet.update_acell("B2", date_str)

        print(f"✅ 생일 축하 실행일 기록됨: {date_str}")

    except Exception as e:

        print(f"❗ set_last_birthday_run 에러: {e}")





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



SPECIAL_CHANNEL_ID = 1192514064035885118  # 릴스 채널 ID

channel_special_log = {}  # {userID-YYYY-M: count}

def safe_int(val):

    try:

        return int(str(val).strip())

    except:

        return 0



#✅ Google Sheets 연결 함수

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

detail_log = {}



# ✅ 서버 시작시

@bot.event

async def on_ready():

    global message_log

    message_log = load_data()

    print(f"✅ 봇 로그인 완료: {bot.user}")

    await tree.sync()

    scheduler = AsyncIOScheduler(timezone=timezone("Asia/Seoul"))

    scheduler.add_job(send_monthly_stats, 'cron', day=1, hour=0, minute=0)

    scheduler.add_job(send_birthday_congrats, 'cron', hour=0, minute=0)

 # ✅ 1분마다 실행되는 작업 등록

    @scheduler.scheduled_job('interval', minutes=1)

    async def periodic_sync():

        await sync_cache_to_sheet()



    scheduler.start()

    

    print("🕛 현재 시간 (KST):", datetime.now(timezone("Asia/Seoul")))





    now = datetime.now()

    today_str = now.strftime("%Y-%m-%d")

    last_run = get_last_run_date_from_sheet()



    if now.day == 1 and now.hour >= 15 and today_str != last_run:

        print("🕒 Google Sheets 기준 1일 15시 이후 실행 → send_monthly_stats()")

        await send_monthly_stats()

        set_last_run_date_to_sheet(today_str)

    scheduler.add_job(

    try_send_monthly_stats,

    CronTrigger(day=1, hour=12, minute='0,5,10,15,20,25,30,35,40,45,50,55')

    )







# ✅ 채팅 감지

@bot.event

async def on_message(message):

    if message.author.bot:

        return



    now = datetime.now()

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





# ✅ 캐시를 구글시트에 합산 저장

async def sync_cache_to_sheet():

    

    try:

        sheet = get_sheet()

        now = datetime.now()

        year, month = now.year, now.month



        records = sheet.get_all_records()

        existing_data = {}  # {user_id: (row_num, current_total)}



        # 기존 사용자 데이터 저장

        for idx, row in enumerate(records, start=2):

            user_id = str(row.get("유저 ID", "")).strip()

            try:

                count = int(str(row.get("누적메시지수", 0)).strip())

            except:

                count = 0

            if user_id:

                existing_data[user_id] = (idx, count)



        update_data = []



        for key, value in list(message_log.items()):

            user_id, y, m = key.split('-')

            if int(y) != year or int(m) != month:

                continue



            total_count = value["total"]

            stats = detail_log.get(key, {})



            if user_id in existing_data:

                row_num, current_total = existing_data[user_id]

                new_total = current_total + total_count

                existing_row = records[row_num - 2]

                mention_total = safe_int(existing_row.get("멘션수", 0)) + stats.get("mention", 0)

                link_total = safe_int(existing_row.get("링크수", 0)) + stats.get("link", 0)

                image_total = safe_int(existing_row.get("이미지수", 0)) + stats.get("image", 0)

               

                update_data.extend([

                    {"range": f"C{row_num}", "values": [[new_total]]},

                    {"range": f"D{row_num}", "values": [[mention_total]]},

                    {"range": f"E{row_num}", "values": [[link_total]]},

                    {"range": f"F{row_num}", "values": [[image_total]]},

                ])



            else:

                # 신규 유저 처리

               # 신규 유저 처리

                user = await bot.fetch_user(int(user_id))

                row = [

                    user_id,

                    user.name,

                    total_count,

                    stats.get("mention", 0),

                    stats.get("link", 0),

                    stats.get("image", 0),

                ]

                sheet.append_row(row, value_input_option="USER_ENTERED", table_range="A1")  # A열부터 맞춰서 넣음

            del message_log[key]



      

        save_data(message_log)



                # ✅ 릴스 채널 누적 저장

        for key, count in list(channel_special_log.items()):

            user_id, y, m = key.split('-')

            if int(y) != year or int(m) != month:

                continue

            if user_id in existing_data:

                row_num, _ = existing_data[user_id]

                current_val = safe_int(records[row_num - 2].get("릴스", 0))

                update_data.append({

                    "range": f"I{row_num}",

                    "values": [[current_val + count]],

                })

            # 캐시 삭제

            del channel_special_log[key]

        

        for key in list(detail_log.keys()):

            if f"-{year}-{month}" in key:

                del detail_log[key]



        if update_data:

            sheet.batch_update(update_data, value_input_option="USER_ENTERED")

    

    except Exception as e:

        print(f"❗ sync_cache_to_sheet 에러: {e}")

        traceback.print_exc()





# ✅ 이번달메시지 명령어

@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")

async def 이번달메시지(interaction: discord.Interaction):

    try:

        await interaction.response.defer()

        

        await sync_cache_to_sheet()  # ✅ 캐시 먼저 업로드



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

            

# 매달1일 자동실행            

async def try_send_monthly_stats():

    now = datetime.now(timezone("Asia/Seoul"))

    today_str = now.strftime("%Y-%m-%d")

    last_run = get_last_run_date_from_sheet()



    if today_str != last_run:

        print(f"🕒 {now.strftime('%H:%M')} → send_monthly_stats() 실행 시도")

        await send_monthly_stats()

        set_last_run_date_to_sheet(today_str)

    else:

        print(f"✅ {now.strftime('%H:%M')} - 이미 실행됨 ({last_run}), 생략")



# ✅ 매달 1일 1등 축하

async def send_monthly_stats():

    try:

        await sync_cache_to_sheet()

        sheet = get_sheet()

        spreadsheet = sheet.spreadsheet

        records = sheet.get_all_records()



        now = datetime.now()

        last_month = now.replace(day=1) - timedelta(days=1)

        year, month = last_month.year, last_month.month



        results = []



        for row in records:

            try:

                uid = int(float(row.get("유저 ID", "0")))

                count = int(str(row.get("누적메시지수", 0)).strip())

                username = row.get("닉네임", f"(ID:{uid})")

                results.append((uid, count, username))

            except:

                continue



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

            display = f"<@{uid}>" if i == 0 else username  # 1등만 태그

            msg += f"{medals[i]} {display} - {count}개\n"



        if sorted_results:

            top_id = sorted_results[0][0]

            msg += f"\n🎉 지난달 1등은 <@{top_id}>님입니다! 모두 축하해주세요 🎉"



        # ✅ 히든 랭킹 출력

        hidden_scores = {"mention": [], "link": [], "image": []}

        for row in records:

            try:

                uid = int(float(row.get("유저 ID", 0)))

                mention = int(row.get("멘션수", 0))

                link = int(row.get("링크수", 0))

                image = int(row.get("이미지수", 0))

               

                hidden_scores["mention"].append((uid, mention))

                hidden_scores["link"].append((uid, link))

                hidden_scores["image"].append((uid, image))

               

            except:

                continue



        hidden_msg = "\n\n💡 히든 랭킹 🕵️"

        names = {"mention": "📣 멘션왕", "link": "🔗 링크왕", "image": "🖼️ 사진왕"}

        for cat, entries in hidden_scores.items():

            if entries:

                top_uid, top_count = sorted(entries, key=lambda x: -x[1])[0]

                if top_count > 0:

                    user = await bot.fetch_user(top_uid)

                    hidden_msg += f"\n{names[cat]}: {user.name} ({top_count}회)"

        msg += hidden_msg



        # ✅ 릴스 채널에서 가장 많이 채팅한 사람 찾기

        try:

            top_special = sorted(records, key=lambda row: -safe_int(row.get("릴스", 0)))[0]

            top_special_count = safe_int(top_special.get("릴스", 0))

            if top_special_count > 0:

                special_uid = int(float(top_special.get("유저 ID", 0)))

                special_user = await bot.fetch_user(special_uid)

                msg += f"\n\n✨ 릴스파인더: {special_user.name} ({top_special_count}회)"

        except Exception as e:

            print(f"❗ 릴스 랭킹 에러: {e}")



    



        

        await channel.send(msg)



        # ✅ 캐시 초기화

        for key in list(message_log.keys()):

            if f"-{year}-{month}" in key:

                del message_log[key]

        save_data(message_log)



        # ✅ 백업 시트 생성

        backup_title = f"{year}년 {month}월"

        try:

            for ws in spreadsheet.worksheets():

                if ws.title == backup_title:

                    spreadsheet.del_worksheet(ws)

                    break

        except Exception as e:

            print(f"❗ 기존 백업 시트 삭제 실패: {e}")



        sheet.duplicate(new_sheet_name=backup_title)

        print(f"✅ 시트 백업 완료: {backup_title}")



        try:

            spreadsheet = sheet.spreadsheet

            worksheets = spreadsheet.worksheets()

            for i, ws in enumerate(worksheets):

                if ws.title == backup_title:

                    spreadsheet.reorder_worksheets(

                        worksheets[:i] + worksheets[i+1:] + [ws]

                    )

                    print(f"✅ 백업 시트를 맨 뒤로 이동 완료: {backup_title}")

                    break

        except Exception as e:

            print(f"❗ 백업 시트 이동 실패: {e}")

        

        # ✅ Sheet1 초기화

        sheet.resize(rows=1)  # 헤더만 남기고 전체 삭제

        print("✅ Sheet1 초기화 완료 (헤더만 남김)")





    except Exception as e:

        print(f"❗ send_monthly_stats 에러 발생: {e}")

        traceback.print_exc()



# ✅ 공익근무표 기능

duty_cycle = ["주간", "야간", "비번", "휴무"]

start_dates = {  

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

    menus = menu_sheet.col_values(1)[1:]  # 첫 번째 열에서 헤더 빼고 메뉴만

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

        menus = menu_sheet.col_values(1)[1:]  # 헤더 제외 메뉴만 읽기



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

        menus = menu_sheet.col_values(1)[1:]  # 헤더 제외 읽기



        if menu_name not in menus:

            await interaction.followup.send(f"❌ '{menu_name}' 메뉴는 목록에 없어요!")

            return



        # 찾은 행 삭제

        index = menus.index(menu_name) + 2  # 2부터 시작(헤더 포함하니까)

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

        menus = menu_sheet.col_values(1)[1:]  # 첫 줄(헤더) 제외하고 가져오기



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



# ✅ 생일추가 기능

@tree.command(name="생일추가", description="당신의 생일을 추가합니다. (형식: MMDD)")

@app_commands.describe(birthday="생일을 MMDD 형식으로 입력해주세요. 예: 0402")

async def 생일추가(interaction: discord.Interaction, birthday: str):

    try:

        await interaction.response.defer()



        # ✅ 숫자만 4자리 입력됐는지 확인

        if not (birthday.isdigit() and len(birthday) == 4):

            await interaction.followup.send("⚠️ 생일은 MMDD 형식의 숫자 4자리로 입력해주세요! 예: 0402")

            return



        # ✅ MM-DD 형태로 변환

        month = birthday[:2]

        day = birthday[2:]

        formatted_birthday = f"{month}-{day}"



        # ✅ 날짜 검증

        try:

            datetime.strptime(formatted_birthday, "%m-%d")

        except ValueError:

            await interaction.followup.send("⚠️ 존재하지 않는 날짜예요! (예: 0231은 안돼요)")

            return



        user_id = str(interaction.user.id)

        nickname = interaction.user.name



        sheet = get_sheet().spreadsheet.worksheet("Dictionary_Birth_SAVE")

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

        import traceback

        traceback.print_exc()

        await interaction.followup.send("⚠️ 생일 저장 중 오류가 발생했어요.")







# ✅ 생일축하 기능 

async def send_birthday_congrats():

    try:

        today_str = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d")

        last_run = get_last_birthday_run()



        if last_run == today_str:

            print("✅ 오늘 생일 축하 이미 완료됨")

            return



        sheet = get_sheet().spreadsheet.worksheet("Dictionary_Birth_SAVE")

        records = sheet.get_all_records()

        today_md = datetime.now(timezone("Asia/Seoul")).strftime("%m-%d")

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



            # ✅ 생일자 있을 때만 실행 기록

            set_last_birthday_run(today_str)

        else:

            print("ℹ️ 오늘 생일인 유저 없음. 실행 기록은 하지 않음.")



    except Exception as e:

        print(f"❗ 생일 축하 에러 발생: {e}")

        import traceback

        traceback.print_exc()

        

@tree.command(name="랭킹정산", description="이번 달 메시지 랭킹을 수동으로 정산합니다. (관리자용)")

async def 랭킹정산(interaction: discord.Interaction):

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

        import traceback

        traceback.print_exc()

        await interaction.followup.send("⚠️ 랭킹 정산 중 오류가 발생했습니다.")







# ✅ Render용 Flask 서버

keep_alive()



# ✅ 봇 실행

bot.run(TOKEN)
