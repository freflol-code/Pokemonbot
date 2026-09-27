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
#  ОБЩИЙ ЧЁРНЫЙ СПИСОК — не появляются нигде
# ==========================================================================
FORBIDDEN_SPECIES: set[str] = {
    # Легендарные
    "articuno", "zapdos", "moltres", "mewtwo",
    "raikou", "entei", "suicune", "lugia", "ho-oh",
    "regirock", "regice", "registeel", "latias", "latios",
    "kyogre", "groudon", "rayquaza",
    "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran",
    "regigigas", "giratina", "cresselia",
    "cobalion", "terrakion", "virizion", "tornadus", "thundurus",
    "reshiram", "zekrom", "landorus", "kyurem",
    "xerneas", "yveltal", "zygarde",
    "tapu-koko", "tapu-lele", "tapu-bulu", "tapu-fini",
    "cosmog", "cosmoem", "solgaleo", "lunala", "necrozma",
    "zacian", "zamazenta", "eternatus", "kubfu", "urshifu",
    "regieleki", "regidrago", "glastrier", "spectrier", "calyrex",
    "enamorus",
    "koraidon", "miraidon", "ting-lu", "chien-pao", "wo-chien",
    "chi-yu", "walking-wake", "iron-leaves", "okidogi",
    "munkidori", "fezandipiti", "ogerpon", "terapagos", "pecharunt",
    # Мифические
    "mew", "celebi", "jirachi", "deoxys",
    "phione", "manaphy", "darkrai", "shaymin", "arceus",
    "victini", "keldeo", "meloetta", "genesect",
    "diancie", "hoopa", "volcanion",
    "magearna", "marshadow", "zeraora", "meltan", "melmetal",
    "zarude",
    # Фоссилы
    "omanyte", "omastar", "kabuto", "kabutops", "aerodactyl",
    "lileep", "cradily", "anorith", "armaldo", "shieldon",
    "bastiodon", "cranidos", "rampardos", "tirtouga", "carracosta",
    "archen", "archeops", "tyrunt", "tyrantrum", "amaura", "aurorus",
    "dracozolt", "arctozolt", "dracovish", "arctovish",
}


# ==========================================================================
#  ЛОКАЦИИ — ЧЁРНЫЕ СПИСКИ (кто НЕ должен появляться)
# ==========================================================================
_BLACKLISTS: dict[str, dict] = {
    "hoshinori": {
        "name": "Хошинори", "emoji": "✨",
        "blacklist": {
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "gyarados", "tyranitar", "bagon",
            "deino", "larvitar", "vullaby", "sandile", "skorupi",
            "heatmor", "durant", "onix", "geodude", "magnemite",
        },
    },
    "verden": {
        "name": "Верден", "emoji": "🌿",
        "blacklist": {
            "klink", "magnemite", "rotom", "voltorb", "bronzor",
            "porygon", "beldum", "durant", "ferroseed", "klefki",
            "onix", "roggenrola", "solosis", "elgyem", "nosepass",
            "drilbur", "numel", "sandshrew", "trapinch", "vulpix-alola",
        },
    },
    "kaiseki": {
        "name": "Кайсэки", "emoji": "🔥",
        "blacklist": {
            "luvdisc", "spinda", "munna", "swablu", "jigglypuff",
            "comfey", "flabebe", "cottonee", "cutiefly", "wynaut",
            "igglybuff", "cleffa", "skitty", "buneary", "deerling",
            "sunkern", "oddish", "hoppip", "wooloo", "bidoof",
        },
    },
    "nordkron": {
        "name": "Нордкрон", "emoji": "❄️",
        "blacklist": {
            "combee", "sunflora", "exeggcute", "bellsprout", "trapinch",
            "growlithe", "vulpix", "bounsweet", "fomantis", "petilil",
            "cherubi", "skiddo", "deerling", "karrablast", "shelmet",
            "volbeat", "illumise", "wurmple", "caterpie", "oddish",
        },
    },
    "aurelis": {
        "name": "Аурелис", "emoji": "⚡",
        "blacklist": {
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "trapinch", "sandile", "roggenrola", "ferroseed", "klink",
            "numel", "larvitar", "gible", "bagon", "deino",
            "sableye", "carbink", "rhyhorn", "geodude", "drilbur",
        },
    },
    "hibiki": {
        "name": "Хибики", "emoji": "🎐",
        "blacklist": {
            "sudowoodo", "bonsly", "trapinch", "sandshrew", "numel",
            "torkoal", "larvitar", "roggenrola", "onix", "geodude",
            "diglett", "bagon", "gible", "ferroseed", "klink",
            "magnemite", "durant", "snover", "snorunt", "bergmite",
        },
    },
    "kurokane": {
        "name": "Курокане", "emoji": "⚙️",
        "blacklist": {
            "cherubi", "flabebe", "petilil", "deerling", "comfey",
            "cutiefly", "bounsweet", "fomantis", "sunkern", "hoppip",
            "skiddo", "oddish", "tangela", "budew", "foongus",
            "karrablast", "shelmet", "volbeat", "illumise", "cottonee",
        },
    },
    "lumier": {
        "name": "Люмьер", "emoji": "💫",
        "blacklist": {
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "geodude", "roggenrola", "ferroseed", "trapinch", "sandile",
            "klink", "magnemite", "durant", "larvitar", "gible",
            "bagon", "deino", "sudowoodo", "bonsly", "numel",
        },
    },
    "estera": {
        "name": "Эстера", "emoji": "🔮",
        "blacklist": {
            "zangoose", "seviper", "mankey", "primeape", "ursaring",
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "tauros", "rhyhorn", "gyarados",
            "tyranitar", "bagon", "deino", "larvitar", "heatmor",
        },
    },
    "reigard": {
        "name": "Рейгард", "emoji": "🐉",
        "blacklist": {
            "comfey", "cutiefly", "flabebe", "cottonee", "luvdisc",
            "jigglypuff", "igglybuff", "cleffa", "skitty", "swablu",
            "wynaut", "munna", "bounsweet", "deerling", "sunkern",
            "hoppip", "wooloo", "oddish", "buneary", "combee",
        },
    },
    "eidolon": {
        "name": "Эйдолон", "emoji": "👻",
        "blacklist": {
            "zigzagoon", "rattata", "bidoof", "skwovet", "yungoos",
            "poochyena", "wurmple", "caterpie", "weedle", "ledyba",
            "spinarak", "sentret", "pidgey", "starly", "lillipup",
            "sunkern", "hoppip", "tangela", "oddish", "zubat",
        },
    },
    "asteris": {
        "name": "Астэрис", "emoji": "🏛️",
        "blacklist": {
            "machop", "timburr", "scraggy", "crabrawler", "zangoose",
            "seviper", "mankey", "primeape", "ursaring", "tauros",
            "rhyhorn", "gible", "bagon", "larvitar", "magikarp",
            "wailmer", "corphish", "krabby", "sandile", "trapinch",
        },
    },
    "tsukishiro": {
        "name": "Цукисиро", "emoji": "🌙",
        "blacklist": {
            "chatot", "exploud", "loudred", "helioptile", "bunnelby",
            "skwovet", "combee", "ledyba", "fletchling", "taillow",
            "wooloo", "buneary", "pichu", "skitty", "vulpix",
            "growlithe", "numel", "torkoal", "bounsweet", "fomantis",
        },
    },
    "red_canyon": {
        "name": "Красный Каньон", "emoji": "🔴",
        "blacklist": {
            "poliwag", "poliwhirl", "lapras", "snover", "sudowoodo",
            "ferroseed", "wooper", "marill", "azurill", "buizel",
            "psyduck", "magikarp", "corphish", "krabby", "wingull",
            "pelipper", "snorunt", "bergmite", "cubchoo", "snom",
        },
    },
    "white_silence": {
        "name": "Белое Безмолвие", "emoji": "⚪",
        "blacklist": {
            "fomantis", "growlithe", "combee", "skiddo", "bounsweet",
            "sunkern", "hoppip", "oddish", "tangela", "cherubi",
            "petilil", "karrablast", "shelmet", "volbeat", "illumise",
            "cutiefly", "comfey", "torkoal", "numel", "vulpix",
        },
    },
    "melancholic_swamps": {
        "name": "Болота Меланхолии", "emoji": "🌫️",
        "blacklist": {
            "vulpix", "growlithe", "litten", "fletchling", "blitzle",
            "pichu", "emolga", "dedenne", "charjabug", "grubbin",
            "skwovet", "yungoos", "buneary", "sentret", "zigzagoon",
            "rattata", "pidgey", "starly", "wooloo", "lillipup",
        },
    },
    "guardians_plateau": {
        "name": "Плато Стражей", "emoji": "🗿",
        "blacklist": {
            "magikarp", "wailmer", "corphish", "krabby", "buizel",
            "psyduck", "poliwag", "marill", "azurill", "luvdisc",
            "comfey", "flabebe", "cutiefly", "cottonee", "skitty",
            "bounsweet", "fomantis", "petilil", "cherubi", "sunkern",
        },
    },
    "phantoms_gate": {
        "name": "Phantom's Gate", "emoji": "👻",
        "blacklist": {
            "skitty", "buneary", "cleffa", "igglybuff", "jigglypuff",
            "wooloo", "bounsweet", "sunkern", "hoppip", "cottonee",
            "comfey", "flabebe", "cutiefly", "deerling", "skiddo",
            "pichu", "emolga", "dedenne", "combee", "ledyba",
        },
    },
}


def find_location_by_channel_name(channel_name: str) -> str | None:
    """Ищет ключ локации по имени канала Discord."""
    if not channel_name:
        return None
    low = channel_name.lower().replace("_", "-")
    for key, data in _BLACKLISTS.items():
        if key in low:
            return key
        ru = data["name"].lower().replace(" ", "-")
        if ru in low:
            return key
    return None


def get_location(location_id: str | None) -> dict:
    if not location_id or location_id not in _BLACKLISTS:
        return _BLACKLISTS["hoshinori"]
    return _BLACKLISTS[location_id]


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


# --------------------------------------------------------------------------- #
#                         ТИПЫ И ГЛОБАЛЬНЫЙ ПУЛ                                #
# --------------------------------------------------------------------------- #

_type_ids_cache: dict[str, set[int]] = {}
_forbidden_ids_cache: Optional[set[int]] = None
_blacklist_ids_cache: dict[str, set[int]] = {}


async def _get_type_ids(type_name: str) -> set[int]:
    """ID покемонов указанного типа (1–1025)."""
    if type_name in _type_ids_cache:
        return _type_ids_cache[type_name]
    url = f"https://pokeapi.co/api/v2/type/{type_name}"
    try:
        data = await pokeapi_client._fetch_json(url)
    except PokeAPIError:
        return set()

    out: set[int] = set()
    for entry in data.get("pokemon", []) or []:
        try:
            pid = int(entry["pokemon"]["url"].rstrip("/").split("/")[-1])
        except (KeyError, ValueError):
            continue
        if 1 <= pid <= 1025:
            out.add(pid)
    _type_ids_cache[type_name] = out
    return out


async def _resolve_names(names: set[str]) -> set[int]:
    """Преобразует имена покемонов в ID через PokéAPI."""
    index = await pokeapi_client.get_species_index()
    by_name = {name: pid for pid, name in index}
    return {by_name[n] for n in names if n in by_name}


async def _get_global_forbidden() -> set[int]:
    global _forbidden_ids_cache
    if _forbidden_ids_cache is None:
        _forbidden_ids_cache = await _resolve_names(FORBIDDEN_SPECIES)
    return _forbidden_ids_cache


async def _get_blacklist_ids(loc_key: str) -> set[int]:
    if loc_key in _blacklist_ids_cache:
        return _blacklist_ids_cache[loc_key]
    loc = get_location(loc_key)
    blacklist = loc.get("blacklist") or set()
    if not blacklist:
        _blacklist_ids_cache[loc_key] = set()
        return set()
    ids = await _resolve_names(set(blacklist))
    _blacklist_ids_cache[loc_key] = ids
    return ids


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


async def _filter_pool(loc_key: str, terrain: str, lure: str) -> set[int]:
    """Возвращает ID покемонов, подходящих под условия.

    Старт: все 1–1025
    - чёрный список локации
    - глобальный чёрный список (легендарные/мифические/фоссилы)
    + фильтр по местности
    + фильтр по приманке
    """
    pool: set[int] = set(range(1, 1026))
    pool -= await _get_global_forbidden()
    pool -= await _get_blacklist_ids(loc_key)

    # Фильтр по местности
    if terrain == "water":
        pool &= await _get_type_ids("water")
    elif terrain == "cave":
        pool &= (
            await _get_type_ids("rock")
            | await _get_type_ids("ground")
            | await _get_type_ids("ghost")
        )
    elif terrain == "forest":
        pool &= await _get_type_ids("grass") | await _get_type_ids("bug")

    # Фильтр по приманке
    if lure and lure != "none":
        pool &= await _get_type_ids(lure)

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
                "(например, `#хошинори`, `#цукисиро`).",
                ephemeral=True,
            )
            return

        lure_key = lure.value if lure else "none"

        try:
            pool = await _filter_pool(loc_key, terrain.value, lure_key)
        except Exception as e:
            log.exception("Ошибка фильтрации пула")
            await interaction.followup.send(
                f"⚠️ Ошибка фильтрации: {e}", ephemeral=True
            )
            return

        if not pool:
            await interaction.followup.send(
                "❌ По таким условиям покемон не найден. "
                "Уберите приманку или смените местность.",
                ephemeral=True,
            )
            return

        pool_list = list(pool)
        random.shuffle(pool_list)

        data = None
        for pid in pool_list[:5]:
            try:
                data = await pokeapi_client.get_pokemon(pid)
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
