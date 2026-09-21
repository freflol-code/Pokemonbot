"""Ловля покемонов: /catch с условиями, но чистым выводом."""
import logging
import random
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    add_pokemon,
    add_to_pokedex,
    get_active_profile,
    get_item_qty,
    take_item,
)
from pokeapi_client import PokeAPIError
from utils import GENDER_EMOJI, format_moves, format_types

log = logging.getLogger(__name__)


# ==========================================================================
#  БАЗОВЫЕ ШАНСЫ ПОКЕБОЛОВ
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

# 20 вариантов для подсказок (лимит Discord — 25)
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
    is_night: bool,
    is_cave: bool,
    is_underwater: bool,
    turn_number: int,
    already_caught: bool,
) -> float:
    """Возвращает итоговый шанс (0–100). Без списка причин — только цифра."""
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
    # heal_ball / luxury_ball — без бонуса к шансу

    # --- Апокорновые ---
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

    # --- Legends: Arceus ---
    elif ball_key == "dream_ball":
        pass  # условный
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

    # --- Модификаторы состояния ---
    if is_badly_wounded:
        base += 25.0
    elif is_wounded:
        base += 15.0

    return max(5.0, min(100.0, base))


class Catch(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="catch",
        description="Поймать покемона (шанс зависит от покебола и условий)",
    )
    @app_commands.describe(
        ball="Какой покебол использовать (из инвентаря персонажа)",
        wounded="Покемон ранен? (+15%)",
        badly_wounded="Покемон сильно ранен? (+25%)",
        underwater="Ловля под водой (для Dive Ball)?",
        cave="Ловля в пещере (для Dusk Ball)?",
        turn="Номер хода боя (для Timer/Quick Ball)",
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
                "❌ У вас нет активного персонажа. Создайте: /new_profile",
                ephemeral=True,
            )
            return

        if profile["profile_type"] == "pokemon":
            await interaction.followup.send(
                f"❌ **{profile['name']}** — это покемон. Покемоны не ловят покемонов.",
                ephemeral=True,
            )
            return

        ball_key = ball.value if ball else "pokeball"

        qty = await get_item_qty(uid, ball_key)
        if qty < 1:
            await interaction.followup.send(
                f"❌ У **{profile['name']}** нет **{BALL_NAMES.get(ball_key, ball_key)}** "
                f"в инвентаре.",
                ephemeral=True,
            )
            return

        # Случайный покемон
        try:
            species_id = random.randint(1, 1025)
            data = await pokeapi_client.get_pokemon(species_id)
            gender = await pokeapi_client.roll_gender(data["id"])
        except PokeAPIError as e:
            await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
            return

        level = random.randint(2, 15)

        # Проверка «уже пойман» для Repeat Ball
        from database import get_trainer
        trainer = await get_trainer(uid)
        already_caught = data["id"] in trainer.get("pokedex_known", [])

        # Расчёт шанса
        chance = _chance_for_ball(
            ball_key,
            species_id=data["id"],
            species_types=data["types"],
            level=level,
            is_wounded=wounded,
            is_badly_wounded=badly_wounded,
            is_night=_is_night(),
            is_cave=cave,
            is_underwater=underwater,
            turn_number=int(turn),
            already_caught=already_caught,
        )

        # Списываем покебол
        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол.", ephemeral=True
            )
            return

        # Бросок
        success = random.randint(1, 100) <= round(chance)

        if success:
            mon = {
                "instance_id": uuid.uuid4().hex[:8],
                "species_id": data["id"],
                "nickname": None,
                "level": level,
                "gender": gender,
                "moves": pokeapi_client.pick_random_moves(data, 4),
                "ability": pokeapi_client.pick_random_ability(data),
            }
            await add_pokemon(uid, mon, to_party=False)
            is_new = await add_to_pokedex(uid, data["id"])

            embed = discord.Embed(
                title=f"🎉 Поймал: {data['name']}!",
                description=(
                    f"**Персонаж:** {profile['name']}\n"
                    f"**Покебол:** {BALL_NAMES[ball_key]}\n\n"
                    f"Уровень: **{level}** {GENDER_EMOJI.get(gender, '')}\n"
                    f"Тип: {format_types(data['types'])}\n"
                    f"Атаки: {format_moves(mon['moves'])}\n"
                    f"ID: `{mon['instance_id']}`"
                    + ("\n\n📖 **Новый вид в Покедексе!**" if is_new else "")
                ),
                color=discord.Color.green(),
            )
            if data.get("artwork"):
                embed.set_thumbnail(url=data["artwork"])
            embed.set_footer(text=f"{BALL_NAMES[ball_key]} осталось: {qty - 1}")
        else:
            embed = discord.Embed(
                title="❌ Не поймал",
                description=(
                    f"**Персонаж:** {profile['name']}\n"
                    f"**Покебол:** {BALL_NAMES[ball_key]}\n\n"
                    f"Покемон вырвался и сбежал."
                ),
                color=discord.Color.dark_red(),
            )
            embed.set_footer(text=f"{BALL_NAMES[ball_key]} осталось: {qty - 1}")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
