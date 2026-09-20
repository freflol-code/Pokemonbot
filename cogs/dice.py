"""Броски для РП-боёв: атака и уклонение."""
from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import battle_math


class Dice(commands.Cog):
    """Кубики для РП-боёв между игроками."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="attack", description="Бросок атаки")
    @app_commands.describe(
        accuracy="Точность атаки в % (1–100). 0 — не промахивается",
        ch="Модификатор точности/уклонения (-6..+6). По умолчанию 0",
    )
    async def attack(
        self,
        interaction: discord.Interaction,
        accuracy: app_commands.Range[int, 0, 100],
        ch: app_commands.Range[int, -6, 6] = 0,
    ) -> None:
        move_accuracy = None if accuracy == 0 else accuracy

        chance = battle_math.effective_accuracy(
            move_accuracy,
            accuracy_stage=ch,
            evasion_stage=-ch,
        )

        roll = random.randint(1, 100)
        hit = roll <= round(chance * 100)

        lines = [f"**{interaction.user.display_name}** атакует…", ""]

        if move_accuracy is None:
            lines.append("Атака не промахивается.")
            lines.append("")
            lines.append("✅ **ПОПАЛ!**")
            color = discord.Color.green()
        else:
            lines.append(f"Точность: **{accuracy}%**")
            if ch != 0:
                sign = "+" if ch > 0 else ""
                lines.append(f"Ch: **{sign}{ch}**")
                lines.append(f"Итоговый шанс: **{chance * 100:.1f}%**")
            lines.append(f"🎲 Выпало: **{roll}**")
            lines.append("")
            if hit:
                lines.append("✅ **ПОПАЛ!**")
                color = discord.Color.green()
            else:
                lines.append("💨 **ПРОМАХ!**")
                color = discord.Color.dark_red()

        embed = discord.Embed(title="⚔️ Атака", description="\n".join(lines), color=color)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dodge", description="Попытка уклониться — 50/50")
    @app_commands.describe(
        ch="Модификатор уклонения (-6..+6). По умолчанию 0",
    )
    async def dodge(
        self,
        interaction: discord.Interaction,
        ch: app_commands.Range[int, -6, 6] = 0,
    ) -> None:
        base = 0.5
        mult = battle_math.stage_multiplier(ch)
        chance = min(0.95, max(0.05, base * mult))

        roll = random.randint(1, 100)
        success = roll <= round(chance * 100)

        lines = [f"**{interaction.user.display_name}** уклоняется…", ""]
        if ch != 0:
            sign = "+" if ch > 0 else ""
            lines.append(f"Ch: **{sign}{ch}**")
        lines.append(f"Шанс: **{chance * 100:.0f}%**")
        lines.append(f"🎲 Выпало: **{roll}**")
        lines.append("")

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