"""Справочники для боевой системы: типы, эффективности, стадии, характеры, погода."""
from __future__ import annotations


# ==========================================================================
#  ТИПЫ И ЭФФЕКТИВНОСТЬ
# ==========================================================================
TYPE_CHART: dict[str, dict[str, float]] = {
    "normal":   {"rock": 0.5, "ghost": 0, "steel": 0.5},
    "fire":     {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 2,
                 "bug": 2, "rock": 0.5, "dragon": 0.5, "steel": 2},
    "water":    {"fire": 2, "water": 0.5, "grass": 0.5, "ground": 2,
                 "rock": 2, "dragon": 0.5},
    "electric": {"water": 2, "electric": 0.5, "grass": 0.5, "ground": 0,
                 "flying": 2, "dragon": 0.5},
    "grass":    {"fire": 0.5, "water": 2, "grass": 0.5, "poison": 0.5,
                 "ground": 2, "flying": 0.5, "bug": 0.5, "rock": 2,
                 "dragon": 0.5, "steel": 0.5},
    "ice":      {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 0.5,
                 "ground": 2, "flying": 2, "dragon": 2, "steel": 0.5},
    "fighting": {"normal": 2, "ice": 2, "poison": 0.5, "flying": 0.5,
                 "psychic": 0.5, "bug": 0.5, "rock": 2, "ghost": 0,
                 "dark": 2, "steel": 2, "fairy": 0.5},
    "poison":   {"grass": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5,
                 "ghost": 0.5, "steel": 0, "fairy": 2},
    "ground":   {"fire": 2, "electric": 2, "grass": 0.5, "poison": 2,
                 "flying": 0, "bug": 0.5, "rock": 2, "steel": 2},
    "flying":   {"electric": 0.5, "grass": 2, "fighting": 2, "bug": 2,
                 "rock": 0.5, "steel": 0.5},
    "psychic":  {"fighting": 2, "poison": 2, "psychic": 0.5, "dark": 0,
                 "steel": 0.5},
    "bug":      {"fire": 0.5, "grass": 2, "fighting": 0.5, "poison": 0.5,
                 "flying": 0.5, "psychic": 2, "ghost": 0.5, "dark": 2,
                 "steel": 0.5, "fairy": 0.5},
    "rock":     {"fire": 2, "ice": 2, "fighting": 0.5, "ground": 0.5,
                 "flying": 2, "bug": 2, "steel": 0.5},
    "ghost":    {"normal": 0, "psychic": 2, "ghost": 2, "dark": 0.5},
    "dragon":   {"dragon": 2, "steel": 0.5, "fairy": 0},
    "dark":     {"fighting": 0.5, "psychic": 2, "ghost": 2, "dark": 0.5,
                 "fairy": 0.5},
    "steel":    {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2,
                 "rock": 2, "steel": 0.5, "fairy": 2},
    "fairy":    {"fire": 0.5, "fighting": 2, "poison": 0.5, "dragon": 2,
                 "dark": 2, "steel": 0.5},
}


def get_type_multiplier(attack_type: str, defender_types: list[str]) -> float:
    mult = 1.0
    row = TYPE_CHART.get(attack_type, {})
    for d in defender_types:
        mult *= row.get(d, 1.0)
    return mult


def damage_label(mult: float) -> str:
    if mult == 0:
        return "❌ Не действует"
    if mult >= 4:
        return "🔥 Сверхэффективно!"
    if mult >= 2:
        return "✨ Суперэффективно!"
    if mult <= 0.25:
        return "🛡️ Совсем неэффективно…"
    if mult <= 0.5:
        return "🛡️ Не очень эффективно…"
    return ""


# ==========================================================================
#  СТАДИИ
# ==========================================================================
STAGE_MULTIPLIERS: dict[int, float] = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1.0,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2,
}


def stage_mult(stage: int) -> float:
    stage = max(-6, min(6, int(stage)))
    return STAGE_MULTIPLIERS[stage]


# ==========================================================================
#  ХАРАКТЕРЫ
# ==========================================================================
NATURES: dict[str, tuple[str | None, str | None]] = {
    "hardy":   (None, None),
    "lonely":  ("attack", "defense"),
    "brave":   ("attack", "speed"),
    "adamant": ("attack", "sp_attack"),
    "naughty": ("attack", "sp_defense"),
    "bold":    ("defense", "attack"),
    "docile":  (None, None),
    "relaxed": ("defense", "speed"),
    "impish":  ("defense", "sp_attack"),
    "lax":     ("defense", "sp_defense"),
    "timid":   ("speed", "attack"),
    "hasty":   ("speed", "defense"),
    "serious": (None, None),
    "jolly":   ("speed", "sp_attack"),
    "naive":   ("speed", "sp_defense"),
    "modest":  ("sp_attack", "attack"),
    "mild":    ("sp_attack", "defense"),
    "quiet":   ("sp_attack", "speed"),
    "bashful": (None, None),
    "rash":    ("sp_attack", "sp_defense"),
    "calm":    ("sp_defense", "attack"),
    "gentle":  ("sp_defense", "defense"),
    "sassy":   ("sp_defense", "speed"),
    "careful": ("sp_defense", "sp_attack"),
    "quirky":  (None, None),
}


def nature_multiplier(nature: str | None) -> dict[str, float]:
    base = {"attack": 1.0, "defense": 1.0, "sp_attack": 1.0,
            "sp_defense": 1.0, "speed": 1.0}
    if not nature:
        return base
    up, down = NATURES.get(nature.lower(), (None, None))
    if up:
        base[up] = 1.1
    if down:
        base[down] = 0.9
    return base


# ==========================================================================
#  СТАТУСЫ
# ==========================================================================
STATUS_EMOJI = {
    "none": "",
    "burn": "🟥",
    "poison": "🟪",
    "paralysis": "🟨",
    "sleep": "💤",
    "freeze": "❄️",
    "confused": "🌀",
    "badly_poison": "🟪",
}

STATUS_BONUS_CATCH = {
    "sleep": 2.5,
    "freeze": 2.5,
    "paralysis": 1.5,
    "burn": 1.5,
    "poison": 1.5,
    "none": 1.0,
}


# ==========================================================================
#  ПОГОДА
# ==========================================================================
WEATHER_LABEL: dict[str, str] = {
    "none":       "— Ясно",
    "sunny":      "☀️ Солнце",
    "rain":       "🌧️ Дождь",
    "sandstorm":  "🏜️ Песчаная буря",
    "snow":       "❄️ Снег",
    "fog":        "🌫️ Туман",
}

# Множители урона по типу атаки
WEATHER_DAMAGE_MULT: dict[str, dict[str, float]] = {
    "sunny":     {"fire": 1.5, "water": 0.5},
    "rain":      {"water": 1.5, "fire": 0.5},
    "sandstorm": {},
    "snow":      {"ice": 1.5},
    "fog":       {},
    "none":      {},
}

# Множители точности
WEATHER_ACCURACY_MULT: dict[str, dict[str, float]] = {
    "sunny":     {},
    "rain":      {"thunder": 1.0, "hurricane": 1.0},
    "sandstorm": {},
    "snow":      {"blizzard": 1.0},
    "fog":       {},
    "none":      {},
}

# Урон в конце хода по типу покемона
WEATHER_TICK_DAMAGE: dict[str, dict] = {
    "sandstorm": {"immune_types": ["rock", "ground", "steel"], "fraction": 16},
    "snow":      {"immune_types": ["ice"], "fraction": 16},
}

# Погодные атаки → какая погода
WEATHER_MOVES: dict[str, str] = {
    "rain-dance":  "rain",
    "sunny-day":   "sunny",
    "sandstorm":   "sandstorm",
    "snowscape":   "snow",
    "hail":        "snow",
    "chilly-reception": "snow",
}

# Способности → какая погода
WEATHER_ABILITIES: dict[str, str] = {
    "drizzle":      "rain",
    "drought":      "sunny",
    "sand-stream":  "sandstorm",
    "snow-warning": "snow",
    "sand-spit":    "sandstorm",
}

# Погодные камни → продлевают погоду
WEATHER_ROCKS = {
    "damp-rock":    "rain",
    "heat-rock":    "sunny",
    "smooth-rock":  "sandstorm",
    "icy-rock":     "snow",
}

WEATHER_DURATION_DEFAULT = 5
WEATHER_DURATION_EXTENDED = 8
