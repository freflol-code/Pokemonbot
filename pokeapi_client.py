"""Асинхронный клиент PokéAPI с кэшированием, русскими именами и защитой от гонок."""
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
MOVE_INDEX_FILE = "move_index_ru.json"

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
_pokemon_cache: dict[int, dict[str, Any]] = {}
_gender_cache: dict[int, int] = {}
_species_index: Optional[list[tuple[int, str]]] = None
_species_index_lock = asyncio.Lock()

_name_index: dict[str, int] = {}
_name_index_lock = asyncio.Lock()
_name_index_ready = False

_ability_names_ru: dict[str, str] = {}

# --- индекс русских имён атак (RU → EN), строится из PokéAPI ---
_move_ru_to_en: dict[str, str] = {}
_move_index_lock = asyncio.Lock()
_move_index_ready = False


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
    abilities = []
    for a in raw.get("abilities", []) or []:
        abilities.append({
            "name": a["ability"]["name"],
            "is_hidden": bool(a.get("is_hidden")),
            "slot": int(a.get("slot", 1)),
        })
    abilities.sort(key=lambda x: x["slot"])

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
        "abilities": abilities,
    }


# --------------------------------------------------------------------------- #
#                             ИНДЕКС ИМЁН                                     #
# --------------------------------------------------------------------------- #

async def _build_name_index() -> dict[str, int]:
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


def pick_random_ability(data: dict[str, Any]) -> Optional[str]:
    """Возвращает английское имя одной случайной обычной способности.

    Если у покемона только скрытые способности — берётся случайная из них.
    Если нет способностей — None.
    """
    abilities = data.get("abilities") or []
    if not abilities:
        return None
    normal = [a["name"] for a in abilities if not a["is_hidden"]]
    if normal:
        return random.choice(normal)
    return random.choice([a["name"] for a in abilities])


async def get_ability_ru(ability_name: str) -> str:
    """Возвращает русское название способности. Кэширует результат."""
    key = _normalize(ability_name)
    if key in _ability_names_ru:
        return _ability_names_ru[key]

    try:
        raw = await _fetch_json(f"{BASE_URL}/ability/{ability_name}")
    except PokeAPIError:
        return ability_name

    ru_name = ability_name
    for n in raw.get("names", []) or []:
        lang = (n.get("language") or {}).get("name")
        if lang == "ru":
            ru_name = n.get("name") or ability_name
            break

    _ability_names_ru[key] = ru_name
    return ru_name


# --------------------------------------------------------------------------- #
#                      ИНДЕКС РУССКИХ ИМЁН АТАК                              #
# --------------------------------------------------------------------------- #

def _norm_move_key(name: str) -> str:
    """Нормализует имя атаки: нижний регистр, без дефисов, схлопнутые пробелы."""
    return _normalize(name).replace("-", " ").strip()


async def _build_move_index() -> dict[str, str]:
    log.info("Генерация индекса русских имён атак (30–60 сек)…")
    index: dict[str, str] = {}
    session = await _get_session()
    sem = asyncio.Semaphore(20)

    try:
        listing = await _fetch_json(f"{BASE_URL}/move?limit=1000")
    except PokeAPIError:
        return {}

    results = listing.get("results", []) or []

    async def fetch_one(url: str, name_en: str):
        async with sem:
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        m = await resp.json()
                        return name_en, m.get("names", []) or []
            except Exception:
                pass
        return None

    tasks = [fetch_one(e["url"], e["name"]) for e in results]
    done = 0
    for coro in asyncio.as_completed(tasks):
        res = await coro
        done += 1
        if done % 100 == 0:
            log.info("Индекс атак: %d/%d", done, len(results))
        if not res:
            continue
        name_en, names = res
        for n in names:
            lang = (n.get("language") or {}).get("name")
            if lang == "ru":
                ru = (n.get("name") or "").strip()
                if ru:
                    index[_norm_move_key(ru)] = name_en

    try:
        with open(MOVE_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        log.info("Индекс атак сохранён (%d записей)", len(index))
    except OSError as e:
        log.warning("Не удалось сохранить индекс атак: %s", e)
    return index


async def ensure_move_index() -> dict[str, str]:
    global _move_ru_to_en, _move_index_ready
    async with _move_index_lock:
        if _move_index_ready:
            return _move_ru_to_en
        if os.path.exists(MOVE_INDEX_FILE):
            try:
                with open(MOVE_INDEX_FILE, encoding="utf-8") as f:
                    _move_ru_to_en = json.load(f)
                _move_index_ready = True
                log.info("Индекс атак загружен: %d записей", len(_move_ru_to_en))
                return _move_ru_to_en
            except (OSError, json.JSONDecodeError) as e:
                log.warning("Не удалось прочитать индекс атак: %s", e)
        _move_ru_to_en = await _build_move_index()
        _move_index_ready = True
        return _move_ru_to_en


def resolve_move_name(name: str) -> str:
    """Если имя русское — ищет английский эквивалент.

    Порядок:
        1. ASCII — пропускаем как есть.
        2. Ручной словарь из battle_data.MOVE_NAMES_RU.
        3. Автоиндекс из move_index_ru.json (на случай, если PokéAPI
           всё-таки знает это имя в официальной локализации).
    """
    if not name:
        return name
    if name.isascii():
        return name

    # 1) ручной словарь
    try:
        from battle_data import resolve_move_ru
        manual = resolve_move_ru(name)
        if manual:
            return manual
    except Exception:
        log.exception("Не удалось использовать battle_data.resolve_move_ru")

    # 2) автоиндекс
    return _move_ru_to_en.get(_norm_move_key(name), name)
