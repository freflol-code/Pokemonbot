"""
Редкости покемонов.

Используется в cogs/catch.py:
    from pokemon_rarity import (
        COMMON,
        RARITY_CATCH_MULTIPLIER,
        RARITY_EMOJI,
        RARITY_LABEL,
        get_rarity,
    )
"""
from __future__ import annotations


# ==========================================================================
#  Уровни редкости
# ==========================================================================
COMMON     = "common"
UNCOMMON   = "uncommon"
RARE       = "rare"
VERY_RARE  = "very_rare"
LEGENDARY  = "legendary"
MYTHICAL   = "mythical"

ALL_RARITIES = (COMMON, UNCOMMON, RARE, VERY_RARE, LEGENDARY, MYTHICAL)


# ==========================================================================
#  Человекочитаемые названия (RU)
# ==========================================================================
RARITY_LABEL: dict[str, str] = {
    COMMON:    "Обычный",
    UNCOMMON:  "Необычный",
    RARE:      "Редкий",
    VERY_RARE: "Очень редкий",
    LEGENDARY: "Легендарный",
    MYTHICAL:  "Мифический",
}


# ==========================================================================
#  Эмодзи для эмбедов
# ==========================================================================
RARITY_EMOJI: dict[str, str] = {
    COMMON:    "⚪",
    UNCOMMON:  "🟢",
    RARE:      "🔵",
    VERY_RARE: "🟣",
    LEGENDARY: "🌟",
    MYTHICAL:  "✨",
}


# ==========================================================================
#  Множители шанса поимки.
#  Больше = легче поймать. Умножается на базовый шанс покебола.
# ==========================================================================
RARITY_CATCH_MULTIPLIER: dict[str, float] = {
    COMMON:    1.00,
    UNCOMMON:  0.85,
    RARE:      0.65,
    VERY_RARE: 0.45,
    LEGENDARY: 0.15,
    MYTHICAL:  0.05,
}


# ==========================================================================
#  Явные списки ID (national dex)
# ==========================================================================
LEGENDARY_IDS: set[int] = {
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
    785, 786, 787, 788, 789, 790, 791, 792,
    793, 794, 795, 796, 797, 798, 799, 800,
    # Gen 8
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898, 905,
    # Gen 9
    1007, 1008, 1009, 1010, 1014, 1015, 1016, 1017, 1024,
}

MYTHICAL_IDS: set[int] = {
    151,        # Mew
    251,        # Celebi
    385, 386,   # Jirachi, Deoxys
    489, 490, 491, 492, 493,  # Phione..Arceus
    494,        # Victini
    647, 648, 649,  # Keldeo, Meloetta, Genesect
    719, 720, 721,  # Diancie, Hoopa, Volcanion
    801, 802,       # Magearna, Marshadow
    807, 808, 809,  # Zeraora, Meltan, Melmetal
    893,        # Zarude
    1025,       # Pecharunt
}

# Псевдо-легендарные и просто очень редкие
VERY_RARE_IDS: set[int] = {
    # Драконьи линии
    147, 148, 149,   # Dratini -> Dragonite
    246, 247, 248,   # Larvitar -> Tyranitar
    371, 372, 373,   # Bagon -> Salamence
    374, 375, 376,   # Beldum -> Metagross
    443, 444, 445,   # Gible -> Garchomp
    633, 634, 635,   # Deino -> Hydreigon
    704, 705, 706,   # Goomy -> Goodra
    782, 783, 784,   # Jangmo-o -> Kommo-o
    885, 886, 887,   # Dreepy -> Dragapult
    996, 997, 998,   # Frigibax -> Baxcalibur
    # Одиночки
    131,  # Lapras
    142,  # Aerodactyl
    143,  # Snorlax
    133, 134, 135, 136, 196, 197, 470, 471, 700,  # Eevee и eeveelutions
    447, 448,  # Riolu, Lucario
    479,       # Rotom
    570, 571,  # Zorua, Zoroark
    # Ископаемые
    138, 139, 140, 141,
    345, 346, 347, 348,
    408, 409, 410, 411,
    564, 565, 566, 567,
}


# ==========================================================================
#  Основная функция
# ==========================================================================
def get_rarity(species_id: int) -> str:
    """
    Определить редкость покемона по national dex ID.

    Легендарные / мифические / явно редкие определяются по спискам,
    остальные — детерминированным хешем (одна и та же особь всегда
    получает одну и ту же редкость).
    """
    if not species_id:
        return COMMON

    sid = int(species_id)

    if sid in MYTHICAL_IDS:
        return MYTHICAL
    if sid in LEGENDARY_IDS:
        return LEGENDARY
    if sid in VERY_RARE_IDS:
        return VERY_RARE

    # Стабильный псевдослучайный выбор по ID
    h = (sid * 2654435761) & 0xFFFFFFFF
    r = h % 100
    if r < 60:
        return COMMON
    if r < 85:
        return UNCOMMON
    if r < 97:
        return RARE
    return VERY_RARE
