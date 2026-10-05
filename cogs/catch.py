"""Ловля покемонов: /catch — условия вводишь, результат видишь."""
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import get_active_profile, get_item_qty, get_trainer, take_item
from pokeapi_client import PokeAPIError
from pokemon_rarity import (
    COMMON,
    RARITY_CATCH_MULTIPLIER,
    RARITY_EMOJI,
    RARITY_LABEL,
    get_rarity,
)

log = logging.getLogger(__name__)


# ==========================================================================
#  ШАНСЫ ПОКЕБОЛОВ
# ==========================================================================
BALL_BASE_CHANCE: dict[str, float] = {
    "pokeball": 25.0,
    "greatball": 50.0,
    "ultraball": 70.0,
    "masterball": 100.0,
    # ... остальные — как было ...
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

# Шары, которые игнорируют редкость (ловят кого угодно)
GUARANTEED_BALLS: frozenset[str] = frozenset({
    "masterball", "cherish_ball", "park_ball", "origin_ball", "gs_ball",
})

# ... BALL_NAMES, CATCHABLE_BALLS, BALL_CHOICES, STATUS_CHOICES,
#     STATUS_MULTIPLIER, _is_night — оставить как было ...


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
    rarity: str = COMMON,
) -> float:
    """Возвращает итоговый шанс (0–100)."""
    # Гарантированные шары ловят всех без исключения
    if ball_key in GUARANTEED_BALLS:
        return 100.0

    base = BALL_BASE_CHANCE.get(ball_key, 25.0)

    # --- Контекстные покеболы ---
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

    # --- Состояние ---
    if is_badly_wounded:
        base += 25.0
    elif is_wounded:
        base += 15.0

    # --- Статус ---
    status_mult = STATUS_MULTIPLIER.get(status, 1.0)
    base = base * status_mult

    # --- Редкость ---
    rarity_mult = RARITY_CATCH_MULTIPLIER.get(rarity, 1.0)
    base *= rarity_mult

    return max(1.0, min(100.0, base))


class Catch(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="catch", description="Ловля покемона")
    @app_commands.describe(
        ball="Покебол из инвентаря персонажа",
        status="Статус покемона (Сон/Заморозка ×2.5, Паралич/Ожог/Яд ×1.5)",
        wounded="Покемон ранен? (+15%)",
        badly_wounded="Сильно ранен? (+25%)",
        underwater="Под водой (для Dive Ball)?",
        cave="В пещере (для Dusk Ball)?",
        turn="Номер хода (для Timer/Quick Ball)",
    )
    @app_commands.choices(ball=BALL_CHOICES, status=STATUS_CHOICES)
    async def catch(
        self,
        interaction: discord.Interaction,
        ball: Optional[app_commands.Choice[str]] = None,
        status: Optional[app_commands.Choice[str]] = None,
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
        status_key = status.value if status else "none"

        qty = await get_item_qty(uid, ball_key)
        if qty < 1:
            await interaction.followup.send(
                f"❌ Нет **{BALL_NAMES.get(ball_key, ball_key)}** в инвентаре.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------- #
        #  Определяем покемона и его редкость
        # ---------------------------------------------------------------- #
        species_id = 0
        species_types: list[str] = []
        data: dict = {}
        try:
            species_id = random.randint(1, 1025)
            data = await pokeapi_client.get_pokemon(species_id)
            species_types = data.get("types", [])
        except PokeAPIError:
            log.warning("PokéAPI недоступен — играем без бонусов к типам")
            species_id = 0
            species_types = []
            data = {}

        rarity = get_rarity(species_id)
        level = random.randint(2, 15)

        # Repeat Ball: вид уже в покедексе?
        trainer = await get_trainer(uid)
        already_caught = species_id in trainer.get("pokedex_known", [])

        chance = _chance_for_ball(
            ball_key,
            species_id=species_id,
            species_types=species_types,
            level=level,
            is_wounded=wounded,
            is_badly_wounded=badly_wounded,
            status=status_key,
            is_night=_is_night(),
            is_cave=cave,
            is_underwater=underwater,
            turn_number=int(turn),
            already_caught=already_caught,
            rarity=rarity,
        )

        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол.", ephemeral=True
            )
            return

        roll = random.randint(1, 100)
        success = roll <= round(chance)

        # ---------------------------------------------------------------- #
        #  Эмбед
        # ---------------------------------------------------------------- #
        mon_name = (data.get("name") or "Неизвестный покемон").title()
        rarity_emoji = RARITY_EMOJI.get(rarity, "⚪")
        rarity_label = RARITY_LABEL.get(rarity, rarity)

        description = (
            f"{rarity_emoji} **{mon_name}** — {rarity_label}\n"
            f"🎚️ Уровень: **{level}**\n"
            f"🎯 Шанс поимки: **{chance:.1f}%** (бросок: {roll})\n"
            f"🎒 Потрачено: **{BALL_NAMES.get(ball_key, ball_key)}** ×1"
        )

        embed = discord.Embed(
            title="🎉 Поймал!" if success else "💨 Не поймал",
            description=description,
            color=(
                discord.Color.green() if success
                else discord.Color.dark_red()
            ),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        elif data.get("sprite"):
            embed.set_thumbnail(url=data["sprite"])

        embed.set_footer(text=f"Осталось {BALL_NAMES.get(ball_key, ball_key)}: {qty - 1}")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
