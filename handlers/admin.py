import logging
import random
import asyncio
from datetime import datetime
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
    get_manage_langs_kb,
    get_premium_users_kb,
    get_confirm_revoke_kb,
    get_kino_management_kb,
    get_serial_wizard_season_kb
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

class FindUserPremState(StatesGroup):
    waiting_for_user_id = State()

class AddGenreState(StatesGroup):
    waiting_for_name = State()

class AddLangState(StatesGroup):
    waiting_for_name = State()

class SerialWizard(StatesGroup):
    waiting_for_poster = State()
    waiting_for_title = State()
    waiting_for_year = State()
    waiting_for_genre = State()
    waiting_for_lang = State()
    waiting_for_country = State()
    waiting_for_quality = State()
    waiting_for_code = State()
    waiting_for_season_name = State()
    waiting_for_episode = State()
    confirm_serial = State()

class AddEpisodeState(StatesGroup):
    waiting_for_serial_code = State()
    waiting_for_season_choice = State()
    waiting_for_new_season_name = State()
    waiting_for_episode_video = State()

class TransferPasswordState(StatesGroup):
    waiting_for_old_password = State()

class ChangeTransferPasswordState(StatesGroup):
    waiting_for_current_password = State()
    waiting_for_new_password = State()

async def is_authorized_admin(user_id: int, db: Database) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    return await db.is_admin(user_id, extra_admins=config.ADMIN_IDS)

async def is_owner_user(user_id: int, db: Database) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    owner_id = await db.get_owner_id()
    return user_id == owner_id

@router.message(Command("admin"))
async def on_admin_cmd(message: Message, db: Database):
    if not await is_authorized_admin(message.from_user.id, db):
        await message.reply("⛔️ Siz admin emassiz!")
        return

    is_owner = await is_owner_user(message.from_user.id, db)
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
    is_owner = await is_owner_user(callback.from_user.id, db)
    text = "👑 <b>Admin Boshqaruv Paneli:</b>"
    await callback.message.edit_text(text, reply_markup=get_admin_main_kb(is_owner=is_owner), parse_mode="HTML")


# ----------------- KINO & SERIAL BOSHQARUVI SUBMENU -----------------
@router.callback_query(F.data == "admin_kino_management")
async def on_kino_management(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    await state.clear()
    text = (
        "🎬 <b>Kino & Serial Boshqaruvi</b>\n\n"
        "Quyidagi amallardan birini tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_kino_management_kb(), parse_mode="HTML")


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
    is_owner = await is_owner_user(callback.from_user.id, db)
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
async def on_cancel_movie(callback: CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    is_owner = await is_owner_user(callback.from_user.id, db)
    await callback.message.edit_text("❌ Kino yuklash bekor qilindi.", reply_markup=get_admin_main_kb(is_owner=is_owner))

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
        [InlineKeyboardButton(text="⬅️ Kino & Serial boshqaruvi", callback_data="admin_kino_management")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ----------------- SERIALLAR RO'YXATI -----------------
@router.callback_query(F.data == "admin_list_serials")
async def on_admin_list_serials(callback: CallbackQuery, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    serials = await db.get_all_serials(limit=50)
    if not serials:
        text = "📺 <b>Bazadagi seriallar ro'yxati:</b>\n\n<i>Hozircha hech qanday serial qo'shilmagan.</i>"
    else:
        text = f"📺 <b>Bazadagi seriallar ro'yxati ({len(serials)} ta):</b>\n\n"
        for idx, s in enumerate(serials, 1):
            text += f"{idx}. <b>{s['title']}</b>\n   🔒 Kod: <code>{s['code']}</code> | 👁 Ko'rishlar: {s.get('views', 0)}\n   🎭 {s.get('genre')} | 📅 {s.get('year')}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📺 Yangi serial qo'shish", callback_data="admin_add_serial"),
            InlineKeyboardButton(text="➕ Qism qo'shish", callback_data="admin_add_episode")
        ],
        [InlineKeyboardButton(text="⬅️ Kino & Serial boshqaruvi", callback_data="admin_kino_management")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

# ----------------- KINO / SERIAL O'CHIRISH -----------------
@router.callback_query(F.data == "admin_delete_movie")
async def on_delete_movie_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return

    await state.set_state(DeleteMovieState.waiting_for_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")
    ]])
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan kino yoki serial kodini yuboring:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(DeleteMovieState.waiting_for_code, F.text)
async def on_delete_movie_code(message: Message, state: FSMContext, db: Database):
    code = message.text.strip()
    deleted = await db.delete_movie_by_code(code)
    if not deleted:
        deleted = await db.delete_serial_by_code(code)

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 Kinolar", callback_data="admin_list_movies"),
        InlineKeyboardButton(text="📺 Seriallar", callback_data="admin_list_serials"),
        InlineKeyboardButton(text="⬅️ Boshqaruv", callback_data="admin_kino_management")
    ]])
    if deleted:
        await message.reply(f"✅ <b>#{code}</b> kodli kino/serial bazadan muvaffaqiyatli o'chirildi!", reply_markup=kb, parse_mode="HTML")
    else:
        await message.reply(f"❌ <b>#{code}</b> kodli kino yoki serial topilmadi!", reply_markup=kb, parse_mode="HTML")

# ================== SERIAL QO'SHISH (FSM WIZARD) ==================
@router.callback_query(F.data == "admin_add_serial")
async def on_start_add_serial(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    await state.set_state(SerialWizard.waiting_for_poster)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        "📺 <b>Yangi serial qo'shish (1/8)</b>\n\n"
        "🖼 <b>Serial uchun poster (muqova) rasmini yuboring:</b>\n\n"
        "<i>Bu rasm foydalanuvchilarga serialni tanlashda ko'rsatiladi.</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(SerialWizard.waiting_for_poster, F.photo)
async def on_serial_poster(message: Message, state: FSMContext, bot: Bot):
    poster_file_id = message.photo[-1].file_id
    poster_url = await upload_poster_to_catbox(bot, poster_file_id)
    await state.update_data(poster_file_id=poster_file_id, poster_url=poster_url or "")
    await state.set_state(SerialWizard.waiting_for_title)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await message.answer("📺 <b>Serial qo'shish (2/8)</b>\n\n📝 <b>Serial nomini yozing:</b>\n\n<i>Masalan: Taxtlar O'yini, Squid Game, Ertugrul</i>", reply_markup=kb, parse_mode="HTML")

@router.message(SerialWizard.waiting_for_title, F.text)
async def on_serial_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(SerialWizard.waiting_for_year)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await message.answer("📺 <b>Serial qo'shish (3/8)</b>\n\n📅 <b>Yilni kiriting:</b>\n\n<i>Masalan: 2011-2019 yoki 2024</i>", reply_markup=kb, parse_mode="HTML")

@router.message(SerialWizard.waiting_for_year, F.text)
async def on_serial_year(message: Message, state: FSMContext, db: Database):
    await state.update_data(year=message.text.strip())
    await state.set_state(SerialWizard.waiting_for_genre)
    genres = await db.get_all_genres()
    kb = get_genre_selector_kb(genres, [])
    await message.answer("📺 <b>Serial qo'shish (4/8)</b>\n\n🎭 <b>Janrni tanlang:</b>", reply_markup=kb, parse_mode="HTML")

@router.callback_query(SerialWizard.waiting_for_genre, F.data.startswith("toggle_wz_genre:"))
async def on_serial_genre_toggle(callback: CallbackQuery, state: FSMContext, db: Database):
    genre = callback.data.split(":")[1]
    data = await state.get_data()
    selected = data.get("genres", [])
    if genre in selected:
        selected.remove(genre)
    else:
        selected.append(genre)
    await state.update_data(genres=selected)
    genres = await db.get_all_genres()
    await callback.message.edit_reply_markup(reply_markup=get_genre_selector_kb(genres, selected))
    await callback.answer()

@router.callback_query(SerialWizard.waiting_for_genre, F.data == "done_wz_genre")
async def on_serial_genre_done(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    selected = data.get("genres", [])
    genre_str = ", ".join(selected) if selected else "Boshqa"
    await state.update_data(genre=genre_str)
    await state.set_state(SerialWizard.waiting_for_lang)
    langs = await db.get_all_languages()
    kb = get_lang_selector_kb(langs, [])
    await callback.message.edit_text("📺 <b>Serial qo'shish (5/8)</b>\n\n🚩 <b>Tilni tanlang:</b>", reply_markup=kb, parse_mode="HTML")

@router.callback_query(SerialWizard.waiting_for_lang, F.data.startswith("toggle_wz_lang:"))
async def on_serial_lang_toggle(callback: CallbackQuery, state: FSMContext, db: Database):
    lang = callback.data.split(":")[1]
    data = await state.get_data()
    selected = data.get("langs", [])
    if lang in selected:
        selected.remove(lang)
    else:
        selected.append(lang)
    await state.update_data(langs=selected)
    langs = await db.get_all_languages()
    await callback.message.edit_reply_markup(reply_markup=get_lang_selector_kb(langs, selected))
    await callback.answer()

@router.callback_query(SerialWizard.waiting_for_lang, F.data == "done_wz_lang")
async def on_serial_lang_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("langs", [])
    lang_str = ", ".join(selected) if selected else "O'zbek"
    await state.update_data(language=lang_str)
    await state.set_state(SerialWizard.waiting_for_country)
    await callback.message.edit_text("📺 <b>Serial qo'shish (6/8)</b>\n\n🌍 <b>Davlatni tanlang:</b>", reply_markup=get_country_selector_kb(), parse_mode="HTML")

@router.callback_query(SerialWizard.waiting_for_country, F.data.startswith("set_wz_country:"))
async def on_serial_country(callback: CallbackQuery, state: FSMContext):
    country = callback.data.split(":")[1]
    await state.update_data(country=country)
    await state.set_state(SerialWizard.waiting_for_quality)
    await callback.message.edit_text("📺 <b>Serial qo'shish (7/8)</b>\n\n⚡️ <b>Sifatni tanlang:</b>", reply_markup=get_quality_selector_kb(), parse_mode="HTML")

@router.callback_query(SerialWizard.waiting_for_quality, F.data.startswith("set_wz_quality:"))
async def on_serial_quality(callback: CallbackQuery, state: FSMContext):
    quality = callback.data.split(":")[1]
    await state.update_data(quality=quality)
    await state.set_state(SerialWizard.waiting_for_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        "📺 <b>Serial qo'shish (8/8)</b>\n\n🔢 <b>Serial kodini kiriting:</b>\n\n"
        "<i>Bu kod foydalanuvchi serialni topish uchun yozadigan unikal raqam.\n"
        "Masalan: 250, 1001, 500\n"
        "Diqqat: Har bir serial va kinoning kodi unikal bo'lishi shart!</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(SerialWizard.waiting_for_code, F.text)
async def on_serial_code(message: Message, state: FSMContext, db: Database):
    code = message.text.strip()
    existing_movie = await db.get_movie_by_code(code)
    existing_serial = await db.get_serial_by_code(code)
    if existing_movie or existing_serial:
        await message.reply(f"⚠️ <b>{code}</b> kodi allaqachon ishlatilgan! Boshqa kod kiriting.", parse_mode="HTML")
        return

    await state.update_data(code=code)
    data = await state.get_data()

    await state.set_state(SerialWizard.waiting_for_season_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await message.answer(
        f"✅ <b>Serial ma'lumotlari tayyor!</b>\n\n"
        f"📺 <b>{data.get('title')}</b> | Kod: <code>{code}</code>\n\n"
        f"Endi <b>1-fasl nomini</b> kiriting:\n"
        f"<i>(Masalan: 1-fasl, Season 1)</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(SerialWizard.waiting_for_season_name, F.text)
async def on_serial_season_name(message: Message, state: FSMContext):
    season_name = message.text.strip()
    data = await state.get_data()
    current_season_number = data.get("current_season_number", 1)
    await state.update_data(
        current_season_name=season_name,
        current_season_number=current_season_number,
        current_episode_number=1,
        episodes_list=[]
    )
    await state.set_state(SerialWizard.waiting_for_episode)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await message.answer(
        f"📺 <b>{data.get('title')}</b> → <b>{season_name}</b>\n\n"
        f"🎬 <b>1-qism videosini yuboring:</b>\n\n"
        f"<i>Bot ushbu qismni {season_name}ga biriktiradi.</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(SerialWizard.waiting_for_episode, F.video | F.document)
async def on_serial_episode_video(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    else:
        file_id = message.document.file_id
        file_type = "document"

    episodes_list = data.get("episodes_list", [])
    current_ep = data.get("current_episode_number", 1)
    season_name = data.get("current_season_name", "1-fasl")
    episodes_list.append({"episode_number": current_ep, "file_id": file_id, "file_type": file_type})
    await state.update_data(episodes_list=episodes_list, current_episode_number=current_ep + 1)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"➕ Yana {current_ep + 1}-qism qo'shish", callback_data="serial_wz_add_more"),
            InlineKeyboardButton(text="✅ Saqlash va tugatish", callback_data="serial_wz_finish")
        ],
        [
            InlineKeyboardButton(text="📁 Yangi fasl ochish", callback_data="serial_wz_new_season")
        ]
    ])
    await message.answer(
        f"✅ <b>{season_name} → {current_ep}-qism</b> qabul qilindi!\n\n"
        f"Bu faslda hozir: <b>{len(episodes_list)} ta qism</b> mavjud.\n\n"
        f"Keyingi qadam:",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(SerialWizard.waiting_for_episode, F.data == "serial_wz_add_more")
async def on_serial_wz_add_more(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_ep = data.get("current_episode_number", 2)
    season_name = data.get("current_season_name", "1-fasl")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        f"📺 <b>{data.get('title')}</b> → <b>{season_name}</b>\n\n"
        f"🎬 <b>{current_ep}-qism videosini yuboring:</b>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(SerialWizard.waiting_for_episode, F.data == "serial_wz_new_season")
async def on_serial_wz_new_season(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_season = data.get("current_season_number", 1)

    seasons_data = data.get("seasons_data", [])
    seasons_data.append({
        "season_number": current_season,
        "season_name": data.get("current_season_name", f"{current_season}-fasl"),
        "episodes": data.get("episodes_list", [])
    })

    await state.update_data(
        seasons_data=seasons_data,
        current_season_number=current_season + 1,
        episodes_list=[]
    )

    await state.set_state(SerialWizard.waiting_for_season_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        f"📺 <b>Yangi fasl nomini kiriting:</b>\n\n"
        f"<i>Masalan: {current_season + 1}-fasl, Season {current_season + 1}</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(SerialWizard.waiting_for_episode, F.data == "serial_wz_finish")
async def on_serial_wz_finish(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    seasons_data = list(data.get("seasons_data", []))
    current_eps = data.get("episodes_list", [])
    if current_eps:
        seasons_data.append({
            "season_number": data.get("current_season_number", 1),
            "season_name": data.get("current_season_name", "1-fasl"),
            "episodes": current_eps
        })

    total_seasons = len(seasons_data)
    total_episodes = sum(len(s["episodes"]) for s in seasons_data)

    await state.update_data(seasons_data=seasons_data)
    await state.set_state(SerialWizard.confirm_serial)

    text = (
        f"✅ <b>Tasdiqlash:</b>\n\n"
        f"📺 <b>Serial:</b> {data.get('title')}\n"
        f"🔢 <b>Kod:</b> <code>{data.get('code')}</code>\n"
        f"📅 <b>Yil:</b> {data.get('year')}\n"
        f"🎭 <b>Janr:</b> {data.get('genre')}\n"
        f"🚩 <b>Til:</b> {data.get('language')}\n"
        f"🌍 <b>Davlat:</b> {data.get('country')}\n"
        f"⚡️ <b>Sifat:</b> {data.get('quality')}\n\n"
        f"📊 <b>Hajmi:</b> {total_seasons} fasl · {total_episodes} qism\n\n"
        f"Bazaga saqlansinmi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, saqlash!", callback_data="serial_wz_confirm_save"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_kino_management")
        ]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(SerialWizard.confirm_serial, F.data == "serial_wz_confirm_save")
async def on_serial_wz_confirm_save(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    seasons_data = data.get("seasons_data", [])

    await callback.message.edit_text("⏳ <b>Serial bazaga saqlanmoqda...</b>", parse_mode="HTML")

    try:
        raw_year = str(data.get("year", "2024")).split("-")[0].strip()
        year_int = int(raw_year) if raw_year.isdigit() else 2024

        serial_id = await db.add_serial(
            code=data["code"],
            title=data["title"],
            poster_file_id=data.get("poster_file_id", ""),
            poster_url=data.get("poster_url", ""),
            language=data.get("language", "O'zbek"),
            genre=data.get("genre", "Boshqa"),
            country=data.get("country", "AQSH"),
            year=year_int,
            quality=data.get("quality", "1080p")
        )

        total_ep_saved = 0
        for season in seasons_data:
            season_id = await db.get_or_create_season(serial_id, season["season_number"], season["season_name"])
            for ep in season["episodes"]:
                await db.add_episode(serial_id, season_id, ep["episode_number"], ep["file_id"], ep["file_type"])
                total_ep_saved += 1

        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📺 Seriallar ro'yxati", callback_data="admin_list_serials")],
            [InlineKeyboardButton(text="⬅️ Boshqaruv", callback_data="admin_kino_management")]
        ])
        await callback.message.edit_text(
            f"✅ <b>Serial muvaffaqiyatli saqlandi!</b>\n\n"
            f"📺 <b>{data['title']}</b>\n"
            f"🔢 Kod: <code>{data['code']}</code>\n"
            f"📊 {len(seasons_data)} fasl · {total_ep_saved} qism bazaga qo'shildi!",
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error saving serial: {e}")
        await callback.message.edit_text(
            f"❌ <b>Xatolik yuz berdi:</b> {e}\n\nQaytadan urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Boshqaruv", callback_data="admin_kino_management")
            ]]),
            parse_mode="HTML"
        )
        await state.clear()

# ================== MAVJUD SERIALGA QISM QO'SHISH ==================
@router.callback_query(F.data == "admin_add_episode")
async def on_add_episode_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_authorized_admin(callback.from_user.id, db):
        return
    await state.set_state(AddEpisodeState.waiting_for_serial_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        "➕ <b>Mavjud serialga qism qo'shish</b>\n\n"
        "📺 <b>Serial kodini kiriting:</b>\n\n"
        "<i>Masalan: 250 (Taxtlar O'yini)</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(AddEpisodeState.waiting_for_serial_code, F.text)
async def on_add_episode_serial_code(message: Message, state: FSMContext, db: Database):
    code = message.text.strip()
    serial = await db.get_serial_by_code(code)
    if not serial:
        await message.reply(f"❌ <b>{code}</b> kodli serial topilmadi! Kodni tekshirib qaytadan kiriting.", parse_mode="HTML")
        return

    await state.update_data(serial_id=serial['id'], serial_title=serial['title'], serial_code=code)
    seasons = await db.get_seasons(serial['id'])

    if not seasons:
        await state.set_state(AddEpisodeState.waiting_for_new_season_name)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
        await message.answer(
            f"📺 <b>{serial['title']}</b> topildi!\n\n"
            f"Hozircha fasllar yo'q. <b>Fasl nomini kiriting:</b>\n"
            f"<i>Masalan: 1-fasl</i>",
            reply_markup=kb, parse_mode="HTML"
        )
    else:
        await state.set_state(AddEpisodeState.waiting_for_season_choice)
        kb = get_serial_wizard_season_kb(seasons, serial['id'])
        await message.answer(
            f"📺 <b>{serial['title']}</b> topildi!\n\n"
            f"Qaysi faslga qism qo'shmoqchisiz?",
            reply_markup=kb, parse_mode="HTML"
        )

@router.callback_query(AddEpisodeState.waiting_for_season_choice, F.data.startswith("wz_serial_pick_season:"))
async def on_add_episode_pick_season(callback: CallbackQuery, state: FSMContext, db: Database):
    parts = callback.data.split(":")
    serial_id = int(parts[1])
    season_id = int(parts[2])
    season_number = int(parts[3])

    next_ep = await db.get_next_episode_number(season_id)
    await state.update_data(season_id=season_id, season_number=season_number, next_episode=next_ep)
    await state.set_state(AddEpisodeState.waiting_for_episode_video)

    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        f"📺 <b>{data.get('serial_title')}</b>\n\n"
        f"📂 Fasl tanlandi.\n\n"
        f"🎬 <b>{next_ep}-qism videosini yuboring:</b>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(AddEpisodeState.waiting_for_season_choice, F.data.startswith("wz_serial_new_season:"))
async def on_add_episode_new_season(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddEpisodeState.waiting_for_new_season_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        "📂 <b>Yangi fasl nomini kiriting:</b>\n\n"
        "<i>Masalan: 2-fasl, Season 2</i>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(AddEpisodeState.waiting_for_new_season_name, F.text)
async def on_add_episode_new_season_name(message: Message, state: FSMContext, db: Database):
    season_name = message.text.strip()
    data = await state.get_data()
    serial_id = data.get("serial_id")

    seasons = await db.get_seasons(serial_id)
    next_season_number = (max([s['season_number'] for s in seasons]) + 1) if seasons else 1

    season_id = await db.get_or_create_season(serial_id, next_season_number, season_name)
    await state.update_data(season_id=season_id, season_number=next_season_number, next_episode=1)
    await state.set_state(AddEpisodeState.waiting_for_episode_video)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await message.answer(
        f"✅ <b>{season_name}</b> yaratildi!\n\n"
        f"🎬 <b>1-qism videosini yuboring:</b>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(AddEpisodeState.waiting_for_episode_video, F.video | F.document)
async def on_add_episode_video(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    else:
        file_id = message.document.file_id
        file_type = "document"

    serial_id = data["serial_id"]
    season_id = data["season_id"]
    next_ep = data["next_episode"]

    await db.add_episode(serial_id, season_id, next_ep, file_id, file_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"➕ Yana {next_ep + 1}-qism qo'shish", callback_data="add_ep_more"),
            InlineKeyboardButton(text="✅ Tugatish", callback_data="add_ep_done")
        ]
    ])
    await state.update_data(next_episode=next_ep + 1)
    await message.answer(
        f"✅ <b>{data.get('serial_title')}</b> → <b>{next_ep}-qism</b> muvaffaqiyatli qo'shildi!\n\n"
        f"Yana qism qo'shasizmi?",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(AddEpisodeState.waiting_for_episode_video, F.data == "add_ep_more")
async def on_add_ep_more(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    next_ep = data.get("next_episode", 2)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_kino_management")]])
    await callback.message.edit_text(
        f"🎬 <b>{data.get('serial_title')}</b>\n\n"
        f"<b>{next_ep}-qism videosini yuboring:</b>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(AddEpisodeState.waiting_for_episode_video, F.data == "add_ep_done")
async def on_add_ep_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yana qism qo'shish", callback_data="admin_add_episode")],
        [InlineKeyboardButton(text="⬅️ Boshqaruv", callback_data="admin_kino_management")]
    ])
    await callback.message.edit_text(
        f"✅ <b>{data.get('serial_title')}</b> serialiga yangi qismlar muvaffaqiyatli qo'shildi!",
        reply_markup=kb, parse_mode="HTML"
    )

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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
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
async def on_add_admin_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
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
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!")
        return
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    admin_id = int(callback.data.split(":")[1])
    await db.delete_admin(admin_id)
    await callback.answer("🗑 Admin o'chirildi!", show_alert=True)
    await on_manage_admins(callback, db)


# ----------------- PREMIUM FOYDALANUVCHILAR BOSHQARUVI -----------------
@router.callback_query(F.data == "admin_premium_users")
async def on_admin_premium_users(callback: CallbackQuery, db: Database, state: FSMContext):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    await state.clear()
    users = await db.get_active_premium_users()
    total_count = len(users)

    if not users:
        text = (
            "💎 <b>Faol Premium obunachilar:</b>\n\n"
            "<i>Hozirda hech qanday faol pullik obunachi mavjud emas.</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ID orqali qidirish", callback_data="find_user_prem_prompt")],
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_menu")]
        ])
    else:
        text = f"💎 <b>Faol Premium obunachilar (Jami: {total_count} ta):</b>\n\n"
        for idx, u in enumerate(users[:6], 1):
            name = u.get("full_name") or u.get("username") or str(u["user_id"])
            p_until = u.get("premium_until")
            if p_until:
                if isinstance(p_until, str):
                    try:
                        p_dt = datetime.fromisoformat(p_until)
                        until_str = p_dt.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        until_str = str(p_until)[:16]
                else:
                    until_str = p_until.strftime("%d.%m.%Y %H:%M")
            else:
                until_str = "Cheksiz"
            text += f"{idx}. <b>{name}</b> (ID: <code>{u['user_id']}</code>)\n   ⏳ Muddat: <i>{until_str}</i>\n"

        text += "\n💡 <i>Obunani bekor qilish (tortib olish) uchun pastdagi tugmalardan foydalaning:</i>"
        kb = get_premium_users_kb(users, page=0)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("prem_users_page:"))
async def on_prem_users_page(callback: CallbackQuery, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    users = await db.get_active_premium_users()
    total_count = len(users)

    start = page * 6
    end = start + 6
    page_users = users[start:end]

    text = f"💎 <b>Faol Premium obunachilar (Sahifa: {page + 1}, Jami: {total_count} ta):</b>\n\n"
    for idx, u in enumerate(page_users, start + 1):
        name = u.get("full_name") or u.get("username") or str(u["user_id"])
        p_until = u.get("premium_until")
        if p_until:
            if isinstance(p_until, str):
                try:
                    p_dt = datetime.fromisoformat(p_until)
                    until_str = p_dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    until_str = str(p_until)[:16]
            else:
                until_str = p_until.strftime("%d.%m.%Y %H:%M")
        else:
            until_str = "Cheksiz"
        text += f"{idx}. <b>{name}</b> (ID: <code>{u['user_id']}</code>)\n   ⏳ Muddat: <i>{until_str}</i>\n"

    text += "\n💡 <i>Obunani bekor qilish (tortib olish) uchun pastdagi tugmalardan foydalaning:</i>"
    kb = get_premium_users_kb(users, page=page)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("revoke_prem_confirm:"))
async def on_revoke_prem_confirm(callback: CallbackQuery, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[1])
    user = await db.get_user(target_user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    name = user.get("full_name") or user.get("username") or str(target_user_id)
    p_until = user.get("premium_until")
    if p_until:
        if isinstance(p_until, str):
            try:
                p_dt = datetime.fromisoformat(p_until)
                until_str = p_dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                until_str = str(p_until)[:16]
        else:
            until_str = p_until.strftime("%d.%m.%Y %H:%M")
    else:
        until_str = "Cheksiz / Belgilanmagan"

    text = (
        "⚠️ <b>Haqiqatan ham Premium obunani bekor qilmoqchimisiz?</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{target_user_id}</code>\n"
        f"⏳ <b>Joriy tugash vaqti:</b> {until_str}\n\n"
        "<i>Eslatma: Obuna bekor qilingach, foydalanuvchiga bu haqda xabar beriladi va Premium imtiyozlari to'xtatiladi.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_confirm_revoke_kb(target_user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("do_revoke_prem:"))
async def on_do_revoke_prem(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    target_user_id = int(callback.data.split(":")[1])
    await db.revoke_user_premium(target_user_id)

    # Notify target user
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "⚠️ <b>Eslatma:</b> Sizning 💎 VIP / Premium obunangiz admin tomonidan bekor qilindi.\n\n"
                "Qayta faollashtirish uchun asosiy menyudagi '💎 Obuna' bo'limiga kiring."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {target_user_id} about revoked premium: {e}")

    await callback.answer("❌ Premium obuna muvaffaqiyatli tortib olindi!", show_alert=True)
    await on_admin_premium_users(callback, db, state)


@router.callback_query(F.data == "find_user_prem_prompt")
async def on_find_user_prem_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    await state.set_state(FindUserPremState.waiting_for_user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_premium_users")
    ]])
    await callback.message.edit_text(
        "🔍 <b>Foydalanuvchining Telegram ID sini kiriting:</b>\n\n"
        "<i>(Faqat raqamlardan iborat Telegram ID yuboring)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.message(FindUserPremState.waiting_for_user_id, F.text)
async def on_find_user_prem_id_received(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        return

    text_val = message.text.strip()
    if not text_val.isdigit():
        await message.reply("⚠️ Iltimos, faqat raqamlardan iborat Telegram ID yuboring!")
        return

    target_id = int(text_val)
    user = await db.get_user(target_id)
    if not user:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Premium a'zolar ro'yxati", callback_data="admin_premium_users")
        ]])
        await message.reply(f"❌ <code>{target_id}</code> ID ga ega foydalanuvchi bot bazasida topilmadi.", reply_markup=kb, parse_mode="HTML")
        await state.clear()
        return

    is_prem = await db.is_user_premium(target_id)
    name = user.get("full_name") or user.get("username") or str(target_id)
    p_until = user.get("premium_until")
    if p_until:
        if isinstance(p_until, str):
            try:
                p_dt = datetime.fromisoformat(p_until)
                until_str = p_dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                until_str = str(p_until)[:16]
        else:
            until_str = p_until.strftime("%d.%m.%Y %H:%M")
    else:
        until_str = "Cheksiz / Belgilanmagan"

    await state.clear()
    if is_prem:
        text = (
            f"👤 <b>Foydalanuvchi topildi:</b>\n\n"
            f"• Nomi: <b>{name}</b>\n"
            f"• ID: <code>{target_id}</code>\n"
            f"• Obuna holati: 💎 Faol\n"
            f"• Tugash vaqti: <i>{until_str}</i>\n\n"
            "Ushbu foydalanuvchining obunasini tortib olmoqchimisiz?"
        )
        await message.reply(text, reply_markup=get_confirm_revoke_kb(target_id), parse_mode="HTML")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Premium a'zolar", callback_data="admin_premium_users")
        ]])
        text = (
            f"👤 <b>Foydalanuvchi topildi:</b>\n\n"
            f"• Nomi: <b>{name}</b>\n"
            f"• ID: <code>{target_id}</code>\n"
            f"• Obuna holati: ❌ Faol emas (Oddiy foydalanuvchi)\n"
        )
        await message.reply(text, reply_markup=kb, parse_mode="HTML")


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
    is_owner = await is_owner_user(callback.from_user.id, db)
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

    is_owner = await is_owner_user(callback.from_user.id, db)
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
async def on_card_settings(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Karta sozlash faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    await state.set_state(CardSettingState.waiting_for_number)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_menu")]])
    await callback.message.edit_text(
        f"💳 <b>Hozirgi karta:</b> <code>{config.CARD_NUMBER}</code> ({config.CARD_HOLDER})\n\n"
        f"Yangi karta raqamini yuboring (masalan: <code>8600 1234 5678 9012</code>):",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(CardSettingState.waiting_for_number, F.text)
async def on_card_number_set(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Karta sozlash faqat Asosiy Admin (Owner) uchun!")
        return
    await state.update_data(card_number=message.text.strip())
    await state.set_state(CardSettingState.waiting_for_holder)
    await message.reply("👤 <b>Karta egasining ism va familiyasini kiriting:</b>\n<i>(Masalan: Palonchiyev Pistonchi)</i>", parse_mode="HTML")

@router.message(CardSettingState.waiting_for_holder, F.text)
async def on_card_holder_set(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Karta sozlash faqat Asosiy Admin (Owner) uchun!")
        return
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
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
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!")
        return
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return

    await db.reset_custom_settings()
    await callback.answer("🔄 Barcha matn va tugmalar standart holatga qaytarildi!", show_alert=True)
    await on_admin_settings_menu(callback, db)

# ----------------- EGALIKNI TOPSHIRISH (TRANSFER OWNER) PAROLLI -----------------
DEFAULT_TRANSFER_PASSWORD = "admin1234"

@router.callback_query(F.data == "admin_transfer_owner")
async def on_transfer_owner_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Faqat botning Asosiy Egasi (Owner) egalikni o'tkaza oladi!", show_alert=True)
        return

    await state.set_state(TransferPasswordState.waiting_for_old_password)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
    await callback.message.edit_text(
        "🔐 <b>Egalikni o'tkazish — Xavfsizlik paroli</b>\n\n"
        "⚠️ <i>Diqqat! Bu o'ta jiddiy amal. Davom etish uchun maxfiy transfer parolini kiriting:</i>\n\n"
        "<i>(Dastlabki standart parol: <code>admin1234</code>. Uni 'Transfer parolini o'zgartirish' orqali yangilashingiz mumkin)</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(TransferPasswordState.waiting_for_old_password, F.text)
async def on_transfer_owner_password_check(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        return

    entered = message.text.strip()
    saved_password = await db.get_setting("transfer_password", DEFAULT_TRANSFER_PASSWORD)
    if entered != saved_password:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
        await message.reply("❌ <b>Noto'g'ri parol kiritildi!</b> Qaytadan urinib ko'ring yoki bekor qiling:", reply_markup=kb, parse_mode="HTML")
        return

    await state.set_state(TransferOwnerState.waiting_for_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
    await message.reply(
        "✅ <b>Parol tasdiqlandi!</b>\n\n"
        "👑 <b>Bot egaligini (SuperAdmin) yangi shaxsga topshirish</b>\n\n"
        "⚠️ <i>Egalik topshirilgach, barcha maxfiy huquqlar yangi egaga o'tadi!</i>\n\n"
        "Yangi eganing <b>Telegram ID</b> sini yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "change_transfer_password")
async def on_change_transfer_password_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Faqat Owner uchun!", show_alert=True)
        return
    await state.set_state(ChangeTransferPasswordState.waiting_for_current_password)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
    await callback.message.edit_text(
        "🔑 <b>Transfer parolini o'zgartirish</b>\n\n"
        "Avval <b>joriy parolni</b> kiriting:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(ChangeTransferPasswordState.waiting_for_current_password, F.text)
async def on_change_password_current(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        return

    entered = message.text.strip()
    saved = await db.get_setting("transfer_password", DEFAULT_TRANSFER_PASSWORD)
    if entered != saved:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
        await message.reply("❌ <b>Joriy parol noto'g'ri!</b>", reply_markup=kb, parse_mode="HTML")
        return

    await state.set_state(ChangeTransferPasswordState.waiting_for_new_password)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_settings_menu")]])
    await message.reply("✅ Tasdiqlandi!\n\n🔑 Endi <b>yangi parolni</b> kiriting (kamida 4 ta belgi):", reply_markup=kb, parse_mode="HTML")

@router.message(ChangeTransferPasswordState.waiting_for_new_password, F.text)
async def on_change_password_new(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        return

    new_password = message.text.strip()
    if len(new_password) < 4:
        await message.reply("⚠️ Parol kamida 4 ta belgidan iborat bo'lishi kerak!")
        return

    await db.set_setting("transfer_password", new_password)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Sozlamalar", callback_data="admin_settings_menu")]])
    await message.reply(
        f"✅ <b>Transfer paroli muvaffaqiyatli yangilandi!</b>\n\n"
        f"Yangi maxfiy parol: <code>{new_password}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(TransferOwnerState.waiting_for_id, F.text)
async def on_transfer_owner_confirm(message: Message, state: FSMContext, bot: Bot, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Ruxsat berilmadi.")
        return

    owner_id = await db.get_owner_id()
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    genres = await db.get_all_genres()
    text = (
        "🎭 <b>Janrlar boshqaruvi:</b>\n\n"
        "<i>Quyidagi janrlardan birini bosib uni o'chirishingiz yoki '➕ Yangi janr qo'shish' tugmasi bilan yangi janr kiritishingiz mumkin:</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_manage_genres_kb(genres), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_genre_prompt")
async def on_add_genre_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    await state.set_state(AddGenreState.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_manage_genres")]])
    await callback.message.edit_text("🎭 <b>Yangi janr nomini yozing:</b>\n<i>(Masalan: Anime, Psixologik, Fantastika)</i>", reply_markup=kb, parse_mode="HTML")

@router.message(AddGenreState.waiting_for_name, F.text)
async def on_genre_name_entered(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!")
        return
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    genre_name = callback.data.split(":")[1]
    await db.delete_genre(genre_name)
    await callback.answer(f"🗑 '{genre_name}' o'chirildi!", show_alert=False)
    await on_manage_genres(callback, db)

# ----------------- TILLAR BOSHQARUVI -----------------
@router.callback_query(F.data == "admin_manage_langs")
async def on_manage_langs(callback: CallbackQuery, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    langs = await db.get_all_languages()
    text = (
        "🚩 <b>Tillar boshqaruvi:</b>\n\n"
        "<i>Quyidagi tillardan birini bosib uni o'chirishingiz yoki '➕ Yangi til qo'shish' tugmasi bilan yangi til kiritishingiz mumkin:</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_manage_langs_kb(langs), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_lang_prompt")
async def on_add_lang_prompt(callback: CallbackQuery, state: FSMContext, db: Database):
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu bo'lim faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    await state.set_state(AddLangState.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_manage_langs")]])
    await callback.message.edit_text("🚩 <b>Yangi til nomini yozing:</b>\n<i>(Masalan: Fransuz, Nemis, Yapon)</i>", reply_markup=kb, parse_mode="HTML")

@router.message(AddLangState.waiting_for_name, F.text)
async def on_lang_name_entered(message: Message, state: FSMContext, db: Database):
    if not await is_owner_user(message.from_user.id, db):
        await state.clear()
        await message.reply("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!")
        return
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
    if not await is_owner_user(callback.from_user.id, db):
        await callback.answer("⛔️ Bu amal faqat Asosiy Admin (Owner) uchun!", show_alert=True)
        return
    lang_name = callback.data.split(":")[1]
    await db.delete_language(lang_name)
    await callback.answer(f"🗑 '{lang_name}' o'chirildi!", show_alert=False)
    await on_manage_langs(callback, db)


