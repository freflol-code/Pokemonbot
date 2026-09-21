"""Заглушка. Тикеты отключены."""
from discord.ext import commands


class Tickets(commands.Cog):
    """Пустой cog — не используется."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))