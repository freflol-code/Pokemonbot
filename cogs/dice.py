"""Броски для РП-боёв: атака, уклонение, крит."""
import random

import discord
from discord import app_commands
from discord.ext import commands


CRIT_CHANCES = {
    0: 6.25,
    1: 12.5,
    2: 50.0,
    3: 100.0,
    4: 100.0,
    5: 100.0,
    6: 100.0,
}

# ==========================================================================
#  ФОРМУЛА УКЛОНЕНИЯ ОТ СКОРОСТИ
# ==========================================================================
# База: 50%. Разница скоростей делится на SPEED_DIVISOR и даёт бонус в %.
# Например при SPEED_DIVISOR = 4:
#   Speed 100 vs 100 → 50%
#   Speed 120 vs 100 → +5% → 55%
#   Speed 150 vs 100 → +12% → 62%
#   Speed 80  vs 100 → -5% → 45%
SPEED_DIVISOR = 4.0

# Границы итогового шанса
DODGE_MIN = 5.0
DODGE_MAX = 95.0


def _roll_crit(cr_stage: int) -> bool:
    cr_stage = max(0, min(6, int(cr_stage)))
    chance = CRIT_CHANCES.get(cr_stage, 6.25)
    return random.random() * 100 < chance


def dodge_chance(
    my_speed: int,
    enemy_speed: int,
    *,
    ch: int = 0,
) -> float:
    """Итоговый шанс уворота (0–100).

    - my_speed — скорость уклоняющегося
    - enemy_speed — скорость атакующего
    - ch — дополнительный модификатор стадии (-6..+6), опционально
    """
    diff = int(my_speed) - int(enemy_speed)
    bonus = diff / SPEED_DIVISOR
    base = 50.0 + bonus

    # Модификатор стадии ch: каждая единица ±3%
    base += ch * 3

    return max(DODGE_MIN, min(DODGE_MAX, base))


class Dice(commands.Cog):
    """Кубики для РП-боёв между игроками."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------ /attack

    @app_commands.command(name="attack", description="Бросок атаки")
    @app_commands.describe(
        accuracy="Точность атаки в % (1–100). 0 — не промахивается",
        ch="Модификатор точности/уклонения (-6..+6). По умолчанию 0",
        cr="Стадия крита (0..+6). 0 — база 6%, +2 — 50%, +3 — 100%",
    )
    async def attack(
        self,
        interaction: discord.Interaction,
        accuracy: app_commands.Range[int, 0, 100],
        ch: app_commands.Range[int, -6, 6] = 0,
        cr: app_commands.Range[int, 0, 6] = 0,
    ) -> None:
        move_accuracy = None if accuracy == 0 else accuracy

        if move_accuracy is None:
            chance = 1.0
        else:
            # ch сдвигает: +1 = +12.5% к базовой точности
            acc_mult = 1.0 + ch * 0.125
            chance = min(1.0, max(0.05, (move_accuracy / 100.0) * acc_mult))

        roll = random.randint(1, 100)
        hit = roll <= round(chance * 100)

        crit = hit and _roll_crit(cr)

        lines = [f"**{interaction.user.display_name}** атакует…", ""]

        if not hit:
            lines.append("💨 **ПРОМАХ!**")
            color = discord.Color.dark_red()
        else:
            lines.append("✅ **ПОПАЛ!**")
            if crit:
                lines.append("")
                lines.append("🌟 **КРИТИЧЕСКИЙ УДАР!**")
                color = discord.Color.gold()
            else:
                color = discord.Color.green()

        embed = discord.Embed(title="⚔️ Атака", description="\n".join(lines), color=color)
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ /dodge

    @app_commands.command(
        name="dodge",
        description="Уклонение (шанс зависит от разницы скоростей)",
    )
    @app_commands.describe(
        my_speed="Скорость уклоняющегося покемона (из PokéAPI)",
        enemy_speed="Скорость атакующего покемона",
        ch="Доп. модификатор уклонения (-6..+6). Каждая единица ±3%",
    )
    async def dodge(
        self,
        interaction: discord.Interaction,
        my_speed: app_commands.Range[int, 1, 999],
        enemy_speed: app_commands.Range[int, 1, 999],
        ch: app_commands.Range[int, -6, 6] = 0,
    ) -> None:
        chance = dodge_chance(my_speed, enemy_speed, ch=ch)

        roll = random.randint(1, 100)
        success = roll <= round(chance)

        lines = [f"**{interaction.user.display_name}** уклоняется…", ""]

        if success:
            lines.append("✅ **УКЛОНИЛСЯ!**")
            color = discord.Color.green()
        else:
            lines.append("❌ **НЕ УСПЕЛ.**")
            color = discord.Color.dark_red()

        embed = discord.Embed(title="💨 Уклонение", description="\n".join(lines), color=color)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dice(bot))
