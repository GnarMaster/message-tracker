import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View

from utils import get_sheet, safe_int, get_job_icon


# ✅ 1차 전직 선택 UI
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
            discord.SelectOption(label="전사", description="삼연격", emoji="⚔️"),
            discord.SelectOption(label="마법사", description="체인라이트닝", emoji="🔮"),
            discord.SelectOption(label="궁수", description="더블샷", emoji="🏹"),
            discord.SelectOption(label="도적", description="스틸", emoji="🥷"),
            discord.SelectOption(label="특수", description="폭탄", emoji="🎭"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        chosen_job = select.values[0]

        sheet = get_sheet()
        sheet.update_cell(self.row_idx, 12, chosen_job)

        await interaction.response.edit_message(
            content=f"✅ 전직이 완료되었습니다! {get_job_icon(chosen_job)} **{chosen_job}**",
            view=None
        )

        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(
                f"🎉 {interaction.user.mention} 님이 "
                f"{get_job_icon(chosen_job)} **{chosen_job}** 으로 전직하였습니다!"
            )


# ✅ 2차 전직 선택 UI
class SecondJobSelectView(View):
    def __init__(self, row_idx: int, bot: commands.Bot, channel_id: int, first_job: str):
        super().__init__(timeout=60)
        self.row_idx = row_idx
        self.bot = bot
        self.channel_id = channel_id

        # 구현 완료된 2차 직업만 제공
        job_options = {
            "전사": [
                discord.SelectOption(label="검성", description="4연격, 강력한 추가타", emoji="🗡️"),
                discord.SelectOption(label="검투사", description="반격 버프 사용", emoji="🛡️"),
                discord.SelectOption(label="투신", description="삼연격 후 랜덤 대상 추가 일격", emoji="🪓"),
            ],
            "마법사": [
                discord.SelectOption(label="폭뢰술사", description="모든 번개를 한 대상에 집중", emoji="⚡"),
                discord.SelectOption(label="연격마도사", description="2타는 지정 대상 공격, 뒤는 랜덤 연격", emoji="🔮"),
            ],
            "궁수": [
                discord.SelectOption(label="저격수", description="치명적인 단일 저격(추가데미지)", emoji="🎯"),
                discord.SelectOption(label="연사수", description="2타후 랜덤 대상 추가 일격", emoji="🏹"),
            ],
            "도적": [
                discord.SelectOption(label="암살자", description="연속 스틸 가능성", emoji="🗡️"),
                discord.SelectOption(label="의적", description="훔친 경험치 일부 분배", emoji="📦"),
                discord.SelectOption(label="카피닌자", description="상대의 스킬 복사", emoji="💀"),
            ],
            "특수": [
                discord.SelectOption(label="파괴광", description="추가 폭발 피해", emoji="💥"),
                discord.SelectOption(label="축제광", description="랜덤 인원에 랜덤 효과 발생", emoji="🎉"),
            ],
        }

        options = job_options.get(first_job, [])

        # ✅ Select 컴포넌트 생성 후 View에 추가
        select = discord.ui.Select(
            placeholder="2차 전직할 직업을 선택하세요!",
            min_values=1,
            max_values=1,
            options=options
        )

        async def select_callback(interaction: discord.Interaction):
            chosen_job = select.values[0]
            sheet = get_sheet()
            sheet.update_cell(self.row_idx, 12, chosen_job)

            await interaction.response.edit_message(
                content=f"✅ 2차 전직 완료! {get_job_icon(chosen_job)} **{chosen_job}**",
                view=None
            )

            channel = self.bot.get_channel(self.channel_id)
            if channel:
                await channel.send(
                    f"🎉 {interaction.user.mention} 님이 "
                    f"{get_job_icon(chosen_job)} **{chosen_job}** 으로 2차 전직했습니다!"
                )

        select.callback = select_callback
        self.add_item(select)


# ✅ Cog
class JobCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 1차 전직
    @app_commands.command(name="전직", description="레벨 5 이상 백수만 전직할 수 있습니다.")
    async def 전직(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sheet = get_sheet()
        records = sheet.get_all_records()
        user_id = str(interaction.user.id)

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                level = safe_int(row.get("레벨", 1))
                job = row.get("직업", "백수")

                if level < 5:
                    await interaction.followup.send(
                        f"❌ {interaction.user.mention} 님은 아직 레벨이 부족합니다! (5 이상 필요)",
                        ephemeral=True
                    )
                    return

                if job != "백수":
                    await interaction.followup.send(
                        f"❌ 이미 `{job}` 직업입니다.",
                        ephemeral=True
                    )
                    return

                view = JobSelectView(idx, self.bot, interaction.channel.id)
                await interaction.followup.send(
                    "⚔️ 전직할 직업을 선택하세요:",
                    view=view,
                    ephemeral=True
                )
                return

        await interaction.followup.send("⚠️ 유저 데이터를 찾을 수 없습니다.", ephemeral=True)

    # 2차 전직
    @app_commands.command(name="2차전직", description="레벨 10 이상 1차 전직자만 2차 전직할 수 있습니다.")
    async def second_job(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        sheet = get_sheet()
        records = sheet.get_all_records()
        user_id = str(interaction.user.id)

        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                level = safe_int(row.get("레벨", 1))
                job = row.get("직업", "백수")

                if level < 10:
                    await interaction.followup.send(
                        f"❌ {interaction.user.mention} 님은 레벨 10 이상만 2차 전직할 수 있어요.",
                        ephemeral=True
                    )
                    return

                if job in ["백수"]:
                    await interaction.followup.send(
                        f"❌ 아직 1차 전직을 하지 않았습니다. `/전직` 먼저 하세요!",
                        ephemeral=True
                    )
                    return

                if job not in ["전사", "마법사", "궁수", "도적", "특수"]:
                    await interaction.followup.send(
                        f"❌ 이미 `{job}` 직업입니다. (2차 전직 완료)",
                        ephemeral=True
                    )
                    return

                view = SecondJobSelectView(idx, self.bot, interaction.channel.id, job)
                await interaction.followup.send(
                    f"⚔️ {interaction.user.mention} 님, 2차 전직 직업을 선택하세요:",
                    view=view,
                    ephemeral=True
                )
                return

        await interaction.followup.send("⚠️ 유저 데이터를 찾을 수 없습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(JobCog(bot))
