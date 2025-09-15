import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from utils import get_sheet, safe_int, check_counter, save_copied_skill
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
                date_str = row.get("사용일시") or row.get("사용 일시")
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    except:
                        return None
        return None

    # ✅ 스킬 사용 로그 기록
    def log_skill_use(self, user_id: str, username: str, skill_name: str, note: str = ""):
        log_sheet = self.get_skill_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, skill_name, note])

    # ✅ 스틸 훔치는 기본값 계산
    def get_steal_base(self) -> int:
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
        return base

    # ✅ 명령어: 스틸
    @app_commands.command(
        name="스틸",
        description="도적 전용 스킬: 다른 유저의 경험치를 훔칩니다. (쿨타임 4시간)"
    )
    async def 스틸(self, interaction: discord.Interaction, target: discord.Member):
        user_id = str(interaction.user.id)
        target_id = str(target.id)

        # ⚡ 먼저 응답 예약
        await interaction.response.defer()

        if user_id == target_id:
            await interaction.followup.send("❌ 자신을 스틸할 수는 없습니다!", ephemeral=True)
            return

        # 최근 사용 기록 확인 (쿨타임 4시간)
        last_used = self.get_last_skill_time(user_id, "스틸")
        if last_used and datetime.now() < last_used + timedelta(hours=4):
            remain = (last_used + timedelta(hours=4)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(
                f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요.", ephemeral=True
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
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.", ephemeral=True)
            return
        if not target_row:
            await interaction.followup.send("⚠️ 대상 유저의 데이터가 없습니다.", ephemeral=True)
            return

        user_idx, user_data = user_row
        target_idx, target_data = target_row
        job = user_data.get("직업", "백수")
        level = safe_int(user_data.get("레벨", 1))

        if job not in ["도적", "암살자", "카피닌자", "의적"]:
            await interaction.followup.send("❌ 도적 계열만 사용할 수 있는 스킬입니다!", ephemeral=True)
            return

        # ✅ 훔칠 양 계산
        base = self.get_steal_base()

        if base <= 0:
            # 실패 처리
            self.log_skill_use(user_id, interaction.user.name, "스틸", f"실패 (대상: {target.name})")
            await interaction.followup.send(
                f"🥷 {interaction.user.name} 님이 {target.mention} 님을 스틸하려 했지만 실패했습니다…"
            )
            return
        steal_amount = base + level

        # ✅ 반격 체크
        counter_msg = check_counter(user_id, interaction.user.name, target_id, target.mention, steal_amount)
        if counter_msg:
            # 반격 발동 → 대상 exp 변화 없음, 시전자 exp 감소
            new_user_exp = safe_int(user_data.get("현재레벨경험치", 0)) - steal_amount
            sheet.update_cell(user_idx, 11, new_user_exp)
            self.log_skill_use(user_id, interaction.user.name, "스틸", f"반격 당함 -{steal_amount} exp")
            await interaction.followup.send(
                f"🥷 {interaction.user.name}님이 {target.mention} 님을 스틸하려 했으나...\n"
                f"{counter_msg}"
            )
            return

        # -------- 직업별 분기 ---------------
        if job == "도적":
            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - steal_amount
            new_user_exp   = safe_int(user_data.get("현재레벨경험치", 0)) + steal_amount
            sheet.update_cell(target_idx, 11, new_target_exp)
            sheet.update_cell(user_idx, 11, new_user_exp)

            self.log_skill_use(
                user_id, interaction.user.name, "스틸",
                f"대상: {target.name}, {steal_amount} 잃음 / 자신: {steal_amount} 획득"
            )

            await interaction.followup.send(
                f"🥷 {interaction.user.name}님이 {target.mention} 님의 {steal_amount} exp를 스틸하였습니다!\n"
                f"💀 {target.name} -{steal_amount} exp"
            )
            return

        elif job == "카피닌자":
            copied_amount = int(steal_amount * 0.7)
            log_sheet = self.get_skill_log_sheet()
            logs = log_sheet.get_all_records()
            recent_skill = "알 수 없음"
            for row in reversed(logs):
                if str(row.get("유저 ID", "")) == target_id:
                    recent_skill = row.get("스킬명", "알 수 없음")
                    break

            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - copied_amount
            new_user_exp   = safe_int(user_data.get("현재레벨경험치", 0)) + copied_amount
            sheet.update_cell(target_idx, 11, new_target_exp)
            sheet.update_cell(user_idx, 11, new_user_exp)

            self.log_skill_use(
                user_id, interaction.user.name, "스틸",
                f"대상: {target.name}, {copied_amount} 잃음 / 자신: {copied_amount} 획득"
            )

            target_job = target_data.get("직업", "백수")
            if target_job in ["도적", "암살자", "의적", "카피닌자"]:
                await interaction.followup.send(
                    f"🥷 {interaction.user.name}님이 {target.mention} 님의 {copied_amount} exp를 스틸하였습니다!\n"
                    f"⚠️ 카피닌자도 도적 계열 스킬은 훔치지 못한다..."
                )
            else:
                save_copied_skill(user_id, recent_skill)
                await interaction.followup.send(
                    f"🥷 {interaction.user.name}님이 {target.mention} 님의 {copied_amount} exp를 스틸하였습니다!\n"
                    f"💀 카피닌자! {interaction.user.name}님이 스킬 **{recent_skill}**을 복사했습니다!"
                )

        elif job == "의적":
            total = steal_amount
            self_gain = total // 2
            share_pool = total - self_gain

            candidates = [
                (idx, row) for idx, row in enumerate(records, start=2)
                if safe_int(row.get("레벨", 1)) >= 5
                and str(row.get("유저 ID", "")) not in (user_id, target_id)
            ]
            chosen = random.sample(candidates, k=min(len(candidates), random.randint(1, 4))) if candidates else []

            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - total
            new_user_exp   = safe_int(user_data.get("현재레벨경험치", 0)) + self_gain
            sheet.update_cell(target_idx, 11, new_target_exp)
            sheet.update_cell(user_idx, 11, new_user_exp)

            self.log_skill_use(
                user_id, interaction.user.name, "스틸",
                f"대상: {target.name}, {steal_amount} 잃음 / 자신: {self_gain} 획득"
            )

            msg = (
                f"🥷 {interaction.user.name}님이 {target.mention} 님의 {total} exp를 스틸하였습니다!\n"
                f"➡️ 본인: +{self_gain} exp"
            )

            if chosen:
                share_each = share_pool // len(chosen)
                msg += "\n📦 의적이 경험치를 나눕니다! 분배 대상:"
                for rand_idx, rand_data in chosen:
                    rand_new_exp = safe_int(rand_data.get("현재레벨경험치", 0)) + share_each
                    sheet.update_cell(rand_idx, 11, rand_new_exp)
                    nickname = rand_data.get("닉네임", "???")
                    msg += f"\n   • {nickname}: +{share_each} exp"
            else:
                msg += f"\n(분배 대상 없음, {share_pool} exp 소멸)"

            await interaction.followup.send(msg)

        elif job == "암살자":
            total = steal_amount
            logs = [f"🗡️ 암살자 스틸 성공! {target.mention} → -{steal_amount} exp"]

            if random.random() <= 0.3:
                total += steal_amount
                logs.append(f"⚡ 연속 스틸! 추가로 -{steal_amount} exp")

            new_target_exp = safe_int(target_data.get("현재레벨경험치", 0)) - total
            new_user_exp   = safe_int(user_data.get("현재레벨경험치", 0)) + total
            sheet.update_cell(target_idx, 11, new_target_exp)
            sheet.update_cell(user_idx, 11, new_user_exp)

            self.log_skill_use(
                user_id, interaction.user.name, "스틸",
                f"대상: {target.name}, {total} 잃음 / 자신: {total} 획득"
            )

            msg = "\n".join(logs)
            await interaction.followup.send(msg)


async def setup(bot):
    await bot.add_cog(Steal(bot))
