import discord
from discord.ext import commands
from datetime import datetime
from utils import get_sheet, safe_int

class VoiceExp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {user_id: {"start": datetime, "stream_start": datetime|None, "stream_total": int}}
        self.voice_sessions = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        user_id = str(member.id)

        # 🎧 음성 채널 입장
        if before.channel is None and after.channel is not None:
            self.voice_sessions[user_id] = {
                "start": datetime.now(),
                "stream_start": None,
                "stream_total": 0
            }

        # 📺 화면공유 시작
        elif before.self_stream is False and after.self_stream is True:
            if user_id in self.voice_sessions:
                self.voice_sessions[user_id]["stream_start"] = datetime.now()

        # 📺 화면공유 종료
        elif before.self_stream is True and after.self_stream is False:
            if user_id in self.voice_sessions and self.voice_sessions[user_id]["stream_start"]:
                start = self.voice_sessions[user_id]["stream_start"]
                self.voice_sessions[user_id]["stream_total"] += (datetime.now() - start).seconds // 60
                self.voice_sessions[user_id]["stream_start"] = None

        # 🚪 음성 채널 퇴장
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_sessions:
                session = self.voice_sessions.pop(user_id)
                minutes = (datetime.now() - session["start"]).seconds // 60

                # 아직 켜져있는 화면공유 있으면 반영
                if session["stream_start"]:
                    session["stream_total"] += (datetime.now() - session["stream_start"]).seconds // 60

                # ✅ EXP 계산 (10분 단위 floor)
                voice_blocks = minutes // 10
                stream_blocks = session["stream_total"] // 10
                voice_exp = voice_blocks * 20
                stream_exp = stream_blocks * 30
                total_exp = voice_exp + stream_exp

                # 📊 Voice_Log 시트 기록
                sheet = get_sheet().spreadsheet
                try:
                    ws = sheet.worksheet("Voice_Log")
                except:
                    ws = sheet.add_worksheet(title="Voice_Log", rows=1000, cols=7)
                    ws.append_row(["유저 ID","닉네임","입장시간","퇴장시간","음성시간(분)","화면공유시간(분)","지급 EXP"])
                ws.append_row([
                    user_id,
                    member.name,
                    session["start"].strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    minutes,
                    session["stream_total"],
                    total_exp
                ])

                # 💾 메인 시트 경험치 업데이트 (sheet1, K열 = 현재레벨경험치)
                if total_exp > 0:
                    main_sheet = sheet.sheet1
                    records = main_sheet.get_all_records()
                    for idx, row in enumerate(records, start=2):
                        if str(row.get("유저 ID")) == user_id:
                            new_exp = safe_int(row.get("현재레벨경험치", 0)) + total_exp
                            main_sheet.update_cell(idx, 11, new_exp)  # 11번 열 = K열
                            break

                    # 📢 기본 채널 알림 (5분 뒤 자동 삭제, 멘션 ❌)
                    if member.guild.system_channel:
                        await member.guild.system_channel.send(
                            f"🎧 {member.name} 님이 음성채널 {minutes}분, "
                            f"화면공유 {session['stream_total']}분 참여 → +{total_exp} exp",
                            delete_after=300
                        )

async def setup(bot):
    await bot.add_cog(VoiceExp(bot))
