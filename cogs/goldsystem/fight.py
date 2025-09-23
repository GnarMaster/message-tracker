import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from utils import get_sheet, safe_int


class DuelView(discord.ui.View):
    def __init__(self, challenger, target, amount, sheet, c_idx, c_data, t_idx, t_data):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.target = target
        self.amount = amount
        self.sheet = sheet
        self.c_idx, self.c_data = c_idx, c_data
        self.t_idx, self.t_data = t_idx, t_data

    # ✅ 수락 버튼
    @discord.ui.button(label="✅ 수락", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ 당신은 대상자가 아닙니다.", ephemeral=True)
            return

        # 무조건 defer (상호작용 실패 방지)
        await interaction.response.defer()

        # 신청 Embed 삭제 (안되면 무시)
        try:
            await interaction.message.delete()
        except:
            pass

        challenger, target = self.challenger, self.target
        c_rolls, t_rolls = [], []
        duel_msgs = []

        # 시작 안내
        await interaction.followup.send(
            f"⚡ 결투 시작 ⚡\n{challenger.name} vs {target.name}\n🎲 주사위를 굴립니다..."
        )

        # 번갈아 주사위 3개씩 굴리기 (2초 간격)
        for i in range(3):
            roll_c = random.randint(1, 6)
            c_rolls.append(roll_c)
            msg_c = await interaction.followup.send(f"{challenger.name} 🎲 {i+1}번째: {roll_c}")
            duel_msgs.append(msg_c)
            await asyncio.sleep(2)

            roll_t = random.randint(1, 6)
            t_rolls.append(roll_t)
            msg_t = await interaction.followup.send(f"{target.name} 🎲 {i+1}번째: {roll_t}")
            duel_msgs.append(msg_t)
            await asyncio.sleep(2)

        # 합계 계산
        c_sum, t_sum = sum(c_rolls), sum(t_rolls)
        if c_sum > t_sum:
            winner, loser = challenger, target
            w_idx, l_idx = self.c_idx, self.t_idx
            w_gold = safe_int(self.c_data.get("골드", 0))
            l_gold = safe_int(self.t_data.get("골드", 0))
            result_text = f"🎉 **{challenger.name}** 승리!"
        elif t_sum > c_sum:
            winner, loser = target, challenger
            w_idx, l_idx = self.t_idx, self.c_idx
            w_gold = safe_int(self.t_data.get("골드", 0))
            l_gold = safe_int(self.c_data.get("골드", 0))
            result_text = f"🎉 **{target.name}** 승리!"
        else:
            winner = loser = None
            result_text = "🤝 무승부! (골드 이동 없음)"

        # 골드 갱신
        if winner and loser:
            new_w_gold = w_gold + self.amount
            new_l_gold = l_gold - self.amount
            self.sheet.update_cell(w_idx, 13, new_w_gold)
            self.sheet.update_cell(l_idx, 13, new_l_gold)

        # 결과 Embed
        embed = discord.Embed(title="⚔️ 결투 결과", color=discord.Color.gold())
        embed.add_field(name=f"{challenger.name} 🎲", value=f"{c_rolls} = **{c_sum}**", inline=False)
        embed.add_field(name=f"{target.name} 🎲", value=f"{t_rolls} = **{t_sum}**", inline=False)
        embed.add_field(name="결과", value=result_text, inline=False)

        if winner and loser:
            embed.add_field(
                name="골드 이동",
                value=f"🥇 {winner.name} +{self.amount}\n💀 {loser.name} -{self.amount}",
                inline=False
            )
            embed.set_footer(
                text=f"{winner.name} 보유: {new_w_gold}골드 | {loser.name} 보유: {new_l_gold}골드"
            )

        # 중간 로그 메시지 삭제
        for msg in duel_msgs:
            try:
                await msg.delete()
            except:
                pass

        await interaction.followup.send(embed=embed)

    # ❌ 거절 버튼
    @discord.ui.button(label="❌ 거절", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ 당신은 대상자가 아닙니다.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            await interaction.message.delete()
        except:
            pass

        await interaction.followup.send(
            embed=discord.Embed(
                title="🚫 결투 거절됨",
                description=f"{self.target.name} 님이 결투를 거절했습니다.",
                color=discord.Color.red()
            )
        )


class Fight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="결투", description="상대방과 골드를 걸고 결투합니다.")
    async def 결투(self, interaction: discord.Interaction, 대상: discord.Member, 금액: int):
        challenger = interaction.user
        target = 대상
        challenger_id, target_id = str(challenger.id), str(target.id)

        await interaction.response.defer(ephemeral=True)

        try:
            if challenger_id == target_id:
                await interaction.edit_original_response(content="❌ 자기 자신과는 결투할 수 없습니다.")
                return
            if 금액 <= 0:
                await interaction.edit_original_response(content="❌ 금액은 1 이상이어야 합니다.")
                return

            sheet = get_sheet()
            records = sheet.get_all_records()

            challenger_row, target_row = None, None
            for idx, row in enumerate(records, start=2):
                if str(row.get("유저 ID", "")) == challenger_id:
                    challenger_row = (idx, row)
                elif str(row.get("유저 ID", "")) == target_id:
                    target_row = (idx, row)

            if not challenger_row or not target_row:
                await interaction.edit_original_response(content="⚠️ 두 사람 모두 데이터가 있어야 합니다.")
                return

            c_idx, c_data = challenger_row
            t_idx, t_data = target_row
            c_gold = safe_int(c_data.get("골드", 0))
            t_gold = safe_int(t_data.get("골드", 0))

            if c_gold < 금액:
                await interaction.edit_original_response(
                    content=f"❌ {challenger.name} 님의 골드가 부족합니다! (보유: {c_gold})"
                )
                return
            if t_gold < 금액:
                await interaction.edit_original_response(
                    content=f"❌ {target.name} 님의 골드가 부족합니다! (보유: {t_gold})"
                )
                return

            # 시전자 안내 (ephemeral)
            await interaction.edit_original_response(content="✅ 결투 신청을 보냈습니다!")

            # 공개 임베드
            embed = discord.Embed(
                title="⚔️ 결투 신청",
                description=f"{challenger.name} 님이 {target.name} 님에게 **{금액}골드**를 걸고 결투를 신청했습니다!\n"
                            f"{target.mention}, 수락하시겠습니까?",
                color=discord.Color.blurple()
            )
            view = DuelView(challenger, target, 금액, sheet, c_idx, c_data, t_idx, t_data)
            await interaction.channel.send(embed=embed, view=view)

        except Exception as e:
            await interaction.edit_original_response(content=f"⚠️ 오류 발생: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fight(bot))
