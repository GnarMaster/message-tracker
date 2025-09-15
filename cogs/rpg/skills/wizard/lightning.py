import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
from utils import get_sheet, safe_int, get_copied_skill, clear_copied_skill

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
        description="마법사 전용 스킬: 지정 1명 + 랜덤 1명 동시 공격 이후 연쇄 공격 (쿨타임 4시간)"
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
            await interaction.followup.send(f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요.", ephemeral=True)
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
                # 랜덤 타겟 후보 (레벨 2 이상만)
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

        # 직업 확인
        job = user_row[1].get("직업", "백수")

        # ✅ 카피닌자 처리
        if job == "카피닌자":
            copied_skill = get_copied_skill(user_id)
            if copied_skill != "체라":
                await interaction.followup.send("❌ 현재 복사한 스킬이 체라가 아닙니다.", ephemeral=True)
                return
            else:
                clear_copied_skill(user_id)
                prefix_msg = f"💀 카피닌자 {interaction.user.name}님이 복사한 스킬 **체인라이트닝**을 발동!\n"
        else :
            if job != "마법사":
                await interaction.followup.send("❌ 마법사만 사용할 수 있는 스킬입니다!", ephemeral=True)
                return
            prefix_msg = f"🔮 {interaction.user.name}님의 **체인라이트닝** 발동!\n"


        level = safe_int(user_row[1].get("레벨", 1))

        # 기본뎀 계산
        if random.randint(1, 100) <= 10:  # 첫타 대성공
            base_damage = 12 + (level * 2)
            msg_base = "🔥 대성공!!!"
        else:
            base_damage = 6 + level
            msg_base = "✅ 성공"

        damage_logs = []

        # 1️⃣ 지정 대상 (풀뎀)
        target_idx, target_data = target_row
        dmg = base_damage
        # 치명타 판정 (10%)
        if random.randint(1, 100) <= 10:
            dmg *= 2
            msg1 = "🔥 치명타!"
        else:
            msg1 = msg_base
        new_exp = safe_int(target_data.get("현재레벨경험치", 0)) - dmg
        sheet.update_cell(target_idx, 11, new_exp)
        damage_logs.append(f"🎯 지정 타겟 {target.mention} → {msg1} ({dmg})")

        # 2️⃣ 첫 랜덤 대상 (기본뎀 // 2)
        if candidates:
            rand_idx, rand_data = random.choice(candidates)
            rand_id = str(rand_data.get("유저 ID"))
            candidates.remove((rand_idx, rand_data))

            base = base_damage // 2
            if base > 0:
                dmg = base
                if random.randint(1, 100) <= 10:
                    dmg *= 2
                    msg2 = "🔥 치명타!"
                else:
                    msg2 = "✅ 명중!"
                new_exp = safe_int(rand_data.get("현재레벨경험치", 0)) - dmg
                sheet.update_cell(rand_idx, 11, new_exp)
                rand_name = rand_data.get("닉네임", f"ID:{rand_id}")
                damage_logs.append(f"⚡ 연쇄 번개: {rand_name} → {msg2} ({dmg})")

                # 3️⃣ 이후 연쇄
                prob = 0.5
                step = 4
                while candidates and random.random() < prob:
                    base = base_damage // step
                    if base <= 0:
                        break
                    dmg = base
                    if random.randint(1, 100) <= 10:
                        dmg *= 2
                        msgX = "🔥 치명타!"
                    else:
                        msgX = "✅ 명중!"
                    rand_idx, rand_data = random.choice(candidates)
                    rand_id = str(rand_data.get("유저 ID"))
                    candidates.remove((rand_idx, rand_data))
                    new_exp = safe_int(rand_data.get("현재레벨경험치", 0)) - dmg
                    sheet.update_cell(rand_idx, 11, new_exp)
                    rand_name = rand_data.get("닉네임", f"ID:{rand_id}")
                    damage_logs.append(f"⚡ 추가 연쇄: {rand_name} → {msgX} ({dmg})")

                    prob *= 0.5
                    step *= 2

        # 로그 기록
        self.log_skill_use(
            user_id, username, "체라",
            "; ".join(damage_logs)
        )

        # 출력 메시지
        await interaction.followup.send(
            prefix_msg +
            "\n".join(damage_logs)
        )

async def setup(bot):
    await bot.add_cog(Mage(bot))
