"""Локации Тэнхо: названия, эмодзи, чёрные списки спавна.

exclude — покемоны, которые НЕ водятся в этой локации.
Общий запрет (FORBIDDEN_SPECIES) — легендарные, мифические, фоссилы.
"""
from __future__ import annotations


# ==========================================================================
#  ОБЩИЙ ЧЁРНЫЙ СПИСОК — не появляются нигде
# ==========================================================================
FORBIDDEN_SPECIES: set[str] = {
    # --- Легендарные ---
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
    # --- Мифические ---
    "mew", "celebi", "jirachi", "deoxys",
    "phione", "manaphy", "darkrai", "shaymin", "arceus",
    "victini", "keldeo", "meloetta", "genesect",
    "diancie", "hoopa", "volcanion",
    "magearna", "marshadow", "zeraora", "meltan", "melmetal",
    "zarude",
    # --- Фоссилы (вымершие) ---
    "omanyte", "omastar", "kabuto", "kabutops", "aerodactyl",
    "lileep", "cradily", "anorith", "armaldo", "shieldon",
    "bastiodon", "cranidos", "rampardos", "tirtouga", "carracosta",
    "archen", "archeops", "tyrunt", "tyrantrum", "amaura", "aurorus",
    "dracozolt", "arctozolt", "dracovish", "arctovish",
}


# ==========================================================================
#  ЛОКАЦИИ
#  exclude — кого НЕ должно быть в этой локации.
# ==========================================================================
LOCATIONS: dict[str, dict] = {
    "hoshinori": {
        "name": "Хошинори", "emoji": "✨",
        "exclude": [
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "gyarados", "tyranitar", "bagon",
            "deino", "larvitar", "vullaby", "sandile", "skorupi",
            "heatmor", "durant", "onix", "geodude", "magnemite",
        ],
    },
    "lastoris": {
        "name": "Ласторис", "emoji": "🌊",
        "exclude": [],
    },
    "verden": {
        "name": "Верден", "emoji": "🌿",
        "exclude": [
            "klink", "magnemite", "rotom", "voltorb", "bronzor",
            "porygon", "beldum", "durant", "ferroseed", "klefki",
            "onix", "roggenrola", "solosis", "elgyem", "nosepass",
            "drilbur", "numel", "sandshrew", "trapinch", "vulpix-alola",
        ],
    },
    "kaiseki": {
        "name": "Кайсэки", "emoji": "🔥",
        "exclude": [
            "luvdisc", "spinda", "munna", "swablu", "jigglypuff",
            "comfey", "flabebe", "cottonee", "cutiefly", "wynaut",
            "igglybuff", "cleffa", "skitty", "buneary", "deerling",
            "sunkern", "oddish", "hoppip", "wooloo", "bidoof",
        ],
    },
    "nordkron": {
        "name": "Нордкрон", "emoji": "❄️",
        "exclude": [
            "combee", "sunflora", "exeggcute", "bellsprout", "trapinch",
            "growlithe", "vulpix", "bounsweet", "fomantis", "petilil",
            "cherubi", "skiddo", "deerling", "karrablast", "shelmet",
            "volbeat", "illumise", "wurmple", "caterpie", "oddish",
        ],
    },
    "aurelis": {
        "name": "Аурелис", "emoji": "⚡",
        "exclude": [
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "trapinch", "sandile", "roggenrola", "ferroseed", "klink",
            "numel", "larvitar", "gible", "bagon", "deino",
            "sableye", "carbink", "rhyhorn", "geodude", "drilbur",
        ],
    },
    "hibiki": {
        "name": "Хибики", "emoji": "🎐",
        "exclude": [
            "sudowoodo", "bonsly", "trapinch", "sandshrew", "numel",
            "torkoal", "larvitar", "roggenrola", "onix", "geodude",
            "diglett", "bagon", "gible", "ferroseed", "klink",
            "magnemite", "durant", "snover", "snorunt", "bergmite",
        ],
    },
    "kurokane": {
        "name": "Курокане", "emoji": "⚙️",
        "exclude": [
            "cherubi", "flabebe", "petilil", "deerling", "comfey",
            "cutiefly", "bounsweet", "fomantis", "sunkern", "hoppip",
            "skiddo", "oddish", "tangela", "budew", "foongus",
            "karrablast", "shelmet", "volbeat", "illumise", "cottonee",
        ],
    },
    "lumier": {
        "name": "Люмьер", "emoji": "💫",
        "exclude": [
            "diglett", "wooper", "onix", "nosepass", "baltoy",
            "geodude", "roggenrola", "ferroseed", "trapinch", "sandile",
            "klink", "magnemite", "durant", "larvitar", "gible",
            "bagon", "deino", "sudowoodo", "bonsly", "numel",
        ],
    },
    "estera": {
        "name": "Эстера", "emoji": "🔮",
        "exclude": [
            "zangoose", "seviper", "mankey", "primeape", "ursaring",
            "houndour", "absol", "sableye", "mawile", "gible",
            "trapinch", "scraggy", "tauros", "rhyhorn", "gyarados",
            "tyranitar", "bagon", "deino", "larvitar", "heatmor",
        ],
    },
    "reigard": {
        "name": "Рейгард", "emoji": "🐉",
        "exclude": [
            "comfey", "cutiefly", "flabebe", "cottonee", "luvdisc",
            "jigglypuff", "igglybuff", "cleffa", "skitty", "swablu",
            "wynaut", "munna", "bounsweet", "deerling", "sunkern",
            "hoppip", "wooloo", "oddish", "buneary", "combee",
        ],
    },
    "eidolon": {
        "name": "Эйдолон", "emoji": "👻",
        "exclude": [
            "zigzagoon", "rattata", "bidoof", "skwovet", "yungoos",
            "poochyena", "wurmple", "caterpie", "weedle", "ledyba",
            "spinarak", "sentret", "pidgey", "starly", "lillipup",
            "sunkern", "hoppip", "tangela", "oddish", "zubat",
        ],
    },
    "asteris": {
        "name": "Астэрис", "emoji": "🏛️",
        "exclude": [
            "machop", "timburr", "scraggy", "crabrawler", "zangoose",
            "seviper", "mankey", "primeape", "ursaring", "tauros",
            "rhyhorn", "gible", "bagon", "larvitar", "magikarp",
            "wailmer", "corphish", "krabby", "sandile", "trapinch",
        ],
    },
    "tsukishiro": {
        "name": "Цукисиро", "emoji": "🌙",
        "exclude": [
            "chatot", "exploud", "loudred", "helioptile", "bunnelby",
            "skwovet", "combee", "ledyba", "fletchling", "taillow",
            "wooloo", "buneary", "pichu", "skitty", "vulpix",
            "growlithe", "numel", "torkoal", "bounsweet", "fomantis",
        ],
    },
    "red_canyon": {
        "name": "Красный Каньон", "emoji": "🔴",
        "exclude": [
            "poliwag", "poliwhirl", "lapras", "snover", "sudowoodo",
            "ferroseed", "wooper", "marill", "azurill", "buizel",
            "psyduck", "magikarp", "corphish", "krabby", "wingull",
            "pelipper", "snorunt", "bergmite", "cubchoo", "snom",
        ],
    },
    "white_silence": {
        "name": "Белое Безмолвие", "emoji": "⚪",
        "exclude": [
            "fomantis", "growlithe", "combee", "skiddo", "bounsweet",
            "sunkern", "hoppip", "oddish", "tangela", "cherubi",
            "petilil", "karrablast", "shelmet", "volbeat", "illumise",
            "cutiefly", "comf
