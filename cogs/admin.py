"""Мастерские команды — выдача покемонов и денег."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    MAX_PARTY_SIZE,
    add_pokebucks,
    add_pokemon,
    add_to_pokedex,
    get_trainer,
)
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, format_moves, load_species, mon_title

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #"""Мастерские команды — выдача покемонов, денег, побед/поражений."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    MAX_PARTY_SIZE,
    add_pokebucks,
    add_pokemon,
    add_to_pokedex,
    get_trainer,
    inc_losses,
    inc_wins,
)
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, format_moves, load_species, mon_title

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                              ПРОВЕРКА ПРАВ                                  #
# --------------------------------------------------------------------------- #

def _master_role_id() -> int:
    raw = os.getenv("MASTER_ROLE_ID", "").strip()
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def is_master():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        role_id = _master_role_id()
        if role_id == 0:
            return False
        return any(r.id == role_id for r in interaction.user.roles)

    return app_commands.check(predicate)


# --------------------------------------------------------------------------- #
#                              АВТОДОПОЛНЕНИЕ                                 #
# --------------------------------------------------------------------------- #

async def _species_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Подсказки по названиям покемонов. Работает и на русском, и на английском."""
    try:
        index = await pokeapi_client.ensure_name_index()
    except PokeAPIError:
        return []

    cur = current.strip().lower().lstrip("#")
    out: list[app_commands.Choice[str]] = []

    POPULAR = [
        ("пикачу", "Пикачу"),
        ("чармандер", "Чармандер"),
        ("чаризард", "Чаризард"),
        ("бульбазавр", "Бульбазавр"),
        ("сквиртл", "Сквиртл"),
        ("иви", "Иви"),
        ("мьюту", "Мьюту"),
        ("джирачи", "Джирачи"),
        ("лукарио", "Лукарио"),
        ("гардевуар", "Гардевуар"),
    ]
    seen_ids: set[int] = set()
    if not cur:
        for key, label in POPULAR:
            sid = index.get(key)
            if sid and sid not in seen_ids:
                out.append(
                    app_commands.Choice(name=f"#{sid:04d} {label}", value=str(sid))
                )
                seen_ids.add(sid)
        if len(out) >= 25:
            return out

    for name, sid in index.items():
        if sid in seen_ids:
            continue
        if not cur or cur in name:
            out.append(
                app_commands.Choice(
                    name=f"#{sid:04d} {name.title()}"[:100], value=str(sid)
                )
            )
            seen_ids.add(sid)
        if len(out) >= 25:
            break
    return out


# --------------------------------------------------------------------------- #
#                                  COG                                        #
# --------------------------------------------------------------------------- #

class Admin(commands.Cog):
    """Команды для мастеров игры."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        for cmd in (
            self.give_pokemon,
            self.give_money,
            self.gm_win,
            self.gm_lose,
        ):
            cmd.error(self._on_error)

    async def _on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "🚫 Эта команда только для мастеров игры."
        else:
            log.exception("Ошибка в мастерской команде", exc_info=error)
            msg = "⚠️ Внутренняя ошибка. Смотрите логи."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ GIVE POKEMON

    @app_commands.command(
        name="give",
        description="[Мастер] Выдать игроку покемона (в команду, если есть место, иначе в ПК)",
    )
    @app_commands.describe(
        user="Кому выдать покемона",
        species="Вид: имя (пикачу / Pikachu) или номер (#25). Начните печатать — подскажу.",
        level="Уровень (1–100, по умолчанию 5)",
        nickname="Кличка (необязательно)",
        moves="Атаки через запятую, 1–4 (не укажете — 4 случайные)",
    )
    @is_master()
    @app_commands.autocomplete(species=_species_autocomplete)
    async def give_pokemon(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        species: str,
        level: app_commands.Range[int, 1, 100] = 5,
        nickname: Optional[str] = None,
        moves: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(
                f"❌ {e}\nМожно вводить русское имя (Пикачу), английское (Pikachu) или номер (#25).",
                ephemeral=True,
            )
            return

        gender = await pokeapi_client.roll_gender(data["id"])

        if moves:
            parsed = [
                m.strip().lower().replace(" ", "-")
                for m in moves.split(",")
                if m.strip()
            ]
            if not (1 <= len(parsed) <= 4):
                await interaction.followup.send(
                    "❌ Укажите от 1 до 4 атак через запятую. Пример: `thunderbolt, quick-attack`",
                    ephemeral=True,
                )
                return
            final_moves = parsed
        else:
            final_moves = pokeapi_client.pick_random_moves(data, 4)

        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send(
                "❌ Кличка не должна быть длиннее 20 символов.", ephemeral=True
            )
            return

        trainer = await get_trainer(user.id)
        has_party_slot = len(trainer["party"]) < MAX_PARTY_SIZE
        to_party = has_party_slot

        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": nick,
            "level": int(level),
            "gender": gender,
            "moves": final_moves,
        }
        added_to_party = await add_pokemon(user.id, mon, to_party=to_party)
        await add_to_pokedex(user.id, data["id"])

        species_data = await load_species([mon])
        title = mon_title(mon, species_data)
        place = "команду" if added_to_party else "ПК"

        embed = discord.Embed(
            title="✅ Покемон выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Покемон:** {title}\n"
                f"**Уровень:** {mon['level']}\n"
                f"**Атаки:** {format_moves(final_moves)}\n"
                f"**ID:** `{mon['instance_id']}`\n"
                f"**Место:** {place}"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await user.send(
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']})!\n"
                f"Он {'в команде' if added_to_party else 'лежит в ПК'}."
            )
        except discord.Forbidden:
            pass

    # ------------------------------------------------------------------ GIVE MONEY

    @app_commands.command(
        name="give_money",
        description="[Мастер] Выдать или забрать Pokébucks у игрока",
    )
    @app_commands.describe(
        user="Кому выдать (или у кого забрать)",
        amount="Сумма. Положительная — выдать, отрицательная — забрать.",
    )
    @is_master()
    async def give_money(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ) -> None:
        new_balance = await add_pokebucks(user.id, int(amount))
        sign = "+" if amount >= 0 else ""
        embed = discord.Embed(
            title="💰 Pokébucks обновлены",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Изменение:** {sign}{amount:,} PB\n"
                f"**Текущий баланс:** {new_balance:,} PB"
            ),
            color=discord.Color.gold() if amount >= 0 else discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ WINS / LOSSES

    @app_commands.command(
        name="gm_win",
        description="[Мастер] Начислить игроку победы",
    )
    @app_commands.describe(
        user="Кому начислить",
        amount="Сколько побед (по умолчанию 1)",
    )
    @is_master()
    async def gm_win(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        await inc_wins(user.id, int(amount))
        t = await get_trainer(user.id)
        embed = discord.Embed(
            title="🏆 Победы засчитаны",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Начислено:** +{amount} побед\n"
                f"**Всего побед:** {t['wins']}\n"
                f"**Поражений:** {t['losses']}"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="gm_lose",
        description="[Мастер] Начислить игроку поражения",
    )
    @app_commands.describe(
        user="Кому начислить",
        amount="Сколько поражений (по умолчанию 1)",
    )
    @is_master()
    async def gm_lose(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        await inc_losses(user.id, int(amount))
        t = await get_trainer(user.id)
        embed = discord.Embed(
            title="💔 Поражения засчитаны",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Начислено:** +{amount} поражений\n"
                f"**Побед:** {t['wins']}\n"
                f"**Всего поражений:** {t['losses']}"
            ),
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
#                              ПРОВЕРКА ПРАВ                                  #
# --------------------------------------------------------------------------- #

def _master_role_id() -> int:
    raw = os.getenv("MASTER_ROLE_ID", "").strip()
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def is_master():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        role_id = _master_role_id()
        if role_id == 0:
            return False
        return any(r.id == role_id for r in interaction.user.roles)

    return app_commands.check(predicate)


# --------------------------------------------------------------------------- #
#                              АВТОДОПОЛНЕНИЕ                                 #
# --------------------------------------------------------------------------- #

async def _species_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Подсказки по названиям покемонов. Работает и на русском, и на английском."""
    try:
        index = await pokeapi_client.ensure_name_index()
    except PokeAPIError:
        return []

    cur = current.strip().lower().lstrip("#")
    out: list[app_commands.Choice[str]] = []

    # Популярные покемоны сверху — чтобы мастеру было удобно
    POPULAR = [
        ("пикачу", "Пикачу"),
        ("чармандер", "Чармандер"),
        ("чаризард", "Чаризард"),
        ("бульбазавр", "Бульбазавр"),
        ("сквиртл", "Сквиртл"),
        ("иви", "Иви"),
        ("мьюту", "Мьюту"),
        ("джирачи", "Джирачи"),
        ("лукарио", "Лукарио"),
        ("гардевуар", "Гардевуар"),
    ]
    seen_ids: set[int] = set()
    if not cur:
        for key, label in POPULAR:
            sid = index.get(key)
            if sid and sid not in seen_ids:
                out.append(app_commands.Choice(name=f"#{sid:04d} {label}", value=str(sid)))
                seen_ids.add(sid)
        if len(out) >= 25:
            return out

    for name, sid in index.items():
        if sid in seen_ids:
            continue
        if not cur or cur in name:
            out.append(app_commands.Choice(name=f"#{sid:04d} {name.title()}"[:100], value=str(sid)))
            seen_ids.add(sid)
        if len(out) >= 25:
            break
    return out


# --------------------------------------------------------------------------- #
#                                  COG                                        #
# --------------------------------------------------------------------------- #

class Admin(commands.Cog):
    """Команды для мастеров игры."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.give_pokemon.error(self._on_error)
        self.give_money.error(self._on_error)

    async def _on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "🚫 Эта команда только для мастеров игры."
        else:
            log.exception("Ошибка в мастерской команде", exc_info=error)
            msg = "⚠️ Внутренняя ошибка. Смотрите логи."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ GIVE POKEMON

    @app_commands.command(
        name="give",
        description="[Мастер] Выдать игроку покемона (в команду, если есть место, иначе в ПК)",
    )
    @app_commands.describe(
        user="Кому выдать покемона",
        species="Вид: имя (пикачу / Pikachu) или номер (#25). Начните печатать — подскажу.",
        level="Уровень (1–100, по умолчанию 5)",
        nickname="Кличка (необязательно)",
        moves="Атаки через запятую, 1–4 (не укажете — 4 случайные)",
    )
    @is_master()
    @app_commands.autocomplete(species=_species_autocomplete)
    async def give_pokemon(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        species: str,
        level: app_commands.Range[int, 1, 100] = 5,
        nickname: Optional[str] = None,
        moves: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(
                f"❌ {e}\nМожно вводить русское имя (Пикачу), английское (Pikachu) или номер (#25).",
                ephemeral=True,
            )
            return

        gender = await pokeapi_client.roll_gender(data["id"])

        if moves:
            parsed = [
                m.strip().lower().replace(" ", "-")
                for m in moves.split(",")
                if m.strip()
            ]
            if not (1 <= len(parsed) <= 4):
                await interaction.followup.send(
                    "❌ Укажите от 1 до 4 атак через запятую. Пример: `thunderbolt, quick-attack`",
                    ephemeral=True,
                )
                return
            final_moves = parsed
        else:
            final_moves = pokeapi_client.pick_random_moves(data, 4)

        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send(
                "❌ Кличка не должна быть длиннее 20 символов.", ephemeral=True
            )
            return

        trainer = await get_trainer(user.id)
        has_party_slot = len(trainer["party"]) < MAX_PARTY_SIZE
        to_party = has_party_slot

        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": nick,
            "level": int(level),
            "gender": gender,
            "moves": final_moves,
        }
        added_to_party = await add_pokemon(user.id, mon, to_party=to_party)
        await add_to_pokedex(user.id, data["id"])

        species_data = await load_species([mon])
        title = mon_title(mon, species_data)
        place = "команду" if added_to_party else "ПК"

        embed = discord.Embed(
            title="✅ Покемон выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Покемон:** {title}\n"
                f"**Уровень:** {mon['level']}\n"
                f"**Атаки:** {format_moves(final_moves)}\n"
                f"**ID:** `{mon['instance_id']}`\n"
                f"**Место:** {place}"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await user.send(
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']})!\n"
                f"Он {'в команде' if added_to_party else 'лежит в ПК'}."
            )
        except discord.Forbidden:
            pass

    # ------------------------------------------------------------------ GIVE MONEY

    @app_commands.command(
        name="give_money",
        description="[Мастер] Выдать или забрать Pokébucks у игрока",
    )
    @app_commands.describe(
        user="Кому выдать (или у кого забрать)",
        amount="Сумма. Положительная — выдать, отрицательная — забрать.",
    )
    @is_master()
    async def give_money(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ) -> None:
        uid = user.id
        new_balance = await add_pokebucks(uid, int(amount))
        sign = "+" if amount >= 0 else ""

        embed = discord.Embed(
            title="💰 Pokébucks обновлены",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Изменение:** {sign}{amount:,} PB\n"
                f"**Текущий баланс:** {new_balance:,} PB"
            ),
            color=discord.Color.gold() if amount >= 0 else discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
