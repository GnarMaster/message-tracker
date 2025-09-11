import discord
from discord import app_commands
from discord.ext import commands
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
            return sheet.add_worksheet(title="Attendance", rows=1000, cols=5)

    @app_commands.command(name="출석", description="하루에 한번, 일정 경험치(10~40)를 제공합니다")
    async def 출석(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 한국 시간(KST) 기준 날짜
        now_kst = datetime.now(timezone("Asia/Seoul"))
        today = now_kst.strftime("%Y-%m-%d")

        sheet = self.get_attendance_sheet()
        records = sheet.get_all_records()

        # 이미 출석했는지 확인
        for row in records:
            row_user = str(row.get("유저 ID", "")).strip()
            row_date = str(row.get("날짜", "")).strip()
            if row_user == user_id and row_date == today:
                await interaction.followup.send("✅ 오늘은 이미 출석체크 했습니다!", ephemeral=True)
                return


        # 랜덤 경험치 보상 (기본 10~60, 10% 확률로 100)
        if random.random() <= 0.1:
            reward = 100
        else:
            reward = random.randint(10, 40)

        # 출석 기록 추가
        sheet.append_row([user_id, username, today, reward])

        # 메인 시트에서 경험치 갱신
        main_sheet = get_sheet()
        records = main_sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                current_exp = safe_int(row.get("현재레벨경험치", 0))
                main_sheet.update_cell(idx, 11, current_exp + reward)
                break

        # ✅ 본인에게만 결과 보여주기
        await interaction.response.send_message(
            f"🎉 출석 완료!\n⭐ 보상 경험치: **{reward} exp**",
            ephemeral=True
        )

        # ✅ 로또 당첨(100 exp)이면 전체 채널에 공지
        if reward == 100:
            await interaction.channel.send(
                f"🎊 {interaction.user.mention} 님이 출석 로또에 당첨되어 **100 exp**를 획득했습니다! 🎉"
            )

async def setup(bot):
    await bot.add_cog(Attendance(bot))
