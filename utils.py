"""Общие вспомогательные функции для форматирования."""
import asyncio
from typing import Any, Iterable

import discord

import pokeapi_client

EMBED_COLOR = discord.Color.from_rgb(230, 57, 70)

GENDER_EMOJI: dict[str, str] = {
    "male": "♂️",
    "female": "♀️",
    "genderless": "⚪",
}

TYPE_RU: dict[str, str] = {
    "normal": "Нормальный", "fire": "Огонь", "water": "Вода",
    "electric": "Электрический", "grass": "Трава", "ice": "Лёд",
    "fighting": "Боевой", "poison": "Яд", "ground": "Земля",
    "flying": "Летающий", "psychic": "Психический", "bug": "Жук",
    "rock": "Камень", "ghost": "Призрак", "dragon": "Дракон",
    "dark": "Тьма", "steel": "Сталь", "fairy": "Фея",
}


async def load_species(
    items: Iterable[dict[str, Any] | int],
) -> dict[int, dict[str, Any]]:
    """Параллельно загружает данные видов; недоступные виды пропускаются."""
    ids: set[int] = set()
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            sid = item.get("species_id")
            if isinstance(sid, int):
                ids.add(sid)
        else:
            try:
                ids.add(int(item))
            except (TypeError, ValueError):
                continue

    if not ids:
        return {}

    results = await asyncio.gather(
        *(pokeapi_client.get_pokemon(i) for i in ids), return_exceptions=True
    )
    return {
        i: r
        for i, r in zip(ids, results)
        if isinstance(r, dict)
    }


def species_name(species: dict[int, dict[str, Any]], species_id: int) -> str:
    data = species.get(species_id)
    return data["name"] if data else f"Покемон #{species_id}"


def format_gender(gender: str | None) -> str:
    if not gender:
        return ""
    return GENDER_EMOJI.get(str(gender), "")


def format_ability(ability_en: str | None) -> str:
    """Красивое отображение способности (без перевода — перевод асинхронный).

    'flash-fire' → 'Flash Fire'. Если способности нет — '—'.
    """
    if not ability_en:
        return "—"
    return str(ability_en).replace("-", " ").title()


async def load_abilities_ru(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Асинхронно подтягивает русские названия для всех уникальных способностей.

    Возвращает {английское_имя: русское_имя}.
    """
    names: set[str] = set()
    for mon in items:
        ab = mon.get("ability") if isinstance(mon, dict) else None
        if ab:
            names.add(ab)

    if not names:
        return {}

    results = await asyncio.gather(
        *(pokeapi_client.get_ability_ru(n) for n in names),
        return_exceptions=True,
    )
    out: dict[str, str] = {}
    for name, ru in zip(names, results):
        out[name] = ru if isinstance(ru, str) else name
    return out


def mon_title(mon: dict[str, Any], species: dict[int, dict[str, Any]]) -> str:
    """Заголовок для покемона: 'Кличка (Вид) ♂' или 'Вид ♀'."""
    sname = species_name(species, mon.get("species_id", 0))
    nick = mon.get("nickname")
    title = f"{nick} ({sname})" if nick else sname
    emoji = format_gender(mon.get("gender"))
    return f"{title} {emoji}".strip()


def format_moves(moves: Iterable[str] | None) -> str:
    if not moves:
        return "—"
    cleaned = [m for m in moves if m]
    if not cleaned:
        return "—"
    return ", ".join(m.replace("-", " ").title() for m in cleaned)


def format_types(types: Iterable[str] | None) -> str:
    if not types:
        return "—"
    return " / ".join(TYPE_RU.get(t, str(t).title()) for t in types if t)
