from utils import safe_int, get_sheet

def plus_damage(user_id: str) -> int:
    """
    유저의 레벨(시트1) + 무기공격력(Weapon 시트)을 합산해서 반환
    스킬에서는:
        dmg = BASE
        dmg += plus_damage(user_id)
    이런 식으로 사용
    """
    sheet = get_sheet().spreadsheet

    # ✅ 시트1에서 레벨 가져오기
    try:
        main_ws = sheet.worksheet("시트1")
        records = main_ws.get_all_records()
        level = 1
        for row in records:
            if str(row.get("유저 ID", "")) == str(user_id):
                level = safe_int(row.get("레벨", 1))
                break
    except:
        level = 1

    # ✅ Weapon 시트에서 무기 공격력 가져오기
    try:
        weapon_ws = sheet.worksheet("Weapon")
        records = weapon_ws.get_all_records()
        weapon_atk = 0
        for row in records:
            if str(row.get("유저 ID", "")) == str(user_id):
                weapon_atk = safe_int(row.get("무기공격력", 0))
                break
    except:
        weapon_atk = 0

    return level + weapon_atk
