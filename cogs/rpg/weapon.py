import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from utils import get_sheet, safe_int

FORGE_CHANNEL_ID = 1422438929801678899  # ⚒️ 대장간 채널 ID
GENERAL_CHANNEL_ID = 685135149788037184  # 📢 전체 공지 채널 ID

# 강화 확률/실패/파괴/소모골드/무기공격력
ENHANCE_TABLE = {
    2: (1.00, 0.00, 0.00, 5, 2),
    3: (0.60, 0.40, 0.00, 10, 4),
    4: (0.50, 0.50, 0.00, 20, 7),
    5: (0.40, 0.60, 0.00, 35, 11),
    6: (0.307, 0.693, 0.00, 55, 16),
    7: (0.205, 0.765, 0.03, 80, 22),
    8: (0.103, 0.857, 0.04, 110, 29),
    9: (0.05, 0.90, 0.05, 145, 35),
    10: (0.00, 0.00, 0.00, 0, 50),  # 만렙
}

# ✅ Weapon 시트 가져오기 (없으면 생성)
def get_weapon_sheet():
    spreadsheet = get_sheet().spreadsheet
    try:
        return spreadsheet.worksheet("Weapon")
    except:
        ws = spreadsheet.add_worksheet(title="Weapon", rows=1000, cols=4)
        ws.append_row(["유저 ID", "닉네임", "무기강화상태", "무기공격력"])
        return ws

def get_weapon(user_id: str):
    ws = get_weapon_sheet()
    records = ws.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID", "")) == str(user_id):
            return idx, row
    return None

def ensure_weapon(user_id: str, nickname: str):
    exist = get_weapon(user_id)
    if exist:
        return exist
    ws = get_weapon_sheet()
    ws.append_row([user_id, nickname, 1, 1])  # 기본 1강, 공격력 1
    return get_weapon(user_id)

def update_weapon(idx, stage, atk):
    ws = get_weapon_sheet()
    ws.update_cell(idx, 3, stage)
    ws.update_cell(idx, 4, atk)

def get_gold(user_id: str):
    """시트1에서 골드(13열) 불러오기"""
    sheet = get_sheet()
    records = sheet.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID", "")) == str(user_id):
            return idx, safe_int(row.get("골드", 0))
    return None, 0

# ✅ 시트1 골드 업데이트
def update_gold(idx, new_gold):
    spreadsheet = get_sheet().spreadsheet
    ws = spreadsheet.worksheet("시트1")
    ws.update_cell(idx, 13, new_gold)


class ForgeView(discord.ui.View):
    def __init__(self, bot, user_id, nickname):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.nickname = nickname

    @discord.ui.button(label="강화하기", style=discord.ButtonStyle.primary)
    async def enhance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ 당신의 무기가 아닙니다!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # ✅ 원본 메시지 삭제
        try:
            await interaction.message.delete()
        except:
            pass

        idx, row = ensure_weapon(self.user_id, self.nickname)
        stage = safe_int(row.get("무기강화상태", 1))
        atk = safe_int(row.get("무기공격력", 1))
        g_idx, gold = get_gold(self.user_id)

        if stage >= 10:
            await interaction.followup.send("⚠️ 이미 10강 만렙입니다!", ephemeral=True)
            return

        succ, fail, destroy, cost, new_atk = ENHANCE_TABLE.get(
            stage+1, (0, 0, 0, 0, atk))
        if gold < cost:
            await interaction.followup.send(
                f"💰 골드 부족! 필요: {cost}G (보유 {gold}G)", ephemeral=True
            )
            return

        # 골드 차감
        update_gold(g_idx, gold - cost)

        msg = await interaction.followup.send("강화 중… 🔨", ephemeral=True)
        await asyncio.sleep(1.5)

        roll = random.random()
        if roll <= succ:
            # 성공
            new_stage = stage + 1
            update_weapon(idx, new_stage, new_atk)
            await msg.edit(content=f"✅ 강화 성공! {stage}강 → {new_stage}강 (공격력 {new_atk})")

            if new_stage == 10:
                channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
                if channel:
                    await channel.send(f"🎉 {interaction.user.mention} 님이 **+10강** 무기 강화에 성공하셨습니다!")

        elif roll <= succ + fail:
            # 실패
            if stage == 5:
                update_weapon(idx, 4, ENHANCE_TABLE[4][4])
                await msg.edit(content="❌ 강화 실패... 5강에서 4강으로 하락했습니다.")
            elif stage >= 6:
                update_weapon(idx, stage-1, ENHANCE_TABLE[stage-1][4])
                await msg.edit(content=f"❌ 강화 실패... {stage}강에서 {stage-1}강으로 하락했습니다.")
            else:
                await msg.edit(content=f"❌ 강화 실패... {stage}강 유지")

        else:
            # 파괴
            update_weapon(idx, 1, 1)
            await msg.edit(content="💥 무기 파괴! 1강으로 초기화되었습니다.")


class WeaponCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="내무기", description="내 무기 상태를 확인하고 강화합니다.")
    async def 무기(self, interaction: discord.Interaction):
        if interaction.channel_id != FORGE_CHANNEL_ID:
            await interaction.response.send_message("❌ 이 명령어는 대장간 채널에서만 사용할 수 있습니다.", ephemeral=True)
            return

        # ✅ defer는 맨 앞에서 호출
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        nickname = interaction.user.name
        idx, row = ensure_weapon(user_id, nickname)
        stage = safe_int(row.get("무기강화상태", 1))
        atk = safe_int(row.get("무기공격력", 1))
        g_idx, gold = get_gold(user_id)

        embed = discord.Embed(title="⚒️ 무기 상태", color=discord.Color.orange())
        embed.add_field(name="닉네임", value=nickname, inline=True)
        embed.add_field(name="강화 단계", value=f"{stage}강", inline=True)
        embed.add_field(name="무기 공격력", value=str(atk), inline=True)
        embed.add_field(name="보유 골드", value=f"{gold}G", inline=True)

        if stage < 10:
            succ, fail, destroy, cost, new_atk = ENHANCE_TABLE[stage+1]
            embed.add_field(name="다음 단계", value=f"{stage+1}강", inline=True)
            embed.add_field(name="성공확률", value=f"{succ*100:.1f}%", inline=True)
            if fail > 0:
                embed.add_field(name="실패확률", value=f"{fail*100:.1f}%", inline=True)
            if destroy > 0:
                embed.add_field(name="파괴확률", value=f"{destroy*100:.1f}%", inline=True)
            embed.add_field(name="소모 골드", value=f"{cost}G", inline=True)
        else:
            embed.add_field(name="상태", value="최대 강화 완료!", inline=False)

        view = None
        if stage < 10:
            view = ForgeView(self.bot, user_id, nickname)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WeaponCog(bot))
