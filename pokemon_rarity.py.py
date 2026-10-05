"""Группы редкости покемонов и модификаторы шанса поимки.

Группы:
    • common          — обычные
    • pseudo_legendary — псевдолегендарные (сильные финальные эволюции)
    • legendary       — легендарные
    • mythical        — мифические

Каждая группа имеет собственный множитель к базовому шансу покебола.
«Гарантированные» шары (Master Ball, Cherish, Park, GS, Origin) поимку
не скейлят — они ловят всех одинаково.
"""
from __future__ import annotations

# ==========================================================================
#  ИДЕНТИФИКАТОРЫ ГРУПП
# ==========================================================================
COMMON            = "common"
PSEUDO_LEGENDARY  = "pseudo_legendary"
LEGENDARY         = "legendary"
MYTHICAL          = "mythical"

RARITY_ORDER = (COMMON, PSEUDO_LEGENDARY, LEGENDARY, MYTHICAL)

RARITY_LABEL: dict[str, str] = {
    COMMON:           "Обычный",
    PSEUDO_LEGENDARY: "Псевдолегендарный",
    LEGENDARY:        "Легендарный",
    MYTHICAL:         "Мифический",
}

RARITY_EMOJI: dict[str, str] = {
    COMMON:           "🟢",
    PSEUDO_LEGENDARY: "🟣",
    LEGENDARY:        "🟡",
    MYTHICAL:         "🔴",
}

# ==========================================================================
#  МНОЖИТЕЛИ ШАНСА ПОИМКИ
#  Применяются к базовому шансу покебола (см. cogs/catch.py).
# ==========================================================================
RARITY_CATCH_MULTIPLIER: dict[str, float] = {
    COMMON:           1.00,   # базовый шанс как есть
    PSEUDO_LEGENDARY: 0.35,   # в ~3 раза сложнее
    LEGENDARY:        0.10,   # в 10 раз сложнее
    MYTHICAL:         0.03,   # в ~33 раза сложнее
}

# Веса спавна (на будущее — если захотите учесть редкость в /spawn)
RARITY_SPAWN_WEIGHT: dict[str, float] = {
    COMMON:           100.0,
    PSEUDO_LEGENDARY: 3.0,
    LEGENDARY:        0.5,
    MYTHICAL:         0.1,
}

# ==========================================================================
#  НАБОРЫ ID ВИДОВ
# ==========================================================================

# Псевдолегендарные — финальные формы «сильных» линий (BST ~600)
PSEUDO_LEGENDARY_IDS: frozenset[int] = frozenset({
    149,   # Dragonite
    248,   # Tyranitar
    373,   # Salamence
    376,   # Metagross
    445,   # Garchomp
    635,   # Hydreigon
    706,   # Goodra
    784,   # Kommo-o
    887,   # Dragapult
    998,   # Baxcalibur
})

# Мифические (получаются только по событиям)
MYTHICAL_IDS: frozenset[int] = frozenset({
    151,   # Mew
    251,   # Celebi
    385,   # Jirachi
    386,   # Deoxys
    489,   # Phione
    490,   # Manaphy
    491,   # Darkrai
    492,   # Shaymin
    493,   # Arceus
    494,   # Victini
    647,   # Keldeo
    648,   # Meloetta
    649,   # Genesect
    719,   # Diancie
    720,   # Hoopa
    721,   # Volcanion
    801,   # Magearna
    802,   # Marshadow
    807,   # Zeraora
    808,   # Meltan
    809,   # Melmetal
    893,   # Zarude
    1025,  # Pecharunt
})

# Легендарные
LEGENDARY_IDS: frozenset[int] = frozenset({
    # Gen 1
    144, 145, 146, 150,
    # Gen 2
    243, 244, 245, 249, 250,
    # Gen 3
    377, 378, 379, 380, 381, 382, 383, 384,
    # Gen 4
    480, 481, 482, 483, 484, 485, 486, 487, 488,
    # Gen 5
    638, 639, 640, 641, 642, 643, 644, 645, 646,
    # Gen 6
    716, 717, 718,
    # Gen 7
    772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 800,
    # Gen 8
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898, 905,
    # Gen 9 (Paldea + DLC)
    1001, 1002, 1003, 1004,        # Treasures of Ruin
    1007, 1008,                    # Koraidon, Miraidon
    1009, 1010,                    # Walking Wake, Iron Leaves
    1014, 1015, 1016, 1017,        # Loyal Three + Ogerpon
    1020, 1021, 1022, 1023,        # Paradox forms
    1024,                          # Terapagos
})

# ==========================================================================
#  ПУБЛИЧНОЕ API
# ==========================================================================

def get_rarity(species_id: int) -> str:
    """Возвращает идентификатор группы редкости для вида."""
    if species_id in MYTHICAL_IDS:
        return MYTHICAL
    if species_id in LEGENDARY_IDS:
        return LEGENDARY
    if species_id in PSEUDO_LEGENDARY_IDS:
        return PSEUDO_LEGENDARY
    return COMMON


def get_catch_multiplier(species_id: int) -> float:
    """Множитель шанса поимки для конкретного вида."""
    return RARITY_CATCH_MULTIPLIER[get_rarity(species_id)]


def get_rarity_label(species_id: int) -> str:
    """Строка вида '🟡 Легендарный' — удобно вставлять в эмбеды."""
    rarity = get_rarity(species_id)
    return f"{RARITY_EMOJI[rarity]} {RARITY_LABEL[rarity]}"


def is_special(species_id: int) -> bool:
    """True для легендарных и мифических — их обычно не спавнят обычным путём."""
    return get_rarity(species_id) in (LEGENDARY, MYTHICAL)