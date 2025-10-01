import discord
from discord import app_commands
from discord.ext import commands
import random
from utils import get_sheet

def load_menu():
    sheet = get_sheet()
    menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
    menus = menu_sheet.col_values(1)[1:]  # 첫 줄(헤더) 제외
    return menus

class Menu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="점메추", description="오늘의 점심 메뉴를 추천해줘요.")
    async def 점메추(self, interaction: discord.Interaction):
        menu_list = load_menu()
        choice = random.choice(menu_list)
        await interaction.response.send_message(f"🥢 오늘의 점심 추천은... **{choice}**!")

    @app_commands.command(name="저메추", description="오늘의 저녁 메뉴를 추천해줘요.")
    async def 저메추(self, interaction: discord.Interaction):
        menu_list = load_menu()
        choice = random.choice(menu_list)
        await interaction.response.send_message(f"🍽️ 오늘의 저녁 추천은... **{choice}**!")

    @app_commands.command(name="메뉴추가", description="메뉴에 새로운 항목을 추가합니다.")
    async def 메뉴추가(self, interaction: discord.Interaction, menu_name: str):
        await interaction.response.defer()
        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]
        if menu_name in menus:
            await interaction.followup.send(f"❌ 이미 '{menu_name}' 메뉴가 있어요!")
            return
        menu_sheet.append_row([menu_name])
        await interaction.followup.send(f"✅ '{menu_name}' 메뉴가 추가됐어요!")

    @app_commands.command(name="메뉴삭제", description="메뉴에서 항목을 삭제합니다.")
    async def 메뉴삭제(self, interaction: discord.Interaction, menu_name: str):
        await interaction.response.defer()
        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]
        if menu_name not in menus:
            await interaction.followup.send(f"❌ '{menu_name}' 메뉴는 목록에 없어요!")
            return
        index = menus.index(menu_name) + 2
        menu_sheet.delete_rows(index)
        await interaction.followup.send(f"🗑️ '{menu_name}' 메뉴가 삭제됐어요!")

    @app_commands.command(name="메뉴판", description="현재 등록된 메뉴를 보여줍니다.")
    async def 메뉴판(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sheet = get_sheet()
        menu_sheet = sheet.spreadsheet.worksheet("Menu_List")
        menus = menu_sheet.col_values(1)[1:]
        if not menus:
            await interaction.followup.send("📭 등록된 메뉴가 없어요!")
            return
        message = "📋 현재 등록된 메뉴\n\n"
        for idx, menu in enumerate(menus, start=1):
            message += f"{idx}. {menu}\n"
        await interaction.followup.send(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(Menu(bot))
