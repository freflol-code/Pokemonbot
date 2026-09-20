"""Покедекс и ловля покемонов."""
from __future__ import annotations

import random
import uuid

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from data.locations import get_location, location_title
from database import (
    POKEBALL_KEY,
    add_pokemon,
    add_to_pokedex,
    get_trainer,
    take_item,
)
from pokeapi_client import PokeAPIError
from utils import (
    EMBED_COLOR,
    GENDER_EMOJI,
    format_moves,
    format_types,
    load_species,
)


class Pokedex(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pokedex", description="Показать известных покемонов")
    async def pokedex(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        t = await get_trainer(interaction.user.id)
        known = sorted(t["pokedex_known"])
        embed = discord.Embed(title="📖 Покедекс", color=EMBED_COLOR)
        if not known:
            embed.description = (
                "Покедекс пуст. Поймайте первого покемона командой /catch!"
            )
        else:
            shown = known[:15]
            species = await load_species(shown)
            lines = []
            for sid in shown:
                d = species.get(sid)
                if d:
                    lines.append(
                        f"`#{sid:04d}` **{d['name']}** — {format_types(d['types'])}"
                    )
                else:
                    lines.append(f"`#{sid:04d}` *(данные недоступны)*")
            embed.description = "\n".join(lines)
        embed.set_footer(
            text=(
                f"Известно видов: {len(known)}/{pokeapi_client.MAX_POKEMON_ID}"
                + (" • показаны первые 15" if len(known) > 15 else "")
            )
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="catch",
        description="Поймать покемона, обитающего в вашей локации (тратит 1 покебол)",
    )
    async def catch(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        uid = interaction.user.id
        trainer = await get_trainer(uid)
        loc = get_location(trainer.get("location"))

        # 1. Есть ли покеболы?
        if trainer["inventory"].get(POKEBALL_KEY, 0) < 1:
            await interaction.followup.send(
                "❌ У вас нет покеболов. Купите их через /shop.", ephemeral=True
            )
            return

        # 2. Данные покемона из локации (до списания ресурса)
        try:
            data = await pokeapi_client.get_wild_pokemon_for_location(
                loc.get("encounters")
            )
            gender = await pokeapi_client.roll_gender(data["id"])
        except PokeAPIError as e:
            await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
            return

        # 3. Атомарно списываем покебол — если не вышло, откат
        taken = await take_item(uid, POKEBALL_KEY, 1)
        if not taken:
            await interaction.followup.send(
                "❌ У вас закончились покеболы.", ephemeral=True
            )
            return

        # 4. Собираем и сохраняем покемона
        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": None,
            "level": random.randint(2, 15),
            "gender": gender,
            "moves": pokeapi_client.pick_random_moves(data),
        }
        await add_pokemon(uid, mon, to_party=False)
        is_new = await add_to_pokedex(uid, data["id"])

        # 5. Красивый отчёт
        trainer_after = await get_trainer(uid)
        balls_left = trainer_after["inventory"].get(POKEBALL_KEY, 0)
        embed = discord.Embed(
            title=f"🎉 Вы поймали {data['name']}!",
            description=(
                f"Локация: {location_title(trainer.get('location'))}\n"
                f"Уровень: **{mon['level']}** {GENDER_EMOJI.get(gender, '')}\n"
                f"Тип: {format_types(data['types'])}\n"
                f"Атаки: {format_moves(mon['moves'])}\n"
                f"ID: `{mon['instance_id']}`\n\n"
                + ("📖 **Новый вид в Покедексе!**\n" if is_new else "")
                + "Покемон отправлен в ПК. Переместить в команду: /team_add"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        embed.set_footer(text=f"Покеболов осталось: {balls_left}")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pokedex(bot))
