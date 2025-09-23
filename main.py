# ✅ 캐시를 구글시트에 합산 저장
async def sync_cache_to_sheet():
    try:
        sheet = get_sheet()
        now = datetime.now()
        year, month = now.year, now.month

        records = sheet.get_all_records()
        # {user_id (str): (row_num, current_total_messages, current_nickname, mentions, links, images,
        #                  current_super, reels, current_level, current_inlevel_exp, current_job, current_gold)}
        existing_data = {}

        # 기존 사용자 데이터 저장
        for idx, row in enumerate(records, start=2):  # 헤더 제외, 2행부터 시작
            user_id_from_sheet = str(row.get("유저 ID", "")).strip()
            if not user_id_from_sheet.isdigit():
                continue

            try:
                total_messages = safe_int(row.get("누적메시지수", 0))
                mentions = safe_int(row.get("멘션수", 0))
                links = safe_int(row.get("링크수", 0))
                images = safe_int(row.get("이미지수", 0))
                current_super = safe_int(row.get("초특급미녀", 0))  # H
                reels = safe_int(row.get("릴스", 0))               # I
                current_nickname = str(row.get("닉네임", "")).strip()
                current_level = safe_int(row.get("레벨", 1))       # J
                current_inlevel_exp = safe_float(row.get("현재레벨경험치", 0))  # K
                current_job = row.get("직업", "백수")              # L
                current_gold = safe_int(row.get("골드", 0))        # M

                existing_data[user_id_from_sheet] = (
                    idx, total_messages, current_nickname,
                    mentions, links, images,
                    current_super, reels,
                    current_level, current_inlevel_exp,
                    current_job, current_gold
                )
            except Exception as e:
                print(f"❗ Google 시트 레코드 처리 중 오류 (행 {idx}, ID {user_id_from_sheet}): {e}")
                traceback.print_exc()
                continue

        update_data = []
        new_users_to_append = []
        keys_to_delete_from_message_log = []

        for key, value in list(message_log.items()):
            user_id, y, m = key.split('-')
            if int(y) != year or int(m) != month:
                continue

            total_messages_from_cache = value["total"]
            stats_from_detail_log = detail_log.get(key, {})
            mention_from_cache = stats_from_detail_log.get("mention", 0)
            link_from_cache = stats_from_detail_log.get("link", 0)
            image_from_cache = stats_from_detail_log.get("image", 0)

            special_key = f"{user_id}-{year}-{month}"
            reels_from_cache = channel_special_log.get(special_key, 0)

            try:
                user_obj = await bot.fetch_user(int(user_id))
            except Exception:
                continue

            if user_id in existing_data:
                (row_num, current_total_messages, current_nickname_from_sheet,
                 current_mentions, current_links, current_images,
                 current_super, current_reels,
                 current_level, current_inlevel_exp,
                 current_job, current_gold) = existing_data[user_id]

                # 닉네임 변경 시 업데이트
                if current_nickname_from_sheet != user_obj.name:
                    update_data.append({"range": f"B{row_num}", "values": [[user_obj.name]]})

                # 값 합산
                new_total_messages = current_total_messages + total_messages_from_cache
                new_mentions = current_mentions + mention_from_cache
                new_links = current_links + link_from_cache
                new_images = current_images + image_from_cache
                new_reels = current_reels + reels_from_cache

                new_level = current_level
                new_inlevel_exp = current_inlevel_exp + total_messages_from_cache

                # 레벨업 체크
                while new_level < 100 and new_inlevel_exp >= exp_needed_for_next_level(new_level):
                    need = exp_needed_for_next_level(new_level)
                    new_inlevel_exp -= need
                    new_level += 1
                    await bot.get_channel(CHANNEL_ID).send(
                        f"🎉 <@{user_id}> 님이 **레벨 {new_level}** 달성!"
                    )
                    if new_level == 5:
                        await bot.get_channel(CHANNEL_ID).send(
                            f"⚔️ <@{user_id}> 님, 이제 `/전직` 명령어를 이용해 전직할 수 있어요!"
                        )

                # 업데이트 목록
                update_data.extend([
                    {"range": f"C{row_num}", "values": [[new_total_messages]]},
                    {"range": f"D{row_num}", "values": [[new_mentions]]},
                    {"range": f"E{row_num}", "values": [[new_links]]},
                    {"range": f"F{row_num}", "values": [[new_images]]},
                    {"range": f"I{row_num}", "values": [[new_reels]]},      # 릴스
                    {"range": f"J{row_num}", "values": [[new_level]]},     # 레벨
                    {"range": f"K{row_num}", "values": [[new_inlevel_exp]]} # 경험치
                ])
                user_levels[user_id] = new_level

            else:
                # 신규 유저 추가
                exp = total_messages_from_cache
                level = 1
                inlevel_exp = exp

                new_users_to_append.append([
                    user_id,
                    user_obj.name,
                    exp,                # C 누적메시지수
                    mention_from_cache, # D 멘션수
                    link_from_cache,    # E 링크수
                    image_from_cache,   # F 이미지수
                    "",                 # G 공백
                    0,                  # H 초특급미녀
                    reels_from_cache,   # I 릴스
                    level,              # J 레벨
                    inlevel_exp,        # K 경험치
                    "백수",             # L 직업
                    0                   # M 골드
                ])

            keys_to_delete_from_message_log.append(key)
            if key in detail_log: del detail_log[key]
            if special_key in channel_special_log: del channel_special_log[special_key]

        # 캐시 삭제
        for key_to_del in keys_to_delete_from_message_log:
            if key_to_del in message_log:
                del message_log[key_to_del]
        save_data(message_log)

        # 시트 반영
        if new_users_to_append:
            sheet.append_rows(new_users_to_append, value_input_option="USER_ENTERED")
            print(f"✅ {len(new_users_to_append)}명 신규 유저 추가됨.")
        if update_data:
            sheet.batch_update(update_data, value_input_option="USER_ENTERED")
            print(f"✅ {len(update_data)}건 업데이트됨.")

    except Exception as e:
        print(f"❗ sync_cache_to_sheet 에러: {e}")
        traceback.print_exc()
