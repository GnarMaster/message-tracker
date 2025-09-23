import discord
from discord import app_commands
from discord.ext import commands
import random
from utils import get_sheet, safe_int


class Gacha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="뽑기", description="10골드를 소모해 랜덤 보상을 뽑습니다!")
    async def 뽑기(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 무조건 첫 응답 예약 (에러 방지)
        await interaction.response.defer(ephemeral=False)

        try:
            sheet = get_sheet()
            records = sheet.get_all_records()

            # 유저 찾기
            user_row = None
            for idx, row in enumerate(records, start=2):
                if str(row.get("유저 ID", "")) == user_id:
                    user_row = (idx, row)
                    break

            if not user_row:
                await interaction.followup.send("⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.")
                return

            row_idx, user_data = user_row
            current_gold = safe_int(user_data.get("골드", 0))

            if current_gold < 10:
                await interaction.followup.send("💰 골드가 부족합니다! (최소 10 필요)")
                return

            # 참가비 차감
            new_gold = current_gold - 10

            # 확률 분포 기반 보상
            rewards = [1, 5, 10, 20, 50, 100]
            weights = [35, 25, 20, 15, 4, 1]  # 합계 = 100
            reward = random.choices(rewards, weights=weights, k=1)[0]

            new_gold += reward

            # 시트 업데이트 (골드 = L열, 보통 12번째 열 → 위치 확인 필요!)
            sheet.update_cell(row_idx, 12, new_gold)

            # 결과 메시지 전송 (5분 뒤 자동 삭제)
            await interaction.followup.send(
                f"🎰 {username} 님의 뽑기 결과!\n"
                f"차감: -10골드\n"
                f"보상: +{reward}골드\n"
                f"💰 현재 보유: {new_gold}골드",
                delete_after=300
            )

        except Exception as e:
            print(f"❗ /뽑기 에러: {e}")
            await interaction.followup.send("⚠️ 오류가 발생했습니다.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))
