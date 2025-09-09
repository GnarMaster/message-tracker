import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from utils import get_sheet, safe_int
import random

class Steal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ✅ Skill_Log 시트 가져오기
    def get_skill_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Skill_Log")
        except:
            return sheet.add_worksheet(title="Skill_Log", rows=1000, cols=5)

    # ✅ 마지막 사용 시간 가져오기
    def get_last_skill_time(self, user_id: str, skill_name: str):
        log_sheet = self.get_skill_log_sheet()
        records = log_sheet.get_all_records()
        for row in reversed(records):
            if str(row.get("유저 ID", "")) == user_id and row.get("스킬명") == skill_name:
                try:
                    return datetime.strptime(row.get("사용일시", ""), "%Y-%m-%d %H:%M:%S")
                except:
                    return None
        return None

    # ✅ 스킬 사용 로그 기록
    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    # ✅ 스틸 훔치는 양 계산 (확률 기반 + 레벨)
    def get_steal_amount(self, level: int) -> int:
        roll = random.uniform(0, 100)

        if roll <= 80:  # 1~10 (각 8%)
            base = random.randint(1, 10)
        elif roll <= 90:  # 실패 (10%)
            base = 0
        elif roll <= 99:  # 11~19 (각 1%)
            base = random.randint(11, 19)
        else:
            # 잭팟 구간 (총 1%)
            jackpot_roll = random.uniform(0, 1)
            if jackpot_roll <= 0.001:       # 0.1%
                base = 200
            elif jackpot_roll <= 0.005:    # 0.4%
                base = 100
            else:                          # 0.5%
                base = 50

        if base == 0:
            return 0  # 실패 → 레벨 보정 없음
        return base + level

    # ✅ 명령어: 스틸
    @app_commands.command(
        name="스틸",
        description="도적 전용 스킬: 다른 유저의 경험치를 훔칩니다. (쿨타임 4시간)"
    )
    async def 스틸(self, interaction: discord.Interaction, target: discord.Member):
        user_id = str(interaction.user.id)
        target_id = str(target.id)

        if user_id == target_id:
            await interaction.response.send_message("❌ 자신을 스틸할 수는 없습니다!", ephemeral=True)
            return

        # ⚡ 먼저 응답 예약 → 404 Unknown interaction 방지
        await interaction.response.defer(ephemeral=False)

        # 최근 사용 기록 확인 (쿨타임 4시간)
        last_used = self.get_last_skill_time(user_id, "스틸")
        if last_used and datetime.now() < last_used + timedelta(hours=4):
            remain = (last_used + timedelta(hours=4)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(
                f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요."
            )
            return

        sheet = get_sheet()
        records = sheet.get_all_records()

        user_row, target_row = None, None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
            if str(row.get("유저 ID", "")) == target_id:
                target_row = (idx, row)

        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.")
            return
        if not target_row:
            await interaction.followup.send("⚠️ 대상 유저의 데이터가 없습니다.")
            return

        user_idx, user_data = user_row
        target_idx, target_data = target_row

        if user_data.get("직업") != "도적":
            await interaction.followup.send("❌ 도적만 사용할 수 있는 스킬입니다!")
            return

        # ✅ 훔칠 양 계산
        current_level = safe_int(user_data.get("레벨", 1))
        steal_amount = self.get_steal_amount(current_level)

        if steal_amount <= 0:
            # 실패 처리
            self.log_skill_use(user_id, interaction.user.name, "스틸", f"실패 (대상: {target.name})")
            await interaction.followup.send(
                f"🥷 {interaction.user.name} 님이 {target.name} 님을 스틸하려 했지만 실패했습니다…"
            )
            return

        # ✅ 경험치 갱신 (음수 허용)
        new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - steal_amount
        new_user_exp = safe_int(user_data.get("현재레벨경험치", 0)) + steal_amount

        sheet.update_cell(target_idx, 11, new_target_exp)
        sheet.update_cell(user_idx, 11, new_user_exp)

        # ✅ 로그 기록
        self.log_skill_use(
            user_id,
            interaction.user.name,
            "스틸",
            f"대상: {target.name}, {steal_amount} exp"
        )

        # ✅ 성공 메시지
        await interaction.followup.send(
            f"🥷 {interaction.user.name} 님이 {target.name} 님을 스틸하였습니다! (**{steal_amount} exp**)\n"
            f"💀 {target.name} 님의 현재 경험치: {new_target_exp}"
        )

async def setup(bot):
    await bot.add_cog(Steal(bot))
