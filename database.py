"""Асинхронная БД на PostgreSQL (Supabase) для Pokébot."""
import json
import logging
import os
from typing import Any, Optional

import asyncpg

log = logging.getLogger(__name__)

POKEBALL_KEY = "pokeball"
POTION_KEY = "potion"
START_POKEBUCKS = 500
MAX_PARTY_SIZE = 6
START_LOCATION = "hoshinori"

_pool: Optional[asyncpg.Pool] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS trainers (
    user_id   BIGINT PRIMARY KEY,
    wins      INTEGER NOT NULL DEFAULT 0,
    losses    INTEGER NOT NULL DEFAULT 0,
    pokebucks INTEGER NOT NULL DEFAULT 500,
    location  TEXT    NOT NULL DEFAULT 'hoshinori'
);

CREATE TABLE IF NOT EXISTS pokemon (
    instance_id TEXT PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES trainers(user_id) ON DELETE CASCADE,
    species_id  INTEGER NOT NULL,
    nickname    TEXT,
    level       INTEGER NOT NULL DEFAULT 5,
    gender      TEXT    NOT NULL DEFAULT 'genderless',
    moves       TEXT    NOT NULL DEFAULT '[]',
    in_party    INTEGER NOT NULL DEFAULT 0,
    slot        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pokemon_user ON pokemon(user_id);
CREATE INDEX IF NOT EXISTS idx_pokemon_party ON pokemon(user_id, in_party);

CREATE TABLE IF NOT EXISTS inventory (
    user_id  BIGINT NOT NULL REFERENCES trainers(user_id) ON DELETE CASCADE,
    item_key TEXT    NOT NULL,
    qty      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item_key)
);

CREATE TABLE IF NOT EXISTS pokedex (
    user_id    BIGINT NOT NULL REFERENCES trainers(user_id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, species_id)
);
"""


async def connect(database_url: Optional[str] = None) -> None:
    global _pool
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL не задан в переменных окружения")

    _pool = await asyncpg.create_pool(
        url,
        min_size=1,
        max_size=5,
        statement_cache_size=0,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
    log.info("PostgreSQL подключён (Supabase)")


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("PostgreSQL закрыт")


def _pool_conn() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите database.connect().")
    return _pool


def _trainer_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "wins": row["wins"],
        "losses": row["losses"],
        "pokebucks": row["pokebucks"],
        "location": row["location"],
    }


def _pokemon_dict(row: asyncpg.Record) -> dict[str, Any]:
    try:
        moves = json.loads(row["moves"]) if row["moves"] else []
    except json.JSONDecodeError:
        moves = []
    return {
        "instance_id": row["instance_id"],
        "species_id": row["species_id"],
        "nickname": row["nickname"],
        "level": row["level"],
        "gender": row["gender"],
        "moves": moves,
    }


async def _ensure_trainer(conn: asyncpg.Connection, user_id: int) -> None:
    await conn.execute(
        "INSERT INTO trainers (user_id, wins, losses, pokebucks, location) "
        "VALUES ($1, 0, 0, $2, $3) ON CONFLICT (user_id) DO NOTHING",
        user_id, START_POKEBUCKS, START_LOCATION,
    )


async def get_trainer(user_id: int) -> dict[str, Any]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)

        trow = await conn.fetchrow("SELECT * FROM trainers WHERE user_id = $1", user_id)
        trainer = _trainer_dict(trow)

        party_rows = await conn.fetch(
            "SELECT * FROM pokemon WHERE user_id = $1 AND in_party = 1 "
            "ORDER BY slot ASC, instance_id ASC", user_id,
        )
        pc_rows = await conn.fetch(
            "SELECT * FROM pokemon WHERE user_id = $1 AND in_party = 0 "
            "ORDER BY instance_id ASC", user_id,
        )
        trainer["party"] = [_pokemon_dict(r) for r in party_rows]
        trainer["pc"] = [_pokemon_dict(r) for r in pc_rows]

        inv_rows = await conn.fetch(
            "SELECT item_key, qty FROM inventory WHERE user_id = $1", user_id,
        )
        trainer["inventory"] = {r["item_key"]: r["qty"] for r in inv_rows}

        dex_rows = await conn.fetch(
            "SELECT species_id FROM pokedex WHERE user_id = $1", user_id,
        )
        trainer["pokedex_known"] = [r["species_id"] for r in dex_rows]

    return trainer


async def set_location(user_id: int, location: str) -> None:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        await conn.execute(
            "UPDATE trainers SET location = $1 WHERE user_id = $2", location, user_id,
        )


async def add_pokebucks(user_id: int, amount: int) -> int:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        row = await conn.fetchrow(
            "SELECT pokebucks FROM trainers WHERE user_id = $1", user_id,
        )
        current = row["pokebucks"] if row else 0
        new_value = max(0, current + int(amount))
        await conn.execute(
            "UPDATE trainers SET pokebucks = $1 WHERE user_id = $2", new_value, user_id,
        )
    return new_value


async def spend_pokebucks(user_id: int, cost: int) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        result = await conn.execute(
            "UPDATE trainers SET pokebucks = pokebucks - $1 "
            "WHERE user_id = $2 AND pokebucks >= $1",
            cost, user_id,
        )
    return result.endswith("1")


async def inc_wins(user_id: int, amount: int = 1) -> None:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        await conn.execute(
            "UPDATE trainers SET wins = wins + $1 WHERE user_id = $2", amount, user_id,
        )


async def inc_losses(user_id: int, amount: int = 1) -> None:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        await conn.execute(
            "UPDATE trainers SET losses = losses + $1 WHERE user_id = $2", amount, user_id,
        )


async def add_pokemon(user_id: int, mon: dict[str, Any], to_party: bool = False) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)

        in_party = 0
        slot: Optional[int] = None
        if to_party:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM pokemon WHERE user_id = $1 AND in_party = 1",
                user_id,
            )
            if cnt < MAX_PARTY_SIZE:
                in_party = 1
                slot = int(cnt)

        moves_json = json.dumps(mon.get("moves", []), ensure_ascii=False)
        await conn.execute(
            "INSERT INTO pokemon "
            "(instance_id, user_id, species_id, nickname, level, gender, moves, in_party, slot) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            mon["instance_id"], user_id, int(mon["species_id"]),
            mon.get("nickname"), int(mon.get("level", 5)),
            mon.get("gender", "genderless"), moves_json, in_party, slot,
        )
    return bool(in_party)


async def remove_pokemon(user_id: int, instance_id: str) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM pokemon WHERE user_id = $1 AND instance_id = $2",
            user_id, instance_id,
        )
    return result.endswith("1")


async def _reslot_party(conn: asyncpg.Connection, user_id: int) -> None:
    rows = await conn.fetch(
        "SELECT instance_id FROM pokemon WHERE user_id = $1 AND in_party = 1 "
        "ORDER BY slot ASC, instance_id ASC", user_id,
    )
    for i, r in enumerate(rows):
        await conn.execute(
            "UPDATE pokemon SET slot = $1 WHERE instance_id = $2",
            i, r["instance_id"],
        )


async def move_pokemon(user_id: int, instance_id: str, to_party: bool) -> tuple[bool, str]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pokemon WHERE user_id = $1 AND instance_id = $2",
            user_id, instance_id,
        )
        if row is None:
            return False, "Покемон не найден."

        already_party = bool(row["in_party"])
        if already_party == to_party:
            return False, "Покемон уже там." if to_party else "Покемон уже в ПК."

        if to_party:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM pokemon WHERE user_id = $1 AND in_party = 1",
                user_id,
            )
            if cnt >= MAX_PARTY_SIZE:
                return False, f"Команда заполнена ({MAX_PARTY_SIZE}/{MAX_PARTY_SIZE})."
            await conn.execute(
                "UPDATE pokemon SET in_party = 1, slot = $1 "
                "WHERE user_id = $2 AND instance_id = $3",
                int(cnt), user_id, instance_id,
            )
        else:
            await conn.execute(
                "UPDATE pokemon SET in_party = 0, slot = NULL "
                "WHERE user_id = $1 AND instance_id = $2",
                user_id, instance_id,
            )
            await _reslot_party(conn, user_id)

    return True, "OK"


async def update_pokemon(user_id: int, instance_id: str, **fields: Any) -> bool:
    if not fields:
        return False
    if "moves" in fields and not isinstance(fields["moves"], str):
        fields["moves"] = json.dumps(fields["moves"], ensure_ascii=False)
    allowed = {"nickname", "level", "gender", "moves", "species_id"}
    update_fields = {k: v for k, v in fields.items() if k in allowed}
    if not update_fields:
        return False

    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(update_fields))
    values = list(update_fields.values()) + [user_id, instance_id]
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE pokemon SET {set_clause} "
            f"WHERE user_id = ${len(values)-1} AND instance_id = ${len(values)}",
            *values,
        )
    return result.endswith("1")


async def get_pokemon(user_id: int, instance_id: str) -> Optional[dict[str, Any]]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pokemon WHERE user_id = $1 AND instance_id = $2",
            user_id, instance_id,
        )
    return _pokemon_dict(row) if row else None


async def add_item(user_id: int, item_key: str, qty: int) -> None:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        await conn.execute(
            "INSERT INTO inventory (user_id, item_key, qty) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id, item_key) DO UPDATE SET qty = inventory.qty + EXCLUDED.qty",
            user_id, item_key, qty,
        )


async def get_item_qty(user_id: int, item_key: str) -> int:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT qty FROM inventory WHERE user_id = $1 AND item_key = $2",
            user_id, item_key,
        )
    return row["qty"] if row else 0


async def take_item(user_id: int, item_key: str, qty: int = 1) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE inventory SET qty = qty - $1 "
            "WHERE user_id = $2 AND item_key = $3 AND qty >= $1",
            qty, user_id, item_key,
        )
    return result.endswith("1")


async def add_to_pokedex(user_id: int, species_id: int) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await _ensure_trainer(conn, user_id)
        result = await conn.execute(
            "INSERT INTO pokedex (user_id, species_id) VALUES ($1, $2) "
            "ON CONFLICT (user_id, species_id) DO NOTHING",
            user_id, int(species_id),
        )
    return result.endswith("1")


async def reset_trainer(user_id: int) -> None:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pokemon   WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM inventory WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM pokedex   WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM trainers  WHERE user_id = $1", user_id)
        await _ensure_trainer(conn, user_id)
        await conn.execute(
            "INSERT INTO inventory (user_id, item_key, qty) VALUES ($1, $2, 5) "
            "ON CONFLICT (user_id, item_key) DO UPDATE SET qty = 5",
            user_id, POKEBALL_KEY,
        )
        await conn.execute(
            "INSERT INTO inventory (user_id, item_key, qty) VALUES ($1, $2, 3) "
            "ON CONFLICT (user_id, item_key) DO UPDATE SET qty = 3",
            user_id, POTION_KEY,
        )
