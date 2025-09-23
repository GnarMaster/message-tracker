import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
from utils import get_sheet, safe_int, get_copied_skill, clear_copied_skill, check_counter

class Archer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_skill_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Skill_Log")
        except:
            return sheet.add_worksheet(title="Skill_Log", rows=1000, cols=5)

    def get_last_skill_time(self, user_id: str, skill_name: str):
        log_sheet = self.get_skill_log_sheet()
        records = log_sheet.get_all_records()
        for row in reversed(records):
            if str(row.get("유저 ID", "")) == user_id and row.get("스킬명") == skill_name:
                date_str = row.get("사용일시")
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    return None
        return None

    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    @app_commands.command(
        name="더블샷",
        description="궁수 전용 스킬: 지정 2명에게 연속 사격 (쿨타임 4시간)"
    )
    async def 더블샷(self, interaction: discord.Interaction, target1: discord.Member, target2: discord.Member):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 첫 응답은 비공개로 defer
        await interaction.response.defer(ephemeral=True)

        try:
            # 쿨타임 확인
            last_used = self.get_last_skill_time(user_id, "더블샷")
            if last_used and datetime.now() < last_used + timedelta(hours=4):
                remain = (last_used + timedelta(hours=4)) - datetime.now()
                minutes = remain.seconds // 60
                await interaction.edit_original_response(
                    content=f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요."
                )
                return

            sheet = get_sheet()
            records = sheet.get_all_records()

            user_row, target1_row, target2_row = None, None, None
            candidates = []
            for idx, row in enumerate(records, start=2):
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = (idx, row)
                elif str(row.get("유저 ID", "")) == str(target1.id):
                    target1_row = (idx, row)
                elif str(row.get("유저 ID", "")) == str(target2.id):
                    target2_row = (idx, row)
                else:
                    if safe_int(row.get("레벨", 1)) >= 5:
                        candidates.append((idx, row))

            if not user_row or not target1_row:
                await interaction.edit_original_response(content="⚠️ 데이터가 없습니다.")
                return

            job = user_row[1].get("직업", "백수")
            level = safe_int(user_row[1].get("레벨", 1))

            if job not in ["궁수", "저격수", "연사수", "카피닌자"]:
                await interaction.edit_original_response(content="❌ 궁수 계열만 사용할 수 있는 스킬입니다!")
                return

            # ✅ 여기까지 오면 성공 → 비공개 응답 삭제
            await interaction.delete_original_response()

            # ✅ 공격 함수
            def shoot_arrow(target_idx, target_data, target_obj, is_first: bool, is_sniper: bool = False):
                base = 10 + level
                crit_chance = 20
                if is_sniper:
                    base = 12 + level
                roll = random.randint(1, 100)
                if roll <= crit_chance:
                    dmg = base * 2
                    msg = f"🔥 치명타! ({dmg})"
                elif roll <= 90:
                    dmg = base
                    msg = f"✅ 명중! ({dmg})"
                else:
                    dmg = 0
                    msg = "❌ 빗나감!"

                if dmg > 0:
                    new_exp = safe_int(target_data.get("현재레벨경험치", 0)) - dmg
                    sheet.update_cell(target_idx, 11, new_exp)

                nickname = target_data.get("닉네임", target_obj.name)
                display_name = target_obj.mention if is_first else nickname
                return f"{display_name} → {msg}", dmg

            damage_logs, counter_msgs = [], []

            # =====================
            # 🔹 직업 분기
            # =====================
            if job == "저격수":
                result_msg = f"🏹 저격수 {username}님의 더블샷 발동!\n"
                for i in range(2):
                    msg, dmg = shoot_arrow(target1_row[0], target1_row[1], target1, is_first=(i == 0), is_sniper=True)
                    damage_logs.append(f"🎯 저격 {i+1}타: {msg}")
                    cm = check_counter(user_id, username, str(target1.id), target1.mention, dmg)
                    if cm: counter_msgs.append(cm)

            elif job == "연사수":
                result_msg = f"🏹 연사수 {username}님의 더블샷 발동!\n"
                msg, dmg = shoot_arrow(target1_row[0], target1_row[1], target1, is_first=True)
                damage_logs.append(f"🏹 1타: {msg}")
                cm = check_counter(user_id, username, str(target1.id), target1.mention, dmg)
                if cm: counter_msgs.append(cm)

                if target2_row:
                    msg, dmg = shoot_arrow(target2_row[0], target2_row[1], target2, is_first=True)
                    damage_logs.append(f"🏹 2타: {msg}")
                    cm = check_counter(user_id, username, str(target2.id), target2.mention, dmg)
                    if cm: counter_msgs.append(cm)

                if candidates:
                    rand_idx, rand_data = random.choice(candidates)
                    rand_id = str(rand_data.get("유저 ID"))
                    rand_obj = discord.Object(id=int(rand_id))
                    msg, dmg = shoot_arrow(rand_idx, rand_data, rand_obj, is_first=False)
                    damage_logs.append(f"⚡ 추가 연사: {msg}")
                    cm = check_counter(user_id, username, rand_id, f"<@{rand_id}>", dmg)
                    if cm: counter_msgs.append(cm)

            else:  # 기본 궁수
                result_msg = f"🏹 궁수 {username}님의 더블샷 발동!\n"
                msg, dmg = shoot_arrow(target1_row[0], target1_row[1], target1, is_first=True)
                damage_logs.append(f"🏹 1타: {msg}")
                cm = check_counter(user_id, username, str(target1.id), target1.mention, dmg)
                if cm: counter_msgs.append(cm)

                if target2_row:
                    msg, dmg = shoot_arrow(target2_row[0], target2_row[1], target2, is_first=True)
                    damage_logs.append(f"🏹 2타: {msg}")
                    cm = check_counter(user_id, username, str(target2.id), target2.mention, dmg)
                    if cm: counter_msgs.append(cm)

            # 로그 기록
            self.log_skill_use(user_id, username, "더블샷", "; ".join(damage_logs))

            result_msg += "\n".join(damage_logs)
            if counter_msgs:
                result_msg += "\n" + "\n".join(counter_msgs)

            # ✅ 성공 시 공개 메시지
            await interaction.followup.send(result_msg)

        except Exception as e:
            # 예외 처리: 비공개로 출력
            await interaction.edit_original_response(content=f"❌ 오류 발생: {e}")

async def setup(bot):
    await bot.add_cog(Archer(bot))
