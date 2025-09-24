from utils import get_sheet, safe_int

def get_inventory_sheet():
    """Inventory 시트 가져오기 (없으면 생성)"""
    sheet = get_sheet().spreadsheet
    try:
        return sheet.worksheet("Inventory")
    except:
        ws = sheet.add_worksheet(title="Inventory", rows=1000, cols=4)
        ws.append_row(["유저 ID", "닉네임", "아이템명", "개수"])
        return ws


def add_item(user_id: str, username: str, item_name: str, amount: int = 1):
    """아이템 추가 (있으면 개수 증가, 없으면 새로 추가)"""
    ws = get_inventory_sheet()
    records = ws.get_all_records()

    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID")) == str(user_id) and row.get("아이템명") == item_name:
            new_cnt = safe_int(row.get("개수", 0)) + amount
            ws.update_cell(idx, 4, new_cnt)
            return
    ws.append_row([user_id, username, item_name, amount])


def use_item(user_id: str, item_name: str, amount: int = 1) -> bool:
    """아이템 사용 (성공하면 True, 없으면 False)"""
    ws = get_inventory_sheet()
    records = ws.get_all_records()

    for idx, row in enumerate(records, start=2):
        if str(row.get("유저 ID")) == str(user_id) and row.get("아이템명") == item_name:
            new_cnt = safe_int(row.get("개수", 0)) - amount
            if new_cnt > 0:
                ws.update_cell(idx, 4, new_cnt)
            else:
                ws.delete_rows(idx)  # 0 이하 → 행 삭제
            return True
    return False


def get_inventory(user_id: str):
    """해당 유저의 인벤토리 반환 → [(아이템명, 개수), ...]"""
    ws = get_inventory_sheet()
    records = ws.get_all_records()
    items = []
    for row in records:
        if str(row.get("유저 ID")) == str(user_id):
            cnt = safe_int(row.get("개수", 0))
            if cnt > 0:
                items.append((row.get("아이템명"), cnt))
    return items
