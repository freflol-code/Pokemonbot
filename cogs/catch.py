"""Ловля покемонов: /catch с шансами от покебола и условий."""
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
from utils import (
    EMBED_COLOR,
    GENDER_EMOJI,
    format_moves,
    format_types,
    load_species,
)

# Пытаемся загрузить локации, если файл залит. Иначе — fallback.
try:
    from data.locations import get_location  # type: ignore
except ImportError:
    def get_location(loc_id):  # type: ignore
        """Все локации одинаковые, если data/locations.py не залит."""
        return {"encounters": None}

log = logging.getLogger(__name__)


# ==========================================================================
#  ШАНСЫ ПОИМКИ ПО ПОКЕБОЛАМ
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

# Discord разрешает максимум 25 вариантов в choices.
# Остальные 8 покеболов (origin, gs, strange, feather, wing, jet, leaden, gigaton)
# остаются в ITEMS — мастер может выдать через /give_item.
CATCHABLE_BALLS = [
    "pokeball", "greatball", "ultraball",
    "net_ball", "dive_ball", "nest_ball", "repeat_ball",
    "timer_ball", "heal_ball", "luxury_ball", "quick_ball", "dusk_ball",
    "premier_ball", "sport_ball", "level_ball", "lure_ball",
    "moon_ball", "friend_ball", "love_ball", "heavy_ball", "fast_ball",
    "dream_ball", "beast_ball", "cherish_ball", "park_ball",
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
) -> tuple[float, list[str]]:
    base = BALL_BASE_CHANCE.get(ball_key, 25.0)
    reasons: list[str] = []

    if ball_key == "net_ball":
        if "water" in species_types or "bug" in species_types:
            base += 25.0
            reasons.append("✅ Net Ball: тип Water/Bug (+25%)")
        else:
            reasons.append("❌ Net Ball: не Water/Bug")
    elif ball_key == "dive_ball":
        if is_underwater:
            base += 25.0
            reasons.append("✅ Dive Ball: под водой (+25%)")
        else:
            reasons.append("❌ Dive Ball: не под водой")
    elif ball_key == "nest_ball":
        if level < 20:
            base += 25.0
            reasons.append(f"✅ Nest Ball: Ур. {level} < 20 (+25%)")
        else:
            reasons.append("❌ Nest Ball: Ур. ≥ 20")
    elif ball_key == "repeat_ball":
        if already_caught:
            base += 25.0
            reasons.append("✅ Repeat Ball: вид уже пойман (+25%)")
        else:
            reasons.append("❌ Repeat Ball: вид не пойман ранее")
    elif ball_key == "timer_ball":
        bonus = min(50.0, 5.0 * turn_number)
        if bonus > 0:
            base += bonus
            reasons.append(f"✅ Timer Ball: ход {turn_number} (+{bonus:.0f}%)")
    elif ball_key == "quick_ball":
        if turn_number == 1:
            base = 95.0
            reasons.append("✅ Quick Ball: первый ход (95%)")
        else:
            reasons.append("❌ Quick Ball: не первый ход")
    elif ball_key == "dusk_ball":
        if is_night or is_cave:
            base += 25.0
            reasons.append("✅ Dusk Ball: ночь/пещера (+25%)")
        else:
            reasons.append("❌ Dusk Ball: не ночь и не пещера")
    elif ball_key == "heal_ball":
        reasons.append("💚 Heal Ball: лечит покемона при поимке")
    elif ball_key == "luxury_ball":
        reasons.append("✨ Luxury Ball: покемон станет дружелюбнее")

    elif ball_key == "sport_ball":
        if "bug" in species_types:
            base += 25.0
            reasons.append("✅ Sport Ball: тип Bug (+25%)")
        else:
            reasons.append("❌ Sport Ball: не Bug")
    elif ball_key == "level_ball":
        if level >= 30:
            base += 30.0
            reasons.append(f"✅ Level Ball: Ур. {level} ≥ 30 (+30%)")
        elif level >= 20:
            base += 20.0
            reasons.append(f"✅ Level Ball: Ур. {level} ≥ 20 (+20%)")
        else:
            reasons.append(f"❌ Level Ball: Ур. {level} < 20")
    elif ball_key == "lure_ball":
        if "water" in species_types:
            base += 25.0
            reasons.append("✅ Lure Ball: тип Water (+25%)")
        else:
            reasons.append("❌ Lure Ball: не Water")
    elif ball_key == "moon_ball":
        if any(t in species_types for t in ("water", "psychic", "fairy", "normal")):
            base += 25.0
            reasons.append("✅ Moon Ball: подходит по типу (+25%)")
        else:
            reasons.append("❌ Moon Ball: не подходит по типу")
    elif ball_key == "friend_ball":
        base += 10.0
        reasons.append("💚 Friend Ball: +10%, дружба вырастет")
    elif ball_key == "love_ball":
        base += 15.0
        reasons.append("💗 Love Ball: +15%")
    elif ball_key == "heavy_ball":
        if level >= 30:
            base += 20.0
            reasons.append(f"✅ Heavy Ball: тяжёлый (Ур.{level}) (+20%)")
        else:
            reasons.append("❌ Heavy Ball: слишком лёгкий")
    elif ball_key == "fast_ball":
        if any(t in species_types for t in ("flying", "electric")):
            base += 25.0
            reasons.append("✅ Fast Ball: быстрый тип (+25%)")
        else:
            reasons.append("❌ Fast Ball: не быстрый тип")
    elif ball_key == "dream_ball":
        reasons.append("💤 Dream Ball: сильнее на спящих (условно)")
    elif ball_key == "beast_ball":
        if (793 <= species_id <= 799) or species_id in (803, 804, 805, 806):
            base = 95.0
            reasons.append("✅ Beast Ball: Ультра-Бист (95%)")
        else:
            reasons.append("❌ Beast Ball: не Ультра-Бист")
    elif ball_key == "strange_ball":
        if level >= 20:
            base += 20.0
            reasons.append(f"✅ Strange Ball: Ур. {level} ≥ 20 (+20%)")
        else:
            reasons.append("❌ Strange Ball: Ур. < 20")
    elif ball_key == "feather_ball":
        base += 5.0
        reasons.append("🪶 Feather Ball: +5%")
    elif ball_key == "wing_ball":
        base += 10.0
        reasons.append("🪽 Wing Ball: +10%")
    elif ball_key == "jet_ball":
        base += 15.0
        reasons.append("🚀 Jet Ball: +15%")
    elif ball_key == "leaden_ball":
        base += 20.0
        reasons.append("⚫ Leaden Ball: +20%")
    elif ball_key == "gigaton_ball":
        base += 30.0
        reasons.append("💥 Gigaton Ball: +30%")
    elif ball_key in ("cherish_ball", "park_ball", "origin_ball", "gs_ball"):
        reasons.append("⭐ Особый болл — 100%")

    if is_badly_wounded:
        base += 25.0
        reasons.append("🩸 Покемон сильно ранен (+25%)")
    elif is_wounded:
        base += 15.0
        reasons.append("💔 Покемон ранен (+15%)")

    base = max(5.0, min(100.0, base))
    return base, reasons


class Catch(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="catch",
        description="Поймать покемона в текущей локации активного персонажа",
    )
    @app_commands.describe(
        ball="Тип покебола (используется из инвентаря персонажа)",
        wounded="Покемон ранен?",
        badly_wounded="Покемон сильно ранен?",
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

        loc = get_location(profile.get("location"))
        encounters = loc.get("encounters") or list(range(1, 1026))

        try:
            species_id = random.choice(encounters)
            data = await pokeapi_client.get_pokemon(species_id)
            gender = await pokeapi_client.roll_gender(data["id"])
        except PokeAPIError as e:
            await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
            return

        level = random.randint(2, 15)

        trainer = await get_trainer(uid)
        already_caught = data["id"] in trainer.get("pokedex_known", [])

        chance, reasons = _chance_for_ball(
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

        taken = await take_item(uid, ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Не удалось списать покебол (инвентарь изменился).", ephemeral=True
            )
            return

        roll = random.randint(1, 100)
        success = roll <= round(chance)

        name_title = f"{data['name']}"

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

            title = f"🎉 Пойман: {name_title}!"
            color = discord.Color.green()
            footer = f"Покемон отправлен в ПК • ID: {mon['instance_id']}"

            embed = discord.Embed(title=title, color=color)
            desc_parts = [
                f"**Игрок:** {interaction.user.mention}",
                f"**Персонаж:** {profile['name']}",
                f"**Покебол:** {BALL_NAMES[ball_key]}",
            ]
            if reasons:
                desc_parts.append("")
                desc_parts.append("**Условия:**")
                desc_parts.extend(reasons)
            desc_parts.append("")
            desc_parts.append(f"**Уровень:** {level} {GENDER_EMOJI.get(gender, '')}")
            desc_parts.append(f"**Тип:** {format_types(data['types'])}")
            desc_parts.append(f"**Атаки:** {format_moves(mon['moves'])}")
            if mon["ability"]:
                try:
                    ability_ru = await pokeapi_client.get_ability_ru(mon["ability"])
                except Exception:
                    ability_ru = mon["ability"]
                desc_parts.append(f"**Способность:** {ability_ru}")
            if is_new:
                desc_parts.append("")
                desc_parts.append("📖 **Новый вид в Покедексе!**")

            embed.description = "\n".join(desc_parts)
            if data.get("artwork"):
                embed.set_thumbnail(url=data["artwork"])
            embed.set_footer(text=footer)
        else:
            title = "💨 Покемон сбежал…"
            color = discord.Color.dark_red()
            desc_parts = [
                f"**Игрок:** {interaction.user.mention}",
                f"**Персонаж:** {profile['name']}",
                f"**Покебол:** {BALL_NAMES[ball_key]}",
            ]
            if reasons:
                desc_parts.append("")
                desc_parts.append("**Условия:**")
                desc_parts.extend(reasons)
            desc_parts.append("")
            desc_parts.append(f"**{name_title}** вырвался и скрылся.")

            embed = discord.Embed(
                title=title, description="\n".join(desc_parts), color=color
            )
            if data.get("artwork"):
                embed.set_thumbnail(url=data["artwork"])
            embed.set_footer(
                text=f"{BALL_NAMES[ball_key]} осталось: {qty - 1}"
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
