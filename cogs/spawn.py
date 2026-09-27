"""Спавн покемонов мастером — /spawn с условиями, уровнями и редкостью."""
import asyncio
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
#  ГЛОБАЛЬНЫЙ ЧЁРНЫЙ СПИСОК (легендарные, мифические, фоссилы)
# ==========================================================================
_FORBIDDEN_RAW = (
    "articuno,zapdos,moltres,mewtwo,"
    "raikou,entei,suicune,lugia,ho-oh,"
    "regirock,regice,registeel,latias,latios,"
    "kyogre,groudon,rayquaza,"
    "uxie,mesprit,azelf,dialga,palkia,heatran,"
    "regigigas,giratina,cresselia,"
    "cobalion,terrakion,virizion,tornadus,thundurus,"
    "reshiram,zekrom,landorus,kyurem,"
    "xerneas,yveltal,zygarde,"
    "tapu-koko,tapu-lele,tapu-bulu,tapu-fini,"
    "cosmog,cosmoem,solgaleo,lunala,necrozma,"
    "zacian,zamazenta,eternatus,kubfu,urshifu,"
    "regieleki,regidrago,glastrier,spectrier,calyrex,"
    "enamorus,koraidon,miraidon,ting-lu,chien-pao,wo-chien,"
    "chi-yu,walking-wake,iron-leaves,okidogi,"
    "munkidori,fezandipiti,ogerpon,terapagos,pecharunt,"
    "mew,celebi,jirachi,deoxys,"
    "phione,manaphy,darkrai,shaymin,arceus,"
    "victini,keldeo,meloetta,genesect,"
    "diancie,hoopa,volcanion,"
    "magearna,marshadow,zeraora,meltan,melmetal,zarude,"
    "omanyte,omastar,kabuto,kabutops,aerodactyl,"
    "lileep,cradily,anorith,armaldo,shieldon,"
    "bastiodon,cranidos,rampardos,tirtouga,carracosta,"
    "archen,archeops,tyrunt,tyrantrum,amaura,aurorus,"
    "dracozolt,arctozolt,dracovish,arctovish"
)
FORBIDDEN_SPECIES: set[str] = set(_FORBIDDEN_RAW.split(","))


# ==========================================================================
#  ЧЁРНЫЕ СПИСКИ ЛОКАЦИЙ (строки через запятую)
# ==========================================================================
_BLACKLISTS_RAW = {
    "hoshinori": (
        "Хошинори", "✨",
        "houndour,absol,sableye,mawile,gible,trapinch,scraggy,gyarados,"
        "tyranitar,bagon,deino,larvitar,vullaby,sandile,skorupi,"
        "heatmor,durant,onix,geodude,magnemite"
    ),
    "verden": (
        "Верден", "🌿",
        "klink,magnemite,rotom,voltorb,bronzor,porygon,beldum,durant,"
        "ferroseed,klefki,onix,roggenrola,solosis,elgyem,nosepass,"
        "drilbur,numel,sandshrew,trapinch,vulpix-alola"
    ),
    "kaiseki": (
        "Кайсэки", "🔥",
        "luvdisc,spinda,munna,swablu,jigglypuff,comfey,flabebe,cottonee,"
        "cutiefly,wynaut,igglybuff,cleffa,skitty,buneary,deerling,"
        "sunkern,oddish,hoppip,wooloo,bidoof"
    ),
    "nordkron": (
        "Нордкрон", "❄️",
        "combee,sunflora,exeggcute,bellsprout,trapinch,growlithe,vulpix,"
        "bounsweet,fomantis,petilil,cherubi,skiddo,deerling,karrablast,"
        "shelmet,volbeat,illumise,wurmple,caterpie,oddish"
    ),
    "aurelis": (
        "Аурелис", "⚡",
        "diglett,wooper,onix,nosepass,baltoy,trapinch,sandile,roggenrola,"
        "ferroseed,klink,numel,larvitar,gible,bagon,deino,sableye,"
        "carbink,rhyhorn,geodude,drilbur"
    ),
    "hibiki": (
        "Хибики", "🎐",
        "sudowoodo,bonsly,trapinch,sandshrew,numel,torkoal,larvitar,"
        "roggenrola,onix,geodude,diglett,bagon,gible,ferroseed,klink,"
        "magnemite,durant,snover,snorunt,bergmite"
    ),
    "kurokane": (
        "Курокане", "⚙️",
        "cherubi,flabebe,petilil,deerling,comfey,cutiefly,bounsweet,"
        "fomantis,sunkern,hoppip,skiddo,oddish,tangela,budew,foongus,"
        "karrablast,shelmet,volbeat,illumise,cottonee"
    ),
    "lumier": (
        "Люмьер", "💫",
        "diglett,wooper,onix,nosepass,baltoy,geodude,roggenrola,ferroseed,"
        "trapinch,sandile,klink,magnemite,durant,larvitar,gible,bagon,"
        "deino,sudowoodo,bonsly,numel"
    ),
    "estera": (
        "Эстера", "🔮",
        "zangoose,seviper,mankey,primeape,ursaring,houndour,absol,sableye,"
        "mawile,gible,trapinch,scraggy,tauros,rhyhorn,gyarados,tyranitar,"
        "bagon,deino,larvitar,heatmor"
    ),
    "reigard": (
        "Рейгард", "🐉",
        "comfey,cutiefly,flabebe,cottonee,luvdisc,jigglypuff,igglybuff,"
        "cleffa,skitty,swablu,wynaut,munna,bounsweet,deerling,sunkern,"
        "hoppip,wooloo,oddish,buneary,combee"
    ),
    "eidolon": (
        "Эйдолон", "👻",
        "zigzagoon,rattata,bidoof,skwovet,yungoos,poochyena,wurmple,"
        "caterpie,weedle,ledyba,spinarak,sentret,pidgey,starly,lillipup,"
        "sunkern,hoppip,tangela,oddish,zubat"
    ),
    "asteris": (
        "Астэрис", "🏛️",
        "machop,timburr,scraggy,crabrawler,zangoose,seviper,mankey,primeape,"
        "ursaring,tauros,rhyhorn,gible,bagon,larvitar,magikarp,wailmer,"
        "corphish,krabby,sandile,trapinch"
    ),
    "tsukishiro": (
        "Цукисиро", "🌙",
        "chatot,exploud,loudred,helioptile,bunnelby,skwovet,combee,ledyba,"
        "fletchling,taillow,wooloo,buneary,pichu,skitty,vulpix,growlithe,"
        "numel,torkoal,bounsweet,fomantis"
    ),
    "red_canyon": (
        "Красный Каньон", "🔴",
        "poliwag,poliwhirl,lapras,snover,sudowoodo,ferroseed,wooper,marill,"
        "azurill,buizel,psyduck,magikarp,corphish,krabby,wingull,pelipper,"
        "snorunt,bergmite,cubchoo,snom"
    ),
    "white_silence": (
        "Белое Безмолвие", "⚪",
        "fomantis,growlithe,combee,skiddo,bounsweet,sunkern,hoppip,oddish,"
        "tangela,cherubi,petilil,karrablast,shelmet,volbeat,illumise,"
        "cutiefly,comfey,torkoal,numel,vulpix"
    ),
    "melancholic_swamps": (
        "Болота Меланхолии", "🌫️",
        "vulpix,growlithe,litten,fletchling,blitzle,pichu,emolga,dedenne,"
        "charjabug,grubbin,skwovet,yungoos,buneary,sentret,zigzagoon,"
        "rattata,pidgey,starly,wooloo,lillipup"
    ),
    "guardians_plateau": (
        "Плато Стражей", "🗿",
        "magikarp,wailmer,corphish,krabby,buizel,psyduck,poliwag,marill,"
        "azurill,luvdisc,comfey,flabebe,cutiefly,cottonee,skitty,bounsweet,"
        "fomantis,petilil,cherubi,sunkern"
    ),
    "phantoms_gate": (
        "Phantom's Gate", "👻",
        "skitty,buneary,cleffa,igglybuff,jigglypuff,wooloo,bounsweet,"
        "sunkern,hoppip,cottonee,comfey,flabebe,cutiefly,deerling,skiddo,"
        "pichu,emolga,dedenne,combee,ledyba"
    ),
}

_BLACKLISTS: dict[str, dict] = {
    key: {"name": name, "emoji": emoji, "blacklist": set(raw.split(","))}
    for key, (name, emoji, raw) in _BLACKLISTS_RAW.items()
}


# ==========================================================================
#  УРОВНИ ПО СТАДИИ ЭВОЛЮЦИИ
# ==========================================================================
# 0 — базовая форма:   2..20
# 1 — 1-я эволюция:   16..40
# 2 — 2-я эволюция:   30..70
# 3+ — редкие длинные: 45..90
_LEVEL_BY_STAGE: dict[int, tuple[int, int]] = {
    0: (2, 20),
    1: (16, 40),
    2: (30, 70),
    3: (45, 90),
    4: (50, 95),
}


def find_location_by_channel_name(channel_name: str) -> str | None:
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


# ==========================================================================
#  КЭШИ
# ==========================================================================
_type_ids_cache: dict[str, set[int]] = {}
_forbidden_ids_cache: Optional[set[int]] = None
_blacklist_ids_cache: dict[str, set[int]] = {}
_species_cache: dict[int, dict] = {}
_stage_cache: dict[int, int] = {}


# --------------------------------------------------------------------------- #
#                     ПОКЕАПИ: ТИПЫ, СТАДИИ, SPECIES                          #
# --------------------------------------------------------------------------- #

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


async def _get_species_data(pokemon_id: int) -> Optional[dict]:
    if pokemon_id in _species_cache:
        return _species_cache[pokemon_id]
    try:
        data = await pokeapi_client._fetch_json(
            f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_id}"
        )
        _species_cache[pokemon_id] = data
        return data
    except PokeAPIError:
        return None


def _walk_chain(node: dict, target_id: int, depth: int = 0) -> Optional[int]:
    """Ищет target_id в цепочке эволюции, возвращает глубину."""
    species_url = (node.get("species") or {}).get("url", "")
    try:
        node_id = int(species_url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        node_id = None
    if node_id == target_id:
        return depth
    for evo in node.get("evolves_to", []) or []:
        result = _walk_chain(evo, target_id, depth + 1)
        if result is not None:
            return result
    return None


async def _get_evolution_stage(pokemon_id: int) -> int:
    """0 — базовая форма, 1 — 1-я эво, 2 — 2-я и т.д."""
    if pokemon_id in _stage_cache:
        return _stage_cache[pokemon_id]

    species = await _get_species_data(pokemon_id)
    if not species:
        _stage_cache[pokemon_id] = 0
        return 0

    chain_url = (species.get("evolution_chain") or {}).get("url")
    if not chain_url:
        _stage_cache[pokemon_id] = 0
        return 0

    try:
        chain_data = await pokeapi_client._fetch_json(chain_url)
    except PokeAPIError:
        _stage_cache[pokemon_id] = 0
        return 0

    chain = chain_data.get("chain") or {}
    stage = _walk_chain(chain, pokemon_id)
    if stage is None:
        stage = 0
    _stage_cache[pokemon_id] = stage
    return stage


async def _resolve_names(names: set[str]) -> set[int]:
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
    loc = _BLACKLISTS.get(loc_key, {})
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
    pool: set[int] = set(range(1, 1026))
    pool -= await _get_global_forbidden()
    pool -= await _get_blacklist_ids(loc_key)

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

    if lure and lure != "none":
        pool &= await _get_type_ids(lure)

    return pool


async def _pick_weighted(candidates: list[int]) -> Optional[int]:
    """Взвешенный выбор по capture_rate. Редкие — реже."""
    if not candidates:
        return None

    species_list = await asyncio.gather(
        *[_get_species_data(pid) for pid in candidates],
        return_exceptions=True,
    )

    weighted: list[tuple[int, float]] = []
    for pid, species in zip(candidates, species_list):
        if not isinstance(species, dict):
            # Не удалось загрузить — даём средний вес
            weighted.append((pid, 20.0))
            continue
        rate = int(species.get("capture_rate") or 100)
        # rate^0.7 — плавная кривая, чтобы редкие не исчезали совсем
        weight = max(1.0, rate ** 0.7)
        weighted.append((pid, weight))

    if not weighted:
        return None

    total = sum(w for _, w in weighted)
    r = random.random() * total
    cumul = 0.0
    for pid, w in weighted:
        cumul += w
        if cumul >= r:
            return pid
    return weighted[-1][0]


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
        level="Уровень (бот поднимет до минимума по стадии эволюции)",
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
        level: Optional[app_commands.Range[int, 1, 100]] = None,
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

        # Берём до 15 случайных кандидатов и выбираем взвешенно по редкости
        sample_size = min(15, len(pool_list))
        candidates = random.sample(pool_list, sample_size)
        chosen_id = await _pick_weighted(candidates)
        if chosen_id is None:
            chosen_id = random.choice(pool_list)

        # Данные покемона
        try:
            data = await pokeapi_client.get_pokemon(chosen_id)
        except PokeAPIError:
            await interaction.followup.send(
                "⚠️ PokéAPI не отвечает, попробуйте позже.", ephemeral=True
            )
            return

        # Стадия эволюции → границы уровня
        stage = await _get_evolution_stage(chosen_id)
        min_lv, max_lv = _LEVEL_BY_STAGE.get(stage, (2, 20))

        # Уровень
        if level is None:
            final_level = random.randint(min_lv, max_lv)
        else:
            final_level = max(int(level), min_lv)
            final_level = min(final_level, max_lv)

        # Пол
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
        embed.add_field(name="🎚️ Уровень", value=str(final_level))
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
