import discord
from discord import app_commands
from discord.ext import commands
from utils import get_job_icon

class JobInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="직업소개", description="모든 직업과 스킬을 소개합니다.")
    async def 직업소개(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ 직업 소개",
            description="각 직업의 고유 스킬을 확인하세요!",
            color=discord.Color.blue()
        )

        jobs = {
            "전사": "삼연격: 점점 낮아지는 확률로 3연속 공격 (쿨타임 4시간)",
            "마법사": "체인라이트닝: 지정 1명 + 랜덤 1명 동시 공격 (쿨타임 4시간)",
            "궁수": "더블샷: 두 번 연속 사격 (쿨타임 4시간)",
            "도적": "스틸: 다른 유저의 경험치를 훔침 (쿨타임 4시간)",
            "특수": "폭탄: 랜덤 대상에게 폭탄 던지기 (쿨타임 6시간)"
        }

        for job, desc in jobs.items():
            embed.add_field(
                name=f"{get_job_icon(job)} {job}",
                value=desc,
                inline=False
            )

      # 🔒 본인에게만 보이도록
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(JobInfo(bot))
