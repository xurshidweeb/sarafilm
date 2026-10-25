import asyncpg
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any
import config

logger = logging.getLogger(__name__)

class PostgresDatabase:
    def __init__(self, database_url: str):
        # Normalize url: asyncpg doesn't support 'channel_binding' parameter in url
        # Strip unsupported parameters if present
        clean_url = database_url.replace("&channel_binding=require", "").replace("channel_binding=require&", "").replace("channel_binding=require", "")
        self.database_url = clean_url
        self.pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=1,
                max_size=10,
                ssl="require"
            )
        return self.pool

    async def init_db(self):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    is_premium INTEGER DEFAULT 0,
                    premium_until TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Movies table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    caption TEXT,
                    quality TEXT DEFAULT '1080p',
                    language TEXT DEFAULT 'O''zbek',
                    genre TEXT DEFAULT 'Boshqa',
                    country TEXT DEFAULT 'AQSH',
                    year INTEGER DEFAULT 2024,
                    poster_file_id TEXT,
                    poster_url TEXT,
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Saved movies (Bookmarks)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_movies (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, movie_id)
                );
            """)

            # Mandatory channels
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    is_private INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Channel join requests
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    channel_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, channel_id)
                );
            """)

            # Admins table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    role TEXT DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Subscription orders / receipts
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    plan_name TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    duration_days INTEGER NOT NULL,
                    receipt_file_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reject_reason TEXT,
                    last_reminded_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Settings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            # Genres table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS genres (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
            """)

            # Languages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS languages (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
            """)

            # Pre-populate default genres if empty
            count_g = await conn.fetchval("SELECT COUNT(*) FROM genres;")
            if count_g == 0:
                defaults = ["Jangari", "Sarguzasht", "Komediya", "Drama", "Fantastika", "Qo'rqinchli", "Multfilm", "Melodrama", "Triller", "Kriminal", "Tarixiy", "Oilaviy"]
                for g in defaults:
                    await conn.execute("INSERT INTO genres (name) VALUES ($1) ON CONFLICT DO NOTHING;", g)

            # Pre-populate default languages if empty
            count_l = await conn.fetchval("SELECT COUNT(*) FROM languages;")
            if count_l == 0:
                defaults = ["O'zbek", "Rus", "Ingliz", "Turk", "Koreys", "Subtitr"]
                for l in defaults:
                    await conn.execute("INSERT INTO languages (name) VALUES ($1) ON CONFLICT DO NOTHING;", l)

        logger.info("Neon PostgreSQL Database initialized successfully.")

    # ------------------ USERS ------------------
    async def add_or_update_user(self, user_id: int, username: Optional[str], full_name: str):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, full_name, last_activity)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    last_activity = CURRENT_TIMESTAMP;
            """, user_id, username, full_name)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1;", user_id)
            return dict(row) if row else None

    async def is_user_premium(self, user_id: int) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT is_premium, premium_until FROM users WHERE user_id = $1;", user_id)
            if not row or not row["is_premium"]:
                return False
            if row["premium_until"]:
                until = row["premium_until"]
                if isinstance(until, str):
                    until = datetime.fromisoformat(until)
                if datetime.now() > until:
                    await conn.execute("UPDATE users SET is_premium = 0 WHERE user_id = $1;", user_id)
                    return False
            return True

    async def set_user_premium(self, user_id: int, days: int):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT premium_until FROM users WHERE user_id = $1;", user_id)
            now = datetime.now()
            if row and row["premium_until"]:
                current_until = row["premium_until"]
                if isinstance(current_until, str):
                    current_until = datetime.fromisoformat(current_until)
                start_date = max(now, current_until)
            else:
                start_date = now
            
            new_until = start_date + timedelta(days=days)
            await conn.execute("""
                UPDATE users SET is_premium = 1, premium_until = $1 WHERE user_id = $2;
            """, new_until, user_id)
            return new_until

    async def get_active_premium_users(self) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, username, full_name, premium_until, created_at
                FROM users
                WHERE is_premium = 1 AND (premium_until IS NULL OR premium_until > NOW())
                ORDER BY premium_until ASC;
            """)
            return [dict(r) for r in rows]

    async def revoke_user_premium(self, user_id: int):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = $1;", user_id)

    async def get_broadcast_recipients(self, exclude_premium: bool = True) -> List[int]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, is_premium, premium_until FROM users;")
            now = datetime.now()
            recipients = []
            for r in rows:
                uid = r["user_id"]
                is_prem = r["is_premium"]
                prem_until = r["premium_until"]
                if exclude_premium and is_prem:
                    if prem_until:
                        try:
                            until = datetime.fromisoformat(prem_until) if isinstance(prem_until, str) else prem_until
                            if now <= until:
                                continue
                        except Exception:
                            pass
                recipients.append(uid)
            return recipients

    # ------------------ MOVIES ------------------
    async def add_movie(self, code: str, title: str, file_id: str, file_type: str,
                        caption: str, quality: str, language: str, genre: str,
                        country: str, year: int, poster_file_id: Optional[str] = None,
                        poster_url: Optional[str] = None) -> int:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            movie_id = await conn.fetchval("""
                INSERT INTO movies (code, title, file_id, file_type, caption, quality, language, genre, country, year, poster_file_id, poster_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id;
            """, code, title, file_id, file_type, caption, quality, language, genre, country, year, poster_file_id, poster_url)
            return movie_id

    async def update_movie_poster(self, movie_id: int, poster_file_id: str, poster_url: Optional[str] = None):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            if poster_url:
                await conn.execute("UPDATE movies SET poster_file_id = $1, poster_url = $2 WHERE id = $3;", poster_file_id, poster_url, movie_id)
            else:
                await conn.execute("UPDATE movies SET poster_file_id = $1 WHERE id = $2;", poster_file_id, movie_id)

    async def get_movie_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM movies WHERE code = $1;", code.strip())
            return dict(row) if row else None

    async def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM movies WHERE id = $1;", movie_id)
            return dict(row) if row else None

    async def search_movies(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            pattern = f"%{query.strip()}%"
            rows = await conn.fetch("""
                SELECT * FROM movies 
                WHERE title ILIKE $1 OR code ILIKE $1 OR genre ILIKE $1
                ORDER BY views DESC LIMIT $2;
            """, pattern, limit)
            return [dict(r) for r in rows]

    async def get_top_movies(self, limit: int = 25) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM movies ORDER BY views DESC LIMIT $1;", limit)
            return [dict(r) for r in rows]

    async def get_filtered_movies(self, genre: Optional[str] = None, country: Optional[str] = None,
                                  language: Optional[str] = None, year: Optional[int] = None,
                                  limit: int = 25) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM movies WHERE 1=1"
            params = []
            if genre:
                params.append(f"%{genre}%")
                query += f" AND genre ILIKE ${len(params)}"
            if country:
                params.append(f"%{country}%")
                query += f" AND country ILIKE ${len(params)}"
            if language:
                params.append(f"%{language}%")
                query += f" AND language ILIKE ${len(params)}"
            if year:
                params.append(year)
                query += f" AND year = ${len(params)}"
            params.append(limit)
            query += f" ORDER BY views DESC LIMIT ${len(params)};"
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def increment_movie_views(self, movie_id: int):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE movies SET views = views + 1 WHERE id = $1;", movie_id)

    async def delete_movie_by_code(self, code: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("DELETE FROM movies WHERE code = $1;", code.strip())
            return not status.endswith(" 0")

    # ------------------ SAVED MOVIES ------------------
    async def toggle_save_movie(self, user_id: int, movie_id: int) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM saved_movies WHERE user_id = $1 AND movie_id = $2;", user_id, movie_id)
            if row:
                await conn.execute("DELETE FROM saved_movies WHERE user_id = $1 AND movie_id = $2;", user_id, movie_id)
                return False
            else:
                await conn.execute("INSERT INTO saved_movies (user_id, movie_id) VALUES ($1, $2);", user_id, movie_id)
                return True

    async def is_movie_saved(self, user_id: int, movie_id: int) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM saved_movies WHERE user_id = $1 AND movie_id = $2;", user_id, movie_id)
            return bool(row)

    async def get_user_saved_movies(self, user_id: int, limit: int = 25) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT m.* FROM movies m
                INNER JOIN saved_movies s ON m.id = s.movie_id
                WHERE s.user_id = $1
                ORDER BY s.created_at DESC LIMIT $2;
            """, user_id, limit)
            return [dict(r) for r in rows]

    # ------------------ CHANNELS & JOIN REQUESTS ------------------
    async def add_channel(self, channel_id: str, title: str, url: str, is_private: bool = False):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO channels (channel_id, title, url, is_private)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (channel_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    url = EXCLUDED.url,
                    is_private = EXCLUDED.is_private;
            """, str(channel_id), title, url, 1 if is_private else 0)

    async def get_all_channels(self) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM channels ORDER BY id ASC;")
            return [dict(r) for r in rows]

    async def delete_channel(self, channel_id: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("DELETE FROM channels WHERE channel_id = $1;", str(channel_id))
            return not status.endswith(" 0")

    async def record_join_request(self, user_id: int, channel_id: str):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO join_requests (user_id, channel_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, channel_id) DO NOTHING;
            """, user_id, str(channel_id))

    async def has_user_join_request(self, user_id: int, channel_id: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id FROM join_requests WHERE user_id = $1 AND channel_id = $2;
            """, user_id, str(channel_id))
            return bool(row)

    async def delete_join_request(self, user_id: int, channel_id: str):
        ch_id = str(channel_id)
        alt_id = ch_id.replace("-100", "") if ch_id.startswith("-100") else f"-100{ch_id.lstrip('-')}"
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM join_requests
                WHERE user_id = $1 AND (channel_id = $2 OR channel_id = $3);
            """, user_id, ch_id, alt_id)

    # ------------------ ADMINS ------------------
    async def is_admin(self, user_id: int, extra_admins: List[int] = None) -> bool:
        if extra_admins and user_id in extra_admins:
            return True
        owner_id = await self.get_owner_id()
        if user_id == owner_id:
            return True
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT user_id FROM admins WHERE user_id = $1;", user_id)
            return bool(row)

    async def add_admin(self, user_id: int, full_name: str, role: str = 'admin'):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO admins (user_id, full_name, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role;
            """, user_id, full_name, role)

    async def delete_admin(self, user_id: int) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("DELETE FROM admins WHERE user_id = $1;", user_id)
            return not status.endswith(" 0")

    async def get_all_admins(self) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM admins ORDER BY created_at ASC;")
            return [dict(r) for r in rows]

    # ------------------ ORDERS / RECEIPTS ------------------
    async def create_order(self, user_id: int, plan_name: str, amount: int, duration_days: int, receipt_file_id: str) -> int:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            order_id = await conn.fetchval("""
                INSERT INTO orders (user_id, plan_name, amount, duration_days, receipt_file_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id;
            """, user_id, plan_name, amount, duration_days, receipt_file_id)
            return order_id

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1;", order_id)
            return dict(row) if row else None

    async def update_order_status(self, order_id: int, status: str, reject_reason: Optional[str] = None):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE orders SET status = $1, reject_reason = $2 WHERE id = $3;
            """, status, reject_reason, order_id)

    async def get_pending_order_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM orders 
                WHERE user_id = $1 AND status = 'pending' 
                ORDER BY id DESC LIMIT 1;
            """, user_id)
            return dict(row) if row else None

    async def cancel_order(self, order_id: int, user_id: int) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("""
                UPDATE orders SET status = 'cancelled' 
                WHERE id = $1 AND user_id = $2 AND status = 'pending';
            """, order_id, user_id)
            return not status.endswith(" 0")

    async def get_overdue_pending_orders(self, hours: int = 2) -> List[Dict[str, Any]]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT o.*, u.username, u.full_name FROM orders o
                LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status = 'pending'
                AND (
                    (o.last_reminded_at IS NULL AND o.created_at <= NOW() - INTERVAL '{hours} hours')
                    OR (o.last_reminded_at <= NOW() - INTERVAL '{hours} hours')
                );
            """)
            return [dict(r) for r in rows]

    async def update_order_reminded(self, order_id: int):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE orders SET last_reminded_at = CURRENT_TIMESTAMP WHERE id = $1;", order_id)

    # ------------------ STATS & MONITORING ------------------
    async def get_stats(self) -> Dict[str, Any]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users;")
            active_today = await conn.fetchval("SELECT COUNT(*) FROM users WHERE last_activity::date = CURRENT_DATE;")
            premium_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_premium = 1;")
            movie_row = await conn.fetchrow("SELECT COUNT(*), COALESCE(SUM(views), 0) FROM movies;")
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
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT value FROM settings WHERE key = $1;", key)
            return val if val is not None else default

    async def set_setting(self, key: str, value: str):
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """, key, value)

    async def get_all_settings(self) -> Dict[str, str]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM settings;")
            return {r["key"]: r["value"] for r in rows}

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
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM settings WHERE key != 'owner_id';")

    # ------------------ GENRES ------------------
    async def get_all_genres(self) -> List[str]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name FROM genres ORDER BY id ASC;")
            return [r["name"] for r in rows]

    async def add_genre(self, name: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                await conn.execute("INSERT INTO genres (name) VALUES ($1) ON CONFLICT (name) DO NOTHING;", name.strip())
                return True
            except Exception:
                return False

    async def delete_genre(self, name: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("DELETE FROM genres WHERE name = $1;", name.strip())
            return not status.endswith(" 0")

    # ------------------ LANGUAGES ------------------
    async def get_all_languages(self) -> List[str]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name FROM languages ORDER BY id ASC;")
            return [r["name"] for r in rows]

    async def add_language(self, name: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            try:
                await conn.execute("INSERT INTO languages (name) VALUES ($1) ON CONFLICT (name) DO NOTHING;", name.strip())
                return True
            except Exception:
                return False

    async def delete_language(self, name: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            status = await conn.execute("DELETE FROM languages WHERE name = $1;", name.strip())
            return not status.endswith(" 0")
