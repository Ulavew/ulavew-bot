# Файл: cogs/anti_crash.py
# Анти-краш — следит за действиями админов через audit log.
# Лимиты берутся из БД (пока редактируются только через config по умолчанию).

import time
import logging
from collections import defaultdict, deque

import discord
from discord.ext import commands

from config import COLOR_ERROR

log = logging.getLogger("TrustBot.AntiCrash")

WINDOW = 10
LIMIT_CHANNEL = 3
LIMIT_ROLE = 3
LIMIT_BAN = 5


class AntiCrash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.actions = defaultdict(lambda: defaultdict(lambda: defaultdict(deque)))

    async def _check(self, guild, actor, action, limit) -> bool:
        now = time.time()
        dq = self.actions[guild.id][actor.id][action]
        dq.append(now)
        while dq and now - dq[0] > WINDOW:
            dq.popleft()
        return len(dq) > limit

    async def _punish(self, guild, actor, action):
        # Снимаем опасные роли
        dangerous = [
            r for r in actor.roles
            if r.permissions.administrator
            or r.permissions.manage_guild
            or r.permissions.ban_members
            or r.permissions.manage_channels
            or r.permissions.manage_roles
        ]
        try:
            if dangerous:
                await actor.remove_roles(*dangerous, reason=f"ANTI-CRASH: {action}")
        except discord.Forbidden:
            log.warning("Не могу снять роли с %s", actor)

        # Уведомление владельцу
        try:
            if guild.owner:
                await guild.owner.send(
                    f"🚨 **ANTI-CRASH** на **{guild.name}**\n"
                    f"{actor.mention} массово делал `{action}`. Роли сняты."
                )
        except discord.Forbidden:
            pass

        # Лог-канал
        s = await self.bot.db.get_settings(guild.id)
        if s["log_channel_id"]:
            ch = guild.get_channel(s["log_channel_id"])
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(embed=discord.Embed(
                        title="🚨 ANTI-CRASH",
                        description=f"{actor.mention} — `{action}`. Роли сняты.",
                        color=COLOR_ERROR,
                    ))
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        s = await self.bot.db.get_settings(channel.guild.id)
        if not s["anti_crash_enabled"]:
            return
        async for entry in channel.guild.audit_logs(
            limit=1, action=discord.AuditLogAction.channel_delete
        ):
            if isinstance(entry.user, discord.Member):
                if await self._check(channel.guild, entry.user, "channel_delete", LIMIT_CHANNEL):
                    await self._punish(channel.guild, entry.user, "channel_delete")
            break

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        s = await self.bot.db.get_settings(role.guild.id)
        if not s["anti_crash_enabled"]:
            return
        async for entry in role.guild.audit_logs(
            limit=1, action=discord.AuditLogAction.role_delete
        ):
            if isinstance(entry.user, discord.Member):
                if await self._check(role.guild, entry.user, "role_delete", LIMIT_ROLE):
                    await self._punish(role.guild, entry.user, "role_delete")
            break

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        s = await self.bot.db.get_settings(guild.id)
        if not s["anti_crash_enabled"]:
            return
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if isinstance(entry.user, discord.Member):
                if await self._check(guild, entry.user, "ban", LIMIT_BAN):
                    await self._punish(guild, entry.user, "ban")
            break


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiCrash(bot))