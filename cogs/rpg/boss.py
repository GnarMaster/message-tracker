import random
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import os
from utils import get_sheet, safe_int

# ✅ 보스 전용 채널 ID (환경변수에서 불러오기)
BOSS_CHANNEL_ID = int(os.getenv("BOSS_CHANNEL_ID", 0))

# ✅ 보스 등장 멘트 리스트
BOSS_INTRO_MESSAGES = [
    "🌩️ 어둠 속에서 {name}(이)가다가온다...",
    "💀 죽음의 기운이 감돌며 {name}(이)가 나타난다!",
    "🌋 용암이 끓어오르며 {name}(이)가 깨어난다!",
    "🌪️ 폭풍이 몰아치며 {name}(이)가 형체를 이룬다!",
    "🌌 차원의 균열이 열리며 {name}(이)가 걸어나온다!",
    "☠️ 이 땅에 재앙이 깃든다... {name}(이)가 등장했다!",
    "❓ 얘가 왜 보스임 ❓ {name} 입갤 ㅋㅋ",
    "🔥Boom! {name}🔥"
]

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

    # ✅ Boss_History 시트 가져오기
    def get_history_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Boss_History")
        except:
            ws = sheet.add_worksheet(title="Boss_History", rows=1000, cols=10)
            ws.append_row(["보스이름", "HP_MAX", "소환일시", "처치일시",
               "막타ID", "막타닉네임",
               "1등ID", "1등닉네임",
               "2등ID", "2등닉네임",
               "3등ID", "3등닉네임",
               "기타참여자수"])
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

        await interaction.response.defer(ephemeral=True)

        if interaction.channel.id != BOSS_CHANNEL_ID:
            await interaction.followup.send("❌ 보스는 전용 채널에서만 소환 가능합니다!", ephemeral=True)
            return

        boss_sheet = self.get_boss_sheet()
        if self.get_current_boss():
            await interaction.followup.send("⚠️ 이미 보스가 소환되어 있습니다!", ephemeral=True)
            return

        hp = random.randint(600, 3000)
        boss_sheet.update(
            "A2:H2",
            [[name, hp, hp, 200, 50, "", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]
        )

        intro_template = random.choice(BOSS_INTRO_MESSAGES)
        intro = intro_template.format(name=name)
        await interaction.delete_original_response()
        await interaction.followup.send(
            f"{intro}\n"
            f"☠️ 보스 **{name}** 등장!\n"
            f"❤️ HP: ???\n"
            f"🎁 보상: 막타 200 EXP | 🥇 1등 150 | 🥈 2등 125 | 🥉 3등 100 | 🙌 참가자 50"
        )

    # ✅ 보스 공격
    @app_commands.command(name="보스공격", description="현재 보스를 공격합니다. (쿨타임 2시간)")
    async def 보스공격(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if interaction.channel.id != BOSS_CHANNEL_ID:
            await interaction.followup.send("❌ 보스는 전용 채널에서만 공격 가능합니다!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        username = interaction.user.name
        boss = self.get_current_boss()

        if not boss:
            await interaction.followup.send("⚠️ 현재 소환된 보스가 없습니다.", ephemeral=True)
            return

        last_used = self.get_last_attack_time(user_id)
        if last_used and datetime.now() < last_used + timedelta(hours=2):
            remain = (last_used + timedelta(hours=2)) - datetime.now()
            minutes = remain.seconds // 60
            await interaction.followup.send(f"⏳ 아직 쿨타임입니다! {minutes}분 뒤 가능", ephemeral=True)
            return

        sheet = get_sheet()
        records = sheet.get_all_records()
        user_row = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
                break
        if not user_row:
            await interaction.followup.send("⚠️ 당신의 데이터가 없습니다.", ephemeral=True)
            return

        job = user_row[1].get("직업", "백수")
        level = safe_int(user_row[1].get("레벨", 1))

        dmg, detail_log, header_msg = self.calc_damage(job, level, interaction.user)

        boss_sheet = self.get_boss_sheet()
        hp_now = safe_int(boss.get("HP_NOW", 0)) - dmg
        boss_sheet.update_cell(2, 3, hp_now)
        boss_sheet.update_cell(2, 6, user_id)

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

        await interaction.delete_original_response()
        if hp_now <= 0:
            # ✅ 막타 공격 로그 먼저 출력
            await interaction.followup.send(
                f"{header_msg}\n{detail_log}\n👉 총합: {dmg} 피해\n💀 보스의 HP가 0이 되었습니다!"
            )
            # ✅ 보상 정산 출력
            await self.reward_boss(interaction, attack_dict, user_id, boss)
        else:
            await interaction.followup.send(
                f"{header_msg}\n{detail_log}\n👉 총합: {dmg} 피해\n남은 HP: ???"
            )

    # ✅ 직업별 데미지 계산
    def calc_damage(self, job: str, level: int, user: discord.Member):
        logs = []
        total_damage = 0
        header_msg = ""
        # (중략: calc_damage 로직은 동일)
        # ...
        return total_damage, "\n".join(logs), header_msg

    # ✅ 보스 보상 처리
    async def reward_boss(self, interaction: discord.Interaction, attack_dict: dict, last_attacker: str, boss: dict):
        sheet = get_sheet(); records = sheet.get_all_records()
        boss_name = boss.get("보스이름","???")
        ranking = sorted(attack_dict.items(), key=lambda x:-x[1])
        # ✅ 보상표 (EXP, GOLD)
        reward_table = {
            "last_hit": (100, 100),
            "1st": (75, 75),
            "2nd": (60, 60),
            "3rd": (50, 50),
            "participant": (25, 25)
        }
        
        rewards = {}
        if len(ranking) >= 1:
            rewards[ranking[0][0]] = reward_table["1st"]
        if len(ranking) >= 2:
            rewards[ranking[1][0]] = reward_table["2nd"]
        if len(ranking) >= 3:
            rewards[ranking[2][0]] = reward_table["3rd"]

        # 막타 보상 추가
        if last_attacker in rewards:
            exp, gold = rewards[last_attacker]
            le, lg = reward_table["last_hit"]
            rewards[last_attacker] = (exp + le, gold + lg)
        else:
            rewards[last_attacker] = reward_table["last_hit"]

        # 기타 참여자
        for uid in attack_dict:
            if uid not in rewards:
                rewards[uid] = reward_table["participant"]

        # ✅ 시트 업데이트
        for idx, row in enumerate(records, start=2):
            uid = str(row.get("유저 ID", ""))
            if uid in rewards:
                exp, gold = rewards[uid]
                current_exp = safe_int(row.get("현재레벨경험치", 0))
                current_gold = safe_int(row.get("골드", 0))
                new_exp = current_exp + exp
                new_gold = current_gold + gold
                sheet.update_cell(idx, 11, new_exp)  # 경험치
                sheet.update_cell(idx, 13, new_gold) # 골드

        # 보스 시트 초기화
        self.get_boss_sheet().update_cell(2,3,0)

        # 히스토리 기록 (생략: 기존 코드 동일)

        # ✅ 출력 메시지 (순서 정리됨)
        msg = f"🎉 보스 **{boss_name}** 쓰러짐!\n\n🏆 누적 데미지 랭킹:\n"
        medals = ["🥇", "🥈", "🥉"]
        exp_list = [75, 60, 50]
        gold_list = [75, 60, 50]
        for i, (uid, dmg) in enumerate(ranking[:3]):
            msg += f"{medals[i]} <@{uid}> ({dmg} 피해) → +{exp_list[i]} EXP, +{gold_list[i]} GOLD\n"

        # 막타
        msg += f"\n⚔️ 막타: <@{last_attacker}> → +100 EXP, +100 GOLD\n"
        # 기타 참여자
        msg += "🙌 기타 참여자 전원 → +25 EXP, +25 GOLD"

        await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(Boss(bot))
