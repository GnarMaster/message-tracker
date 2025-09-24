import discord
from discord.ext import commands
from discord import app_commands
from utils import get_sheet, safe_int, get_job_icon
from inventory_utils import use_item, get_inventory

# ✅ 1차 전직 직업 목록
FIRST_JOBS = ["전사", "마법사", "궁수", "도적", "특수"]

class JobSelect(discord.ui.Select):
    def __init__(self, user_id, row_idx, user_data):
        self.user_id = user_id
        self.row_idx = row_idx
        self.user_data = user_data

        options = [
            discord.SelectOption(label=job, description=f"{get_job_icon(job)} {job}")
            for job in FIRST_JOBS
        ]
        super().__init__(placeholder="변경할 직업을 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        new_job = self.values[0]
        old_job = self.user_data.get("직업", "백수")

        # ✅ 같은 직업이면 막기
        if new_job == old_job:
            await interaction.response.send_message(
                f"❌ 이미 **{get_job_icon(old_job)} {old_job}** 직업입니다!",
                ephemeral=True
            )
            return

        # ✅ 직업변경권 확인 & 차감
        has_ticket = use_item(self.user_id, "직업변경권", 1)
        if not has_ticket:
            await interaction.response.send_message("❌ 직업변경권이 없습니다!", ephemeral=True)
            return

        # ✅ 시트 업데이트 (직업 열: 12번째라고 가정)
        sheet = get_sheet()
        sheet.update_cell(self.row_idx, 12, new_job)

        # ✅ 본인에겐 따로 메시지 X (전체 방송으로 충분)
        await interaction.response.defer(ephemeral=True)

        # ✅ 서버 전체 방송
        await interaction.channel.send(
            f"{interaction.user.mention} 님이 "
            f"{get_job_icon(old_job)} **{old_job}** → {get_job_icon(new_job)} **{new_job}** 으로 전직하였습니다!"
        )

class JobChangeView(discord.ui.View):
    def __init__(self, user_id, row_idx, user_data):
        super().__init__(timeout=30)
        self.add_item(JobSelect(user_id, row_idx, user_data))

class ChangeJob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="직업변경", description="직업 변경권을 사용하여 직업을 변경합니다")
    async def 직업변경(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sheet = get_sheet()
        records = sheet.get_all_records()

        user_id = str(interaction.user.id)
        user_row = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID")) == user_id:
                user_row = (idx, row)
                break

        if not user_row:
            await interaction.followup.send("⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.", ephemeral=True)
            return

        row_idx, user_data = user_row

        # ✅ 직업변경권 보유 여부 확인
        items = dict(get_inventory(user_id))
        if items.get("직업변경권", 0) <= 0:
            await interaction.followup.send("❌ 직업변경권이 없습니다!", ephemeral=True)
            return

        view = JobChangeView(user_id, row_idx, user_data)
        await interaction.followup.send("⚔️ 변경할 직업을 선택하세요:", view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChangeJob(bot))
