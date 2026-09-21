"""Ловля покемонов: /catch — только результат броска."""
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import get_active_profile, get_item_qty, take_item

log = logging.getLogger(__name__)


# ==========================================================================
#  ШАНСЫ ПОКЕБОЛОВ
# ==========================================================================
BALL_BASE_CHANCE: dict[str, float] = {
    "pokeball": 25.0,
    "greatball": 50.0,
    "ultraball": 70.0,
    "masterball": 100.0,
    "net_ball": 25.0,
    "dive_ball": 25.0,
    "nest_ball": 25.0,
    "repeat_ball": 25.0,
    "timer_ball": 25.0,
    "heal_ball": 25.0,
    "luxury_ball": 25.0,
    "quick_ball": 25.0,
    "dusk_ball": 25.0,
    "premier_ball": 25.0,
    "cherish_ball": 100.0,
    "park_ball": 100.0,
    "sport_ball": 25.0,
    "origin_ball": 100.0,
    "gs_ball": 100.0,
    "strange_ball": 25.0,
    "dream_ball": 25.0,
    "level_ball": 25.0,
    "lure_ball": 25.0,
    "moon_ball": 25.0,
    "friend_ball": 25.0,
    "love_ball": 25.0,
    "heavy_ball": 25.0,
    "fast_ball": 25.0,
    "feather_ball": 25.0,
    "wing_ball": 25.0,
    "jet_ball": 25.0,
    "leaden_ball": 25.0,
    "gigaton_ball": 25.0,
    "beast_ball": 25.0,
}

BALL_NAMES: dict[str, str] = {
    "pokeball": "Покебол",
    "greatball": "Грейтбол",
    "ultraball": "Ультрабол",
    "masterball": "Мастербол",
    "net_ball": "Нетбол",
    "dive_ball": "Дайвбол",
    "nest_ball": "Нестбол",
    "repeat_ball": "Репитбол",
    "timer_ball": "Таймербол",
    "heal_ball": "Хилбол",
    "luxury_ball": "Люксбол",
    "quick_ball": "Квикбол",
    "dusk_ball": "Дускбол",
    "premier_ball": "Премьер-болл",
    "cherish_ball": "Чериш-болл",
    "park_ball": "Парк-болл",
    "sport_ball": "Спорт-болл",
    "level_ball": "Левел-болл",
    "lure_ball": "Люр-болл",
    "moon_ball": "Мун-болл",
    "friend_ball": "Френд-болл",
    "love_ball": "Лав-болл",
    "heavy_ball": "Хэви-болл",
    "fast_ball": "Фаст-болл",
    "dream_ball": "Дрим-болл",
    "beast_ball": "Бист-болл",
    "origin_ball": "Ориджин-болл",
    "gs_ball": "GS-болл",
    "strange_ball": "Стрэндж-болл",
    "feather_ball": "Фезер-болл",
    "wing_ball": "Винг-болл",
    "jet_ball": "Джет-болл",
    "leaden_ball": "Леден-болл",
    "gigaton_ball": "Гигатон-болл",
}

CATCHABLE_BALLS = [
    "pokeball", "greatball", "ultraball",
    "net_ball", "dive_ball", "nest_ball", "repeat_ball",
    "timer_ball", "heal_ball", "luxury_ball", "quick_ball", "dusk_ball",
    "premier_ball", "sport_ball", "level_ball", "lure_ball",
    "moon_ball", "friend_ball", "love_ball", "heavy_ball",
]

BALL_CHOICES = [
    app_commands.Choice(name=BALL_NAMES[k], value=k) for k in CATCHABLE_BALLS
]


class Catch(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="catch",
        description="Ловля покемона",
    )
    @app_commands.describe(
        ball="Покебол из инвентаря персонажа",
        wounded="Покемон ранен?",
        badly_wounded="Сильно ранен?",
        underwater="Под водой (для Dive Ball)?",
        cave="В пещере (для Dusk Ball)?",
        turn="Номер хода (для Timer/Quick Ball)",
    )
    @app_commands.choices(ball=BALL_CHOICES)
    async def catch(
        self,
        interaction: discord.Interaction,
        ball: Optional[app_commands.Choice[str]] = None,
        wounded: bool = False,
        badly_wounded: bool = False,
        underwater: bool = False,
        cave: bool = False,
        turn: app_commands.Range[int, 1, 50] = 1,
    ) -> None:
        await interaction.response.defer()

        uid = interaction.user.id
        profile = await get_active_profile(uid)
        if not profile:
            await interaction.followup.send(
                "❌ У вас нет активного персонажа.", ephemeral=True
            )
            return

        if profile["profile_type"] == "pokemon":
            await interaction.followup.send(
                f"❌ **{profile['name']}** — покемон.", ephemeral=True
            )
            return

        ball_key = ball.value if ball else "pokeball"

        qty = await get_item_qty(uid, ball_key)
        if qty < 1:
            await interaction.followup.send(
                f"❌ Нет **{BALL_NAMES.get(ball_key, ball_key)}** в инвентаре.",
                ephemeral=True,
            )
            return

        # Базовый шанс + модификаторы условий
        chance = BALL_BASE_CHANCE.get(ball_key, 25.0)

        # Timer Ball: растёт с ходом
        if ball_key == "timer_ball":
            chance += min(50.0, 5.0 * turn)

        # Quick Ball: 95% на первом ходу
        if ball_key == "quick_ball" and turn == 1:
            chance = 95.0

        # Dusk Ball: +25% ночью или в пещере
        if ball_key == "dusk_ball" and cave:
            chance += 25.0
        elif ball_key == "dusk_ball":
            import datetime
            hour = datetime.datetime.now().hour
            if hour >= 22 or hour < 6:
                chance += 25.0

        # Dive Ball: +25% под водой
        if ball_key == "dive_ball" and underwater:
            chance += 25.0

        # Nest Ball: +25% если уровень < 20 (не проверяем, доверяем мастеру)

        # Состояние покемона
        if badly_wounded:
            chance += 25.0
        elif wounded:
            chance += 15.0

        chance = max(5.0, min(100.0, chance))

        # Списываем покебол
        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол.", ephemeral=True
            )
            return

        # Бросок
        success = random.randint(1, 100) <= round(chance)

        embed = discord.Embed(
            title="🎉 Поймал!" if success else "💨 Не поймал",
            color=discord.Color.green() if success else discord.Color.dark_red(),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
