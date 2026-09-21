# Файл: cogs/logging_cog.py
# Расширенное логирование событий сервера.

import logging

import discord
from discord.ext import commands

from config import COLOR_OK, COLOR_WARN, COLOR_ERROR

log = logging.getLogger("TrustBot.Logging")


class LoggingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send(self, guild, embed):
        s = await self.bot.db.get_settings(guild.id)
        if not s["log_channel_id"]:
            return
        ch = guild.get_channel(s["log_channel_id"])
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._send(channel.guild, discord.Embed(
            title="📁 Канал создан",
            description=f"{channel.mention} (`{channel.id}`)",
            color=COLOR_OK,
        ))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self._send(channel.guild, discord.Embed(
            title="🗑️ Канал удалён",
            description=f"`{channel.name}` (`{channel.id}`)",
            color=COLOR_ERROR,
        ))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._send(role.guild, discord.Embed(
            title="🎭 Роль создана",
            description=f"{role.mention} (`{role.id}`)",
            color=COLOR_OK,
        ))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._send(role.guild, discord.Embed(
            title="🗑️ Роль удалена",
            description=f"`{role.name}` (`{role.id}`)",
            color=COLOR_ERROR,
        ))

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self._send(guild, discord.Embed(
            title="🔨 Бан",
            description=f"{user.mention} (`{user.id}`)",
            color=COLOR_ERROR,
        ))

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self._send(guild, discord.Embed(
            title="♻️ Разбан",
            description=f"{user.mention} (`{user.id}`)",
            color=COLOR_OK,
        ))

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Изменение ролей
        if before.roles != after.roles:
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            parts = []
            if added:
                parts.append("**+** " + ", ".join(r.mention for r in added))
            if removed:
                parts.append("**−** " + ", ".join(r.mention for r in removed))
            await self._send(after.guild, discord.Embed(
                title="🎭 Изменение ролей",
                description=f"{after.mention}\n" + "\n".join(parts),
                color=COLOR_WARN,
            ))

        # Таймаут
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                title, color = "🔇 Таймаут", COLOR_WARN
                desc = f"{after.mention} до {after.timed_out_until:%d.%m %H:%M} UTC"
            else:
                title, color = "🔊 Размут", COLOR_OK
                desc = f"{after.mention} размучен"
            await self._send(after.guild, discord.Embed(
                title=title, description=desc, color=color,
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingCog(bot))