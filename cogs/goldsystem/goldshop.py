import discord
from discord.ext import commands
from discord import app_commands
from utils import get_sheet, safe_int
from inventory_utils import add_item
import random

# 🛒 상점 아이템 리스트 
SHOP_ITEMS = [
    {"name": "직업변경권", "price": 200, "desc": "직업을 변경할 수 있는 특별한 권한"},
    {"name": "5천원 상품권", "price": 5000, "desc": "관리자가 직접 지급하는 리워드"},
    {"name": "경험치 구매권", "price": 100, "desc": "50~100 랜덤 EXP를 획득합니다"}
]


def get_item_by_name(name: str):
    for item in SHOP_ITEMS:
        if item["name"] == name:
            return item
    return None


class ShopSelect(discord.ui.Select):
    def __init__(self, user_id, row_idx, user_data):
        self.user_id = user_id
        self.row_idx = row_idx
        self.user_data = user_data

        options = [
            discord.SelectOption(
                label=item["name"],
                description=f"{item['price']} 골드 | {item['desc']}"
            )
            for item in SHOP_ITEMS
        ]
        super().__init__(placeholder="구매할 아이템을 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if str(interaction.user.id) != self.user_id:
            await interaction.followup.send("❌ 본인만 이용할 수 있습니다.", ephemeral=True)
            return

        selected_item = get_item_by_name(self.values[0])
        if not selected_item:
            await interaction.followup.send("⚠️ 알 수 없는 아이템입니다.", ephemeral=True)
            return

        sheet = get_sheet()
        current_gold = safe_int(self.user_data.get("골드", 0))

        # ✅ 골드 부족 체크
        if current_gold < selected_item["price"]:
            await interaction.followup.send("💰 골드가 부족합니다.", ephemeral=True)
            return

        new_gold = current_gold - selected_item["price"]
        sheet.update_cell(self.row_idx, 13, new_gold)  # 13번째 열이 '골드'

        if selected_item["name"] == "경험치 구매권":
            gained_exp = random.randint(50, 100)
            current_exp = safe_int(self.user_data.get("현재레벨경험치", 0))
            new_exp = current_exp + gained_exp
            sheet.update_cell(self.row_idx, 11, new_exp)

            await interaction.followup.send(
                f"✨ 경험치 구매권 사용 완료!\n"
                f"⭐ {gained_exp} EXP 획득!\n"
                f"📊 현재 경험치: {new_exp}\n"
                f"💰 남은 골드: {new_gold}",
                ephemeral=True
            )
        else:
            # ✅ 인벤토리에 추가
            add_item(self.user_id, interaction.user.name, selected_item["name"], 1)

            await interaction.followup.send(
                f"✅ {selected_item['name']} 구매 완료!\n"
                f"💰 남은 골드: {new_gold}\n"
                f"🎒 아이템이 인벤토리에 추가되었습니다.",
                ephemeral=True
            )


class ShopView(discord.ui.View):
    def __init__(self, user_id, row_idx, user_data):
        super().__init__(timeout=30)
        self.add_item(ShopSelect(user_id, row_idx, user_data))


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="골드상점", description="골드로 아이템을 구매할 수 있는 상점을 엽니다")
    async def 골드상점(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sheet = get_sheet()
        records = sheet.get_all_records()

        user_id = str(interaction.user.id)
        user_row = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID")) == user_id:
                user_row = (idx, row)
                break

        if not user_row:
            await interaction.followup.send("⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.", ephemeral=True)
            return

        row_idx, user_data = user_row
        view = ShopView(user_id, row_idx, user_data)
        await interaction.followup.send("🛒 골드상점에 오신 것을 환영합니다!", view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Shop(bot))
