import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

from main import get_sheet, safe_int, get_job_icon


class JobSelectView(View):
    def __init__(self, row_idx: int, bot: commands.Bot, channel_id: int):
        super().__init__(timeout=60)
        self.row_idx = row_idx
        self.bot = bot
        self.channel_id = channel_id

        self.add_item(
            Select(
                placeholder="전직할 직업을 선택하세요!",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(label="전사", description="추가 경험치 10%", emoji="⚔️"),
                    discord.SelectOption(label="마법사", description="특정 시간대 경험치 보너스", emoji="🔮"),
                    discord.SelectOption(label="궁수", description="헤드샷! 일정 확률 경험치 2배", emoji="🏹"),
                    discord.SelectOption(label="도적", description="하루 한번 경험치 스틸", emoji="🥷"),
                    discord.SelectOption(label="특수", description="0.5~2.5배 랜덤 경험치", emoji="🎭"),
                    
                ]
            )
        )

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select):
        chosen_job = select.values[0]
        sheet = get_sheet()
        sheet.update_cell(self.row_idx, 12, chosen_job)

        # 본인에게는 ephemeral로 완료 안내
        await interaction.response.edit_message(
            content=f"✅ 전직이 완료되었습니다! ({chosen_job} {get_job_icon(chosen_job)})",
            view=None
        )

        # 전체 채널 공지
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(
                f"🎉 {interaction.user.mention} 님이 "
                f"{get_job_icon(chosen_job)} **{chosen_job}** 으로 전직하였습니다!"
            )


class JobCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="전직", description="레벨 5 이상 백수만 전직할 수 있습니다.")
    async def 전직(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sheet = get_sheet()
        records = sheet.get_all_records()
        user_id = str(interaction.user.id)

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                current_level = safe_int(row.get("레벨", 1))
                current_job = row.get("직업", "백수")

                if current_level < 5:
                    await interaction.followup.send(
                        f"❌ {interaction.user.mention} 님은 아직 레벨이 부족합니다! "
                        "레벨 5 이상만 전직할 수 있어요.",
                        ephemeral=True
                    )
                    return

                if current_job != "백수":
                    await interaction.followup.send(
                        f"❌ {interaction.user.mention} 님은 이미 `{current_job}` 직업입니다. "
                        "전직은 한 번만 가능합니다!",
                        ephemeral=True
                    )
                    return

                # 조건 충족 → 전직 UI
                view = JobSelectView(idx, self.bot, interaction.channel.id)
                await interaction.followup.send(
                    "⚔️ 전직할 직업을 선택하세요:",
                    view=view,
                    ephemeral=True
                )
                return

        await interaction.followup.send(
            "⚠️ 유저 데이터를 찾을 수 없어요. 메시지를 좀 더 쳐야 기록이 생길 수 있어요!",
            ephemeral=True
        )
