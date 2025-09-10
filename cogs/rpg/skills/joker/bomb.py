import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random

from utils import get_sheet, safe_int


class Bomb(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ✅ Skill_Log 시트 가져오기
    def get_skill_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Skill_Log")
        except:
            return sheet.add_worksheet(title="Skill_Log", rows=1000, cols=5)

    # ✅ 마지막 사용 시간 가져오기
    def get_last_skill_time(self, user_id: str, skill_name: str):
        log_sheet = self.get_skill_log_sheet()
        records = log_sheet.get_all_records()
        for row in reversed(records):
            if str(row.get("유저 ID", "")) == user_id and row.get("스킬명") == skill_name:
                date_str = row.get("사용일시") or row.get("사용 일시")
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    except:
                        return None
        return None

    # ✅ 스킬 사용 로그 기록
    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    # ✅ 피해량 계산
    def get_bomb_damage(self, level: int):
        roll = random.uniform(0, 100)
        if roll <= 70:   # 70%
            return random.randint(15, 25) + level, "normal"
        elif roll <= 90: # 20%
            return random.randint(33, 47) + level, "medium"
        elif roll <= 99: # 9%
            sub_roll = random.uniform(0,100)
            if sub_roll <=1:
                return 300 + level, "LEGEND"
            else : 
                return random.randint(55, 90) + level, "critical"
        else:            # 1% 자폭
            return -40, "self"

    # ✅ 폭탄 스킬
    @app_commands.command(
        name="폭탄",
        description="특수 전용 스킬: 랜덤 유저에게 폭탄을 던집니다. (쿨타임 4시간)"
    )
    async def 폭탄(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ⚡ 먼저 응답 예약
        await interaction.response.defer(ephemeral=False)

        # 최근 사용 기록 확인 (쿨타임 4시간)
        last_used = self.get_last_skill_time(user_id, "폭탄")
        if last_used and datetime.now() < last_used + timedelta(hours=4):
            remain = (last_used + timedelta(hours=4)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(
                f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요."
            )
            return

        sheet = get_sheet()
        records = sheet.get_all_records()

        user_row = None
        candidates = []

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
            else:
                # 후보자 조건: 레벨 >= 2
                if safe_int(row.get("레벨", 1)) >= 2:
                    candidates.append((idx, row))

        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.")
            return
        if not candidates:
            await interaction.followup.send("⚠️ 폭탄을 맞을 대상(레벨 2 이상 유저)이 없습니다.")
            return

        user_idx, user_data = user_row

        # 직업 확인
        if user_data.get("직업") != "특수":
            await interaction.followup.send("❌ 특수 직업만 사용할 수 있는 스킬입니다!")
            return

        # 랜덤 대상 선정
        target_idx, target_data = random.choice(candidates)
        target_id = str(target_data.get("유저 ID"))
        target_name = target_data.get("닉네임", f"ID:{target_id}")

        # 피해량 계산
        level = safe_int(user_data.get("레벨",1))
        damage, dmg_type = self.get_bomb_damage(level)

        if dmg_type == "self":
            # 자폭
            new_user_exp = safe_int(user_data.get("현재레벨경험치", 0)) + damage  # damage는 -40
            sheet.update_cell(user_idx, 11, new_user_exp)

            self.log_skill_use(user_id, username, "폭탄", f"자폭 -40 exp")
            await interaction.followup.send(
                f"💣 {username} 님의 폭탄이 폭발해버렸다!\n☠️ 스스로 -40 exp (현재 경험치: {new_user_exp})"
            )
            return
        else:
            # 상대 피해
            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - damage
            sheet.update_cell(target_idx, 11, new_target_exp)

            self.log_skill_use(
                user_id,
                username,
                "폭탄",
                f"대상: {target_name}, -{damage} exp"
            )

            if dmg_type == "normal":
                effect = "🎯"
            elif dmg_type == "medium":
                effect = "💥"
            elif: dmg_type == "LEGEND":
                effect = "⚡레전드상황발생⚡"
            else:
                effect = "🔥 치명적!"

            await interaction.followup.send(
                f"💣 {username} 님이 폭탄을 던졌습니다!\n"
                f"{effect} 랜덤 타겟: <@{target_id}> → -{damage} exp (현재 경험치: {new_target_exp})"
            )


async def setup(bot):
    await bot.add_cog(Bomb(bot))
