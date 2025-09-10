import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
from utils import get_sheet, safe_int

class Mage(commands.Cog):
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
                date_str = row.get("사용일시")
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    return None
        return None

    # ✅ 스킬 사용 로그 기록
    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    # ✅ 체라 스킬
    @app_commands.command(
        name="체라",
        description="마법사 전용 스킬: 지정한 1명과 랜덤 1명을 동시에 공격합니다. (쿨타임 4시간)"
    )
    async def 체라(self, interaction: discord.Interaction, target: discord.Member):
        user_id = str(interaction.user.id)
        username = interaction.user.name
        target_id = str(target.id)

        await interaction.response.defer()

        # 쿨타임 확인 (4시간)
        last_used = self.get_last_skill_time(user_id, "체라")
        if last_used and datetime.now() < last_used + timedelta(hours=4):
            remain = (last_used + timedelta(hours=4)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요.")
            return

        sheet = get_sheet()
        records = sheet.get_all_records()

        user_row, target_row = None, None
        candidates = []
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
            elif str(row.get("유저 ID", "")) == target_id:
                target_row = (idx, row)
            else:
                # 랜덤 타겟은 레벨 2 이상만
                if safe_int(row.get("레벨", 1)) >= 2:
                    candidates.append((idx, row))

        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.")
            return
        if not target_row:
            await interaction.followup.send("⚠️ 대상 유저의 데이터가 없습니다.")
            return
        if not candidates:
            await interaction.followup.send("⚠️ 랜덤으로 맞을 유저(레벨 2 이상)가 없습니다.")
            return

        # 직업 확인 (마법사)
        if user_row[1].get("직업") != "마법사":
            await interaction.followup.send("❌ 마법사만 사용할 수 있는 스킬입니다!")
            return

        level = safe_int(user_row[1].get("레벨", 1))

        # 데미지 계산 함수
        def calc_damage():
            if random.randint(1, 100) <= 10:  # 10% 확률 대성공
                return 15 + (level * 2), "🔥 대성공!!!"
            else:
                return 8 + level, "✅ 성공"

        # 지정 대상 피해
        dmg1, msg1 = calc_damage()
        target_idx, target_data = target_row
        new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - dmg1
        sheet.update_cell(target_idx, 11, new_target_exp)

        # 랜덤 대상 피해 (절반만 적용)
        rand_idx, rand_data = random.choice(candidates)
        rand_id = str(rand_data.get("유저 ID"))
        dmg2 = dmg1 // 2
        new_rand_exp = safe_int(rand_data.get("현재레벨경험치", 0)) - dmg2
        sheet.update_cell(rand_idx, 11, new_rand_exp)

        # 로그 기록
        self.log_skill_use(
            user_id, username, "체라",
            f"{target.name} -{dmg1}, {rand_data.get('닉네임')} -{dmg2}"
        )

        # 출력 메시지
        await interaction.followup.send(
            f"🔮 {interaction.user.mention} 님의 **체인라이트닝** 발동!\n"
            f"🎯 지정 타겟: {target.mention} → {msg1} ({dmg1})\n"
            f"⚡ 연쇄 번개: <@{rand_id}> → 절반 피해 ({dmg2})\n"
            f"👉 {target.mention} -{dmg1} exp | <@{rand_id}> -{dmg2} exp"
        )

async def setup(bot):
    await bot.add_cog(Mage(bot))
