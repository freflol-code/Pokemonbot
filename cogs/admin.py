"""Мастерские команды — выдача и редактирование покемонов, деньги, предметы, победы/поражения."""
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
    add_item,
    add_item_by_profile,
    add_pokebucks,
    add_pokemon,
    add_pokemon_by_profile,
    add_to_pokedex,
    add_to_pokedex_by_profile,
    get_item_qty,
    get_pokemon,
    get_pokemon_by_profile,
    get_profile,
    get_trainer,
    inc_losses,
    inc_wins,
    list_profiles,
    remove_pokemon,
    remove_pokemon_by_profile,
    update_pokemon,
    update_pokemon_by_profile,
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


async def _profile_autocomplete(
    interaction: discord.Interaction, current: str
):
    """Подсказывает профили выбранного игрока."""
    user: Optional[discord.Member] = interaction.namespace.user
    if user is None:
        return []
    profiles = await list_profiles(user.id)
    cur = current.strip().lower()
    out = []
    for p in profiles:
        if p["profile_type"] == "pokemon":
            label = f"🐾 {p['name']} • Ур.{p.get('level') or '?'}"
        else:
            label = f"🎓 {p['name']}"
        if p["is_active"]:
            label = "🟢 " + label
        if not cur or cur in label.lower() or cur in p["profile_id"]:
            out.append(app_commands.Choice(name=label[:100], value=p["profile_id"]))
        if len(out) >= 25:
            break
    return out


async def _instance_autocomplete(
    interaction: discord.Interaction, current: str
):
    """ID покемонов выбранного игрока — с учётом profile_id, если он указан."""
    user: Optional[discord.Member] = interaction.namespace.user
    if user is None:
        return []
    profile_id = (interaction.namespace.profile_id or "").strip() if hasattr(interaction.namespace, "profile_id") else ""

    if profile_id:
        profile = await get_profile(profile_id)
        if not profile or profile["user_id"] != user.id:
            return []
        t = {
            "party": [],
            "pc": [],
        }
        # Достаём покемонов конкретного профиля
        from database import _pool_conn  # локальный импорт, чтобы не плодить публичные функции
        pool = _pool_conn()
        async with pool.acquire() as conn:
            party_rows = await conn.fetch(
                "SELECT * FROM pokemon WHERE profile_id = $1 AND in_party = 1 "
                "ORDER BY slot ASC, instance_id ASC", profile_id,
            )
            pc_rows = await conn.fetch(
                "SELECT * FROM pokemon WHERE profile_id = $1 AND in_party = 0 "
                "ORDER BY instance_id ASC", profile_id,
            )
        from database import _pokemon_dict
        t["party"] = [_pokemon_dict(r) for r in party_rows]
        t["pc"] = [_pokemon_dict(r) for r in pc_rows]
    else:
        t = await get_trainer(user.id)

    cur = current.strip().lower()
    out = []
    for where, mon in (
        [("К", m) for m in t.get("party", [])] + [("П", m) for m in t.get("pc", [])]
    ):
        sid = mon["species_id"]
        nick_part = mon.get("nickname") or f"#{sid}"
        label = f"[{where}] {nick_part} • Ур.{mon['level']} • {mon['instance_id']}"
        if not cur or cur in mon["instance_id"] or cur in label.lower():
            out.append(app_commands.Choice(name=label[:100], value=mon["instance_id"]))
        if len(out) >= 25:
            break
    return out


async def _item_autocomplete(
    interaction: discord.Interaction, current: str
):
    try:
        from cogs.inventory import ITEMS
    except Exception:
        return []
    cur = current.strip().lower().replace(" ", "_")
    out = []
    for key, info in ITEMS.items():
        name = str(info.get("name", key))
        label = f"{name} ({key})"
        if not cur or cur in key or cur in name.lower():
            out.append(app_commands.Choice(name=label[:100], value=key))
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
        description="[Мастер] Выдать покемона игроку (в активный или указанный профиль)",
    )
    @app_commands.describe(
        user="Кому выдать покемона",
        species="Вид: имя (пикачу / Pikachu) или номер (#25)",
        level="Уровень (1–100, по умолчанию 5)",
        gender="Пол. Не укажете — определится случайно по виду.",
        nickname="Кличка (необязательно)",
        moves="Атаки через запятую, 1–4 (не укажете — 4 случайные)",
        ability="Способность. Не укажете — выберется случайная обычная.",
        profile_id="Конкретный персонаж (если нужно выдать не активному)",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    @is_master()
    @app_commands.autocomplete(
        species=_species_autocomplete, profile_id=_profile_autocomplete
    )
    async def give_pokemon(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        species: str,
        level: app_commands.Range[int, 1, 100] = 5,
        gender: Optional[app_commands.Choice[str]] = None,
        nickname: Optional[str] = None,
        moves: Optional[str] = None,
        ability: Optional[str] = None,
        profile_id: Optional[str] = None,
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

        if ability:
            final_ability = ability.strip().lower().replace(" ", "-")
        else:
            final_ability = pokeapi_client.pick_random_ability(data)

        nick = (nickname or "").strip() or None
        if nick and len(nick) > 20:
            await interaction.followup.send("❌ Кличка не длиннее 20 символов.", ephemeral=True)
            return

        # Определяем целевой профиль
        if profile_id:
            target_profile = await get_profile(profile_id.strip())
            if not target_profile or target_profile["user_id"] != user.id:
                await interaction.followup.send(
                    "❌ Профиль с таким ID не найден у указанного игрока.", ephemeral=True
                )
                return
            profile_name = f"{target_profile['name']} (`{target_profile['profile_id']}`)"
            profile_type = target_profile["profile_type"]
        else:
            trainer = await get_trainer(user.id)
            target_profile = trainer
            profile_name = f"{trainer['name']} (активный)"
            profile_type = trainer["profile_type"]

        if profile_type == "pokemon":
            await interaction.followup.send(
                f"❌ **{target_profile['name']}** — это покемон. Ему нельзя выдать покемона.",
                ephemeral=True,
            )
            return

        party_len = len(target_profile.get("party", []))
        to_party = party_len < MAX_PARTY_SIZE

        mon = {
            "instance_id": uuid.uuid4().hex[:8],
            "species_id": data["id"],
            "nickname": nick,
            "level": int(level),
            "gender": mon_gender,
            "moves": final_moves,
            "ability": final_ability,
        }

        if profile_id:
            added_to_party = await add_pokemon_by_profile(
                target_profile["profile_id"], mon, to_party=to_party
            )
            await add_to_pokedex_by_profile(target_profile["profile_id"], data["id"])
        else:
            added_to_party = await add_pokemon(user.id, mon, to_party=to_party)
            await add_to_pokedex(user.id, data["id"])

        species_data = await load_species([mon])
        title = mon_title(mon, species_data)
        place = "команда" if added_to_party else "ПК"
        ability_ru = (
            await pokeapi_client.get_ability_ru(final_ability) if final_ability else "—"
        )

        embed = discord.Embed(
            title="✅ Покемон выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Персонаж:** {profile_name}\n"
                f"**Покемон:** {title}\n"
                f"**Уровень:** {mon['level']}\n"
                f"**Пол:** {mon_gender} ({gender_source})\n"
                f"**Способность:** {ability_ru}\n"
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
                f"🎁 Мастер выдал вам **{title}** (Ур. {mon['level']}) "
                f"персонажу **{target_profile['name']}**!\n"
                f"Он {'в команде' if added_to_party else 'лежит в ПК'}."
            )
        except discord.Forbidden:
            pass

    # ------------------------------------------------------------------ /gm_delete

    @app_commands.command(name="gm_delete", description="[Мастер] Удалить покемона у игрока")
    @app_commands.describe(
        user="Владелец покемона",
        instance_id="ID покемона",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete, profile_id=_profile_autocomplete
    )
    async def gm_delete(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
        profile_id: Optional[str] = None,
    ) -> None:
        iid = instance_id.strip().lower()

        if profile_id:
            pid = profile_id.strip()
            profile = await get_profile(pid)
            if not profile or profile["user_id"] != user.id:
                await interaction.response.send_message(
                    "❌ Профиль не найден у игрока.", ephemeral=True
                )
                return
            mon = await get_pokemon_by_profile(pid, iid)
            if not mon:
                await interaction.response.send_message(
                    "❌ Покемон не найден в этом профиле.", ephemeral=True
                )
                return
            species = await load_species([mon])
            title = mon_title(mon, species)
            await remove_pokemon_by_profile(pid, iid)
        else:
            mon = await get_pokemon(user.id, iid)
            if not mon:
                await interaction.response.send_message(
                    "❌ Покемон не найден в активном профиле.", ephemeral=True
                )
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
    @app_commands.describe(
        user="Владелец", instance_id="ID покемона",
        level="Новый уровень (1–100)",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete, profile_id=_profile_autocomplete
    )
    async def gm_set_level(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
        level: app_commands.Range[int, 1, 100],
        profile_id: Optional[str] = None,
    ) -> None:
        iid = instance_id.strip().lower()
        if profile_id:
            ok = await update_pokemon_by_profile(profile_id.strip(), iid, level=int(level))
        else:
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
        description="[Мастер] Изменить вид покемона",
    )
    @app_commands.describe(
        user="Владелец", instance_id="ID покемона",
        species="Новый вид (имя или #номер)",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete,
        species=_species_autocomplete,
        profile_id=_profile_autocomplete,
    )
    async def gm_set_species(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, species: str,
        profile_id: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            data = await pokeapi_client.get_pokemon_by_name(species)
        except PokeAPIError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return
        iid = instance_id.strip().lower()

        if profile_id:
            pid = profile_id.strip()
            old = await get_pokemon_by_profile(pid, iid)
            if not old:
                await interaction.followup.send("❌ Покемон не найден.", ephemeral=True)
                return
            await update_pokemon_by_profile(pid, iid, species_id=data["id"])
            await add_to_pokedex_by_profile(pid, data["id"])
        else:
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
    @app_commands.describe(
        user="Владелец", instance_id="ID покемона",
        moves="Атаки через запятую, 1–4",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete, profile_id=_profile_autocomplete
    )
    async def gm_set_moves(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, moves: str,
        profile_id: Optional[str] = None,
    ) -> None:
        parsed = [m.strip().lower().replace(" ", "-") for m in moves.split(",") if m.strip()]
        if not (1 <= len(parsed) <= 4):
            await interaction.response.send_message(
                "❌ Укажите от 1 до 4 атак через запятую.", ephemeral=True
            )
            return
        iid = instance_id.strip().lower()
        if profile_id:
            ok = await update_pokemon_by_profile(profile_id.strip(), iid, moves=parsed)
        else:
            ok = await update_pokemon(user.id, iid, moves=parsed)
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Атаки покемона `{iid}`:\n{format_moves(parsed)}", ephemeral=True
        )

    # ------------------------------------------------------------------ /gm_set_nick

    @app_commands.command(name="gm_set_nick", description="[Мастер] Изменить кличку покемона")
    @app_commands.describe(
        user="Владелец", instance_id="ID покемона",
        nickname="Кличка до 20 символов ('-' — сбросить)",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete, profile_id=_profile_autocomplete
    )
    async def gm_set_nick(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str, nickname: str,
        profile_id: Optional[str] = None,
    ) -> None:
        new_value = None if nickname.strip() in ("", "-") else nickname.strip()[:20]
        iid = instance_id.strip().lower()
        if profile_id:
            ok = await update_pokemon_by_profile(profile_id.strip(), iid, nickname=new_value)
        else:
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
    @app_commands.describe(
        user="Владелец", instance_id="ID покемона",
        gender="Новый пол",
        profile_id="Профиль (если покемон у неактивного персонажа)",
    )
    @app_commands.choices(gender=GENDER_CHOICES)
    @is_master()
    @app_commands.autocomplete(
        instance_id=_instance_autocomplete, profile_id=_profile_autocomplete
    )
    async def gm_set_gender(
        self, interaction: discord.Interaction,
        user: discord.Member, instance_id: str,
        gender: app_commands.Choice[str],
        profile_id: Optional[str] = None,
    ) -> None:
        iid = instance_id.strip().lower()
        if profile_id:
            ok = await update_pokemon_by_profile(profile_id.strip(), iid, gender=gender.value)
        else:
            ok = await update_pokemon(user.id, iid, gender=gender.value)
        if not ok:
            await interaction.response.send_message("❌ Покемон не найден.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Пол покемона `{iid}` → **{gender.name}**.", ephemeral=True
        )

    # ------------------------------------------------------------------ /give_money

    @app_commands.command(
        name="give_money",
        description="[Мастер] Выдать или забрать Pokébucks у игрока (в активный профиль)",
    )
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

    # ------------------------------------------------------------------ /give_item

    @app_commands.command(
        name="give_item",
        description="[Мастер] Выдать игроку предмет из каталога (в активный профиль)",
    )
    @app_commands.describe(
        user="Кому выдать",
        item="Ключ предмета (начните печатать — подскажу)",
        quantity="Сколько (1–999)",
    )
    @is_master()
    @app_commands.autocomplete(item=_item_autocomplete)
    async def give_item(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        item: str,
        quantity: app_commands.Range[int, 1, 999] = 1,
    ) -> None:
        from cogs.inventory import ITEMS

        key = item.strip().lower().replace(" ", "_")
        if key not in ITEMS:
            await interaction.response.send_message(
                f"❌ Предмет `{key}` не найден в каталоге.",
                ephemeral=True,
            )
            return

        await add_item(user.id, key, int(quantity))
        name = ITEMS[key]["name"]
        qty_now = await get_item_qty(user.id, key)

        embed = discord.Embed(
            title="📦 Предмет выдан",
            description=(
                f"**Игрок:** {user.mention}\n"
                f"**Предмет:** {name} × {quantity}\n"
                f"**Теперь в инвентаре:** {qty_now} шт."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ /gm_win, /gm_lose

    @app_commands.command(name="gm_win", description="[Мастер] Начислить победы активному профилю")
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
                f"**Персонаж:** {t['name']}\n"
                f"**Начислено:** +{amount}\n"
                f"**Побед:** {t['wins']} • **Поражений:** {t['losses']}"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="gm_lose", description="[Мастер] Начислить поражения активному профилю")
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
                f"**Персонаж:** {t['name']}\n"
                f"**Начислено:** +{amount}\n"
                f"**Побед:** {t['wins']} • **Поражений:** {t['losses']}"
            ),
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
