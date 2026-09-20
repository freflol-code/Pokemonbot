"""Мастерские команды — выдача покемонов."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import MAX_PARTY_SIZE, add_pokemon, add_to_pokedex, get_trainer
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
#                              АВТОДОПОЛНЕНИЯ                                 #
# --------------------------------------------------------------------------- #

async def _species_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Подсказки по названиям покемонов, начиная с первых букв."""
    try:
        index = await pokeapi_client.get_species_index()
    except PokeAPIError:
        return []
    cur = current.strip().lower().lstrip("#")
    out: list[app_commands.Choice[str]] = []
    for sid, name in index:
        if not cur or cur in name or cur == str(sid):
            pretty = name.replace("-", " ").title()
            out.append(app_commands.Choice(name=f"#{sid:04d} {pretty}", value=name))
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

    async def _on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "🚫 Эта команда только для мастеров игры."
        else:
            log.exception("Ошибка в /give", exc_info=error)
            msg = "⚠️ Внутренняя ошибка. Смотрите логи."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    @app_commands.command(
        name="give",
        description="[Мастер] Выдать игроку покемона (в команду, если есть место, иначе в ПК)",
    )
    @app_commands.describe(
        user="Кому выдать покемона",
        species="Вид: имя (pikachu) или номер (#25). Начните печатать — подскажу.",
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

        # 1. Резолвим вид покемона
        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(
                f"❌ Вид не найден: {e}\n"
                f"Попробуйте английское имя (pikachu) или номер (#25).",
                ephemeral=True,
            )
            return

        # 2. Пол — определяем по виду
        gender = await pokeapi_client.roll_gender(data["id"])

        # 3. Атаки
        if moves:
            parsed = [
                m.strip().lower().replace(" ", "-")
                for m in moves.split(",")
                if m.strip()
            ]
            if not (1 <= len(parsed) <= 4):
                await interaction.followup.send(
                    "❌ Укажите от 1 до 4 атак через запятую. "
                    "Пример: `thunderbolt, quick-attack`",
                    ephemeral=True,
                )
                return
            final_moves = parsed
        else:
            final_moves = pokeapi_client.pick_random_moves(data, 4)

        # 4. Кличка
        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send(
                "❌ Кличка не должна быть длиннее 20 символов.", ephemeral=True
            )
            return

        # 5. Определяем, куда положить: в команду (если есть место) или в ПК
        trainer = await get_trainer(user.id)
        has_party_slot = len(trainer["party"]) < MAX_PARTY_SIZE
        to_party = has_party_slot

        # 6. Собираем и сохраняем
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

        # 7. Отчёт мастеру
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

        # 8. Уведомление игроку в личку
        try:
            await user.send(
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']})!\n"
                f"Он {'в команде' if added_to_party else 'лежит в ПК'}."
            )
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
