"""Асинхронный клиент PokéAPI с кэшированием и защитой от гонок."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://pokeapi.co/api/v2"
MAX_POKEMON_ID = 1025

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
_pokemon_cache: dict[int, dict[str, Any]] = {}
_gender_cache: dict[int, int] = {}
_species_index: Optional[list[tuple[int, str]]] = None
_species_index_lock = asyncio.Lock()


class PokeAPIError(Exception):
    """Ошибка при обращении к PokéAPI."""


async def _get_session() -> aiohttp.ClientSession:
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "pokebot-discord/1.0"},
            )
        return _session


async def close() -> None:
    global _session
    async with _session_lock:
        if _session is not None and not _session.closed:
            await _session.close()
        _session = None


async def _fetch_json(url: str, retries: int = 3) -> dict[str, Any]:
    session = await _get_session()
    for attempt in range(retries):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status == 404:
                    raise PokeAPIError(f"Не найдено: {url}")
                if resp.status == 429 or resp.status >= 500:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise PokeAPIError(f"PokéAPI вернул статус {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(1.0 * (attempt + 1))
    raise PokeAPIError("PokéAPI недоступен, попробуйте позже")


def _extract_species_id(raw: dict[str, Any], fallback: int) -> int:
    species_url = (raw.get("species") or {}).get("url")
    if not species_url:
        return fallback
    try:
        return int(species_url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return fallback


def _process_pokemon_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Преобразует сырой ответ PokéAPI в наш формат."""
    sprites = raw.get("sprites") or {}
    artwork = ((sprites.get("other") or {}).get("official-artwork") or {}).get(
        "front_default"
    )
    return {
        "id": raw["id"],
        "species_id": _extract_species_id(raw, raw["id"]),
        "name": raw["name"].replace("-", " ").title(),
        "raw_name": raw["name"],
        "types": [t["type"]["name"] for t in raw["types"]],
        "sprite": sprites.get("front_default") or artwork,
        "artwork": artwork or sprites.get("front_default"),
        "stats": {s["stat"]["name"]: s["base_stat"] for s in raw["stats"]},
        "moves": [m["move"]["name"] for m in raw["moves"]],
    }


async def get_pokemon(pokemon_id: int) -> dict[str, Any]:
    if pokemon_id in _pokemon_cache:
        return _pokemon_cache[pokemon_id]
    raw = await _fetch_json(f"{BASE_URL}/pokemon/{pokemon_id}")
    data = _process_pokemon_raw(raw)
    _pokemon_cache[pokemon_id] = data
    return data


async def get_pokemon_by_name(name_or_id: str) -> dict[str, Any]:
    """Ищет покемона по имени ('pikachu', 'mr-mime', '#25') или по номеру."""
    query = str(name_or_id).strip().lower().lstrip("#").replace(" ", "-")
    if not query:
        raise PokeAPIError("Пустой запрос")

    if query.isdigit():
        return await get_pokemon(int(query))

    for data in _pokemon_cache.values():
        if data.get("raw_name") == query:
            return data

    raw = await _fetch_json(f"{BASE_URL}/pokemon/{query}")
    data = _process_pokemon_raw(raw)
    _pokemon_cache[data["id"]] = data
    return data


async def get_random_pokemon() -> dict[str, Any]:
    return await get_pokemon(random.randint(1, MAX_POKEMON_ID))


async def get_species_index() -> list[tuple[int, str]]:
    """Ленивый кэш всех видов: [(id, 'pikachu'), ...] — для автодополнения."""
    global _species_index
    async with _species_index_lock:
        if _species_index is None:
            raw = await _fetch_json(f"{BASE_URL}/pokemon?limit={MAX_POKEMON_ID}")
            _species_index = [
                (int(r["url"].rstrip("/").split("/")[-1]), r["name"])
                for r in raw.get("results", [])
            ]
            log.info("Загружен индекс видов PokéAPI: %d записей", len(_species_index))
        return _species_index


async def _gender_rate(species_id: int) -> int:
    if species_id in _gender_cache:
        return _gender_cache[species_id]
    try:
        raw = await _fetch_json(f"{BASE_URL}/pokemon-species/{species_id}")
        rate = int(raw.get("gender_rate", 4))
    except PokeAPIError:
        rate = 4
    _gender_cache[species_id] = rate
    return rate


async def roll_gender(pokemon_id: int) -> str:
    data = await get_pokemon(pokemon_id)
    rate = await _gender_rate(data["species_id"])
    if rate == -1:
        return "genderless"
    return "female" if random.random() < rate / 8 else "male"


def pick_random_moves(data: dict[str, Any], count: int = 4) -> list[str]:
    moves = data.get("moves") or []
    return random.sample(moves, min(count, len(moves)))