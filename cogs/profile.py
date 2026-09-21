"""Профили игроков: создание, переключение, просмотр."""
import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    create_profile,
    delete_profile,
    get_active_profile,
    get_profile,
    get_trainer,
    list_profiles,
    switch_profile,
)
from utils import EMBED_COLOR, format_ability, format_moves, load_species

PROFILE_TYPE_CHOICES = [
    app_commands.Choice(name="🎓 Тренер", value="trainer"),
    app_commands.Choice(name="🐾 Покемон", value="pokemon"),
]

PROFILE_TYPE_LABEL = {
    "trainer": "🎓 Тренер",
    "pokemon": "🐾 Покемон",
}

STATUS_LABEL = {
    "wild": "🌿 Дикий",
    "caught": "🔴 Пойман",
}

POKEBALL_LABEL = {
    "pokeball": "Покебол",
    "greatball": "Грейтбол",
    "ultraball": "Ультрабол",
    "masterball": "Мастербол",
    "net_ball": "Нетбол",
    "dive_ball": "Дайвбол",
    "nest_ball": "Нестбол",
    "repeat_ball": "Репитбол",
    "timer_ball": "Таймербол",
    "heal_ball": "Хилбол",
    "luxury_ball": "Люксбол",
    "quick_ball": "Квикбол",
    "dusk_ball": "Дускбол",
}


def _ptype_label(ptype: str) -> str:
    return PROFILE_TYPE_LABEL.get(ptype, ptype)


def _status_label(status: str | None, pokeball: str | None) -> str:
    status = status or "wild"
    base = STATUS_LABEL.get(status, status)
    if status == "caught" and pokeball:
        ball_name = POKEBALL_LABEL.get(pokeball, pokeball)
        return f"{base} ({ball_name})"
    return base


async def _pokemon_profile_fields(profile: dict) -> dict[str, str]:
    """Данные для эмбеда профиля-покемона: справочные значения."""
    moves = profile.get("moves") or []
    ability_en = profile.get("ability")

    # Русское название способности (если есть)
    ability_ru = ability_en
    if ability_en:
        try:
            ability_ru = await pokeapi_client.get_ability_ru(ability_en)
        except Exception:
            ability_ru = ability_en

    # Если у профиля не указан вид — пытаемся понять из имени (не обязательно)
    return {
        "level": str(profile.get("level") or "—"),
        "ability": ability_ru or "—",
        "moves": format_moves(moves) if moves else "—",
        "status": _status_label(profile.get("status"), profile.get("pokeball")),
    }


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------ /new_profile

    @app_commands.command(
        name="new_profile",
        description="Создать нового персонажа (тренера или покемона)",
    )
    @app_commands.describe(
        name="Имя персонажа (до 40 символов)",
        profile_type="Тип: тренер или покемон",
        avatar="Картинка-аватар (прикрепите файл)",
        level="Уровень (только для покемонов)",
        ability="Способность (только для покемонов), например blaze",
        moves="Атаки через запятую (только для покемонов), до 4",
        status="Статус покемона: wild (дикий) или caught (пойман)",
        pokeball="В каком покеболе сидит (только если caught), например pokeball",
    )
    @app_commands.choices(
        profile_type=PROFILE_TYPE_CHOICES,
        status=[
            app_commands.Choice(name="🌿 Дикий", value="wild"),
            app_commands.Choice(name="🔴 Пойман", value="caught"),
        ],
    )
    async def new_profile(
        self,
        interaction: discord.Interaction,
        name: str,
        profile_type: app_commands.Choice[str],
        avatar: discord.Attachment | None = None,
        level: app_commands.Range[int, 1, 100] | None = None,
        ability: str | None = None,
        moves: str | None = None,
        status: app_commands.Choice[str] | None = None,
        pokeball: str | None = None,
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

        # Поля для покемона
        mon_level = None
        mon_ability = None
        mon_moves = None
        mon_status = None
        mon_ball = None

        if profile_type.value == "pokemon":
            mon_level = int(level) if level else 5
            mon_ability = (ability or "").strip().lower().replace(" ", "-") or None
            if moves:
                parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
                if not (1 <= len(parsed) <= 4):
                    await interaction.response.send_message(
                        "❌ Укажите от 1 до 4 атак через запятую.", ephemeral=True
                    )
                    return
                mon_moves = parsed
            mon_status = status.value if status else "wild"
            if mon_status == "caught":
                mon_ball = (pokeball or "pokeball").strip().lower().replace(" ", "_")

        profile = await create_profile(
            user_id=interaction.user.id,
            name=name,
            profile_type=profile_type.value,
            avatar_url=avatar_url,
            make_active=True,
            level=mon_level,
            moves=mon_moves,
            ability=mon_ability,
            status=mon_status,
            pokeball=mon_ball,
        )

        embed = discord.Embed(
            title="✅ Профиль создан",
            description=(
                f"**Имя:** {name}\n"
                f"**Тип:** {_ptype_label(profile['profile_type'])}\n"
                f"**Статус:** 🟢 активен"
            ),
            color=discord.Color.green(),
        )
        if profile_type.value == "pokemon":
            embed.add_field(name="Уровень", value=str(profile.get("level") or "—"))
            embed.add_field(name="Способность", value=profile.get("ability") or "—")
            embed.add_field(
                name="Атаки",
                value=format_moves(profile.get("moves") or []),
                inline=False,
            )
            embed.add_field(
                name="Статус",
                value=_status_label(profile.get("status"), profile.get("pokeball")),
                inline=False,
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
                "У вас нет ни одного персонажа. Создайте: /new_profile",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"👥 Ваши персонажи ({len(profiles)})",
            color=EMBED_COLOR,
        )
        for p in profiles:
            marker = "🟢 " if p["is_active"] else "⚪ "
            if p["profile_type"] == "pokemon":
                detail = (
                    f"🐾 Покемон • Ур. {p.get('level') or '—'} • "
                    f"{_status_label(p.get('status'), p.get('pokeball'))}"
                )
            else:
                detail = (
                    f"🎓 Тренер • 🏆 {p['wins']} • 💔 {p['losses']} • "
                    f"💰 {p['pokebucks']:,} PB"
                )
            embed.add_field(
                name=f"{marker}{p['name']}",
                value=f"{detail}\nID: `{p['profile_id']}`",
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
                f"({_ptype_label(profile['profile_type'])})."
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

        own = target.id == interaction.user.id
        suffix = "" if own else " (чужой)"

        embed = discord.Embed(
            title=f"{_ptype_label(active['profile_type'])} — {active['name']}{suffix}",
            color=EMBED_COLOR,
        )
        if active.get("avatar_url"):
            embed.set_thumbnail(url=active["avatar_url"])

        if active["profile_type"] == "pokemon":
            # Профиль ПОКЕМОНА
            fields = await _pokemon_profile_fields(active)
            embed.add_field(name="🎚️ Уровень", value=fields["level"])
            embed.add_field(name="✨ Способность", value=fields["ability"])
            embed.add_field(name="⚔️ Атаки", value=fields["moves"], inline=False)
            embed.add_field(name="🔴 Статус", value=fields["status"], inline=False)
        else:
            # Профиль ТРЕНЕРА
            t = await get_trainer(target.id)
            embed.add_field(name="🏆 Победы", value=str(t["wins"]))
            embed.add_field(name="💔 Поражения", value=str(t["losses"]))
            embed.add_field(name="💰 Pokébucks", value=f"{t['pokebucks']:,}")
            embed.add_field(name="📖 Известно видов", value=str(len(t["pokedex_known"])))
            embed.add_field(name="🎒 Команда", value=f"{len(t['party'])}/6")
            embed.add_field(name="🖥️ ПК", value=str(len(t["pc"])))

        embed.set_footer(
            text=f"ID: {active['profile_id']} • Тренер: {target.display_name}"
        )
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

        if active["profile_type"] == "pokemon":
            desc = (
                f"**{active['name']}** — это покемон. "
                f"Кошелёк доступен только тренерам."
            )
            embed = discord.Embed(title="💰 Баланс", description=desc, color=EMBED_COLOR)
            await interaction.response.send_message(embed=embed)
            return

        if target.id == interaction.user.id:
            desc = f"**{active['name']}**: {active['pokebucks']:,} Pokébucks"
        else:
            desc = (
                f"**{target.display_name}** ({active['name']}): "
                f"{active['pokebucks']:,} Pokébucks"
            )

        embed = discord.Embed(title="💰 Баланс", description=desc, color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
