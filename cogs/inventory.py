"""Инвентарь и магазин, привязанный к каналу."""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from data.locations import LOCATIONS
from database import add_item, get_item_qty, get_trainer, spend_pokebucks
from utils import EMBED_COLOR

# ==========================================================================
#  КАТАЛОГ ПРЕДМЕТОВ
#  Здесь описаны ВСЕ существующие предметы (ключ → имя и цена).
# ==========================================================================
ITEMS: dict[str, dict[str, object]] = {
    "pokeball":     {"name": "Покебол",     "price": 50},
    "greatball":    {"name": "Грейтбол",    "price": 120},
    "potion":       {"name": "Зелье",       "price": 40},
    "super_potion": {"name": "Супер-зелье", "price": 100},
    "revive":       {"name": "Оживитель",   "price": 300},
}

# ==========================================================================
#  СТАНДАРТНЫЙ АССОРТИМЕНТ
#  Пока во всех магазинах один и тот же набор.
#  Когда захочешь разные — замени на dict[location_key] -> list[item_key].
# ==========================================================================
STANDARD_STOCK: list[str] = ["pokeball", "greatball", "potion", "super_potion", "revive"]


def _load_shop_channels() -> dict[int, str]:
    """Читает переменные SHOP_CHANNEL_<LOCATION> из окружения.

    Возвращает {channel_id: location_key}.
    location_key — ключ из LOCATIONS (hoshinori, lastoris, ...).
    """
    mapping: dict[int, str] = {}
    for loc_key in LOCATIONS.keys():
        env_name = f"SHOP_CHANNEL_{loc_key.upper()}"
        raw = os.getenv(env_name, "").strip()
        if not raw:
            continue
        try:
            mapping[int(raw)] = loc_key
        except ValueError:
            continue
    return mapping


# Считается один раз при импорте модуля
SHOP_CHANNELS: dict[int, str] = _load_shop_channels()


def _location_by_channel(channel_id: int) -> str | None:
    """Возвращает ключ локации или None, если канал не магазинный."""
    return SHOP_CHANNELS.get(channel_id)


async def _shop_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Показывает стандартный набор (позже — набор текущей локации)."""
    cur = current.strip().lower()
    out: list[app_commands.Choice[str]] = []
    for key in STANDARD_STOCK:
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
        embed.set_footer(text=f"Баланс: {t['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="Магазин (работает только в каналах магазинов)")
    @app_commands.describe(
        item="Что купить",
        quantity="Сколько (1–99)",
    )
    @app_commands.autocomplete(item=_shop_autocomplete)
    async def shop(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        # 1. Проверяем, что команда вызвана в канале магазина
        loc_key = _location_by_channel(interaction.channel_id or 0)
        if loc_key is None:
            await interaction.response.send_message(
                "❌ Магазин доступен только в специальных каналах магазинов.",
                ephemeral=True,
            )
            return

        loc = LOCATIONS.get(loc_key, {})
        loc_name = f"{loc.get('emoji', '🏪')} {loc.get('name', loc_key)}"

        # 2. Проверяем, что предмет есть в каталоге
        key = item.strip().lower()
        if key not in ITEMS:
            await interaction.response.send_message(
                "❌ Такого предмета нет в каталоге.", ephemeral=True
            )
            return

        # 3. Пока во всех магазинах стандартный набор. Позже — свой для каждой локации.
        if key not in STANDARD_STOCK:
            await interaction.response.send_message(
                "❌ Этот предмет здесь не продаётся.", ephemeral=True
            )
            return

        info = ITEMS[key]
        total = int(info["price"]) * quantity

        # 4. Списываем Pokébucks атомарно
        uid = interaction.user.id
        t_before = await get_trainer(uid)
        paid = await spend_pokebucks(uid, total)
        if not paid:
            await interaction.response.send_message(
                f"❌ Недостаточно Pokébucks: нужно **{total:,}**, "
                f"у вас **{t_before['pokebucks']:,}**.",
                ephemeral=True,
            )
            return

        # 5. Начисляем предмет
        await add_item(uid, key, quantity)

        t_after = await get_trainer(uid)
        qty_now = await get_item_qty(uid, key)
        embed = discord.Embed(
            title="🛒 Покупка совершена",
            description=(
                f"Магазин: {loc_name}\n"
                f"Куплено: **{info['name']}** × {quantity}\n"
                f"Потрачено: **{total:,}** PB\n"
                f"Теперь у вас: **{qty_now}** шт."
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Остаток: {t_after['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventory(bot))
