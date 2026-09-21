# Файл: cogs/anti_raid.py
# Анти-рейд. Лимиты берутся из БД (меняются через !Ulavew).

import asyncio
import time
import logging
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord.ext import commands

from config import COLOR_OK, COLOR_WARN, COLOR_ERROR

log = logging.getLogger("TrustBot.AntiRaid")


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.joins: dict[int, deque] = defaultdict(deque)
        self.quarantine: dict[int, bool] = {}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        s = await self.bot.db.get_settings(guild.id)

        # --- 1) Account Age Gate ---
        age_days = (discord.utils.utcnow() - member.created_at).days
        if age_days < s["min_account_age"]:
            try:
                await member.send(
                    f"❌ Ваш аккаунт слишком новый ({age_days} дн.). "
                    f"Минимум для входа: {s['min_account_age']} дн."
                )
            except discord.Forbidden:
                pass
            try:
                await member.kick(reason="Account Age Gate")
                await self._log(guild,
                    f"🔨 Кикнут новый аккаунт {member} (возраст {age_days} дн.)")
            except discord.Forbidden:
                log.warning("Нет прав кикнуть %s", member)
            return

        # --- 2) Массовые заходы ---
        if not s["anti_raid_enabled"]:
            return

        now = time.time()
        dq = self.joins[guild.id]
        dq.append(now)
        while dq and now - dq[0] > s["raid_join_window"]:
            dq.popleft()

        if len(dq) > s["raid_join_limit"] and not self.quarantine.get(guild.id):
            await self._activate_quarantine(guild, s)

    async def _activate_quarantine(self, guild: discord.Guild, s: dict):
        self.quarantine[guild.id] = True
        await self._log(
            guild,
            f"🚨 **АНТИ-РЕЙД!** >{s['raid_join_limit']} заходов за "
            f"{s['raid_join_window']} сек.",
            color=COLOR_ERROR,
        )

        # Кик всех, кто зашёл в окне
        cutoff = discord.utils.utcnow() - timedelta(seconds=s["raid_join_window"])
        for m in list(guild.members):
            if m.joined_at and m.joined_at >= cutoff:
                try:
                    await m.kick(reason="Anti-Raid quarantine")
                except discord.Forbidden:
                    pass

        await asyncio.sleep(60)
        self.quarantine[guild.id] = False
        self.joins[guild.id].clear()
        await self._log(guild, "✅ Карантин снят.", color=COLOR_OK)

    async def _log(self, guild, text, color=COLOR_WARN):
        s = await self.bot.db.get_settings(guild.id)
        if not s["log_channel_id"]:
            return
        ch = guild.get_channel(s["log_channel_id"])
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(embed=discord.Embed(description=text, color=color))
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))