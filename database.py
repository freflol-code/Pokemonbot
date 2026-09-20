"""Асинхронная БД на SQLite для Pokébot."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import aiosqlite

from data.locations import START_LOCATION

log = logging.getLogger(__name__)

POKEBALL_KEY = "pokeball"
POTION_KEY = "potion"
START_POKEBUCKS = 500
MAX_PARTY_SIZE = 6
DEFAULT_DB_PATH = "pokebot.db"

_db: Optional[aiosqlite.Connection] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS trainers (
    user_id   INTEGER PRIMARY KEY,
    wins      INTEGER NOT NULL DEFAULT 0,
    losses    INTEGER NOT NULL DEFAULT 0,
    pokebucks INTEGER NOT NULL DEFAULT 500,
    location  TEXT    NOT NULL DEFAULT 'hoshinori'
);

CREATE TABLE IF NOT EXISTS pokemon (
    instance_id TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    species_id  INTEGER NOT NULL,
    nickname    TEXT,
    level       INTEGER NOT NULL DEFAULT 5,
    gender      TEXT    NOT NULL DEFAULT 'genderless',
    moves       TEXT    NOT NULL DEFAULT '[]',
    in_party    INTEGER NOT NULL DEFAULT 0,
    slot        INTEGER,
    FOREIGN KEY (user_id) REFERENCES trainers(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pokemon_user ON pokemon(user_id);
CREATE INDEX IF NOT EXISTS idx_pokemon_party ON pokemon(user_id, in_party);

CREATE TABLE IF NOT EXISTS inventory (
    user_id  INTEGER NOT NULL,
    item_key TEXT    NOT NULL,
    qty      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES trainers(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pokedex (
    user_id    INTEGER NOT NULL,
    species_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, species_id),
    FOREIGN KEY (user_id) REFERENCES trainers(user_id) ON DELETE CASCADE
);
"""


# --------------------------------------------------------------------------- #
#                            ПОДКЛЮЧЕНИЕ / ОТКРЫТИЕ                          #
# --------------------------------------------------------------------------- #

async def connect(db_path: Optional[str] = None) -> None:
    """Открывает SQLite, создаёт таблицы и включает внешние ключи."""
    global _db
    path = db_path or os.getenv("SQLITE_DB", DEFAULT_DB_PATH)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON")
    await _db.executescript(SCHEMA)
    await _db.commit()
    log.info("SQLite подключён: %s", path)


async def close() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        log.info("SQLite закрыт")


def _conn() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("SQLite не инициализирован. Вызовите database.connect().")
    return _db


# --------------------------------------------------------------------------- #
#                              ХЕЛПЕРЫ                                        #
# --------------------------------------------------------------------------- #

def _trainer_dict(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "wins": row["wins"],
        "losses": row["losses"],
        "pokebucks": row["pokebucks"],
        "location": row["location"],
    }


def _pokemon_dict(row: aiosqlite.Row) -> dict[str, Any]:
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


async def _ensure_trainer(user_id: int) -> None:
    db = _conn()
    await db.execute(
        "INSERT OR IGNORE INTO trainers (user_id, wins, losses, pokebucks, location) "
        "VALUES (?, 0, 0, ?, ?)",
        (user_id, START_POKEBUCKS, START_LOCATION),
    )
    await db.commit()


# --------------------------------------------------------------------------- #
#                                ТРЕНЕРЫ                                      #
# --------------------------------------------------------------------------- #

async def get_trainer(user_id: int) -> dict[str, Any]:
    """Возвращает словарь тренера в том же формате, что и раньше (совместимость)."""
    await _ensure_trainer(user_id)
    db = _conn()

    async with db.execute(
        "SELECT * FROM trainers WHERE user_id = ?", (user_id,)
    ) as cur:
        trow = await cur.fetchone()
    trainer = _trainer_dict(trow)

    async with db.execute(
        "SELECT * FROM pokemon WHERE user_id = ? AND in_party = 1 "
        "ORDER BY slot ASC, instance_id ASC",
        (user_id,),
    ) as cur:
        party_rows = await cur.fetchall()

    async with db.execute(
        "SELECT * FROM pokemon WHERE user_id = ? AND in_party = 0 "
        "ORDER BY rowid ASC",
        (user_id,),
    ) as cur:
        pc_rows = await cur.fetchall()

    trainer["party"] = [_pokemon_dict(r) for r in party_rows]
    trainer["pc"] = [_pokemon_dict(r) for r in pc_rows]

    async with db.execute(
        "SELECT item_key, qty FROM inventory WHERE user_id = ?", (user_id,)
    ) as cur:
        inv_rows = await cur.fetchall()
    trainer["inventory"] = {r["item_key"]: r["qty"] for r in inv_rows}

    async with db.execute(
        "SELECT species_id FROM pokedex WHERE user_id = ?", (user_id,)
    ) as cur:
        dex_rows = await cur.fetchall()
    trainer["pokedex_known"] = [r["species_id"] for r in dex_rows]

    return trainer


async def set_location(user_id: int, location: str) -> None:
    await _ensure_trainer(user_id)
    db = _conn()
    await db.execute(
        "UPDATE trainers SET location = ? WHERE user_id = ?", (location, user_id)
    )
    await db.commit()


async def add_pokebucks(user_id: int, amount: int) -> int:
    """Прибавляет сумму (может быть отрицательной). Не уходит ниже 0."""
    await _ensure_trainer(user_id)
    db = _conn()
    async with db.execute(
        "SELECT pokebucks FROM trainers WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    current = row["pokebucks"] if row else 0
    new_value = max(0, current + int(amount))
    await db.execute(
        "UPDATE trainers SET pokebucks = ? WHERE user_id = ?", (new_value, user_id)
    )
    await db.commit()
    return new_value


async def spend_pokebucks(user_id: int, cost: int) -> bool:
    """Атомарно списывает деньги. False — если не хватает."""
    await _ensure_trainer(user_id)
    db = _conn()
    cursor = await db.execute(
        "UPDATE trainers SET pokebucks = pokebucks - ? "
        "WHERE user_id = ? AND pokebucks >= ?",
        (cost, user_id, cost),
    )
    await db.commit()
    return cursor.rowcount > 0


async def inc_wins(user_id: int, amount: int = 1) -> None:
    await _ensure_trainer(user_id)
    db = _conn()
    await db.execute(
        "UPDATE trainers SET wins = wins + ? WHERE user_id = ?", (amount, user_id)
    )
    await db.commit()


async def inc_losses(user_id: int, amount: int = 1) -> None:
    await _ensure_trainer(user_id)
    db = _conn()
    await db.execute(
        "UPDATE trainers SET losses = losses + ? WHERE user_id = ?", (amount, user_id)
    )
    await db.commit()


# --------------------------------------------------------------------------- #
#                                ПОКЕМОНЫ                                     #
# --------------------------------------------------------------------------- #

async def add_pokemon(
    user_id: int, mon: dict[str, Any], to_party: bool = False
) -> bool:
    """Добавляет покемона. Возвращает True, если он попал в команду."""
    await _ensure_trainer(user_id)
    db = _conn()

    in_party = 0
    slot: Optional[int] = None
    if to_party:
        async with db.execute(
            "SELECT COUNT(*) AS c FROM pokemon WHERE user_id = ? AND in_party = 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row["c"] < MAX_PARTY_SIZE:
            in_party = 1
            slot = int(row["c"])

    moves_json = json.dumps(mon.get("moves", []), ensure_ascii=False)
    await db.execute(
        "INSERT INTO pokemon "
        "(instance_id, user_id, species_id, nickname, level, gender, moves, in_party, slot) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mon["instance_id"],
            user_id,
            int(mon["species_id"]),
            mon.get("nickname"),
            int(mon.get("level", 5)),
            mon.get("gender", "genderless"),
            moves_json,
            in_party,
            slot,
        ),
    )
    await db.commit()
    return bool(in_party)


async def remove_pokemon(user_id: int, instance_id: str) -> bool:
    db = _conn()
    cursor = await db.execute(
        "DELETE FROM pokemon WHERE user_id = ? AND instance_id = ?",
        (user_id, instance_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def _reslot_party(user_id: int) -> None:
    """Пересобирает слоты в команде (0, 1, 2, ...), чтобы не было дырок."""
    db = _conn()
    async with db.execute(
        "SELECT instance_id FROM pokemon WHERE user_id = ? AND in_party = 1 "
        "ORDER BY slot ASC, instance_id ASC",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    for i, r in enumerate(rows):
        await db.execute(
            "UPDATE pokemon SET slot = ? WHERE instance_id = ?",
            (i, r["instance_id"]),
        )


async def move_pokemon(
    user_id: int, instance_id: str, to_party: bool
) -> tuple[bool, str]:
    """Перемещает покемона между ПК и командой. Возвращает (успех, сообщение)."""
    db = _conn()

    async with db.execute(
        "SELECT * FROM pokemon WHERE user_id = ? AND instance_id = ?",
        (user_id, instance_id),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return False, "Покемон не найден."

    already_party = bool(row["in_party"])
    if already_party == to_party:
        return False, "Покемон уже там." if to_party else "Покемон уже в ПК."

    if to_party:
        async with db.execute(
            "SELECT COUNT(*) AS c FROM pokemon WHERE user_id = ? AND in_party = 1",
            (user_id,),
        ) as cur:
            cnt_row = await cur.fetchone()
        if cnt_row["c"] >= MAX_PARTY_SIZE:
            return False, f"Команда заполнена ({MAX_PARTY_SIZE}/{MAX_PARTY_SIZE})."
        new_slot = int(cnt_row["c"])
        await db.execute(
            "UPDATE pokemon SET in_party = 1, slot = ? "
            "WHERE user_id = ? AND instance_id = ?",
            (new_slot, user_id, instance_id),
        )
    else:
        await db.execute(
            "UPDATE pokemon SET in_party = 0, slot = NULL "
            "WHERE user_id = ? AND instance_id = ?",
            (user_id, instance_id),
        )
        await _reslot_party(user_id)

    await db.commit()
    return True, "OK"


async def update_pokemon(user_id: int, instance_id: str, **fields: Any) -> bool:
    """Обновляет поля покемона: nickname, level, gender, moves, species_id."""
    if not fields:
        return False
    if "moves" in fields and not isinstance(fields["moves"], str):
        fields["moves"] = json.dumps(fields["moves"], ensure_ascii=False)
    allowed = {"nickname", "level", "gender", "moves", "species_id"}
    update_fields = {k: v for k, v in fields.items() if k in allowed}
    if not update_fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in update_fields)
    values = list(update_fields.values()) + [user_id, instance_id]
    db = _conn()
    cursor = await db.execute(
        f"UPDATE pokemon SET {set_clause} WHERE user_id = ? AND instance_id = ?",
        values,
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_pokemon(user_id: int, instance_id: str) -> dict[str, Any] | None:
    db = _conn()
    async with db.execute(
        "SELECT * FROM pokemon WHERE user_id = ? AND instance_id = ?",
        (user_id, instance_id),
    ) as cur:
        row = await cur.fetchone()
    return _pokemon_dict(row) if row else None


# --------------------------------------------------------------------------- #
#                                ИНВЕНТАРЬ                                    #
# --------------------------------------------------------------------------- #

async def add_item(user_id: int, item_key: str, qty: int) -> None:
    await _ensure_trainer(user_id)
    db = _conn()
    await db.execute(
        "INSERT INTO inventory (user_id, item_key, qty) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, item_key) DO UPDATE SET qty = qty + excluded.qty",
        (user_id, item_key, qty),
    )
    await db.commit()


async def get_item_qty(user_id: int, item_key: str) -> int:
    db = _conn()
    async with db.execute(
        "SELECT qty FROM inventory WHERE user_id = ? AND item_key = ?",
        (user_id, item_key),
    ) as cur:
        row = await cur.fetchone()
    return row["qty"] if row else 0


async def take_item(user_id: int, item_key: str, qty: int = 1) -> bool:
    """Списывает qty предметов. False, если не хватает."""
    db = _conn()
    cursor = await db.execute(
        "UPDATE inventory SET qty = qty - ? "
        "WHERE user_id = ? AND item_key = ? AND qty >= ?",
        (qty, user_id, item_key, qty),
    )
    await db.commit()
    return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
#                                ПОКЕДЕКС                                     #
# --------------------------------------------------------------------------- #

async def add_to_pokedex(user_id: int, species_id: int) -> bool:
    """True — вид добавлен впервые, False — уже был."""
    await _ensure_trainer(user_id)
    db = _conn()
    cursor = await db.execute(
        "INSERT OR IGNORE INTO pokedex (user_id, species_id) VALUES (?, ?)",
        (user_id, int(species_id)),
    )
    await db.commit()
    return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
#                                  СБРОС                                      #
# --------------------------------------------------------------------------- #

async def reset_trainer(user_id: int) -> None:
    """Полный сброс тренера к стартовому состоянию."""
    db = _conn()
    await db.execute("DELETE FROM pokemon   WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM pokedex   WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM trainers  WHERE user_id = ?", (user_id,))
    await db.commit()

    await _ensure_trainer(user_id)
    await add_item(user_id, POKEBALL_KEY, 5)
    await add_item(user_id, POTION_KEY, 3)
