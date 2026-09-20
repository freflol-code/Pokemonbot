"""Локации и их магазины.

Здесь только соответствие ключа локации (для .env SHOP_CHANNEL_*) 
и человеческого названия. Всё остальное не нужно.
"""
from __future__ import annotations

from typing import Any

# Куда попадает новый игрок (используется в БД по умолчанию)
START_LOCATION = "hoshinori"

# Ключ локации → отображаемое имя и эмодзи.
# Ключ в UPPERCASE используется для переменной окружения SHOP_CHANNEL_<KEY>.
LOCATIONS: dict[str, dict[str, Any]] = {
    "hoshinori": {"name": "Хошинори",  "emoji": "✨"},
    "lastoris":  {"name": "Ласторис",  "emoji": "🌊"},
    "verden":    {"name": "Верден",    "emoji": "🌿"},
    "kaiseki":   {"name": "Кайсеки",   "emoji": "🔥"},
    "nordkron":  {"name": "Нордкрон",  "emoji": "❄️"},
    "aurelis":   {"name": "Аурелис",   "emoji": "⚡"},
    "hibiki":    {"name": "Хибики",    "emoji": "🎐"},
    "kurokane":  {"name": "Курокане",  "emoji": "⚙️"},
    "lumier":    {"name": "Люмьер",    "emoji": "💫"},
    "estera":    {"name": "Эстера",    "emoji": "🔮"},
    "reigard":   {"name": "Рейгард",   "emoji": "🐉"},
    "eidolon":   {"name": "Эйдолон",   "emoji": "👻"},
}


def get_location(location_id: str | None) -> dict[str, Any]:
    if not location_id or location_id not in LOCATIONS:
        return LOCATIONS[START_LOCATION]
    return LOCATIONS[location_id]


def location_title(location_id: str | None) -> str:
    loc = get_location(location_id)
    return f"{loc['emoji']} {loc['name']}"
