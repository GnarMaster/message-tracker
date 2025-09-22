# import discord
# from discord.ext import commands
# from datetime import datetime
# from utils import get_sheet, safe_int

# class VoiceExp(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#         self.voice_sessions = {}  # {user_id: 입장시간}

#     def get_or_create_sheet(self, title, headers):
#         sheet = get_sheet().spreadsheet
#         try:
#             ws = sheet.worksheet(title)
#         except:
#             ws = sheet.add_worksheet(title=title, rows=1000, cols=len(headers))
#             ws.append_row(headers)
#         return ws

#     @commands.Cog.listener()
#     async def on_voice_state_update(self, member, before, after):
#         user_id = str(member.id)
#         user_name = member.name

#         # 🎧 음성채널 입장
#         if before.channel is None and after.channel is not None:
#             self.voice_sessions[user_id] = datetime.now()

#             ws_voice = self.get_or_create_sheet(
#                 "Voice_Log",
#                 ["유저 ID","닉네임","입장시간","퇴장시간","음성시간(분)","지급 EXP"]
#             )
#             ws_voice.append_row([
#                 user_id,
#                 user_name,
#                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 "", "", ""
#             ])

#         # 📺 화면공유 시작
#         elif before.self_stream is False and after.self_stream is True:
#             ws_stream = self.get_or_create_sheet(
#                 "Voice_Stream_Log",
#                 ["유저 ID","닉네임","시작시간","종료시간","화면공유시간(분)","지급 EXP"]
#             )
#             ws_stream.append_row([
#                 user_id,
#                 user_name,
#                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 "", "", ""
#             ])

#         # 📺 화면공유 종료
#         elif before.self_stream is True and after.self_stream is False:
#             sheet = get_sheet().spreadsheet
#             ws_stream = self.get_or_create_sheet(
#                 "Voice_Stream_Log",
#                 ["유저 ID","닉네임","시작시간","종료시간","화면공유시간(분)","지급 EXP"]
#             )
#             records = ws_stream.get_all_records()
#             for idx, row in enumerate(reversed(records), start=2):
#                 if str(row["유저 ID"]) == user_id and row["종료시간"] == "":
#                     start_time = datetime.strptime(row["시작시간"], "%Y-%m-%d %H:%M:%S")
#                     minutes = (datetime.now() - start_time).seconds // 60
#                     exp = (minutes // 10) * 30
#                     row_num = len(records) - idx + 2
#                     ws_stream.update(
#                         f"D{row_num}:F{row_num}",
#                         [[datetime.now().strftime("%Y-%m-%d %H:%M:%S"), minutes, exp]]
#                     )
#                     break

#         # 🚪 음성채널 퇴장
#         elif before.channel is not None and after.channel is None:
#             if user_id not in self.voice_sessions:
#                 return

#             join_time = self.voice_sessions.pop(user_id)
#             leave_time = datetime.now()
#             minutes = (leave_time - join_time).seconds // 60
#             voice_exp = (minutes // 10) * 20

#             sheet = get_sheet().spreadsheet

#             # Voice_Log 갱신 (퇴장시간, 음성시간, EXP 한 번에 업데이트)
#             ws_voice = self.get_or_create_sheet(
#                 "Voice_Log",
#                 ["유저 ID","닉네임","입장시간","퇴장시간","음성시간(분)","지급 EXP"]
#             )
#             records = ws_voice.get_all_records()
#             for idx, row in enumerate(reversed(records), start=2):
#                 if str(row["유저 ID"]) == user_id and row["퇴장시간"] == "":
#                     row_num = len(records) - idx + 2
#                     ws_voice.update(
#                         f"D{row_num}:F{row_num}",
#                         [[leave_time.strftime("%Y-%m-%d %H:%M:%S"), minutes, voice_exp]]
#                     )
#                     break

#             # 🎥 Stream 로그 합산 (이번 세션 안의 기록만)
#             ws_stream = self.get_or_create_sheet(
#                 "Voice_Stream_Log",
#                 ["유저 ID","닉네임","시작시간","종료시간","화면공유시간(분)","지급 EXP"]
#             )
#             stream_records = ws_stream.get_all_records()
#             stream_minutes = 0
#             stream_exp = 0
#             for row in stream_records:
#                 if str(row["유저 ID"]) == user_id and row["종료시간"] != "":
#                     start_time = datetime.strptime(row["시작시간"], "%Y-%m-%d %H:%M:%S")
#                     end_time = datetime.strptime(row["종료시간"], "%Y-%m-%d %H:%M:%S")
#                     if start_time >= join_time and end_time <= leave_time:
#                         stream_minutes += safe_int(row["화면공유시간(분)"])
#                         stream_exp += safe_int(row["지급 EXP"])

#             total_exp = voice_exp + stream_exp

#             # 💾 메인 시트 경험치 갱신
#             main_sheet = sheet.sheet1
#             records = main_sheet.get_all_records()
#             for idx, row in enumerate(records, start=2):
#                 if str(row.get("유저 ID")) == user_id:
#                     new_exp = safe_int(row.get("현재레벨경험치", 0)) + total_exp
#                     main_sheet.update_cell(idx, 11, new_exp)  # K열
#                     break

#             # 📢 기본 채널 알림
#             if member.guild.system_channel:
#                 await member.guild.system_channel.send(
#                     f"🎧 {user_name} 님이 음성채널 {minutes}분, "
#                     f"화면공유 {stream_minutes}분 참여 → +{total_exp} exp",
#                     delete_after=300
#                 )

# async def setup(bot):
#     await bot.add_cog(VoiceExp(bot))
