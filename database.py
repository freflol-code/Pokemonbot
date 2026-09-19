"""Подключение к MongoDB и работа с документами тренеров."""
from __future__ import annotations

import logging
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from pymongo.results import UpdateResult

log = logging.getLogger(__name__)

POKEBALL_KEY = "pokeball"
POTION_KEY = "potion"
START_POKEBUCKS = 500
MAX_PARTY_SIZE = 6

_client: Optional[AsyncIOMotorClient] = None
_collection = None


async def connect(uri: str, db_name: str) -> None:
    """Подключается к MongoDB, проверяет связь и создаёт индекс."""
    global _client, _collection
    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000)
    await _client.admin.command("ping")
    _collection = _client[db_name]["trainers"]
    await _collection.create_index("user_id", unique=True)
    log.info("Подключено к MongoDB (база %s)", db_name)


def close() -> None:
    if _client is not None:
        _client.close()


def _new_trainer(user_id: int) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "wins": 0,
        "losses": 0,
        "pokebucks": START_POKEBUCKS,
        "pokedex_known": [],
        "inventory": {POKEBALL_KEY: 5, POTION_KEY: 3},
        "party": [],
        "pc": [],
    }


async def get_trainer(user_id: int) -> dict[str, Any]:
    """Возвращает документ тренера; при первом обращении создаёт его."""
    doc = await _collection.find_one({"user_id": user_id})
    if doc is not None:
        return doc
    doc = _new_trainer(user_id)
    try:
        await _collection.insert_one(doc)
    except DuplicateKeyError:  # параллельный запрос успел раньше
        doc = await _collection.find_one({"user_id": user_id})
    return doc


async def update_trainer(
    user_id: int,
    update: dict[str, Any],
    extra_filter: Optional[dict[str, Any]] = None,
) -> UpdateResult:
    """Атомарно применяет операторы обновления Mongo ($set, $inc, $push...).

    extra_filter добавляет условия (например, достаточно ли денег) — если они
    не выполнены, matched_count у результата будет равен 0.
    """
    await get_trainer(user_id)
    flt: dict[str, Any] = {"user_id": user_id}
    if extra_filter:
        flt.update(extra_filter)
    return await _collection.update_one(flt, update)
