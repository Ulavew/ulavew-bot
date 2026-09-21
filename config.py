# Файл: config.py
# Константы и настройки бота.

import os

# Токен бота
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН")

# Имя файла БД
DB_NAME = "trustbot.db"

# Префикс команд
PREFIX = "!"

# ============ АНТИ-СПАМ (не меняется через меню) ============
SPAM_WINDOW = 7
SPAM_LIMIT = 5
SPAM_TIMEOUT_SECONDS = 600
CAPS_THRESHOLD = 0.7
CAPS_MIN_LENGTH = 10
MENTION_LIMIT = 5

# ============ СТУПЕНИ НАКАЗАНИЙ ============
WARNS_BEFORE_MUTE = 1
WARNS_BEFORE_KICK = 3
WARNS_BEFORE_BAN = 5

# ============ ЦВЕТА EMBED ============
COLOR_OK = 0x57F287
COLOR_WARN = 0xFEE75C
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2

# ============ БРЕНДИНГ ============
BOT_NAME = "Ulavew"
BOT_VERSION = "1.0"