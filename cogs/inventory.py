"""Инвентарь и магазин, привязанный к каналу."""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from database import add_item, get_item_qty, get_trainer, spend_pokebucks
from utils import EMBED_COLOR

# ==========================================================================
#  КАТАЛОГ ПРЕДМЕТОВ
# ==========================================================================
ITEMS: dict[str, dict[str, object]] = {
    # ---- Базовые расходники ----
    "pokeball":       {"name": "Покебол",                    "price": 50},
    "greatball":      {"name": "Грейтбол",                   "price": 120},
    "ultraball":      {"name": "Ультрабол",                  "price": 250},
    "masterball":     {"name": "Мастербол",                  "price": 10000},
    "potion":         {"name": "Зелье",                      "price": 40},
    "super_potion":   {"name": "Супер-зелье",                "price": 100},
    "hyper_potion":   {"name": "Гипер-зелье",                "price": 250},
    "max_potion":     {"name": "Макс-зелье",                 "price": 500},
    "revive":         {"name": "Оживитель",                  "price": 300},
    "max_revive":     {"name": "Макс-оживитель",             "price": 1000},
    "antidote":       {"name": "Антидот",                    "price": 60},
    "full_heal":      {"name": "Полное лечение",             "price": 600},
    "max_honey":      {"name": "Макс-мёд",                   "price": 2500},

    # ---- Зелья и восстановление (для Вердена) ----
    "fresh_water":    {"name": "Свежая вода",                "price": 200},
    "soda_pop":       {"name": "Газировка",                  "price": 300},
    "lemonade":       {"name": "Лимонад",                    "price": 350},
    "moomoo_milk":    {"name": "Молоко Му-Му",               "price": 500},
    "full_restore":   {"name": "Полное восстановление",      "price": 3000},

    # ---- Травы ----
    "energy_powder":  {"name": "Энергопорошок",              "price": 500},
    "energy_root":    {"name": "Энергокорень",               "price": 800},
    "heal_powder":    {"name": "Целебный порошок",           "price": 450},
    "revival_herb":   {"name": "Трава возрождения",          "price": 2800},
    "white_herb":     {"name": "Белая трава",                "price": 3000},
    "mental_herb":    {"name": "Ментальная трава",           "price": 3000},
    "power_herb":     {"name": "Трава силы",                 "price": 4000},

    # ---- Специализированные покеболы ----
    "net_ball":       {"name": "Нетбол",                     "price": 150},
    "dive_ball":      {"name": "Дайвбол",                    "price": 180},
    "nest_ball":      {"name": "Нестбол",                    "price": 120},
    "repeat_ball":    {"name": "Репитбол",                   "price": 200},
    "timer_ball":     {"name": "Таймербол",                  "price": 250},
    "heal_ball":      {"name": "Хилбол",                     "price": 300},
    "luxury_ball":    {"name": "Люксбол",                    "price": 350},
    "quick_ball":     {"name": "Квикбол",                    "price": 400},
    "dusk_ball":      {"name": "Дускбол",                    "price": 180},

    # ---- Новые покеболы (событийные / редкие) ----
    "premier_ball":   {"name": "Премьер-болл",               "price": 100},
    "cherish_ball":   {"name": "Чериш-болл",                 "price": 0},
    "park_ball":      {"name": "Парк-болл",                  "price": 0},
    "sport_ball":     {"name": "Спорт-болл",                 "price": 300},
    "origin_ball":    {"name": "Ориджин-болл",               "price": 0},
    "gs_ball":        {"name": "GS-болл",                    "price": 0},
    "strange_ball":   {"name": "Стрэндж-болл",               "price": 0},
    "dream_ball":     {"name": "Дрим-болл",                  "price": 500},
    "beast_ball":     {"name": "Бист-болл",                  "price": 5000},

    # ---- Апокорновые (Johto) ----
    "level_ball":     {"name": "Левел-болл",                 "price": 250},
    "lure_ball":      {"name": "Люр-болл",                   "price": 250},
    "moon_ball":      {"name": "Мун-болл",                   "price": 250},
    "friend_ball":    {"name": "Френд-болл",                 "price": 200},
    "love_ball":      {"name": "Лав-болл",                   "price": 200},
    "heavy_ball":     {"name": "Хэви-болл",                  "price": 300},
    "fast_ball":      {"name": "Фаст-болл",                  "price": 250},

    # ---- Legends: Arceus ----
    "feather_ball":   {"name": "Фезер-болл",                 "price": 150},
    "wing_ball":      {"name": "Винг-болл",                  "price": 180},
    "jet_ball":       {"name": "Джет-болл",                  "price": 200},
    "leaden_ball":    {"name": "Леден-болл",                 "price": 250},
    "gigaton_ball":   {"name": "Гигатон-болл",               "price": 500},

    # ---- Исследовательские (прокачка) ----
    "protein":        {"name": "Протеин",                    "price": 5000},
    "iron":           {"name": "Железо",                     "price": 5000},
    "calcium":        {"name": "Кальций",                    "price": 5000},
    "zinc":           {"name": "Цинк",                       "price": 5000},
    "carbos":         {"name": "Карбос",                     "price": 5000},
    "hp_up":          {"name": "HP Up",                      "price": 5000},
    "rare_candy":     {"name": "Редкая конфета",             "price": 8000},

    # ---- Камни эволюции ----
    "fire_stone":     {"name": "Огненный камень",            "price": 3000},
    "water_stone":    {"name": "Водный камень",              "price": 3000},
    "thunder_stone":  {"name": "Грозовой камень",            "price": 3000},
    "leaf_stone":     {"name": "Листовой камень",            "price": 3000},
    "moon_stone":     {"name": "Лунный камень",              "price": 5000},
    "sun_stone":      {"name": "Солнечный камень",           "price": 5000},
    "shiny_stone":    {"name": "Блестящий камень",           "price": 6000},
    "dusk_stone":     {"name": "Камень сумрака",             "price": 6000},
    "dawn_stone":     {"name": "Камень рассвета",            "price": 6000},
    "ice_stone":      {"name": "Ледяной камень",             "price": 5000},

    # ---- Мега-камни ----
    "mega_stone_aggron":      {"name": "Мега-камень Аггрона",       "price": 25000},
    "mega_stone_gengar":      {"name": "Мега-камень Генгара",       "price": 30000},
    "mega_stone_lucario":     {"name": "Мега-камень Лукарио",       "price": 35000},
    "mega_stone_garchomp":    {"name": "Мега-камень Гарчомпа",      "price": 40000},
    "mega_stone_metagross":   {"name": "Мега-камень Метагросса",    "price": 45000},
    "mega_stone_salamence":   {"name": "Мега-камень Саламенса",     "price": 45000},
    "mega_stone_dragonite":   {"name": "Мега-камень Драгонита",     "price": 50000},
    "mega_stone_charizard_x": {"name": "Мега-камень Чаризарда X",   "price": 40000},
    "mega_stone_charizard_y": {"name": "Мега-камень Чаризарда Y",   "price": 40000},

    # ---- Z-кольцо и Z-кристаллы ----
    "z_ring":             {"name": "Z-кольцо",                   "price": 5000},
    "z_crystal_normal":   {"name": "Z-кристалл: Обычный",        "price": 15000},
    "z_crystal_fire":     {"name": "Z-кристалл: Огонь",          "price": 18000},
    "z_crystal_water":    {"name": "Z-кристалл: Вода",           "price": 18000},
    "z_crystal_electric": {"name": "Z-кристалл: Электро",        "price": 18000},
    "z_crystal_grass":    {"name": "Z-кристалл: Трава",          "price": 18000},
    "z_crystal_ice":      {"name": "Z-кристалл: Лёд",            "price": 18000},
    "z_crystal_fighting": {"name": "Z-кристалл: Боевой",         "price": 18000},
    "z_crystal_poison":   {"name": "Z-кристалл: Яд",             "price": 18000},
    "z_crystal_ground":   {"name": "Z-кристалл: Земля",          "price": 18000},
    "z_crystal_flying":   {"name": "Z-кристалл: Летающий",       "price": 18000},
    "z_crystal_bug":      {"name": "Z-кристалл: Жук",            "price": 18000},
    "z_crystal_rock":     {"name": "Z-кристалл: Камень",         "price": 18000},
    "z_crystal_steel":    {"name": "Z-кристалл: Сталь",          "price": 22000},
    "z_crystal_dark":     {"name": "Z-кристалл: Тьма",           "price": 22000},
    "z_crystal_fairy":    {"name": "Z-кристалл: Фея",            "price": 22000},
    "z_crystal_dragon":   {"name": "Z-кристалл: Дракон",         "price": 25000},
    "z_crystal_ghost":    {"name": "Z-кристалл: Призрак",        "price": 25000},
    "z_crystal_psychic":  {"name": "Z-кристалл: Психика",        "price": 25000},

    # ---- Динамакс ----
    "dynamax_band":       {"name": "Динамакс-браслет",           "price": 100000},

    # ---- Усиления (X-предметы) ----
    "x_attack":       {"name": "X Атака",                    "price": 500},
    "x_defense":      {"name": "X Защита",                   "price": 500},
    "x_sp_atk":       {"name": "X Спец. Атака",              "price": 500},
    "x_sp_def":       {"name": "X Спец. Защита",             "price": 500},
    "x_speed":        {"name": "X Скорость",                 "price": 500},
    "x_accuracy":     {"name": "X Точность",                 "price": 500},
    "dire_hit":       {"name": "Dire Hit",                   "price": 700},
    "guard_spec":     {"name": "Guard Spec",                 "price": 700},

    # ---- Ягоды ----
    "liechi_berry":   {"name": "Ягода Личи",                 "price": 3000},
    "ganlon_berry":   {"name": "Ягода Ганлон",               "price": 3000},
    "salac_berry":    {"name": "Ягода Салак",                "price": 3000},
    "petaya_berry":   {"name": "Ягода Петая",                "price": 3000},
    "apicot_berry":   {"name": "Ягода Апикот",               "price": 3000},
    "lansat_berry":   {"name": "Ягода Лансат",               "price": 4000},
    "sitrus_berry":   {"name": "Ягода Ситрус",               "price": 800},
    "lum_berry":      {"name": "Ягода Лум",                  "price": 1200},

    # ---- Held items ----
    "choice_band":    {"name": "Choice Band",                "price": 8000},
    "choice_specs":   {"name": "Choice Specs",               "price": 8000},
    "choice_scarf":   {"name": "Choice Scarf",               "price": 8000},
    "life_orb":       {"name": "Life Orb",                   "price": 10000},
    "focus_sash":     {"name": "Focus Sash",                 "price": 9000},
    "leftovers":      {"name": "Leftovers",                  "price": 7000},
    "assault_vest":   {"name": "Assault Vest",               "price": 9000},
    "expert_belt":    {"name": "Expert Belt",                "price": 8000},
    "rocky_helmet":   {"name": "Rocky Helmet",               "price": 7500},

    # ---- Хибики: транспорт и скорость ----
    "bicycle":        {"name": "Велосипед",                  "price": 15000},
    "acro_bike":      {"name": "Акро-велосипед",             "price": 25000},
    "mach_bike":      {"name": "Мах-велосипед",              "price": 25000},
    "running_shoes":  {"name": "Беговые кроссовки",          "price": 5000},
    "quick_claw":     {"name": "Quick Claw",                 "price": 6000},
    "quick_powder":   {"name": "Quick Powder",               "price": 5000},

    # ---- Люмьер: аксессуары ----
    "ribbon_pink":     {"name": "Розовая лента",             "price": 800},
    "ribbon_blue":     {"name": "Синяя лента",               "price": 800},
    "ribbon_gold":     {"name": "Золотая лента",             "price": 2500},
    "bow_silk":        {"name": "Шёлковый бант",             "price": 1200},
    "bow_lace":        {"name": "Кружевной бант",            "price": 1800},
    "scarf_silk":      {"name": "Шёлковый шарф",             "price": 1500},
    "scarf_warm":      {"name": "Тёплый шарф",               "price": 1500},
    "necklace_pearl":  {"name": "Жемчужное ожерелье",        "price": 3000},
    "necklace_star":   {"name": "Ожерелье-звезда",           "price": 3500},
    "hat_top":         {"name": "Цилиндр",                   "price": 2500},
    "hat_beret":       {"name": "Берет",                     "price": 1200},
    "glasses_sun":     {"name": "Солнечные очки",            "price": 1000},
    "glasses_monocle": {"name": "Монокль",                   "price": 2800},
    "crown_flower":    {"name": "Венок из цветов",           "price": 1500},
    "crown_tiara":     {"name": "Тиара",                     "price": 4000},
    "cape_silk":       {"name": "Шёлковая накидка",          "price": 5000},
    "pendant_moon":    {"name": "Кулон-луна",                "price": 2200},
    "pendant_sun":     {"name": "Кулон-солнце",              "price": 2200},

    # ---- Рейгард: испытательные предметы ----
    "weakness_policy":  {"name": "Weakness Policy",          "price": 9000},
    "protective_pads":  {"name": "Protective Pads",          "price": 8000},
    "loaded_dice":      {"name": "Loaded Dice",              "price": 7500},
    "covert_cloak":     {"name": "Covert Cloak",             "price": 8500},
    "clear_amulet":     {"name": "Clear Amulet",             "price": 8000},
    "booster_energy":   {"name": "Booster Energy",           "price": 12000},

    # ---- Рейгард: подстройка покемонов ----
    "ability_capsule":  {"name": "Ability Capsule",          "price": 15000},
    "ability_patch":    {"name": "Ability Patch",            "price": 40000},
    "bottle_cap":       {"name": "Bottle Cap",               "price": 20000},
    "gold_bottle_cap":  {"name": "Gold Bottle Cap",          "price": 60000},

    # ---- Рейгард: мятные листья ----
    "mint_adamant":     {"name": "Мятный лист: Адамант",     "price": 10000},
    "mint_jolly":       {"name": "Мятный лист: Джолли",      "price": 10000},
    "mint_modest":      {"name": "Мятный лист: Модест",      "price": 10000},
    "mint_timid":       {"name": "Мятный лист: Тимид",       "price": 10000},
    "mint_bold":        {"name": "Мятный лист: Болд",        "price": 10000},
    "mint_calm":        {"name": "Мятный лист: Калм",        "price": 10000},
    "mint_impish":      {"name": "Мятный лист: Импиш",       "price": 10000},
    "mint_careful":     {"name": "Мятный лист: Кэафул",      "price": 10000},

    # ---- Эйдолон: эксклюзивы Лиги ----
    "league_badge":         {"name": "Значок Лиги",          "price": 25000},
    "champion_cape":        {"name": "Плащ чемпиона",        "price": 75000},
    "hall_of_fame_ticket":  {"name": "Билет в Зал славы",    "price": 150000},
    "elite_pass":           {"name": "Пропуск элиты",        "price": 100000},
}

# ==========================================================================
#  ЛОКАЦИИ
# ==========================================================================
LOCATION_NAMES: dict[str, str] = {
    "hoshinori": "✨ Хошинори",
    "lastoris":  "🌊 Ласторис",
    "verden":    "🌿 Верден",
    "kaiseki":   "🔥 Кайсэки",
    "nordkron":  "❄️ Нордкрон",
    "aurelis":   "⚡ Аурелис",
    "hibiki":    "🎐 Хибики",
    "kurokane":  "⚙️ Курокане",
    "lumier":    "💫 Люмьер",
    "estera":    "🔮 Эстера",
    "reigard":   "🐉 Рейгард",
    "eidolon":   "👻 Эйдолон",
    "asteris":   "🏛️ Астэрис",
}

# ==========================================================================
#  АССОРТИМЕНТ ПО ЛОКАЦИЯМ
# ==========================================================================
DEFAULT_STOCK: list[str] = [
    "pokeball", "greatball",
    "potion", "super_potion", "revive",
]

# Полный ассортимент — с новыми покеболами
FULL_BALLS: list[str] = [
    "pokeball", "greatball", "ultraball",
    "net_ball", "dive_ball", "nest_ball", "repeat_ball",
    "timer_ball", "heal_ball", "luxury_ball", "quick_ball", "dusk_ball",
    "premier_ball", "sport_ball", "level_ball", "lure_ball",
    "moon_ball", "friend_ball", "love_ball", "heavy_ball", "fast_ball",
    "dream_ball", "beast_ball",
    "feather_ball", "wing_ball", "jet_ball", "leaden_ball", "gigaton_ball",
]

# Расширенный набор — с событийными (только для Эйдолона)
LEGENDARY_BALLS: list[str] = FULL_BALLS + [
    "cherish_ball", "park_ball", "origin_ball", "gs_ball", "strange_ball",
]

ASTERIS_STOCK: list[str] = [
    # Расходники
    "pokeball", "greatball", "ultraball",
    "potion", "super_potion", "hyper_potion", "max_potion",
    "revive", "max_revive", "antidote", "full_heal", "max_honey",
    # Камни эволюции
    "fire_stone", "water_stone", "thunder_stone", "leaf_stone",
    "moon_stone", "sun_stone", "shiny_stone", "dusk_stone",
    "dawn_stone", "ice_stone",
    # Мега-камни
    "mega_stone_aggron", "mega_stone_gengar", "mega_stone_lucario",
    "mega_stone_garchomp", "mega_stone_metagross", "mega_stone_salamence",
    "mega_stone_dragonite", "mega_stone_charizard_x", "mega_stone_charizard_y",
    # Z-кольцо и кристаллы
    "z_ring",
    "z_crystal_normal", "z_crystal_fire", "z_crystal_water",
    "z_crystal_electric", "z_crystal_grass", "z_crystal_ice",
    "z_crystal_fighting", "z_crystal_poison", "z_crystal_ground",
    "z_crystal_flying", "z_crystal_bug", "z_crystal_rock",
    "z_crystal_steel", "z_crystal_dark", "z_crystal_fairy",
    "z_crystal_dragon", "z_crystal_ghost", "z_crystal_psychic",
    # Динамакс
    "dynamax_band",
    # Полный набор покеболов
    *FULL_BALLS,
]

STOCK_BY_LOCATION: dict[str, list[str]] = {
    "asteris": ASTERIS_STOCK,

    "verden": [
        "pokeball", "greatball", "potion", "super_potion", "revive",
        "fresh_water", "soda_pop", "lemonade", "moomoo_milk", "full_restore",
        "energy_powder", "energy_root", "heal_powder", "revival_herb",
        "white_herb", "mental_herb", "power_herb",
        "net_ball", "dive_ball", "nest_ball", "repeat_ball",
        "timer_ball", "heal_ball", "luxury_ball", "quick_ball",
        # Апокорновые для «Луга»
        "friend_ball", "love_ball", "moon_ball",
        "protein", "iron", "calcium", "zinc", "carbos", "hp_up", "rare_candy",
    ],

    "kaiseki": [
        "pokeball", "greatball",
        "potion", "super_potion", "hyper_potion", "max_potion",
        "revive", "max_revive", "full_heal",
        "x_attack", "x_defense", "x_sp_atk", "x_sp_def",
        "x_speed", "x_accuracy", "dire_hit", "guard_spec",
        "sitrus_berry", "lum_berry",
        "liechi_berry", "ganlon_berry", "salac_berry",
        "petaya_berry", "apicot_berry", "lansat_berry",
        "choice_band", "choice_specs", "choice_scarf",
        "life_orb", "focus_sash", "leftovers",
        "assault_vest", "expert_belt", "rocky_helmet",
    ],

    "aurelis": [
        "pokeball", "greatball", "ultraball",
        "potion", "super_potion", "hyper_potion", "max_potion",
        "revive", "max_revive", "antidote", "full_heal", "max_honey",
        "fresh_water", "soda_pop", "lemonade", "moomoo_milk", "full_restore",
        "energy_powder", "energy_root", "heal_powder", "revival_herb",
        "white_herb", "mental_herb", "power_herb",
        "protein", "iron", "calcium", "zinc", "carbos", "hp_up", "rare_candy",
        "fire_stone", "water_stone", "thunder_stone", "leaf_stone",
        "moon_stone", "sun_stone", "shiny_stone", "dusk_stone",
        "dawn_stone", "ice_stone",
        "mega_stone_aggron", "mega_stone_gengar", "mega_stone_lucario",
        "mega_stone_garchomp", "mega_stone_metagross", "mega_stone_salamence",
        "mega_stone_dragonite", "mega_stone_charizard_x", "mega_stone_charizard_y",
        "z_ring",
        "z_crystal_normal", "z_crystal_fire", "z_crystal_water",
        "z_crystal_electric", "z_crystal_grass", "z_crystal_ice",
        "z_crystal_fighting", "z_crystal_poison", "z_crystal_ground",
        "z_crystal_flying", "z_crystal_bug", "z_crystal_rock",
        "z_crystal_steel", "z_crystal_dark", "z_crystal_fairy",
        "z_crystal_dragon", "z_crystal_ghost", "z_crystal_psychic",
        "dynamax_band",
        "x_attack", "x_defense", "x_sp_atk", "x_sp_def",
        "x_speed", "x_accuracy", "dire_hit", "guard_spec",
        "sitrus_berry", "lum_berry",
        "liechi_berry", "ganlon_berry", "salac_berry",
        "petaya_berry", "apicot_berry", "lansat_berry",
        "choice_band", "choice_specs", "choice_scarf",
        "life_orb", "focus_sash", "leftovers",
        "assault_vest", "expert_belt", "rocky_helmet",
        # Полный набор покеболов
        *FULL_BALLS,
    ],

    "hibiki": [
        "pokeball", "greatball", "ultraball", "quick_ball",
        "potion", "super_potion", "hyper_potion", "max_potion",
        "revive", "max_revive", "antidote", "full_heal", "max_honey",
        "fresh_water", "soda_pop", "lemonade", "moomoo_milk", "full_restore",
        "energy_powder", "energy_root", "heal_powder", "revival_herb",
        "white_herb", "mental_herb", "power_herb",
        "net_ball", "dive_ball", "nest_ball", "repeat_ball",
        "timer_ball", "heal_ball", "luxury_ball",
        # Апокорновые под скорость
        "fast_ball", "level_ball",
        "protein", "iron", "calcium", "zinc", "carbos", "hp_up", "rare_candy",
        "fire_stone", "water_stone", "thunder_stone", "leaf_stone",
        "moon_stone", "sun_stone", "shiny_stone", "dusk_stone",
        "dawn_stone", "ice_stone",
        "mega_stone_aggron", "mega_stone_gengar", "mega_stone_lucario",
        "mega_stone_garchomp", "mega_stone_metagross", "mega_stone_salamence",
        "mega_stone_dragonite", "mega_stone_charizard_x", "mega_stone_charizard_y",
        "z_ring",
        "z_crystal_normal", "z_crystal_fire", "z_crystal_water",
        "z_crystal_electric", "z_crystal_grass", "z_crystal_ice",
        "z_crystal_fighting", "z_crystal_poison", "z_crystal_ground",
        "z_crystal_flying", "z_crystal_bug", "z_crystal_rock",
        "z_crystal_steel", "z_crystal_dark", "z_crystal_fairy",
        "z_crystal_dragon", "z_crystal_ghost", "z_crystal_psychic",
        "dynamax_band",
        "x_attack", "x_defense", "x_sp_atk", "x_sp_def",
        "x_speed", "x_accuracy", "dire_hit", "guard_spec",
        "sitrus_berry", "lum_berry",
        "liechi_berry", "ganlon_berry", "salac_berry",
        "petaya_berry", "apicot_berry", "lansat_berry",
        "choice_band", "choice_specs", "choice_scarf",
        "life_orb", "focus_sash", "leftovers",
        "assault_vest", "expert_belt", "rocky_helmet",
        "bicycle", "acro_bike", "mach_bike", "running_shoes",
        "quick_claw", "quick_powder",
    ],

    "kurokane": [
        "pokeball", "greatball", "ultraball",
        "net_ball", "dive_ball", "nest_ball", "repeat_ball",
        "timer_ball", "heal_ball", "luxury_ball", "quick_ball",
        "premier_ball", "sport_ball", "level_ball", "lure_ball",
        "moon_ball", "friend_ball", "love_ball", "heavy_ball", "fast_ball",
        "potion", "super_potion", "revive",
    ],

    "lumier": [
        "pokeball", "greatball", "potion", "super_potion", "revive",
        "ribbon_pink", "ribbon_blue", "ribbon_gold",
        "bow_silk", "bow_lace",
        "scarf_silk", "scarf_warm",
        "necklace_pearl", "necklace_star",
        "hat_top", "hat_beret",
        "glasses_sun", "glasses_monocle",
        "crown_flower", "crown_tiara",
        "cape_silk",
        "pendant_moon", "pendant_sun",
    ],

    "reigard": [
        "pokeball", "greatball", "ultraball",
        "net_ball", "dive_ball", "nest_ball", "repeat_ball",
        "timer_ball", "heal_ball", "luxury_ball", "quick_ball",
        "potion", "super_potion", "hyper_potion", "max_potion",
        "revive", "max_revive", "antidote", "full_heal", "max_honey",
        "fresh_water", "soda_pop", "lemonade", "moomoo_milk", "full_restore",
        "energy_powder", "energy_root", "heal_powder", "revival_herb",
        "white_herb", "mental_herb", "power_herb",
        "protein", "iron", "calcium", "zinc", "carbos", "hp_up", "rare_candy",
        "fire_stone", "water_stone", "thunder_stone", "leaf_stone",
        "moon_stone", "sun_stone", "shiny_stone", "dusk_stone",
        "dawn_stone", "ice_stone",
        "mega_stone_aggron", "mega_stone_gengar", "mega_stone_lucario",
        "mega_stone_garchomp", "mega_stone_metagross", "mega_stone_salamence",
        "mega_stone_dragonite", "mega_stone_charizard_x", "mega_stone_charizard_y",
        "z_ring",
        "z_crystal_normal", "z_crystal_fire", "z_crystal_water",
        "z_crystal_electric", "z_crystal_grass", "z_crystal_ice",
        "z_crystal_fighting", "z_crystal_poison", "z_crystal_ground",
        "z_crystal_flying", "z_crystal_bug", "z_crystal_rock",
        "z_crystal_steel", "z_crystal_dark", "z_crystal_fairy",
        "z_crystal_dragon", "z_crystal_ghost", "z_crystal_psychic",
        "dynamax_band",
        "x_attack", "x_defense", "x_sp_atk", "x_sp_def",
        "x_speed", "x_accuracy", "dire_hit", "guard_spec",
        "sitrus_berry", "lum_berry",
        "liechi_berry", "ganlon_berry", "salac_berry",
        "petaya_berry", "apicot_berry", "lansat_berry",
        "choice_band", "choice_specs", "choice_scarf",
        "life_orb", "focus_sash", "leftovers",
        "assault_vest", "expert_belt", "rocky_helmet",
        "weakness_policy", "protective_pads", "loaded_dice",
        "covert_cloak", "clear_amulet", "booster_energy",
        "ability_capsule", "ability_patch",
        "bottle_cap", "gold_bottle_cap",
        "mint_adamant", "mint_jolly", "mint_modest", "mint_timid",
        "mint_bold", "mint_calm", "mint_impish", "mint_careful",
        # Полный набор покеболов
        *FULL_BALLS,
    ],

    "eidolon": [
        "pokeball", "greatball", "ultraball",
        "net_ball", "dive_ball", "nest_ball", "repeat_ball",
        "timer_ball", "heal_ball", "luxury_ball", "quick_ball",
        "potion", "super_potion", "hyper_potion", "max_potion",
        "revive", "max_revive", "antidote", "full_heal", "max_honey",
        "fresh_water", "soda_pop", "lemonade", "moomoo_milk", "full_restore",
        "energy_powder", "energy_root", "heal_powder", "revival_herb",
        "white_herb", "mental_herb", "power_herb",
        "protein", "iron", "calcium", "zinc", "carbos", "hp_up", "rare_candy",
        "fire_stone", "water_stone", "thunder_stone", "leaf_stone",
        "moon_stone", "sun_stone", "shiny_stone", "dusk_stone",
        "dawn_stone", "ice_stone",
        "mega_stone_aggron", "mega_stone_gengar", "mega_stone_lucario",
        "mega_stone_garchomp", "mega_stone_metagross", "mega_stone_salamence",
        "mega_stone_dragonite", "mega_stone_charizard_x", "mega_stone_charizard_y",
        "z_ring",
        "z_crystal_normal", "z_crystal_fire", "z_crystal_water",
        "z_crystal_electric", "z_crystal_grass", "z_crystal_ice",
        "z_crystal_fighting", "z_crystal_poison", "z_crystal_ground",
        "z_crystal_flying", "z_crystal_bug", "z_crystal_rock",
        "z_crystal_steel", "z_crystal_dark", "z_crystal_fairy",
        "z_crystal_dragon", "z_crystal_ghost", "z_crystal_psychic",
        "dynamax_band",
        "x_attack", "x_defense", "x_sp_atk", "x_sp_def",
        "x_speed", "x_accuracy", "dire_hit", "guard_spec",
        "sitrus_berry", "lum_berry",
        "liechi_berry", "ganlon_berry", "salac_berry",
        "petaya_berry", "apicot_berry", "lansat_berry",
        "choice_band", "choice_specs", "choice_scarf",
        "life_orb", "focus_sash", "leftovers",
        "assault_vest", "expert_belt", "rocky_helmet",
        "weakness_policy", "protective_pads", "loaded_dice",
        "covert_cloak", "clear_amulet", "booster_energy",
        "ability_capsule", "ability_patch",
        "bottle_cap", "gold_bottle_cap",
        "mint_adamant", "mint_jolly", "mint_modest", "mint_timid",
        "mint_bold", "mint_calm", "mint_impish", "mint_careful",
        "league_badge", "champion_cape",
        "hall_of_fame_ticket", "elite_pass",
        # Полный + событийный набор покеболов
        *LEGENDARY_BALLS,
    ],
}


def stock_for_location(loc_key: str) -> list[str]:
    """Возвращает список предметов для локации. Если нет — стандартный."""
    return STOCK_BY_LOCATION.get(loc_key, DEFAULT_STOCK)


def _load_shop_channels() -> dict[int, str]:
    """{channel_id: location_key} — из переменных SHOP_CHANNEL_<KEY>."""
    mapping: dict[int, str] = {}
    for loc_key in LOCATION_NAMES.keys():
        raw = os.getenv(f"SHOP_CHANNEL_{loc_key.upper()}", "").strip()
        if not raw:
            continue
        try:
            mapping[int(raw)] = loc_key
        except ValueError:
            continue
    return mapping


SHOP_CHANNELS: dict[int, str] = _load_shop_channels()


def _location_by_channel(channel_id: int) -> str | None:
    return SHOP_CHANNELS.get(channel_id)


async def _shop_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Показывает товары, доступные в текущем канале-магазине."""
    loc_key = _location_by_channel(interaction.channel_id or 0)
    if loc_key is None:
        return []
    keys = stock_for_location(loc_key)
    cur = current.strip().lower()
    out: list[app_commands.Choice[str]] = []
    for key in keys:
        info = ITEMS.get(key)
        if not info:
            continue
        if int(info.get("price", 0)) <= 0:
            continue  # не продаётся
        label = f"{info['name']} — {info['price']:,} PB"
        if not cur or cur in key or cur in str(info["name"]).lower():
            out.append(app_commands.Choice(name=label[:100], value=key))
        if len(out) >= 25:
            break
    return out


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="inventory", description="Показать инвентарь")
    async def inventory(self, interaction: discord.Interaction) -> None:
        t = await get_trainer(interaction.user.id)
        inv: dict[str, int] = t.get("inventory", {})
        lines = [
            f"**{ITEMS.get(key, {}).get('name', key)}** × {qty}"
            for key, qty in sorted(inv.items())
            if qty > 0
        ]
        embed = discord.Embed(
            title="🎒 Инвентарь",
            description="\n".join(lines) if lines else "Инвентарь пуст. Загляните в /shop",
            color=EMBED_COLOR,
        )
        embed.set_footer(
            text=f"{t['name']} • Баланс: {t['pokebucks']:,} Pokébucks"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="shop",
        description="Магазин (работает только в каналах магазинов)",
    )
    @app_commands.describe(item="Что купить", quantity="Сколько (1–99)")
    @app_commands.autocomplete(item=_shop_autocomplete)
    async def shop(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        loc_key = _location_by_channel(interaction.channel_id or 0)
        if loc_key is None:
            await interaction.response.send_message(
                "❌ Магазин доступен только в специальных каналах магазинов.",
                ephemeral=True,
            )
            return

        loc_name = LOCATION_NAMES.get(loc_key, loc_key)
        available = stock_for_location(loc_key)

        key = item.strip().lower()
        if key not in ITEMS:
            await interaction.response.send_message(
                "❌ Такого предмета нет в каталоге.", ephemeral=True
            )
            return

        if key not in available:
            await interaction.response.send_message(
                f"❌ **{ITEMS[key]['name']}** не продаётся в магазине "
                f"{loc_name}. Обратитесь в другой город.",
                ephemeral=True,
            )
            return

        info = ITEMS[key]
        price = int(info["price"])
        if price <= 0:
            await interaction.response.send_message(
                f"❌ **{info['name']}** нельзя купить — только получить от мастера.",
                ephemeral=True,
            )
            return

        total = price * quantity

        uid = interaction.user.id
        t_before = await get_trainer(uid)
        paid = await spend_pokebucks(uid, total)
        if not paid:
            await interaction.response.send_message(
                f"❌ Недостаточно Pokébucks: нужно **{total:,}**, "
                f"у вас **{t_before['pokebucks']:,}**.",
                ephemeral=True,
            )
            return

        await add_item(uid, key, quantity)

        t_after = await get_trainer(uid)
        qty_now = await get_item_qty(uid, key)
        embed = discord.Embed(
            title="🛒 Покупка совершена",
            description=(
                f"Магазин: {loc_name}\n"
                f"Куплено: **{info['name']}** × {quantity}\n"
                f"Потрачено: **{total:,}** PB\n"
                f"Теперь у вас: **{qty_now}** шт."
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Остаток: {t_after['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventory(bot))
