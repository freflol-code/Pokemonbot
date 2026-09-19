"""Мастерские команды (только для роли MASTER_ROLE_ID или админов)."""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import get_trainer, update_trainer
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, format_moves, load_species, mon_title

log = logging.getLogger(__name__)

MAX_MOVES = 4
MIN_MOVES = 1

GENDER_CHOICES = [
    app_commands.Choice(name="♂️ Самец", value="male"),
    app_commands.Choice(name="♀️ Самка", value="female"),
    app_commands.Choice(name="⚪ Бесполый", value="genderless"),
]


# --------------------------------------------------------------------------- #
#                              ПРОВЕРКА ПРАВ                                  #
# --------------------------------------------------------------------------- #

def _master_role_id() -> int:
    raw = os.getenv("MASTER_ROLE_ID", "").strip()
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def is_master():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        role_id = _master_role_id()
        if role_id == 0:
            return False
        return any(r.id == role_id for r in interaction.user.roles)

    return app_commands.check(predicate)


# --------------------------------------------------------------------------- #
#                              АВТОДОПОЛНЕНИЯ                                 #
# --------------------------------------------------------------------------- #

async def _species_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Подсказывает виды покемонов по первым буквам."""
    try:
        index = await pokeapi_client.get_species_index()
    except PokeAPIError:
        return []
    cur = current.strip().lower().lstrip("#")
    out: list[app_commands.Choice[str]] = []
    for sid, name in index:
        if not cur or cur in name or cur == str(sid):
            pretty = name.replace("-", " ").title()
            out.append(app_commands.Choice(name=f"#{sid:04d} {pretty}", value=name))
        if len(out) >= 25:
            break
    return out


async def _instance_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Подсказывает ID покемонов у игрока, указанного в user."""
    user: Optional[discord.Member] = interaction.namespace.user
    if user is None:
        return []
    trainer = await get_trainer(user.id)
    cur = current.strip().lower()
    out: list[app_commands.Choice[str]] = []
    for source, where in (("party", "Команда"), ("pc", "ПК")):
        for m in trainer[source]:
            nick = m.get("nickname")
            name_part = nick if nick else f"#{m['species_id']}"
            label = f"[{where}] {name_part} Ур.{m['level']} • {m['instance_id']}"
            if not cur or cur in m["instance_id"] or cur in label.lower():
                out.append(
                    app_commands.Choice(name=label[:100], value=m["instance_id"])
                )
            if len(out) >= 25:
                break
        if len(out) >= 25:
            break
    return out


# --------------------------------------------------------------------------- #
#                                  COG                                        #
# --------------------------------------------------------------------------- #

class Admin(commands.Cog):
    """Команды для мастеров игры."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        for cmd in (
            self.give_pokemon,
            self.gm_set_level,
            self.gm_set_moves,
            self.gm_set_gender,
            self.gm_rename,
            self.gm_delete,
            self.give_item,
            self.give_money,
            self.reset_trainer,
            self.gm_add_win,
            self.gm_add_loss,
            self.gm_set_stats,
        ):
            cmd.error(self._on_master_error)

    async def _on_master_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "🚫 Эта команда только для мастеров игры."
        else:
            log.exception("Ошибка в мастерской команде", exc_info=error)
            msg = "⚠️ Внутренняя ошибка. Смотрите логи."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ GIVE

    @app_commands.command(
        name="give_pokemon",
        description="[Мастер] Выдать игроку конкретного покемона",
    )
    @app_commands.describe(
        user="Кому выдать покемона (выберите участника)",
        species="Вид: имя (pikachu) или номер (#25). Начните печатать — подскажу.",
        level="Уровень покемона от 1 до 100 (по умолчанию 5)",
        gender="Пол (не укажете — бот определит по виду случайно)",
        nickname="Кличка до 20 символов (необязательно)",
        moves="Атаки через запятую: от 1 до 4. Пример: thunderbolt, quick-attack, iron-tail",
        to_party="True — сразу в команду, False — в ПК (по умолчанию)",
    )
    @is_master()
    @app_commands.autocomplete(species=_species_autocomplete)
    async def give_pokemon(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        species: str,
        level: app_commands.Range[int, 1, 100] = 5,
        gender: Optional[app_commands.Choice[str]] = None,
        nickname: Optional[str] = None,
        moves: Optional[str] = None,
        to_party: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        # 1. Резолвим вид
        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(
                f"❌ Вид не найден: {e}\n"
                f"Попробуйте написать английское имя (pikachu) или номер (#25).",
                ephemeral=True,
            )
            return

        # 2. Пол
        mon_gender = gender.value if gender else await pokeapi_client.roll_gender(data["id"])

        # 3. Атаки
        if moves:
            parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
            if not (MIN_MOVES <= len(parsed) <= MAX_MOVES):
                await interaction.followup.send(
                    f"❌ Укажите от **{MIN_MOVES}** до **{MAX_MOVES}** атак через запятую "
                    f"(у вас {len(parsed)}). Пример: `thunderbolt, quick-attack`",
                    ephemeral=True,
                )
                return
            final_moves = parsed
        else:
            final_moves = pokeapi_client.pick_random_moves(data, MAX_MOVES)

        # 4. Кличка
        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send(
                "❌ Кличка не должна быть длиннее 20 символов.", ephemeral=True
            )
            return

        # 5. Собираем покемона
        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": nick,
            "level": int(level),
            "gender": mon_gender,
            "moves": final_moves,
        }

        # 6. Куда положить
        trainer = await get_trainer(user.id)
        place = "party" if (to_party and len(trainer["party"]) < 6) else "pc"
        await update_trainer(user.id, {"$push": {place: mon}})

        # 7. Отчёт мастеру
        species_data = await load_species([mon])
        title = mon_title(mon, species_data)
        embed = discord.Embed(
            title="✅ Покемон выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Покемон:** {title}\n"
                f"**Уровень:** {mon['level']}\n"
                f"**Атаки ({len(final_moves)}/{MAX_MOVES}):** {format_moves(final_moves)}\n"
                f"**ID:** `{mon['instance_id']}`\n"
                f"**Место:** {'команда' if place == 'party' else 'ПК'}"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        await interaction.followup.send(embed=embed, ephemeral=True)

        # 8. Уведомление игроку
        try:
            await user.send(
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']})!\n"
                f"Проверить: /pc или /party"
            )
        except discord.Forbidden:
            pass

    # ------------------------------------------------------------------ SET

    @app_commands.command(
        name="gm_set_level", description="[Мастер] Установить уровень покемона"
    )
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона — начните печатать, покажу варианты",
        level="Новый уровень (1–100)",
    )
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_level(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        instance_id: str,
        level: app_commands.Range[int, 1, 100],
    ) -> None:
        iid = instance_id.strip().lower()
        for field in ("party", "pc"):
            res = await update_trainer(
                user.id,
                {"$set": {f"{field}.$.level": int(level)}},
                {f"{field}.instance_id": iid},
            )
            if res.matched_count:
                await interaction.response.send_message(
                    f"✅ Уровень покемона `{iid}` изменён на **{level}**.", ephemeral=True
                )
                return
        await interaction.response.send_message(
            "❌ Покемон с таким ID не найден у указанного игрока.", ephemeral=True
        )

    @app_commands.command(
        name="gm_set_moves", description="[Мастер] Установить атаки покемона"
    )
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона — начните печатать, покажу варианты",
        moves="Атаки через запятую: от 1 до 4. Пример: thunderbolt, quick-attack",
    )
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_moves(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        instance_id: str,
        moves: str,
    ) -> None:
        parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
        if not (MIN_MOVES <= len(parsed) <= MAX_MOVES):
            await interaction.response.send_message(
                f"❌ Нужно от **{MIN_MOVES}** до **{MAX_MOVES}** атак "
                f"(у вас {len(parsed)}).",
                ephemeral=True,
            )
            return
        iid = instance_id.strip().lower()
        for field in ("party", "pc"):
            res = await update_trainer(
                user.id,
                {"$set": {f"{field}.$.moves": parsed}},
                {f"{field}.instance_id": iid},
            )
            if res.matched_count:
                await interaction.response.send_message(
                    f"✅ Атаки покемона `{iid}` ({len(parsed)}/{MAX_MOVES}):\n"
                    f"{format_moves(parsed)}",
                    ephemeral=True,
                )
                return
        await interaction.response.send_message(
            "❌ Покемон с таким ID не найден у указанного игрока.", ephemeral=True
        )

    @app_commands.command(
        name="gm_set_gender", description="[Мастер] Установить пол покемона"
    )
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона",
        gender="Новый пол",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_gender(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        instance_id: str,
        gender: app_commands.Choice[str],
    ) -> None:
        iid = instance_id.strip().lower()
        for field in ("party", "pc"):
            res = await update_trainer(
                user.id,
                {"$set": {f"{field}.$.gender": gender.value}},
                {f"{field}.instance_id": iid},
            )
            if res.matched_count:
                await interaction.response.send_message(
                    f"✅ Пол покемона `{iid}` теперь **{gender.name}**.", ephemeral=True
                )
                return
        await interaction.response.send_message(
            "❌ Покемон с таким ID не найден у указанного игрока.", ephemeral=True
        )

    @app_commands.command(
        name="gm_rename",
        description="[Мастер] Переименовать покемона без ограничений",
    )
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона",
        nickname="Новая кличка до 20 символов ('-' — сбросить)",
    )
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_rename(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        instance_id: str,
        nickname: str,
    ) -> None:
        new_value = None if nickname.strip() in ("", "-") else nickname.strip()[:20]
        iid = instance_id.strip().lower()
        for field in ("party", "pc"):
            res = await update_trainer(
                user.id,
                {"$set": {f"{field}.$.nickname": new_value}},
                {f"{field}.instance_id": iid},
            )
            if res.matched_count:
                txt = "сброшена" if new_value is None else f"**{new_value}**"
                await interaction.response.send_message(
                    f"✅ Кличка покемона `{iid}` {txt}.", ephemeral=True
                )
                return
        await interaction.response.send_message(
            "❌ Покемон с таким ID не найден у указанного игрока.", ephemeral=True
        )

    @app_commands.command(
        name="gm_delete", description="[Мастер] Удалить покемона у игрока"
    )
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона",
    )
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_delete(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        instance_id: str,
    ) -> None:
        iid = instance_id.strip().lower()
        for field in ("party", "pc"):
            res = await update_trainer(user.id, {"$pull": {field: {"instance_id": iid}}})
            if res.modified_count:
                await interaction.response.send_message(
                    f"✅ Покемон `{iid}` удалён у {user.mention}.", ephemeral=True
                )
                return
        await interaction.response.send_message(
            "❌ Покемон с таким ID не найден у указанного игрока.", ephemeral=True
        )

    # ------------------------------------------------------------------ MONEY / ITEMS

    @app_commands.command(
        name="give_money", description="[Мастер] Выдать/забрать Pokébucks у игрока"
    )
    @app_commands.describe(
        user="Кому",
        amount="Сколько. Положительное — выдать, отрицательное — забрать.",
    )
    @is_master()
    async def give_money(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ) -> None:
        await update_trainer(user.id, {"$inc": {"pokebucks": int(amount)}})
        t = await get_trainer(user.id)
        sign = "+" if amount >= 0 else ""
        await interaction.response.send_message(
            f"✅ {user.mention}: {sign}{amount} PB. Баланс: **{t['pokebucks']:,}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="give_item", description="[Мастер] Выдать игроку предметы"
    )
    @app_commands.describe(
        user="Кому",
        item="Ключ предмета (pokeball, greatball, potion, revive...)",
        quantity="Сколько (1–999)",
    )
    @is_master()
    async def give_item(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        item: str,
        quantity: app_commands.Range[int, 1, 999] = 1,
    ) -> None:
        key = item.strip().lower()
        await update_trainer(user.id, {"$inc": {f"inventory.{key}": int(quantity)}})
        await interaction.response.send_message(
            f"✅ {user.mention} получил **{key} × {quantity}**.", ephemeral=True
        )

    # ------------------------------------------------------------------ BATTLE STATS

    @app_commands.command(
        name="gm_add_win",
        description="[Мастер] Начислить игроку победу (+1)",
    )
    @app_commands.describe(
        user="Кому начислить победу",
        amount="Сколько побед добавить (по умолчанию 1)",
    )
    @is_master()
    async def gm_add_win(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        await update_trainer(user.id, {"$inc": {"wins": int(amount)}})
        t = await get_trainer(user.id)
        await interaction.response.send_message(
            f"🏆 {user.mention}: **+{amount}** побед. "
            f"Итого: **{t['wins']}** 🏆 / **{t['losses']}** 💔",
            ephemeral=True,
        )

    @app_commands.command(
        name="gm_add_loss",
        description="[Мастер] Начислить игроку поражение (+1)",
    )
    @app_commands.describe(
        user="Кому начислить поражение",
        amount="Сколько поражений добавить (по умолчанию 1)",
    )
    @is_master()
    async def gm_add_loss(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        await update_trainer(user.id, {"$inc": {"losses": int(amount)}})
        t = await get_trainer(user.id)
        await interaction.response.send_message(
            f"💔 {user.mention}: **+{amount}** поражений. "
            f"Итого: **{t['wins']}** 🏆 / **{t['losses']}** 💔",
            ephemeral=True,
        )

    @app_commands.command(
        name="gm_set_stats",
        description="[Мастер] Установить точное число побед и поражений",
    )
    @app_commands.describe(
        user="Кому установить статистику",
        wins="Побед (0–9999)",
        losses="Поражений (0–9999)",
    )
    @is_master()
    async def gm_set_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        wins: app_commands.Range[int, 0, 9999],
        losses: app_commands.Range[int, 0, 9999],
    ) -> None:
        await update_trainer(
            user.id,
            {"$set": {"wins": int(wins), "losses": int(losses)}},
        )
        await interaction.response.send_message(
            f"✅ Статистика {user.mention} установлена: "
            f"**{wins}** 🏆 / **{losses}** 💔",
            ephemeral=True,
        )

    # ------------------------------------------------------------------ RESET

    @app_commands.command(
        name="reset_trainer",
        description="[Мастер] Полностью сбросить профиль игрока (НЕОБРАТИМО)",
    )
    @app_commands.describe(
        user="Кого сбросить",
        confirm="Введите ровно 'ДА' для подтверждения",
    )
    @is_master()
    async def reset_trainer(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        confirm: str,
    ) -> None:
        if confirm != "ДА":
            await interaction.response.send_message(
                "❌ Отменено. Для подтверждения введите `confirm:ДА`", ephemeral=True
            )
            return
        await update_trainer(
            user.id,
            {
                "$set": {
                    "wins": 0,
                    "losses": 0,
                    "pokebucks": 500,
                    "pokedex_known": [],
                    "inventory": {"pokeball": 5, "potion": 3},
                    "party": [],
                    "pc": [],
                }
            },
        )
        await interaction.response.send_message(
            f"♻️ Профиль {user.mention} сброшен к стартовому состоянию.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))