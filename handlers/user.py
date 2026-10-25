import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command

import config
from database import Database
from keyboards.inline import (
    get_main_menu_kb,
    get_filter_menu_kb,
    get_genre_filter_kb,
    get_country_filter_kb,
    get_language_filter_kb,
    get_year_filter_kb,
    get_movie_action_kb,
    get_movie_poster_kb,
    get_movie_not_found_kb,
    get_mandatory_channels_kb
)
from handlers.subscription import check_user_access

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.via_bot)
async def on_via_bot_message(message: Message):
    # Ignore inline-sent messages so the bot never attempts to search them as text
    return

def format_movie_caption(movie: dict, channel_tag: str = None) -> str:
    """Format movie post with all details"""
    lang = movie.get("language") or "O'zbek"
    quality = movie.get("quality") or "1080p"
    genre = movie.get("genre") or "Boshqa"
    country = movie.get("country") or "AQSH"
    year = movie.get("year") or 2024
    views = movie.get("views", 0)
    tag = channel_tag or f"@{config.BOT_USERNAME}"
    if not tag.startswith("@") and not tag.startswith("http"):
        tag = f"@{tag}"
    return (
        f"🎬 <b>Kino nomi:</b> {movie['title']}\n\n"
        f"⚡️ <b>Sifati:</b> {quality}\n"
        f"🌐 <b>Tili:</b> {lang}\n"
        f"🎭 <b>Janri:</b> {genre}\n"
        f"📅 <b>Yili:</b> {year} | 🌍 <b>Davlati:</b> {country}\n\n"
        f"Ko'proq kinolar: {tag}\n\n"
        f"🔒 <b>Kod:</b> {movie['code']}\n"
        f"👁 <b>Jami ko'rishlar:</b> {views} ta"
    )

@router.message(CommandStart())
async def on_start(message: Message, bot: Bot, db: Database):
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)

    # Check if user has access (Mandatory subscription or Premium)
    has_access, missing = await check_user_access(bot, db, user.id)
    if not has_access:
        sub_text = (
            "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
            "<i>(Eslatma: Premium foydalanuvchilar kanallarga a'zo bo'lmasdan to'g'ridan-to'g'ri foydalana oladi)</i>"
        )
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    # Deep-link parameter (e.g. /start watch_5555 or /start save_5555 or /start 5555)
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if param.startswith("watch_"):
            code = param.replace("watch_", "").strip()
            await send_movie_video_directly(message, bot, db, code)
            return
        elif param.startswith("save_"):
            code = param.replace("save_", "").strip()
            await handle_deep_link_save(message, bot, db, code)
            return
        elif param.isdigit():
            # User opened t.me/bot?start=5555 directly -> Send video immediately!
            await send_movie_video_directly(message, bot, db, param)
            return

    settings = await db.get_all_settings()
    greeting = settings.get("start_text") or (
        "👋 <b>Assalomu alaykum , botimizga xush kelibsiz</b>\n\n"
        "🎬 Bot orqali siz sevimli filmlar, seriallar va multfilmlarni sifatli formatda ko'rishingiz mumkin\n\n"
        "🚀 <b>Shunchaki:</b>\n"
        "— Kino yoki serialning kodini yuboring\n"
        "— Pastdagi bo'limlardan birini tanlang va zavqlaning! 😉"
    )
    await message.answer(greeting, reply_markup=get_main_menu_kb(settings), parse_mode="HTML")

@router.message(Command("search"))
async def cmd_search(message: Message, bot: Bot, db: Database):
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)
    has_access, missing = await check_user_access(bot, db, user.id)
    if not has_access:
        sub_text = "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Film qidirish (Inline)", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
    ])
    await message.answer(
        "🔍 <b>Film qidirish:</b>\n\n"
        "• Film nomini yoki uning kodini chatga yozib yuboring (masalan: <code>Qasoskorlar</code> yoki <code>5555</code>)\n"
        "• Yoki pastdagi <b>'🔍 Film qidirish'</b> tugmasini bosib to'g'ridan-to'g'ri qidiring!",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(Command("top"))
async def cmd_top(message: Message, bot: Bot, db: Database):
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)
    has_access, missing = await check_user_access(bot, db, user.id)
    if not has_access:
        sub_text = "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    top_movies = await db.get_top_movies(limit=10)
    if not top_movies:
        await message.answer("🎬 Hozircha filmlar mavjud emas.")
        return

    msg = "🎬 <b>Eng sara va eng ko'p ko'rilgan TOP-10 filmlar:</b>\n\n"
    buttons = []
    for idx, m in enumerate(top_movies, 1):
        msg += f"<b>{idx}. {m['title']}</b>\n— Kod: <code>{m['code']}</code> | 👁 {m.get('views', 0)} ta ko'rish\n\n"
        buttons.append([InlineKeyboardButton(text=f"🎬 {idx}. {m['title']}", callback_data=f"open_movie_code:{m['code']}")])

    buttons.append([
        InlineKeyboardButton(text="🎬 Inline orqali ko'rish", switch_inline_query_current_chat="top_films"),
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
    ])
    msg += "💡 <i>Filmni ochish uchun quyidagi tugmalardan birini bosing:</i>"
    await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.message(Command("saved"))
async def cmd_saved(message: Message, bot: Bot, db: Database):
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)
    has_access, missing = await check_user_access(bot, db, user.id)
    if not has_access:
        sub_text = "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    saved_movies = await db.get_user_saved_movies(user.id, limit=20)
    if not saved_movies:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Film qidirish", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
        ])
        await message.answer(
            "⭐ <b>Sizda saqlangan filmlar ro'yxati hozircha bo'sh.</b>\n\n"
            "Istalgan kinoni ko'rish vaqtida <b>⭐ Saqlash</b> tugmasini bosib shu yerga qo'shishingiz mumkin!",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    msg = f"⭐ <b>Siz saqlagan filmlar (Jami: {len(saved_movies)} ta):</b>\n\n"
    buttons = []
    for idx, m in enumerate(saved_movies[:10], 1):
        msg += f"<b>{idx}. {m['title']}</b> (Kod: <code>{m['code']}</code>)\n"
        buttons.append([InlineKeyboardButton(text=f"🎬 {idx}. {m['title']}", callback_data=f"open_movie_code:{m['code']}")])

    buttons.append([
        InlineKeyboardButton(text="⭐ Inline orqali ochish", switch_inline_query_current_chat="saved_films"),
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
    ])
    msg += "\n💡 <i>Filmni ochish uchun tugmani bosing:</i>"
    await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

async def send_movie_video_directly(message: Message, bot: Bot, db: Database, code: str):
    user_id = message.from_user.id
    has_access, missing = await check_user_access(bot, db, user_id)
    if not has_access:
        sub_text = "⚠️ <b>Kinoni tomosha qilish uchun avval homiy kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    movie = await db.get_movie_by_code(code)
    if not movie:
        await message.answer(
            f"❌ <b>#{code}</b> kodli kino topilmadi. Kodni to'g'ri kiritganingizga ishonch hosil qiling.",
            reply_markup=get_movie_not_found_kb(),
            parse_mode="HTML"
        )
        return

    await db.increment_movie_views(movie["id"])
    movie["views"] = movie.get("views", 0) + 1

    is_saved = await db.is_movie_saved(user_id, movie["id"])
    action_kb = get_movie_action_kb(movie["id"], movie["code"], is_saved=is_saved)

    video_caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"⚡️ <b>Sifati:</b> {movie.get('quality', '1080p')} | 🔒 <b>Kodi:</b> <code>{movie['code']}</code>\n\n"
        f"🍿 <i>Maroqli tomosha tilaymiz!</i>"
    )

    try:
        if movie.get("file_type") == "video":
            await bot.send_video(chat_id=message.chat.id, video=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
        elif movie.get("file_type") == "photo":
            await bot.send_photo(chat_id=message.chat.id, photo=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=message.chat.id, document=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending movie {movie['id']}: {e}")
        await message.answer(f"❌ Kinoni yuklashda xatolik yuz berdi: {e}", reply_markup=get_movie_not_found_kb())

async def send_movie_poster(message: Message, bot: Bot, db: Database, code: str):
    user_id = message.from_user.id
    has_access, missing = await check_user_access(bot, db, user_id)
    if not has_access:
        sub_text = "⚠️ <b>Kinoni ko'rish uchun avval homiy kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    movie = await db.get_movie_by_code(code)
    if not movie:
        await message.answer(
            f"❌ <b>#{code}</b> kodli kino topilmadi. Kodni to'g'ri kiritganingizga ishonch hosil qiling.",
            reply_markup=get_movie_not_found_kb(),
            parse_mode="HTML"
        )
        return

    # Increment view counter
    await db.increment_movie_views(movie["id"])
    movie["views"] = movie.get("views", 0) + 1

    channel_tag = await db.get_setting("movie_channel", f"@{config.BOT_USERNAME}")
    caption = format_movie_caption(movie, channel_tag=channel_tag)
    is_saved = await db.is_movie_saved(user_id, movie["id"])

    # If movie has a poster (obloshka), send the poster first with [🎬 Kinoni ko'rish] button
    poster_id = movie.get("poster_file_id")
    if poster_id:
        poster_kb = get_movie_poster_kb(movie["id"], movie["code"], is_saved=is_saved)
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=poster_id,
                caption=caption,
                reply_markup=poster_kb,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning(f"Could not send poster photo: {e}")

    # Fallback if no poster: send the video directly
    action_kb = get_movie_action_kb(movie["id"], movie["code"], is_saved=is_saved)
    video_caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"⚡️ <b>Sifati:</b> {movie.get('quality', '1080p')} | 🔒 <b>Kodi:</b> <code>{movie['code']}</code>\n\n"
        f"🍿 <i>Maroqli tomosha tilaymiz!</i>"
    )
    try:
        if movie.get("file_type") == "video":
            await bot.send_video(chat_id=message.chat.id, video=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
        elif movie.get("file_type") == "photo":
            await bot.send_photo(chat_id=message.chat.id, photo=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=message.chat.id, document=movie["file_id"], caption=video_caption, reply_markup=action_kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending movie {movie['id']}: {e}")
        await message.answer(f"❌ Kinoni yuklashda xatolik yuz berdi: {e}")

async def handle_deep_link_save(message: Message, bot: Bot, db: Database, code: str):
    user_id = message.from_user.id
    has_access, missing = await check_user_access(bot, db, user_id)
    if not has_access:
        sub_text = "⚠️ <b>Kinoni saqlash uchun avval homiy kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    movie = await db.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ <b>#{code}</b> kodli kino topilmadi.", reply_markup=get_movie_not_found_kb(), parse_mode="HTML")
        return

    is_saved = await db.is_movie_saved(user_id, movie["id"])
    if not is_saved:
        await db.toggle_save_movie(user_id, movie["id"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinoni ko'rish", callback_data=f"watch_movie:{movie['id']}")],
        [
            InlineKeyboardButton(text="⭐ Saqlanganlar", switch_inline_query_current_chat="saved_films"),
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ]
    ])
    caption = (
        f"⭐ <b>'{movie['title']}'</b> kinoni saqlanganlar ro'yxatiga qo'shildi!\n\n"
        f"🍿 <i>Kinoni tomosha qilish uchun pastdagi tugmani bosing:</i>"
    )
    poster_id = movie.get("poster_file_id")
    if poster_id:
        try:
            await bot.send_photo(chat_id=message.chat.id, photo=poster_id, caption=caption, reply_markup=kb, parse_mode="HTML")
            return
        except Exception as e:
            logger.warning(f"Error sending photo in handle_deep_link_save: {e}")
    await message.answer(caption, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("watch_movie:"))
async def on_watch_movie(callback: CallbackQuery, bot: Bot, db: Database):
    user_id = callback.from_user.id
    has_access, missing = await check_user_access(bot, db, user_id)
    if not has_access:
        sub_text = "⚠️ <b>Kinoni tomosha qilish uchun avval homiy kanallarga a'zo bo'ling:</b>"
        await callback.message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        await callback.answer()
        return

    movie_id = int(callback.data.split(":")[1])
    movie = await db.get_movie_by_id(movie_id)
    if not movie:
        await callback.answer("Kino topilmadi!", show_alert=True)
        return

    # Increment view counter
    await db.increment_movie_views(movie["id"])
    movie["views"] = movie.get("views", 0) + 1

    is_saved = await db.is_movie_saved(user_id, movie["id"])
    kb = get_movie_action_kb(movie["id"], movie["code"], is_saved=is_saved)
    video_caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"⚡️ Sifati: {movie.get('quality', '1080p')} | 🔒 Kodi: <code>{movie['code']}</code>\n\n"
        f"🍿 <i>Maroqli tomosha tilaymiz!</i>"
    )

    try:
        if movie.get("file_type") == "video":
            await bot.send_video(
                chat_id=callback.message.chat.id,
                video=movie["file_id"],
                caption=video_caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
        elif movie.get("file_type") == "photo":
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=movie["file_id"],
                caption=video_caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await bot.send_document(
                chat_id=callback.message.chat.id,
                document=movie["file_id"],
                caption=video_caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
        await callback.answer("🍿 Maroqli tomosha!")
    except Exception as e:
        logger.error(f"Error sending video for movie {movie_id}: {e}")
        await callback.answer("Kinoni yuborishda xatolik yuz berdi.", show_alert=True)

@router.callback_query(F.data.startswith("toggle_save:"))
async def on_toggle_save(callback: CallbackQuery, bot: Bot, db: Database):
    has_access, missing = await check_user_access(bot, db, callback.from_user.id)
    if not has_access:
        await callback.answer("⚠️ Avval homiy kanallarga a'zo bo'ling!", show_alert=True)
        await callback.message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>",
            reply_markup=get_mandatory_channels_kb(missing),
            parse_mode="HTML"
        )
        return

    movie_id = int(callback.data.split(":")[1])
    movie = await db.get_movie_by_id(movie_id)
    if not movie:
        await callback.answer("Kino topilmadi!", show_alert=True)
        return

    is_saved = await db.toggle_save_movie(callback.from_user.id, movie_id)
    if is_saved:
        await callback.answer("⭐ Saqlanganlarga qo'shildi!", show_alert=False)
    else:
        await callback.answer("🗑 Saqlanganlardan o'chirildi!", show_alert=False)

    if movie.get("poster_file_id"):
        new_kb = get_movie_poster_kb(movie_id, movie["code"], is_saved=is_saved)
    else:
        new_kb = get_movie_action_kb(movie_id, movie["code"], is_saved=is_saved)

    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass


@router.callback_query(F.data == "open_filter")
async def on_open_filter(callback: CallbackQuery, bot: Bot, db: Database):
    has_access, missing = await check_user_access(bot, db, callback.from_user.id)
    if not has_access:
        await callback.answer("⚠️ Avval homiy kanallarga a'zo bo'ling!", show_alert=True)
        await callback.message.answer(
            "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>",
            reply_markup=get_mandatory_channels_kb(missing),
            parse_mode="HTML"
        )
        return
    text = "📁 <b>Filterlash uchun kerakli kategoriyani tanlang</b>"
    await callback.message.edit_text(text, reply_markup=get_filter_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "filter_sub:genre")
async def on_filter_genre(callback: CallbackQuery):
    await callback.message.edit_text("🎭 <b>Kerakli janrni tanlang:</b>", reply_markup=get_genre_filter_kb(), parse_mode="HTML")

@router.callback_query(F.data == "filter_sub:country")
async def on_filter_country(callback: CallbackQuery):
    await callback.message.edit_text("🌐 <b>Kerakli davlatni tanlang:</b>", reply_markup=get_country_filter_kb(), parse_mode="HTML")

@router.callback_query(F.data == "filter_sub:lang")
async def on_filter_lang(callback: CallbackQuery):
    await callback.message.edit_text("🚩 <b>Kerakli tilni tanlang:</b>", reply_markup=get_language_filter_kb(), parse_mode="HTML")

@router.callback_query(F.data == "filter_sub:year")
async def on_filter_year(callback: CallbackQuery):
    await callback.message.edit_text("📅 <b>Kerakli yilni tanlang:</b>", reply_markup=get_year_filter_kb(), parse_mode="HTML")

@router.callback_query(F.data == "open_imdb")
async def on_open_imdb(callback: CallbackQuery):
    await callback.answer("🟡 IMDb qidiruv: Shunchaki kinoning nomini chatga yozib yuboring!", show_alert=True)

@router.message(F.text)
async def on_text_message(message: Message, bot: Bot, db: Database):
    if message.via_bot:
        return

    text = message.text.strip()
    if text.startswith("/"):
        return

    # Check if text is a movie code (digits)
    if text.isdigit():
        await send_movie_poster(message, bot, db, text)
        return

    # Otherwise search by title
    user_id = message.from_user.id
    has_access, missing = await check_user_access(bot, db, user_id)
    if not has_access:
        sub_text = "⚠️ <b>Botdan foydalanish uchun homiy kanallarga a'zo bo'ling:</b>"
        await message.answer(sub_text, reply_markup=get_mandatory_channels_kb(missing), parse_mode="HTML")
        return

    results = await db.search_movies(text, limit=10)
    if not results:
        await message.answer(
            f"❌ <b>'{text}'</b> nomli kino topilmadi.\nKino kodini kiritib ko'ring yoki boshqa nom yozing.",
            reply_markup=get_movie_not_found_kb(),
            parse_mode="HTML"
        )
        return

    if len(results) == 1:
        # Send that movie poster directly
        await send_movie_poster(message, bot, db, results[0]["code"])
    else:
        # List matching movies with clickable buttons
        msg = f"🔍 <b>'{text}'</b> bo'yicha topilgan kinolar:\n\n"
        buttons = []
        for idx, m in enumerate(results, 1):
            msg += f"<b>{idx}. {m['title']}</b>\n— Kod: <code>{m['code']}</code> | 👁 {m.get('views', 0)} ta\n\n"
            buttons.append([InlineKeyboardButton(text=f"🎬 {idx}. {m['title']}", callback_data=f"open_movie_code:{m['code']}")])
        buttons.append([
            InlineKeyboardButton(text="🔍 Qayta qidirish", switch_inline_query_current_chat=""),
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ])
        msg += "💡 <i>Kinoni tanlash uchun quyidagi tugmalardan birini bosing:</i>"
        await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.callback_query(F.data.startswith("open_movie_code:"))
async def on_open_movie_code(callback: CallbackQuery, bot: Bot, db: Database):
    code = callback.data.split(":")[1]
    await send_movie_poster(callback.message, bot, db, code)
    await callback.answer()
