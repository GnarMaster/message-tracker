import discord
from discord.ext import commands
from discord import app_commands
from utils import safe_int, get_sheet
from inventory_utils import get_inventory  # ✅ 인벤토리 유틸 사용

class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    
    @app_commands.command(name="인벤토리", description="내 인벤토리를 확인합니다")
    async def 인벤토리(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # 🔒 본인만 보이게

        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 메인 시트에서 현재 골드 가져오기
        sheet = get_sheet()
        records = sheet.get_all_records()
        gold = 0
        for row in records:
            if str(row.get("유저 ID", "")) == user_id:
                gold = safe_int(row.get("골드", 0))
                break

        # ✅ 인벤토리 가져오기
        items = get_inventory(user_id)

        embed = discord.Embed(
            title=f"🎒 {username} 님의 인벤토리",
            description="보유 중인 아이템과 골드를 확인하세요.",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 보유 골드", value=f"{gold} 골드", inline=False)

        if not items:
            embed.add_field(
                name="📦 보유 아이템",
                value="❌ 현재 보유한 아이템이 없습니다.",
                inline=False
            )
        else:
            item_text = "\n".join([f"• **{name}** x{cnt}" for name, cnt in items])
            embed.add_field(
                name="📦 보유 아이템",
                value=item_text,
                inline=False
            )

        embed.set_footer(text="아이템은 상점에서 구매하거나 이벤트로 획득할 수 있습니다.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
