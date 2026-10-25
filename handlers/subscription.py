import logging
from aiogram import Router, F, Bot
from aiogram.types import ChatJoinRequest, ChatMemberUpdated, CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from database import Database
from keyboards.inline import get_main_menu_kb, get_mandatory_channels_kb

logger = logging.getLogger(__name__)
router = Router()

async def check_user_access(bot: Bot, db: Database, user_id: int):
    """
    Checks if user has access to bot features.
    1. Premium users ALWAYS have access (exempt from mandatory channels).
    2. Otherwise, user must be a member or have submitted an active join request to each mandatory channel.
    Returns: (has_access: bool, missing_channels: list)
    """
    # 1. Premium check
    if await db.is_user_premium(user_id):
        return True, []

    # 2. Channel check
    channels = await db.get_all_channels()
    if not channels:
        return True, []

    missing_channels = []
    for ch in channels:
        ch_id = str(ch["channel_id"])
        alt_id = ch_id.replace("-100", "") if ch_id.startswith("-100") else f"-100{ch_id.lstrip('-')}"
        is_private = bool(ch.get("is_private", 0)) or not ch_id.startswith("@")

        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["creator", "administrator", "member", "restricted"]:
                # User is actively in channel
                continue
            elif member.status == "kicked":
                # User was banned/kicked from channel -> Delete join request and block
                await db.delete_join_request(user_id, ch_id)
                missing_channels.append(ch)
                continue
            elif member.status == "left":
                # User is not currently a member.
                # If it's a private channel, verify if user has a valid pending join request
                if is_private:
                    if await db.has_user_join_request(user_id, ch_id) or await db.has_user_join_request(user_id, alt_id):
                        continue
                missing_channels.append(ch)
            else:
                missing_channels.append(ch)
        except TelegramBadRequest as e:
            # If bot cannot check membership directly, check join request
            if await db.has_user_join_request(user_id, ch_id) or await db.has_user_join_request(user_id, alt_id):
                continue
            missing_channels.append(ch)
        except Exception as e:
            logger.warning(f"Error checking channel {ch_id} for user {user_id}: {e}")
            missing_channels.append(ch)

    if not missing_channels:
        return True, []
    return False, missing_channels

@router.chat_member()
async def handle_chat_member_updated(event: ChatMemberUpdated, db: Database):
    """
    Catches when a user leaves or is kicked from any mandatory channel.
    Immediately deletes their join request so they can no longer access the bot.
    """
    user_id = event.new_chat_member.user.id
    chat_id = str(event.chat.id)
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    logger.info(f"ChatMemberUpdated: User {user_id} in {chat_id} changed from {old_status} to {new_status}")

    if new_status in ["left", "kicked"]:
        await db.delete_join_request(user_id, chat_id)
        logger.info(f"User {user_id} left/kicked channel {chat_id}. Removed join request.")

@router.chat_join_request()
async def handle_chat_join_request(event: ChatJoinRequest, db: Database):
    """
    Catches join requests to private channels.
    Even before admin approves the request, the user gets credit and can watch movies!
    """
    user_id = event.from_user.id
    chat_id = str(event.chat.id)
    await db.record_join_request(user_id, chat_id)
    if chat_id.startswith("-100"):
        await db.record_join_request(user_id, chat_id.replace("-100", ""))
    logger.info(f"Recorded join request: User {user_id} -> Channel {chat_id}")

@router.callback_query(F.data == "check_subscription")
async def on_check_subscription(callback: CallbackQuery, bot: Bot, db: Database):
    has_access, missing = await check_user_access(bot, db, callback.from_user.id)
    if has_access:
        await callback.answer("✅ Obuna tasdiqlandi!", show_alert=False)
        greeting = (
            "👋 <b>Assalomu alaykum , botimizga xush kelibsiz</b>\n\n"
            "🎬 Bot orqali siz sevimli filmlar, seriallar va multfilmlarni sifatli formatda ko'rishingiz mumkin\n\n"
            "🚀 <b>Shunchaki:</b>\n"
            "— Kino yoki serialning kodini yuboring\n"
            "— Pastdagi bo'limlardan birini tanlang va zavqlaning! 😉"
        )
        try:
            await callback.message.edit_text(greeting, reply_markup=get_main_menu_kb(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(greeting, reply_markup=get_main_menu_kb(), parse_mode="HTML")
    else:
        await callback.answer("⚠️ Hali barcha kanallarga a'zo bo'lmadingiz yoki ariza yubormadingiz!", show_alert=True)
