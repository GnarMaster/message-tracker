import discord
from discord.ext import commands
from datetime import datetime, timedelta

class Duty(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.duty_cycle = ["주간", "야간", "비번", "휴무"]
        self.start_dates = {
            "임현수": datetime(2025, 4, 14)
        }

    @discord.app_commands.command(name="공익근무표", description="오늘의 공익 근무표를 확인합니다.")
    async def duty_chart(self, interaction: discord.Interaction):
        today = (datetime.utcnow() + timedelta(hours=9)).date()
        result = [f"[{today} 공익근무표]"]

        for name, start_date in self.start_dates.items():
            days_passed = (today - start_date.date()).days
            duty = self.duty_cycle[days_passed % len(self.duty_cycle)]
            result.append(f"{name} - {duty}")

        await interaction.response.send_message("\n".join(result))

async def setup(bot):
    await bot.add_cog(Duty(bot))
