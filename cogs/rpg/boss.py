import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
import os
from utils import get_sheet, safe_int

# ✅ 보스 전용 채널 ID (환경변수에서 불러오기)
BOSS_CHANNEL_ID = int(os.getenv("BOSS_CHANNEL_ID", 0))


class Boss(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ✅ Boss_State 시트 가져오기
    def get_boss_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Boss_State")
        except:
            ws = sheet.add_worksheet(title="Boss_State", rows=100, cols=10)
            ws.append_row(["보스이름", "HP_MAX", "HP_NOW", "보상_막타", "보상_참여", "마지막공격자", "공격자ID", "소환일시"])
            return ws

    # ✅ 현재 보스 상태
    def get_current_boss(self):
        boss_sheet = self.get_boss_sheet()
        records = boss_sheet.get_all_records()
        if not records:
            return None
        boss = records[0]
        if safe_int(boss.get("HP_NOW", 0)) > 0:
            return boss
        return None

    # ✅ 로그 시트
    def get_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Boss_Log")
        except:
            ws = sheet.add_worksheet(title="Boss_Log", rows=1000, cols=5)
            ws.append_row(["사용일시", "유저ID", "닉네임", "행동", "메모"])
            return ws

    def get_last_attack_time(self, user_id: str):
        log_sheet = self.get_log_sheet()
        records = log_sheet.get_all_records()
        for row in reversed(records):
            if str(row.get("유저ID", "")) == user_id and row.get("행동") == "보스공격":
                try:
                    return datetime.strptime(row.get("사용일시"), "%Y-%m-%d %H:%M:%S")
                except:
                    return None
        return None

    def log_attack(self, user_id: str, username: str, dmg: int, note: str = ""):
        log_sheet = self.get_log_sheet()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([now_str, user_id, username, "보스공격", f"{dmg} 피해 {note}"])

    # ✅ 보스 소환
    @app_commands.command(name="보스소환", description="보스를 소환합니다.")
    async def 보스소환(self, interaction: discord.Interaction, name: str):
        # 채널 제한
        if interaction.channel.id != BOSS_CHANNEL_ID:
            await interaction.response.send_message("❌ 보스는 전용 채널에서만 소환 가능합니다!", ephemeral=True)
            return

        boss_sheet = self.get_boss_sheet()
        if self.get_current_boss():
            await interaction.response.send_message("⚠️ 이미 보스가 소환되어 있습니다!", ephemeral=True)
            return

        hp = random.randint(3000, 8000)
        boss_sheet.resize(rows=1)  # 기존 데이터 초기화
        boss_sheet.append_row([name, hp, hp, 200, 50, "", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    
        # ✅ 응답 예약 후 followup 사용
        await interaction.response.defer()
        await interaction.followup.send(
            f"🐉 보스 **{name}** 등장!\nHP: ???\n보상: 막타 200 EXP, 1등 150 / 2등 125 / 3등 100 / 나머지 50"
        )

    
    # ✅ 보스 공격
    @app_commands.command(name="보스공격", description="현재 보스를 공격합니다. (쿨타임 2시간)")
    async def 보스공격(self, interaction: discord.Interaction):
        # 채널 제한
        if interaction.channel.id != BOSS_CHANNEL_ID:
            await interaction.response.send_message("❌ 보스는 전용 채널에서만 공격 가능합니다!", ephemeral=True)
            return

        await interaction.response.defer()  # ✅ 응답 예약

        user_id = str(interaction.user.id)
        username = interaction.user.name
        boss = self.get_current_boss()

        if not boss:
            await interaction.followup.send("⚠️ 현재 소환된 보스가 없습니다.")
            return

        # 쿨타임 확인
        last_used = self.get_last_attack_time(user_id)
        if last_used and datetime.now() < last_used + timedelta(hours=2):
            remain = (last_used + timedelta(hours=2)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(f"⏳ 아직 쿨타임입니다! {minutes}분 뒤 가능")
            return

        # 유저 직업 가져오기
        sheet = get_sheet()
        records = sheet.get_all_records()
        user_row = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
                break
        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.")
            return

        job = user_row[1].get("직업", "백수")
        level = safe_int(user_row[1].get("레벨", 1))

        # 👉 직업별 데미지 계산
        dmg, detail_log, header_msg = self.calc_damage(job, level, interaction.user)

        # ✅ HP 갱신
        boss_sheet = self.get_boss_sheet()
        hp_now = safe_int(boss.get("HP_NOW", 0)) - dmg
        boss_sheet.update_cell(2, 3, hp_now)   # HP_NOW
        boss_sheet.update_cell(2, 6, user_id)  # 마지막 공격자

        # ✅ 공격자 누적데미지 갱신
        attackers = boss.get("공격자ID", "")
        attack_dict = {}
        if attackers:
            for pair in attackers.split(","):
                if ":" in pair:
                    uid, d = pair.split(":")
                    attack_dict[uid] = safe_int(d)
        attack_dict[user_id] = attack_dict.get(user_id, 0) + dmg
        new_attackers = ",".join([f"{uid}:{d}" for uid, d in attack_dict.items()])
        boss_sheet.update_cell(2, 7, new_attackers)

        self.log_attack(user_id, username, dmg, detail_log)

        # ✅ 출력
        if hp_now <= 0:
            await self.reward_boss(interaction, attack_dict, user_id, boss.get("보스이름"))
        else:
            await interaction.followup.send(
                f"{header_msg}\n{detail_log}\n👉 총합: {dmg} 피해\n남은 HP: ???"
            )

    # ✅ 직업별 데미지 계산 (보스용)
    def calc_damage(self, job: str, level: int, user: discord.Member):
        logs = []
        total_damage = 0
        header_msg = ""

        if job == "전사":  # 삼연격
            header_msg = f"⚔️ {user.mention} 님이 보스에게 **삼연격**을 시전했다!"
            chances = [90, 45, 15]
            for i, chance in enumerate(chances, start=1):
                if random.randint(1, 100) <= chance:
                    base = 4 + level
                    if random.randint(1, 100) <= 10:
                        dmg = base * 2
                        logs.append(f"{i}타: 🔥 치명타! ({dmg})")
                    else:
                        dmg = base
                        logs.append(f"{i}타: ✅ 명중 ({dmg})")
                    total_damage += dmg
                else:
                    logs.append(f"{i}타: ❌ 실패")
        elif job == "마법사":  # 체라
            header_msg = f"🔮 {user.mention} 님의 **체인라이트닝** 발동!"
            base = 10 + level
            dmg = base + random.randint(0, level)
            if random.randint(1, 100) <= 10:
                dmg *= 2
                logs.append(f"⚡ 체라: 치명타! ({dmg})")
            else:
                logs.append(f"⚡ 체라: {dmg}")
            total_damage += dmg
        elif job == "궁수":  # 더블샷
            header_msg = f"🏹 {user.mention} 님의 **더블샷** 발동!"
            for i in range(2):
                base = 4 + level
                roll = random.randint(1, 100)
                if roll <= 10:
                    dmg = base * 2
                    logs.append(f"🎯 {i+1}타: 치명타! ({dmg})")
                elif roll <= 90:
                    dmg = base
                    logs.append(f"🎯 {i+1}타: 명중 ({dmg})")
                else:
                    dmg = 0
                    logs.append(f"🎯 {i+1}타: 빗나감")
                total_damage += dmg
        elif job == "도적":  # 스틸
            header_msg = f"🥷 {user.mention} 님이 보스를 **스틸**하였다!"
            base = random.randint(1, 20) + level
            logs.append(f"🥷 스틸: {base} 피해")
            total_damage += base
        elif job == "특수":  # 폭탄
            header_msg = f"💣 {user.mention} 님이 보스에게 **폭탄**을 던졌다!"
            roll = random.uniform(0, 100)
            if roll <= 70:
                dmg = random.randint(15, 25) + level
                logs.append(f"💣 폭탄 명중 ({dmg})")
            elif roll <= 90:
                dmg = random.randint(33, 47) + level
                logs.append(f"💥 강력 폭발 ({dmg})")
            elif roll <= 99:
                dmg = random.randint(55, 90) + level
                logs.append(f"🔥 치명적 폭발 ({dmg})")
            else:
                dmg = 0
                logs.append(f"☠️ 자폭! (데미지 없음)")
            total_damage += dmg
        else:
            header_msg = f"👊 {user.mention} 님의 평타!"
            total_damage = random.randint(10, 30)
            logs.append(f"평타 ({total_damage})")

        return total_damage, "\n".join(logs), header_msg

    # ✅ 보스 보상 처리
    async def reward_boss(self, interaction: discord.Interaction, attack_dict: dict, last_attacker: str, boss_name: str):
        sheet = get_sheet()
        records = sheet.get_all_records()

        # 누적 데미지 랭킹
        ranking = sorted(attack_dict.items(), key=lambda x: -x[1])
        rewards = {}
        if len(ranking) >= 1: rewards[ranking[0][0]] = rewards.get(ranking[0][0], 0) + 150
        if len(ranking) >= 2: rewards[ranking[1][0]] = rewards.get(ranking[1][0], 0) + 125
        if len(ranking) >= 3: rewards[ranking[2][0]] = rewards.get(ranking[2][0], 0) + 100

        # 막타 보상
        rewards[last_attacker] = rewards.get(last_attacker, 0) + 200

        # 기타 참여자 보상
        for uid in attack_dict.keys():
            if uid not in rewards:
                rewards[uid] = 50

        # 경험치 지급
        for idx, row in enumerate(records, start=2):
            uid = str(row.get("유저 ID", ""))
            if uid in rewards:
                exp = safe_int(row.get("현재레벨경험치", 0))
                sheet.update_cell(idx, 11, exp + rewards[uid])

        # 보스 종료
        boss_sheet = self.get_boss_sheet()
        boss_sheet.update_cell(2, 3, 0)  # HP_NOW = 0

        # 출력 메시지
        msg = f"🎉 보스 **{boss_name}** 쓰러짐!\n\n🏆 누적 데미지 랭킹:\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, dmg) in enumerate(ranking[:3]):
            msg += f"{medals[i]} <@{uid}> ({dmg} 피해) +{rewards[uid]} EXP\n"

        msg += f"\n⚔️ 막타: <@{last_attacker}> +200 EXP\n🙌 기타 참여자 전원 +50 EXP"
        await interaction.followup.send(msg)  # ✅ 수정: followup 사용


async def setup(bot):
    await bot.add_cog(Boss(bot))
