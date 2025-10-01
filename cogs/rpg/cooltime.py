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

    @app_commands.command(name="쿨타임", description="내 직업 스킬의 쿨타임을 확인합니다.")
    async def 쿨타임(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # ✅ 응답 예약
        await interaction.response.defer(ephemeral=True)

        # 내 직업 확인
        sheet = get_sheet()
        records = sheet.get_all_records()
        my_job = None
        for row in records:
            if str(row.get("유저 ID", "")) == user_id:
                my_job = row.get("직업", "백수")
                break

        # ✅ 직업별 스킬 매핑 (1차 + 2차 포함)
        job_skills = {
            # 전사 계열
            "전사": "삼연격", "검성": "삼연격", "검투사": "삼연격", "투신": "삼연격",
            # 마법사 계열
            "마법사": "체라", "폭뢰술사": "체라", "연격마도사": "체라",
            # 궁수 계열
            "궁수": "더블샷", "저격수": "더블샷", "연사수": "더블샷",
            # 도적 계열
            "도적": "스틸", "암살자": "스틸", "의적": "스틸", "카피닌자": "스틸",
            # 특수 계열
            "특수": "붐", "파괴광": "붐", "축제광": "붐",
        }

        if my_job not in job_skills:
            await interaction.followup.send("⚠️ 넌 백수다!")
            return

        skill = job_skills[my_job]

        # 마지막 사용 시간 확인
        last_used = self.get_last_skill_time(user_id, skill)
        if last_used:
            next_available = last_used + timedelta(hours=4)
            if datetime.now() < next_available:
                remain = next_available - datetime.now()
                minutes = remain.seconds // 60
                msg = f"⏳ {skill}: {minutes}분 남음"
            else:
                msg = f"✅ {skill}: 사용 가능"
        else:
            msg = f"✅ {skill}: 아직 사용한 적 없음"

        await interaction.followup.send(
            f"📊 **{interaction.user.name}** 님 ({my_job}) 의 스킬 쿨타임 현황\n{msg}"
        )

async def setup(bot):
    await bot.add_cog(CoolTime(bot))
