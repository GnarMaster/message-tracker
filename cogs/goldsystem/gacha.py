import discord
from discord.ext import commands
import random
from discord import app_commands
from utils import get_sheet, safe_int

# 👉 뽑기 채널 ID (이 채널에서만 /뽑기기계 실행 가능)
GACHA_CHANNEL_ID = 1419961802938384435  # 실제 가차 채널 ID로 교체하세요


class GachaButtonView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="뽑기 돌리기 🎰", style=discord.ButtonStyle.green, custom_id="gacha_button")
    async def gacha_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        try:
            # 🔹 즉시 defer 해서 interaction 타임아웃 방지
            await interaction.response.defer(thinking=True, ephemeral=False)

            # 🔹 "뽑는 중..." 안내 메시지 전송 (followup)
            msg = await interaction.followup.send("🎰 뽑는 중...", wait=True)

            # === 실제 로직 ===
            sheet = get_sheet()
            records = sheet.get_all_records()

            user_row = None
            for idx, row in enumerate(records, start=2):
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = (idx, row)
                    break

            if not user_row:
                await msg.edit(content="⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.", embed=None, view=None)
                return

            row_idx, user_data = user_row
            current_gold = safe_int(user_data.get("골드", 0))

            if current_gold < 10:
                await msg.edit(content="💰 골드가 부족합니다! (최소 10 필요)", embed=None, view=None)
                return

            new_gold = current_gold - 10

            # 🔹 보상 및 확률
            rewards = [1, 5, 10, 20, 50, 100]
            weights = [30, 30, 20, 15, 4, 1]  # 총합 100
            reward = random.choices(rewards, weights=weights, k=1)[0]

            new_gold += reward
            sheet.update_cell(row_idx, 13, new_gold)  # M열 = 골드

            embed = discord.Embed(
                title="🎰 뽑기 결과!",
                description=f"{username} 님이 뽑기를 돌렸습니다!",
                color=discord.Color.gold()
            )
            embed.add_field(name="차감", value="-10 골드", inline=True)
            embed.add_field(name="보상", value=f"+{reward} 골드", inline=True)
            embed.add_field(name="보유 골드", value=f"{new_gold} 골드", inline=False)
            embed.set_footer(text="⏳ 이 메시지는 5분 뒤 자동 삭제됩니다.")

            # 🔹 결과 메시지로 교체
            await msg.edit(content=None, embed=embed, view=None, delete_after=300)

        except Exception as e:
            print(f"❗ 뽑기 버튼 에러: {e}")
            try:
                await interaction.followup.send("⚠️ 오류가 발생했습니다.", ephemeral=True)
            except:
                pass


class GachaButtonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(GachaButtonView(self.bot))  # 봇 재시작 후에도 버튼 유지

    @app_commands.command(name="뽑기기계", description="현재 채널에 뽑기 머신을 설치합니다. (가차채널 전용)")
    async def 뽑기기계(self, interaction: discord.Interaction):
        # ✅ 채널 제한
        if interaction.channel.id != GACHA_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 이 명령어는 지정된 뽑기방에서만 사용할 수 있어요!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎰 뽑기 머신",
            description="버튼을 눌러 뽑기를 돌려보세요! (10골드 필요)",
            color=discord.Color.green()
        )

        # 🔹 확률표 추가
        prob_text = (
            "1골드 → 30%\n"
            "5골드 → 30%\n"
            "10골드 → 20%\n"
            "20골드 → 15%\n"
            "50골드 → 4%\n"
            "100골드 → 1%"
        )
        embed.add_field(name="📊 확률표", value=prob_text, inline=False)

        view = GachaButtonView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        print(f"✅ 뽑기 머신이 채널 {interaction.channel.id} 에 설치됨")


async def setup(bot: commands.Bot):
    await bot.add_cog(GachaButtonCog(bot))
