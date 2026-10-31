import aiosqlite
from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Dict, Any
import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def connect(self):
        return await aiosqlite.connect(self.db_path)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    is_premium INTEGER DEFAULT 0,
                    premium_until TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Movies table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    caption TEXT,
                    quality TEXT DEFAULT '1080p',
                    language TEXT DEFAULT "O'zbek",
                    genre TEXT DEFAULT 'Boshqa',
                    country TEXT DEFAULT 'AQSH',
                    year INTEGER DEFAULT 2024,
                    poster_file_id TEXT,
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                await db.execute("ALTER TABLE movies ADD COLUMN poster_file_id TEXT")
            except Exception:
                pass

            try:
                await db.execute("ALTER TABLE movies ADD COLUMN poster_url TEXT")
            except Exception:
                pass

            # Saved movies (Bookmarks)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS saved_movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, movie_id)
                )
            """)

            # Mandatory channels
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    is_private INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Channel join requests (tracks user applications to private channels)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, channel_id)
                )
            """)

            # Admins table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    role TEXT DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Subscription orders / receipts
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_name TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    duration_days INTEGER NOT NULL,
                    receipt_file_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reject_reason TEXT,
                    last_reminded_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                await db.execute("ALTER TABLE orders ADD COLUMN last_reminded_at TIMESTAMP")
            except Exception:
                pass

            # Settings table (for customizable texts, buttons, owner_id)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Genres table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS genres (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            # Languages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS languages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            # Pre-populate default genres if empty
            cur = await db.execute("SELECT COUNT(*) FROM genres")
            count_g = (await cur.fetchone())[0]
            if count_g == 0:
                defaults = ["Jangari", "Sarguzasht", "Komediya", "Drama", "Fantastika", "Qo'rqinchli", "Multfilm", "Melodrama", "Triller", "Kriminal", "Tarixiy", "Oilaviy"]
                for g in defaults:
                    await db.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (g,))

            # Pre-populate default languages if empty
            cur = await db.execute("SELECT COUNT(*) FROM languages")
            count_l = (await cur.fetchone())[0]
            if count_l == 0:
                defaults = ["O'zbek", "Rus", "Ingliz", "Turk", "Koreys", "Subtitr"]
                for l in defaults:
                    await db.execute("INSERT OR IGNORE INTO languages (name) VALUES (?)", (l,))

            # Serials table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS serials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    poster_file_id TEXT,
                    poster_url TEXT,
                    language TEXT DEFAULT 'O''zbek',
                    genre TEXT DEFAULT 'Boshqa',
                    country TEXT DEFAULT 'AQSH',
                    year INTEGER DEFAULT 2024,
                    quality TEXT DEFAULT '1080p',
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seasons table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS seasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    serial_id INTEGER NOT NULL REFERENCES serials(id) ON DELETE CASCADE,
                    season_number INTEGER NOT NULL,
                    season_name TEXT NOT NULL DEFAULT '1-fasl',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(serial_id, season_number)
                )
            """)

            # Episodes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    serial_id INTEGER NOT NULL REFERENCES serials(id) ON DELETE CASCADE,
                    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
                    episode_number INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(season_id, episode_number)
                )
            """)

            await db.commit()
            logger.info("Database initialized successfully.")

    # ------------------ USERS ------------------
    async def add_or_update_user(self, user_id: int, username: Optional[str], full_name: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, last_activity)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_activity = CURRENT_TIMESTAMP
            """, (user_id, username, full_name))
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def is_user_premium(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT is_premium, premium_until FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or not row[0]:
                return False
            if row[1]:
                until = datetime.fromisoformat(row[1]) if isinstance(row[1], str) else row[1]
                if datetime.now() > until:
                    # Expired
                    await db.execute("UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,))
                    await db.commit()
                    return False
            return True

    async def set_user_premium(self, user_id: int, days: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            now = datetime.now()
            if row and row[0]:
                current_until = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0]
                start_date = max(now, current_until)
            else:
                start_date = now
            
            new_until = start_date + timedelta(days=days)
            await db.execute("""
                UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?
            """, (new_until.isoformat(), user_id))
            await db.commit()
            return new_until

    async def get_active_premium_users(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT user_id, username, full_name, premium_until, created_at
                FROM users
                WHERE is_premium = 1
                ORDER BY premium_until ASC
            """)
            rows = await cursor.fetchall()
            now = datetime.now()
            res = []
            for r in rows:
                p_until = r["premium_until"]
                if p_until:
                    try:
                        until = datetime.fromisoformat(p_until) if isinstance(p_until, str) else p_until
                        if now > until:
                            continue
                    except Exception:
                        pass
                res.append(dict(r))
            return res

    async def revoke_user_premium(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_broadcast_recipients(self, exclude_premium: bool = True) -> List[int]:
        """
        Returns a list of user IDs to send broadcasts to.
        If exclude_premium is True, excludes users who currently have an active premium subscription.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id, is_premium, premium_until FROM users")
            rows = await cursor.fetchall()
            now = datetime.now()
            recipients = []
            for uid, is_prem, prem_until in rows:
                if exclude_premium and is_prem:
                    if prem_until:
                        try:
                            until = datetime.fromisoformat(prem_until) if isinstance(prem_until, str) else prem_until
                            if now <= until:
                                continue  # Active premium user, skip!
                        except Exception:
                            pass
                recipients.append(uid)
            return recipients

    # ------------------ MOVIES ------------------
    async def add_movie(self, code: str, title: str, file_id: str, file_type: str,
                        caption: str, quality: str, language: str, genre: str,
                        country: str, year: int, poster_file_id: Optional[str] = None,
                        poster_url: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO movies (code, title, file_id, file_type, caption, quality, language, genre, country, year, poster_file_id, poster_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, title, file_id, file_type, caption, quality, language, genre, country, year, poster_file_id, poster_url))
            await db.commit()
            return cursor.lastrowid

    async def update_movie_poster(self, movie_id: int, poster_file_id: str, poster_url: Optional[str] = None):
        async with aiosqlite.connect(self.db_path) as db:
            if poster_url:
                await db.execute("UPDATE movies SET poster_file_id = ?, poster_url = ? WHERE id = ?", (poster_file_id, poster_url, movie_id))
            else:
                await db.execute("UPDATE movies SET poster_file_id = ? WHERE id = ?", (poster_file_id, movie_id))
            await db.commit()

    async def get_movie_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM movies WHERE code = ?", (code.strip(),))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def search_movies(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            pattern = f"%{query.strip()}%"
            cursor = await db.execute("""
                SELECT * FROM movies 
                WHERE title LIKE ? OR code LIKE ? OR genre LIKE ?
                ORDER BY views DESC LIMIT ?
            """, (pattern, pattern, pattern, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_top_movies(self, limit: int = 25) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM movies ORDER BY views DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_filtered_movies(self, genre: Optional[str] = None, country: Optional[str] = None,
                                  language: Optional[str] = None, year: Optional[int] = None,
                                  limit: int = 25) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM movies WHERE 1=1"
            params = []
            if genre:
                query += " AND genre LIKE ?"
                params.append(f"%{genre}%")
            if country:
                query += " AND country LIKE ?"
                params.append(f"%{country}%")
            if language:
                query += " AND language LIKE ?"
                params.append(f"%{language}%")
            if year:
                query += " AND year = ?"
                params.append(year)
            query += " ORDER BY views DESC LIMIT ?"
            params.append(limit)
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def increment_movie_views(self, movie_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE movies SET views = views + 1 WHERE id = ?", (movie_id,))
            await db.commit()

    async def delete_movie_by_code(self, code: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM movies WHERE code = ?", (code.strip(),))
            await db.commit()
            return cursor.rowcount > 0

    # ------------------ SAVED MOVIES ------------------
    async def toggle_save_movie(self, user_id: int, movie_id: int) -> bool:
        """Returns True if now saved, False if removed"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id FROM saved_movies WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
            row = await cursor.fetchone()
            if row:
                await db.execute("DELETE FROM saved_movies WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
                await db.commit()
                return False
            else:
                await db.execute("INSERT INTO saved_movies (user_id, movie_id) VALUES (?, ?)", (user_id, movie_id))
                await db.commit()
                return True

    async def is_movie_saved(self, user_id: int, movie_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id FROM saved_movies WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
            row = await cursor.fetchone()
            return bool(row)

    async def get_user_saved_movies(self, user_id: int, limit: int = 25) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT m.* FROM movies m
                INNER JOIN saved_movies s ON m.id = s.movie_id
                WHERE s.user_id = ?
                ORDER BY s.created_at DESC LIMIT ?
            """, (user_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ------------------ CHANNELS & JOIN REQUESTS ------------------
    async def add_channel(self, channel_id: str, title: str, url: str, is_private: bool = False):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO channels (channel_id, title, url, is_private)
                VALUES (?, ?, ?, ?)
            """, (str(channel_id), title, url, 1 if is_private else 0))
            await db.commit()

    async def get_all_channels(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channels ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_channel(self, channel_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM channels WHERE channel_id = ?", (str(channel_id),))
            await db.commit()
            return cursor.rowcount > 0

    async def record_join_request(self, user_id: int, channel_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO join_requests (user_id, channel_id)
                VALUES (?, ?)
            """, (user_id, str(channel_id)))
            await db.commit()

    async def has_user_join_request(self, user_id: int, channel_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id FROM join_requests WHERE user_id = ? AND channel_id = ?
            """, (user_id, str(channel_id)))
            row = await cursor.fetchone()
            return bool(row)

    async def delete_join_request(self, user_id: int, channel_id: str):
        ch_id = str(channel_id)
        alt_id = ch_id.replace("-100", "") if ch_id.startswith("-100") else f"-100{ch_id.lstrip('-')}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM join_requests
                WHERE user_id = ? AND (channel_id = ? OR channel_id = ?)
            """, (user_id, ch_id, alt_id))
            await db.commit()

    # ------------------ ADMINS ------------------
    async def is_admin(self, user_id: int, extra_admins: List[int] = None) -> bool:
        if extra_admins and user_id in extra_admins:
            return True
        owner_id = await self.get_owner_id()
        if user_id == owner_id:
            return True
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return bool(row)

    async def add_admin(self, user_id: int, full_name: str, role: str = 'admin'):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO admins (user_id, full_name, role)
                VALUES (?, ?, ?)
            """, (user_id, full_name, role))
            await db.commit()

    async def delete_admin(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_all_admins(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM admins ORDER BY created_at ASC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ------------------ ORDERS / RECEIPTS ------------------
    async def create_order(self, user_id: int, plan_name: str, amount: int, duration_days: int, receipt_file_id: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO orders (user_id, plan_name, amount, duration_days, receipt_file_id)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, plan_name, amount, duration_days, receipt_file_id))
            await db.commit()
            return cursor.lastrowid

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_order_status(self, order_id: int, status: str, reject_reason: Optional[str] = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE orders SET status = ?, reject_reason = ? WHERE id = ?
            """, (status, reject_reason, order_id))
            await db.commit()

    async def get_pending_order_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM orders 
                WHERE user_id = ? AND status = 'pending' 
                ORDER BY id DESC LIMIT 1
            """, (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def cancel_order(self, order_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE orders SET status = 'cancelled' 
                WHERE id = ? AND user_id = ? AND status = 'pending'
            """, (order_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_overdue_pending_orders(self, hours: int = 2) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"""
                SELECT o.*, u.username, u.full_name FROM orders o
                LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status = 'pending'
                AND (
                    (o.last_reminded_at IS NULL AND o.created_at <= datetime('now', '-{hours} hours'))
                    OR (o.last_reminded_at <= datetime('now', '-{hours} hours'))
                )
            """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_order_reminded(self, order_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE orders SET last_reminded_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (order_id,))
            await db.commit()

    # ------------------ STATS & MONITORING ------------------
    async def get_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            # Total users
            cur = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cur.fetchone())[0]

            # Today active users
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE date(last_activity) = date('now')")
            active_today = (await cur.fetchone())[0]

            # Premium users
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            premium_users = (await cur.fetchone())[0]

            # Total movies
            cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(views), 0) FROM movies")
            movie_row = await cur.fetchone()
            total_movies = movie_row[0]
            total_views = movie_row[1]

            return {
                "total_users": total_users,
                "active_today": active_today,
                "premium_users": premium_users,
                "total_movies": total_movies,
                "total_views": total_views,
            }

    # ------------------ SETTINGS & TEXTS ------------------
    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            """, (key, value))
            await db.commit()

    async def get_all_settings(self) -> Dict[str, str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM settings")
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}

    async def get_owner_id(self) -> int:
        owner = await self.get_setting("owner_id")
        if owner and owner.isdigit():
            return int(owner)
        if config.ADMIN_IDS:
            return config.ADMIN_IDS[0]
        return 6873538625

    async def transfer_owner(self, new_owner_id: int, new_owner_name: str = "SuperAdmin"):
        await self.set_setting("owner_id", str(new_owner_id))
        await self.add_admin(new_owner_id, new_owner_name, role="superadmin")

    async def reset_custom_settings(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM settings WHERE key != 'owner_id'")
            await db.commit()

    # ------------------ GENRES ------------------
    async def get_all_genres(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM genres ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    async def add_genre(self, name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO genres (name) VALUES (?)", (name.strip(),))
                await db.commit()
                return True
            except Exception:
                return False

    async def delete_genre(self, name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM genres WHERE name = ?", (name.strip(),))
            await db.commit()
            return cursor.rowcount > 0

    # ------------------ LANGUAGES ------------------
    async def get_all_languages(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM languages ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    async def add_language(self, name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO languages (name) VALUES (?)", (name.strip(),))
                await db.commit()
                return True
            except Exception:
                return False

    async def delete_language(self, name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM languages WHERE name = ?", (name.strip(),))
            await db.commit()
            return cursor.rowcount > 0

    # ================== SERIALS ==================
    async def add_serial(self, code: str, title: str, poster_file_id: str, poster_url: str,
                         language: str, genre: str, country: str, year: int, quality: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT OR REPLACE INTO serials (code, title, poster_file_id, poster_url, language, genre, country, year, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, title, poster_file_id, poster_url, language, genre, country, year, quality))
            await db.commit()
            return cursor.lastrowid

    async def get_serial_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM serials WHERE code = ?", (code,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_serial_by_id(self, serial_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM serials WHERE id = ?", (serial_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_serials(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM serials ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def search_serials(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM serials WHERE LOWER(title) LIKE LOWER(?) OR code = ? ORDER BY views DESC LIMIT ?",
                (f"%{query}%", query, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_or_create_season(self, serial_id: int, season_number: int, season_name: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM seasons WHERE serial_id = ? AND season_number = ?",
                (serial_id, season_number)
            )
            row = await cursor.fetchone()
            if row:
                return row['id']
            cursor2 = await db.execute(
                "INSERT INTO seasons (serial_id, season_number, season_name) VALUES (?, ?, ?)",
                (serial_id, season_number, season_name)
            )
            await db.commit()
            return cursor2.lastrowid

    async def get_seasons(self, serial_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT s.*, COUNT(e.id) as episode_count
                FROM seasons s
                LEFT JOIN episodes e ON e.season_id = s.id
                WHERE s.serial_id = ?
                GROUP BY s.id
                ORDER BY s.season_number ASC
            """, (serial_id,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def add_episode(self, serial_id: int, season_id: int, episode_number: int,
                          file_id: str, file_type: str = 'video') -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT OR REPLACE INTO episodes (serial_id, season_id, episode_number, file_id, file_type)
                VALUES (?, ?, ?, ?, ?)
            """, (serial_id, season_id, episode_number, file_id, file_type))
            await db.commit()
            return cursor.lastrowid

    async def get_episodes(self, season_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM episodes WHERE season_id = ? ORDER BY episode_number ASC",
                (season_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_episode(self, season_id: int, episode_number: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM episodes WHERE season_id = ? AND episode_number = ?",
                (season_id, episode_number)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_next_episode_number(self, season_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT MAX(episode_number) FROM episodes WHERE season_id = ?", (season_id,))
            row = await cursor.fetchone()
            return (row[0] or 0) + 1

    async def increment_serial_views(self, serial_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE serials SET views = views + 1 WHERE id = ?", (serial_id,))
            await db.commit()

    async def delete_serial_by_code(self, code: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM serials WHERE code = ?", (code,))
            await db.commit()
            return cursor.rowcount > 0


