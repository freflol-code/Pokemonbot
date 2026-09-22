"""Ловля покемонов: /catch — условия вводишь, результат видишь."""
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

# Статусы: высокий бонус ×2.5, низкий ×1.5
STATUS_CHOICES = [
    app_commands.Choice(name="💤 Сон", value="sleep"),
    app_commands.Choice(name="❄️ Заморозка", value="freeze"),
    app_commands.Choice(name="🟨 Паралич", value="paralysis"),
    app_commands.Choice(name="🟥 Ожог", value="burn"),
    app_commands.Choice(name="🟪 Отравление", value="poison"),
    app_commands.Choice(name="— Нет статуса", value="none"),
]

STATUS_MULTIPLIER: dict[str, float] = {
    "sleep": 2.5,
    "freeze": 2.5,
    "paralysis": 1.5,
    "burn": 1.5,
    "poison": 1.5,
    "none": 1.0,
}


def _is_night() -> bool:
    import datetime
    hour = datetime.datetime.now().hour
    return hour >= 22 or hour < 6


def _chance_for_ball(
    ball_key: str,
    *,
    species_id: int = 0,
    species_types: list[str],
    level: int,
    is_wounded: bool,
    is_badly_wounded: bool,
    status: str,
    is_night: bool,
    is_cave: bool,
    is_underwater: bool,
    turn_number: int,
    already_caught: bool,
) -> float:
    """Возвращает итоговый шанс (0–100)."""
    base = BALL_BASE_CHANCE.get(ball_key, 25.0)

    if ball_key == "net_ball":
        if "water" in species_types or "bug" in species_types:
            base += 25.0
    elif ball_key == "dive_ball":
        if is_underwater:
            base += 25.0
    elif ball_key == "nest_ball":
        if level < 20:
            base += 25.0
    elif ball_key == "repeat_ball":
        if already_caught:
            base += 25.0
    elif ball_key == "timer_ball":
        base += min(50.0, 5.0 * turn_number)
    elif ball_key == "quick_ball":
        if turn_number == 1:
            base = 95.0
    elif ball_key == "dusk_ball":
        if is_night or is_cave:
            base += 25.0
    elif ball_key == "sport_ball":
        if "bug" in species_types:
            base += 25.0
    elif ball_key == "level_ball":
        if level >= 30:
            base += 30.0
        elif level >= 20:
            base += 20.0
    elif ball_key == "lure_ball":
        if "water" in species_types:
            base += 25.0
    elif ball_key == "moon_ball":
        if any(t in species_types for t in ("water", "psychic", "fairy", "normal")):
            base += 25.0
    elif ball_key == "friend_ball":
        base += 10.0
    elif ball_key == "love_ball":
        base += 15.0
    elif ball_key == "heavy_ball":
        if level >= 30:
            base += 20.0
    elif ball_key == "fast_ball":
        if any(t in species_types for t in ("flying", "electric")):
            base += 25.0
    elif ball_key == "beast_ball":
        if (793 <= species_id <= 799) or species_id in (803, 804, 805, 806):
            base = 95.0
    elif ball_key == "strange_ball":
        if level >= 20:
            base += 20.0
    elif ball_key == "feather_ball":
        base += 5.0
    elif ball_key == "wing_ball":
        base += 10.0
    elif ball_key == "jet_ball":
        base += 15.0
    elif ball_key == "leaden_ball":
        base += 20.0
    elif ball_key == "gigaton_ball":
        base += 30.0

    # Состояние
    if is_badly_wounded:
        base += 25.0
    elif is_wounded:
        base += 15.0

    # Статус — умножаем шанс
    status_mult = STATUS_MULTIPLIER.get(status, 1.0)
    base = base * status_mult

    return max(5.0, min(100.0, base))


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
        status="Статус покемона (Сон/Заморозка ×2.5, остальные ×1.5)",
        underwater="Под водой (для Dive Ball)?",
        cave="В пещере (для Dusk Ball)?",
        turn="Номер хода (для Timer/Quick Ball)",
    )
    @app_commands.choices(ball=BALL_CHOICES, status=STATUS_CHOICES)
    async def catch(
        self,
        interaction: discord.Interaction,
        ball: Optional[app_commands.Choice[str]] = None,
        wounded: bool = False,
        badly_wounded: bool = False,
        status: Optional[app_commands.Choice[str]] = None,
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
        status_key = status.value if status else "none"

        qty = await get_item_qty(uid, ball_key)
        if qty < 1:
            await interaction.followup.send(
                f"❌ Нет **{BALL_NAMES.get(ball_key, ball_key)}** в инвентаре.",
                ephemeral=True,
            )
            return

        # Просто для проверки — «уже пойман» не нужен, но для Repeat Ball
        # можно было бы использовать. Сейчас считаем, что вид новый.
        chance = _chance_for_ball(
            ball_key,
            species_types=[],
            level=10,
            is_wounded=wounded,
            is_badly_wounded=badly_wounded,
            status=status_key,
            is_night=_is_night(),
            is_cave=cave,
            is_underwater=underwater,
            turn_number=int(turn),
            already_caught=False,
        )

        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол.", ephemeral=True
            )
            return

        success = random.randint(1, 100) <= round(chance)

        embed = discord.Embed(
            title="🎉 Поймал!" if success else "💨 Не поймал",
            color=discord.Color.green() if success else discord.Color.dark_red(),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
