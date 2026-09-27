"""Спавн покемонов мастером — /spawn с условиями."""
import logging
import os
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from data.locations import find_location_by_channel_name, get_location
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, GENDER_EMOJI, format_moves, format_types

log = logging.getLogger(__name__)


TIME_CHOICES = [
    app_commands.Choice(name="☀️ Полдень", value="noon"),
    app_commands.Choice(name="🌞 День", value="day"),
    app_commands.Choice(name="🌙 Ночь", value="night"),
]

TERRAIN_CHOICES = [
    app_commands.Choice(name="🌿 Суша", value="land"),
    app_commands.Choice(name="🌊 Вода", value="water"),
    app_commands.Choice(name="🕳️ Пещера", value="cave"),
    app_commands.Choice(name="🌲 Лес", value="forest"),
]

LURE_CHOICES = [
    app_commands.Choice(name="— Без приманки", value="none"),
    app_commands.Choice(name="🔥 Огонь", value="fire"),
    app_commands.Choice(name="💧 Вода", value="water"),
    app_commands.Choice(name="🌿 Трава", value="grass"),
    app_commands.Choice(name="⚡ Электро", value="electric"),
    app_commands.Choice(name="❄️ Лёд", value="ice"),
    app_commands.Choice(name="🥊 Боевой", value="fighting"),
    app_commands.Choice(name="☠️ Яд", value="poison"),
    app_commands.Choice(name="🏜️ Земля", value="ground"),
    app_commands.Choice(name="🕊️ Летающий", value="flying"),
    app_commands.Choice(name="🔮 Психика", value="psychic"),
    app_commands.Choice(name="🐛 Жук", value="bug"),
    app_commands.Choice(name="🪨 Камень", value="rock"),
    app_commands.Choice(name="👻 Призрак", value="ghost"),
    app_commands.Choice(name="🐉 Дракон", value="dragon"),
    app_commands.Choice(name="🌑 Тьма", value="dark"),
    app_commands.Choice(name="⚙️ Сталь", value="steel"),
    app_commands.Choice(name="✨ Фея", value="fairy"),
]


def _master_role_id() -> int:
    raw = os.getenv("MASTER_ROLE_ID", "").strip()
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def is_master():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        role_id = _master_role_id()
        if role_id == 0:
            return False
        return any(r.id == role_id for r in interaction.user.roles)
    return app_commands.check(predicate)


# --------------------------------------------------------------------------- #
#                           ФИЛЬТРАЦИЯ ПО ТИПА                                 #
# --------------------------------------------------------------------------- #

_type_cache: dict[str, list[str]] = {}


async def _get_types(name: str) -> list[str]:
    """Возвращает список типов покемона по имени (с кэшем)."""
    if name in _type_cache:
        return _type_cache[name]
    try:
        data = await pokeapi_client.get_pokemon_by_name(name)
        types = data.get("types", [])
    except PokeAPIError:
        types = []
    _type_cache[name] = types
    return types


def _time_label(key: str) -> str:
    return {
        "noon": "☀️ Полдень",
        "day": "🌞 День",
        "night": "🌙 Ночь",
    }.get(key, key)


def _terrain_label(key: str) -> str:
    return {
        "land": "🌿 Суша",
        "water": "🌊 Вода",
        "cave": "🕳️ Пещера",
        "forest": "🌲 Лес",
    }.get(key, key)


def _lure_label(key: str) -> str:
    if not key or key == "none":
        return "—"
    for ch in LURE_CHOICES:
        if ch.value == key:
            return ch.name
    return key


async def _filter_pool(
    base_pool: list[str], terrain: str, lure: str
) -> list[str]:
    """Фильтрует пул локации по местности и приманке."""
    pool = list(base_pool)

    # Фильтр по местности
    if terrain != "land":
        allow = {
            "water": ["water"],
            "cave": ["rock", "ground", "ghost"],
            "forest": ["grass", "bug"],
        }.get(terrain, [])
        if allow:
            filtered = []
            for name in pool:
                types = await _get_types(name)
                if any(t in types for t in allow):
                    filtered.append(name)
            pool = filtered

    # Фильтр по приманке
    if lure and lure != "none":
        filtered = []
        for name in pool:
            types = await _get_types(name)
            if lure in types:
                filtered.append(name)
        pool = filtered

    return pool


class Spawn(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="spawn",
        description="[Мастер] Заспавнить случайного покемона по условиям",
    )
    @app_commands.describe(
        time="Время суток",
        terrain="Местность",
        lure="Приманка (фильтр по типу)",
        level="Уровень (1–100, по умолчанию 5)",
        nickname="Кличка (необязательно)",
    )
    @app_commands.choices(
        time=TIME_CHOICES,
        terrain=TERRAIN_CHOICES,
        lure=LURE_CHOICES,
    )
    @is_master()
    async def spawn(
        self,
        interaction: discord.Interaction,
        time: app_commands.Choice[str],
        terrain: app_commands.Choice[str],
        lure: Optional[app_commands.Choice[str]] = None,
        level: app_commands.Range[int, 1, 100] = 5,
        nickname: Optional[str] = None,
    ) -> None:
        await interaction.response.defer()

        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Только на сервере.", ephemeral=True)
            return

        loc_key = find_location_by_channel_name(channel.name)
        if not loc_key:
            await interaction.followup.send(
                "❌ `/spawn` работает только в каналах локаций "
                "(например, `#хошинори`, `#цукисиро` и т.д.).",
                ephemeral=True,
            )
            return

        loc = get_location(loc_key)
        base_pool = loc.get("encounters") or []

        if not base_pool:
            await interaction.followup.send(
                f"❌ В локации **{loc['name']}** не задан пул спавна.",
                ephemeral=True,
            )
            return

        lure_key = lure.value if lure else "none"

        pool = await _filter_pool(base_pool, terrain.value, lure_key)
        if not pool:
            await interaction.followup.send(
                "❌ По таким условиям покемон не найден. "
                "Уберите приманку или смените местность.",
                ephemeral=True,
            )
            return

        # Берём случайного из пула. Пробуем несколько раз, если PokéAPI не отвечает.
        random.shuffle(pool)
        data = None
        for name in pool[:5]:
            try:
                data = await pokeapi_client.get_pokemon_by_name(name)
                break
            except PokeAPIError:
                continue

        if data is None:
            await interaction.followup.send(
                "⚠️ PokéAPI не отвечает, попробуйте позже.", ephemeral=True
            )
            return

        try:
            gender = await pokeapi_client.roll_gender(data["id"])
        except Exception:
            gender = "genderless"

        moves = pokeapi_client.pick_random_moves(data, 4)
        nick = (nickname or "").strip() or None

        display_name = data["name"]
        if nick:
            display_name = f"{nick} ({data['name']})"

        embed = discord.Embed(
            title=f"🌿 Появление: {display_name}",
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="🕒 Условия",
            value=(
                f"{_time_label(time.value)}\n"
                f"{_terrain_label(terrain.value)}\n"
                f"**Приманка:** {_lure_label(lure_key)}"
            ),
            inline=False,
        )
        embed.add_field(name="🎚️ Уровень", value=str(int(level)))
        embed.add_field(name="🎭 Пол", value=GENDER_EMOJI.get(gender, "—"))
        embed.add_field(name="🌐 Типы", value=format_types(data["types"]))
        embed.add_field(
            name="⚔️ Атаки",
            value=format_moves(moves),
            inline=False,
        )
        if data.get("artwork"):
            embed.set_image(url=data["artwork"])
        embed.set_footer(text=f"Мастер: {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Spawn(bot))
