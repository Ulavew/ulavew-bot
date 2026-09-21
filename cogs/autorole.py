# Файл: cogs/autorole.py
# Авто-роль: выдаёт указанную роль каждому новому участнику при заходе.

import logging

import discord
from discord.ext import commands

log = logging.getLogger("Ulavew.AutoRole")


class AutoRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """При заходе участника выдаём ему авто-роль из настроек."""
        guild = member.guild
        s = await self.bot.db.get_settings(guild.id)

        role_id = s.get("auto_role_id")
        if not role_id:
            return  # авто-роль не настроена

        role = guild.get_role(role_id)
        if not role:
            log.warning("Авто-роль %s не найдена на сервере %s", role_id, guild.id)
            return

        try:
            await member.add_roles(role, reason="Ulavew: авто-роль при заходе")
            log.info("Выдана авто-роль %s участнику %s", role.name, member)
        except discord.Forbidden:
            log.warning(
                "Нет прав выдать авто-роль %s. Проверь иерархию ролей и права бота.",
                role.name,
            )
        except discord.HTTPException as e:
            log.exception("Ошибка выдачи авто-роли: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRole(bot))