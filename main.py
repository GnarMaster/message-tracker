from keep_alive import keep_alive
import re
import discord
import traceback
import random
from discord.ext import commands
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # import 구문 수정
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

from utils import get_sheet, safe_int, get_job_icon

LAST_RUN_FILE = "last_run.json"
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID"))
KST = timezone("Asia/Seoul")
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

# 생일축하했는지 확인하는 함수
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

SPECIAL_CHANNEL_ID = 1192514064035885118  # 릴스 채널 ID
channel_special_log = {}  # {userID-YYYY-M: count}


def safe_float(val):
    try:
        return float(str(val).strip())
    except:
        return 0.0


def format_exp(value: float) -> str:
    if value.is_integer():   # 값이 정수면
        return str(int(value))
    return f"{value:.1f}"    # 소숫점 1자리까지

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
user_levels = {}
# ✅ 서버 시작시

@bot.event
async def on_ready():
    bot.GENERAL_CHANNEL_ID= GENERAL_CHANNEL_ID
    global message_log
    message_log = load_data()
    print(f"✅ 봇 로그인 완료: {bot.user}") 
    # cogs/ 하위 모든 폴더까지 탐색
    for root, dirs, files in os.walk("./cogs"):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                rel_path = os.path.relpath(os.path.join(root, file), ".")
                module_name = rel_path.replace(os.sep, ".")[:-3]  # .py 제거
                try:
                    await bot.load_extension(module_name)
                    print(f"✅ Loaded extension: {module_name}")
                except Exception as e:
                    print(f"❗ Failed to load {module_name}: {e}")

    await tree.sync()

    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(send_birthday_congrats, 'cron', hour=0, minute=0)
    # ✅ 1분마다 실행되는 작업 등록

    @scheduler.scheduled_job('interval', minutes=1)
    async def periodic_sync():
        await sync_cache_to_sheet()

    scheduler.start()

    print("🕛 현재 시간 (KST):", datetime.now(KST))

    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d")
    last_run = get_last_run_date_from_sheet()


# ✅ 채팅 감지
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = datetime.now(KST)
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
    
# 요구 경험치
def exp_needed_for_next_level(level: int) -> int:

    if level < 5:
        return int(0.5 * (level ** 2) + level*11)
    elif level < 10:
        return int(0.7 * (level ** 2) + 70)
    elif level < 20:
        return int(1.2 * (level ** 2) + 150)
    elif level < 30:
        return int(1.5 * (level ** 2) + 200)
    elif level < 50:
        return int(1.2 * (level ** 2) + 500)
    else:
        # 50 이상 → 급격히 상승
        return int(5 * (level ** 2) + level * 20 + 1000)

# ✅ 캐시를 구글시트에 합산 저장
async def sync_cache_to_sheet():
    try:
        sheet = get_sheet()
        now = datetime.now(KST)
        year, month = now.year, now.month

        records = sheet.get_all_records()
        # {user_id (str): (row_num, current_total_messages, current_nickname, current_mentions, current_links, current_images, current_reels)}
        existing_data = {}

        # 기존 사용자 데이터 저장 및 유효성 검사 강화
        for idx, row in enumerate(records, start=2):  # 헤더가 1행이므로 실제 데이터는 2행부터 시작
            user_id_from_sheet = str(row.get("유저 ID", "")).strip()

            # 유저 ID가 순수 숫자인지 확인 (Discord ID는 항상 숫자)
            if not user_id_from_sheet.isdigit():
                print(
                    f"⚠️ Google 시트에서 유효하지 않은 유저 ID (비숫자) 발견: '{user_id_from_sheet}' (행: {idx})")
                continue  # 유효하지 않은 ID는 건너뛰기

            try:
                # 모든 통계 값을 안전하게 정수로 변환
                total_messages = safe_int(row.get("누적메시지수", 0))
                mentions = safe_int(row.get("멘션수", 0))
                links = safe_int(row.get("링크수", 0))
                images = safe_int(row.get("이미지수", 0))
                reels = safe_int(row.get("릴스", 0))
                current_nickname = str(row.get("닉네임", "")).strip()
                current_level = safe_int(row.get("레벨", 1))
                current_inlevel_exp = safe_float(row.get("현재레벨경험치", 0))
                current_gold = safe_int(row.get("골드",0))
                # 유효한 user_id_from_sheet 일 때만 저장
                if user_id_from_sheet:
                    existing_data[user_id_from_sheet] = (
                        idx, total_messages, current_nickname, mentions, links, images, reels, current_level, current_inlevel_exp, current_gold)
            except Exception as e:
                print(
                    f"❗ Google 시트 레코드 처리 중 오류 발생 (ID: {user_id_from_sheet}, 행: {idx}): {e}")
                traceback.print_exc()
                continue

        update_data = []  # 일괄 업데이트를 위한 리스트
        new_users_to_append = []  # 새로 추가할 유저 목록 (append_rows용)
        keys_to_delete_from_message_log = []  # 처리 완료 후 message_log에서 삭제할 키 목록

        for key, value in list(message_log.items()):
            user_id, y, m = key.split('-')

            # 현재 달이 아닌 데이터는 이 함수에서 처리하지 않음 (send_monthly_stats에서 처리됨)
            if int(y) != year or int(m) != month:
                continue

            total_messages_from_cache = value["total"]
            stats_from_detail_log = detail_log.get(
                key, {})  # detail_log에서 현재 캐시 통계 가져오기

            mention_from_cache = stats_from_detail_log.get("mention", 0)
            link_from_cache = stats_from_detail_log.get("link", 0)
            image_from_cache = stats_from_detail_log.get("image", 0)

            # 릴스 채널 캐시 가져오기
            special_key = f"{user_id}-{year}-{month}"
            reels_from_cache = channel_special_log.get(special_key, 0)

            # 사용자 객체를 미리 가져와 닉네임과 실제 ID를 확인
            user_obj = None
            try:
                user_obj = await bot.fetch_user(int(user_id))
            except discord.NotFound:
                print(
                    f"⚠️ Discord에서 유저 ID '{user_id}'를 찾을 수 없음. 데이터 처리를 건너뜁니다.")
                # 해당 유저의 캐시 데이터는 일단 유지하여 나중에 다시 시도하거나 수동 확인
                continue
            except Exception as e:
                print(f"❗ Discord 유저 객체 가져오기 오류 (ID: {user_id}): {e}")
                traceback.print_exc()
                continue

            if user_id in existing_data:
                # 기존 사용자 데이터 업데이트
                row_num, current_total_messages, current_nickname_from_sheet, current_mentions, current_links, current_images, current_reels, current_level, current_inlevel_exp, current_gold = existing_data[
                    user_id]

                # 닉네임 변경 시 업데이트 목록에 추가
                if current_nickname_from_sheet != user_obj.name:
                    update_data.append(
                        {"range": f"B{row_num}", "values": [[user_obj.name]]})

                # 누적 메시지 수 및 상세 통계 업데이트 (현재 시트 값 + 캐시 값)
                new_total_messages = current_total_messages + total_messages_from_cache
                new_mentions = current_mentions + mention_from_cache
                new_links = current_links + link_from_cache
                new_images = current_images + image_from_cache
                new_reels = current_reels + reels_from_cache  # 릴스도 합산

                new_level = current_level
                general_channel = bot.get_channel(GENERAL_CHANNEL_ID)
                
                # if total_messages_from_cache >= 50:
                #     penalty = total_messages_from_cache
                #     new_inlevel_exp = max(0, current_inlevel_exp - penalty)
                #     log_msg = f"🚨 도배 감지!  {current_nickname_from_sheet} 경험치 {penalty} 차감"
                #     print(log_msg)
                #     if general_channel:
                #         await general_channel.send(log_msg)
                # elif total_messages_from_cache >= 40:
                #     new_inlevel_exp = current_inlevel_exp
                #     log_msg = f"⚠️ 도배 의심!  {current_nickname_from_sheet} 경험치 미지급"
                #     print(log_msg)
                #     if general_channel:
                #         await general_channel.send(log_msg)
                # else:
                new_inlevel_exp = current_inlevel_exp + total_messages_from_cache

                # ✅ 레벨업 체크
                while new_level < 100 and new_inlevel_exp >= exp_needed_for_next_level(new_level):
                    need = exp_needed_for_next_level(new_level)
                    new_inlevel_exp -= need
                    new_level += 1
                    await bot.get_channel(CHANNEL_ID).send(
                        f"🎉 {user_obj.name} 님이 **레벨 {new_level}** 달성!"
                    )

                    if new_level == 5:
                        await bot.get_channel(CHANNEL_ID).send(
                            f"⚔️이제 `/전직` 명령어를 이용해 전직할 수 있어요!"
                        )

                update_data.extend([
                    {"range": f"C{row_num}", "values": [[new_total_messages]]},
                    {"range": f"D{row_num}", "values": [[new_mentions]]},
                    {"range": f"E{row_num}", "values": [[new_links]]},
                    {"range": f"F{row_num}", "values": [[new_images]]},
                    {"range": f"I{row_num}", "values": [
                        [new_reels]]},  # 릴스 업데이트
                    {"range": f"J{row_num}", "values": [[new_level]]},
                    {"range": f"K{row_num}", "values": [[new_inlevel_exp]]}
                ])
                # 업데이트된 데이터는 existing_data에 반영하여 다음 루프에서 사용 가능하게 할 수도 있지만,
                # 1분마다 캐시를 비우므로 큰 문제는 아님.

                user_levels[user_id] = new_level
            else:
                # 신규 유저 처리 - append_rows를 위해 리스트에 추가
                exp = total_messages_from_cache
                level = 1
                inlevel_exp = exp

                new_users_to_append.append([
                    user_id,
                    user_obj.name,
                    exp,  # 신규 유저는 현재 캐시 값 그대로
                    mention_from_cache,
                    link_from_cache,
                    image_from_cache,
                    0,  # G열 (비워둠)
                    0,  # H열 (비워둠)
                    reels_from_cache,  # 릴스 데이터
                    level,
                    inlevel_exp,
                    "백수",
                    100
                ])

            # 처리된 캐시 키를 삭제 목록에 추가
            keys_to_delete_from_message_log.append(key)

            # detail_log와 channel_special_log는 message_log와 같은 키로 관리되므로 함께 삭제
            if key in detail_log:
                del detail_log[key]
            if special_key in channel_special_log:
                del channel_special_log[special_key]

        # --- 위에서 처리된 message_log 키 삭제 ---
        for key_to_del in keys_to_delete_from_message_log:
            if key_to_del in message_log:
                del message_log[key_to_del]
        save_data(message_log)  # message_log 변경사항 로컬 파일에 저장

        # --- 일괄 Google Sheet 업데이트 및 추가 ---

        # 일괄 신규 유저 추가
        if new_users_to_append:
            # append_rows는 가장 마지막 행에 추가되므로, 헤더가 아닌 데이터 시작 행을 고려할 필요 없음
            sheet.append_rows(new_users_to_append,
                              value_input_option="USER_ENTERED")
            print(
                f"✅ Google 시트에 {len(new_users_to_append)}명의 새로운 유저 데이터가 추가됨.")

        # 일괄 업데이트 실행
        if update_data:
            sheet.batch_update(update_data, value_input_option="USER_ENTERED")
            print(f"✅ Google 시트에 {len(update_data)}건의 데이터가 일괄 업데이트됨.")

        # 모든 캐시가 처리된 후 안전하게 저장
        # detail_log, channel_special_log는 파일로 저장되지 않으므로 따로 save_data 호출할 필요 없음

    except Exception as e:
        print(f"❗ sync_cache_to_sheet 에러: {e}")
        traceback.print_exc()

# ✅ 이번달메시지 명령어
@tree.command(name="이번달메시지", description="이번 달 메시지 랭킹을 확인합니다.")
async def 이번달메시지(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        await sync_cache_to_sheet()

        sheet = get_sheet()
        records = sheet.get_all_records()

        now = datetime.now(KST)
        year, month = now.year, now.month
        results = []

        for row in records:
            uid_raw = str(row.get("유저 ID", "0")).strip()
            uid = int(uid_raw) if uid_raw.isdigit() else 0
            count = safe_int(row.get("누적메시지수", 0))
            username = row.get("닉네임", f"(ID:{uid})")

            # ✅ 메시지 수 0인 경우 제외
            if count > 0:
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
        print("❗ /이번달메시지 에러:", e)
        traceback.print_exc()
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")
        except:
            pass

# ✅ 내레벨 명령어
@tree.command(name="내레벨", description="현재 나의 레벨과 경험치를 확인합니다.")
async def 내레벨(interaction: discord.Interaction):
    try:
        await interaction.response.defer()  # 공개 출력 (ephemeral 제거)
        await sync_cache_to_sheet()

        sheet = get_sheet()
        records = sheet.get_all_records()

        user_id = str(interaction.user.id)
        username = interaction.user.name

        # 유저 찾기
        for row in records:
            if str(row.get("유저 ID", "")).strip() == user_id:
                level = safe_int(row.get("레벨", 1))
                exp = safe_float(row.get("현재레벨경험치", 0))
                need = exp_needed_for_next_level(level)
                job = row.get("직업", "백수")
                icon = get_job_icon(job)
                exp_str = format_exp(exp)

                msg = (f"👤 **{username}** 님의 현재 상태\n"
                       f"📊 레벨: **{level}**\n"
                       f"⭐ 경험치: {exp_str} / {need}\n"
                       f"{icon} 직업: {job}")
                await interaction.followup.send(msg)
                return

        # 만약 데이터가 없을 때
        await interaction.followup.send("⚠️ 아직 기록된 데이터가 없어요.")

    except Exception as e:
        print(f"❗ /내레벨 에러: {e}")
        await interaction.followup.send("⚠️ 정보를 불러오는 데 실패했습니다.")
 
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
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        last_run = get_last_birthday_run()

        if last_run == today_str:
            print("✅ 오늘 생일 축하 이미 완료됨")
            return

        sheet = get_sheet().spreadsheet.worksheet("Dictionary_Birth_SAVE")
        records = sheet.get_all_records()
        today_md = datetime.now(KST).strftime("%m-%d")
        birthday_users = []

        for row in records:
            if row.get("생일", "").strip() == today_md:
                uid = str(row.get("유저 ID", "")).strip()
                birthday_users.append(uid)

        if birthday_users:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                mentions = "\n".join(
                    [f"🎂 <@{uid}> 님" for uid in birthday_users])
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
  
# ✅ Render용 Flask 서버
keep_alive()

# ✅ 봇 실행
bot.run(TOKEN)
