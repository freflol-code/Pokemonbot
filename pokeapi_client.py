"""Асинхронный клиент PokéAPI с кэшированием, русскими именами и защитой от гонок."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import unicodedata
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://pokeapi.co/api/v2"
MAX_POKEMON_ID = 1025
NAME_INDEX_FILE = "name_index.json"

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
_pokemon_cache: dict[int, dict[str, Any]] = {}
_gender_cache: dict[int, int] = {}
_species_index: Optional[list[tuple[int, str]]] = None
_species_index_lock = asyncio.Lock()

_name_index: dict[str, int] = {}
_name_index_lock = asyncio.Lock()
_name_index_ready = False


class PokeAPIError(Exception):
    """Ошибка при обращении к PokéAPI."""


# --------------------------------------------------------------------------- #
#                          СЕССИЯ И HTTP-ЗАПРОСЫ                              #
# --------------------------------------------------------------------------- #

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


async def _fetch_json(url: str, retries: int = 3, timeout: int = 15) -> dict[str, Any]:
    session = await _get_session()
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=timeout) as resp:
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


# --------------------------------------------------------------------------- #
#                    НОРМАЛИЗАЦИЯ И ОБРАБОТКА                                 #
# --------------------------------------------------------------------------- #

def _normalize(text: str) -> str:
    if not text:
        return ""
    s = text.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = " ".join(s.split())
    return s


def _extract_species_id(raw: dict[str, Any], fallback: int) -> int:
    species_url = (raw.get("species") or {}).get("url")
    if not species_url:
        return fallback
    try:
        return int(species_url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return fallback


def _process_pokemon_raw(raw: dict[str, Any]) -> dict[str, Any]:
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


# --------------------------------------------------------------------------- #
#                             ИНДЕКС ИМЁН                                     #
# --------------------------------------------------------------------------- #

async def _build_name_index() -> dict[str, int]:
    """Скачивает все виды и собирает {имя: id} (русские + английские + номера)."""
    log.info("Генерация индекса имён покемонов (1–2 минуты)…")
    index: dict[str, int] = {}
    session = await _get_session()
    sem = asyncio.Semaphore(20)

    async def fetch_one(sid: int) -> Optional[dict[str, Any]]:
        async with sem:
            try:
                async with session.get(
                    f"{BASE_URL}/pokemon-species/{sid}",
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                pass
        return None

    tasks = [fetch_one(i) for i in range(1, MAX_POKEMON_ID + 1)]
    done = 0
    for coro in asyncio.as_completed(tasks):
        data = await coro
        done += 1
        if done % 200 == 0:
            log.info("Индекс: %d/%d", done, MAX_POKEMON_ID)
        if not data:
            continue
        sid = data.get("id")
        if not isinstance(sid, int):
            continue
        eng = data.get("name")
        if eng:
            index[_normalize(eng)] = sid
            index[str(sid)] = sid
        for n in data.get("names", []) or []:
            name = (n.get("name") or "").strip()
            if name:
                index[_normalize(name)] = sid

    try:
        with open(NAME_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        log.info("Индекс сохранён (%d записей)", len(index))
    except OSError as e:
        log.warning("Не удалось сохранить индекс: %s", e)
    return index


async def ensure_name_index() -> dict[str, int]:
    """Ленивая загрузка. Кэшируется в файл NAME_INDEX_FILE."""
    global _name_index, _name_index_ready
    async with _name_index_lock:
        if _name_index_ready:
            return _name_index
        if os.path.exists(NAME_INDEX_FILE):
            try:
                with open(NAME_INDEX_FILE, "r", encoding="utf-8") as f:
                    _name_index = json.load(f)
                _name_index_ready = True
                log.info("Индекс загружен из файла: %d записей", len(_name_index))
                return _name_index
            except (OSError, json.JSONDecodeError) as e:
                log.warning("Не удалось прочитать индекс: %s. Строю заново", e)
        _name_index = await _build_name_index()
        _name_index_ready = True
        return _name_index


# --------------------------------------------------------------------------- #
#                              ОСНОВНОЙ API                                   #
# --------------------------------------------------------------------------- #

async def get_pokemon(pokemon_id: int) -> dict[str, Any]:
    if pokemon_id in _pokemon_cache:
        return _pokemon_cache[pokemon_id]
    raw = await _fetch_json(f"{BASE_URL}/pokemon/{pokemon_id}")
    data = _process_pokemon_raw(raw)
    _pokemon_cache[pokemon_id] = data
    return data


async def get_pokemon_by_name(name_or_id: str) -> dict[str, Any]:
    """Поиск по русскому/английскому имени или номеру."""
    query_raw = str(name_or_id).strip().lstrip("#").strip()
    if not query_raw:
        raise PokeAPIError("Пустой запрос")

    if query_raw.isdigit():
        return await get_pokemon(int(query_raw))

    index = await ensure_name_index()
    sid = index.get(_normalize(query_raw))
    if sid:
        return await get_pokemon(sid)

    raw_name = query_raw.lower().replace(" ", "-")
    try:
        raw = await _fetch_json(f"{BASE_URL}/pokemon/{raw_name}")
        data = _process_pokemon_raw(raw)
        _pokemon_cache[data["id"]] = data
        return data
    except PokeAPIError:
        raise PokeAPIError(
            f"Покемон «{query_raw}» не найден. "
            f"Введите русское/английское имя или номер (#25)."
        )


async def get_random_pokemon() -> dict[str, Any]:
    return await get_pokemon(random.randint(1, MAX_POKEMON_ID))


async def get_species_index() -> list[tuple[int, str]]:
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


async def get_wild_pokemon_for_location(encounters: list[int] | None) -> dict[str, Any]:
    if encounters:
        species_id = random.choice(encounters)
    else:
        species_id = random.randint(1, MAX_POKEMON_ID)
    return await get_pokemon(species_id)
