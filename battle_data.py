"""Справочники боевой системы: типы, стадии, характеры, погода, статусы,
приоритеты, способности, pivot-атаки, крит-стадии, словарь RU→EN атак."""
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
    "badly_poison": "🟪",
    "paralysis": "🟨",
    "sleep": "💤",
    "freeze": "❄️",
    "confused": "🌀",
    "infatuated": "💗",
    "leech_seed": "🌱",
    "taunt": "😤",
    "encore": "🎵",
    "disable": "🚫",
    "substitute": "🎭",
    "flash_fire": "🔥",
}

STATUS_BONUS_CATCH = {
    "sleep": 2.5,
    "freeze": 2.5,
    "paralysis": 1.5,
    "burn": 1.5,
    "poison": 1.5,
    "badly_poison": 1.5,
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

WEATHER_DAMAGE_MULT: dict[str, dict[str, float]] = {
    "sunny":     {"fire": 1.5, "water": 0.5},
    "rain":      {"water": 1.5, "fire": 0.5},
    "sandstorm": {},
    "snow":      {"ice": 1.5},
    "fog":       {},
    "none":      {},
}

WEATHER_ACCURACY_MULT: dict[str, dict[str, float]] = {
    "sunny":     {},
    "rain":      {"thunder": 1.0, "hurricane": 1.0},
    "sandstorm": {},
    "snow":      {"blizzard": 1.0},
    "fog":       {},
    "none":      {},
}

WEATHER_TICK_DAMAGE: dict[str, dict] = {
    "sandstorm": {"immune_types": ["rock", "ground", "steel"], "fraction": 16},
    "snow":      {"immune_types": ["ice"], "fraction": 16},
}

WEATHER_MOVES: dict[str, str] = {
    "rain-dance":  "rain",
    "sunny-day":   "sunny",
    "sandstorm":   "sandstorm",
    "snowscape":   "snow",
    "hail":        "snow",
    "chilly-reception": "snow",
}

WEATHER_ABILITIES: dict[str, str] = {
    "drizzle":      "rain",
    "drought":      "sunny",
    "sand-stream":  "sandstorm",
    "snow-warning": "snow",
    "sand-spit":    "sandstorm",
}

WEATHER_ROCKS = {
    "damp-rock":    "rain",
    "heat-rock":    "sunny",
    "smooth-rock":  "sandstorm",
    "icy-rock":     "snow",
}

WEATHER_DURATION_DEFAULT = 5
WEATHER_DURATION_EXTENDED = 8


# ==========================================================================
#  ПРИОРИТЕТЫ АТАК
# ==========================================================================
MOVE_PRIORITY: dict[str, int] = {
    "helping-hand": 5,
    "detect": 4,
    "protect": 4,
    "spiky-shield": 4,
    "baneful-bunker": 4,
    "kings-shield": 4,
    "obstruct": 4,
    "endure": 4,
    "wide-guard": 4,
    "quick-guard": 4,
    "magic-coat": 4,
    "snatch": 4,
    "follow-me": 3,
    "rage-powder": 3,
    "crafty-shield": 3,
    "fake-out": 2,
    "extreme-speed": 2,
    "feint": 2,
    "accelerock": 1,
    "aqua-jet": 1,
    "bullet-punch": 1,
    "ice-shard": 1,
    "jet-punch": 1,
    "mach-punch": 1,
    "quick-attack": 1,
    "shadow-sneak": 1,
    "sucker-punch": 1,
    "vacuum-wave": 1,
    "water-shuriken": 1,
    "avalanche": -4,
    "beak-blast": -3,
    "counter": -5,
    "dragon-tail": -6,
    "focus-punch": -3,
    "mirror-coat": -5,
    "roar": -6,
    "shell-trap": -3,
    "whirlwind": -6,
    "circle-throw": -6,
    "vital-throw": -1,
    "trick-room": -7,
}


def get_move_priority(raw_name: str) -> int:
    low = raw_name.lower().replace(" ", "-").strip()
    return MOVE_PRIORITY.get(low, 0)


# ==========================================================================
#  СТАТУСНЫЕ АТАКИ
# ==========================================================================
STATUS_MOVES: dict[str, dict] = {
    # -------------------- Наложение статусов --------------------
    "will-o-wisp":   {"category": "inflict", "target": "opponent", "status": "burn",      "accuracy": 85},
    "toxic":         {"category": "inflict", "target": "opponent", "status": "badly_poison", "accuracy": 90},
    "poison-powder": {"category": "inflict", "target": "opponent", "status": "poison",    "accuracy": 75},
    "thunder-wave":  {"category": "inflict", "target": "opponent", "status": "paralysis", "accuracy": 90},
    "glare":         {"category": "inflict", "target": "opponent", "status": "paralysis", "accuracy": 100},
    "stun-spore":    {"category": "inflict", "target": "opponent", "status": "paralysis", "accuracy": 75},
    "sleep-powder":  {"category": "inflict", "target": "opponent", "status": "sleep",     "accuracy": 75},
    "spore":         {"category": "inflict", "target": "opponent", "status": "sleep",     "accuracy": 100},
    "hypnosis":      {"category": "inflict", "target": "opponent", "status": "sleep",     "accuracy": 60},
    "sing":          {"category": "inflict", "target": "opponent", "status": "sleep",     "accuracy": 55},
    "confuse-ray":   {"category": "inflict", "target": "opponent", "status": "confused",  "accuracy": 100},
    "supersonic":    {"category": "inflict", "target": "opponent", "status": "confused",  "accuracy": 55},
    "sweet-kiss":    {"category": "inflict", "target": "opponent", "status": "confused",  "accuracy": 75},
    "teeter-dance":  {"category": "inflict", "target": "opponent", "status": "confused",  "accuracy": 100},
    "attract":       {"category": "inflict", "target": "opponent", "status": "infatuated","accuracy": 100},

    # -------------------- Волатильные статусы --------------------
    "substitute":    {"category": "substitute", "target": "self",     "fraction": 4,   "accuracy": None},
    "leech-seed":    {"category": "leech_seed", "target": "opponent", "accuracy": 90},
    "taunt":         {"category": "taunt",      "target": "opponent", "accuracy": 100, "turns": 3},
    "encore":        {"category": "encore",     "target": "opponent", "accuracy": 100, "turns": 3},
    "disable":       {"category": "disable",    "target": "opponent", "accuracy": 100, "turns": 4},

    # -------------------- Повышение статов (self) --------------------
    "swords-dance":  {"category": "boost", "target": "self", "stat": "attack",     "stages": 2, "accuracy": None},
    "dragon-dance":  {"category": "boost", "target": "self", "stat": "attack",     "stages": 1, "accuracy": None},
    "howl":          {"category": "boost", "target": "self", "stat": "attack",     "stages": 1, "accuracy": None},
    "bulk-up":       {"category": "boost", "target": "self", "stat": "attack",     "stages": 1, "accuracy": None},
    "iron-defense":  {"category": "boost", "target": "self", "stat": "defense",    "stages": 2, "accuracy": None},
    "acid-armor":    {"category": "boost", "target": "self", "stat": "defense",    "stages": 2, "accuracy": None},
    "withdraw":      {"category": "boost", "target": "self", "stat": "defense",    "stages": 1, "accuracy": None},
    "harden":        {"category": "boost", "target": "self", "stat": "defense",    "stages": 1, "accuracy": None},
    "nasty-plot":    {"category": "boost", "target": "self", "stat": "sp_attack",  "stages": 2, "accuracy": None},
    "calm-mind":     {"category": "boost", "target": "self", "stat": "sp_attack",  "stages": 1, "accuracy": None},
    "growth":        {"category": "boost", "target": "self", "stat": "attack",     "stages": 1, "accuracy": None},
    "amnesia":       {"category": "boost", "target": "self", "stat": "sp_defense", "stages": 2, "accuracy": None},
    "agility":       {"category": "boost", "target": "self", "stat": "speed",      "stages": 2, "accuracy": None},
    "rock-polish":   {"category": "boost", "target": "self", "stat": "speed",      "stages": 2, "accuracy": None},
    "double-team":   {"category": "boost", "target": "self", "stat": "evasion",    "stages": 1, "accuracy": None},
    "minimize":      {"category": "boost", "target": "self", "stat": "evasion",    "stages": 2, "accuracy": None},

    # -------------------- Понижение статов (opponent) --------------------
    "growl":         {"category": "debuff", "target": "opponent", "stat": "attack",     "stages": -1, "accuracy": 100},
    "leer":          {"category": "debuff", "target": "opponent", "stat": "defense",    "stages": -1, "accuracy": 100},
    "tail-whip":     {"category": "debuff", "target": "opponent", "stat": "defense",    "stages": -1, "accuracy": 100},
    "screech":       {"category": "debuff", "target": "opponent", "stat": "defense",    "stages": -2, "accuracy": 85},
    "scary-face":    {"category": "debuff", "target": "opponent", "stat": "speed",      "stages": -2, "accuracy": 100},
    "cotton-spore":  {"category": "debuff", "target": "opponent", "stat": "speed",      "stages": -2, "accuracy": 100},
    "charm":         {"category": "debuff", "target": "opponent", "stat": "attack",     "stages": -2, "accuracy": 100},
    "string-shot":   {"category": "debuff", "target": "opponent", "stat": "speed",      "stages": -2, "accuracy": 95},
    "flash":         {"category": "debuff", "target": "opponent", "stat": "accuracy",   "stages": -1, "accuracy": 100},
    "sand-attack":   {"category": "debuff", "target": "opponent", "stat": "accuracy",   "stages": -1, "accuracy": 100},
    "smokescreen":   {"category": "debuff", "target": "opponent", "stat": "accuracy",   "stages": -1, "accuracy": 100},
    "metal-sound":   {"category": "debuff", "target": "opponent", "stat": "sp_defense", "stages": -2, "accuracy": 85},
    "fake-tears":    {"category": "debuff", "target": "opponent", "stat": "sp_defense", "stages": -2, "accuracy": 100},

    # -------------------- Лечение --------------------
    "recover":       {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "soft-boiled":   {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "roost":         {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "slack-off":     {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "synthesis":     {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "moonlight":     {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "morning-sun":   {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "rest":          {"category": "heal", "target": "self", "fraction": 1,   "accuracy": None,
                      "self_status": "sleep", "sleep_turns": 2},
    "wish":          {"category": "heal", "target": "self", "fraction": 2,   "accuracy": None},
    "heal-bell":     {"category": "heal", "target": "self", "cure_team": True, "accuracy": None},
    "aromatherapy":  {"category": "heal", "target": "self", "cure_team": True, "accuracy": None},
}


def is_status_move(raw_name: str) -> bool:
    return raw_name.lower().replace(" ", "-").strip() in STATUS_MOVES


def get_status_move(raw_name: str) -> dict | None:
    return STATUS_MOVES.get(raw_name.lower().replace(" ", "-").strip())


# ==========================================================================
#  PIVOT / BATON PASS
# ==========================================================================
BATON_PASS_MOVES: set[str] = {"baton-pass"}

PIVOT_MOVES: set[str] = {
    "u-turn", "volt-switch", "flip-turn",
    "parting-shot", "teleport",
}


def is_baton_pass(raw_name: str) -> bool:
    return raw_name.lower().replace(" ", "-").strip() in BATON_PASS_MOVES


def is_pivot_move(raw_name: str) -> bool:
    return raw_name.lower().replace(" ", "-").strip() in PIVOT_MOVES


# ==========================================================================
#  КРИТИЧЕСКИЕ АТАКИ
# ==========================================================================
HIGH_CRIT_MOVES: set[str] = {
    "slash", "night-slash", "cross-chop", "stone-edge", "leaf-blade",
    "psycho-cut", "shadow-claw", "razor-wind", "crabhammer", "karate-chop",
    "razor-leaf", "sky-attack", "air-cutter", "attack-order", "blaze-kick",
    "cross-poison", "drill-run", "spacial-rend", "snipe-shot", "aeroblast",
    "sacred-fire", "origin-pulse", "precipice-blades", "dragon-claw",
    "poison-tail", "shadow-blast", "wicked-blow", "mighty-cleave",
}


def get_crit_stage(raw_name: str, extra: int = 0) -> int:
    stage = extra
    if raw_name.lower().replace(" ", "-").strip() in HIGH_CRIT_MOVES:
        stage += 1
    return max(0, min(4, stage))


CRIT_CHANCES: dict[int, float] = {
    0: 1 / 24,
    1: 1 / 8,
    2: 1 / 2,
    3: 1.0,
    4: 1.0,
}


# ==========================================================================
#  СПОСОБНОСТИ: ИММУНИТЕТЫ К ТИПАМ
# ==========================================================================
ABILITY_TYPE_IMMUNITY: dict[str, tuple[str, str]] = {
    "levitate":        ("ground", "immune"),
    "volt-absorb":     ("electric", "heal"),
    "water-absorb":    ("water", "heal"),
    "dry-skin":        ("water", "heal"),
    "earth-eater":     ("ground", "heal"),
    "flash-fire":      ("fire", "boost"),
    "sap-sipper":      ("grass", "boost"),
    "lightning-rod":   ("electric", "boost"),
    "storm-drain":     ("water", "boost"),
    "motor-drive":     ("electric", "boost"),
    "well-baked-body": ("fire", "boost"),
    "wind-rider":      ("flying", "boost"),
    "thermal-exchange": ("fire", "boost"),
}

ABILITY_IMMUNITY_BOOST: dict[str, str] = {
    "flash-fire":      "sp_attack",
    "sap-sipper":      "attack",
    "lightning-rod":   "sp_attack",
    "storm-drain":     "sp_attack",
    "motor-drive":     "speed",
    "well-baked-body": "defense",
    "wind-rider":      "attack",
    "thermal-exchange": "attack",
}

ABILITY_PERSISTING_BOOST: dict[str, str] = {
    "flash-fire": "flash_fire",
}


# ==========================================================================
#  СПОСОБНОСТИ: МОДИФИКАТОРЫ УРОНА
# ==========================================================================
ABILITY_ATTACK_MULT: dict[str, float] = {
    "huge-power": 2.0,
    "pure-power": 2.0,
    "guts":       1.5,
    "hustle":     1.5,
    "toxic-boost": 1.5,
    "flare-boost": 1.5,
}

ABILITY_DEFENSE_MULT: dict[str, float] = {
    "marvel-scale": 1.5,
    "grass-pelt":   1.5,
    "fur-coat":     2.0,
}

ABILITY_DAMAGE_TAKEN_MULT: dict[str, dict[str, float]] = {
    "thick-fat":   {"fire": 0.5, "ice": 0.5},
    "heatproof":   {"fire": 0.5},
    "water-bubble": {"fire": 0.5},
    "purifying-salt": {"ghost": 0.5},
    "fluffy":      {"fire": 2.0},
    "ice-scales":  {"special": 0.5},
}

ABILITY_OUTGOING_MULT: dict[str, float] = {
    "adaptability": 1.0,
    "tinted-lens":  2.0,
    "filter":       0.75,
    "solid-rock":   0.75,
    "prism-armor":  0.75,
    "technician":   1.5,
    "sheer-force":  1.3,
}


# ==========================================================================
#  СПОСОБНОСТИ: ОСОБЫЕ ЭФФЕКТЫ
# ==========================================================================
STURDY_ABILITIES = {"sturdy"}
HALVE_AT_FULL_HP = {"multiscale", "shadow-shield"}
INDIRECT_DAMAGE_IMMUNE = {"magic-guard"}
WEATHER_IMMUNE = {"overcoat", "sand-veil", "sand-rush", "snow-cloak", "ice-body"}

END_OF_TURN_ABILITIES: dict[str, dict] = {
    "rain-dish":    {"weather": "rain",  "fraction": 16},
    "ice-body":     {"weather": "snow",  "fraction": 16},
    "dry-skin":     {"weather": "rain",  "fraction": 8, "hurt_sunny": True},
    "solar-power":  {"hurt_weather": "sunny", "fraction": 8, "boost": "sp_attack"},
}

END_TURN_BOOST_ABILITIES: dict[str, str] = {
    "speed-boost": "speed",
    "moody": "random",
}

SWITCH_HEAL_ABILITIES: dict[str, float] = {
    "regenerator": 1 / 3,
}

SWITCH_CURE_ABILITIES = {"natural-cure"}

WONDER_GUARD = "wonder-guard"


# ==========================================================================
#  ХЕЛПЕРЫ ДЛЯ СПОСОБНОСТЕЙ
# ==========================================================================
def get_type_immunity(ability: str) -> tuple[str, str] | None:
    return ABILITY_TYPE_IMMUNITY.get((ability or "").lower())


def get_attack_mult(ability: str, has_status: bool, status: str) -> float:
    ab = (ability or "").lower()
    if ab not in ABILITY_ATTACK_MULT:
        return 1.0
    if ab == "guts" and not has_status:
        return 1.0
    if ab == "toxic-boost" and status != "badly_poison":
        return 1.0
    if ab == "flare-boost" and status != "burn":
        return 1.0
    return ABILITY_ATTACK_MULT[ab]


def get_defense_mult(ability: str, has_status: bool) -> float:
    ab = (ability or "").lower()
    if ab not in ABILITY_DEFENSE_MULT:
        return 1.0
    if ab == "marvel-scale" and not has_status:
        return 1.0
    return ABILITY_DEFENSE_MULT[ab]


def get_damage_taken_mult(ability: str, move_type: str, damage_class: str) -> float:
    ab = (ability or "").lower()
    row = ABILITY_DAMAGE_TAKEN_MULT.get(ab)
    if not row:
        return 1.0
    if move_type in row:
        return row[move_type]
    if damage_class in row:
        return row[damage_class]
    return 1.0


# ==========================================================================
#  РУЧНОЙ СЛОВАРЬ РУССКИХ ИМЁН АТАК (фан-перевод → PokéAPI slug)
# ==========================================================================
MOVE_NAMES_RU: dict[str, str] = {
    # --- базовые нормальные ---
    "царапина": "scratch",
    "захват": "tackle",
    "удар": "pound",
    "хвост-хлыст": "tail-whip",
    "рычание": "growl",
    "быстрая атака": "quick-attack",
    "стремительная атака": "quick-attack",
    "пощёчина": "double-slap",
    "двойная атака": "double-hit",
    "слэм": "slam",
    "раздавить": "slam",
    "тело-броском": "body-slam",
    "бодислэм": "body-slam",
    "гипер-луч": "hyper-beam",
    "сверхлуч": "hyper-beam",
    "взрыв": "explosion",
    "самоуничтожение": "self-destruct",
    "сдача": "submission",
    "удар-сверху": "skull-bash",
    "обманка": "feint",
    "приманка": "swagger",
    "самоуверенность": "swagger",
    "хвастовство": "swagger",
    "мудрость": "calm-mind",
    "концентрация": "calm-mind",
    "скорлупа-броня": "iron-defense",

    # --- огонь ---
    "огонёк": "ember",
    "искра-огня": "ember",
    "огненный-шар": "fire-blast",
    "огненный вихрь": "fire-spin",
    "пламя": "flamethrower",
    "огнемёт": "flamethrower",
    "огнемет": "flamethrower",
    "солнечный луч": "solar-beam",
    "солнечный-удар": "sunny-day",
    "вихрь-огня": "fire-spin",
    "инферно": "inferno",
    "огненный-клык": "fire-fang",
    "укус-огня": "fire-fang",

    # --- вода ---
    "водный пистолет": "water-gun",
    "водяной-пистолет": "water-gun",
    "гидро-насос": "hydro-pump",
    "гидронасос": "hydro-pump",
    "прибой": "surf",
    "сёрф": "surf",
    "водопад": "waterfall",
    "аква-джет": "aqua-jet",
    "водные-лезвия": "razor-shell",
    "водяной-шар": "water-pulse",
    "водный-импульс": "water-pulse",
    "пузырь": "bubble",
    "пузыри": "bubble-beam",
    "пузырьковый луч": "bubble-beam",

    # --- электричество ---
    "разряд": "thunder-shock",
    "удар-током": "thunder-shock",
    "громовая-волна": "thunder-wave",
    "электрошок": "thunder-shock",
    "гром": "thunder",
    "молния": "thunderbolt",
    "громовой-удар": "thunder-punch",
    "громовой-клык": "thunder-fang",
    "электро-шар": "electro-ball",
    "вольт-переключение": "volt-switch",
    "вольт-свитч": "volt-switch",

    # --- трава ---
    "поглощение": "absorb",
    "мега-поглощение": "mega-drain",
    "гига-поглощение": "giga-drain",
    "лист-лезвие": "leaf-blade",
    "лезвие-листа": "leaf-blade",
    "листовой-шторм": "leaf-storm",
    "семена-лечения": "leech-seed",
    "высасывание": "leech-seed",
    "усыпляющий-порошок": "sleep-powder",
    "спор": "spore",
    "яд-порошок": "poison-powder",
    "лунный свет": "moonlight",
    "синтез": "synthesis",
    "солнечный свет": "synthesis",

    # --- лёд ---
    "ледяной-удар": "ice-punch",
    "лёд-луч": "ice-beam",
    "ледяной-луч": "ice-beam",
    "метель": "blizzard",
    "вьюга": "blizzard",
    "лёд-клык": "ice-fang",
    "ледяной-клык": "ice-fang",
    "лёд-осколок": "ice-shard",
    "снег": "snowscape",

    # --- боевой ---
    "удар-кулаком": "karate-chop",
    "каратэ-чоп": "karate-chop",
    "низкий-пинок": "low-kick",
    "ближний-бой": "close-combat",
    "высокий-пинок": "high-jump-kick",
    "мега-удар": "mega-punch",
    "динамический-удар": "dynamic-punch",
    "сверх-удар": "superpower",

    # --- яд ---
    "кислота": "acid",
    "кислотный-распылитель": "acid-spray",
    "токсичный": "toxic",
    "яд": "poison-sting",
    "укус-яда": "poison-fang",
    "грязный-удар": "sludge",

    # --- земля ---
    "землетрясение": "earthquake",
    "удар-земли": "earth-power",
    "магнитуда": "magnitude",
    "грязевой-выстрел": "mud-shot",
    "грязь-бомба": "mud-bomb",

    # --- летающие ---
    "воздушный ас": "aerial-ace",
    "воздушный-ас": "aerial-ace",
    "крыло-атака": "wing-attack",
    "клюв-атака": "peck",
    "полёт": "fly",
    "ураган": "hurricane",
    "вихрь-ветра": "gust",
    "порыв-ветра": "gust",
    "воздушный-резец": "air-cutter",

    # --- психические ---
    "психический": "psychic",
    "пси-луч": "psybeam",
    "психический удар": "psycho-cut",
    "гипноз": "hypnosis",
    "медитация": "meditate",
    "ясновидение": "future-sight",
    "замешательство": "confusion",
    "конфузия": "confusion",
    "конфуз-луч": "confuse-ray",
    "лунный свет-пси": "moonblast",

    # --- жук ---
    "укус-жука": "bug-bite",
    "жало-атака": "pin-missile",
    "кси-удар": "x-scissor",
    "первый-удар": "first-impression",
    "лёгкое-жало": "fury-cutter",

    # --- камень ---
    "каменный-удар": "rock-throw",
    "каменная-бомба": "rock-blast",
    "камнепад": "rock-slide",
    "обвал": "rock-slide",
    "каменное-лезвие": "stone-edge",
    "мощный-камень": "power-gem",
    "старый-камень": "ancient-power",

    # --- призрак ---
    "теневой-шар": "shadow-ball",
    "тень-удар": "shadow-punch",
    "тень-когти": "shadow-claw",
    "пожиратель-душ": "soul-eater",
    "проклятие": "curse",
    "ликс": "lick",
    "облизывание": "lick",

    # --- дракон ---
    "дракон-ярость": "dragon-rage",
    "драконий-клык": "dragon-claw",
    "драконий-когти": "dragon-claw",
    "драконий-пульс": "dragon-pulse",
    "дракон-вздох": "dragon-breath",
    "драконий-танец": "dragon-dance",
    "дракон-метеор": "draco-meteor",
    "дракон-нырок": "dragon-dive",
    "драконий-шар": "dragon-pulse",

    # --- тёмный ---
    "тёмный-удар": "dark-pulse",
    "тёмный-импульс": "dark-pulse",
    "кусание": "bite",
    "укус-тьмы": "crunch",
    "хруст": "crunch",
    "преследование": "pursuit",
    "обман": "feint-attack",
    "подлый-удар": "sucker-punch",

    # --- сталь ---
    "металлические когти": "metal-claw",
    "металлический коготь": "metal-claw",
    "железная голова": "iron-head",
    "железный натиск": "iron-head",
    "железная броня": "iron-defense",
    "железная защита": "iron-defense",
    "металлический шум": "metal-sound",
    "пушечный-шар": "flash-cannon",
    "вспышка-пушки": "flash-cannon",
    "железный-хвост": "iron-tail",
    "стальной-крыло": "steel-wing",

    # --- фея ---
    "очарование": "charm",
    "детский-голосок": "disarming-voice",
    "лунная-пушка": "moonblast",
    "фея-ветер": "fairy-wind",
    "милый-поцелуй": "sweet-kiss",
    "обезоруживающий голос": "disarming-voice",
    "магический огонь": "magical-flame",

    # --- статусные / вспомогательные ---
    "меч-танец": "swords-dance",
    "танец-мечей": "swords-dance",
    "двойная-команда": "double-team",
    "раздвоение": "double-team",
    "ускорение": "agility",
    "ловкость": "agility",
    "укрепление": "harden",
    "защита": "defense-curl",
    "спокойствие": "calm-mind",
    "медитация-ума": "calm-mind",
    "отдых": "rest",
    "восстановление": "recover",
    "лечение": "recover",
    "заживление": "heal-bell",
    "колокол-лечения": "heal-bell",
    "защитный-барьер": "protect",
    "защита-барьер": "protect",
    "отражение": "reflect",
    "световой-экран": "light-screen",
    "попутный-ветер": "tailwind",
    "обманка-экрана": "substitute",
    "заменитель": "substitute",
    "насмешка": "taunt",
    "приказ-повтор": "encore",
    "запрет": "disable",
    "фокус-внимание": "focus-energy",
    "двойная-защита": "double-team",
    "увеличение-силы": "swords-dance",
    "каменная-броня": "iron-defense",
}


def resolve_move_ru(name: str) -> str | None:
    """Ищет английский slug для русского имени атаки. None если не найден."""
    if not name:
        return None
    key = name.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    for cand in (key, key.replace(" ", "-")):
        v = MOVE_NAMES_RU.get(cand)
        if v:
            return v
    return None
