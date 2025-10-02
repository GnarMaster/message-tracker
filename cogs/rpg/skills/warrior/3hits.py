import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
import os
from utils import get_sheet, safe_int, get_copied_skill, clear_copied_skill, check_counter, add_counter_buff
from cogs.rpg.skills.SkillLogic import plus_damage

# PVP 채널 ID 불러오기
PVP_CHANNEL_ID = int(os.getenv("PVP_CHANNEL_ID", 0))

class ThreeHits(commands.Cog):
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
        name="삼연격",
        description="전사 전용 스킬: 점점 낮아지는 확률로 3연속 공격을 시도합니다. (쿨타임 4시간)"
    )
    async def 삼연격(self, interaction: discord.Interaction, target: discord.Member):
        # ✅ PVP 채널 제한
        if interaction.channel.id != PVP_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ 이 명령어는 PVP 채널에서만 사용할 수 있습니다.",
                ephemeral=True
            )
            return
        user_id = str(interaction.user.id)
        username = interaction.user.name
        target_id = str(target.id)

        # ✅ 첫 응답은 비공개로 defer
        await interaction.response.defer(ephemeral=True)

        try:
            # 쿨타임 체크
            last_used = self.get_last_skill_time(user_id, "삼연격")
            if last_used and datetime.now() < last_used + timedelta(hours=4):
                remain = (last_used + timedelta(hours=4)) - datetime.now()
                minutes = remain.seconds // 60
                await interaction.edit_original_response(
                    content=f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요."
                )
                return

            sheet = get_sheet()
            records = sheet.get_all_records()

            user_row, target_row = None, None
            for idx, row in enumerate(records, start=2):
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = (idx, row)
                if str(row.get("유저 ID", "")) == target_id:
                    target_row = (idx, row)

            if not user_row:
                await interaction.edit_original_response(content="⚠️ 당신의 데이터가 없습니다.")
                return
            if not target_row:
                await interaction.edit_original_response(content="⚠️ 대상 유저의 데이터가 없습니다.")
                return

            # 직업 확인
            job = user_row[1].get("직업", "백수")
            if job == "카피닌자":
                copied_skill = get_copied_skill(user_id)
                if copied_skill != "삼연격":
                    await interaction.edit_original_response(content="❌ 현재 복사한 스킬이 삼연격이 아닙니다.")
                    return
                clear_copied_skill(user_id)
                prefix_msg = f"💀 카피닌자 {interaction.user.name}님이 복사한 스킬 **삼연격**을 발동!\n"
            elif job not in ["전사", "검성", "투신", "검투사"]:
                await interaction.edit_original_response(content="❌ 전사 계열만 사용할 수 있는 스킬입니다!")
                return
            else:
                if job == "검성":
                    prefix_msg = f"🗡️ 검성 {interaction.user.name} 님이 {target.mention} 님에게 **사연격**을 시전했다!\n"
                elif job == "투신":
                    prefix_msg = f"🪓 투신 {interaction.user.name} 님이 {target.mention} 님에게 **삼연격**을 시전했다!\n"
                elif job == "검투사":
                    prefix_msg = f"🛡️ 검투사 {interaction.user.name} 님이 {target.mention} 님에게 **삼연격**을 시전했다!\n"
                else:
                    prefix_msg = f"⚔️ {interaction.user.name} 님이 {target.mention} 님에게 **삼연격**을 시전했다!\n"


            #데미지 계산 구간
            BASE = 7 #전사 기본데미지
            def calc_base_damage():
                crit_roll = random.randint(1, 100)
                if crit_roll <= 10:  # 10% 치명타
                    return BASE + plus_damage(user_id), "🔥 치명타!"
                else:
                    return BASE + plus_damage(user_id), "✅ 명중!"

            if job == "검성":
                chances = [90, 60, 30, 15]
            else:
                chances = [90, 45, 15]

            logs = []
            total_damage = 0

            for i, chance in enumerate(chances, start=1):
                roll = random.randint(1, 100)
                if roll <= chance:
                    base, msg = calc_base_damage()
                    if i == 2:
                        dmg = int(base * 1.2)
                    elif i == 3:
                        dmg = int(base * 1.3)
                    elif i == 4:
                        dmg = int(base * 1.5)
                    else:
                        dmg = base
                    logs.append(f"{i}타: {msg} ({dmg})")
                    total_damage += dmg
                else:
                    logs.append(f"{i}타: ❌ 실패...")

            # 메인 타겟 exp 차감
            target_idx, target_data = target_row
            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - total_damage
            sheet.update_cell(target_idx, 11, new_target_exp)

            # 검투사 전용: 25% 확률로 반격 버프 부여
            if job == "검투사":
                if random.random() <= 0.25:
                    add_counter_buff(user_id, username)

            # 결과 메시지 생성
            result_msg = "\n".join(logs)
            result_msg += f"\n👉 총합: {target.mention} 님에게 {total_damage} 피해!"

            # ✅ 메인 타겟 반격 체크
            counter_msg_main = check_counter(user_id, username, target_id, target.mention, total_damage)
            if counter_msg_main:
                result_msg += f"\n{counter_msg_main}"

            # 투신 전용 추가 일격
            if job == "투신":
                candidates = [
                    (idx, row) for idx, row in enumerate(records, start=2)
                    if str(row.get("유저 ID", "")) not in (user_id, target_id)
                    and safe_int(row.get("레벨", 1)) >= 5
                ]
                if candidates:
                    rand_idx, rand_data = random.choice(candidates)
                    rand_base, rand_msg = calc_base_damage()
                    bonus_dmg = int(rand_base * 1.2)

                    # 경험치 차감
                    rand_new_exp = safe_int(rand_data.get("현재레벨경험치", 0)) - bonus_dmg
                    sheet.update_cell(rand_idx, 11, rand_new_exp)

                    nickname = rand_data.get("닉네임", "???")
                    result_msg += f"\n⚡ 투신의 추가 일격! {nickname} → {rand_msg} ({bonus_dmg})"

                    # ✅ 추가 일격 반격 체크
                    counter_msg_bonus = check_counter(user_id, username, str(rand_data.get("유저 ID")), nickname, bonus_dmg)
                    if counter_msg_bonus:
                        result_msg += f"\n{counter_msg_bonus}"

            # 로그 기록
            self.log_skill_use(user_id, username, "삼연격", f"대상: {target.name}, 총 {total_damage} 피해")

            # ✅ 성공 시: 비공개 응답 삭제 후 공개 메시지
            await interaction.delete_original_response()
            await interaction.followup.send(prefix_msg + result_msg)

        except Exception as e:
            # 예외 처리: 비공개 메시지로 출력
            await interaction.edit_original_response(content=f"❌ 오류 발생: {e}")

async def setup(bot):
    await bot.add_cog(ThreeHits(bot))
