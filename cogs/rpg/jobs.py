import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View

from datetime import datetime, timedelta
from pytz import timezone

from utils import get_sheet, safe_int, get_job_icon

def get_job_log_sheet():
    sheet = get_sheet().spreadsheet
    try:
        return sheet.worksheet("직변로그")
    except:
        ws = sheet.add_worksheet(title="직변로그", rows=1000, cols=5)
        ws.append_row(["직변 일시", "유저 ID", "닉네임", "기존 직업", "변경 직업"])
        return ws

class JobSelectView(View):
    def __init__(self, row_idx: int, bot: commands.Bot, channel_id: int):
        super().__init__(timeout=60)
        self.row_idx = row_idx
        self.bot = bot
        self.channel_id = channel_id

    @discord.ui.select(
        placeholder="전직할 직업을 선택하세요!",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="전사", description="삼연격: 지정 1명에게 점점 낮아지는 확률로 3연속 공격 (쿨타임 4시간)", emoji="⚔️"),
            discord.SelectOption(label="마법사", description="체인라이트닝: 지정 1명 + 랜덤 1명 동시 공격, 이후 연쇄 공격 (쿨타임 4시간)", emoji="🔮"),
            discord.SelectOption(label="궁수", description="더블샷: 지정 2명에게 연속 사격 (쿨타임 4시간, 같은 유저 지목 가능)", emoji="🏹"),
            discord.SelectOption(label="도적", description="스틸: 지정 1명의 경험치를 훔침 (쿨타임 4시간)", emoji="🥷"),
            discord.SelectOption(label="특수", description="폭탄: 랜덤 1명에게 폭탄 던지기 (쿨타임 4시간)", emoji="🎭"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        chosen_job = select.values[0]

        # ✅ 시트 업데이트
        sheet = get_sheet()
        records = sheet.get_all_records()
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 기존 직업 확인 및 업데이트
        old_job = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                old_job = row.get("직업", "백수")
                sheet.update_cell(idx, 12, chosen_job)  # 직업 갱신
                break

        # ✅ 직변로그 기록
        ws = get_job_log_sheet()
        today_str = datetime.now(timezone("Asia/Seoul")).strftime("%Y-%m-%d")
        ws.append_row([today_str, user_id, username, old_job, chosen_job])

        # ✅ 본인에게만 확인 메시지
        await interaction.response.edit_message(
            content=f"✅ 전직이 완료되었습니다! {old_job} → {chosen_job} {get_job_icon(chosen_job)}",
            view=None
        )

        # ✅ 전체 채널 공지
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(
                f"🎉 {interaction.user.mention} 님이 "
                f"{get_job_icon(chosen_job)} **{old_job} → {chosen_job}** 으로 전직했습니다!"
            )

class JobCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="전직", description="레벨 5 이상만 전직할 수 있습니다. 2주에 한번 변경 가능합니다")
    async def 전직(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sheet = get_sheet()
        records = sheet.get_all_records()
        user_id = str(interaction.user.id)

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                current_level = safe_int(row.get("레벨", 1))
                current_job = row.get("직업", "백수")

                # 🔴 레벨 부족
                if current_level < 5:
                    await interaction.followup.send(
                        f"❌ {interaction.user.mention} 님은 아직 레벨이 부족합니다! "
                        "레벨 5 이상만 전직할 수 있어요.",
                        ephemeral=True
                    )
                    return
                # 🔹 직변로그에서 최근 전직일 확인
                ws = get_job_log_sheet()
                log_records = ws.get_all_records()
                last_change = None
                for log in log_records:
                    if str(log.get("유저 ID", "")) == user_id:
                        try:
                            d = datetime.strptime(log.get("직변 일시", ""), "%Y-%m-%d").date()
                            if not last_change or d > last_change:
                                last_change = d
                        except:
                            pass

                today = datetime.now(timezone("Asia/Seoul")).date()
                if last_change and today < last_change + timedelta(days=14):
                    remain = (last_change + timedelta(days=14)) - today
                    await interaction.followup.send(
                        f"⏳ 최근 전직일: {last_change} → {remain.days}일 뒤 다시 가능합니다!",
                        ephemeral=True
                    )
                    return
                    
                # ✅ 조건 충족 → 전직 UI
                view = JobSelectView(idx, self.bot, interaction.channel.id)
                await interaction.followup.send(
                    f"⚔️ 현재 직업: {current_job}\n새 직업을 선택하세요:",
                    view=view,
                    ephemeral=True
                )
                return

        # 🔴 유저 데이터 없음
        await interaction.followup.send(
            "⚠️ 유저 데이터를 찾을 수 없어요. 메시지를 좀 더 쳐야 기록이 생길 수 있어요!",
            ephemeral=True
        )
async def setup(bot):
    await bot.add_cog(JobCog(bot))
