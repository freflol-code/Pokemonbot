"""Инвентарь и локационный магазин."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from data.locations import get_location, location_title
from database import add_item, get_item_qty, get_trainer, spend_pokebucks
from utils import EMBED_COLOR

# Полный каталог предметов. Где продаётся — смотри data/locations.py → "shops".
ITEMS: dict[str, dict[str, object]] = {
    "pokeball":     {"name": "Покебол",     "price": 50},
    "greatball":    {"name": "Грейтбол",    "price": 120},
    "potion":       {"name": "Зелье",       "price": 40},
    "super_potion": {"name": "Супер-зелье", "price": 100},
    "revive":       {"name": "Оживитель",   "price": 300},
}


async def _shop_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Показывает только товары текущей локации игрока."""
    t = await get_trainer(interaction.user.id)
    loc = get_location(t.get("location"))
    cur = current.strip().lower()
    out: list[app_commands.Choice[str]] = []
    for key in loc["shops"]:
        info = ITEMS.get(key)
        if not info:
            continue
        label = f"{info['name']} — {info['price']} PB"
        if not cur or cur in key or cur in str(info["name"]).lower():
            out.append(app_commands.Choice(name=label[:100], value=key))
        if len(out) >= 25:
            break
    return out


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="inventory", description="Показать инвентарь")
    async def inventory(self, interaction: discord.Interaction) -> None:
        t = await get_trainer(interaction.user.id)
        inv: dict[str, int] = t.get("inventory", {})
        lines = [
            f"**{ITEMS.get(key, {}).get('name', key)}** × {qty}"
            for key, qty in sorted(inv.items())
            if qty > 0
        ]
        embed = discord.Embed(
            title="🎒 Инвентарь",
            description="\n".join(lines) if lines else "Инвентарь пуст. Загляните в /shop",
            color=EMBED_COLOR,
        )
        embed.set_footer(
            text=f"{location_title(t.get('location'))} • Баланс: {t['pokebucks']:,} PB"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="Магазин текущей локации")
    @app_commands.describe(
        item="Что купить (доступны только товары вашей локации)",
        quantity="Сколько (1–99)",
    )
    @app_commands.autocomplete(item=_shop_autocomplete)
    async def shop(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        key = item.strip().lower()
        uid = interaction.user.id

        # 1. Существует ли предмет в каталоге
        if key not in ITEMS:
            await interaction.response.send_message(
                "❌ Такого предмета нет в каталоге.", ephemeral=True
            )
            return

        # 2. Продаётся ли он в текущей локации игрока
        t = await get_trainer(uid)
        loc = get_location(t.get("location"))
        if key not in loc["shops"]:
            available = ", ".join(
                ITEMS[k]["name"] for k in loc["shops"] if k in ITEMS
            ) or "—"
            await interaction.response.send_message(
                f"❌ **{ITEMS[key]['name']}** не продаётся в локации "
                f"{loc['emoji']} **{loc['name']}**.\n"
                f"Здесь доступно: {available}.\n"
                f"Попробуйте /travel в другой город.",
                ephemeral=True,
            )
            return

        info = ITEMS[key]
        total = int(info["price"]) * quantity

        # 3. Атомарно списываем Pokébucks
        paid = await spend_pokebucks(uid, total)
        if not paid:
            await interaction.response.send_message(
                f"❌ Недостаточно Pokébucks: нужно **{total:,}**, "
                f"у вас **{t['pokebucks']:,}**.",
                ephemeral=True,
            )
            return

        # 4. Начисляем предмет
        await add_item(uid, key, quantity)

        # 5. Показываем результат
        t_after = await get_trainer(uid)
        qty_now = await get_item_qty(uid, key)
        embed = discord.Embed(
            title="🛒 Покупка совершена",
            description=(
                f"Вы купили **{info['name']}** × {quantity} "
                f"за **{total:,}** PB.\n"
                f"Локация: {location_title(loc)}\n"
                f"Теперь у вас: **{qty_now}**"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Остаток: {t_after['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventory(bot))
