@discord.ui.button(label="뽑기 돌리기 🎰", style=discord.ButtonStyle.green, custom_id="gacha_button")
async def gacha_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    user_id = str(interaction.user.id)
    username = interaction.user.name

    try:
        # Interaction 즉시 응답 (thinking=True → "처리 중" 표시)
        await interaction.response.defer(thinking=True, ephemeral=False)

        # "뽑는 중..." 메시지 보내기
        loading_msg = await interaction.followup.send("🎰 뽑는 중...")

        # === 시트 업데이트 & 뽑기 로직 ===
        sheet = get_sheet()
        records = sheet.get_all_records()

        user_row = None
        for idx, row in enumerate(records, start=2):
            if str(row.get("유저 ID", "")) == user_id:
                user_row = (idx, row)
                break

        if not user_row:
            await loading_msg.edit(content="⚠️ 데이터가 없습니다. 먼저 메시지를 쳐서 등록하세요.")
            return

        row_idx, user_data = user_row
        current_gold = safe_int(user_data.get("골드", 0))

        if current_gold < 10:
            await loading_msg.edit(content="💰 골드가 부족합니다! (최소 10 필요)")
            return

        new_gold = current_gold - 10

        rewards = [1, 5, 10, 20, 50, 100]
        weights = [30, 30, 20, 15, 4, 1]  # 총합 100
        reward = random.choices(rewards, weights=weights, k=1)[0]

        new_gold += reward
        sheet.update_cell(row_idx, 13, new_gold)  # M열 = 골드

        embed = discord.Embed(
            title="🎰 뽑기 결과!",
            description=f"{username} 님이 뽑기를 돌렸습니다!",
            color=discord.Color.gold()
        )
        embed.add_field(name="차감", value="-10 골드", inline=True)
        embed.add_field(name="보상", value=f"+{reward} 골드", inline=True)
        embed.add_field(name="보유 골드", value=f"{new_gold} 골드", inline=False)
        embed.set_footer(text="⏳ 이 메시지는 5분 뒤 자동 삭제됩니다.")

        # 결과 메시지 보내기
        await interaction.followup.send(embed=embed, delete_after=300)

        # "뽑는 중..." 메시지는 지우기
        await loading_msg.delete()

    except Exception as e:
        print(f"❗ 뽑기 버튼 에러: {e}")
        try:
            await interaction.followup.send("⚠️ 오류가 발생했습니다.", ephemeral=True)
        except:
            pass
