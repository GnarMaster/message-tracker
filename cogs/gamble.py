import discord
from discord.ext import commands
from discord import app_commands
import uuid
from utils import get_sheet, safe_int


class GambleButton(discord.ui.Button):
    def __init__(self, label, gamble_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.gamble_id = gamble_id
        self.option = label

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name
        sheet = get_sheet().spreadsheet

        # Gamble_Log 시트 준비
        try:
            ws = sheet.worksheet("Gamble_Log")
        except:
            ws = sheet.add_worksheet(title="Gamble_Log", rows=1000, cols=7)
            ws.append_row(["도박 ID","유저 ID","닉네임","선택지","베팅 EXP","정답여부","지급 EXP"])

        records = ws.get_all_records()

        # 이미 참여했는지 확인 → 아무 반응 없이 무시
        for row in records:
            if row["도박 ID"] == self.gamble_id and str(row["유저 ID"]) == user_id:
                return

        # EXP -100 차감 (메인 시트)
        main_sheet = sheet.sheet1
        main_records = main_sheet.get_all_records()
        for idx, row in enumerate(main_records, start=2):
            if str(row.get("유저 ID")) == user_id:
                new_exp = safe_int(row.get("현재레벨경험치", 0)) - 100
                main_sheet.update_cell(idx, 11, new_exp)  # K열
                break

        # Gamble_Log 기록
        ws.append_row([self.gamble_id, user_id, username, self.option, 100, "", ""])


class CloseButton(discord.ui.Button):
    def __init__(self, gamble_id, host_id, view):
        super().__init__(label="⏹️ 마감하기", style=discord.ButtonStyle.danger)
        self.gamble_id = gamble_id
        self.host_id = host_id
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 마감 권한이 없습니다.", ephemeral=True)
            return

        # 선택지 버튼 비활성화
        for child in self.view_ref.children:
            if isinstance(child, GambleButton):
                child.disabled = True
        # 정산 버튼 활성화
        for child in self.view_ref.children:
            if isinstance(child, SettleButton):
                child.disabled = False
        self.disabled = True

        await self.view_ref.message.edit(
            content=f"🎲 도박 마감 🎲\n도박 ID: {self.gamble_id}\n⏰ 베팅이 종료되었습니다.",
            view=self.view_ref
        )


class SettleSelect(discord.ui.Select):
    def __init__(self, gamble_id, options, parent_view):
        self.gamble_id = gamble_id
        self.parent_view = parent_view
        select_options = [discord.SelectOption(label=opt, description=f"{opt} 선택") for opt in options]
        super().__init__(placeholder="정답을 선택하세요", options=select_options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        answer = self.values[0]
        sheet = get_sheet().spreadsheet
        ws = sheet.worksheet("Gamble_Log")
        records = ws.get_all_records()

        total_bet = 0
        winners = []
        for idx, row in enumerate(records, start=2):
            if row["도박 ID"] == self.gamble_id:
                total_bet += safe_int(row["베팅 EXP"])
                if row["선택지"] == answer:
                    winners.append((idx, row))

        if not winners:
            await interaction.response.send_message("❌ 정답자가 없습니다! (상금 몰수)", ephemeral=True)
            return

        prize = total_bet // len(winners)

        # 정산 처리
        winner_names = []
        for idx, row in winners:
            ws.update(f"F{idx}:G{idx}", [["O", prize]])
            winner_names.append(row["닉네임"])

            # 메인 시트 EXP 지급
            user_id = str(row["유저 ID"])
            main_sheet = sheet.sheet1
            main_records = main_sheet.get_all_records()
            for midx, mrow in enumerate(main_records, start=2):
                if str(mrow.get("유저 ID")) == user_id:
                    new_exp = safe_int(mrow.get("현재레벨경험치", 0)) + prize
                    main_sheet.update_cell(midx, 11, new_exp)
                    break

        winners_text = "\n".join([f"- {name}" for name in winner_names])

        # 정산 결과 공개 메시지
        await interaction.channel.send(
            f"✅ 정산 완료!\n"
            f"정답: {answer}\n"
            f"총 상금: {total_bet} exp\n"
            f"당첨자({len(winners)}명, 1인당 {prize} exp):\n{winners_text}"
        )

        # 투표 임베드 삭제
        try:
            await self.parent_view.message.delete()
        except:
            pass


class SettleButton(discord.ui.Button):
    def __init__(self, gamble_id, host_id, options, parent_view):
        super().__init__(label="⚖️ 정산하기", style=discord.ButtonStyle.success, disabled=True)
        self.gamble_id = gamble_id
        self.host_id = host_id
        self.options = options
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 정산 권한이 없습니다.", ephemeral=True)
            return

        view = discord.ui.View()
        view.add_item(SettleSelect(self.gamble_id, self.options, self.parent_view))
        await interaction.response.send_message("⚖️ 정답을 선택하세요:", view=view, ephemeral=True)


class GambleView(discord.ui.View):
    def __init__(self, gamble_id, topic, options, host_id):
        super().__init__(timeout=None)
        self.gamble_id = gamble_id
        self.topic = topic
        self.host_id = host_id

        for opt in options:
            self.add_item(GambleButton(opt, gamble_id))

        self.close_btn = CloseButton(gamble_id, host_id, self)
        self.settle_btn = SettleButton(gamble_id, host_id, options, self)
        self.add_item(self.close_btn)
        self.add_item(self.settle_btn)

        self.message = None


class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="도박시작", description="도박을 시작합니다 (관리자 전용)")
    async def start_gamble(self, interaction: discord.Interaction, 주제: str, *선택지: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 가능합니다.", ephemeral=True)
            return
        if len(선택지) < 2:
            await interaction.response.send_message("❌ 최소 2개 이상의 선택지가 필요합니다.", ephemeral=True)
            return

        gamble_id = f"GAMBLE_{uuid.uuid4().hex[:8]}"
        embed = discord.Embed(
            title="🎲 도박 시작 🎲",
            description=f"주제: {주제}\n베팅 금액: 100 EXP",
            color=discord.Color.gold()
        )
        view = GambleView(gamble_id, 주제, 선택지, str(interaction.user.id))
        message = await interaction.channel.send(embed=embed, view=view)
        view.message = message
        await interaction.response.send_message("✅ 도박을 시작했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Gamble(bot))
