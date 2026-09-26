"""Спавн покемонов мастером — /spawn с условиями."""
import logging
import os
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, GENDER_EMOJI, format_moves, format_types

log = logging.getLogger(__name__)


# ==========================================================================
#  ВЫБОР УСЛОВИЙ
# ==========================================================================
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


# ==========================================================================
#  ФИЛЬТРАЦИЯ ПУЛА
# ==========================================================================

_pool_cache: dict[str, list[int]] = {}


async def _fetch_type_pokemon(type_name: str) -> list[int]:
    """Возвращает список ID покемонов указанного типа (1–1025). С кэшем."""
    if type_name in _pool_cache:
        return _pool_cache[type_name]

    url = f"https://pokeapi.co/api/v2/type/{type_name}"
    try:
        data = await pokeapi_client._fetch_json(url)
    except PokeAPIError:
        return []

    out: list[int] = []
    for entry in data.get("pokemon", []) or []:
        try:
            pid = int(entry["pokemon"]["url"].rstrip("/").split("/")[-1])
        except (KeyError, ValueError):
            continue
        if 1 <= pid <= 1025:
            out.append(pid)

    _pool_cache[type_name] = out
    return out


async def _filter_pool(terrain: str, lure: str) -> list[int]:
    """Возвращает список ID покемонов, подходящих под условия."""
    pool: Optional[set[int]] = None

    # --- Фильтр по местности ---
    if terrain == "water":
        s = set(await _fetch_type_pokemon("water"))
        pool = s if pool is None else pool & s
    elif terrain == "cave":
        s = set(await _fetch_type_pokemon("rock"))
        s |= set(await _fetch_type_pokemon("ground"))
        s |= set(await _fetch_type_pokemon("ghost"))
        pool = s if pool is None else pool & s
    elif terrain == "forest":
        s = set(await _fetch_type_pokemon("grass"))
        s |= set(await _fetch_type_pokemon("bug"))
        pool = s if pool is None else pool & s
    # land — без фильтра

    # --- Фильтр по приманке ---
    if lure and lure != "none":
        s = set(await _fetch_type_pokemon(lure))
        pool = s if pool is None else pool & s

    if not pool:
        return list(range(1, 1026))
    return [p for p in pool if 1 <= p <= 1025]


def _time_label(key: str) -> str:
    return {"noon": "☀️ Полдень", "day": "🌞 День", "night": "🌙 Ночь"}.get(key, key)


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

        # Проверка канала — только в каналах-локациях
        from cogs.inventory import SHOP_CHANNELS
        if (interaction.channel_id or 0) not in SHOP_CHANNELS:
            await interaction.followup.send(
                "❌ `/spawn` работает только в каналах локаций.",
                ephemeral=True,
            )
            return

        lure_key = lure.value if lure else "none"

        # Подбираем пул
        pool = await _filter_pool(terrain.value, lure_key)
        if not pool:
            await interaction.followup.send(
                "❌ По таким условиям покемон не найден. Уберите приманку или смените местность.",
                ephemeral=True,
            )
            return

        # Случайный покемон
        species_id = random.choice(pool)
        try:
            data = await pokeapi_client.get_pokemon(species_id)
            gender = await pokeapi_client.roll_gender(data["id"])
        except PokeAPIError as e:
            await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
            return

        moves = pokeapi_client.pick_random_moves(data, 4)
        nick = (nickname or "").strip() or None

        display_name = data["name"]
        if nick:
            display_name = f"{nick} ({data['name']})"

        # Эмбед
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