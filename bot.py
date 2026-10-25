import asyncio
import logging
import sys
import os
from aiohttp import web

# Ensure UTF-8 output on Windows consoles
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
from database import Database
from handlers import (
    subscription_router,
    payment_router,
    admin_router,
    inline_router,
    user_router
)
from keyboards.inline import get_order_review_kb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def pending_orders_reminder_worker(bot: Bot, db: Database):
    """
    Every 10 minutes, checks for pending orders older than 2 hours that haven't been reminded recently.
    Sends reminder to ADMIN_GROUP_ID with action buttons.
    """
    logger.info("Pending orders reminder worker started.")
    while True:
        try:
            await asyncio.sleep(600)  # Check every 10 minutes
            target_chat = config.ADMIN_GROUP_ID or (config.ADMIN_IDS[0] if config.ADMIN_IDS else None)
            if not target_chat:
                continue

            overdue_orders = await db.get_overdue_pending_orders(hours=2)
            for order in overdue_orders:
                user_tag = f"@{order['username']}" if order.get("username") else f"ID: {order['user_id']}"
                price_str = f"{order['amount']:,}".replace(",", " ")

                reminder_text = (
                    f"⏰ <b>ESLATMA: Ko'rib chiqilmagan ariza!</b>\n\n"
                    f"⚠️ Ushbu to'lov cheki <b>2 soatdan ortiq vaqt</b> davomida kutilmoqda:\n\n"
                    f"🧾 <b>Ariza raqami:</b> #{order['id']}\n"
                    f"👤 <b>Foydalanuvchi:</b> {user_tag}\n"
                    f"📦 <b>Tarif:</b> {order['plan_name']} ({price_str} UZS)\n"
                    f"📅 <b>Yuborilgan vaqti:</b> {order['created_at']}\n\n"
                    f"<i>Iltimos, chekni tekshirib tasdiqlang yoki rad qiling:</i>"
                )

                review_kb = get_order_review_kb(order["id"])
                try:
                    await bot.send_photo(
                        chat_id=target_chat,
                        photo=order["receipt_file_id"],
                        caption=reminder_text,
                        reply_markup=review_kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    try:
                        await bot.send_document(
                            chat_id=target_chat,
                            document=order["receipt_file_id"],
                            caption=reminder_text,
                            reply_markup=review_kb,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send reminder for order #{order['id']}: {e}")

                await db.update_order_reminded(order["id"])

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in pending_orders_reminder_worker: {e}")

async def start_health_check_server():
    """
    Render Web Service port binding and external ping (UptimeRobot).
    Listens on the PORT env var provided by Render (or 8080 by default).
    """
    port = int(os.getenv("PORT", 8080))
    app = web.Application()

    async def handle_ping(request):
        return web.Response(text="Bot is running! 🚀\nVersion: 2.1-premium\nStatus: OK", content_type="text/plain")

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Health check HTTP server listening on port {port}")
    except Exception as e:
        logger.warning(f"Could not start health check HTTP server on port {port}: {e}")

async def main():
    logger.info("Initializing Kino Bot...")
    
    # Initialize Database
    db = Database(config.DATABASE_PATH)
    await db.init_db()

    # Pre-populate SuperAdmin from config
    for admin_id in config.ADMIN_IDS:
        await db.add_admin(admin_id, f"SuperAdmin ({admin_id})", role="superadmin")

    # Initialize Bot and Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Dependency injection: pass db to all handlers
    dp["db"] = db

    # Include routers in proper order
    dp.include_router(subscription_router)
    dp.include_router(payment_router)
    dp.include_router(admin_router)
    dp.include_router(inline_router)
    dp.include_router(user_router)

    # Set Telegram bot commands (with retry)
    for _ in range(5):
        try:
            await bot.set_my_commands([
                BotCommand(command="start", description="Botni ishga tushirish / Yangilash"),
                BotCommand(command="search", description="🔍 Film qidirish"),
                BotCommand(command="top", description="🎬 Top filmlar"),
                BotCommand(command="saved", description="⭐ Saqlangan filmlar"),
                BotCommand(command="premium", description="💎 VIP Obuna")
            ])
            break
        except Exception as e:
            logger.warning(f"Error setting commands (retrying in 2s): {e}")
            await asyncio.sleep(2)

    # Delete webhook to enable long polling cleanly
    for _ in range(5):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            bot_info = await bot.get_me()
            logger.info(f"Bot @{bot_info.username} is successfully running!")
            logger.info(f"SuperAdmin IDs: {config.ADMIN_IDS}")
            break
        except Exception as e:
            logger.warning(f"Error connecting to Telegram (retrying in 2s): {e}")
            await asyncio.sleep(2)

    # Start background reminder worker for unreviewed orders
    reminder_task = asyncio.create_task(pending_orders_reminder_worker(bot, db))

    # Start health check server for Render & UptimeRobot
    await start_health_check_server()

    # Start Polling with auto-reconnect
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=["message", "callback_query", "inline_query", "chat_join_request", "chat_member", "my_chat_member"]
            )
            break
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            logger.error(f"Polling error: {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)
    
    reminder_task.cancel()
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
