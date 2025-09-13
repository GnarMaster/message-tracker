import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from utils import get_sheet, safe_int

class CoolTime(commands.Cog):
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

    @app_commands.command(name="쿨타임", description="내가 다음 스킬을 사용할 수 있을 때까지 남은 시간을 확인합니다.")
    async def 쿨타임(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Skill_Log에서 본인 직업 스킬만 확인
        log_sheet = self.get_skill_log_sheet()
        records = log_sheet.get_all_records()
        skills = ["삼연격", "체라", "더블샷", "스틸", "폭탄"]

        result = []
        for skill in skills:
            last_used = self.get_last_skill_time(user_id, skill)
            if last_used:
                next_available = last_used + timedelta(hours=4)
                if datetime.now() < next_available:
                    remain = next_available - datetime.now()
                    minutes = remain.seconds // 60
                    result.append(f"⏳ {skill}: {minutes}분 남음")
                else:
                    result.append(f"✅ {skill}: 사용 가능")
            else:
                result.append(f"✅ {skill}: 아직 사용한 적 없음")

        msg = "\n".join(result)
        await interaction.response.send_message(
            f"📊 **{interaction.user.name}** 님의 스킬 쿨타임 현황\n{msg}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(CoolTime(bot))
