"""Покедекс и ловля покемонов."""
import uuid

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import POKEBALL_KEY, get_trainer, update_trainer
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, GENDER_EMOJI, format_moves, format_types, load_species

import random


class Pokedex(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pokedex", description="Показать известных покемонов")
    async def pokedex(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        t = await get_trainer(interaction.user.id)
        known = sorted(t["pokedex_known"])
        embed = discord.Embed(
            title="📖 Покедекс",
            color=EMBED_COLOR,
        )
        if not known:
            embed.description = "Покедекс пуст. Поймайте первого покемона командой /catch!"
        else:
            shown = known[:15]
            species = await load_species(shown)
            lines = []
            for sid in shown:
                d = species.get(sid)
                if d:
                    lines.append(f"`#{sid:04d}` **{d['name']}** — {format_types(d['types'])}")
                else:
                    lines.append(f"`#{sid:04d}` *(данные недоступны)*")
            embed.description = "\n".join(lines)
        embed.set_footer(
            text=f"Известно видов: {len(known)}/{pokeapi_client.MAX_POKEMON_ID}"
            + (" • показаны первые 15" if len(known) > 15 else "")
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="catch", description="Поймать случайного покемона (тратит 1 покебол)")
    async def catch(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        uid = interaction.user.id
        trainer = await get_trainer(uid)
        if trainer["inventory"].get(POKEBALL_KEY, 0) < 1:
            await interaction.followup.send(
                "❌ У вас нет покеболов. Купите их через /shop.", ephemeral=True
            )
            return

        # Сначала загружаем данные — если API недоступен, покебол не тратится
        try:
            data = await pokeapi_client.get_random_pokemon()
            gender = await pokeapi_client.roll_gender(data["id"])
        except PokeAPIError as e:
            await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
            return

        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": None,
            "level": random.randint(2, 15),
            "gender": gender,
            "moves": pokeapi_client.pick_random_moves(data),
        }
        res = await update_trainer(
            uid,
            {
                "$inc": {f"inventory.{POKEBALL_KEY}": -1},
                "$addToSet": {"pokedex_known": data["id"]},
                "$push": {"pc": mon},
            },
            {f"inventory.{POKEBALL_KEY}": {"$gte": 1}},
        )
        if res.matched_count == 0:
            await interaction.followup.send("❌ У вас закончились покеболы.", ephemeral=True)
            return

        is_new = data["id"] not in trainer["pokedex_known"]
        embed = discord.Embed(
            title=f"🎉 Вы поймали {data['name']}!",
            description=(
                f"Уровень: **{mon['level']}** {GENDER_EMOJI[gender]}\n"
                f"Тип: {format_types(data['types'])}\n"
                f"Атаки: {format_moves(mon['moves'])}\n"
                f"ID: `{mon['instance_id']}`\n\n"
                + ("📖 **Новый вид в Покедексе!**\n" if is_new else "")
                + "Покемон отправлен в ПК. Переместите в команду: /team_add"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        embed.set_footer(
            text=f"Покеболов осталось: {trainer['inventory'].get(POKEBALL_KEY, 1) - 1}"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pokedex(bot))
