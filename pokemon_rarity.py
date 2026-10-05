"""Группы редкости покемонов и модификаторы шанса поимки."""
from __future__ import annotations

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

RARITY_CATCH_MULTIPLIER: dict[str, float] = {
    COMMON:           1.00,
    PSEUDO_LEGENDARY: 0.35,
    LEGENDARY:        0.10,
    MYTHICAL:         0.03,
}

PSEUDO_LEGENDARY_IDS: frozenset[int] = frozenset({
    149, 248, 373, 376, 445, 635, 706, 784, 887, 998,
})

MYTHICAL_IDS: frozenset[int] = frozenset({
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808,
    809, 893, 1025,
})

LEGENDARY_IDS: frozenset[int] = frozenset({
    144, 145, 146, 150,
    243, 244, 245, 249, 250,
    377, 378, 379, 380, 381, 382, 383, 384,
    480, 481, 482, 483, 484, 485, 486, 487, 488,
    638, 639, 640, 641, 642, 643, 644, 645, 646,
    716, 717, 718,
    772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 800,
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898, 905,
    1001, 1002, 1003, 1004,
    1007, 1008, 1009, 1010,
    1014, 1015, 1016, 1017,
    1020, 1021, 1022, 1023,
    1024,
})

_IDS_BY_RARITY: dict[str, frozenset[int]] = {
    PSEUDO_LEGENDARY: PSEUDO_LEGENDARY_IDS,
    LEGENDARY:        LEGENDARY_IDS,
    MYTHICAL:         MYTHICAL_IDS,
}


def get_rarity(species_id: int) -> str:
    if species_id in MYTHICAL_IDS:
        return MYTHICAL
    if species_id in LEGENDARY_IDS:
        return LEGENDARY
    if species_id in PSEUDO_LEGENDARY_IDS:
        return PSEUDO_LEGENDARY
    return COMMON


def get_catch_multiplier(species_id: int) -> float:
    return RARITY_CATCH_MULTIPLIER[get_rarity(species_id)]


def get_ids_for_rarity(rarity: str) -> list[int]:
    """Список видов в указанной группе. Для COMMON — пустой (собирается отдельно)."""
    return sorted(_IDS_BY_RARITY.get(rarity, set()))
