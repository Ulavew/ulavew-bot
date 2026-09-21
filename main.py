# Файл: main.py
# Точка входа. Грузит коги автоматически.

import asyncio
import logging
import pkgutil

import discord
from discord.ext import commands

import cogs
from config import BOT_TOKEN, PREFIX
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Ulavew")


INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
INTENTS.moderation = True
INTENTS.guilds = True
INTENTS.bans = True


class TrustBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=INTENTS,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.db = Database()

    async def setup_hook(self):
        await self.db.connect()
        log.info("База данных подключена")

        # Автозагрузка всех когов из cogs/
        for _, module_name, _ in pkgutil.iter_modules(cogs.__path__):
            if module_name.startswith("_"):
                continue
            ext = f"cogs.{module_name}"
            try:
                await self.load_extension(ext)
                log.info("Загружен модуль: %s", ext)
            except Exception as e:
                log.exception("Ошибка загрузки %s: %s", ext, e)

        # Синхронизация слэш-команд (у нас только /setup_verify)
        await self.tree.sync()
        log.info("Слэш-команды синхронизированы")

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_ready(self):
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id)


async def main():
    bot = TrustBot()
    async with bot:
        await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлено вручную")