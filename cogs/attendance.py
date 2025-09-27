import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from pytz import timezone
import random
from utils import get_sheet, safe_int

class Attendance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_attendance_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Attendance")
        except:
            ws = sheet.add_worksheet(title="Attendance", rows=1000, cols=4)
            ws.append_row(["유저 ID", "닉네임", "출석일자", "지급 골드"])
            return ws

    @app_commands.command(name="출석", description="매일 출석체크하고 10~50 골드를 획득합니다.")
    async def 출석(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # 🔒 자기 자신만 볼 수 있게

        user_id = str(interaction.user.id)
        username = interaction.user.name
        today = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d")

        # ✅ Attendance 시트에서 오늘 출석했는지 확인
        att_sheet = self.get_attendance_sheet()
        records = att_sheet.get_all_records()
        for row in records:
            if str(row.get("유저 ID", "")) == user_id and row.get("출석일자") == today:
                await interaction.followup.send("✅ 이미 오늘 출석을 완료했어요!", ephemeral=True)
                return

        # ✅ 랜덤 보상 골드 (10~50)
        reward = random.randint(10, 50)

        # ✅ 메인 시트에서 골드 업데이트
        sheet = get_sheet()
        main_records = sheet.get_all_records()
        row_idx, user_row = None, None
        for idx, row in enumerate(main_records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                row_idx, user_row = idx, row
                break

        if not user_row:
            await interaction.followup.send("⚠️ 유저 데이터가 없습니다. 먼저 채팅을 쳐서 등록하세요.", ephemeral=True)
            return

        current_gold = safe_int(user_row.get("골드", 0))
        new_gold = current_gold + reward
        sheet.update_cell(row_idx, 13, new_gold)  # 13번째 열이 '골드'

        # ✅ Attendance 시트에 기록
        att_sheet.append_row([user_id, username, today, reward])

        # ✅ 자기 자신만 보이는 메시지
        await interaction.followup.send(
            f"🎉 출석 완료!\n"
            f"오늘 보상: **{reward} 골드**\n"
            f"현재 보유 골드: **{new_gold} 골드**",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Attendance(bot))
