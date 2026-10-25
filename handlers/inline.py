import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import config
from database import Database
from handlers.subscription import check_user_access

logger = logging.getLogger(__name__)
router = Router()

DEFAULT_THUMB = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=200"

def create_movie_article(m: dict, bot_username: str, prefix_id: str, title_prefix: str = "") -> InlineQueryResultArticle:
    lang = m.get("language") or "O'zbek"
    quality = m.get("quality") or "1080p"
    genre = m.get("genre") or "Boshqa"
    country = m.get("country") or "AQSH"
    year = m.get("year") or 2024
    views = m.get("views", 0)
    title = f"{title_prefix}{m['title']}"

    desc = f"🎬 #{m['code']} • {quality} | 👁 {views}\n🚩 {lang}, {genre}"

    thumb = m.get("poster_url") or DEFAULT_THUMB

    caption = (
        f"<a href=\"{thumb}\">&#8205;</a>"
        f"🎬 <b>{m['title']}</b>\n\n"
        f"⚡️ <b>Sifati:</b> {quality}\n"
        f"🌐 <b>Tili:</b> {lang}\n"
        f"🎭 <b>Janri:</b> {genre}\n"
        f"📅 <b>Yili:</b> {year} | 🌍 <b>Davlati:</b> {country}\n\n"
        f"Ko'proq kinolar: @{bot_username}\n\n"
        f"🔒 <b>Kodi:</b> <code>{m['code']}</code>\n"
        f"👁 <b>Jami ko'rishlar:</b> {views} ta\n\n"
        f"🍿 <i>Kinoni tomosha qilish uchun quyidagi tugmani bosing:</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Kinoni ko'rish", url=f"https://t.me/{bot_username}?start=watch_{m['code']}")
        ],
        [
            InlineKeyboardButton(text="⭐ Saqlash", url=f"https://t.me/{bot_username}?start=save_{m['code']}"),
            InlineKeyboardButton(text="↗️ Ulashish", switch_inline_query=m['title'])
        ]
    ])

    lpo = LinkPreviewOptions(
        url=thumb,
        prefer_large_media=True,
        show_above_text=True
    )

    msg_content = InputTextMessageContent(
        message_text=caption,
        parse_mode="HTML",
        link_preview_options=lpo
    )
    return InlineQueryResultArticle(
        id=f"{prefix_id}_{m['id']}",
        title=title,
        description=desc,
        input_message_content=msg_content,
        reply_markup=kb,
        thumbnail_url=thumb
    )

@router.inline_query()
async def on_inline_query(inline_query: InlineQuery, bot: Bot, db: Database):
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    bot_username = config.BOT_USERNAME
    results = []

    try:
        has_access, missing = await check_user_access(bot, db, user_id)
        if not has_access:
            results.append(
                InlineQueryResultArticle(
                    id="sub_required",
                    title="⚠️ Homiy kanallarga a'zo bo'ling!",
                    description="Botdan foydalanish uchun majburiy kanallarga a'zo bo'lishingiz shart.",
                    input_message_content=InputTextMessageContent(
                        message_text="⚠️ <b>Botdan to'liq foydalanish uchun homiy kanallarga a'zo bo'ling!</b>\n\nBotga o'tib /start buyrug'ini bosing.",
                        parse_mode="HTML"
                    ),
                    thumbnail_url=DEFAULT_THUMB
                )
            )
            await inline_query.answer(results=results, cache_time=1, is_personal=True)
            return

        if query == "top_films" or query.startswith("top_films"):
            movies = await db.get_top_movies(limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_top",
                        title="Top filmlar topilmadi",
                        description="Hozircha botda filmlar mavjud emas.",
                        input_message_content=InputTextMessageContent(
                            message_text="ℹ️ Hozircha botda filmlar mavjud emas.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for idx, m in enumerate(movies, 1):
                    results.append(create_movie_article(m, bot_username, "top", f"{idx}. "))

        elif query == "saved_films" or query.startswith("saved_films"):
            movies = await db.get_user_saved_movies(user_id, limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_saved",
                        title="Saqlangan film topilmadi",
                        description="Siz hali hech qanday filmni saqlamadingiz.",
                        input_message_content=InputTextMessageContent(
                            message_text="ℹ️ Siz hali hech qanday filmni saqlamadingiz. Filmlar ostidagi '⭐ Saqlash' tugmasini bosib saqlab olishingiz mumkin.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "saved"))

        elif query.startswith("genre:"):
            genre = query.split(":", 1)[1].strip()
            movies = await db.get_filtered_movies(genre=genre, limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_genre",
                        title=f"'{genre.title()}' janrida film topilmadi",
                        description="Ushbu janrga oid boshqa filmlar tez orada qo'shiladi.",
                        input_message_content=InputTextMessageContent(
                            message_text=f"ℹ️ '{genre.title()}' janrida hozircha film topilmadi.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "genre"))

        elif query.startswith("country:"):
            country = query.split(":", 1)[1].strip()
            movies = await db.get_filtered_movies(country=country, limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_country",
                        title=f"'{country.title()}' davlatiga oid film topilmadi",
                        description="Ushbu davlatga oid filmlar tez orada qo'shiladi.",
                        input_message_content=InputTextMessageContent(
                            message_text=f"ℹ️ '{country.title()}' davlatiga oid hozircha film topilmadi.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "country"))

        elif query.startswith("lang:"):
            lang = query.split(":", 1)[1].strip()
            movies = await db.get_filtered_movies(language=lang, limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_lang",
                        title=f"'{lang.title()}' tilida film topilmadi",
                        description="Ushbu tildagi filmlar tez orada qo'shiladi.",
                        input_message_content=InputTextMessageContent(
                            message_text=f"ℹ️ '{lang.title()}' tilida hozircha film topilmadi.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "lang"))

        elif query.startswith("year:"):
            year_str = query.split(":", 1)[1].strip()
            year_val = int(year_str) if year_str.isdigit() else None
            movies = await db.get_filtered_movies(year=year_val, limit=30)
            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_year",
                        title=f"{year_str}-yil filmi topilmadi",
                        description="Ushbu yildagi filmlar tez orada qo'shiladi.",
                        input_message_content=InputTextMessageContent(
                            message_text=f"ℹ️ {year_str}-yilda chiqarilgan film hozircha topilmadi.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "year"))

        else:
            if not query:
                movies = await db.get_top_movies(limit=20)
            else:
                movies = await db.search_movies(query, limit=20)

            if not movies:
                results.append(
                    InlineQueryResultArticle(
                        id="no_search",
                        title=f"'{query}' bo'yicha film topilmadi",
                        description="Kino kodini kiritib ko'ring yoki boshqa nom bilan qidiring.",
                        input_message_content=InputTextMessageContent(
                            message_text=f"❌ <b>'{query}'</b> bo'yicha film topilmadi.\nKino kodini kiritib ko'ring yoki boshqa nom bilan qidiring.",
                            parse_mode="HTML"
                        ),
                        thumbnail_url=DEFAULT_THUMB
                    )
                )
            else:
                for m in movies:
                    results.append(create_movie_article(m, bot_username, "search"))

        await inline_query.answer(results=results, cache_time=2, is_personal=True)
    except Exception as e:
        logger.error(f"Error in on_inline_query: {e}", exc_info=True)

