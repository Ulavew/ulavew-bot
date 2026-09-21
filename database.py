# Файл: database.py
# Асинхронная обёртка над SQLite.

import aiosqlite
from config import DB_NAME


class Database:
    def __init__(self, path: str = DB_NAME):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._migrate()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _create_tables(self):
        await self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id            INTEGER PRIMARY KEY,
            log_channel_id      INTEGER,
            verify_channel_id   INTEGER,
            verify_role_id      INTEGER,
            quarantine_role_id  INTEGER,
            auto_role_id        INTEGER,
            anti_raid_enabled   INTEGER DEFAULT 1,
            anti_crash_enabled  INTEGER DEFAULT 1,
            automod_enabled     INTEGER DEFAULT 1,
            raid_join_limit     INTEGER DEFAULT 10,
            raid_join_window    INTEGER DEFAULT 10,
            min_account_age     INTEGER DEFAULT 7
        );
        CREATE TABLE IF NOT EXISTS warns (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            moderator  INTEGER NOT NULL,
            reason     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        -- Кастомные роли модерации
        CREATE TABLE IF NOT EXISTS mod_roles (
            guild_id  INTEGER NOT NULL,
            action    TEXT NOT NULL,
            role_id   INTEGER NOT NULL,
            PRIMARY KEY (guild_id, action)
        );
        """)
        await self.conn.commit()

    async def _migrate(self):
        cur = await self.conn.execute("PRAGMA table_info(guild_settings)")
        existing = {row["name"] for row in await cur.fetchall()}
        needed = {
            "log_channel_id": "INTEGER",
            "verify_channel_id": "INTEGER",
            "verify_role_id": "INTEGER",
            "quarantine_role_id": "INTEGER",
            "auto_role_id": "INTEGER",
            "anti_raid_enabled": "INTEGER DEFAULT 1",
            "anti_crash_enabled": "INTEGER DEFAULT 1",
            "automod_enabled": "INTEGER DEFAULT 1",
            "raid_join_limit": "INTEGER DEFAULT 10",
            "raid_join_window": "INTEGER DEFAULT 10",
            "min_account_age": "INTEGER DEFAULT 7",
        }
        for col, typ in needed.items():
            if col not in existing:
                await self.conn.execute(
                    f"ALTER TABLE guild_settings ADD COLUMN {col} {typ}"
                )
        await self.conn.commit()

    # ---------- Настройки ----------
    async def get_settings(self, guild_id: int) -> dict:
        cur = await self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        row = await cur.fetchone()
        if row is None:
            await self.conn.execute(
                "INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
            )
            await self.conn.commit()
            cur = await self.conn.execute(
                "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
            )
            row = await cur.fetchone()
        return dict(row)

    async def update_setting(self, guild_id: int, key: str, value):
        allowed = {
            "log_channel_id", "verify_channel_id", "verify_role_id",
            "quarantine_role_id", "auto_role_id", "anti_raid_enabled",
            "anti_crash_enabled", "automod_enabled", "raid_join_limit",
            "raid_join_window", "min_account_age",
        }
        if key not in allowed:
            raise ValueError(f"Недопустимое поле: {key}")
        await self.conn.execute(
            f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?",
            (value, guild_id),
        )
        await self.conn.commit()

    # ---------- Варны ----------
    async def add_warn(self, guild_id, user_id, moderator, reason) -> int:
        cur = await self.conn.execute(
            "INSERT INTO warns (guild_id, user_id, moderator, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, moderator, reason),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_warns(self, guild_id: int, user_id: int) -> list[dict]:
        cur = await self.conn.execute(
            "SELECT * FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            (guild_id, user_id),
        )
        return [dict(r) for r in await cur.fetchall()]

    async def clear_warns(self, guild_id: int, user_id: int):
        await self.conn.execute(
            "DELETE FROM warns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await self.conn.commit()

    # ---------- Кастомные роли модерации ----------
    async def set_mod_role(self, guild_id: int, action: str, role_id: int):
        """Устанавливает роль для действия (ban/kick/mute/warn/unban)."""
        await self.conn.execute(
            "INSERT OR REPLACE INTO mod_roles (guild_id, action, role_id) VALUES (?, ?, ?)",
            (guild_id, action, role_id),
        )
        await self.conn.commit()

    async def get_mod_role(self, guild_id: int, action: str) -> int | None:
        """Возвращает ID роли для действия или None."""
        cur = await self.conn.execute(
            "SELECT role_id FROM mod_roles WHERE guild_id = ? AND action = ?",
            (guild_id, action),
        )
        row = await cur.fetchone()
        return row["role_id"] if row else None

    async def clear_mod_role(self, guild_id: int, action: str):
        """Убирает роль для действия."""
        await self.conn.execute(
            "DELETE FROM mod_roles WHERE guild_id = ? AND action = ?",
            (guild_id, action),
        )
        await self.conn.commit()