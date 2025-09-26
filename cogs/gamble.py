import discord
from discord.ext import commands
from discord import app_commands
import uuid
import asyncio
import os
from utils import get_sheet, safe_int

# ✅ 베팅 금액 입력 Modal
class BetAmountModal(discord.ui.Modal, title="베팅 GOLD 입력"):
    def __init__(self, gamble_id, option):
        super().__init__()
        self.gamble_id = gamble_id
        self.option = option
        self.amount = discord.ui.TextInput(
            label="베팅 GOLD (1~100)", # 이제 3초 오류 걱정 없이 바로 입력하세요
            placeholder="숫자만 입력",
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # 1. 3초 제한 회피를 위해 defer를 즉시 실행 (가장 먼저)
        await interaction.response.defer(ephemeral=True) 

        try:
            amount = safe_int(self.amount.value)
            
            # 금액 범위 체크
            if amount <= 0 or amount > 100:
                await interaction.followup.send("❌ 베팅 금액은 1~100 사이여야 합니다.", ephemeral=True)
                return

            # 2. 모든 Sheets I/O 작업을 동기 함수로 묶어 to_thread로 실행
            def process_bet_sync(gamble_id, user_id, amount):
                # Sheets 객체 및 시트 가져오기 (느린 작업)
                sheet = get_sheet().spreadsheet 
                
                # Gamble_Log 시트 확인/생성 
                try:
                    ws = sheet.worksheet("Gamble_Log")
                except:
                    ws = sheet.add_worksheet(title="Gamble_Log", rows=1000, cols=7)
                    ws.append_row(
                        ["도박 ID", "유저 ID", "닉네임", "선택지", "베팅 GOLD", "정답여부", "지급 GOLD"]
                    )
                
                # 이미 참여했는지 확인
                records = ws.get_all_records()
                for row in records:
                    if row["도박 ID"] == gamble_id and str(row["유저 ID"]) == user_id:
                        return "already_participated", None, None, ws
                
                # GOLD 잔액 확인 및 차감
                main_sheet = sheet.sheet1
                main_records = main_sheet.get_all_records()
                current_gold = 0
                user_row_index = -1

                for idx, row in enumerate(main_records, start=2):
                    if str(row.get("유저 ID")) == user_id:
                        current_gold = safe_int(row.get("골드", 0))
                        user_row_index = idx
                        break
                
                # 잔액 부족 체크 (요청 사항 반영)
                if current_gold < amount:
                    return "insufficient_gold", current_gold, current_gold, ws

                if user_row_index != -1:
                    new_gold = current_gold - amount
                    # GOLD 차감 (컬럼 13)
                    main_sheet.update_cell(user_row_index, 13, new_gold)
                    return "success", new_gold, current_gold, ws
                
                return "user_not_found", None, None, ws

            # 3. 백그라운드 스레드에서 실행
            result, new_gold, current_gold, ws = await asyncio.to_thread(
                process_bet_sync, self.gamble_id, user_id, amount
            )

            # 4. 결과에 따라 응답 처리 (Sheets 접근 없음)
            if result == "already_participated":
                await interaction.followup.send("❌ 이미 베팅에 참여했습니다.", ephemeral=True)
                return
            elif result == "insufficient_gold":
                 await interaction.followup.send(
                    f"❌ 골드가 부족합니다! 현재 소지 골드: {current_gold} GOLD", 
                    ephemeral=True
                )
                 return
            elif result == "user_not_found":
                await interaction.followup.send("❌ 사용자 정보를 찾을 수 없습니다.", ephemeral=True)
                return
            elif result == "success":
                # Gamble_Log에 베팅 기록 (최종 기록)
                await asyncio.to_thread(ws.append_row, [self.gamble_id, user_id, username, self.option, amount, "", ""])

                await interaction.followup.send(
                    f"✅ {amount} GOLD 베팅 완료! ({self.option})\n💰 남은 골드: {new_gold} GOLD",
                    ephemeral=True
                )

        except Exception as e:
            # 베팅 실패 시 잔액 부족 외의 오류 처리
            await interaction.followup.send(f"⚠️ 처리 중 오류 발생: {e}", ephemeral=True)


# --- (이하 나머지 클래스들은 GOLD 업데이트 및 컬럼 13 반영 완료 상태) ---

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
        await interaction.response.defer(ephemeral=True)
        if str(interaction.user.id) != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 마감 권한이 없습니다.", ephemeral=True)
            return

        for child in self.view_ref.children:
            if isinstance(child, GambleButton):
                child.disabled = True
        for child in self.view_ref.children:
            if isinstance(child, SettleButton):
                child.disabled = False
        self.disabled = True

        if self.view_ref.message:
            await self.view_ref.message.edit(
                content=f"🎲 도박 마감 🎲\n도박 ID: {self.gamble_id}\n⏰ 베팅이 종료되었습니다.",
                view=self.view_ref
            )
        if self.view_ref.admin_message:
            try:
                await self.view_ref.admin_message.edit(
                    content=f"🎲 도박 마감 (관리자용) 🎲\n도박 ID: {self.gamble_id}\n⏰ 베팅이 종료되었습니다.",
                    view=self.view_ref
                )
            except:
                pass


# ✅ 정산 Select
class SettleSelect(discord.ui.Select):
    def __init__(self, gamble_id, options, parent_view):
        self.gamble_id = gamble_id
        self.parent_view = parent_view
        select_options = [discord.SelectOption(label=opt, description=f"{opt} 선택") for opt in options]
        super().__init__(placeholder="정답을 선택하세요", options=select_options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            answer = self.values[0]
            sheet = get_sheet().spreadsheet
            ws = sheet.worksheet("Gamble_Log")
            
            # Sheets 동기 작업을 스레드에서 처리하는 함수 정의
            def process_settle_sync(gamble_id, answer):
                records = ws.get_all_records()
                total_bet = 0
                winners = []
                
                for idx, row in enumerate(records, start=2):
                    if row["도박 ID"] == gamble_id:
                        total_bet += safe_int(row.get("베팅 GOLD", 0))
                        if str(row.get("선택지", "")).strip() == str(answer).strip():
                            winners.append((idx, row))
                return total_bet, winners
            
            total_bet, winners = await asyncio.to_thread(process_settle_sync, self.gamble_id, answer)


            if not winners:
                await interaction.channel.send("❌ 정답자가 없습니다! (상금 몰수)")
                try:
                    if self.parent_view.message:
                        await self.parent_view.message.delete()
                    if self.parent_view.admin_message:
                        await self.parent_view.admin_message.delete()
                except:
                    pass
                return

            total_winner_bet = sum(safe_int(row.get("베팅 GOLD", 0)) for _, row in winners)
            winner_texts = []

            # Sheets 업데이트 및 GOLD 지급을 위한 동기 함수 정의
            def update_sheets_sync(winners, total_bet, total_winner_bet):
                main_sheet = sheet.sheet1
                main_records = main_sheet.get_all_records()
                
                local_winner_texts = []
                
                # ✅ 정답자가 1명일 경우 → 베팅 금액의 2배 지급
                if len(winners) == 1:
                    idx, row = winners[0]
                    bet_amount = safe_int(row.get("베팅 GOLD", 0))
                    share = bet_amount * 2

                    ws.update_cell(idx, 6, "O")
                    ws.update_cell(idx, 7, share)

                    local_winner_texts.append(f"- {row['닉네임']} (+{share} GOLD)")

                    user_id = str(row["유저 ID"])
                    for midx, mrow in enumerate(main_records, start=2):
                        if str(mrow.get("유저 ID")) == user_id:
                            new_GOLD = safe_int(mrow.get("골드", 0)) + share
                            main_sheet.update_cell(midx, 13, new_GOLD) # 컬럼 13으로 수정됨
                            break

                else:
                    # ✅ 정답자가 2명 이상일 경우 → 비례 배분
                    for idx, row in winners:
                        bet_amount = safe_int(row.get("베팅 GOLD", 0))
                        share = int(total_bet * (bet_amount / total_winner_bet)) if total_winner_bet > 0 else 0

                        ws.update_cell(idx, 6, "O")
                        ws.update_cell(idx, 7, share)

                        local_winner_texts.append(f"- {row['닉네임']} (+{share} GOLD)")

                        user_id = str(row["유저 ID"])
                        for midx, mrow in enumerate(main_records, start=2):
                            if str(mrow.get("유저 ID")) == user_id:
                                new_GOLD = safe_int(mrow.get("골드", 0)) + share
                                main_sheet.update_cell(midx, 13, new_GOLD) # 컬럼 13으로 수정됨
                                break
                return "\n".join(local_winner_texts)
            
            # Sheets 업데이트 실행
            winners_text = await asyncio.to_thread(update_sheets_sync, winners, total_bet, total_winner_bet)

            await interaction.channel.send(
                f"✅ 정산 완료!\n"
                f"정답: {answer}\n"
                f"총 상금: {total_bet} GOLD\n"
                f"분배 결과:\n{winners_text}"
            )

            try:
                if self.parent_view.message:
                    await self.parent_view.message.delete()
                if self.parent_view.admin_message:
                    await self.parent_view.admin_message.delete()
            except:
                pass

        except Exception as e:
            await interaction.followup.send(f"⚠️ 정산 오류 발생: {e}", ephemeral=True)


# ✅ 정산 버튼
class SettleButton(discord.ui.Button):
    def __init__(self, gamble_id, host_id, options, parent_view):
        super().__init__(label="⚖️ 정산하기", style=discord.ButtonStyle.success, disabled=True)
        self.gamble_id = gamble_id
        self.host_id = host_id
        self.options = options
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if str(interaction.user.id) != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 정산 권한이 없습니다.", ephemeral=True)
            return

        view = discord.ui.View()
        view.add_item(SettleSelect(self.gamble_id, self.options, self.parent_view))
        await interaction.followup.send("⚖️ 정답을 선택하세요:", view=view, ephemeral=True)


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
        self.admin_message = None


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
            description=f"주제: {주제}\n베팅 금액: 자유 (최대 100 GOLD)",
            color=discord.Color.gold()
        )
        view = GambleView(gamble_id, 주제, options, str(interaction.user.id))

        # 일반 채널 메시지
        message = await interaction.channel.send(embed=embed, view=view)
        view.message = message
            
        await interaction.response.send_message("✅ 도박을 시작했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Gamble(bot))
