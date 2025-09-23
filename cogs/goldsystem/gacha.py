import discord
from discord.ext import commands
import random
from utils import get_sheet, safe_int

# 👉 뽑기방 채널 ID를 여기에 넣으세요
GACHA_CHANNEL_ID = 123456789012345678  # 실제 채널 ID로 교체


class GachaButtonView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)  # timeout=None → 봇 켜져 있는 한 버튼 살아있음
        self.bot = bot

    @discord.ui.button(label="뽑기 돌리기 🎰", style=discord.ButtonStyle.green, custom_id="gacha_button")
    async def gacha_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 먼저 응답 예약 (404 방지)
        await interaction.response.defer(ephemeral=False)

        try:
            sheet = get_sheet()
            records = sheet.get_all_records()

            # 유저 찾기
            user_row = None
            for idx, row in enumerate(records, start=2):  # 2행부터 데이터 시작
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = (idx, row)
                    break

            if not user_row:
                await interaction.followup.send("⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.", ephemeral=True)
                return

            row_idx, user_data = user_row
            current_gold = safe_int(user_data.get("골드", 0))

            if current_gold < 10:
                await interaction.followup.send("💰 골드가 부족합니다! (최소 10 필요)", ephemeral=True)
                return

            # 참가비 차감
            new_gold = current_gold - 10

            # 🎲 랜덤 보상 (기댓값 10골드)
            rewards = [1, 5, 10, 20, 50, 100]
            weights = [35, 25, 20, 15, 4, 1]  # 총합 100
            reward = random.choices(rewards, weights=weights, k=1)[0]

            new_gold += reward
            sheet.update_cell(row_idx, 13, new_gold)  # ✅ 골드 = M열 (13번째 열)

            # 결과 임베드
            embed = discord.Embed(
                title="🎰 뽑기 결과!",
                description=f"{username} 님이 뽑기를 돌렸습니다!",
                color=discord.Color.gold()
            )
            embed.add_field(name="차감", value="-10 골드", inline=True)
            embed.add_field(name="보상", value=f"+{reward} 골드", inline=True)
            embed.add_field(name="보유 골드", value=f"{new_gold} 골드", inline=False)
            embed.set_footer(text="⏳ 이 메시지는 5분 뒤 자동 삭제됩니다.")

            # ✅ 결과 출력 (5분 뒤 자동 삭제)
            await interaction.followup.send(embed=embed, delete_after=300)

        except Exception as e:
            print(f"❗ /뽑기 버튼 에러: {e}")
            try:
                await interaction.followup.send("⚠️ 오류가 발생했습니다.", ephemeral=True)
            except:
                pass


class GachaButtonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(GACHA_CHANNEL_ID)
        if not channel:
            return

        # ✅ 최근 20개 메시지 확인해서 "뽑기 머신"이 이미 있으면 새로 안 띄움
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and msg.embeds:
                embed = msg.embeds[0]
                if embed.title == "🎰 뽑기 머신":
                    print(f"⚠️ 이미 뽑기 머신이 채널 {GACHA_CHANNEL_ID} 에 존재함 → 새로 생성하지 않음")
                    self.bot.add_view(GachaButtonView(self.bot))  # 버튼은 다시 등록해줘야 함
                    return

        # 없으면 새로 생성
        embed = discord.Embed(
            title="🎰 뽑기 머신",
            description="버튼을 눌러 뽑기를 돌려보세요! (10골드 필요)",
            color=discord.Color.green()
        )
        view = GachaButtonView(self.bot)
        await channel.send(embed=embed, view=view)
        print(f"✅ 뽑기 머신이 채널 {GACHA_CHANNEL_ID} 에 새로 생성됨")

        # 봇 재시작 후에도 버튼이 동작하도록 view 등록
        self.bot.add_view(GachaButtonView(self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(GachaButtonCog(bot))
