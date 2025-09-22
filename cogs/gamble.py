import discord
from discord.ext import commands
from discord import app_commands
import uuid
from utils import get_sheet, safe_int


# ✅ 베팅 금액 입력 Modal
class BetAmountModal(discord.ui.Modal, title="베팅 금액 입력"):
    def __init__(self, gamble_id, option):
        super().__init__()
        self.gamble_id = gamble_id
        self.option = option
        self.amount = discord.ui.TextInput(
            label="베팅 금액 (1~100)",
            placeholder="숫자만 입력",
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name
        sheet = get_sheet().spreadsheet

        # 시트 준비
        try:
            ws = sheet.worksheet("Gamble_Log")
        except:
            ws = sheet.add_worksheet(title="Gamble_Log", rows=1000, cols=7)
            ws.append_row(["도박 ID","유저 ID","닉네임","선택지","베팅 EXP","정답여부","지급 EXP"])

        records = ws.get_all_records()

        # 이미 참여했으면 무시
        for row in records:
            if row["도박 ID"] == self.gamble_id and str(row["유저 ID"]) == user_id:
                await interaction.response.send_message("❌ 이미 베팅에 참여했습니다.", ephemeral=True)
                return

        amount = safe_int(self.amount.value)
        if amount <= 0 or amount > 100:
            await interaction.response.send_message("❌ 베팅 금액은 1~100 사이여야 합니다.", ephemeral=True)
            return

        # EXP 차감
        main_sheet = sheet.sheet1
        main_records = main_sheet.get_all_records()
        for idx, row in enumerate(main_records, start=2):
            if str(row.get("유저 ID")) == user_id:
                new_exp = safe_int(row.get("현재레벨경험치", 0)) - amount
                main_sheet.update_cell(idx, 11, new_exp)  # K열
                break

        # 기록
        ws.append_row([self.gamble_id, user_id, username, self.option, amount, "", ""])

        await interaction.response.send_message(
            f"✅ {amount} EXP 베팅 완료! ({self.option})",
            ephemeral=True
        )


# ✅ 베팅 버튼
class GambleButton(discord.ui.Button):
    def __init__(self, label, gamble_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.gamble_id = gamble_id
        self.option = label

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BetAmountModal(self.gamble_id, self.option))


# ✅ 마감 버튼
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

        for child in self.view_ref.children:
            if isinstance(child, GambleButton):
                child.disabled = True
        for child in self.view_ref.children:
            if isinstance(child, SettleButton):
                child.disabled = False
        self.disabled = True

        await self.view_ref.message.edit(
            content=f"🎲 도박 마감 🎲\n도박 ID: {self.gamble_id}\n⏰ 베팅이 종료되었습니다.",
            view=self.view_ref
        )
        await interaction.response.defer(ephemeral=True)


# ✅ 정산 Select
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

        total_winner_bet = sum(safe_int(row["베팅 EXP"]) for _, row in winners)

        # 비례 배분
        winner_texts = []
        for idx, row in winners:
            bet_amount = safe_int(row["베팅 EXP"])
            share = int(total_bet * (bet_amount / total_winner_bet))
            ws.update(f"F{idx}:G{idx}", [["O", share]])

            winner_texts.append(f"- {row['닉네임']} (+{share} EXP)")

            # 메인 시트 EXP 지급
            user_id = str(row["유저 ID"])
            main_sheet = sheet.sheet1
            main_records = main_sheet.get_all_records()
            for midx, mrow in enumerate(main_records, start=2):
                if str(mrow.get("유저 ID")) == user_id:
                    new_exp = safe_int(mrow.get("현재레벨경험치", 0)) + share
                    main_sheet.update_cell(midx, 11, new_exp)
                    break

        winners_text = "\n".join(winner_texts)

        await interaction.channel.send(
            f"✅ 정산 완료!\n"
            f"정답: {answer}\n"
            f"총 상금: {total_bet} exp\n"
            f"분배 결과:\n{winners_text}"
        )

        try:
            await self.parent_view.message.delete()
        except:
            pass

        await interaction.response.defer(ephemeral=True)


# ✅ 정산 버튼
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


# ✅ View
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


# ✅ Cog
class Gamble(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="도박시작", description="도박을 시작합니다 (관리자 전용, 선택지 최대 8개)")
    async def start_gamble(
        self,
        interaction: discord.Interaction,
        주제: str,
        선택지1: str,
        선택지2: str,
        선택지3: str = None,
        선택지4: str = None,
        선택지5: str = None,
        선택지6: str = None,
        선택지7: str = None,
        선택지8: str = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 가능합니다.", ephemeral=True)
            return

        options = [opt for opt in [
            선택지1, 선택지2, 선택지3, 선택지4,
            선택지5, 선택지6, 선택지7, 선택지8
        ] if opt]

        if len(options) < 2:
            await interaction.response.send_message("❌ 최소 2개 이상의 선택지가 필요합니다.", ephemeral=True)
            return

        gamble_id = f"GAMBLE_{uuid.uuid4().hex[:8]}"
        embed = discord.Embed(
            title="🎲 도박 시작 🎲",
            description=f"주제: {주제}\n베팅 금액: 자유 (최대 100 EXP)",
            color=discord.Color.gold()
        )
        view = GambleView(gamble_id, 주제, options, str(interaction.user.id))
        message = await interaction.channel.send(embed=embed, view=view)
        view.message = message
        await interaction.response.send_message("✅ 도박을 시작했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Gamble(bot))

