# Файл: cogs/menu.py
# Меню /ulavew. Бот "Ulavew". Доступно ТОЛЬКО владельцу сервера.

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import COLOR_INFO, COLOR_OK, COLOR_WARN, COLOR_ERROR

log = logging.getLogger("Ulavew.Menu")


# =====================================================================
# ПРОВЕРКА ДОСТУПА
# =====================================================================
def is_owner(interaction: discord.Interaction) -> bool:
    return (
        interaction.guild is not None
        and interaction.user.id == interaction.guild.owner_id
    )


async def deny(interaction: discord.Interaction):
    msg = "❌ Эта панель доступна только **владельцу сервера**."
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass


def yn(v) -> str:
    return "🟢 Включено" if v else "🔴 Отключено"


def footer(embed: discord.Embed) -> discord.Embed:
    embed.set_footer(text="Ulavew • Система защиты сервера")
    return embed


# =====================================================================
# МОДАЛЬНОЕ ОКНО ВВОДА ЧИСЛА
# =====================================================================
class NumberModal(discord.ui.Modal):
    def __init__(self, title: str, label: str, key: str, current: int,
                 db, guild_id: int, parent_view: discord.ui.View):
        super().__init__(title=title)
        self.key = key
        self.db = db
        self.guild_id = guild_id
        self.parent_view = parent_view
        self.input = discord.ui.TextInput(
            label=label, default=str(current), required=True, max_length=10,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await deny(interaction)
        try:
            value = int(self.input.value)
            if value < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Нужно целое неотрицательное число.", ephemeral=True
            )
        await self.db.update_setting(self.guild_id, self.key, value)
        try:
            msg = await interaction.original_response()
            await msg.edit(embed=await self.parent_view.build_embed(),
                           view=self.parent_view)
        except Exception as e:
            log.warning("Не удалось обновить меню после модалки: %s", e)


# =====================================================================
# СЕЛЕКТЫ
# =====================================================================
class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, key: str, db, guild_id: int, parent_view):
        super().__init__(
            placeholder="📁 Выберите канал...",
            channel_types=[discord.ChannelType.text],
        )
        self.key = key
        self.db = db
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await deny(interaction)
        ch = self.values[0]
        await self.db.update_setting(self.guild_id, self.key, ch.id)
        await interaction.response.edit_message(
            embed=await self.parent_view.build_embed(),
            view=self.parent_view,
        )


class RoleSelect(discord.ui.RoleSelect):
    def __init__(self, key: str, db, guild_id: int, parent_view):
        super().__init__(placeholder="🎭 Выберите роль...")
        self.key = key
        self.db = db
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await deny(interaction)
        role = self.values[0]
        await self.db.update_setting(self.guild_id, self.key, role.id)
        await interaction.response.edit_message(
            embed=await self.parent_view.build_embed(),
            view=self.parent_view,
        )


# =====================================================================
# ГЛАВНОЕ МЕНЮ
# =====================================================================
class MainMenuView(discord.ui.View):
    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id

    def build_embed(self, settings: dict | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ Ulavew — Панель управления",
            description=(
                "**Добро пожаловать в центр управления защитой сервера!**\n\n"
                "🛡 **Анти-рейд** — защита от массовых заходов ботов\n"
                "🚨 **Анти-краш** — мониторинг действий администрации\n"
                "🗑 **Автомод** — фильтр чата и наказания\n"
                "✅ **Верификация** — кнопка проверки участников\n"
                "🎭 **Авто-роль** — роль новым участникам при заходе\n"
                "👮 **Роли модерации** — кому доступны бан/кик/мут/варн\n"
                "📋 **Логи** — канал для событий сервера\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "👤 **Слэш-команды модерации:**\n"
                "`/ban` `/unban` `/kick` `/mute` `/unmute` `/warn` "
                "`/warns` `/clearwarns`\n\n"
                "⏱ **Формат времени:** `10м`, `1ч`, `2д`, `30с`\n\n"
                "👇 Выбери раздел кнопкой ниже."
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="🛡 Анти-рейд", style=discord.ButtonStyle.primary, row=0)
    async def btn_anti_raid(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = AntiRaidView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="🚨 Анти-краш", style=discord.ButtonStyle.primary, row=0)
    async def btn_anti_crash(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = AntiCrashView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="🗑 Автомод", style=discord.ButtonStyle.primary, row=0)
    async def btn_automod(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = AutomodView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="✅ Верификация", style=discord.ButtonStyle.success, row=1)
    async def btn_verify(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = VerifyView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="🎭 Авто-роль", style=discord.ButtonStyle.success, row=1)
    async def btn_autorole(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = AutoRoleView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="👮 Роли модерации", style=discord.ButtonStyle.success, row=1)
    async def btn_mod_roles(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = ModRolesView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="📋 Логи", style=discord.ButtonStyle.secondary, row=2)
    async def btn_logs(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        v = LogsView(self.bot, self.guild_id, parent=self)
        await interaction.response.edit_message(embed=await v.build_embed(), view=v)

    @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.danger, row=2)
    async def btn_close(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            content="✅ Меню закрыто.", embed=None, view=None
        )


# =====================================================================
# РАЗДЕЛ: АНТИ-РЕЙД
# =====================================================================
class AntiRaidView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        embed = discord.Embed(
            title="🛡 Анти-рейд — Защита от массовых атак",
            description=(
                "**Что делает модуль:**\n"
                "Автоматически останавливает массовые заходы ботов и рейдеров, "
                "а также кикает слишком новые аккаунты.\n\n"
                "**Текущие настройки:**\n"
                f"┣ Статус модуля: **{yn(s['anti_raid_enabled'])}**\n"
                f"┣ Лимит заходов: **`{s['raid_join_limit']}`** чел.\n"
                f"┣ За окно: **`{s['raid_join_window']}`** сек.\n"
                f"┗ Мин. возраст аккаунта: **`{s['min_account_age']}`** дн.\n\n"
                "⚙️ **Настройка:**\n"
                "• **Вкл/Выкл** — включить или отключить защиту\n"
                "• **Лимит заходов** — сколько человек за раз = атака\n"
                "• **Окно** — за сколько секунд считать заходы\n"
                "• **Возраст** — минимальный возраст аккаунта в днях"
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="🔄 Вкл / Выкл", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await self.db.update_setting(self.guild_id, "anti_raid_enabled",
                                     0 if s["anti_raid_enabled"] else 1)
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="📊 Лимит заходов", style=discord.ButtonStyle.secondary)
    async def set_limit(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await interaction.response.send_modal(NumberModal(
            title="Лимит заходов",
            label="Сколько заходов = атака (например, 10)",
            key="raid_join_limit", current=s["raid_join_limit"],
            db=self.db, guild_id=self.guild_id, parent_view=self,
        ))

    @discord.ui.button(label="⏱ Окно (сек)", style=discord.ButtonStyle.secondary)
    async def set_window(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await interaction.response.send_modal(NumberModal(
            title="Временное окно",
            label="За сколько секунд считать заходы (например, 10)",
            key="raid_join_window", current=s["raid_join_window"],
            db=self.db, guild_id=self.guild_id, parent_view=self,
        ))

    @discord.ui.button(label="👤 Возраст (дн)", style=discord.ButtonStyle.secondary)
    async def set_age(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await interaction.response.send_modal(NumberModal(
            title="Минимальный возраст аккаунта",
            label="Сколько дней должно быть аккаунту (0 = выкл)",
            key="min_account_age", current=s["min_account_age"],
            db=self.db, guild_id=self.guild_id, parent_view=self,
        ))

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# РАЗДЕЛ: АНТИ-КРАШ
# =====================================================================
class AntiCrashView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        embed = discord.Embed(
            title="🚨 Анти-краш — Защита от действий админов",
            description=(
                "**Что делает модуль:**\n"
                "Следит за действиями администрации через audit log. "
                "Если админ массово удаляет каналы, роли или банит — "
                "Ulavew снимает с него опасные роли и уведомляет владельца.\n\n"
                "**Лимиты за 10 секунд:**\n"
                "┣ 🗑 Удаление каналов: **`3`**\n"
                "┣ 🎭 Удаление ролей: **`3`**\n"
                "┗ 🔨 Баны: **`5`**\n\n"
                f"**Статус модуля:** {yn(s['anti_crash_enabled'])}\n\n"
                "⚠️ Рекомендуется держать включённым всегда."
            ),
            color=COLOR_WARN,
        )
        return footer(embed)

    @discord.ui.button(label="🔄 Вкл / Выкл", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await self.db.update_setting(self.guild_id, "anti_crash_enabled",
                                     0 if s["anti_crash_enabled"] else 1)
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# РАЗДЕЛ: АВТОМОД
# =====================================================================
class AutomodView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        embed = discord.Embed(
            title="🗑 Автомод — Фильтр чата",
            description=(
                "**Что делает модуль:**\n"
                "Автоматически удаляет спам, капс, массовые упоминания и "
                "запрещённые ссылки. Нарушители получают наказания.\n\n"
                "**Активные фильтры:**\n"
                "┣ 💬 **Спам** — 5+ сообщений за 7 секунд\n"
                "┣ 🔠 **CAPS** — >70% текста заглавными\n"
                "┣ 📢 **Упоминания** — больше 5 @упоминаний\n"
                "┣ 🔗 **Инвайты discord.gg** — блокируются\n"
                "┗ 🌐 **Фишинговые ссылки** — блокируются\n\n"
                "**Наказания:** Варн → Мут 10 мин → Кик → Бан\n\n"
                f"**Статус модуля:** {yn(s['automod_enabled'])}\n\n"
                "ℹ️ Администраторы **не** проверяются автомодом."
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="🔄 Вкл / Выкл", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        await self.db.update_setting(self.guild_id, "automod_enabled",
                                     0 if s["automod_enabled"] else 1)
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# РАЗДЕЛ: ВЕРИФИКАЦИЯ
# =====================================================================
class VerifyView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db
        self.add_item(RoleSelect("verify_role_id", self.db, guild_id, self))
        self.add_item(ChannelSelect("verify_channel_id", self.db, guild_id, self))

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        role = f"<@&{s['verify_role_id']}>" if s["verify_role_id"] else "❌ *не выбрана*"
        ch = f"<#{s['verify_channel_id']}>" if s["verify_channel_id"] else "❌ *не выбран*"
        embed = discord.Embed(
            title="✅ Верификация — Проверка новых участников",
            description=(
                "**Что делает модуль:**\n"
                "Отправляет в указанный канал сообщение с кнопкой. "
                "Новые участники нажимают на кнопку и получают роль доступа.\n\n"
                "**Как настроить:**\n"
                "1️⃣ Выбери **роль** и **канал** в селектах ниже\n"
                "2️⃣ Нажми **«📨 Отправить панель»**\n"
                "3️⃣ В канале появится сообщение с кнопкой\n\n"
                "**Текущие настройки:**\n"
                f"┣ 🎭 Роль верификации: {role}\n"
                f"┗ 📁 Канал с кнопкой: {ch}"
            ),
            color=COLOR_OK,
        )
        return footer(embed)

    @discord.ui.button(label="📨 Отправить панель", style=discord.ButtonStyle.success, row=2)
    async def send_panel(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        s = await self.db.get_settings(self.guild_id)
        if not s["verify_channel_id"] or not s["verify_role_id"]:
            return await interaction.response.send_message(
                "❌ Сначала выбери **роль** и **канал**.", ephemeral=True
            )
        ch = interaction.guild.get_channel(s["verify_channel_id"])
        role = interaction.guild.get_role(s["verify_role_id"])
        if not ch or not role:
            return await interaction.response.send_message(
                "❌ Канал или роль не найдены.", ephemeral=True
            )

        embed = discord.Embed(
            title="🔒 Верификация — Ulavew",
            description=(
                "**Добро пожаловать на сервер!**\n\n"
                "Чтобы получить доступ к каналам, пройди простую верификацию.\n\n"
                "👇 **Нажми на кнопку ниже, чтобы пройти верификацию.**\n\n"
                f"После нажатия ты автоматически получишь роль {role.mention} "
                "и полный доступ к серверу."
            ),
            color=COLOR_OK,
        )
        embed.set_footer(text="Ulavew • Система защиты сервера")

        try:
            await ch.send(embed=embed, view=VerifyButtonView())
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Нет прав писать в этот канал.", ephemeral=True
            )
        await interaction.response.send_message(
            f"✅ Панель верификации отправлена в {ch.mention}!\nРоль: {role.mention}",
            ephemeral=True,
        )

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger, row=2)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ Пройти верификацию",
        style=discord.ButtonStyle.success,
        custom_id="ulavew:verify_button",
    )
    async def verify(self, interaction, _):
        await interaction.response.defer(ephemeral=True)
        s = await interaction.client.db.get_settings(interaction.guild.id)
        if not s["verify_role_id"]:
            return await interaction.followup.send(
                "❌ Роль не настроена. Обратись к администрации.", ephemeral=True
            )
        role = interaction.guild.get_role(s["verify_role_id"])
        if not role:
            return await interaction.followup.send(
                "❌ Роль не найдена. Обратись к администрации.", ephemeral=True
            )
        if role in interaction.user.roles:
            return await interaction.followup.send(
                "✅ Ты уже верифицирован!", ephemeral=True
            )
        try:
            await interaction.user.add_roles(role, reason="Ulavew: verification passed")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ Бот не может выдать роль.", ephemeral=True
            )
        await interaction.followup.send(
            f"🎉 **Верификация пройдена!** Тебе выдана роль {role.mention}.\n"
            f"Добро пожаловать! 🚀",
            ephemeral=True,
        )


# =====================================================================
# РАЗДЕЛ: АВТО-РОЛЬ
# =====================================================================
class AutoRoleView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db
        self.add_item(RoleSelect("auto_role_id", self.db, guild_id, self))

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        role = f"<@&{s['auto_role_id']}>" if s.get("auto_role_id") else "❌ *не выбрана*"
        embed = discord.Embed(
            title="🎭 Авто-роль — Роль новым участникам",
            description=(
                "**Что делает модуль:**\n"
                "Каждому новому участнику при заходе на сервер "
                "автоматически выдаётся указанная роль.\n\n"
                "**Как это работает:**\n"
                "1️⃣ Ты выбираешь роль в селекте ниже\n"
                "2️⃣ Когда кто-то заходит — Ulavew сразу выдаёт ему эту роль\n"
                "3️⃣ Удобно для выдачи базового доступа новичкам\n\n"
                "**Текущая настройка:**\n"
                f"┗ 🎭 Авто-роль: {role}\n\n"
                "⚠️ **Важно:** роль Ulavew должна быть **выше** "
                "выдаваемой роли в иерархии ролей.\n\n"
                "💡 **Совет:** жми «🗑 Сбросить», чтобы отключить авто-роль."
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="🗑 Сбросить авто-роль", style=discord.ButtonStyle.secondary, row=1)
    async def clear(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await self.db.update_setting(self.guild_id, "auto_role_id", None)
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# РАЗДЕЛ: РОЛИ МОДЕРАЦИИ
# =====================================================================
# 4 действия — 4 селекта (каждый на своём ряду 0-3),
# 2 кнопки — на ряду 4. Так Discord не ругается на конфликт.
MOD_ACTIONS = {
    "ban":  "🔨 Бан / Разбан",
    "kick": "👢 Кик",
    "mute": "🔇 Мут / Размут",
    "warn": "⚠️ Варн",
}


class ModRoleSelect(discord.ui.RoleSelect):
    """Селект роли для одного действия (ban/kick/mute/warn)."""
    def __init__(self, action: str, db, guild_id: int, parent_view, row: int):
        super().__init__(
            placeholder=f"{MOD_ACTIONS[action]} — выберите роль...",
            row=row,
        )
        self.action = action
        self.db = db
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await deny(interaction)
        role = self.values[0]
        await self.db.set_mod_role(self.guild_id, self.action, role.id)
        await interaction.response.edit_message(
            embed=await self.parent_view.build_embed(), view=self.parent_view
        )


class ModRolesView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db
        # Один селект = один ряд (0, 1, 2, 3)
        for idx, action in enumerate(MOD_ACTIONS.keys()):
            self.add_item(ModRoleSelect(action, self.db, guild_id, self, row=idx))

    async def build_embed(self):
        lines = []
        for action, label in MOD_ACTIONS.items():
            role_id = await self.db.get_mod_role(self.guild_id, action)
            role = f"<@&{role_id}>" if role_id else "❌ *не задана*"
            lines.append(f"┣ {label}: {role}")
        if lines:
            lines[-1] = lines[-1].replace("┣", "┗", 1)

        embed = discord.Embed(
            title="👮 Роли модерации — Доступ к командам",
            description=(
                "**Что делает модуль:**\n"
                "Позволяет выдать конкретные роли для использования "
                "команд модерации. Участники с этими ролями смогут "
                "банить, кикать, мутить и выдавать варны — **даже если "
                "у них нет стандартных прав Discord**.\n\n"
                "**Как это работает:**\n"
                "• 👑 **Владелец сервера** — может всё всегда\n"
                "• 🔑 **Стандартные права Discord** — тоже работают\n"
                "• 🎭 **Кастомные роли** — дают право на конкретное действие\n\n"
                "**Текущие настройки:**\n"
                + "\n".join(lines) + "\n\n"
                "⚙️ **Настройка:**\n"
                "Выбери роль в селектах ниже. Например, выбери роль "
                "**«Модератор»** для **🔨 Бан / Разбан** — и все с этой "
                "ролью смогут использовать `/ban` и `/unban`.\n\n"
                "🗑 **Сброс:** кнопка ниже очищает все кастомные роли."
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="🗑 Сбросить все роли", style=discord.ButtonStyle.danger, row=4)
    async def reset(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        for action in MOD_ACTIONS.keys():
            await self.db.clear_mod_role(self.guild_id, action)
        await interaction.response.edit_message(
            embed=await self.build_embed(), view=self
        )

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# РАЗДЕЛ: ЛОГИ
# =====================================================================
class LogsView(discord.ui.View):
    def __init__(self, bot, guild_id, parent: MainMenuView):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.parent = parent
        self.db = bot.db
        self.add_item(ChannelSelect("log_channel_id", self.db, guild_id, self))

    async def build_embed(self):
        s = await self.db.get_settings(self.guild_id)
        ch = f"<#{s['log_channel_id']}>" if s["log_channel_id"] else "❌ *не выбран*"
        embed = discord.Embed(
            title="📋 Логи — Журнал событий",
            description=(
                "**Что делает модуль:**\n"
                "Записывает все важные события сервера в указанный канал.\n\n"
                "**Что логируется:**\n"
                "┣ 📁 Создание и удаление каналов\n"
                "┣ 🎭 Создание и удаление ролей\n"
                "┣ 🎭 Изменение ролей у участников\n"
                "┣ 🔨 Баны и разбаны\n"
                "┣ 🔇 Выдача и снятие таймаутов\n"
                "┣ 🛡 Срабатывания анти-рейда\n"
                "┣ 🚨 Срабатывания анти-краша\n"
                "┗ 🗑 Действия автомода и модерации\n\n"
                "**Текущая настройка:**\n"
                f"┗ 📁 Канал логов: {ch}\n\n"
                "⚙️ Выбери канал в селекте ниже."
            ),
            color=COLOR_INFO,
        )
        return footer(embed)

    @discord.ui.button(label="⬅️ Назад в меню", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction, _):
        if not is_owner(interaction):
            return await deny(interaction)
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )


# =====================================================================
# КОГ /ulavew
# =====================================================================
class MenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(VerifyButtonView())

    @app_commands.command(
        name="ulavew",
        description="🛡 Панель управления Ulavew (только владелец)",
    )
    async def ulavew(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            return await interaction.response.send_message(
                "❌ Эта панель доступна только **владельцу сервера**.",
                ephemeral=True,
            )
        view = MainMenuView(self.bot, interaction.guild.id)
        await interaction.response.send_message(
            embed=view.build_embed(), view=view, ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MenuCog(bot))