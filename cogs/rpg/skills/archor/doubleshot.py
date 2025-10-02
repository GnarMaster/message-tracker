import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
import os
from utils import get_sheet, safe_int, get_copied_skill, clear_copied_skill, check_counter
from cogs.rpg.skills.SkillLogic import plus_damage

# PVP 채널 ID 불러오기
PVP_CHANNEL_ID = int(os.getenv("PVP_CHANNEL_ID", 0))

class Archer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_skill_log_sheet(self):
        sheet = get_sheet().spreadsheet
        try:
            return sheet.worksheet("Skill_Log")
        except:
            # 시트가 없으면 새로 생성합니다.
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

    # ⭐ 1. shoot_arrow 함수 수정: 데미지만 계산하고 반환 (시트 업데이트 로직 제거)
    def shoot_arrow(self, target_data, target_obj, is_first: bool, is_sniper: bool, user_id: str):
        base = 10 + plus_damage(user_id)
        crit_chance = 10
        if is_sniper:
            base = 14 + plus_damage(user_id)

        roll = random.randint(1, 100)
        if roll <= crit_chance:
            dmg = base * 2
            msg = f"🔥 치명타! ({dmg})"
        elif roll <= 90:
            dmg = base
            msg = f"✅ 명중! ({dmg})"
        else:
            dmg = 0
            msg = "❌ 빗나감!"

        # ❌ sheet.update_cell 로직 제거

        # ✅ 출력용 이름 처리
        # target_data에 '유저 ID'가 없을 수도 있으므로 safe_int를 통해 안전하게 처리
        target_id_str = str(target_data.get("유저 ID", ""))
        nickname = target_data.get("닉네임") or getattr(target_obj, "name", f"ID:{target_id_str}")
        
        # 첫 번째 공격이거나, target_obj가 멘션 가능한 객체일 때 멘션 사용
        if is_first and hasattr(target_obj, "mention"):
            display_name = target_obj.mention
        else:
            display_name = nickname

        return f"{display_name} → {msg}", dmg


    @app_commands.command(
        name="더블샷",
        description="궁수 전용 스킬: 지정 2명에게 연속 사격 (쿨타임 4시간)"
    )
    async def 더블샷(self, interaction: discord.Interaction, target1: discord.Member, target2: discord.Member = None):
        
        # ✅ PVP 채널 제한
        if interaction.channel.id != PVP_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ 이 명령어는 PVP 채널에서만 사용할 수 있습니다.",
                ephemeral=True
            )
            return
        user_id = str(interaction.user.id)
        username = interaction.user.name

        # ✅ 첫 응답은 비공개로 defer
        await interaction.response.defer(ephemeral=True)

        try:
            # 쿨타임 확인 로직은 그대로 유지합니다.
            last_used = self.get_last_skill_time(user_id, "더블샷")
            if last_used and datetime.now() < last_used + timedelta(hours=4):
                remain = (last_used + timedelta(hours=4)) - datetime.now()
                minutes = remain.seconds // 60
                await interaction.edit_original_response(
                    content=f"⏳ 아직 쿨타임입니다! {minutes}분 뒤에 다시 시도하세요."
                )
                return

            sheet = get_sheet()
            records = sheet.get_all_records()

            user_row, target1_row, target2_row = None, None, None
            candidates = []
            
            # 🎯 타겟 정보 및 시트 행 찾기
            for idx, row in enumerate(records, start=2):
                uid_str = str(row.get("유저 ID", ""))
                if uid_str == user_id:
                    user_row = (idx, row)
                elif uid_str == str(target1.id):
                    target1_row = (idx, row)
                elif target2 and uid_str == str(target2.id):
                    target2_row = (idx, row)
                else:
                    if safe_int(row.get("레벨", 1)) >= 5:
                        candidates.append((idx, row))

            if not user_row or not target1_row:
                await interaction.edit_original_response(content="⚠️ 데이터가 없습니다.")
                return

            job = user_row[1].get("직업", "백수")
            level = safe_int(user_row[1].get("레벨", 1))

            if job not in ["궁수", "저격수", "연사수", "카피닌자"]:
                await interaction.edit_original_response(content="❌ 궁수 계열만 사용할 수 있는 스킬입니다!")
                return

            # ✅ 여기까지 오면 성공 → 비공개 응답 삭제 (혹은 나중에 성공 메시지로 편집)
            # 여기서는 편의상 그대로 delete_original_response()를 유지합니다.
            await interaction.delete_original_response()
            
            # ⭐ 2. 누적 데미지를 저장할 딕셔너리 초기화
            # {유저_ID: [시트_행번호, 데이터_딕셔너리, 누적_데미지_합계, 타겟_객체]}
            targets_info = {}
            target1_id = str(target1.id)
            targets_info[target1_id] = [target1_row[0], target1_row[1], 0, target1]
            
            if target2 and target2_row:
                target2_id = str(target2.id)
                if target2_id not in targets_info:
                    targets_info[target2_id] = [target2_row[0], target2_row[1], 0, target2]
            
            damage_logs, counter_msgs = [], []

            # 🔨 데미지 적용 및 누적 헬퍼 함수
            def apply_shot(target_id: str, is_first_hit: bool, is_sniper: bool = False):
                if target_id not in targets_info: return None, 0

                idx, data, total_dmg, obj = targets_info[target_id]
                
                # 수정된 shoot_arrow 호출 (시트 업데이트 X)
                log_msg_part, dmg = self.shoot_arrow(data, obj, is_first_hit, is_sniper, level) 
                
                # 누적 데미지 업데이트
                targets_info[target_id][2] += dmg 
                
                # 카운터 체크 (데미지가 0이 아니어야 카운터 체크)
                if dmg > 0:
                    cm = check_counter(user_id, username, target_id, obj.mention, dmg)
                    if cm: counter_msgs.append(cm)
                
                return log_msg_part, dmg
            
            # =====================
            # 🔹 직업 분기 (누적 데미지 로직 적용)
            # =====================
            if job == "저격수":
                if target2:
                    await interaction.followup.send("❌ 저격수는 반드시 한 명만 지정해야 합니다!",ephemeral=True)
                    return
                
                result_msg = f"🏹 저격수 {username}님의 더블샷 발동!\n"
                for i in range(2):
                    msg, dmg = apply_shot(target1_id, is_first_hit=(i == 0), is_sniper=True)
                    damage_logs.append(f"🎯 저격 {i+1}타: {msg}")

            elif job == "연사수":
                result_msg = f"🏹 연사수 {username}님의 더블샷 발동!\n"
                
                # 1타 (target1)
                msg, dmg = apply_shot(target1_id, is_first_hit=True)
                damage_logs.append(f"🏹 1타: {msg}")

                # 2타 (target2)
                if target2 and target2_row:
                    msg, dmg = apply_shot(str(target2.id), is_first_hit=True)
                    damage_logs.append(f"🏹 2타: {msg}")

                # 추가 연사 (candidates) - 로직 유지
                if candidates:
                    rand_idx, rand_data = random.choice(candidates)
                    rand_id = str(rand_data.get("유저 ID"))
                    rand_obj = discord.Object(id=int(rand_id))
                    
                    # targets_info에 임시로 추가 (이 공격만 끝나면 사라짐)
                    targets_info[rand_id] = [rand_idx, rand_data, 0, rand_obj] 
                    
                    # apply_shot은 targets_info를 사용하지만, 최종 업데이트 로직이 끝난 후 이 키는 사라지므로 문제 없음
                    msg, dmg = apply_shot(rand_id, is_first_hit=False) 
                    damage_logs.append(f"⚡ 추가 연사: {msg}")

                    # 임시로 추가한 랜덤 대상은 최종 업데이트 전에 제거하는 것이 깔끔함
                    del targets_info[rand_id]


            else:  # 기본 궁수 및 카피닌자
                result_msg = f"🏹 궁수 {username}님의 더블샷 발동!\n"
                
                # 1타 (target1)
                msg, dmg = apply_shot(target1_id, is_first_hit=True)
                damage_logs.append(f"🏹 1타: {msg}")

                # 2타 대상 설정 (target2 없으면 target1)
                target2_id = str(target2.id) if target2 else target1_id
                
                # 2타: target1과 같아도 targets_info에 누적 데미지가 합산됨
                msg, dmg = apply_shot(target2_id, is_first_hit=False) 
                damage_logs.append(f"🏹 2타: {msg}")

            
            # =====================
            # ⭐ 3. 최종 시트 업데이트 ⭐ (모든 공격의 누적 데미지 반영)
            # =====================
            update_cells = []
            
            for target_id, (idx, data, total_dmg, obj) in targets_info.items():
                if total_dmg > 0:
                    # 로드된 데이터의 경험치 값을 사용 (가장 최근 동기화된 값)
                    current_exp = safe_int(data.get("현재레벨경험치", 0)) 
                    new_exp = current_exp - total_dmg
                    
                    # 일괄 업데이트 목록에 추가 (K열은 11번째 컬럼)
                    update_cells.append({
                        "range": f"K{idx}",
                        "values": [[new_exp]]
                    })
                    
            if update_cells:
                # 단일 API 호출로 모든 경험치 변경사항 반영
                sheet.batch_update(update_cells, value_input_option="USER_ENTERED")


            # 로그 기록
            self.log_skill_use(user_id, username, "더블샷", "; ".join(damage_logs))

            result_msg += "\n".join(damage_logs)
            if counter_msgs:
                result_msg += "\n" + "\n".join(counter_msgs)

            await interaction.followup.send(result_msg)

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ 오류 발생: {e}")

async def setup(bot):
    await bot.add_cog(Archer(bot))
