"""Рандомные фразы для боевых сообщений."""
import random


# ===== Атака =====
ATTACK_TEMPLATES = [
    "{who} использует **{move}**!",
    "{who} применяет **{move}**!",
    "{who} атакует **{move}**!",
    "{who} вызывает **{move}**!",
    "{who} применяет приём **{move}**!",
]

HIT_TEMPLATES = [
    "{target} получает **{dmg}** урона!",
    "{target} отлетает, теряя **{dmg}** HP!",
    "{target} вздрагивает — **{dmg}** урона.",
    "Удар в цель! **{target}** теряет **{dmg}** HP.",
    "{target} держится, но получает **{dmg}** урона.",
]

MISS_TEMPLATES = [
    "{target} ловко уворачивается — промах!",
    "{target} уходит в сторону — мимо!",
    "Атака проходит мимо — {target} успел!",
    "{target} уклоняется — промах!",
]

IMMUNE_TEMPLATES = [
    "Атака не действует на {target}…",
    "Никакого эффекта — {target} невосприимчив.",
    "{target} даже не заметил атаки.",
]

CRIT_LINES = [
    "💥 **Критический удар!**",
    "💥 **Критический удар!**",
    "💥 Попадание в слабое место!",
]

# ===== Защита =====
PROTECT_LINES = [
    "{who} окружает себя защитным барьером!",
    "{who} успевает выставить Protect!",
    "Вспышка света — {who} под Protect!",
]

REFLECT_LINES = [
    "На стороне {who} появляется Рефлект!",
    "{who} создаёт физический барьер — Reflect.",
]

LIGHT_SCREEN_LINES = [
    "На стороне {who} вспыхивает Light Screen!",
    "{who} выставляет магический барьер — Light Screen.",
]

TAILWIND_LINES = [
    "{who} ловит попутный ветер — Tailwind!",
    "{who} ускоряет союзников — Tailwind.",
]

HAZARD_LINES = {
    "spikes": [
        "{who} разбрасывает **Спайки** по полю соперника!",
        "{who} усеивает поле шипами!",
    ],
    "toxic_spikes": [
        "{who} разбрасывает **Токсичные шипы**!",
        "{who} отравляет поле шипами!",
    ],
    "stealth_rock": [
        "{who} вызывает **Камни** — Stealth Rock!",
        "{who} усеивает поле осколками камней!",
    ],
    "sticky_web": [
        "{who} плетёт **Липкую паутину**!",
        "{who} замедляет соперника — Sticky Web.",
    ],
}

# ===== Погода =====
WEATHER_LINES = {
    "sunny": [
        "☀️ **Солнце** заливает поле!",
        "☀️ Лучи солнца усиливают огонь!",
    ],
    "rain": [
        "🌧️ **Дождь** начинается!",
        "🌧️ Ливень хлещет по арене!",
    ],
    "sandstorm": [
        "🏜️ **Песчаная буря** поднимается!",
        "🏜️ Песок застилает всё вокруг!",
    ],
    "snow": [
        "❄️ **Снег** пошёл!",
        "❄️ Поле покрывается инеем!",
    ],
    "fog": [
        "🌫️ **Туман** опускается на арену!",
    ],
}

WEATHER_END_LINES = [
    "Погода вернулась в норму.",
    "Небо снова ясное.",
    "Погодный эффект закончился.",
]

WEATHER_TICK_LINES = {
    "sandstorm": [
        "🏜️ **{name}** страдает от песчаной бури (−{dmg} HP).",
        "🏜️ Песок хлещет **{name}** (−{dmg} HP).",
    ],
    "snow": [
        "❄️ **{name}** мёрзнет (−{dmg} HP).",
        "❄️ Снег отнимает силы у **{name}** (−{dmg} HP).",
    ],
}

WEATHER_HEAL_LINES = {
    "snow": [
        "❄️ **{name}** восстанавливает HP благодаря Ice Body (+{hp}).",
    ],
    "rain": [
        "🌧️ **{name}** восстанавливает HP благодаря Rain Dish (+{hp}).",
    ],
}

# ===== Смена покемона =====
SWITCH_LINES = [
    "{who} отзывает покемона и выпускает **{next_mon}**!",
    "{who} меняет тактику — выходит **{next_mon}**!",
    "Возврат! {who} выпускает **{next_mon}**.",
]

FAINT_LINES = [
    "**{name}** теряет сознание!",
    "**{name}** падает без сил!",
    "**{name}** больше не может сражаться!",
]

# ===== Статусы =====
STATUS_INFLICT = {
    "burn": [
        "**{name}** получает ожог!",
        "**{name}** обожжён!",
    ],
    "poison": [
        "**{name}** отравлен!",
        "Яд растекается по телу **{name}**!",
    ],
    "badly_poison": [
        "**{name}** сильно отравлен! Яд будет усиливаться…",
        "**{name}** поражён смертельным ядом!",
    ],
    "paralysis": [
        "**{name}** парализован!",
        "Тело **{name}** свело!",
    ],
    "sleep": [
        "**{name}** засыпает…",
        "**{name}** погружается в сон…",
    ],
    "freeze": [
        "**{name}** замерзает!",
        "**{name}** покрывается льдом!",
    ],
    "confused": [
        "**{name}** в замешательстве!",
        "**{name}** сбит с толку!",
    ],
    "infatuated": [
        "**{name}** влюблён!",
        "**{name}** потерял голову от любви!",
    ],
}

STATUS_TICK = {
    "burn": "**{name}** страдает от ожога: −{dmg} HP.",
    "poison": "**{name}** теряет HP от яда: −{dmg}.",
    "badly_poison": "**{name}** мучается от сильного яда: −{dmg}.",
}

PARALYSIS_SKIP = [
    "**{name}** не может двигаться — паралич!",
    "**{name}** дёргается, но не может атаковать!",
]

SLEEP_SKIP = [
    "**{name}** крепко спит.",
    "**{name}** продолжает спать.",
]

FROZEN_SKIP = [
    "**{name}** вмерзла в лёд.",
    "**{name}** не может двигаться — заморожен!",
]

WAKE_UP = [
    "**{name}** просыпается!",
    "**{name}** открывает глаза!",
]

THAW = [
    "Лёд трескается — **{name}** свободен!",
    "**{name}** разбивает лёд!",
]

# ===== Волатильные статусы =====

# Конфуз
CONFUSED_SELF_HIT = [
    "🌀 **{name}** бьёт себя в замешательстве (−{dmg} HP)!",
    "🌀 **{name}** атакует сам себя (−{dmg} HP)!",
    "🌀 От замешательства **{name}** наносит урон себе (−{dmg} HP)!",
]

CONFUSED_END = [
    "🌀 **{name}** приходит в себя!",
    "🌀 Замешательство **{name}** проходит.",
]

CONFUSED_ALREADY = [
    "🌀 **{name}** уже в замешательстве.",
]

# Влюблённость
INFATUATED_SKIP = [
    "💗 **{name}** не может атаковать — влюблён!",
    "💗 **{name}** колеблется и пропускает ход!",
    "💗 **{name}** слишком очарован, чтобы драться!",
]

INFATUATED_END = [
    "💗 **{name}** избавляется от чар.",
    "💗 **{name}** берёт себя в руки.",
]

INFATUATED_FAIL = [
    "💗 Эффект не сработал (пол не подходит).",
    "💗 **{name}** не поддался чарам.",
]

# ===== Leech Seed =====
LEECH_SEED_INFLICT = [
    "🌱 На **{name}** проросли семена!",
    "🌱 **{name}** обвит лианами Leech Seed!",
]

LEECH_SEED_TICK = [
    "🌱 Семена высасывают силы **{name}** (−{dmg} HP).",
    "🌱 **{name}** теряет HP от Leech Seed (−{dmg}).",
]

LEECH_SEED_ALREADY = [
    "🌱 **{name}** уже обвит семенами.",
]

# ===== Taunt / Encore / Disable =====
TAUNT_INFLICT = [
    "😤 **{name}** раздражён и не может использовать статусные атаки!",
    "😤 **{name}** под Taunt — только атакующие приёмы!",
]

TAUNT_END = [
    "😤 **{name}** успокаивается — Taunt спадает.",
]

TAUNT_ALREADY = [
    "😤 **{name}** уже под Taunt.",
]

ENCORE_INFLICT = [
    "🎵 **{name}** вынужден повторять **{move}**!",
    "🎵 **{name}** попал под Encore — повторяет **{move}**!",
]

ENCORE_END = [
    "🎵 Encore у **{name}** заканчивается.",
]

ENCORE_ALREADY = [
    "🎵 **{name}** уже под Encore.",
]

ENCORE_NO_MOVE = [
    "🎵 Но **{name}** ещё ничего не использовал…",
]

DISABLE_INFLICT = [
    "🚫 **{name}** больше не может использовать **{move}**!",
    "🚫 **{move}** заблокирован у **{name}** (Disable)!",
]

DISABLE_END = [
    "🚫 Disable у **{name}** спадает.",
]

DISABLE_ALREADY = [
    "🚫 **{name}** уже под Disable.",
]

DISABLE_NO_MOVE = [
    "🚫 Но **{name}** ещё не использовал атак…",
]

# ===== Substitute =====
SUBSTITUTE_CREATE = [
    "🎭 **{name}** создаёт заменителя (−{hp} HP)!",
    "🎭 Появляется Substitute **{name}** (−{hp} HP).",
]

SUBSTITUTE_TOO_LOW = [
    "🎭 У **{name}** слишком мало HP для Substitute.",
]

SUBSTITUTE_ALREADY = [
    "🎭 У **{name}** уже есть Substitute.",
]

SUBSTITUTE_ABSORB = [
    "🎭 Substitute **{name}** принимает удар (−{dmg} HP).",
    "🎭 Заменитель **{name}** держит удар (−{dmg} HP).",
]

SUBSTITUTE_BREAK = [
    "🎭 Substitute **{name}** разрушен!",
    "🎭 Заменитель **{name}** не выдержал!",
]

SUBSTITUTE_BLOCK = [
    "🎭 Substitute **{name}** блокирует эффект!",
]

# ===== Pivot / Baton Pass =====
BATON_PASS_LINE = [
    "🔄 **{who}** передаёт эстафету **{next_mon}** (Baton Pass)!",
    "🔄 Baton Pass! **{next_mon}** принимает все усиления!",
]

PIVOT_LINE = [
    "🔄 **{who}** наносит удар и отступает — выходит **{next_mon}**!",
    "🔄 После атаки **{who}** меняет **{next_mon}**!",
]

# ===== Способности: иммунитеты и эффекты =====
ABILITY_IMMUNITY_LINES = {
    "levitate": [
        "🌪️ Атака не достаёт — **{name}** парит в воздухе (Levitate)!",
    ],
    "volt-absorb": [
        "⚡ **{name}** поглощает электричество (Volt Absorb) и лечится!",
    ],
    "water-absorb": [
        "💧 **{name}** впитывает воду (Water Absorb) и восстанавливает HP!",
    ],
    "dry-skin": [
        "💧 **{name}** впитывает влагу (Dry Skin) и лечится!",
    ],
    "earth-eater": [
        "🌍 **{name}** съедает землю (Earth Eater) и лечится!",
    ],
    "flash-fire": [
        "🔥 **{name}** поглощает огонь (Flash Fire) — сила Fire-атак растёт!",
    ],
    "sap-sipper": [
        "🌿 **{name}** впитывает траву (Sap Sipper) — атака растёт!",
    ],
    "lightning-rod": [
        "⚡ **{name}** притягивает молнии (Lightning Rod) — спец. атака растёт!",
    ],
    "storm-drain": [
        "💧 **{name}** впитывает воду (Storm Drain) — спец. атака растёт!",
    ],
    "motor-drive": [
        "⚙️ **{name}** поглощает электричество (Motor Drive) — скорость растёт!",
    ],
    "well-baked-body": [
        "🍞 **{name}** не боится огня (Well-Baked Body) — защита растёт!",
    ],
    "wind-rider": [
        "💨 **{name}** ловит поток (Wind Rider) — атака растёт!",
    ],
    "thermal-exchange": [
        "🔥 **{name}** поглощает жар (Thermal Exchange) — атака растёт!",
    ],
    "wonder-guard": [
        "🛡️ **{name}** защищён Wonder Guard — только суперэффективные атаки!",
    ],
}

ABILITY_STURDY_LINE = [
    "💪 **{name}** держится из последних сил (Sturdy)!",
]

ABILITY_MULTISCALE_LINE = [
    "🐉 **{name}** ослабляет удар благодаря Multiscale!",
    "🛡️ Shadow Shield **{name}** смягчает удар!",
]

ABILITY_SWITCH_HEAL = [
    "💚 **{name}** восстанавливает HP при смене (Regenerator).",
]

ABILITY_SWITCH_CURE = [
    "✨ **{name}** избавляется от статуса (Natural Cure).",
]

# ===== End-of-turn способности =====
ABILITY_END_HEAL = {
    "rain-dish": [
        "🌧️ **{name}** подкрепляется влагой (Rain Dish, +{hp} HP).",
    ],
    "ice-body": [
        "❄️ **{name}** восстанавливает HP (Ice Body, +{hp} HP).",
    ],
    "dry-skin": [
        "💧 **{name}** восстанавливает HP от влаги (Dry Skin, +{hp} HP).",
    ],
}

ABILITY_END_HURT = {
    "solar-power": [
        "☀️ **{name}** страдает от солнечной энергии (Solar Power, −{dmg} HP).",
    ],
    "dry-skin": [
        "🔥 **{name}** сохнет на солнце (Dry Skin, −{dmg} HP).",
    ],
}

ABILITY_END_BOOST = {
    "speed-boost": [
        "💨 **{name}** ускоряется (Speed Boost)!",
    ],
    "moody": [
        "🎲 **{name}** непредсказуемо меняет статы (Moody)!",
    ],
}

# ===== Ожог / яд — детали =====
BURN_ATTACK_DROP = [
    "🟥 Ожог ослабляет физические атаки **{name}**!",
]

PARALYSIS_SPEED_DROP = [
    "🟨 Паралич снизил скорость **{name}**!",
]

# ===== Предметы (X-предметы, ягоды, Choice и т.д.) =====
ITEM_ACTIVATED = [
    "🎒 **{name}** активирует **{item}**!",
    "🎒 Предмет **{name}** срабатывает: **{item}**!",
]


def pick(templates: list[str]) -> str:
    return random.choice(templates)
