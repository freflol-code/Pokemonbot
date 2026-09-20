"""Просмотр Покедекса тренера."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import get_trainer
from utils import EMBED_COLOR, format_types, load_species


class Pokedex(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="pokedex",
        description="Показать виды покемонов, которые у вас есть (или были выданы)",
    )
    async def pokedex(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        t = await get_trainer(interaction.user.id)
        known = sorted(t["pokedex_known"])
        embed = discord.Embed(title="📖 Покедекс", color=EMBED_COLOR)

        if not known:
            embed.description = (
                "Покедекс пуст. Покемонов выдаёт мастер игры командой `/give`."
            )
        else:
            shown = known[:20]
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
                + (" • показаны первые 20" if len(known) > 20 else "")
            )
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pokedex(bot))
