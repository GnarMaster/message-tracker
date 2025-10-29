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
    "⚡ 하늘이 갈라지고 천둥이 울려퍼진다...",
    "🌩️ 어둠 속에서 거대한 기운이 다가온다...",
    "💀 죽음의 기운이 감돌며 보스가 나타난다!",
    "🌋 용암이 끓어오르며 괴물이 깨어난다!",
    "🌪️ 폭풍이 몰아치며 그림자가 형체를 이룬다!",
    "🌌 차원의 균열이 열리며 괴물이 걸어나온다!",
    "☠️ 이 땅에 재앙이 깃든다... 보스가 등장했다!",
    "❓ 얘가 왜 보스임 ❓"
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
            ws.append_row(["보스이름", "HP_MAX", "HP_NOW", "보상_막타",
                          "보상_참여", "마지막공격자", "공격자ID", "소환일시"])
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
        log_sheet.append_row(
            [now_str, user_id, username, "보스공격", f"{dmg} 피해 {note}"])

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

        intro = random.choice(BOSS_INTRO_MESSAGES)
        await interaction.delete_original_response()
        await interaction.followup.send(
            f"{intro}\n"
            f"☠️ 보스 **{name}** 등장!\n"
            f"❤️ HP: ???\n"
            f"🎁 보상: 막타 100EXP, 100GOLD | 🥇 1등 75EXP, 75GOLD | 🥈 2등 60EXP, 60GOLD | 🥉 3등 50EXP, 50GOLD | 🙌 참가자 25EXP, 25GOLD"
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

        dmg, detail_log, header_msg = self.calc_damage(
            job, level, interaction.user)

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
        new_attackers = ",".join(
            [f"{uid}:{d}" for uid, d in attack_dict.items()])
        boss_sheet.update_cell(2, 7, new_attackers)

        self.log_attack(user_id, username, dmg, detail_log)

        await interaction.delete_original_response()
        if hp_now <= 0:
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
        weapon_atk = 0
        # ✅ 무기 공격력 불러오기
        
        # ⚔️ 전사
        if job in ["전사", "검성", "투신", "검투사"]:
            header_msg = f"⚔️ {user.name} 님이 보스에게 **삼연격**을 시전했다!"
            chances = [90, 60, 30, 15] if job == "검성" else [90, 45, 15]
            for i, chance in enumerate(chances, start=1):
                if random.randint(1, 100) <= chance:
                    dmg = 8+level+weapon_atk
                    if random.randint(1, 100) <= 10:
                        dmg *= 2
                        logs.append(f"{i}타: 🔥 치명타! ({dmg})")
                    else:
                        logs.append(f"{i}타: ✅ 명중 ({dmg})")
                    total_damage += dmg
                else:
                    logs.append(f"{i}타: ❌ 실패")
            if job == "투신":
                bonus = int((8+level)*1.5)
                logs.append(f"⚡ 투신 추가 일격! ({bonus})")
                total_damage += bonus
            if job == "검투사":
                logs.append("🛡️ 검투사 보정: 총 피해 1.5배 적용!")
                total_damage = int(total_damage*1.5)

        # 🔮 마법사
        elif job in ["마법사", "폭뢰술사", "연격마도사"]:
            header_msg = f"🔮 {user.name} 님의 **체인라이트닝** 발동!"
            base = 6+level+weapon_atk
            multiplier, hit, i = 1, True, 1
            while hit and multiplier >= 1/64:
                dmg = max(1, int(base*multiplier))
                if random.randint(1, 100) <= 10:
                    dmg *= 2
                    logs.append(f"{i}타: ⚡ 치명타! ({dmg})")
                else:
                    logs.append(f"{i}타: ⚡ 명중 ({dmg})")
                total_damage += dmg
                if i >= 2:
                    hit = random.random() <= 0.5
                i += 1
                multiplier /= 2
            if job in ["폭뢰술사", "연격마도사"]:
                logs.append("⚡ 2차 전직 보정: 총 피해 1.5배 적용!")
                total_damage = int(total_damage*1.5)

        # 🏹 궁수
        elif job in ["궁수", "저격수", "연사수"]:
            header_msg = f"🏹 {user.name} 님의 **더블샷** 발동!"
            for i in range(2):
                base = 10+level+weapon_atk
                roll = random.randint(1, 100)
                if roll <= 20:
                    dmg = base*2
                    logs.append(f"{i+1}타: 🎯 치명타! ({dmg})")
                    total_damage += dmg
                elif roll <= 90:
                    dmg = base
                    logs.append(f"{i+1}타: 🎯 명중 ({dmg})")
                    total_damage += dmg
                else:
                    logs.append(f"{i+1}타: ❌ 빗나감")
            if job in ["저격수", "연사수"]:
                logs.append("⚡ 2차 전직 보정: 총 피해 1.5배 적용!")
                total_damage = int(total_damage*1.5)

        # 🥷 도적
        elif job in ["도적", "암살자", "의적", "카피닌자"]:
            header_msg = f"🥷 {user.name} 님이 보스를 **스틸**하였다!"
            roll = random.uniform(0, 100)
            if roll <= 80:
                dmg = (random.randint(1, 10)+level+weapon_atk)*2
            elif roll <= 90:
                dmg = 0
            elif roll <= 99:
                dmg = (random.randint(11, 19)+level+weapon_atk)*2
            else:
                jackpot = random.random()
                if jackpot <= 0.001:
                    dmg = 200+level+weapon_atk
                elif jackpot <= 0.005:
                    dmg = 100+level+weapon_atk
                else:
                    dmg = (50+level+weapon_atk)*2
            total_damage += dmg
            logs.append(f"스틸 피해: {dmg}")
            if job == "암살자" and dmg > 0 and random.random() <= 0.3:
                logs.append(f"⚡ 연속 스틸 발동! 추가 {dmg} 피해")
                total_damage += dmg
            if job in ["의적", "카피닌자"]:
                logs.append("📦 특수효과 무효 → 피해 1.5배 적용!")
                total_damage = int(total_damage*1.5)

        # 💣 특수
        elif job in ["특수", "축제광", "파괴광"]:
            header_msg = f"💣 {user.name} 님이 보스에게 **폭탄**을 던졌다!"
            roll = random.uniform(0, 100)
            if roll <= 70:
                dmg = random.randint(20, 30)+level+weapon_atk
                logs.append(f"💣 폭탄 명중 ({dmg})")
            elif roll <= 90:
                dmg = random.randint(45, 60)+level+weapon_atk
                logs.append(f"💥 강력 폭발 ({dmg})")
            elif roll <= 99:
                if random.uniform(0, 100) <= 1:
                    dmg = 300+level+weapon_atk
                    logs.append(f"🌋 전설적 폭발 ({dmg})")
                else:
                    dmg = random.randint(80, 100)+level+weapon_atk
                    logs.append(f"🔥 치명적 폭발 ({dmg})")
            else:
                dmg = 0
                logs.append(f"☠️ 자폭! (데미지 없음)")
            total_damage += dmg
            if job in ["축제광", "파괴광"]:
                logs.append("💥 2차 전직 보정: 총 피해 1.5배 적용!")
                total_damage = int(total_damage*1.5)

        # 👊 기본 평타
        else:
            header_msg = f"👊 {user.name} 님의 평타!"
            total_damage = random.randint(5, 10)
            logs.append(f"평타 ({total_damage})")

        return total_damage, "\n".join(logs), header_msg

    # ✅ 보스 보상 처리
    async def reward_boss(self, interaction: discord.Interaction, attack_dict: dict, last_attacker: str, boss: dict):
        sheet = get_sheet()
        records = sheet.get_all_records()
        boss_name = boss.get("보스이름", "???")
        ranking = sorted(attack_dict.items(), key=lambda x: -x[1])
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
                sheet.update_cell(idx, 13, new_gold)  # 골드

        # 보스 시트 초기화
        self.get_boss_sheet().update_cell(2, 3, 0)

        history = self.get_history_sheet()
        try:
            last_user = await interaction.client.fetch_user(int(last_attacker))
            last_name = last_user.name
        except:
            last_name = "Unknown"
        rank_info = []
        for i in range(3):
            if len(ranking) > i:
                uid = ranking[i][0]
                try:
                    u = await interaction.client.fetch_user(int(uid))
                    uname = u.name
                except:
                    uname = "Unknown"
                rank_info.extend([uid, uname])
            else:
                rank_info.extend(["", ""])
        history.append_row([
            boss_name, boss.get("HP_MAX", 0), boss.get(
                "소환일시", ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_attacker, last_name, rank_info[0], rank_info[1], rank_info[2], rank_info[3], rank_info[4], rank_info[5], max(
                0, len(attack_dict)-3)
        ])

        # ✅ 출력 메시지
        msg = f"\n⚔️ 막타: <@{last_attacker}> → +100 EXP, +100 GOLD\n"

        msg += f"🎉 보스 **{boss_name}** 쓰러짐!\n\n🏆 누적 데미지 랭킹:\n"
        medals = ["🥇", "🥈", "🥉"]
        exp_list = [75, 60, 50]
        gold_list = [75, 60, 50]
        for i, (uid, dmg) in enumerate(ranking[:3]):
            msg += f"{medals[i]} <@{uid}> ({dmg} 피해) → +{exp_list[i]} EXP, +{gold_list[i]} GOLD\n"

        msg += f"🙌 기타 참여자 전원 → +25 EXP, +25 GOLD"

        await interaction.followup.send(msg)


async def setup(bot):
    await bot.add_cog(Boss(bot))
