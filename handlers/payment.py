import logging
from aiogram import Router, F, Bot
from datetime import datetime
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import config
from database import Database
from keyboards.inline import (
    get_main_menu_kb,
    get_subscription_kb,
    get_pending_order_kb,
    get_order_status_kb,
    get_order_review_kb,
    get_mandatory_channels_kb
)

logger = logging.getLogger(__name__)
router = Router()

class PaymentState(StatesGroup):
    waiting_for_receipt = State()

class AdminRejectState(StatesGroup):
    waiting_for_reason = State()

@router.callback_query(F.data == "open_subscription")
async def on_open_subscription(callback: CallbackQuery, db: Database):
    user_id = callback.from_user.id
    is_premium = await db.is_user_premium(user_id)
    pending_order = await db.get_pending_order_by_user(user_id)
    settings = await db.get_all_settings()

    if is_premium:
        user = await db.get_user(user_id)
        until_raw = user.get("premium_until") if user else None
        until = datetime.fromisoformat(until_raw) if isinstance(until_raw, str) else until_raw
        now = datetime.now()

        if until and until > now:
            delta = until - now
            days_left = delta.days
            hours_left = int(delta.seconds // 3600)
            if days_left > 0:
                time_str = f"<b>{days_left}</b> kun, <b>{hours_left}</b> soat"
            else:
                time_str = f"<b>{hours_left}</b> soat"
            until_str = until.strftime("%d.%m.%Y %H:%M")
        else:
            time_str = "Tugagan"
            until_str = "—"

        status_text = (
            "💎 <b>Sizning Premium obunangiz faol!</b>\n\n"
            f"⏳ <b>Qolgan muddat:</b> {time_str}\n"
            f"📅 <b>Tugash vaqti:</b> {until_str}\n\n"
            "✨ <b>Sizning imtiyozlaringiz:</b>\n"
            "• Barcha filmlar to'liq ochilgan\n"
            "• Reklamasiz va cheksiz tomosha\n"
            "• Homiy kanallarga a'zo bo'lish talab qilinmaydi\n\n"
            "🔄 <i>Obunani hozirdanoq uzaytirishingiz mumkin! Yangi muddat avvalgi qolgan muddatingizga to'liq qo'shiladi.</i>"
        )
        if pending_order:
            price_str = f"{pending_order['amount']:,}".replace(",", " ")
            status_text += (
                f"\n\n🕒 <b>Ko'rib chiqilayotgan uzaytirish arizangiz bor:</b>\n"
                f"<i>{pending_order['plan_name']} · {price_str} UZS</i>"
            )

        buttons = [
            [InlineKeyboardButton(text="🔄 Obunani uzaytirish", callback_data="extend_subscription")]
        ]
        if pending_order:
            buttons.append([InlineKeyboardButton(text="🕒 Arizam holati", callback_data=f"view_my_order:{pending_order['id']}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="back_to_main")])

        await callback.message.edit_text(status_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        return

    base_text = settings.get("premium_text") or (
        "💎 <b>Eng Sara Filmlar Premium</b>\n\n"
        "◾️ Premium film va seriallar to'liq ochiladi\n"
        "◾️ Film olishda reklamaga o'tish talab qilinmaydi\n"
        "◾️ Obuna muddati davomida cheksiz tomosha\n\n"
        "⬇️ <b>Quyidagi tariflardan birini tanlang</b>"
    )

    if pending_order:
        price_str = f"{pending_order['amount']:,}".replace(",", " ")
        text = (
            f"{base_text}\n\n"
            f"🕒 <b>Sizda ko'rib chiqilayotgan ariza bor</b>\n"
            f"<i>{pending_order['plan_name']} · {price_str} UZS</i>"
        )
        await callback.message.edit_text(text, reply_markup=get_pending_order_kb(pending_order["id"]), parse_mode="HTML")
    else:
        await callback.message.edit_text(base_text, reply_markup=get_subscription_kb(), parse_mode="HTML")

@router.callback_query(F.data == "extend_subscription")
async def on_extend_subscription(callback: CallbackQuery, db: Database):
    user_id = callback.from_user.id
    pending_order = await db.get_pending_order_by_user(user_id)
    if pending_order:
        price_str = f"{pending_order['amount']:,}".replace(",", " ")
        text = (
            "🕒 <b>Sizda allaqachon ko'rib chiqilayotgan ariza mavjud!</b>\n\n"
            f"💎 <b>Tarif:</b> {pending_order['plan_name']}\n"
            f"💰 <b>Summa:</b> {price_str} UZS\n\n"
            "<i>Adminlar chekni tekshirib tasdiqlagach, ushbu muddat mavjud obunangizga avtomatik qo'shiladi.</i>"
        )
        await callback.message.edit_text(text, reply_markup=get_pending_order_kb(pending_order["id"]), parse_mode="HTML")
        return

    text = (
        "💎 <b>Premium obunani uzaytirish</b>\n\n"
        "Quyidagi tariflardan birini tanlang. Tanlangan muddat mavjud obunangizga to'liq qo'shiladi!\n\n"
        "<i>(Masalan, obunangiz tugashiga 5 kun qolgan bo'lsa va 1 oylik olsangiz, umumiy 35 kun bo'ladi)</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_subscription_kb(back_callback="open_subscription"), parse_mode="HTML")

@router.callback_query(F.data.startswith("view_my_order:"))
async def on_view_my_order(callback: CallbackQuery, db: Database):
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Ariza topilmadi!", show_alert=True)
        return

    price_str = f"{order['amount']:,}".replace(",", " ")
    created_at = str(order.get("created_at", ""))
    if len(created_at) >= 16:
        parts = created_at.split()
        d_parts = parts[0].split("-")
        if len(d_parts) == 3:
            created_at = f"{d_parts[2]}.{d_parts[1]}.{d_parts[0]} {parts[1][:5]}"

    text = (
        "🕒 <b>Arizangiz ko'rib chiqilmoqda</b>\n\n"
        f"🧾 <b>Ariza:</b> #{order['id']}\n"
        f"💎 <b>Tarif:</b> {order['plan_name']} ({order['duration_days']} kun)\n"
        f"💰 <b>Summa:</b> {price_str} UZS\n"
        f"📅 <b>Yuborilgan:</b> {created_at}\n\n"
        "<i>Tasdiqlangach obuna avtomatik yoqiladi va sizga xabar keladi. Agar chekni xato yuborgan bo'lsangiz, arizani bekor qilib qaytadan yuborishingiz mumkin</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_order_status_kb(order["id"]), parse_mode="HTML")

@router.callback_query(F.data.startswith("cancel_my_order:"))
async def on_cancel_my_order(callback: CallbackQuery, db: Database):
    order_id = int(callback.data.split(":")[1])
    cancelled = await db.cancel_order(order_id, callback.from_user.id)
    if cancelled:
        await callback.answer("🗑 Arizangiz bekor qilindi!", show_alert=True)
    else:
        await callback.answer("Arizani bekor qilib bo'lmadi yoki allaqachon ko'rib chiqilgan.", show_alert=True)

    settings = await db.get_all_settings()
    base_text = settings.get("premium_text") or (
        "💎 <b>Eng Sara Filmlar Premium</b>\n\n"
        "◾️ Premium film va seriallar to'liq ochiladi\n"
        "◾️ Film olishda reklamaga o'tish talab qilinmaydi\n"
        "◾️ Obuna muddati davomida cheksiz tomosha\n\n"
        "⬇️ <b>Quyidagi tariflardan birini tanlang</b>"
    )
    await callback.message.edit_text(base_text, reply_markup=get_subscription_kb(), parse_mode="HTML")

@router.callback_query(F.data == "back_to_main")
async def on_back_to_main(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    await state.clear()
    settings = await db.get_all_settings()
    greeting = settings.get("start_text") or (
        "👋 <b>Assalomu alaykum , botimizga xush kelibsiz</b>\n\n"
        "🎬 Bot orqali siz sevimli filmlar, seriallar va multfilmlarni sifatli formatda ko'rishingiz mumkin\n\n"
        "🚀 <b>Shunchaki:</b>\n"
        "— Kino yoki serialning kodini yuboring\n"
        "— Pastdagi bo'limlardan birini tanlang va zavqlaning! 😉"
    )
    try:
        await callback.message.edit_text(greeting, reply_markup=get_main_menu_kb(settings), parse_mode="HTML")
    except Exception:
        await callback.message.answer(greeting, reply_markup=get_main_menu_kb(settings), parse_mode="HTML")

@router.callback_query(F.data.startswith("buy_plan:"))
async def on_select_plan(callback: CallbackQuery, state: FSMContext):
    plan_key = callback.data.split(":")[1]
    plan = config.TARIFFS.get(plan_key)
    if not plan:
        await callback.answer("Tarif topilmadi!", show_alert=True)
        return

    await state.update_data(plan_key=plan_key)
    await state.set_state(PaymentState.waiting_for_receipt)

    price_str = f"{plan['price']:,}".replace(",", " ")
    text = (
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"📦 <b>Tanlangan tarif:</b> {plan['name']} ({price_str} UZS)\n"
        f"⏳ <b>Amal qilish muddati:</b> {plan['days']} kun\n\n"
        f"💳 <b>Karta raqami:</b> <code>{config.CARD_NUMBER}</code>\n"
        f"👤 <b>Karta egasi:</b> {config.CARD_HOLDER}\n\n"
        f"📥 <i>To'lovni amalga oshirib, to'lov cheki rasmi (skrinshot)ni shu yerga yuboring:</i>"
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Bekor qilish / Ortga", callback_data="open_subscription")
    ]])
    await callback.message.answer(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "get_free_sub")
async def on_get_free(callback: CallbackQuery, db: Database):
    channels = await db.get_all_channels()
    if channels:
        text = (
            "🎁 <b>Bepul tomosha qilish uchun quyidagi homiy kanallarga a'zo bo'ling:</b>\n\n"
            "<i>(Barcha kanallarga a'zo bo'lgach yoki ariza yuborgach, '✅ Obunani tekshirish' tugmasini bosing)</i>"
        )
        await callback.message.edit_text(text, reply_markup=get_mandatory_channels_kb(channels), parse_mode="HTML")
    else:
        text = (
            "🎁 <b>Tabriklaymiz!</b>\n\n"
            "Hozirda hech qanday homiy kanal majburiy emas. Barcha filmlarni bepul tomosha qilishingiz mumkin!\n"
            "Shunchaki kino kodini yoki nomini chatga yuboring."
        )
        home_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")
        ]])
        await callback.message.answer(text, reply_markup=home_kb, parse_mode="HTML")
    await callback.answer()

@router.message(PaymentState.waiting_for_receipt, F.photo | F.document)
async def on_receipt_received(message: Message, state: FSMContext, bot: Bot, db: Database):
    data = await state.get_data()
    plan_key = data.get("plan_key", "1_month")
    plan = config.TARIFFS.get(plan_key, config.TARIFFS["1_month"])

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    # Save to database
    order_id = await db.create_order(
        user_id=message.from_user.id,
        plan_name=plan["name"],
        amount=plan["price"],
        duration_days=plan["days"],
        receipt_file_id=file_id
    )
    await state.clear()

    # Reply to user
    user_receipt_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Arizam holati", callback_data=f"view_my_order:{order_id}")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
    ])
    await message.reply(
        "✅ <b>To'lov chekingiz qabul qilindi!</b>\n\n"
        "Adminlar chekni tekshirib chiqqach, obunangiz avtomatik ravishda faollashtiriladi.",
        reply_markup=user_receipt_kb,
        parse_mode="HTML"
    )

    # Forward receipt to Admin Group or Admins
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "Mavjud emas"
    price_str = f"{plan['price']:,}".replace(",", " ")
    admin_caption = (
        f"🆕 <b>Yangi to'lov cheki!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {user.full_name} ({username_str})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📦 <b>Tarif:</b> {plan['name']} ({price_str} UZS)\n"
        f"⏳ <b>Muddat:</b> {plan['days']} kun\n"
        f"🔢 <b>Buyurtma raqami:</b> #{order_id}"
    )

    review_kb = get_order_review_kb(order_id)

    target_chats = []
    if config.ADMIN_GROUP_ID:
        target_chats.append(config.ADMIN_GROUP_ID)
    else:
        # Fallback to configured admin IDs
        target_chats.extend(config.ADMIN_IDS)

    for target in target_chats:
        try:
            if message.photo:
                await bot.send_photo(chat_id=target, photo=file_id, caption=admin_caption, reply_markup=review_kb, parse_mode="HTML")
            else:
                await bot.send_document(chat_id=target, document=file_id, caption=admin_caption, reply_markup=review_kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send receipt to admin chat {target}: {e}")

@router.callback_query(F.data.startswith("order_approve:"))
async def on_order_approve(callback: CallbackQuery, bot: Bot, db: Database):
    order_id = int(callback.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    if order["status"] != "pending":
        await callback.answer(f"Ushbu buyurtma allaqachon ko'rib chiqilgan ({order['status']})!", show_alert=True)
        return

    # Update database
    await db.update_order_status(order_id, "approved")
    new_until = await db.set_user_premium(order["user_id"], order["duration_days"])

    # Notify user
    try:
        user_approved_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎬 Filmlarni tomosha qilish", callback_data="back_to_main")
        ]])
        await bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"🎉 <b>Tabriklaymiz! To'lovingiz tasdiqlandi.</b>\n\n"
                f"💎 Sizga <b>{order['duration_days']} kunlik</b> Premium obuna faollashtirildi!\n"
                f"📅 Amal qilish muddati: <b>{new_until.strftime('%Y-%m-%d %H:%M')}</b> gacha.\n\n"
                f"Endi botdan cheksiz, reklamasiz va majburiy kanallarsiz foydalanishingiz mumkin! 🍿"
            ),
            reply_markup=user_approved_kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {order['user_id']} of approval: {e}")

    admin_tag = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    new_caption = f"{callback.message.caption or callback.message.text}\n\n✅ <b>TASDIQLANDI</b> (Admin: {admin_tag})"
    try:
        await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    except Exception:
        await callback.message.edit_text(text=new_caption, parse_mode="HTML")
    await callback.answer("✅ Buyurtma tasdiqlandi!")

@router.callback_query(F.data.startswith("order_reject:"))
async def on_order_reject(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(reject_order_id=order_id, reject_msg_id=callback.message.message_id, reject_chat_id=callback.message.chat.id)
    await state.set_state(AdminRejectState.waiting_for_reason)

    await callback.message.reply(
        f"✍️ <b>Buyurtma #{order_id}</b> ni rad qilish sababini yozib yuboring:\n"
        f"<i>(Masalan: Chek soxta, to'lov kelib tushmadi, yoki to'lov summasi to'liq emas)</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminRejectState.waiting_for_reason)
async def on_rejection_reason_entered(message: Message, state: FSMContext, bot: Bot, db: Database):
    data = await state.get_data()
    order_id = data.get("reject_order_id")
    orig_msg_id = data.get("reject_msg_id")
    orig_chat_id = data.get("reject_chat_id")
    reason = message.text.strip()

    await state.clear()
    order = await db.get_order(order_id)
    if not order:
        await message.reply("Buyurtma topilmadi!")
        return

    await db.update_order_status(order_id, "rejected", reject_reason=reason)

    # Notify user
    try:
        user_rejected_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Qayta urinib ko'rish", callback_data="open_subscription")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
        ])
        await bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"❌ <b>To'lovingiz rad etildi!</b>\n\n"
                f"📌 <b>Sabab:</b> {reason}\n\n"
                f"Iltimos, qaytadan to'g'ri chekni yuboring yoki admin bilan bog'laning."
            ),
            reply_markup=user_rejected_kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {order['user_id']} of rejection: {e}")

    admin_tag = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await message.reply(f"✅ Buyurtma #{order_id} rad etildi va foydalanuvchiga xabar yuborildi.")

    if orig_chat_id and orig_msg_id:
        try:
            note = f"\n\n❌ <b>RAD ETILDI</b>\nSababi: {reason}\n(Admin: {admin_tag})"
            await bot.edit_message_caption(chat_id=orig_chat_id, message_id=orig_msg_id, caption=note, parse_mode="HTML")
        except Exception:
            pass
