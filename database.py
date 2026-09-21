"""Асинхронная БД на PostgreSQL (Supabase) для Pokébot с мульти-профилями."""
import json
import logging
import os
import uuid
from typing import Any, Optional

import asyncpg

log = logging.getLogger(__name__)

POKEBALL_KEY = "pokeball"
POTION_KEY = "potion"
START_POKEBUCKS = 0
MAX_PARTY_SIZE = 6
START_LOCATION = "hoshinori"

PROFILE_TYPES = ("trainer", "pokemon")

_pool: Optional[asyncpg.Pool] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    profile_id   TEXT PRIMARY KEY,
    user_id      BIGINT NOT NULL,
    name         TEXT NOT NULL,
    profile_type TEXT NOT NULL DEFAULT 'trainer',
    avatar_url   TEXT,
    wins         INTEGER NOT NULL DEFAULT 0,
    losses       INTEGER NOT NULL DEFAULT 0,
    pokebucks    INTEGER NOT NULL DEFAULT 0,
    location     TEXT NOT NULL DEFAULT 'hoshinori',
    is_active    BOOLEAN NOT NULL DEFAULT FALSE,
    level        INTEGER,
    moves        TEXT,
    ability      TEXT,
    status       TEXT DEFAULT 'wild',
    pokeball     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_active ON profiles(user_id) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS pokemon (
    instance_id TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    species_id  INTEGER NOT NULL,
    nickname    TEXT,
    level       INTEGER NOT NULL DEFAULT 5,
    gender      TEXT NOT NULL DEFAULT 'genderless',
    moves       TEXT NOT NULL DEFAULT '[]',
    ability     TEXT,
    in_party    INTEGER NOT NULL DEFAULT 0,
    slot        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pokemon_profile ON pokemon(profile_id);
CREATE INDEX IF NOT EXISTS idx_pokemon_party ON pokemon(profile_id, in_party);

CREATE TABLE IF NOT EXISTS inventory (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    item_key   TEXT NOT NULL,
    qty        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, item_key)
);

CREATE TABLE IF NOT EXISTS pokedex (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL,
    PRIMARY KEY (profile_id, species_id)
);
"""

MIGRATION = """
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS level INTEGER;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS moves TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS ability TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'wild';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS pokeball TEXT;
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
        await _migrate_or_create(conn)
    log.info("PostgreSQL подключён (Supabase)")


async def _migrate_or_create(conn: asyncpg.Connection) -> None:
    old_schema = await conn.fetchval("SELECT to_regclass('public.trainers')")
    if old_schema:
        log.warning("Обнаружена старая схема (trainers) — сбрасываю таблицы")
        for tbl in ("pokemon", "inventory", "pokedex", "trainers"):
            await conn.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
    await conn.execute(SCHEMA)
    await conn.execute(MIGRATION)


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("PostgreSQL закрыт")


def _pool_conn() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("PostgreSQL не инициализирован.")
    return _pool


# --------------------------------------------------------------------------- #
#                        ПРОФИЛИ (персонажи игрока)                            #
# --------------------------------------------------------------------------- #

def _profile_dict(row: asyncpg.Record) -> dict[str, Any]:
    try:
        moves = json.loads(row["moves"]) if row["moves"] else []
    except (json.JSONDecodeError, TypeError):
        moves = []
    return {
        "profile_id": row["profile_id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "profile_type": row["profile_type"],
        "avatar_url": row["avatar_url"],
        "wins": row["wins"],
        "losses": row["losses"],
        "pokebucks": row["pokebucks"],
        "location": row["location"],
        "is_active": row["is_active"],
        "level": row["level"],
        "moves": moves,
        "ability": row["ability"],
        "status": row["status"] or "wild",
        "pokeball": row["pokeball"],
    }


async def create_profile(
    user_id: int,
    name: str,
    profile_type: str = "trainer",
    avatar_url: Optional[str] = None,
    make_active: bool = True,
    level: Optional[int] = None,
    moves: Optional[list[str]] = None,
    ability: Optional[str] = None,
    status: Optional[str] = None,
    pokeball: Optional[str] = None,
) -> dict[str, Any]:
    if profile_type not in PROFILE_TYPES:
        profile_type = "trainer"

    pid = uuid.uuid4().hex[:12]
    moves_json = json.dumps(moves, ensure_ascii=False) if moves else None

    pool = _pool_conn()
    async with pool.acquire() as conn:
        if make_active:
            await conn.execute(
                "UPDATE profiles SET is_active = FALSE WHERE user_id = $1", user_id,
            )
        await conn.execute(
            "INSERT INTO profiles "
            "(profile_id, user_id, name, profile_type, avatar_url, is_active, "
            " level, moves, ability, status, pokeball) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
            pid, user_id, name, profile_type, avatar_url, make_active,
            level, moves_json, ability, status, pokeball,
        )
        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE profile_id = $1", pid,
        )
    return _profile_dict(row)


async def get_profile(profile_id: str) -> Optional[dict[str, Any]]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE profile_id = $1", profile_id,
        )
    return _profile_dict(row) if row else None


async def list_profiles(user_id: int) -> list[dict[str, Any]]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM profiles WHERE user_id = $1 ORDER BY created_at ASC",
            user_id,
        )
    return [_profile_dict(r) for r in rows]


async def get_active_profile(user_id: int) -> Optional[dict[str, Any]]:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id = $1 AND is_active = TRUE LIMIT 1",
            user_id,
        )
    return _profile_dict(row) if row else None


async def switch_profile(user_id: int, profile_id: str) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM profiles WHERE profile_id = $1 AND user_id = $2",
            profile_id, user_id,
        )
        if not exists:
            return False
        await conn.execute(
            "UPDATE profiles SET is_active = FALSE WHERE user_id = $1", user_id,
        )
        await conn.execute(
            "UPDATE profiles SET is_active = TRUE WHERE profile_id = $1", profile_id,
        )
    return True


async def delete_profile(user_id: int, profile_id: str) -> bool:
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE profile_id = $1 AND user_id = $2",
            profile_id, user_id,
        )
        if not row:
            return False
        was_active = bool(row["is_active"])
        await conn.execute("DELETE FROM profiles WHERE profile_id = $1", profile_id)
        if was_active:
            new_active = await conn.fetchrow(
                "SELECT profile_id FROM profiles WHERE user_id = $1 "
                "ORDER BY created_at ASC LIMIT 1", user_id,
            )
            if new_active:
                await conn.execute(
                    "UPDATE profiles SET is_active = TRUE WHERE profile_id = $1",
                    new_active["profile_id"],
                )
    return True


async def _ensure_profile(user_id: int) -> dict[str, Any]:
    profile = await get_active_profile(user_id)
    if profile:
        return profile
    return await create_profile(user_id, name="Тренер", profile_type="trainer")


# --------------------------------------------------------------------------- #
#                    СОВМЕСТИМОСТЬ СО СТАРЫМИ КОГАМИ                           #
# --------------------------------------------------------------------------- #

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
        "ability": row["ability"],
    }


async def get_trainer(user_id: int) -> dict[str, Any]:
    profile = await _ensure_profile(user_id)
    pid = profile["profile_id"]

    pool = _pool_conn()
    async with pool.acquire() as conn:
        party_rows = await conn.fetch(
            "SELECT * FROM pokemon WHERE profile_id = $1 AND in_party = 1 "
            "ORDER BY slot ASC, instance_id ASC", pid,
        )
        pc_rows = await conn.fetch(
            "SELECT * FROM pokemon WHERE profile_id = $1 AND in_party = 0 "
            "ORDER BY instance_id ASC", pid,
        )
        inv_rows = await conn.fetch(
            "SELECT item_key, qty FROM inventory WHERE profile_id = $1", pid,
        )
        dex_rows = await conn.fetch(
            "SELECT species_id FROM pokedex WHERE profile_id = $1", pid,
        )

    trainer = dict(profile)
    trainer["party"] = [_pokemon_dict(r) for r in party_rows]
    trainer["pc"] = [_pokemon_dict(r) for r in pc_rows]
    trainer["inventory"] = {r["item_key"]: r["qty"] for r in inv_rows}
    trainer["pokedex_known"] = [r["species_id"] for r in dex_rows]
    return trainer


async def _pid_of(user_id: int) -> str:
    profile = await _ensure_profile(user_id)
    return profile["profile_id"]


# --------------------------------------------------------------------------- #
#                        ДЕНЬГИ / ЛОКАЦИЯ / СТАТЫ                              #
# --------------------------------------------------------------------------- #

async def set_location(user_id: int, location: str) -> None:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE profiles SET location = $1 WHERE profile_id = $2", location, pid,
        )


async def add_pokebucks(user_id: int, amount: int) -> int:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pokebucks FROM profiles WHERE profile_id = $1", pid,
        )
        current = row["pokebucks"] if row else 0
        new_value = max(0, current + int(amount))
        await conn.execute(
            "UPDATE profiles SET pokebucks = $1 WHERE profile_id = $2", new_value, pid,
        )
    return new_value


async def spend_pokebucks(user_id: int, cost: int) -> bool:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE profiles SET pokebucks = pokebucks - $1 "
            "WHERE profile_id = $2 AND pokebucks >= $1", cost, pid,
        )
    return result.endswith("1")


async def inc_wins(user_id: int, amount: int = 1) -> None:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE profiles SET wins = wins + $1 WHERE profile_id = $2", amount, pid,
        )


async def inc_losses(user_id: int, amount: int = 1) -> None:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE profiles SET losses = losses + $1 WHERE profile_id = $2", amount, pid,
        )


# --------------------------------------------------------------------------- #
#                                  ПОКЕМОНЫ                                    #
# --------------------------------------------------------------------------- #

async def add_pokemon(user_id: int, mon: dict[str, Any], to_party: bool = False) -> bool:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        in_party = 0
        slot: Optional[int] = None
        if to_party:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM pokemon WHERE profile_id = $1 AND in_party = 1",
                pid,
            )
            if cnt < MAX_PARTY_SIZE:
                in_party = 1
                slot = int(cnt)

        moves_json = json.dumps(mon.get("moves", []), ensure_ascii=False)
        await conn.execute(
            "INSERT INTO pokemon "
            "(instance_id, profile_id, species_id, nickname, level, gender, moves, ability, in_party, slot) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            mon["instance_id"], pid, int(mon["species_id"]),
            mon.get("nickname"), int(mon.get("level", 5)),
            mon.get("gender", "genderless"), moves_json,
            mon.get("ability"), in_party, slot,
        )
    return bool(in_party)


async def remove_pokemon(user_id: int, instance_id: str) -> bool:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM pokemon WHERE profile_id = $1 AND instance_id = $2",
            pid, instance_id,
        )
    return result.endswith("1")


async def _reslot_party(conn: asyncpg.Connection, pid: str) -> None:
    rows = await conn.fetch(
        "SELECT instance_id FROM pokemon WHERE profile_id = $1 AND in_party = 1 "
        "ORDER BY slot ASC, instance_id ASC", pid,
    )
    for i, r in enumerate(rows):
        await conn.execute(
            "UPDATE pokemon SET slot = $1 WHERE instance_id = $2",
            i, r["instance_id"],
        )


async def move_pokemon(user_id: int, instance_id: str, to_party: bool) -> tuple[bool, str]:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pokemon WHERE profile_id = $1 AND instance_id = $2",
            pid, instance_id,
        )
        if row is None:
            return False, "Покемон не найден."

        already_party = bool(row["in_party"])
        if already_party == to_party:
            return False, "Покемон уже там." if to_party else "Покемон уже в ПК."

        if to_party:
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM pokemon WHERE profile_id = $1 AND in_party = 1",
                pid,
            )
            if cnt >= MAX_PARTY_SIZE:
                return False, f"Команда заполнена ({MAX_PARTY_SIZE}/{MAX_PARTY_SIZE})."
            await conn.execute(
                "UPDATE pokemon SET in_party = 1, slot = $1 "
                "WHERE profile_id = $2 AND instance_id = $3",
                int(cnt), pid, instance_id,
            )
        else:
            await conn.execute(
                "UPDATE pokemon SET in_party = 0, slot = NULL "
                "WHERE profile_id = $1 AND instance_id = $2",
                pid, instance_id,
            )
            await _reslot_party(conn, pid)
    return True, "OK"


async def update_pokemon(user_id: int, instance_id: str, **fields: Any) -> bool:
    if not fields:
        return False
    if "moves" in fields and not isinstance(fields["moves"], str):
        fields["moves"] = json.dumps(fields["moves"], ensure_ascii=False)
    allowed = {"nickname", "level", "gender", "moves", "species_id", "ability"}
    update_fields = {k: v for k, v in fields.items() if k in allowed}
    if not update_fields:
        return False

    pid = await _pid_of(user_id)
    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(update_fields))
    values = list(update_fields.values()) + [pid, instance_id]
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE pokemon SET {set_clause} "
            f"WHERE profile_id = ${len(values)-1} AND instance_id = ${len(values)}",
            *values,
        )
    return result.endswith("1")


async def get_pokemon(user_id: int, instance_id: str) -> Optional[dict[str, Any]]:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pokemon WHERE profile_id = $1 AND instance_id = $2",
            pid, instance_id,
        )
    return _pokemon_dict(row) if row else None


# --------------------------------------------------------------------------- #
#                                  ИНВЕНТАРЬ                                   #
# --------------------------------------------------------------------------- #

async def add_item(user_id: int, item_key: str, qty: int) -> None:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO inventory (profile_id, item_key, qty) VALUES ($1, $2, $3) "
            "ON CONFLICT (profile_id, item_key) DO UPDATE "
            "SET qty = inventory.qty + EXCLUDED.qty",
            pid, item_key, qty,
        )


async def get_item_qty(user_id: int, item_key: str) -> int:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT qty FROM inventory WHERE profile_id = $1 AND item_key = $2",
            pid, item_key,
        )
    return row["qty"] if row else 0


async def take_item(user_id: int, item_key: str, qty: int = 1) -> bool:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE inventory SET qty = qty - $1 "
            "WHERE profile_id = $2 AND item_key = $3 AND qty >= $1",
            qty, pid, item_key,
        )
    return result.endswith("1")


# --------------------------------------------------------------------------- #
#                                  ПОКЕДЕКС                                    #
# --------------------------------------------------------------------------- #

async def add_to_pokedex(user_id: int, species_id: int) -> bool:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "INSERT INTO pokedex (profile_id, species_id) VALUES ($1, $2) "
            "ON CONFLICT (profile_id, species_id) DO NOTHING",
            pid, int(species_id),
        )
    return result.endswith("1")


# --------------------------------------------------------------------------- #
#                                    СБРОС                                     #
# --------------------------------------------------------------------------- #

async def reset_trainer(user_id: int) -> None:
    pid = await _pid_of(user_id)
    pool = _pool_conn()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pokemon   WHERE profile_id = $1", pid)
        await conn.execute("DELETE FROM inventory WHERE profile_id = $1", pid)
        await conn.execute("DELETE FROM pokedex   WHERE profile_id = $1", pid)
        await conn.execute(
            "UPDATE profiles SET wins = 0, losses = 0, pokebucks = 0 WHERE profile_id = $1",
            pid,
        )
