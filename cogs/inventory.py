"""Инвентарь, магазин по локациям и переводы между игроками."""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from database import get_trainer, update_trainer
from utils import EMBED_COLOR

# --------------------------------------------------------------------------- #
#                              ПРЕДМЕТЫ                                       #
# --------------------------------------------------------------------------- #

ITEMS: dict[str, dict] = {
    "pokeball":      {"name": "Покебол",        "price": 200,  "desc": "Ловля покемонов"},
    "greatball":     {"name": "Грейтбол",       "price": 600,  "desc": "Ловля (лучше покебола)"},
    "ultraball":     {"name": "Ультрабол",      "price": 1200, "desc": "Ловля (почти всегда срабатывает)"},
    "potion":        {"name": "Поушен",         "price": 300,  "desc": "+20 HP"},
    "super_potion":  {"name": "Супер-поушен",   "price": 700,  "desc": "+50 HP"},
    "hyper_potion":  {"name": "Гипер-поушен",   "price": 1500, "desc": "+200 HP"},
    "max_potion":    {"name": "Макс-поушен",    "price": 2500, "desc": "Полное HP"},
    "revive":        {"name": "Оживитель",      "price": 1500, "desc": "Воскрешает на 50% HP"},
    "max_revive":    {"name": "Макс-оживитель", "price": 4000, "desc": "Воскрешает полностью"},
    "antidote":      {"name": "Антидот",        "price": 100,  "desc": "Лечит отравление"},
    "burn_heal":     {"name": "Бёрн-хил",       "price": 250,  "desc": "Лечит ожог"},
    "awakening":     {"name": "Пробуждение",    "price": 250,  "desc": "Будит покемона"},
    "ice_heal":      {"name": "Айс-хил",        "price": 250,  "desc": "Лечит заморозку"},
    "paralyze_heal": {"name": "Паралайз-хил",   "price": 200,  "desc": "Лечит паралич"},
    "full_heal":     {"name": "Фулл-хил",       "price": 600,  "desc": "Лечит все статусы"},
    "protein":       {"name": "Протеин",        "price": 9800, "desc": "+Атака навсегда"},
    "iron":          {"name": "Железо",         "price": 9800, "desc": "+Защита навсегда"},
    "carbos":        {"name": "Карбос",         "price": 9800, "desc": "+Скорость навсегда"},
    "calcium":       {"name": "Кальций",        "price": 9800, "desc": "+Спец. атака навсегда"},
    "hp_up":         {"name": "HP-Ап",          "price": 9800, "desc": "+HP навсегда"},
}

# --------------------------------------------------------------------------- #
#           ЛОКАЦИИ (ENV-ключ → город Тэнхо + ассортимент)                     #
# --------------------------------------------------------------------------- #

LOCATIONS: dict[str, dict] = {
    # 1. Хошинори — стартовая деревня
    "viridian": {
        "name": "Хошинори",
        "env": "PokeShop_Viridian",
        "items": ["pokeball", "potion", "antidote"],
    },
    # 2. Астерис
    "pewter": {
        "name": "Астерис",
        "env": "PokeShop_Pewter",
        "items": ["pokeball", "greatball", "potion", "antidote"],
    },
    # 3. Верден
    "cerulean": {
        "name": "Верден",
        "env": "PokeShop_Cerulean",
        "items": ["pokeball", "greatball", "potion", "super_potion",
                  "antidote", "paralyze_heal"],
    },
    # 4. Кайсэки
    "vermilion": {
        "name": "Кайсэки",
        "env": "PokeShop_Vermilion",
        "items": ["pokeball", "greatball", "potion", "super_potion",
                  "antidote", "burn_heal", "awakening"],
    },
    # 5. Нордкрон
    "lavender": {
        "name": "Нордкрон",
        "env": "PokeShop_Lavender",
        "items": ["pokeball", "greatball", "potion", "super_potion",
                  "revive", "antidote", "paralyze_heal", "burn_heal"],
    },
    # 6. Аурелис
    "celadon": {
        "name": "Аурелис",
        "env": "PokeShop_Celadon",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion",
                  "revive", "antidote", "full_heal"],
    },
    # 7. Хибики
    "fuchsia": {
        "name": "Хибики",
        "env": "PokeShop_Fuchsia",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion",
                  "revive", "full_heal", "paralyze_heal"],
    },
    # 8. Куронаке
    "saffron": {
        "name": "Куронаке",
        "env": "PokeShop_Saffron",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion",
                  "revive", "full_heal", "ice_heal", "burn_heal"],
    },
    # 9. Люмьер
    "cinnabar": {
        "name": "Люмьер",
        "env": "PokeShop_Cinnabar",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion", "max_potion",
                  "revive", "full_heal"],
    },
    # 10. Эстера
    "goldenrod": {
        "name": "Эстера",
        "env": "PokeShop_Goldenrod",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion", "max_potion",
                  "revive", "max_revive", "full_heal"],
    },
    # 11. Рейгард
    "lilycove": {
        "name": "Рейгард",
        "env": "PokeShop_Lilycove",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion", "max_potion",
                  "revive", "max_revive", "full_heal",
                  "protein", "iron"],
    },
    # 12. Эйдолон — столица Лиги
    "slateport": {
        "name": "Эйдолон",
        "env": "PokeShop_Slateport",
        "items": ["pokeball", "greatball", "ultraball",
                  "potion", "super_potion", "hyper_potion", "max_potion",
                  "revive", "max_revive", "full_heal",
                  "protein", "iron", "carbos", "calcium", "hp_up"],
    },
}


def _load_channel_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for loc_key, data in LOCATIONS.items():
        raw = os.getenv(data["env"], "").strip()
        if not raw or not raw.isdigit():
            continue
        mapping[int(raw)] = loc_key
    return mapping


def _find_location(channel_id: int | None) -> str | None:
    if channel_id is None:
        return None
    return _load_channel_map().get(channel_id)


def _items_list(loc_key: str) -> str:
    loc = LOCATIONS[loc_key]
    return ", ".join(ITEMS[k]["name"] for k in loc["items"])


# --------------------------------------------------------------------------- #
#                              COG                                            #
# --------------------------------------------------------------------------- #

class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="inventory", description="Показать инвентарь (только вам)")
    async def inventory(self, interaction: discord.Interaction) -> None:
        t = await get_trainer(interaction.user.id)
        lines = []
        for key, qty in sorted(t["inventory"].items()):
            if qty <= 0:
                continue
            info = ITEMS.get(key)
            name = info["name"] if info else key
            lines.append(f"**{name}** × {qty}")
        embed = discord.Embed(
            title="🎒 Инвентарь",
            description="\n".join(lines) if lines else "Инвентарь пуст.",
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Баланс: {t['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="shop",
        description="Купить предмет (только в канале магазина)",
    )
    @app_commands.describe(
        item="ID предмета (например potion, pokeball)",
        quantity="Количество (1–99)",
    )
    async def shop(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        loc_key = _find_location(interaction.channel_id)
        if loc_key is None:
            await interaction.response.send_message(
                "❌ Эта команда работает только в канале магазина. "
                "Перейдите в соответствующий канал.",
                ephemeral=True,
            )
            return

        loc = LOCATIONS[loc_key]
        key = item.strip().lower()
        if key not in ITEMS:
            await interaction.response.send_message(
                f"❌ Неизвестный предмет `{key}`.\n"
                f"Доступно в **{loc['name']}**: {_items_list(loc_key)}",
                ephemeral=True,
            )
            return
        if key not in loc["items"]:
            await interaction.response.send_message(
                f"❌ В **{loc['name']}** этого нет.\n"
                f"Доступно: {_items_list(loc_key)}",
                ephemeral=True,
            )
            return

        info = ITEMS[key]
        total = info["price"] * quantity

        res = await update_trainer(
            interaction.user.id,
            {"$inc": {"pokebucks": -total, f"inventory.{key}": quantity}},
            {"pokebucks": {"$gte": total}},
        )
        if res.matched_count == 0:
            t = await get_trainer(interaction.user.id)
            await interaction.response.send_message(
                f"❌ Недостаточно Pokébucks: нужно **{total:,}**, у вас **{t['pokebucks']:,}**.",
                ephemeral=True,
            )
            return

        t = await get_trainer(interaction.user.id)
        embed = discord.Embed(
            title="🛒 Покупка совершена",
            description=(
                f"**{loc['name']}**\n"
                f"Куплено: **{info['name']}** × {quantity}\n"
                f"Цена: **{total:,}** PB\n"
                f"_{info['desc']}_"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Остаток: {t['pokebucks']:,} Pokébucks")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="shop_list",
        description="Показать ассортимент текущего магазина",
    )
    async def shop_list(self, interaction: discord.Interaction) -> None:
        loc_key = _find_location(interaction.channel_id)
        if loc_key is None:
            await interaction.response.send_message(
                "❌ Эта команда работает только в канале магазина.",
                ephemeral=True,
            )
            return
        loc = LOCATIONS[loc_key]
        lines = [
            f"**{ITEMS[k]['name']}** — {ITEMS[k]['price']:,} PB — _{ITEMS[k]['desc']}_"
            for k in loc["items"]
        ]
        embed = discord.Embed(
            title=f"🏪 {loc['name']}",
            description="\n".join(lines),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Купить: /shop item:<id> quantity:<n>")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="transfer_item", description="Перевести предметы другому игроку"
    )
    @app_commands.describe(
        user="Кому перевести",
        item="ID предмета (например potion)",
        quantity="Сколько (1–99)",
    )
    async def transfer_item(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        item: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Нельзя переводить самому себе.", ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "❌ Нельзя переводить ботам.", ephemeral=True
            )
            return

        key = item.strip().lower()
        if key not in ITEMS:
            await interaction.response.send_message(
                f"❌ Неизвестный предмет `{key}`.", ephemeral=True
            )
            return

        res = await update_trainer(
            interaction.user.id,
            {"$inc": {f"inventory.{key}": -quantity}},
            {f"inventory.{key}": {"$gte": quantity}},
        )
        if res.matched_count == 0:
            await interaction.response.send_message(
                f"❌ У вас нет **{ITEMS[key]['name']}** в нужном количестве.",
                ephemeral=True,
            )
            return

        await update_trainer(user.id, {"$inc": {f"inventory.{key}": quantity}})

        await interaction.response.send_message(
            f"✅ Переведено **{ITEMS[key]['name']} × {quantity}** → {user.mention}",
            ephemeral=True,
        )

    @app_commands.command(
        name="transfer_money", description="Перевести Pokébucks другому игроку"
    )
    @app_commands.describe(user="Кому перевести", amount="Сколько (1–999999)")
    async def transfer_money(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 999999],
    ) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Нельзя переводить самому себе.", ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "❌ Нельзя переводить ботам.", ephemeral=True
            )
            return

        res = await update_trainer(
            interaction.user.id,
            {"$inc": {"pokebucks": -amount}},
            {"pokebucks": {"$gte": amount}},
        )
        if res.matched_count == 0:
            await interaction.response.send_message(
                "❌ Недостаточно Pokébucks.", ephemeral=True
            )
            return

        await update_trainer(user.id, {"$inc": {"pokebucks": amount}})

        await interaction.response.send_message(
            f"✅ Переведено **{amount:,} Pokébucks** → {user.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventory(bot))