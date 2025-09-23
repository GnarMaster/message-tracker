import discord
from discord.ext import commands
from discord import app_commands
from utils import get_sheet, safe_int

class MyGold(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="내골드", description="현재 보유 골드를 확인합니다.")
    async def 내골드(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 첫 응답은 비공개 defer (404 방지)
        await interaction.response.defer(ephemeral=True)

        try:
            sheet = get_sheet()
            records = sheet.get_all_records()

            user_row = None
            for row in records:
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = row
                    break

            if not user_row:
                await interaction.edit_original_response(
                    content="⚠️ 아직 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요."
                )
                return

            current_gold = safe_int(user_row.get("골드", 0))

            embed = discord.Embed(
                title="💰 내 골드 확인",
                description=f"**{username}** 님의 현재 보유 골드",
                color=discord.Color.gold()
            )
            embed.add_field(name="보유 골드", value=f"{current_gold} 골드", inline=False)

            # ✅ 성공 → defer 응답 수정
            await interaction.edit_original_response(embed=embed)

        except Exception as e:
            # ✅ 예외 발생 시도 → 안전하게 메시지 수정
            try:
                await interaction.edit_original_response(content=f"⚠️ 오류 발생: {e}")
            except:
                await interaction.followup.send(f"⚠️ 오류 발생: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MyGold(bot))
