import logging
import random
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramRetryAfter

import config
from database import Database
from keyboards.inline import (
    get_admin_main_kb,
    get_confirm_movie_kb,
    get_admin_settings_kb,
    get_edit_buttons_kb,
    get_genre_selector_kb,
    get_lang_selector_kb,
    get_country_selector_kb,
    get_quality_selector_kb,
    get_manage_genres_kb,
    get_manage_langs_kb
)

import io
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)
router = Router()

async def upload_poster_to_catbox(bot: Bot, poster_file_id: str) -> Optional[str]:
    try:
        f_info = await bot.get_file(poster_file_id)
        if not f_info.file_path:
            return None
        file_bytes = io.BytesIO()
        await bot.download_file(f_info.file_path, file_bytes)
        file_bytes.seek(0)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('fileToUpload', file_bytes.read(), filename='poster.jpg', content_type='image/jpeg')
            async with session.post('https://catbox.moe/user/api.php', data=data, timeout=12) as resp:
                if resp.status == 200:
                    url = (await resp.text()).strip()
                    if url.startswith("http"):
                        logger.info(f"Uploaded poster to Catbox: {url}")
                        return url
    except Exception as e:
        logger.warning(f"Error uploading poster to Catbox: {e}")
    return None

class MovieWizard(StatesGroup):
    waiting_for_media = State()
    waiting_for_poster = State()
    waiting_for_title = State()
    waiting_for_year = State()
    waiting_for_genre = State()
    waiting_for_lang = State()
    waiting_for_country = State()
    waiting_for_quality = State()
    waiting_for_code = State()
    confirm_movie = State()

class DeleteMovieState(StatesGroup):
    waiting_for_code = State()

class AddChannelState(StatesGroup):
    waiting_for_id = State()
    waiting_for_title = State()
    waiting_for_url = State()

class AddAdminState(StatesGroup):
    waiting_for_id = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm_broadcast = State()

class CardSettingState(StatesGroup):
    waiting_for_number = State()
    waiting_for_holder = State()

class AdminSettingState(StatesGroup):
    waiting_for_value = State()

class TransferOwnerState(StatesGroup):
    waiting_for_id = State()

class AddGenreState(StatesGroup):
    waiting_for_name = State()

class AddLangState(StatesGroup):
    waiting_for_name = State()

async def is_authorized_admin(user_id: int, db: Database) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    return await db.is_admin(user_id, extra_admins=config.ADMIN_IDS)

@router.message(Command("admin"))
async def on_admin_cmd(message: Message, db: Database):
    if not await is_authorized_admin(message.from_user.id, db):
        await message.reply("⛔️ Siz admin emassiz!")
        return

    is_owner = (message.from_user.id == await db.get_owner_id())
    text = (
        "👑 <b>Admin Boshqaruv Paneliga xush kelibsiz!</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await message.answer(text, reply_markup=get_admin_main_kb(is_owner=is_owner), parse_mode="HTML")

# ----------------- STATISTIKA -----------------
@router.callback_query(F.data == "admin_stats")
async def on_admin_stats(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    stats = await db.get_stats()
    text = (
        "📊 <b>Bot Statistikasi va Monitoring:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"⚡️ <b>Bugungi faol foydalanuvchilar:</b> {stats['active_today']} ta\n"
        f"💎 <b>Premium foydalanuvchilar:</b> {stats['premium_users']} ta\n"
        f"🎬 <b>Jami kinolar:</b> {stats['total_movies']} ta\n"
        f"👁 <b>Jami ko'rishlar:</b> {stats['total_views']} ta\n\n"
        f"🟢 <b>Bot holati:</b> Online (Ishlamoqda)\n"
        f"💳 <b>Karta:</b> {config.CARD_NUMBER} ({config.CARD_HOLDER})"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_menu")
    ]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_menu")
async def on_back_admin_menu(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    await state.clear()
    is_owner = (callback.from_user.id == await db.get_owner_id())
    text = "👑 <b>Admin Boshqaruv Paneli:</b>"
    await callback.message.edit_text(text, reply_markup=get_admin_main_kb(is_owner=is_owner), parse_mode="HTML")


# ----------------- KINO QO'SHISH (FSM WIZARD) -----------------
@router.callback_query(F.data == "admin_add_movie")
async def on_start_add_movie(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    await state.set_state(MovieWizard.waiting_for_media)
    text = (
        "🎬 <b>Video yoki rasm faylini yuboring:</b>\n\n"
        "<i>Keyin bot sizdan kino uchun nom so'raydi va kod yaratadi.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")
    ]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.message(MovieWizard.waiting_for_media, F.video | F.photo | F.document)
async def on_media_received(message: Message, state: FSMContext):
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        file_id = message.document.file_id
        file_type = "document"

    await state.update_data(file_id=file_id, file_type=file_type)
    await state.set_state(MovieWizard.waiting_for_poster)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ O'tkazib yuborish (Obloshkasiz)", callback_data="skip_poster")
    ]])
    await message.reply(
        "🖼 <b>2️⃣ Kino obloshkasini (poster rasmini) yuboring:</b>\n\n"
        "<i>(Foydalanuvchi kinoni qidirganda yoki tanlaganda birinchi bo'lib shu obloshka chiqadi. Agar obloshkasi bo'lmasa, 'O'tkazib yuborish' tugmasini bosing yoki /skip deb yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(MovieWizard.waiting_for_poster, F.photo)
async def on_poster_received(message: Message, state: FSMContext, bot: Bot):
    poster_file_id = message.photo[-1].file_id
    await state.update_data(poster_file_id=poster_file_id)
    poster_url = await upload_poster_to_catbox(bot, poster_file_id)
    await state.update_data(poster_url=poster_url)
    await state.set_state(MovieWizard.waiting_for_title)
    await message.reply("🎬 <b>3️⃣ Kino nomini kiriting:</b>\n<i>(Masalan: Avatar yoki Dacha)</i>", parse_mode="HTML")

@router.message(MovieWizard.waiting_for_poster, F.text == "/skip")
async def on_poster_skipped_cmd(message: Message, state: FSMContext):
    await state.update_data(poster_file_id=None)
    await state.set_state(MovieWizard.waiting_for_title)
    await message.reply("🎬 <b>3️⃣ Kino nomini kiriting:</b>\n<i>(Masalan: Avatar yoki Dacha)</i>", parse_mode="HTML")

@router.callback_query(MovieWizard.waiting_for_poster, F.data == "skip_poster")
async def on_poster_skipped_btn(callback: CallbackQuery, state: FSMContext):
    await state.update_data(poster_file_id=None)
    await state.set_state(MovieWizard.waiting_for_title)
    await callback.message.edit_text("🎬 <b>3️⃣ Kino nomini kiriting:</b>\n<i>(Masalan: Avatar yoki Dacha)</i>", parse_mode="HTML")


@router.message(MovieWizard.waiting_for_title, F.text)
async def on_title_received(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(MovieWizard.waiting_for_year)
    await message.reply("📅 <b>Kino chiqarilgan yilini kiriting:</b>\n<i>(Masalan: 2024 yoki 2026)</i>", parse_mode="HTML")

@router.message(MovieWizard.waiting_for_year, F.text)
async def on_year_received(message: Message, state: FSMContext, db: Database):
    text_val = message.text.strip()
    year = int(text_val) if text_val.isdigit() else 2024
    await state.update_data(year=year, selected_genres=[])
    await state.set_state(MovieWizard.waiting_for_genre)

    all_genres = await db.get_all_genres()
    kb = get_genre_selector_kb(all_genres, [])
    await message.reply(
        f"📅 Yili: <b>{year}</b>\n\n"
        "🎭 <b>5️⃣ Kino janrini tanlang:</b>\n\n"
        "<i>(Bir nechta janrni tugmalarni bosib ✅ qilib tanlashingiz mumkin, so'ng 'Tanlandi' tugmasini bosing yoki matn yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(MovieWizard.waiting_for_genre, F.data.startswith("toggle_wz_genre:"))
async def on_toggle_wz_genre(callback: CallbackQuery, state: FSMContext, db: Database):
    genre_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected = list(data.get("selected_genres", []))
    if genre_name in selected:
        selected.remove(genre_name)
    else:
        selected.append(genre_name)
    await state.update_data(selected_genres=selected)

    all_genres = await db.get_all_genres()
    kb = get_genre_selector_kb(all_genres, selected)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(MovieWizard.waiting_for_genre, F.data == "done_wz_genre")
async def on_done_wz_genre(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    selected = data.get("selected_genres", [])
    genre_str = ", ".join(selected) if selected else "Boshqa"
    await state.update_data(genre=genre_str, selected_langs=[])

    all_langs = await db.get_all_languages()
    await state.set_state(MovieWizard.waiting_for_lang)
    kb = get_lang_selector_kb(all_langs, [])
    await callback.message.edit_text(
        f"✅ Janr: <b>{genre_str}</b>\n\n"
        "🌐 <b>6️⃣ Kino tilini tanlang:</b>\n\n"
        "<i>(Tugmalarni bosib tanlang, so'ng 'Tanlandi' tugmasini bosing yoki matn yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(MovieWizard.waiting_for_genre, F.text)
async def on_genre_text_received(message: Message, state: FSMContext, db: Database):
    genre_str = message.text.strip()
    await state.update_data(genre=genre_str, selected_langs=[])

    all_langs = await db.get_all_languages()
    await state.set_state(MovieWizard.waiting_for_lang)
    kb = get_lang_selector_kb(all_langs, [])
    await message.reply(
        f"✅ Janr: <b>{genre_str}</b>\n\n"
        "🌐 <b>6️⃣ Kino tilini tanlang:</b>\n\n"
        "<i>(Tugmalarni bosib tanlang, so'ng 'Tanlandi' tugmasini bosing yoki matn yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(MovieWizard.waiting_for_lang, F.data.startswith("toggle_wz_lang:"))
async def on_toggle_wz_lang(callback: CallbackQuery, state: FSMContext, db: Database):
    lang_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected = list(data.get("selected_langs", []))
    if lang_name in selected:
        selected.remove(lang_name)
    else:
        selected.append(lang_name)
    await state.update_data(selected_langs=selected)

    all_langs = await db.get_all_languages()
    kb = get_lang_selector_kb(all_langs, selected)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(MovieWizard.waiting_for_lang, F.data == "done_wz_lang")
async def on_done_wz_lang(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_langs", [])
    lang_str = ", ".join(selected) if selected else "O'zbek"
    await state.update_data(language=lang_str)

    await state.set_state(MovieWizard.waiting_for_country)
    kb = get_country_selector_kb()
    await callback.message.edit_text(
        f"✅ Tili: <b>{lang_str}</b>\n\n"
        "🌍 <b>7️⃣ Ishlab chiqarilgan davlatni tanlang:</b>\n\n"
        "<i>(Tugmalardan birini tanlang yoki qo'lda yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(MovieWizard.waiting_for_lang, F.text)
async def on_lang_text_received(message: Message, state: FSMContext):
    lang_str = message.text.strip()
    await state.update_data(language=lang_str)

    await state.set_state(MovieWizard.waiting_for_country)
    kb = get_country_selector_kb()
    await message.reply(
        f"✅ Tili: <b>{lang_str}</b>\n\n"
        "🌍 <b>7️⃣ Ishlab chiqarilgan davlatni tanlang:</b>\n\n"
        "<i>(Tugmalardan birini tanlang yoki qo'lda yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(MovieWizard.waiting_for_country, F.data.startswith("set_wz_country:"))
async def on_country_selected_btn(callback: CallbackQuery, state: FSMContext):
    country = callback.data.split(":")[1]
    await state.update_data(country=country)
    await state.set_state(MovieWizard.waiting_for_quality)
    kb = get_quality_selector_kb()
    await callback.message.edit_text(
        f"✅ Davlati: <b>{country}</b>\n\n"
        "⚡️ <b>8️⃣ Kino sifatini tanlang:</b>\n\n"
        "<i>(Tugmalardan birini tanlang yoki qo'lda yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(MovieWizard.waiting_for_country, F.text)
async def on_country_received(message: Message, state: FSMContext):
    country = message.text.strip()
    await state.update_data(country=country)
    await state.set_state(MovieWizard.waiting_for_quality)
    kb = get_quality_selector_kb()
    await message.reply(
        f"✅ Davlati: <b>{country}</b>\n\n"
        "⚡️ <b>8️⃣ Kino sifatini tanlang:</b>\n\n"
        "<i>(Tugmalardan birini tanlang yoki qo'lda yozing)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(MovieWizard.waiting_for_quality, F.data.startswith("set_wz_quality:"))
async def on_quality_selected_btn(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":")[1]
    await state.update_data(quality=quality)
    await state.set_state(MovieWizard.waiting_for_code)
    await callback.message.edit_text(
        f"✅ Sifati: <b>{quality}</b>\n\n"
        "🔒 <b>9️⃣ Kino kodini kiriting:</b>\n\n"
        "<i>Odamlar shu kod orqali kinoni topishadi. Avtomatik 5 xonali kod olish uchun <b>'Avto'</b> deb yozing.</i>",
        parse_mode="HTML"
    )

@router.message(MovieWizard.waiting_for_quality, F.text)
async def on_quality_received(message: Message, state: FSMContext):
    quality = message.text.strip()
    await state.update_data(quality=quality)
    await state.set_state(MovieWizard.waiting_for_code)
    await message.reply(
        f"✅ Sifati: <b>{quality}</b>\n\n"
        "🔒 <b>9️⃣ Kino kodini kiriting:</b>\n\n"
        "<i>Odamlar shu kod orqali kinoni topishadi. Avtomatik 5 xonali kod olish uchun <b>'Avto'</b> deb yozing.</i>",
        parse_mode="HTML"
    )


@router.message(MovieWizard.waiting_for_code, F.text)
async def on_code_received(message: Message, state: FSMContext, bot: Bot, db: Database):
    code_text = message.text.strip()
    if code_text.lower() in ["avto", "auto", "yaratish"]:
        code = str(random.randint(10000, 99999))
    else:
        code = code_text

    # Check if code already exists
    existing = await db.get_movie_by_code(code)
    if existing:
        await message.reply(f"⚠️ <b>#{code}</b> kodli kino allaqachon mavjud! Boshqa kod kiriting:")
        return

    await state.update_data(code=code)
    data = await state.get_data()

    # Create preview matching screenshot 4 & new fields
    caption = (
        f"🎬 <b>Kino nomi:</b> {data['title']}\n\n"
        f"⚡️ <b>Sifati:</b> {data['quality']}\n"
        f"🌐 <b>Tili:</b> {data['language']}\n"
        f"🎭 <b>Janri:</b> {data['genre']}\n"
        f"📅 <b>Yili:</b> {data.get('year', 2024)} | 🌍 <b>Davlati:</b> {data.get('country', 'AQSH')}\n\n"
        f"Ko'proq kinolar: @{config.BOT_USERNAME}\n\n"
        f"🔒 <b>Kod:</b> {data['code']}\n"
        f"👁 <b>Jami ko'rishlar:</b> 0 ta"
    )

    await state.set_state(MovieWizard.confirm_movie)

    # Send preview: If poster exists, show poster with caption; otherwise send media
    poster_id = data.get("poster_file_id")
    if poster_id:
        await bot.send_photo(chat_id=message.chat.id, photo=poster_id, caption=caption, parse_mode="HTML")
    elif data["file_type"] == "video":
        await bot.send_video(chat_id=message.chat.id, video=data["file_id"], caption=caption, parse_mode="HTML")
    elif data["file_type"] == "photo":
        await bot.send_photo(chat_id=message.chat.id, photo=data["file_id"], caption=caption, parse_mode="HTML")
    else:
        await bot.send_document(chat_id=message.chat.id, document=data["file_id"], caption=caption, parse_mode="HTML")

    await message.answer("👆 <b>Kino namunasi tayyor. Kinoni tasdiqlaysizmi?</b>", reply_markup=get_confirm_movie_kb(), parse_mode="HTML")

@router.callback_query(MovieWizard.confirm_movie, F.data == "movie_confirm_save")
async def on_confirm_movie_save(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database):
    data = await state.get_data()
    poster_url = data.get("poster_url")
    if not poster_url and data.get("poster_file_id"):
        poster_url = await upload_poster_to_catbox(bot, data["poster_file_id"])

    await db.add_movie(
        code=data["code"],
        title=data["title"],
        file_id=data["file_id"],
        file_type=data["file_type"],
        caption="",
        quality=data["quality"],
        language=data["language"],
        genre=data.get("genre", "Boshqa"),
        country=data.get("country", "AQSH"),
        year=data.get("year", 2024),
        poster_file_id=data.get("poster_file_id"),
        poster_url=poster_url
    )
    await state.clear()
    is_owner = (callback.from_user.id == await db.get_owner_id())
    await callback.message.edit_text(
        f"🎉 <b>Kino muvaffaqiyatli saqlandi va nashr qilindi!</b>\n\n"
        f"📌 <b>Nomi:</b> {data['title']}\n"
        f"🔒 <b>Kodi:</b> <code>{data['code']}</code>\n"
        f"🎭 <b>Janri:</b> {data.get('genre')}\n"
        f"📅 <b>Yili:</b> {data.get('year')}\n\n"
        f"Endi foydalanuvchilar ushbu kod orqali yoki filter orqali kinoni topishlari mumkin.",
        reply_markup=get_admin_main_kb(is_owner=is_owner),
        parse_mode="HTML"
    )

@router.callback_query(MovieWizard.confirm_movie, F.data == "movie_cancel")
async def on_cancel_movie(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Kino yuklash bekor qilindi.", reply_markup=get_admin_main_kb())

# ----------------- KINOLAR RO'YXATI -----------------
@router.callback_query(F.data == "admin_list_movies")
async def on_admin_list_movies(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    movies = await db.get_top_movies(limit=50)
    if not movies:
        text = "📋 <b>Bazadagi kinolar ro'yxati:</b>\n\n<i>Hozircha hech qanday kino qo'shilmagan.</i>"
    else:
        text = f"📋 <b>Bazadagi kinolar ro'yxati ({len(movies)} ta):</b>\n\n"
        for idx, m in enumerate(movies, 1):
            text += f"{idx}. <b>{m['title']}</b>\n   🔒 Kod: <code>{m['code']}</code> | 👁 Ko'rishlar: {m.get('views', 0)}\n   🎭 {m.get('genre')} | 📅 {m.get('year')}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="admin_add_movie"),
            InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="admin_delete_movie")
        ],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ----------------- KINO O'CHIRISH -----------------
@router.callback_query(F.data == "admin_delete_movie")
async def on_delete_movie_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    await state.set_state(DeleteMovieState.waiting_for_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")
    ]])
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan kinongizning kodini yuboring:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(DeleteMovieState.waiting_for_code, F.text)
async def on_delete_movie_code(message: Message, state: FSMContext, db: Database):
    code = message.text.strip()
    deleted = await db.delete_movie_by_code(code)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin_list_movies"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")
    ]])
    if deleted:
        await message.reply(f"✅ <b>#{code}</b> kodli kino bazadan muvaffaqiyatli o'chirildi!", reply_markup=kb, parse_mode="HTML")
    else:
        await message.reply(f"❌ <b>#{code}</b> kodli kino topilmadi!", reply_markup=kb, parse_mode="HTML")

# ----------------- MAJBURIY KANALLAR -----------------
@router.callback_query(F.data == "admin_channels")
async def on_admin_channels(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    channels = await db.get_all_channels()
    text = "📢 <b>Majburiy a'zo bo'linadigan kanallar ro'yxati:</b>\n\n"
    if not channels:
        text += "<i>Hozircha hech qanday kanal qo'shilmagan.</i>\n"
    else:
        for idx, ch in enumerate(channels, 1):
            text += f"{idx}. <b>{ch['title']}</b> (ID: <code>{ch['channel_id']}</code>)\n   Havola: {ch['url']}\n\n"

    kb_buttons = [
        [InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="admin_add_channel")],
    ]
    for ch in channels:
        kb_buttons.append([
            InlineKeyboardButton(text=f"🗑 O'chirish: {ch['title'][:20]}", callback_data=f"del_channel:{ch['channel_id']}")
        ])
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_channel")
async def on_add_channel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannelState.waiting_for_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_channels")]])
    await callback.message.edit_text(
        "📢 <b>Kanal qo'shish:</b>\n\n"
        "1️⃣ <b>Eng oson yo'li:</b> O'sha kanaldagi <b>istalgan bitta postni botga FORWARD (uzatish) qiling</b>! Bot avtomatik ID va nomini oladi.\n\n"
        "2️⃣ <b>Yoki:</b> Kanal usernamesi (<code>@kanal_nomi</code>) yoki ID sini (<code>-100...</code>) yuboring.\n\n"
        "⚠️ <i>Eslatma: Bot kanalda <b>Admin</b> bo'lishi shart!</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(AddChannelState.waiting_for_id)
async def on_channel_id_received(message: Message, state: FSMContext, bot: Bot):
    # 1. Forwarded post from channel
    if message.forward_from_chat:
        ch_id = str(message.forward_from_chat.id)
        title = message.forward_from_chat.title or "Kanal"
        await state.update_data(channel_id=ch_id, title=title)
        await state.set_state(AddChannelState.waiting_for_url)
        await message.reply(
            f"✅ Kanal aniqlandi: <b>{title}</b>\n🆔 ID: <code>{ch_id}</code>\n\n"
            "🔗 <b>Endi ushbu kanalga taklif havolasini (link) yuboring:</b>\n"
            "<i>(Masalan: <code>https://t.me/kanal</code> yoki zayavka havolasi <code>https://t.me/+...</code>)</i>",
            parse_mode="HTML"
        )
        return

    text = (message.text or "").strip()
    # Check if user sent an invite link instead of ID
    if "t.me/+" in text or "t.me/joinchat" in text:
        await message.reply(
            "⚠️ <b>Siz taklif havolasini yubordingiz!</b>\n\n"
            "Yopiq kanalning haqiqiy ID sini aniqlash uchun shu kanaldan <b>istalgan bitta postni botga FORWARD (uzatish) qilib yuboring</b>.",
            parse_mode="HTML"
        )
        return

    # User entered username or numeric ID
    ch_id = text
    if not ch_id.startswith("@") and not ch_id.startswith("-"):
        if ch_id.isdigit():
            ch_id = f"-100{ch_id}"
        elif not ch_id.startswith("http"):
            ch_id = f"@{ch_id}"

    try:
        chat = await bot.get_chat(ch_id)
        title = chat.title or "Kanal"
        await state.update_data(channel_id=str(chat.id), title=title)
        await state.set_state(AddChannelState.waiting_for_url)
        await message.reply(
            f"✅ Kanal topildi: <b>{title}</b>\n🆔 ID: <code>{chat.id}</code>\n\n"
            "🔗 <b>Endi ushbu kanalga taklif havolasini (link) yuboring:</b>\n"
            "<i>(Masalan: <code>https://t.me/kanal</code> yoki zayavka havolasi <code>https://t.me/+...</code>)</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Error resolving chat {ch_id}: {e}")
        # Allow manual entry if bot could not verify immediately
        await state.update_data(channel_id=ch_id)
        await state.set_state(AddChannelState.waiting_for_title)
        await message.reply(
            f"📝 <b>Kanal nomini kiriting:</b>\n<i>(Masalan: Eng Sara Filmlar Rasmiy)</i>\n\n"
            "<i>(Tavsiya: Yopiq kanal bo'lsa, xabarni forward qilib yuborish osonroq)</i>",
            parse_mode="HTML"
        )

@router.message(AddChannelState.waiting_for_title, F.text)
async def on_channel_title_received(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddChannelState.waiting_for_url)
    await message.reply(
        "🔗 <b>Kanal havolasini kiriting:</b>\n"
        "<i>(Masalan: <code>https://t.me/kanal</code> yoki private invite link <code>https://t.me/+...</code>)</i>",
        parse_mode="HTML"
    )

@router.message(AddChannelState.waiting_for_url, F.text)
async def on_channel_url_received(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    url = message.text.strip()
    await db.add_channel(
        channel_id=data["channel_id"],
        title=data["title"],
        url=url,
        is_private="+" in url or "joinchat" in url
    )
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📢 Kanallar ro'yxati", callback_data="admin_channels"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")
    ]])
    await message.reply(
        f"✅ <b>{data['title']}</b> kanali muvaffaqiyatli saqlandi!\n\n"
        f"🆔 ID: <code>{data['channel_id']}</code>\n"
        f"🔗 Havola: {url}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("del_channel:"))
async def on_del_channel(callback: CallbackQuery, db: Database):
    ch_id = callback.data.split(":")[1]
    await db.delete_channel(ch_id)
    await callback.answer("🗑 Kanal o'chirildi!", show_alert=True)
    # Refresh channels list
    await on_admin_channels(callback, db)

# ----------------- ADMINLAR BOSHQARUVI -----------------
@router.callback_query(F.data == "admin_manage_admins")
async def on_manage_admins(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    admins = await db.get_all_admins()
    text = "👥 <b>Adminlar ro'yxati:</b>\n\n"
    text += f"👑 <b>Asosiy Adminlar (Env):</b> {', '.join(str(x) for x in config.ADMIN_IDS)}\n\n"
    if admins:
        for idx, a in enumerate(admins, 1):
            text += f"{idx}. <b>{a['full_name']}</b> (ID: <code>{a['user_id']}</code>)\n"
    else:
        text += "<i>Qo'shimcha adminlar yo'q.</i>\n"

    kb_buttons = [
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="admin_add_admin_prompt")]
    ]
    for a in admins:
        kb_buttons.append([
            InlineKeyboardButton(text=f"🗑 O'chirish: {a['full_name'][:15]}", callback_data=f"del_admin:{a['user_id']}")
        ])
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_admin_prompt")
async def on_add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddAdminState.waiting_for_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_manage_admins")]])
    await callback.message.edit_text(
        "👤 <b>Yangi adminning Telegram ID sini yuboring:</b>\n\n"
        "<i>(Foydalanuvchi o'z ID sini @userinfobot orqali bilishi mumkin)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(AddAdminState.waiting_for_id, F.text)
async def on_admin_id_received(message: Message, state: FSMContext, bot: Bot, db: Database):
    text_val = message.text.strip()
    if not text_val.isdigit():
        await message.reply("⚠️ Iltimos, faqat raqamlardan iborat Telegram ID yuboring!")
        return

    new_admin_id = int(text_val)
    try:
        user_chat = await bot.get_chat(new_admin_id)
        name = user_chat.full_name or str(new_admin_id)
    except Exception:
        name = f"Admin {new_admin_id}"

    await db.add_admin(new_admin_id, name)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👥 Adminlar boshqaruvi", callback_data="admin_manage_admins"),
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")
    ]])
    await message.reply(f"✅ <b>{name}</b> (ID: <code>{new_admin_id}</code>) admin sifatida saqlandi!", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("del_admin:"))
async def on_del_admin(callback: CallbackQuery, db: Database):
    admin_id = int(callback.data.split(":")[1])
    await db.delete_admin(admin_id)
    await callback.answer("🗑 Admin o'chirildi!", show_alert=True)
    await on_manage_admins(callback, db)

# ----------------- REKLAMA TARQATISH (BROADCAST) -----------------
@router.callback_query(F.data == "admin_broadcast")
async def on_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastState.waiting_for_message)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")]])
    await callback.message.edit_text(
        "📢 <b>Reklama tarqatish bo'limi:</b>\n\n"
        "Foydalanuvchilarga yubormoqchi bo'lgan reklamangizni yuboring:\n\n"
        "• <b>Istalgan turdagi post:</b> Matn, rasm, video, GIF (animatsiya), ovozli xabar yoki fayl.\n"
        "• <b>Post matni va tugmalari:</b> Butunligicha, barcha formatlashlar (caption, havolalar, inline tugmalar) bilan yuboriladi.\n"
        "• <b>Forward (uzatilgan) xabar:</b> Agar boshqa kanal yoki chatdan uzatilgan xabar tashlasangiz, xuddi shunday uzatilgan holatda tarqatiladi!\n\n"
        "<i>Reklamani shu yerga yuboring:</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(BroadcastState.waiting_for_message)
async def on_broadcast_message_received(message: Message, state: FSMContext, db: Database):
    is_forwarded = bool(
        getattr(message, "forward_origin", None) or
        getattr(message, "forward_from", None) or
        getattr(message, "forward_from_chat", None) or
        getattr(message, "forward_date", None)
    )

    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
        is_forwarded=is_forwarded
    )
    await state.set_state(BroadcastState.confirm_broadcast)

    recipients = await db.get_broadcast_recipients(exclude_premium=True)
    total = len(recipients)
    type_str = "🔄 Uzatilgan (Forward) xabar" if is_forwarded else "📝 Yangi xabar / post (Nusxa)"

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Ha, reklamani tarqatish", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])

    await message.reply(
        "👆 <b>Reklama namunasi yuqoridagi xabaringiz.</b>\n\n"
        f"👥 <b>Qabul qiluvchilar soni:</b> {total} ta foydalanuvchi\n"
        f"💎 <i>(Premium obunachilarga reklama yuborilmaydi)</i>\n"
        f"📌 <b>Xabar turi:</b> {type_str}\n\n"
        "<i>Ushbu reklamani barcha foydalanuvchilarga tarqatishni tasdiqlaysizmi?</i>",
        reply_markup=confirm_kb,
        parse_mode="HTML"
    )

@router.callback_query(BroadcastState.confirm_broadcast, F.data == "cancel_broadcast")
async def on_cancel_broadcast(callback: CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    is_owner = (callback.from_user.id == await db.get_owner_id())
    await callback.message.edit_text("❌ Reklama tarqatish bekor qilindi.", reply_markup=get_admin_main_kb(is_owner=is_owner))

@router.callback_query(BroadcastState.confirm_broadcast, F.data == "confirm_broadcast")
async def on_confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database):
    data = await state.get_data()
    await state.clear()

    broadcast_chat_id = data["broadcast_chat_id"]
    broadcast_message_id = data["broadcast_message_id"]
    is_forwarded = data["is_forwarded"]

    status_msg = await callback.message.edit_text(
        "⏳ <b>Reklama tarqatilmoqda...</b>\n\n"
        "<i>Iltimos kuting, xabar foydalanuvchilarga yetkazilmoqda...</i>",
        parse_mode="HTML"
    )

    recipients = await db.get_broadcast_recipients(exclude_premium=True)

    sent = 0
    blocked = 0

    for uid in recipients:
        try:
            if is_forwarded:
                try:
                    await bot.forward_message(
                        chat_id=uid,
                        from_chat_id=broadcast_chat_id,
                        message_id=broadcast_message_id
                    )
                except Exception:
                    await bot.copy_message(
                        chat_id=uid,
                        from_chat_id=broadcast_chat_id,
                        message_id=broadcast_message_id
                    )
            else:
                await bot.copy_message(
                    chat_id=uid,
                    from_chat_id=broadcast_chat_id,
                    message_id=broadcast_message_id
                )
            sent += 1
            await asyncio.sleep(0.04)  # ~25 messages/second limit
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                if is_forwarded:
                    await bot.forward_message(
                        chat_id=uid,
                        from_chat_id=broadcast_chat_id,
                        message_id=broadcast_message_id
                    )
                else:
                    await bot.copy_message(
                        chat_id=uid,
                        from_chat_id=broadcast_chat_id,
                        message_id=broadcast_message_id
                    )
                sent += 1
            except Exception:
                blocked += 1
        except Exception:
            blocked += 1

    is_owner = (callback.from_user.id == await db.get_owner_id())
    await status_msg.edit_text(
        f"📊 <b>Reklama tarqatish yakunlandi:</b>\n\n"
        f"✅ <b>Yetkazildi:</b> {sent} ta\n"
        f"❌ <b>Yetib bormadi (bloklaganlar):</b> {blocked} ta\n"
        f"👥 <b>Jami yuborilganlar:</b> {len(recipients)} ta\n\n"
        f"💎 <i>(Premium obunachilarga reklama yuborilmadi)</i>",
        reply_markup=get_admin_main_kb(is_owner=is_owner),
        parse_mode="HTML"
    )

# ----------------- KARTA SOZLAMALARI -----------------
@router.callback_query(F.data == "admin_card_settings")
async def on_card_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CardSettingState.waiting_for_number)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")]])
    await callback.message.edit_text(
        f"💳 <b>Hozirgi karta:</b> <code>{config.CARD_NUMBER}</code> ({config.CARD_HOLDER})\n\n"
        f"Yangi karta raqamini yuboring (masalan: <code>8600 1234 5678 9012</code>):",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(CardSettingState.waiting_for_number, F.text)
async def on_card_number_set(message: Message, state: FSMContext):
    await state.update_data(card_number=message.text.strip())
    await state.set_state(CardSettingState.waiting_for_holder)
    await message.reply("👤 <b>Karta egasining ism va familiyasini kiriting:</b>\n<i>(Masalan: Palonchiyev Pistonchi)</i>", parse_mode="HTML")

@router.message(CardSettingState.waiting_for_holder, F.text)
async def on_card_holder_set(message: Message, state: FSMContext):
    data = await state.get_data()
    config.CARD_NUMBER = data["card_number"]
    config.CARD_HOLDER = message.text.strip()
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin_menu")
    ]])
    await message.reply(
        f"✅ <b>Karta ma'lumotlari muvaffaqiyatli yangilandi!</b>\n\n"
        f"💳 Raqam: <code>{config.CARD_NUMBER}</code>\n"
        f"👤 Egasi: {config.CARD_HOLDER}",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ----------------- SOZLAMALAR (MATN VA TUGMALAR) -----------------
@router.callback_query(F.data == "admin_settings_menu")
async def on_admin_settings_menu(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    settings = await db.get_all_settings()
    start_preview = (settings.get("start_text") or "Standart matn")[:60] + "..."
    premium_preview = (settings.get("premium_text") or "Standart matn")[:60] + "..."
    channel_preview = settings.get("movie_channel") or f"@{config.BOT_USERNAME}"

    text = (
        "⚙️ <b>Bot Matnlari va Tugmalari Sozlamalari:</b>\n\n"
        f"📝 <b>Start xabari:</b> <i>{start_preview}</i>\n"
        f"💎 <b>Obuna xabari:</b> <i>{premium_preview}</i>\n"
        f"📢 <b>Kanal tegi (postlarda):</b> <code>{channel_preview}</code>\n\n"
        "O'zgartirmoqchi bo'lgan parametrni tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_settings_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_edit_buttons_menu")
async def on_admin_edit_buttons_menu(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    settings = await db.get_all_settings()
    b_obuna = settings.get("btn_obuna", "💎 Obuna")
    b_top = settings.get("btn_top", "🎬 Top Filmlar")
    b_filter = settings.get("btn_filter", "📁 Filter")
    b_saved = settings.get("btn_saved", "⭐ Saqlangan")
    b_search = settings.get("btn_search", "🔍 Film qidirish")

    text = (
        "🔘 <b>Asosiy Menyu Tugmalari Sozlamalari:</b>\n\n"
        f"1. 💎 Obuna: <code>{b_obuna}</code>\n"
        f"2. 🎬 Top Filmlar: <code>{b_top}</code>\n"
        f"3. 📁 Filter: <code>{b_filter}</code>\n"
        f"4. ⭐ Saqlangan: <code>{b_saved}</code>\n"
        f"5. 🔍 Film qidirish: <code>{b_search}</code>\n\n"
        "Nomini o'zgartirmoqchi bo'lgan tugmani tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_edit_buttons_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("edit_setting:"))
async def on_start_edit_setting(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    key = callback.data.split(":")[1]
    await state.update_data(setting_key=key)
    await state.set_state(AdminSettingState.waiting_for_value)

    names = {
        "start_text": "Start xabari matni",
        "premium_text": "Obuna bo'limi matni",
        "movie_channel": "Kino postlari ostidagi kanal/reklama tegi",
        "btn_obuna": "Obuna tugmasi matni",
        "btn_top": "Top Filmlar tugmasi matni",
        "btn_filter": "Filter tugmasi matni",
        "btn_saved": "Saqlangan tugmasi matni",
        "btn_search": "Film qidirish tugmasi matni",
    }
    title = names.get(key, key)
    cur_val = await db.get_setting(key, "Standart")

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
    await callback.message.edit_text(
        f"✏️ <b>{title}ni tahrirlash:</b>\n\n"
        f"<b>Hozirgi qiymat:</b>\n{cur_val}\n\n"
        f"<i>Iltimos, yangi matnni yuboring:</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(AdminSettingState.waiting_for_value, F.text)
async def on_save_setting_value(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    key = data.get("setting_key")
    if not key:
        await state.clear()
        return

    new_val = message.text.strip()
    await db.set_setting(key, new_val)
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalarga qaytish", callback_data="admin_settings_menu")],
        [InlineKeyboardButton(text="👑 Bosh menyu", callback_data="admin_menu")]
    ])
    await message.reply(f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n\nYangi qiymat:\n{new_val}", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "reset_all_settings")
async def on_reset_settings(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    await db.reset_custom_settings()
    await callback.answer("🔄 Barcha matn va tugmalar standart holatga qaytarildi!", show_alert=True)
    await on_admin_settings_menu(callback, db)

# ----------------- EGALIKNI TOPSHIRISH (TRANSFER OWNER) -----------------
@router.callback_query(F.data == "admin_transfer_owner")
async def on_transfer_owner_start(callback: CallbackQuery, state: FSMContext, db: Database):
    owner_id = await db.get_owner_id()
    if callback.from_user.id != owner_id:
        await callback.answer("⛔️ Faqat botning Asosiy Egasi (Owner) egalikni o'tkaza oladi!", show_alert=True)
        return

    await state.set_state(TransferOwnerState.waiting_for_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")]])
    await callback.message.edit_text(
        "👑 <b>Bot egaligini (SuperAdmin) boshqa shaxsga topshirish</b>\n\n"
        "⚠️ <i>Diqqat! Egalikni topshirganingizdan so'ng, barcha boshqaruv yangi egaga o'tadi!</i>\n\n"
        "Yangi eganing Telegram ID sini yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(TransferOwnerState.waiting_for_id, F.text)
async def on_transfer_owner_confirm(message: Message, state: FSMContext, bot: Bot, db: Database):
    owner_id = await db.get_owner_id()
    if message.from_user.id != owner_id:
        await state.clear()
        await message.reply("⛔️ Ruxsat berilmadi.")
        return

    text_val = message.text.strip()
    if not text_val.isdigit():
        await message.reply("⚠️ Iltimos, faqat raqamlardan iborat Telegram ID yuboring!")
        return

    new_owner_id = int(text_val)
    if new_owner_id == owner_id:
        await message.reply("⚠️ Siz allaqachon bot egasisiz!")
        return

    try:
        chat = await bot.get_chat(new_owner_id)
        name = chat.full_name or str(new_owner_id)
    except Exception:
        name = f"User_{new_owner_id}"

    await db.transfer_owner(new_owner_id, name)
    await state.clear()

    # Inform old owner
    home_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
    ]])
    await message.reply(
        f"🎉 <b>Bot egaligi muvaffaqiyatli topshirildi!</b>\n\n"
        f"👑 Yangi egasi: <b>{name}</b> (ID: <code>{new_owner_id}</code>)\n"
        f"Endi botning to'liq nazorati yangi egaga tegishli.",
        reply_markup=home_kb,
        parse_mode="HTML"
    )

    # Attempt to notify new owner
    try:
        await bot.send_message(
            chat_id=new_owner_id,
            text=f"👑 <b>Tabriklaymiz! Sizga botning to'liq egalik huquqi (SuperAdmin) topshirildi!</b>\n\n"
                 f"Boshqaruv panelini ochish uchun /admin buyrug'ini yuboring.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify new owner {new_owner_id}: {e}")

# ----------------- JANRLAR BOSHQARUVI -----------------
@router.callback_query(F.data == "admin_manage_genres")
async def on_manage_genres(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    genres = await db.get_all_genres()
    text = (
        "🎭 <b>Janrlar boshqaruvi:</b>\n\n"
        "<i>Quyidagi janrlardan birini bosib uni o'chirishingiz yoki '➕ Yangi janr qo'shish' tugmasi bilan yangi janr kiritishingiz mumkin:</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_manage_genres_kb(genres), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_genre_prompt")
async def on_add_genre_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddGenreState.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_manage_genres")]])
    await callback.message.edit_text("🎭 <b>Yangi janr nomini yozing:</b>\n<i>(Masalan: Anime, Psixologik, Fantastika)</i>", reply_markup=kb, parse_mode="HTML")

@router.message(AddGenreState.waiting_for_name, F.text)
async def on_genre_name_entered(message: Message, state: FSMContext, db: Database):
    name = message.text.strip()
    success = await db.add_genre(name)
    await state.clear()
    genres = await db.get_all_genres()
    if success:
        await message.reply(f"✅ <b>'{name}'</b> janri muvaffaqiyatli qo'shildi!", reply_markup=get_manage_genres_kb(genres), parse_mode="HTML")
    else:
        await message.reply(f"⚠️ Ushbu janr allaqachon mavjud yoki xatolik yuz berdi.", reply_markup=get_manage_genres_kb(genres), parse_mode="HTML")

@router.callback_query(F.data.startswith("del_genre:"))
async def on_del_genre(callback: CallbackQuery, db: Database):
    genre_name = callback.data.split(":")[1]
    await db.delete_genre(genre_name)
    await callback.answer(f"🗑 '{genre_name}' o'chirildi!", show_alert=False)
    await on_manage_genres(callback, db)

# ----------------- TILLAR BOSHQARUVI -----------------
@router.callback_query(F.data == "admin_manage_langs")
async def on_manage_langs(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    langs = await db.get_all_languages()
    text = (
        "🚩 <b>Tillar boshqaruvi:</b>\n\n"
        "<i>Quyidagi tillardan birini bosib uni o'chirishingiz yoki '➕ Yangi til qo'shish' tugmasi bilan yangi til kiritishingiz mumkin:</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_manage_langs_kb(langs), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_lang_prompt")
async def on_add_lang_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddLangState.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_manage_langs")]])
    await callback.message.edit_text("🚩 <b>Yangi til nomini yozing:</b>\n<i>(Masalan: Fransuz, Nemis, Yapon)</i>", reply_markup=kb, parse_mode="HTML")

@router.message(AddLangState.waiting_for_name, F.text)
async def on_lang_name_entered(message: Message, state: FSMContext, db: Database):
    name = message.text.strip()
    success = await db.add_language(name)
    await state.clear()
    langs = await db.get_all_languages()
    if success:
        await message.reply(f"✅ <b>'{name}'</b> tili muvaffaqiyatli qo'shildi!", reply_markup=get_manage_langs_kb(langs), parse_mode="HTML")
    else:
        await message.reply(f"⚠️ Ushbu til allaqachon mavjud yoki xatolik yuz berdi.", reply_markup=get_manage_langs_kb(langs), parse_mode="HTML")

@router.callback_query(F.data.startswith("del_lang:"))
async def on_del_lang(callback: CallbackQuery, db: Database):
    lang_name = callback.data.split(":")[1]
    await db.delete_language(lang_name)
    await callback.answer(f"🗑 '{lang_name}' o'chirildi!", show_alert=False)
    await on_manage_langs(callback, db)


