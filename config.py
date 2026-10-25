import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8684376265:AAEY9zIGtDP35AVhOx7pwzMDe4Ab0nNQ5go")
BOT_USERNAME = os.getenv("BOT_USERNAME", "EngSaraFilmlarUzBot")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "EngSaraFilmlarUzBot")

# Admin IDs (comma separated integers)
raw_admins = os.getenv("ADMIN_IDS", "6873538625")
ADMIN_IDS = [int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()]

# Admin verification group (where payment receipts are forwarded)
raw_group = os.getenv("ADMIN_GROUP_ID", "").strip()
if raw_group:
    if raw_group.startswith("-"):
        ADMIN_GROUP_ID = int(raw_group)
    else:
        ADMIN_GROUP_ID = int(f"-100{raw_group}" if len(raw_group) >= 9 else f"-{raw_group}")
else:
    ADMIN_GROUP_ID = None

# Payment details
CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 0000 0000 0000")
CARD_HOLDER = os.getenv("CARD_HOLDER", "Admin")

# Database
DATABASE_PATH = str(BASE_DIR / os.getenv("DATABASE_PATH", "bot_database.sqlite3"))

# Premium Tariffs
TARIFFS = {
    "1_month": {"name": "1 oy", "price": 15000, "days": 30, "label": "1 oy - 15 000 UZS"},
    "3_month": {"name": "3 oy", "price": 40000, "days": 90, "label": "3 oy - 40 000 UZS"},
    "6_month": {"name": "6 oy", "price": 75000, "days": 180, "label": "6 oy - 75 000 UZS"},
    "12_month": {"name": "12 oy", "price": 140000, "days": 365, "label": "12 oy - 140 000 UZS"},
}
