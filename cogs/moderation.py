# Файл: cogs/moderation.py
# Автомод + слэш-команды модерации с поддержкой кастомных ролей.

import re
import time
import asyncio
import logging
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    SPAM_WINDOW, SPAM_LIMIT, SPAM_TIMEOUT_SECONDS,
    CAPS_THRESHOLD, CAPS_MIN_LENGTH, MENTION_LIMIT,
    WARNS_BEFORE_MUTE, WARNS_BEFORE_KICK, WARNS_BEFORE_BAN,
    COLOR_WARN, COLOR_OK, COLOR_ERROR,
)

log = logging.getLogger("Ulavew.Moderation")

INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9\-]+)")
CAPS_RE = re.compile(r"[A-ZА-ЯЁ]")


# =====================================================================
# ПАРСЕР ВРЕМЕНИ
# =====================================================================
TIME_UNITS = {"с": 1, "s": 1, "м": 60, "m": 60, "ч": 3600, "h": 3600, "д": 86400, "d": 86400}
TIME_HINT = "Формат: `10м`, `1ч`, `2д`, `30с`."


def parse_time(text: str) -> int | None:
    if not text:
        return None
    text = text.strip().lower()
    if not text or text[-1] not in TIME_UNITS:
        return None
    try:
        v = int(text[:-1])
        if v <= 0:
            return None
        return v * TIME_UNITS[text[-1]]
    except ValueError:
        return None


def humanize(sec: int) -> str:
    d, h = sec // 86400, (sec % 86400) // 3600
    m, s = (sec % 3600) // 60, sec % 60
    parts = []
    if d: parts.append(f"{d} дн.")
    if h: parts.append(f"{h} ч.")
    if m and not d: parts.append(f"{m} мин.")
    if s and not d and not h: parts.append(f"{s} сек.")
    return " ".join(parts) if parts else "0 сек."


# =====================================================================
# ПРОВЕРКА ПРАВ
# =====================================================================
async def has_mod_right(interaction: discord.Interaction, action: str) -> bool:
    """
    Проверяет, имеет ли пользователь право на действие.
    Приоритет:
      1. Владелец сервера — всегда да
      2. Стандартное право Discord
      3. Кастомная роль из БД
    """
    user = interaction.user
    guild = interaction.guild
    if user.id == guild.owner_id:
        return True

    # Стандартные права Discord
    perms = user.guild_permissions
    if action in ("ban", "unban") and perms.ban_members:
        return True
    if action == "kick" and perms.kick_members:
        return True
    if action in ("mute", "unmute", "warn", "warns") and perms.moderate_members:
        return True
    if action == "clearwarns" and perms.administrator:
        return True

    # Кастомная роль
    role_id = await interaction.client.db.get_mod_role(guild.id, action)
    if role_id:
        role = guild.get_role(role_id)
        if role and role in user.roles:
            return True
    return False


async def deny_rights(interaction: discord.Interaction, action: str):
    """Отправляет приватный отказ."""
    msg = (
        f"❌ У вас нет прав на действие **`{action}`**.\n"
        f"Попросите владельца сервера выдать вам соответствующую роль "
        f"через меню `/ulavew` → 👮 Роли модерации."
    )
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spam = defaultdict(lambda: defaultdict(deque))

    # =================================================================
    # АВТОМОД (без изменений)
    # =================================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.author.guild_permissions.administrator:
            return
        s = await self.bot.db.get_settings(message.guild.id)
        if not s["automod_enabled"]:
            return
        content = message.content or ""

        now = time.time()
        dq = self.spam[message.guild.id][message.author.id]
        dq.append(now)
        while dq and now - dq[0] > SPAM_WINDOW:
            dq.popleft()
        if len(dq) > SPAM_LIMIT:
            return await self._violate(message, "Спам сообщениями")
        if len(message.mentions) > MENTION_LIMIT or message.mention_everyone:
            return await self._violate(message, "Массовые упоминания")
        letters = [c for c in content if c.isalpha()]
        if len(letters) >= CAPS_MIN_LENGTH:
            if len(CAPS_RE.findall(content)) / len(letters) >= CAPS_THRESHOLD:
                return await self._violate(message, "Избыточный CAPS")
        if INVITE_RE.search(content):
            return await self._violate(message, "Запрещённая инвайт-ссылка")

    async def _violate(self, message, reason):
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        await self.bot.db.add_warn(message.guild.id, message.author.id,
                                   self.bot.user.id, reason)
        warns = await self.bot.db.get_warns(message.guild.id, message.author.id)
        count = len(warns)
        action = "предупреждение"
        try:
            if count >= WARNS_BEFORE_BAN:
                await message.author.ban(reason=reason, delete_message_days=1)
                action = "бан"
            elif count >= WARNS_BEFORE_KICK:
                await message.author.kick(reason=reason)
                action = "кик"
            elif count >= WARNS_BEFORE_MUTE:
                await message.author.timeout(
                    discord.utils.utcnow() + timedelta(seconds=SPAM_TIMEOUT_SECONDS),
                    reason=reason,
                )
                action = f"мут на {humanize(SPAM_TIMEOUT_SECONDS)}"
        except discord.Forbidden:
            action = "не удалось (нет прав)"
        s = await self.bot.db.get_settings(message.guild.id)
        if s["log_channel_id"]:
            ch = message.guild.get_channel(s["log_channel_id"])
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=discord.Embed(
                        title="🛡️ Автомод — Ulavew",
                        description=(
                            f"**Нарушитель:** {message.author.mention}\n"
                            f"**Причина:** {reason}\n"
                            f"**Варнов:** {count}\n"
                            f"**Наказание:** {action}"
                        ),
                        color=COLOR_WARN,
                    ))
                except discord.Forbidden:
                    pass

    # =================================================================
    # /ban
    # =================================================================
    @app_commands.command(name="ban", description="🔨 Забанить участника (можно на время)")
    @app_commands.describe(
        member="Кого забанить",
        reason="Причина бана",
        time="Время бана: 10м, 1ч, 2д. Пусто — навсегда",
        delete_days="Удалить сообщения за N дней (0–7)",
    )
    async def ban_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Не указана",
        time: str = "",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        if not await has_mod_right(interaction, "ban"):
            return await deny_rights(interaction, "ban")

        if member.top_role >= interaction.user.top_role \
                and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ Нельзя забанить участника с ролью выше или равной твоей.",
                ephemeral=True,
            )
        duration = None
        if time:
            duration = parse_time(time)
            if duration is None:
                return await interaction.response.send_message(
                    f"❌ Неверный формат времени: `{time}`\n{TIME_HINT}",
                    ephemeral=True,
                )
        await interaction.response.defer()
        try:
            await member.ban(
                reason=f"{reason} | Модератор: {interaction.user}",
                delete_message_days=delete_days,
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ У бота нет прав забанить этого участника."
            )
        if duration:
            until_ts = int(time.time()) + duration
            text = (
                f"🔨 **{member.mention}** забанен на **{humanize(duration)}**.\n"
                f"**Причина:** {reason}\n**Разбан:** <t:{until_ts}:R>"
            )
            asyncio.create_task(self._schedule_unban(
                interaction.guild, member.id, duration,
                f"Временный бан истёк ({humanize(duration)})",
            ))
        else:
            text = f"🔨 **{member.mention}** забанен навсегда.\n**Причина:** {reason}"
        await interaction.followup.send(text)
        await self._log_action(
            interaction.guild, "🔨 Бан",
            f"{member.mention} — {reason}"
            + (f" | Срок: {humanize(duration)}" if duration else " | Навсегда"),
            COLOR_ERROR,
        )

    async def _schedule_unban(self, guild, user_id: int, seconds: int, reason: str):
        await asyncio.sleep(seconds)
        try:
            await guild.unban(discord.Object(id=user_id), reason=f"Ulavew: {reason}")
            s = await self.bot.db.get_settings(guild.id)
            if s["log_channel_id"]:
                ch = guild.get_channel(s["log_channel_id"])
                if isinstance(ch, discord.TextChannel):
                    try:
                        await ch.send(embed=discord.Embed(
                            title="♻️ Авто-разбан — Ulavew",
                            description=f"<@{user_id}> разбанен: {reason}",
                            color=COLOR_OK,
                        ))
                    except discord.Forbidden:
                        pass
        except (discord.NotFound, discord.Forbidden):
            pass

    # =================================================================
    # /unban
    # =================================================================
    @app_commands.command(name="unban", description="♻️ Разбанить пользователя по ID")
    @app_commands.describe(user_id="ID пользователя", reason="Причина")
    async def unban_cmd(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "Не указана",
    ):
        if not await has_mod_right(interaction, "unban"):
            return await deny_rights(interaction, "unban")
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message(
                "❌ ID должен быть числом.", ephemeral=True
            )
        try:
            await interaction.guild.unban(
                discord.Object(id=uid),
                reason=f"{reason} | Модератор: {interaction.user}",
            )
        except discord.NotFound:
            return await interaction.response.send_message(
                "❌ Этот пользователь не в бане.", ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ У бота нет прав разбанить.", ephemeral=True
            )
        await interaction.response.send_message(
            f"♻️ Пользователь `<@{uid}>` разбанен.\n**Причина:** {reason}"
        )
        await self._log_action(
            interaction.guild, "♻️ Разбан",
            f"<@{uid}> — {reason}", COLOR_OK,
        )

    # =================================================================
    # /kick
    # =================================================================
    @app_commands.command(name="kick", description="👢 Кикнуть участника")
    @app_commands.describe(member="Кого кикнуть", reason="Причина")
    async def kick_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Не указана",
    ):
        if not await has_mod_right(interaction, "kick"):
            return await deny_rights(interaction, "kick")
        if member.top_role >= interaction.user.top_role \
                and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ Нельзя кикнуть участника с ролью выше или равной твоей.",
                ephemeral=True,
            )
        try:
            await member.kick(reason=f"{reason} | Модератор: {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ У бота нет прав кикнуть этого участника.", ephemeral=True
            )
        await interaction.response.send_message(
            f"👢 **{member.mention}** кикнут.\n**Причина:** {reason}"
        )
        await self._log_action(
            interaction.guild, "👢 Кик", f"{member.mention} — {reason}", COLOR_WARN,
        )

    # =================================================================
    # /mute
    # =================================================================
    @app_commands.command(name="mute", description="🔇 Выдать мут (таймаут)")
    @app_commands.describe(
        member="Кого замутить",
        time="Длительность: 10м, 1ч, 2д, 30с",
        reason="Причина мута",
    )
    async def mute_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        time: str = "10м",
        reason: str = "Не указана",
    ):
        if not await has_mod_right(interaction, "mute"):
            return await deny_rights(interaction, "mute")
        if member.top_role >= interaction.user.top_role \
                and interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ Нельзя замутить участника с ролью выше или равной твоей.",
                ephemeral=True,
            )
        duration = parse_time(time)
        if duration is None:
            return await interaction.response.send_message(
                f"❌ Неверный формат времени: `{time}`\n{TIME_HINT}",
                ephemeral=True,
            )
        if duration > 28 * 86400:
            return await interaction.response.send_message(
                "❌ Максимальная длительность мута — **28 дней**.", ephemeral=True
            )
        try:
            await member.timeout(
                discord.utils.utcnow() + timedelta(seconds=duration),
                reason=f"{reason} | Модератор: {interaction.user}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ У бота нет прав замутить этого участника.", ephemeral=True
            )
        until_ts = int(time.time()) + duration
        await interaction.response.send_message(
            f"🔇 **{member.mention}** получил мут на **{humanize(duration)}**.\n"
            f"**Причина:** {reason}\n**Окончание:** <t:{until_ts}:R>"
        )
        await self._log_action(
            interaction.guild, "🔇 Мут",
            f"{member.mention} — {reason} | Срок: {humanize(duration)}",
            COLOR_WARN,
        )

    # =================================================================
    # /unmute
    # =================================================================
    @app_commands.command(name="unmute", description="🔊 Снять мут")
    @app_commands.describe(member="С кого снять мут")
    async def unmute_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if not await has_mod_right(interaction, "mute"):
            return await deny_rights(interaction, "mute")
        try:
            await member.timeout(None, reason=f"Снято: {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ У бота нет прав снять мут.", ephemeral=True
            )
        await interaction.response.send_message(f"🔊 С **{member.mention}** снят мут.")
        await self._log_action(interaction.guild, "🔊 Размут",
                               f"{member.mention}", COLOR_OK)

    # =================================================================
    # /warn
    # =================================================================
    @app_commands.command(name="warn", description="⚠️ Выдать предупреждение")
    @app_commands.describe(member="Кому выдать варн", reason="Причина")
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Не указана",
    ):
        if not await has_mod_right(interaction, "warn"):
            return await deny_rights(interaction, "warn")
        await self.bot.db.add_warn(
            interaction.guild.id, member.id, interaction.user.id, reason
        )
        warns = await self.bot.db.get_warns(interaction.guild.id, member.id)
        await interaction.response.send_message(
            f"⚠️ **{member.mention}** получил предупреждение.\n"
            f"**Причина:** {reason}\n**Всего варнов:** {len(warns)}"
        )
        await self._log_action(interaction.guild, "⚠️ Варн",
                               f"{member.mention} — {reason}", COLOR_WARN)

    # =================================================================
    # /warns
    # =================================================================
    @app_commands.command(name="warns", description="📋 Показать варны")
    @app_commands.describe(member="Чьи варны")
    async def warns_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if not await has_mod_right(interaction, "warn"):
            return await deny_rights(interaction, "warn")
        warns = await self.bot.db.get_warns(interaction.guild.id, member.id)
        if not warns:
            return await interaction.response.send_message(
                f"У **{member.mention}** нет предупреждений.", ephemeral=True
            )
        lines = [f"`#{w['id']}` <@{w['moderator']}> — {w['reason']}" for w in warns[:15]]
        await interaction.response.send_message(
            f"**Предупреждения {member.mention}** ({len(warns)}):\n" + "\n".join(lines),
            ephemeral=True,
        )

    # =================================================================
    # /clearwarns
    # =================================================================
    @app_commands.command(name="clearwarns", description="🗑 Сбросить варны")
    @app_commands.describe(member="У кого сбросить")
    async def clearwarns_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if not await has_mod_right(interaction, "clearwarns"):
            return await deny_rights(interaction, "clearwarns")
        await self.bot.db.clear_warns(interaction.guild.id, member.id)
        await interaction.response.send_message(
            f"✅ Предупреждения **{member.mention}** сброшены.", ephemeral=True
        )

    # ---------- Логирование ----------
    async def _log_action(self, guild, title, text, color):
        s = await self.bot.db.get_settings(guild.id)
        if not s["log_channel_id"]:
            return
        ch = guild.get_channel(s["log_channel_id"])
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=discord.Embed(
                    title=f"{title} — Ulavew", description=text, color=color,
                ))
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))