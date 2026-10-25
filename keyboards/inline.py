from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional, List, Dict, Any

def get_main_menu_kb(buttons: dict = None) -> InlineKeyboardMarkup:
    """Main menu keyboard without IMDb and with dynamic button texts"""
    b = buttons or {}
    t_obuna = b.get("btn_obuna", "💎 Obuna")
    t_top = b.get("btn_top", "🎬 Top Filmlar")
    t_filter = b.get("btn_filter", "📁 Filter")
    t_saved = b.get("btn_saved", "⭐ Saqlangan")
    t_search = b.get("btn_search", "🔍 Film qidirish")

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t_obuna, callback_data="open_subscription"),
            InlineKeyboardButton(text=t_top, switch_inline_query_current_chat="top_films")
        ],
        [
            InlineKeyboardButton(text=t_filter, callback_data="open_filter"),
            InlineKeyboardButton(text=t_saved, switch_inline_query_current_chat="saved_films")
        ],
        [
            InlineKeyboardButton(text=t_search, switch_inline_query_current_chat="")
        ]
    ])

def get_subscription_kb(back_callback: str = "back_to_main") -> InlineKeyboardMarkup:
    """Subscription / Premium tariffs matching screenshot 2"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 oy - 15 000 UZS", callback_data="buy_plan:1_month")],
        [InlineKeyboardButton(text="3 oy - 40 000 UZS", callback_data="buy_plan:3_month")],
        [InlineKeyboardButton(text="6 oy - 75 000 UZS", callback_data="buy_plan:6_month")],
        [InlineKeyboardButton(text="12 oy - 140 000 UZS", callback_data="buy_plan:12_month")],
        [InlineKeyboardButton(text="🎁 Bepul olish", callback_data="get_free_sub")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data=back_callback)]
    ])

def get_pending_order_kb(order_id: int) -> InlineKeyboardMarkup:
    """Keyboard when user has a pending order matching screenshot 1"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Arizam holati", callback_data=f"view_my_order:{order_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_main")]
    ])

def get_order_status_kb(order_id: int) -> InlineKeyboardMarkup:
    """Keyboard inside order status details matching screenshot 2"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Arizani bekor qilish", callback_data=f"cancel_my_order:{order_id}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="open_subscription")]
    ])

def get_filter_menu_kb() -> InlineKeyboardMarkup:
    """Filter categories matching screenshot 4"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Davlat", callback_data="filter_sub:country"),
            InlineKeyboardButton(text="🚩 Til", callback_data="filter_sub:lang")
        ],
        [
            InlineKeyboardButton(text="🎭 Janr", callback_data="filter_sub:genre"),
            InlineKeyboardButton(text="📅 Yil", callback_data="filter_sub:year")
        ],
        [
            InlineKeyboardButton(text="⬅️ Ortga", callback_data="back_to_main")
        ]
    ])

def get_genre_filter_kb() -> InlineKeyboardMarkup:
    """Genres list triggering inline query genre:name"""
    genres = [
        "Jangari", "Sarguzasht", "Komediya", "Drama",
        "Fantastika", "Qo'rqinchli", "Multfilm", "Melodrama",
        "Triller", "Kriminal", "Tarixiy", "Oilaviy"
    ]
    buttons = []
    row = []
    for g in genres:
        row.append(InlineKeyboardButton(text=f"🎭 {g}", switch_inline_query_current_chat=f"genre:{g.lower()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="open_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_country_filter_kb() -> InlineKeyboardMarkup:
    """Countries list triggering inline query country:name"""
    countries = ["AQSH", "Turkiya", "Koreya", "Rossiya", "Hindiston", "O'zbekiston", "Buyuk Britaniya", "Fransiya"]
    buttons = []
    row = []
    for c in countries:
        row.append(InlineKeyboardButton(text=f"🌐 {c}", switch_inline_query_current_chat=f"country:{c.lower()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="open_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_language_filter_kb() -> InlineKeyboardMarkup:
    """Languages list triggering inline query lang:name"""
    langs = ["O'zbek", "Rus", "Ingliz", "Subtitr"]
    buttons = []
    row = []
    for l in langs:
        row.append(InlineKeyboardButton(text=f"🚩 {l}", switch_inline_query_current_chat=f"lang:{l.lower()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="open_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_year_filter_kb() -> InlineKeyboardMarkup:
    """Years list triggering inline query year:name"""
    years = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2015"]
    buttons = []
    row = []
    for y in years:
        row.append(InlineKeyboardButton(text=f"📅 {y}", switch_inline_query_current_chat=f"year:{y}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="open_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_movie_poster_kb(movie_id: int, movie_code: str, is_saved: bool = False) -> InlineKeyboardMarkup:
    """Actions under movie poster: Watch, Save, Share, Search, Main Menu"""
    save_text = "❌ Saqlangandan o'chirish" if is_saved else "⭐ Saqlash"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Kinoni ko'rish", callback_data=f"watch_movie:{movie_id}")
        ],
        [
            InlineKeyboardButton(text=save_text, callback_data=f"toggle_save:{movie_id}"),
            InlineKeyboardButton(text="🔄 Ulashish", switch_inline_query=f"{movie_code}")
        ],
        [
            InlineKeyboardButton(text="🔍 Film qidirish", switch_inline_query_current_chat=""),
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ]
    ])

def get_movie_action_kb(movie_id: int, movie_code: str, is_saved: bool = False) -> InlineKeyboardMarkup:
    """Actions under a movie: Save/Unsave, Share, Search, Main Menu"""
    save_text = "❌ Saqlangandan o'chirish" if is_saved else "⭐ Saqlash"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=save_text, callback_data=f"toggle_save:{movie_id}"),
            InlineKeyboardButton(text="🔄 Ulashish", switch_inline_query=f"{movie_code}")
        ],
        [
            InlineKeyboardButton(text="🔍 Boshqa film qidirish", switch_inline_query_current_chat=""),
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ]
    ])

def get_movie_not_found_kb() -> InlineKeyboardMarkup:
    """Navigation keyboard when movie is not found"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Film qidirish", switch_inline_query_current_chat=""),
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ]
    ])


def get_mandatory_channels_kb(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Keyboard prompting user to join channels and verify"""
    keyboard = []
    for idx, ch in enumerate(channels, 1):
        keyboard.append([
            InlineKeyboardButton(text=f"📢 {idx}-kanalga a'zo bo'lish", url=ch["url"])
        ])
    keyboard.append([
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_review_kb(order_id: int) -> InlineKeyboardMarkup:
    """Admin group buttons for approving or rejecting receipt"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"order_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Rad qilish", callback_data=f"order_reject:{order_id}")
        ]
    ])

def get_confirm_movie_kb() -> InlineKeyboardMarkup:
    """Confirm movie wizard step"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, saqlash", callback_data="movie_confirm_save"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="movie_cancel")
        ]
    ])

def get_admin_main_kb(is_owner: bool = False) -> InlineKeyboardMarkup:
    """Admin panel main keyboard with strict role separation"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="admin_add_movie")
        ],
        [
            InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="admin_delete_movie"),
            InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin_list_movies")
        ],
        [
            InlineKeyboardButton(text="📢 Majburiy kanallar", callback_data="admin_channels"),
            InlineKeyboardButton(text="📢 Reklama tarqatish", callback_data="admin_broadcast")
        ]
    ]
    if is_owner:
        buttons.extend([
            [
                InlineKeyboardButton(text="👥 Adminlar boshqaruvi", callback_data="admin_manage_admins"),
                InlineKeyboardButton(text="💎 Premium a'zolar", callback_data="admin_premium_users")
            ],
            [
                InlineKeyboardButton(text="💳 Karta sozlash", callback_data="admin_card_settings"),
                InlineKeyboardButton(text="⚙️ Matn & Tugmalar", callback_data="admin_settings_menu")
            ],
            [
                InlineKeyboardButton(text="👑 Egalikni o'tkazish (Transfer Owner)", callback_data="admin_transfer_owner")
            ]
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_premium_users_kb(users: List[Dict[str, Any]], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """List active premium users with revoke button"""
    buttons = []
    start = page * per_page
    end = start + per_page
    current_page_users = users[start:end]

    for u in current_page_users:
        name = u.get("full_name") or u.get("username") or str(u["user_id"])
        buttons.append([
            InlineKeyboardButton(text=f"❌ Obunani olish: {name[:18]}", callback_data=f"revoke_prem_confirm:{u['user_id']}")
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"prem_users_page:{page - 1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"prem_users_page:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="🔍 ID orqali qidirish", callback_data="find_user_prem_prompt"),
        InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_revoke_kb(user_id: int) -> InlineKeyboardMarkup:
    """Confirm revoking premium subscription"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Ha, obunani tortib olish", callback_data=f"do_revoke_prem:{user_id}"),
            InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_premium_users")
        ]
    ])


def get_admin_settings_kb() -> InlineKeyboardMarkup:
    """Settings menu for editing bot texts and buttons"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Janrlar ro'yxati (Sozlash)", callback_data="admin_manage_genres")],
        [InlineKeyboardButton(text="🚩 Tillar ro'yxati (Sozlash)", callback_data="admin_manage_langs")],
        [InlineKeyboardButton(text="📝 Start xabari matni", callback_data="edit_setting:start_text")],
        [InlineKeyboardButton(text="💎 Obuna xabari matni", callback_data="edit_setting:premium_text")],
        [InlineKeyboardButton(text="📢 Kanal/Reklama tegi (postlarda)", callback_data="edit_setting:movie_channel")],
        [InlineKeyboardButton(text="🔘 Asosiy menyu tugmalari", callback_data="admin_edit_buttons_menu")],
        [InlineKeyboardButton(text="🔄 Barcha sozlamalarni tiklash (Reset)", callback_data="reset_all_settings")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")]
    ])

def get_edit_buttons_kb() -> InlineKeyboardMarkup:
    """Submenu for customizing main menu buttons"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 'Obuna' tugmasi", callback_data="edit_setting:btn_obuna")],
        [InlineKeyboardButton(text="🎬 'Top Filmlar' tugmasi", callback_data="edit_setting:btn_top")],
        [InlineKeyboardButton(text="📁 'Filter' tugmasi", callback_data="edit_setting:btn_filter")],
        [InlineKeyboardButton(text="⭐ 'Saqlangan' tugmasi", callback_data="edit_setting:btn_saved")],
        [InlineKeyboardButton(text="🔍 'Film qidirish' tugmasi", callback_data="edit_setting:btn_search")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_settings_menu")]
    ])

def get_genre_selector_kb(all_genres: List[str], selected: List[str]) -> InlineKeyboardMarkup:
    """Keyboard for selecting multiple genres with checkmarks"""
    keyboard = []
    row = []
    for g in all_genres:
        is_sel = g in selected
        txt = f"✅ {g}" if is_sel else g
        row.append(InlineKeyboardButton(text=txt, callback_data=f"toggle_wz_genre:{g}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    done_text = f"✅ Tanlandi ({len(selected)}) · Davom etish ➡️" if selected else "➡️ O'tkazib yuborish"
    keyboard.append([InlineKeyboardButton(text=done_text, callback_data="done_wz_genre")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_lang_selector_kb(all_langs: List[str], selected: List[str]) -> InlineKeyboardMarkup:
    """Keyboard for selecting languages with checkmarks"""
    keyboard = []
    row = []
    for l in all_langs:
        is_sel = l in selected
        txt = f"✅ {l}" if is_sel else l
        row.append(InlineKeyboardButton(text=txt, callback_data=f"toggle_wz_lang:{l}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    done_text = f"✅ Tanlandi ({len(selected)}) · Davom etish ➡️" if selected else "➡️ O'tkazib yuborish"
    keyboard.append([InlineKeyboardButton(text=done_text, callback_data="done_wz_lang")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_country_selector_kb() -> InlineKeyboardMarkup:
    """Quick country selector buttons"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇸 AQSH", callback_data="set_wz_country:AQSH"),
            InlineKeyboardButton(text="🇹🇷 Turkiya", callback_data="set_wz_country:Turkiya")
        ],
        [
            InlineKeyboardButton(text="🇰🇷 Koreya", callback_data="set_wz_country:Koreya"),
            InlineKeyboardButton(text="🇷🇺 Rossiya", callback_data="set_wz_country:Rossiya")
        ],
        [
            InlineKeyboardButton(text="🇮🇳 Hindiston", callback_data="set_wz_country:Hindiston"),
            InlineKeyboardButton(text="🇺🇿 O'zbekiston", callback_data="set_wz_country:O'zbekiston")
        ],
        [
            InlineKeyboardButton(text="🇬🇧 Buyuk Britaniya", callback_data="set_wz_country:Buyuk Britaniya"),
            InlineKeyboardButton(text="🇫🇷 Fransiya", callback_data="set_wz_country:Fransiya")
        ],
        [
            InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")
        ]
    ])

def get_quality_selector_kb() -> InlineKeyboardMarkup:
    """Quick quality selector buttons"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="4K Ultra HD", callback_data="set_wz_quality:4K Ultra HD"),
            InlineKeyboardButton(text="1080p Full HD", callback_data="set_wz_quality:1080p")
        ],
        [
            InlineKeyboardButton(text="720p HD", callback_data="set_wz_quality:720p"),
            InlineKeyboardButton(text="480p", callback_data="set_wz_quality:480p")
        ],
        [
            InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")
        ]
    ])

def get_manage_genres_kb(genres: List[str]) -> InlineKeyboardMarkup:
    """Admin keyboard for adding/deleting genres"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Yangi janr qo'shish", callback_data="admin_add_genre_prompt")]
    ]
    row = []
    for g in genres:
        row.append(InlineKeyboardButton(text=f"🗑 {g}", callback_data=f"del_genre:{g}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⬅️ Sozlamalar", callback_data="admin_settings_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_manage_langs_kb(langs: List[str]) -> InlineKeyboardMarkup:
    """Admin keyboard for adding/deleting languages"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Yangi til qo'shish", callback_data="admin_add_lang_prompt")]
    ]
    row = []
    for l in langs:
        row.append(InlineKeyboardButton(text=f"🗑 {l}", callback_data=f"del_lang:{l}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⬅️ Sozlamalar", callback_data="admin_settings_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


