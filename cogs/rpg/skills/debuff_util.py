import random
from utils import get_sheet

# ✅ Buff_Log 시트 접근
def get_buff_log_sheet():
    sheet = get_sheet().spreadsheet
    try:
        return sheet.worksheet("Buff_Log")
    except:
        return sheet.add_worksheet(title="Buff_Log", rows=1000, cols=6)

# ✅ 유저의 효과 리스트 가져오기
def get_effects(user_id: str):
    sheet = get_buff_log_sheet()
    records = sheet.get_all_records()
    return [row.get("상태") for row in records if str(row.get("유저 ID", "")) == str(user_id)]

# ✅ 효과 제거
def remove_effect(user_id: str, effect: str):
    sheet = get_buff_log_sheet()
    records = sheet.get_all_records()
    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID", "")) == str(user_id) and row.get("상태") == effect:
            sheet.delete_rows(idx)
            break

# ────────────────────────────────
# 🔹 시전자 효과 (마비, 저주, 혼란, 광란)
# ────────────────────────────────
def apply_caster_effects(attacker_id: str, target_id: str, records: list):
    """
    스킬 사용 직전에 시전자에게 걸린 효과를 확인/처리.
    return: (최종 target_id, caster_msgs, extra_flags)
    """
    messages = []
    effects = get_effects(attacker_id)

    # 광란 → 자기 자신 공격
    if "광란" in effects:
        target_id = attacker_id
        remove_effect(attacker_id, "광란")
        messages.append("🤪 광란 발동! 자기 자신을 공격합니다.")

    # 혼란 → 무작위 다른 대상 공격
    if "혼란" in effects:
        candidates = [row for row in records if str(row.get("유저 ID")) not in (attacker_id, target_id)]
        if candidates:
            new_target = random.choice(candidates)
            target_id = str(new_target.get("유저 ID"))
            messages.append("😵 혼란 발동! 무작위 대상을 공격합니다.")
        remove_effect(attacker_id, "혼란")

    # 마비는 쿨타임 계산 시점에서 따로 처리 필요
    if "마비" in effects:
        remove_effect(attacker_id, "마비")
        messages.append("⚡ 마비 상태! 이번 스킬은 쿨타임이 2시간 늘어납니다.")
        return target_id, messages, {"paralysis": True}

    return target_id, messages, {}

# ────────────────────────────────
# 🔹 피격자 효과 (반격, 표식)
# ────────────────────────────────
def apply_target_effects(attacker_id: str, target_id: str, damage: int):
    """
    피해 계산 직후, 피격자에게 걸린 효과를 확인/처리.
    return: (최종 damage, target_msgs, extra_penalty_to_attacker)
    """
    messages = []
    penalty_to_attacker = 0
    effects = get_effects(target_id)

    # 표식 → 피해 증가
    if "표식" in effects:
        damage = int(damage * 1.5)
        remove_effect(target_id, "표식")
        messages.append("🎯 표식 효과! 피해가 증가했습니다.")

    # 반격 → 공격자도 같은 피해
    if "반격" in effects:
        penalty_to_attacker += damage
        remove_effect(target_id, "반격")
        messages.append("🛡️ 반격 발동! 공격자가 피해를 입습니다.")

    return damage, messages, penalty_to_attacker

# ────────────────────────────────
# 🔹 저주 (공격 후 처리)
# ────────────────────────────────
def apply_curse(attacker_id: str, damage: int):
    """
    공격 끝난 후, 시전자에게 저주 효과가 있으면 자신도 피해.
    return: (추가 피해량, curse_msgs)
    """
    messages = []
    effects = get_effects(attacker_id)
    penalty = 0

    if "저주" in effects:
        penalty = damage
        remove_effect(attacker_id, "저주")
        messages.append("☠️ 저주 발동! 자신도 같은 피해를 입었습니다.")

    return penalty, messages
