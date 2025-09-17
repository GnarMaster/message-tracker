import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
from utils import get_sheet, safe_int, get_copied_skill, clear_copied_skill, check_counter

class Archer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_skill_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Skill_Log")
        except:
            return sheet.add_worksheet(title="Skill_Log", rows=1000, cols=5)

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

    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    @app_commands.command(
        name="더블샷",
        description="궁수 전용 스킬: 지정한 두 명을 동시에 저격합니다. (쿨타임 4시간)"
    )
    @app_commands.describe(target1="첫 번째 대상", target2="두 번째 대상")
    async def 더블샷(self, interaction: discord.Interaction, target1: discord.Member, target2: discord.Member):
        user_id = str(interaction.user.id)
        username = interaction.user.name

        await interaction.response.send_message("🏹 더블샷 준비 중...", ephemeral=True)

        # 쿨타임 확인
        last_used = self.get_last_skill_time(user_id, "더블샷")
        if last_used and datetime.now() < last_used + timedelta(hours=4):
            remain = (last_used + timedelta(hours=4)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요.", ephemeral=True)
            return

        sheet = get_sheet()
        records = sheet.get_all_records()

        user_row, row1, row2 = None, None, None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
            if str(row.get("유저 ID", "")) == str(target1.id):
                row1 = (idx, row)
            if str(row.get("유저 ID", "")) == str(target2.id):
                row2 = (idx, row)

        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.", ephemeral=True)
            return
        if not row1 or not row2:
            await interaction.followup.send("⚠️ 대상 유저의 데이터가 없습니다.", ephemeral=True)
            return

        # 직업 확인
        job = user_row[1].get("직업", "백수")
        if job == "카피닌자":
            copied_skill = get_copied_skill(user_id)
            if copied_skill != "더블샷":
                await interaction.followup.send("❌ 현재 복사한 스킬이 더블샷이 아닙니다.", ephemeral=True)
                return
            clear_copied_skill(user_id)
            prefix_msg = f"💀 카피닌자 {interaction.user.name}님이 복사한 스킬 **더블샷**을 발동!\n"
        else:
            if job != "궁수":
                await interaction.followup.send("❌ 궁수만 사용할 수 있는 스킬입니다!", ephemeral=True)
                return
            prefix_msg = f"🏹 {interaction.user.name} 님의 **더블샷** 발동!\n"

        level = safe_int(user_row[1].get("레벨", 1))
        user_idx, user_data = user_row

        def calc_damage():
            base = 4 + level
            crit_chance = 20
            miss_chance = max(0, 10 - (level // 5))
            hit_chance = 100 - crit_chance - miss_chance

            roll = random.randint(1, 100)
            if roll <= crit_chance:
                return base * 2, "🔥 치명타!!!"
            elif roll <= crit_chance + hit_chance:
                return base, "✅ 명중!"
            else:
                return 0, "❌ 빗나감..."

        # ================================
        # 🔹 광란 체크 (시전자 기준)
        # ================================
        debuff_cog = interaction.client.get_cog("Debuff")
        if debuff_cog and debuff_cog.check_madness(user_id):
            # 광란 발동 → 자기 자신 두 발 맞음
            dmg1, msg1 = calc_damage()
            dmg2, msg2 = calc_damage()
            total_dmg = dmg1 + dmg2

            new_exp = safe_int(user_data.get("현재레벨경험치", 0)) - total_dmg
            sheet.update_cell(user_idx, 11, new_exp)

            self.log_skill_use(user_id, username, "더블샷", f"광란! 자기 자신 -{total_dmg}")
            
            result_msg = (
                prefix_msg +
                f"🤪 광란 발동! {username} 님은 이성을 잃고 자기 자신을 공격했습니다!\n" +
                f"💥 1발: {msg1} ({dmg1})\n" +
                f"💥 2발: {msg2} ({dmg2})\n" +
                f"☠️ 최종 피해: {total_dmg}"
            )
            await interaction.followup.send(result_msg)
            return

        result_msg = prefix_msg
       
        # 첫 번째 타겟
        dmg1, msg1 = calc_damage()
        idx1, data1 = row1
        cm1 = check_counter(user_id, username, str(target1.id), target1.mention, dmg1)

        if cm1:
            # 반격이면 공격자 경험치 차감
            result_msg += f"🎯 첫 번째 타겟: {target1.mention} → 공격 무효!\n{cm1}\n"
        else:
            new_exp1 = safe_int(data1.get("현재레벨경험치", 0)) - dmg1
            sheet.update_cell(idx1, 11, new_exp1)
            result_msg += f"🎯 첫 번째 타겟: {target1.mention} → {msg1} ({dmg1})\n"

        # 두 번째 타겟
        dmg2, msg2 = calc_damage()
        idx2, data2 = row2
        cm2 = check_counter(user_id, username, str(target2.id), target2.mention, dmg2)

        if cm2:
            result_msg += f"🎯 두 번째 타겟: {target2.mention} → 공격 무효!\n{cm2}\n"
        else:
            if idx1 == idx2:
                # 같은 대상이면 누적 적용
                new_exp2 = safe_int(data1.get("현재레벨경험치", 0)) - dmg1 - dmg2
                sheet.update_cell(idx2, 11, new_exp2)
            else:
                new_exp2 = safe_int(data2.get("현재레벨경험치", 0)) - dmg2
                sheet.update_cell(idx2, 11, new_exp2)
            result_msg += f"🎯 두 번째 타겟: {target2.mention} → {msg2} ({dmg2})\n"

        # 로그 저장
        self.log_skill_use(user_id, username, "더블샷", f"{target1.name} -{dmg1}, {target2.name} -{dmg2}")

        await interaction.followup.send(result_msg)


async def setup(bot):
    await bot.add_cog(Archer(bot))
