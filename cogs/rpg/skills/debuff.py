import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from utils import get_sheet

# 🔒 관리자 전용 ID (본인)
ADMIN_ID = 648091499887591424  

class Debuff(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ✅ Buff_Log 시트 가져오기
    def get_buff_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Buff_Log")
        except:
            return sheet.add_worksheet(title="Buff_Log", rows=1000, cols=6)

    # ✅ 효과 기록 추가
    def add_effect(self, target_id: str, target_name: str, effect: str, caster_id: str, caster_name: str):
        sheet = self.get_buff_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now_str, target_id, target_name, effect, caster_id, caster_name])

    # ✅ 효과 조회
    def get_effects(self, user_id: str):
        sheet = self.get_buff_log_sheet()
        records = sheet.get_all_records()
        active = []
        for row in records:
            if str(row.get("유저 ID", "")) == str(user_id):
                active.append(row.get("상태"))
        return active

    # ✅ 효과 제거
    def remove_effect(self, user_id: str, effect: str):
        sheet = self.get_buff_log_sheet()
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):  # 헤더 제외
            if str(row.get("유저 ID", "")) == str(user_id) and row.get("상태") == effect:
                sheet.delete_rows(idx)
                break

    # ✅ 시전자 전용 알림 (ephemeral)
    async def notify_caster(self, interaction, target_name: str, effect: str):
        try:
            await interaction.followup.send(
                f"🤫 {target_name} 님에게 **{effect}** 효과가 부여되었습니다.",
                ephemeral=True
            )
        except:
            pass

    # ============================
    #  미치광이 광란 버프 관련 함수
    # ============================
    def check_madness(self, user_id: str) -> bool:
        """
        유저가 '광란' 상태면 효과를 제거하고 True 반환,
        아니면 False 반환.
        """
        effects = self.get_effects(user_id)
        if "광란" in effects:
            self.remove_effect(user_id, "광란")
            return True
        return False

    # ✅ 테스트용: 버프/디버프 걸기 (관리자만 가능)
    @app_commands.command(name="버프걸기", description="테스트용: 특정 유저에게 버프/디버프를 겁니다. (관리자 전용)")
    async def 버프걸기(self, interaction: discord.Interaction, target: discord.Member, effect: str):
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다!", ephemeral=True)
            return

        caster = interaction.user
        self.add_effect(str(target.id), target.name, effect, str(caster.id), caster.name)
        await interaction.response.send_message(
            f"✨ {target.mention} 님에게 **{effect}** 효과가 부여되었습니다!"
        )

async def setup(bot):
    await bot.add_cog(Debuff(bot))
