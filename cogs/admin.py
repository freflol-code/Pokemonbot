"""Мастерские команды — выдача и редактирование покемонов, деньги, победы/поражения."""
import logging
import os
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    MAX_PARTY_SIZE,
    add_pokebucks,
    add_pokemon,
    add_to_pokedex,
    get_pokemon,
    get_trainer,
    inc_losses,
    inc_wins,
    remove_pokemon,
    update_pokemon,
)
from pokeapi_client import PokeAPIError
from utils import EMBED_COLOR, format_moves, load_species, mon_title

log = logging.getLogger(__name__)

GENDER_CHOICES = [
    app_commands.Choice(name="♂️ Самец", value="male"),
    app_commands.Choice(name="♀️ Самка", value="female"),
    app_commands.Choice(name="⚪ Бесполый", value="genderless"),
]


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
):
    try:
        index = await pokeapi_client.ensure_name_index()
    except PokeAPIError:
        return []
    except AttributeError:
        log.exception("pokeapi_client без ensure_name_index — пересоберите проект")
        return []

    cur = current.strip().lower().lstrip("#")
    out = []
    POPULAR = [
        ("пикачу", "Пикачу"), ("чармандер", "Чармандер"),
        ("чаризард", "Чаризард"), ("бульбазавр", "Бульбазавр"),
        ("сквиртл", "Сквиртл"), ("иви", "Иви"),
        ("мьюту", "Мьюту"), ("джирачи", "Джирачи"),
        ("лукарио", "Лукарио"), ("гардевуар", "Гардевуар"),
    ]
    seen = set()
    if not cur:
        for key, label in POPULAR:
            sid = index.get(key)
            if sid and sid not in seen:
                out.append(app_commands.Choice(name=f"#{sid:04d} {label}", value=str(sid)))
                seen.add(sid)
        if len(out) >= 25:
            return out

    for name, sid in index.items():
        if sid in seen:
            continue
        if not cur or cur in name:
            out.append(app_commands.Choice(name=f"#{sid:04d} {name.title()}"[:100], value=str(sid)))
            seen.add(sid)
        if len(out) >= 25:
            break
    return out


async def _instance_autocomplete(
    interaction: discord.Interaction, current: str
):
    """Подсказывает ID покемонов выбранного мастера пользователя."""
    user: Optional[discord.Member] = interaction.namespace.user
    if user is None:
        return []
    t = await get_trainer(user.id)
    cur = current.strip().lower()
    out = []
    for where, mon in (
        [("К", m) for m in t["party"]] + [("П", m) for m in t["pc"]]
    ):
        sid = mon["species_id"]
        nick_part = mon.get("nickname") or f"#{sid}"
        label = f"[{where}] {nick_part} • Ур.{mon['level']} • {mon['instance_id']}"
        if not cur or cur in mon["instance_id"] or cur in label.lower():
            out.append(app_commands.Choice(name=label[:100], value=mon["instance_id"]))
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

    async def cog_app_command_error(
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

    # ------------------------------------------------------------------ /give

    @app_commands.command(
        name="give",
        description="[Мастер] Выдать игроку покемона (в команду, если есть место, иначе в ПК)",
    )
    @app_commands.describe(
        user="Кому выдать покемона",
        species="Вид: имя (пикачу / Pikachu) или номер (#25)",
        level="Уровень (1–100, по умолчанию 5)",
        gender="Пол. Не укажете — определится случайно по виду.",
        nickname="Кличка (необязательно)",
        moves="Атаки через запятую, 1–4 (не укажете — 4 случайные)",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
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
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(
                f"❌ {e}\nМожно вводить русское имя (Пикачу), английское (Pikachu) или номер (#25).",
                ephemeral=True,
            )
            return

        if gender is not None:
            mon_gender = gender.value
            gender_source = "задан мастером"
        else:
            mon_gender = await pokeapi_client.roll_gender(data["id"])
            gender_source = "случайный"

        if moves:
            parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
            if not (1 <= len(parsed) <= 4):
                await interaction.followup.send(
                    "❌ Укажите от 1 до 4 атак через запятую.", ephemeral=True
                )
                return
            final_moves = parsed
        else:
            final_moves = pokeapi_client.pick_random_moves(data, 4)

        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send("❌ Кличка не длиннее 20 символов.", ephemeral=True)
            return

        trainer = await get_trainer(user.id)
        to_party = len(trainer["party"]) < MAX_PARTY_SIZE

        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": nick,
            "level": int(level),
            "gender": mon_gender,
            "moves": final_moves,
        }
        added_to_party = await add_pokemon(user.id, mon, to_party=to_party)
        await add_to_pokedex(user.id, data["id"])

        species_data = await load_species([mon])
        title = mon_title(mon, species_data)
        place = "команду" if added_to_party else "ПК"

        embed = discord.Embed(
            title="✅ Покемон выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Покемон:** {title}\n"
                f"**Уровень:** {mon['level']}\n"
                f"**Пол:** {mon_gender} ({gender_source})\n"
                f"**Атаки:** {format_moves(final_moves)}\n"
                f"**ID:** `{mon['instance_id']}`\n"
                f"**Место:** {place}"
            ),
            color=discord.Color.green(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            await user.send(
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']})!\n"
                f"Он {'в команде' if added_to_party else 'лежит в ПК'}."
            )
        except discord.Forbidden:
            pass

    # ------------------------------------------------------------------ /gm_delete

    @app_commands.command(name="gm_delete", description="[Мастер] Удалить покемона у игрока")
    @app_commands.describe(user="Владелец покемона", instance_id="ID покемона")
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_delete(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
    ) -> None:
        iid = instance_id.strip().lower()
        mon = await get_pokemon(user.id, iid)
        if not mon:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        species = await load_species([mon])
        title = mon_title(mon, species)
        await remove_pokemon(user.id, iid)
        embed = discord.Embed(
            title="🗑️ Покемон удалён",
            description=f"**Игрок:** {user.mention}\n**Покемон:** {title}\n**ID:** `{iid}`",
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ /gm_set_level

    @app_commands.command(name="gm_set_level", description="[Мастер] Изменить уровень покемона")
    @app_commands.describe(user="Владелец", instance_id="ID покемона", level="Новый уровень (1–100)")
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_level(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
        level: app_commands.Range[int, 1, 100],
    ) -> None:
        iid = instance_id.strip().lower()
        ok = await update_pokemon(user.id, iid, level=int(level))
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Уровень покемона `{iid}` → **{level}**.", ephemeral=True
        )

    # ------------------------------------------------------------------ /gm_set_species

    @app_commands.command(
        name="gm_set_species",
        description="[Мастер] Изменить вид покемона (например, при эволюции или сюжете)",
    )
    @app_commands.describe(user="Владелец", instance_id="ID покемона", species="Новый вид (имя или #номер)")
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete, species=_species_autocomplete)
    async def gm_set_species(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, species: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return
        iid = instance_id.strip().lower()
        old = await get_pokemon(user.id, iid)
        if not old:
            await interaction.followup.send("❌ Покемон не найден.", ephemeral=True)
            return
        await update_pokemon(user.id, iid, species_id=data["id"])
        await add_to_pokedex(user.id, data["id"])
        embed = discord.Embed(
            title="🧬 Вид покемона изменён",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**ID:** `{iid}`\n"
                f"**Было:** #{old['species_id']}\n"
                f"**Стало:** #{data['id']} {data['name']}"
            ),
            color=discord.Color.purple(),
        )
        if data.get("artwork"):
            embed.set_thumbnail(url=data["artwork"])
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ /gm_set_moves

    @app_commands.command(name="gm_set_moves", description="[Мастер] Изменить атаки покемона")
    @app_commands.describe(user="Владелец", instance_id="ID покемона", moves="Атаки через запятую, 1–4")
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_moves(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, moves: str,
    ) -> None:
        parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
        if not (1 <= len(parsed) <= 4):
            await interaction.response.send_message(
                "❌ Укажите от 1 до 4 атак через запятую.", ephemeral=True
            )
            return
        iid = instance_id.strip().lower()
        ok = await update_pokemon(user.id, iid, moves=parsed)
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Атаки покемона `{iid}`:\n{format_moves(parsed)}", ephemeral=True
        )

    # ------------------------------------------------------------------ /gm_set_nick

    @app_commands.command(name="gm_set_nick", description="[Мастер] Изменить кличку покемона")
    @app_commands.describe(user="Владелец", instance_id="ID покемона", nickname="Кличка до 20 символов ('-' — сбросить)")
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_nick(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, nickname: str,
    ) -> None:
        new_value = None if nickname.strip() in ("", "-") else nickname.strip()[:20]
        iid = instance_id.strip().lower()
        ok = await update_pokemon(user.id, iid, nickname=new_value)
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        text = "сброшена" if new_value is None else f"**{new_value}**"
        await interaction.response.send_message(
            f"✅ Кличка покемона `{iid}` {text}.", ephemeral=True
        )

    # ------------------------------------------------------------------ /gm_set_gender

    @app_commands.command(name="gm_set_gender", description="[Мастер] Изменить пол покемона")
    @app_commands.describe(user="Владелец", instance_id="ID покемона", gender="Новый пол")
    @app_commands.choices(gender=GENDER_CHOICES)
    @is_master()
    @app_commands.autocomplete(instance_id=_instance_autocomplete)
    async def gm_set_gender(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
        gender: app_commands.Choice[str],
    ) -> None:
        iid = instance_id.strip().lower()
        ok = await update_pokemon(user.id, iid, gender=gender.value)
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Пол покемона `{iid}` → **{gender.name}**.", ephemeral=True
        )

    # ------------------------------------------------------------------ /give_money

    @app_commands.command(name="give_money", description="[Мастер] Выдать или забрать Pokébucks")
    @app_commands.describe(user="Кому", amount="Сумма (+ выдать, − забрать)")
    @is_master()
    async def give_money(
        self, interaction: discord.Interaction,
        user: discord.Member, amount: int,
    ) -> None:
        new_balance = await add_pokebucks(user.id, int(amount))
        sign = "+" if amount >= 0 else ""
        embed = discord.Embed(
            title="💰 Pokébucks обновлены",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Изменение:** {sign}{amount:,} PB\n"
                f"**Текущий баланс:** {new_balance:,} PB"
            ),
            color=discord.Color.gold() if amount >= 0 else discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ /gm_win, /gm_lose

    @app_commands.command(name="gm_win", description="[Мастер] Начислить игроку победы")
    @app_commands.describe(user="Кому", amount="Сколько побед (по умолчанию 1)")
    @is_master()
    async def gm_win(
        self, interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        await inc_wins(user.id, int(amount))
        t = await get_trainer(user.id)
        embed = discord.Embed(
            title="🏆 Победы засчитаны",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Начислено:** +{amount}\n"
                f"**Побед:** {t['wins']} • **Поражений:** {t['losses']}"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="gm_lose", description="[Мастер] Начислить игроку поражения")
    @app_commands.describe(user="Кому", amount="Сколько поражений (по умолчанию 1)")
    @is_master()
    async def gm_lose(
        self, interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100] = 1,
    ) -> None:
        await inc_losses(user.id, int(amount))
        t = await get_trainer(user.id)
        embed = discord.Embed(
            title="💔 Поражения засчитаны",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Начислено:** +{amount}\n"
                f"**Побед:** {t['wins']} • **Поражений:** {t['losses']}"
            ),
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
