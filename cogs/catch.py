"""Ловля покемонов: /catch — простой бросок по шансу покебола."""
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
    get_trainer,
    take_item,
)
from pokeapi_client import PokeAPIError
from utils import GENDER_EMOJI, format_moves, format_types, load_species

log = logging.getLogger(__name__)


# ==========================================================================
#  ШАНСЫ ПОИМКИ — фиксированные, без условий
# ==========================================================================
BALL_CHANCE: dict[str, float] = {
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

# 20 вариантов в подсказках (лимит Discord — 25)
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
        description="Поймать покемона (шанс зависит от покебола)",
    )
    @app_commands.describe(
        ball="Какой покебол использовать (из инвентаря персонажа)",
    )
    @app_commands.choices(ball=BALL_CHOICES)
    async def catch(
        self,
        interaction: discord.Interaction,
        ball: Optional[app_commands.Choice[str]] = None,
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

        # Проверка инвентаря
        qty = await get_item_qty(uid, ball_key)
        if qty < 1:
            await interaction.followup.send(
                f"❌ У **{profile['name']}** нет **{BALL_NAMES.get(ball_key, ball_key)}** "
                f"в инвентаре.",
                ephemeral=True,
            )
            return

        # Списываем покебол
        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол.", ephemeral=True
            )
            return

        # Бросок
        chance = BALL_CHANCE.get(ball_key, 25.0)
        success = random.randint(1, 100) <= round(chance)

        if success:
            # Случайный покемон из Покедекса
            try:
                species_id = random.randint(1, 1025)
                data = await pokeapi_client.get_pokemon(species_id)
                gender = await pokeapi_client.roll_gender(data["id"])
            except PokeAPIError as e:
                await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
                return

            level = random.randint(2, 15)
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

            name = data["name"]
            embed = discord.Embed(
                title=f"🎉 Поймал: {name}!",
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
