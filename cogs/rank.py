import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import traceback
from utils import get_sheet, safe_int
from pytz import timezone

KST = timezone("Asia/Seoul")

class Rank(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 🔹 지난달 랭킹 정산
    async def send_monthly_stats(self):
        try:
            sheet = get_sheet()
            spreadsheet = sheet.spreadsheet
            records = sheet.get_all_records()

            now = datetime.now(KST)
            last_month = now.replace(day=1) - timedelta(days=1)
            year, month = last_month.year, last_month.month

            results = []
            medals = ["🥇", "🥈", "🥉"]

            for row in records:
                try:
                    uid_raw = str(row.get("유저 ID", "0")).strip()
                    uid = int(uid_raw) if uid_raw.isdigit() else 0
                    count = safe_int(row.get("누적메시지수", 0))
                    username = row.get("닉네임", f"(ID:{uid})")
                    results.append((uid, count, username))
                except Exception as e:
                    print(f"❗ 레코드 처리 오류: {e}")
                    continue

            if not results:
                print("⚠️ 정산할 데이터 없음")
                return

            sorted_results = sorted(results, key=lambda x: -x[1])
            channel = self.bot.get_channel(int(self.bot.GENERAL_CHANNEL_ID))
            if not channel:
                print("❗ 정산 채널을 찾을 수 없음")
                return

            # 📝 메시지 랭킹
            msg = f"📊 {year}년 {month}월 시즌 최종 랭킹\n\n"
            msg += "📝 메시지 랭킹 TOP 3\n"
            for i, (uid, count, username) in enumerate(sorted_results[:3], 1):
                msg += f"{i}. {username} - {count}개\n"

            # ⭐ 레벨 랭킹 (추가)
            level_ranking = sorted(
                [(r.get("유저 ID"), safe_int(r.get("레벨", 1)), safe_int(r.get("현재레벨경험치", 0)), r.get("닉네임"))
                 for r in records if str(r.get("유저 ID")).isdigit()],
                key=lambda x: (-x[1], -x[2])
            )
            msg += "\n⭐ 레벨 랭킹 TOP 3\n"
            for i, (uid, level, exp, username) in enumerate(level_ranking[:3], 1):
                msg += f"{i}. {username} - Lv.{level} ({exp} exp)\n"

            prizes = [15000, 10000, 5000]
            msg += "\n🎁 지난 시즌 보상 (상품권)\n"
            for i, (uid, level, exp, username) in enumerate(level_ranking[:3], 1):
                prize = prizes[i-1]
                msg += f"{medals[i-1]} {i}등: @{uid} → {prize:,}원 상품권 지급\n"

            # 안내 멘트
            msg += (
                "\n🎉 1~3등을 축하합니다! 상품은 관리자에 의해 지급됩니다.\n\n"
                "📢 새로운 시즌이 시작되었습니다!\n"
                "레벨과 경험치가 초기화되었으며, 모든 유저는 다시 도전할 수 있습니다.\n"
                "이번 시즌의 챔피언은 누가 될까요? 🔥"
            )

            await channel.send(msg)
            print("✅ 랭킹 메시지 전송 완료")

            # ✅ 백업 시트 생성
            backup_title = f"{year}년 {month}월"
            try:
                for ws in spreadsheet.worksheets():
                    if ws.title == backup_title:
                        spreadsheet.del_worksheet(ws)
                        break
                sheet.duplicate(new_sheet_name=backup_title)
                print(f"✅ 시트 백업 완료: {backup_title}")

                worksheets = spreadsheet.worksheets()
                for i, ws in enumerate(worksheets):
                    if ws.title == backup_title:
                        spreadsheet.reorder_worksheets(
                            worksheets[:i] + worksheets[i+1:] + [ws]
                        )
                        print(f"✅ 백업 시트를 맨 뒤로 이동 완료: {backup_title}")
                        break
            except Exception as e:
                print(f"❗ 백업 시트 작업 실패: {e}")

            # ✅ Sheet1 초기화 (유저 ID, 닉네임, 골드 유지 / 나머지는 0으로)
            header = sheet.row_values(1)
            reset_data = []
            for row in records:
                user_id = row.get("유저 ID", "")
                nickname = row.get("닉네임", "")
                gold = safe_int(row.get("골드", 0))
                new_row = []
                for col_name in header:
                    if col_name == "유저 ID":
                        new_row.append(user_id)
                    elif col_name == "닉네임":
                        new_row.append(nickname)
                    elif col_name == "골드":
                        new_row.append(gold)
                    elif col_name == "직업":
                        new_row.append("백수")
                    else:
                        new_row.append(0)
                reset_data.append(new_row)

            sheet.resize(rows=1)
            sheet.append_row(header)
            sheet.append_rows(reset_data)
            print("✅ Sheet1 초기화 완료")

        except Exception as e:
            print("❗ send_monthly_stats 에러:", e)
            traceback.print_exc()

    # 🔹 /랭킹정산 명령어
    @app_commands.command(name="랭킹정산", description="이번 달 메시지 랭킹을 수동으로 정산합니다. (관리자 전용)")
    async def 랭킹정산(self, interaction: discord.Interaction):
        admin_id = 648091499887591424  # 👉 본인 ID

        if interaction.user.id != admin_id:
            await interaction.response.send_message("❌ 이 명령어는 관리자만 실행할 수 있습니다.", ephemeral=True)
            return

        print(f"📌 [/랭킹정산] 실행 by {interaction.user.id}")
        await interaction.response.defer()  # ✅ interaction 만료 방지
        try:
            await self.send_monthly_stats()
            await interaction.followup.send("✅ 랭킹 정산이 완료되었습니다!")
        except Exception as e:
            print("❌ 랭킹정산 실행 중 오류:", e)
            traceback.print_exc()
            await interaction.followup.send("⚠️ 랭킹 정산 중 오류 발생")

async def setup(bot: commands.Bot):
    await bot.add_cog(Rank(bot))
