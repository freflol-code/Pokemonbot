"""Ловля покемонов: /catch — выбираешь условия, жмёшь кнопку."""
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

# ... BALL_BASE_CHANCE, GUARANTEED_BALLS, BALL_NAMES, CATCHABLE_BALLS,
#     BALL_CHOICES, STATUS_CHOICES, STATUS_MULTIPLIER, _is_night, _chance_for_ball
#     (оставить без изменений из предыдущего ответа) ...


# ==========================================================================
#  КНОПКА БРОСКА
# ==========================================================================
class CatchView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        ball_key: str,
        chance: float,
        species_id: int,
        level: int,
        data: dict,
        rarity: str,
        qty_before: int,
    ):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.ball_key = ball_key
        self.chance = chance
        self.species_id = species_id
        self.level = level
        self.data = data
        self.rarity = rarity
        self.qty_before = qty_before

    @discord.ui.button(
        label="Бросить покебол", style=discord.ButtonStyle.primary, emoji="🎒"
    )
    async def throw_ball(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это не ваш бросок.", ephemeral=True
            )
            return

        # Блокируем кнопку, чтобы нельзя было нажать дважды
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Списываем покебол
        taken = await take_item(self.user_id, self.ball_key, 1)
        if not taken:
            await interaction.followup.send(
                "❌ Покебол куда-то пропал. Проверьте инвентарь.", ephemeral=True
            )
            return

        # Бросок
        roll = random.randint(1, 100)
        success = roll <= round(self.chance)

        mon_name = (self.data.get("name") or "Неизвестный покемон").title()
        rarity_emoji = RARITY_EMOJI.get(self.rarity, "⚪")
        rarity_label = RARITY_LABEL.get(self.rarity, self.rarity)

        description = (
            f"{rarity_emoji} **{mon_name}** — {rarity_label}\n"
            f"🎚️ Уровень: **{self.level}**\n"
            f"🎯 Шанс поимки: **{self.chance:.1f}%** (бросок: {roll})\n"
            f"🎒 Потрачено: **{BALL_NAMES.get(self.ball_key, self.ball_key)}** ×1\n"
            f"📦 Осталось: **{self.qty_before - 1}** шт."
        )

        embed = discord.Embed(
            title="🎉 Поймал!" if success else "💨 Не поймал",
            description=description,
            color=(
                discord.Color.green() if success
                else discord.Color.dark_red()
            ),
        )
        if self.data.get("artwork"):
            embed.set_thumbnail(url=self.data["artwork"])
        elif self.data.get("sprite"):
            embed.set_thumbnail(url=self.data["sprite"])

        await interaction.edit_original_response(embed=embed, view=self)

        # Если поймал — добавляем в ПК/покедекс (опционально, зависит от вашей логики)
        if success:
            await interaction.followup.send(
                f"✅ **{mon_name}** отправлен в ПК!", ephemeral=False
            )


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

        # Определяем покемона
        species_id = 0
        species_types: list[str] = []
        data: dict = {}
        try:
            species_id = random.randint(1, 1025)
            data = await pokeapi_client.get_pokemon(species_id)
            species_types = data.get("types", [])
        except PokeAPIError:
            log.warning("PokéAPI недоступен")
            species_id = 0
            species_types = []
            data = {}

        rarity = get_rarity(species_id)
        level = random.randint(2, 15)

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

        # Отправляем эмбед с кнопкой
        mon_name = (data.get("name") or "Неизвестный покемон").title()
        rarity_emoji = RARITY_EMOJI.get(rarity, "⚪")
        rarity_label = RARITY_LABEL.get(rarity, rarity)

        embed = discord.Embed(
            title="🌿 Дикий покемон появился!",
            description=(
                f"{rarity_emoji} **{mon_name}** — {rarity_label}\n"
                f"🎚️ Уровень: **{level}**\n"
                f"🎯 Шанс поимки: **{chance:.1f}%**\n"
                f"🎒 Покебол: **{BALL_NAMES.get(ball_key, ball_key)}**"
            ),
            color=discord.Color.blue(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        elif data.get("sprite"):
            embed.set_thumbnail(url=data["sprite"])

        view = CatchView(
            user_id=uid,
            ball_key=ball_key,
            chance=chance,
            species_id=species_id,
            level=level,
            data=data,
            rarity=rarity,
            qty_before=qty,
        )
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Catch(bot))
