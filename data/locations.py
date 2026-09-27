"""Все локации: название, эмодзи, пул спавна.

Пулы указаны по английским именам PokéAPI.
Исключены: легендарные, мифические и вымершие (фоссилы).
"""
from __future__ import annotations

from typing import Any, Optional


LOCATIONS: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------ #
    #                       ОСНОВНЫЕ 13 ЛОКАЦИЙ                          #
    # ------------------------------------------------------------------ #
    "hoshinori": {
        "name": "Хошинори",
        "emoji": "✨",
        "encounters": [
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "gyarados", "tyranitar", "bagon",
            "deino", "larvitar", "vullaby", "sandile", "skorupi",
            "heatmor", "durant", "onix", "geodude", "magnemite",
        ],
    },
    "lastoris": {
        "name": "Ласторис",
        "emoji": "🌊",
        "encounters": [],
    },
    "verden": {
        "name": "Верден",
        "emoji": "🌿",
        "encounters": [
            "klink", "magnemite", "rotom", "voltorb", "bronzor",
            "porygon", "beldum", "durant", "ferroseed", "klefki",
            "onix", "roggenrola", "solosis", "elgyem", "nosepass",
            "drilbur", "numel", "sandshrew", "trapinch", "vulpix-alola",
        ],
    },
    "kaiseki": {
        "name": "Кайсэки",
        "emoji": "🔥",
        "encounters": [
            "luvdisc", "spinda", "munna", "swablu", "jigglypuff",
            "comfey", "flabebe", "cottonee", "cutiefly", "wynaut",
            "igglybuff", "cleffa", "skitty", "buneary", "deerling",
            "sunkern", "oddish", "hoppip", "wooloo", "bidoof",
        ],
    },
    "nordkron": {
        "name": "Нордкрон",
        "emoji": "❄️",
        "encounters": [
            "combee", "sunflora", "exeggcute", "bellsprout", "trapinch",
            "growlithe", "vulpix", "bounsweet", "fomantis", "petilil",
            "cherubi", "skiddo", "deerling", "karrablast", "shelmet",
            "volbeat", "illumise", "wurmple", "caterpie", "oddish",
        ],
    },
    "aurelis": {
        "name": "Аурелис",
        "emoji": "⚡",
        "encounters": [
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "trapinch", "sandile", "roggenrola", "ferroseed", "klink",
            "numel", "larvitar", "gible", "bagon", "deino",
            "sableye", "carbink", "rhyhorn", "geodude", "drilbur",
        ],
    },
    "hibiki": {
        "name": "Хибики",
        "emoji": "🎐",
        "encounters": [
            "sudowoodo", "bonsly", "trapinch", "sandshrew", "numel",
            "torkoal", "larvitar", "roggenrola", "onix", "geodude",
            "diglett", "bagon", "gible", "ferroseed", "klink",
            "magnemite", "durant", "snover", "snorunt", "bergmite",
        ],
    },
    "kurokane": {
        "name": "Курокане",
        "emoji": "⚙️",
        "encounters": [
            "cherubi", "flabebe", "petilil", "deerling", "comfey",
            "cutiefly", "bounsweet", "fomantis", "sunkern", "hoppip",
            "skiddo", "oddish", "tangela", "budew", "foongus",
            "karrablast", "shelmet", "volbeat", "illumise", "cottonee",
        ],
    },
    "lumier": {
        "name": "Люмьер",
        "emoji": "💫",
        "encounters": [
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "geodude", "roggenrola", "ferroseed", "trapinch", "sandile",
            "klink", "magnemite", "durant", "larvitar", "gible",
            "bagon", "deino", "sudowoodo", "bonsly", "numel",
        ],
    },
    "estera": {
        "name": "Эстера",
        "emoji": "🔮",
        "encounters": [
            "zangoose", "seviper", "mankey", "primeape", "ursaring",
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "tauros", "rhyhorn", "gyarados",
            "tyranitar", "bagon", "deino", "larvitar", "heatmor",
        ],
    },
    "reigard": {
        "name": "Рейгард",
        "emoji": "🐉",
        "encounters": [
            "comfey", "cutiefly", "flabebe", "cottonee", "luvdisc",
            "jigglypuff", "igglybuff", "cleffa", "skitty", "swablu",
            "wynaut", "munna", "bounsweet", "deerling", "sunkern",
            "hoppip", "wooloo", "oddish", "buneary", "combee",
        ],
    },
    "eidolon": {
        "name": "Эйдолон",
        "emoji": "👻",
        "encounters": [
            "zigzagoon", "rattata", "bidoof", "skwovet", "yungoos",
            "poochyena", "wurmple", "caterpie", "weedle", "ledyba",
            "spinarak", "sentret", "pidgey", "starly", "lillipup",
            "sunkern", "hoppip", "tangela", "oddish", "zubat",
        ],
    },
    "asteris": {
        "name": "Астэрис",
        "emoji": "🏛️",
        "encounters": [
            "machop", "timburr", "scraggy", "crabrawler", "zangoose",
            "seviper", "mankey", "primeape", "ursaring", "tauros",
            "rhyhorn", "gible", "bagon", "larvitar", "magikarp",
            "wailmer", "corphish", "krabby", "sandile", "trapinch",
        ],
    },

    # ------------------------------------------------------------------ #
    #                    ДОПОЛНИТЕЛЬНЫЕ ЛОКАЦИИ                          #
    # ------------------------------------------------------------------ #
    "tsukishiro": {
        "name": "Цукисиро",
        "emoji": "🌙",
        "encounters": [
            "chatot", "exploud", "loudred", "helioptile", "bunnelby",
            "skwovet", "combee", "ledyba", "fletchling", "taillow",
            "wooloo", "buneary", "pichu", "skitty", "vulpix",
            "growlithe", "numel", "torkoal", "bounsweet", "fomantis",
        ],
    },
    "red_canyon": {
        "name": "Красный Каньон",
        "emoji": "🔴",
        "encounters": [
            "poliwag", "poliwhirl", "lapras", "snover", "sudowoodo",
            "ferroseed", "wooper", "marill", "azurill", "buizel",
            "psyduck", "magikarp", "corphish", "krabby", "wingull",
            "pelipper", "snorunt", "bergmite", "cubchoo", "snom",
        ],
    },
    "white_silence": {
        "name": "Белое Безмолвие",
        "emoji": "⚪",
        "encounters": [
            "fomantis", "growlithe", "combee", "skiddo", "bounsweet",
            "sunkern", "hoppip", "oddish", "tangela", "cherubi",
            "petilil", "karrablast", "shelmet", "volbeat", "illumise",
            "cutiefly", "comfey", "torkoal", "numel", "vulpix",
        ],
    },
    "melancholic_swamps": {
        "name": "Болота Меланхолии",
        "emoji": "🌫️",
        "encounters": [
            "vulpix", "growlithe", "litten", "fletchling", "blitzle",
            "pichu", "emolga", "dedenne", "charjabug", "grubbin",
            "skwovet", "yungoos", "buneary", "sentret", "zigzagoon",
            "rattata", "pidgey", "starly", "wooloo", "lillipup",
        ],
    },
    "guardians_plateau": {
        "name": "Плато Стражей",
        "emoji": "🗿",
        "encounters": [
            "magikarp", "wailmer", "corphish", "krabby", "buizel",
            "psyduck", "poliwag", "marill", "azurill", "luvdisc",
            "comfey", "flabebe", "cutiefly", "cottonee", "skitty",
            "bounsweet", "fomantis", "petilil", "cherubi", "sunkern",
        ],
    },
    "phantoms_gate": {
        "name": "Phantom's Gate",
        "emoji": "👻",
        "encounters": [
            "skitty", "buneary", "cleffa", "igglybuff", "jigglypuff",
            "wooloo", "bounsweet", "sunkern", "hoppip", "cottonee",
            "comfey", "flabebe", "cutiefly", "deerling", "skiddo",
            "pichu", "emolga", "dedenne", "combee", "ledyba",
        ],
    },
}


LOCATION_NAMES: dict[str, str] = {
    key: f"{data['emoji']} {data['name']}"
    for key, data in LOCATIONS.items()
}


def get_location(location_id: Optional[str]) -> dict[str, Any]:
    if not location_id or location_id not in LOCATIONS:
        return LOCATIONS["hoshinori"]
    return LOCATIONS[location_id]


def location_title(location_id: Optional[str]) -> str:
    loc = get_location(location_id)
    return f"{loc['emoji']} {loc['name']}"


def all_location_ids() -> list[str]:
    return list(LOCATIONS.keys())


def find_location_by_channel_name(channel_name: str) -> Optional[str]:
    """Ищет ключ локации по имени канала Discord."""
    if not channel_name:
        return None
    low = channel_name.lower().replace("_", "-")
    for key, data in LOCATIONS.items():
        if key in low:
            return key
        ru = data["name"].lower().replace(" ", "-")
        if ru in low:
            return key
    return None