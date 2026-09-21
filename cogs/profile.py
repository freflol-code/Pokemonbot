"""Профили игроков: создание, переключение, просмотр."""
import discord
from discord import app_commands
from discord.ext import commands

from database import (
    PROFILE_TYPES,
    create_profile,
    delete_profile,
    get_active_profile,
    get_profile,
    get_trainer,
    list_profiles,
    switch_profile,
)
from utils import EMBED_COLOR

PROFILE_TYPE_CHOICES = [
    app_commands.Choice(name="🎓 Тренер", value="trainer"),
    app_commands.Choice(name="🐾 Покемон", value="pokemon"),
]

PROFILE_TYPE_LABEL = {
    "trainer": "🎓 Тренер",
    "pokemon": "🐾 Покемон",
}


def _profile_type_label(ptype: str) -> str:
    return PROFILE_TYPE_LABEL.get(ptype, ptype)


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------ /new_profile

    @app_commands.command(
        name="new_profile",
        description="Создать нового персонажа (профиль)",
    )
    @app_commands.describe(
        name="Имя персонажа (до 40 символов)",
        profile_type="Тип персонажа: тренер или покемон",
        avatar="Картинка-аватар (прикрепите файл)",
    )
    @app_commands.choices(profile_type=PROFILE_TYPE_CHOICES)
    async def new_profile(
        self,
        interaction: discord.Interaction,
        name: str,
        profile_type: app_commands.Choice[str],
        avatar: discord.Attachment | None = None,
    ) -> None:
        name = name.strip()
        if not name:
            await interaction.response.send_message(
                "❌ Имя не может быть пустым.", ephemeral=True
            )
            return
        if len(name) > 40:
            await interaction.response.send_message(
                "❌ Имя не должно быть длиннее 40 символов.", ephemeral=True
            )
            return

        avatar_url = None
        if avatar is not None:
            if not (avatar.content_type or "").startswith("image/"):
                await interaction.response.send_message(
                    "❌ Аватар должен быть картинкой (png, jpg, gif).", ephemeral=True
                )
                return
            avatar_url = avatar.url

        profile = await create_profile(
            user_id=interaction.user.id,
            name=name,
            profile_type=profile_type.value,
            avatar_url=avatar_url,
            make_active=True,
        )

        embed = discord.Embed(
            title="✅ Профиль создан",
            description=(
                f"**Имя:** {name}\n"
                f"**Тип:** {_profile_type_label(profile['profile_type'])}\n"
                f"**Статус:** 🟢 активен"
            ),
            color=discord.Color.green(),
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"ID профиля: {profile['profile_id']}")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ /my_profiles

    @app_commands.command(
        name="my_profiles",
        description="Показать всех ваших персонажей",
    )
    async def my_profiles(self, interaction: discord.Interaction) -> None:
        profiles = await list_profiles(interaction.user.id)
        if not profiles:
            await interaction.response.send_message(
                "У вас нет ни одного персонажа. Создайте первого: /new_profile",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"👥 Ваши персонажи ({len(profiles)})",
            color=EMBED_COLOR,
        )
        for p in profiles:
            marker = "🟢 " if p["is_active"] else "⚪ "
            embed.add_field(
                name=f"{marker}{p['name']}",
                value=(
                    f"Тип: {_profile_type_label(p['profile_type'])}\n"
                    f"🏆 {p['wins']} • 💔 {p['losses']} • 💰 {p['pokebucks']:,} PB\n"
                    f"ID: `{p['profile_id']}`"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ /switch

    @app_commands.command(
        name="switch",
        description="Переключиться на другого персонажа",
    )
    @app_commands.describe(profile_id="ID профиля (см. /my_profiles)")
    async def switch(
        self,
        interaction: discord.Interaction,
        profile_id: str,
    ) -> None:
        pid = profile_id.strip()
        ok = await switch_profile(interaction.user.id, pid)
        if not ok:
            await interaction.response.send_message(
                "❌ Профиль с таким ID не найден у вас.", ephemeral=True
            )
            return

        profile = await get_profile(pid)
        embed = discord.Embed(
            title="🔄 Активный персонаж изменён",
            description=(
                f"Теперь вы играете за **{profile['name']}** "
                f"({_profile_type_label(profile['profile_type'])})."
            ),
            color=discord.Color.green(),
        )
        if profile.get("avatar_url"):
            embed.set_thumbnail(url=profile["avatar_url"])
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ /delete_profile

    @app_commands.command(
        name="delete_profile",
        description="Удалить персонажа (НЕОБРАТИМО)",
    )
    @app_commands.describe(
        profile_id="ID профиля",
        confirm="Введите 'ДА' для подтверждения",
    )
    async def delete_profile_cmd(
        self,
        interaction: discord.Interaction,
        profile_id: str,
        confirm: str,
    ) -> None:
        if confirm != "ДА":
            await interaction.response.send_message(
                "❌ Отменено. Для подтверждения введите `confirm:ДА`", ephemeral=True
            )
            return

        pid = profile_id.strip()
        profile = await get_profile(pid)
        if not profile or profile["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Профиль не найден у вас.", ephemeral=True
            )
            return

        await delete_profile(interaction.user.id, pid)
        await interaction.response.send_message(
            f"🗑️ Профиль **{profile['name']}** удалён.", ephemeral=True
        )

    # ------------------------------------------------------------------ /profile

    @app_commands.command(name="profile", description="Показать профиль персонажа")
    @app_commands.describe(user="Чей активный профиль посмотреть (по умолчанию — свой)")
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        target = user or interaction.user
        active = await get_active_profile(target.id)
        if not active:
            msg = (
                "У вас нет ни одного персонажа. Создайте: /new_profile"
                if target.id == interaction.user.id
                else f"У {target.display_name} нет ни одного персонажа."
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        t = await get_trainer(target.id)

        own = target.id == interaction.user.id
        suffix = "" if own else " (чужой)"
        title = f"{_profile_type_label(t['profile_type'])} — {t['name']}{suffix}"

        embed = discord.Embed(title=title, color=EMBED_COLOR)
        if t.get("avatar_url"):
            embed.set_thumbnail(url=t["avatar_url"])
        embed.add_field(name="🏆 Победы", value=str(t["wins"]))
        embed.add_field(name="💔 Поражения", value=str(t["losses"]))
        embed.add_field(name="💰 Pokébucks", value=f"{t['pokebucks']:,}")
        embed.add_field(name="📖 Известно видов", value=str(len(t["pokedex_known"])))
        embed.add_field(name="🎒 Команда", value=f"{len(t['party'])}/6")
        embed.add_field(name="🖥️ ПК", value=str(len(t["pc"])))
        embed.set_footer(text=f"ID профиля: {t['profile_id']} • Тренер: {target.display_name}")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ /balance

    @app_commands.command(name="balance", description="Показать баланс Pokébucks")
    @app_commands.describe(user="Чей баланс посмотреть (по умолчанию — свой)")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        target = user or interaction.user
        active = await get_active_profile(target.id)
        if not active:
            msg = (
                "У вас нет персонажа. Создайте: /new_profile"
                if target.id == interaction.user.id
                else f"У {target.display_name} нет персонажа."
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        if target.id == interaction.user.id:
            desc = f"**{active['name']}**: {active['pokebucks']:,} Pokébucks"
        else:
            desc = f"**{target.display_name}** ({active['name']}): {active['pokebucks']:,} Pokébucks"

        embed = discord.Embed(title="💰 Баланс", description=desc, color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
