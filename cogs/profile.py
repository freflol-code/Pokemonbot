"""Профиль тренера и баланс."""
import discord
from discord import app_commands
from discord.ext import commands

from database import get_trainer
from utils import EMBED_COLOR


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="profile", description="Показать профиль тренера")
    async def profile(self, interaction: discord.Interaction) -> None:
        t = await get_trainer(interaction.user.id)
        embed = discord.Embed(
            title=f"Профиль тренера {interaction.user.display_name}", color=EMBED_COLOR
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🏆 Победы", value=str(t["wins"]))
        embed.add_field(name="💔 Поражения", value=str(t["losses"]))
        embed.add_field(name="💰 Pokébucks", value=f"{t['pokebucks']:,}")
        embed.add_field(name="📖 Известно видов", value=str(len(t["pokedex_known"])))
        embed.add_field(name="🎒 Команда", value=f"{len(t['party'])}/6")
        embed.add_field(name="🖥️ ПК", value=str(len(t["pc"])))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="balance", description="Показать баланс Pokébucks")
    async def balance(self, interaction: discord.Interaction) -> None:
        t = await get_trainer(interaction.user.id)
        embed = discord.Embed(
            title="💰 Баланс",
            description=f"У вас **{t['pokebucks']:,}** Pokébucks",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
