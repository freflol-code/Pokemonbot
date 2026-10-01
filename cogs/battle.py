"""Боевая система: статусы, приоритеты, статы, Baton Pass / U-turn / Volt Switch,
Substitute, Leech Seed, Taunt, Encore, Disable, способности, badly poison."""
import asyncio
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import battle_messages as msg
import pokeapi_client
from battle_data import (
    STATUS_EMOJI,
    damage_label,
    get_crit_stage,
    get_move_priority,
    get_status_move,
    is_status_move,
)
from battle_engine import (
    BATTLE_ITEMS,
    BattlePokemon,
    SideField,
    WeatherField,
    ability_weather_on_switch,
    accuracy_check,
    apply_battle_item,
    apply_end_of_turn,
    apply_field_move,
    apply_intimidate,
    apply_switch_cure,
    apply_switch_heal,
    apply_switch_in_hazards,
    calc_damage,
    crit_check,
    is_baton_pass_move,
    is_battle_item,
    is_field_move,
    is_pivot_move,
    is_weather_move,
    on_switch_in_ability,
)
from database import (
    get_active_profile,
    get_trainer,
    inc_losses,
    inc_wins,
    take_item,
)
from pokeapi_client import PokeAPIError

log = logging.getLogger(__name__)


# ==========================================================================
#  ЛОКАЛИЗАЦИЯ
# ==========================================================================
STAT_RU = {
    "attack":     "Атака",
    "defense":    "Защита",
    "sp_attack":  "Спец. атака",
    "sp_defense": "Спец. защита",
    "speed":      "Скорость",
    "accuracy":   "Точность",
    "evasion":    "Уклонение",
}

STATUS_RU = {
    "burn":         "ожог",
    "poison":       "отравление",
    "badly_poison": "сильное отравление",
    "paralysis":    "паралич",
    "sleep":        "сон",
    "freeze":       "заморозка",
    "confused":     "замешательство",
    "infatuated":   "влюблённость",
}

TYPE_STATUS_IMMUNITY: dict[str, set[str]] = {
    "burn":         {"fire"},
    "poison":       {"poison", "steel"},
    "badly_poison": {"poison", "steel"},
    "paralysis":    {"electric"},
    "freeze":       {"ice"},
}

ABILITY_STATUS_IMMUNITY: dict[str, set[str]] = {
    "burn":         {"water-veil", "thermal-exchange"},
    "poison":       {"immunity"},
    "badly_poison": {"immunity"},
    "paralysis":    {"limber"},
    "sleep":        {"insomnia", "vital-spirit"},
    "freeze":       {"magma-armor"},
    "confused":     {"own-tempo"},
}


# ==========================================================================
#  ЗАГРУЗКА ДАННЫХ
# ==========================================================================
async def _load_mon_data(mon: dict) -> Optional[dict]:
    try:
        data = await pokeapi_client.get_pokemon(mon["species_id"])
    except PokeAPIError:
        return None

    abilities = data.get("abilities") or []
    ability = None
    for a in abilities:
        if not a.get("is_hidden"):
            ability = a["name"]
            break
    if not ability and abilities:
        ability = abilities[0]["name"]

    return {
        "instance_id": mon.get("instance_id", ""),
        "id": data.get("id"),
        "name": data["name"].title(),
        "types": data.get("types", []),
        "stats": data.get("stats", {}),
        "artwork": data.get("artwork"),
        "ability": ability,
        "item": mon.get("item"),
        "gender": mon.get("gender", "genderless"),
        "all_moves": list(data.get("moves", []) or []),
    }


def _broken_move(name: str) -> dict:
    """Заглушка для атаки, которую не удалось распознать."""
    return {
        "name": f"❓ {name}"[:80],
        "raw_name": "struggle",
        "power": 40,
        "type": "normal",
        "accuracy": 100,
        "damage_class": "physical",
        "broken": True,
    }


async def _load_moves(move_names: list[str]) -> list[dict]:
    """Загружает атаки из PokéAPI.

    Русские имена пробуем перевести через battle_data.MOVE_NAMES_RU
    (и автоиндекс PokéAPI), ASCII-slug запрашиваем напрямую.
    Если перевести не удалось — ставим кнопку-заглушку «❓ имя»,
    чтобы игрок видел, что именно не распознано.
    """
    out: list[dict] = []
    for name in move_names[:4]:
        if not name:
            continue

        resolved = pokeapi_client.resolve_move_name(name)
        raw = resolved.lower().replace(" ", "-").strip()

        if not raw.isascii():
            log.warning("Атака не распознана (осталось русской): %r", name)
            out.append(_broken_move(name))
            continue

        try:
            m = await pokeapi_client._fetch_json(
                f"https://pokeapi.co/api/v2/move/{raw}"
            )
        except PokeAPIError:
            log.warning("Атака не найдена в PokéAPI: %r (→ %r)", name, raw)
            out.append(_broken_move(name))
            continue

        out.append({
            "name": raw.replace("-", " ").title(),
            "raw_name": raw,
            "power": m.get("power") or 0,
            "type": (m.get("type") or {}).get("name", "normal"),
            "accuracy": m.get("accuracy"),
            "damage_class": (m.get("damage_class") or {}).get("name", "physical"),
        })
    return out


def _hp_bar(mon: BattlePokemon) -> str:
    ratio = mon.hp / mon.max_hp if mon.max_hp else 0
    filled = int(round(ratio * 10))
    return f"`{'█' * filled}{'░' * (10 - filled)}`"


def _status_emoji_str(mon: BattlePokemon) -> str:
    parts: list[str] = []
    if mon.status != "none":
        parts.append(STATUS_EMOJI.get(mon.status, ""))
    for key in mon.volatile:
        parts.append(STATUS_EMOJI.get(key, ""))
    if mon.has_substitute:
        parts.append(STATUS_EMOJI.get("substitute", "🎭"))
    if mon.leech_seed:
        parts.append(STATUS_EMOJI.get("leech_seed", "🌱"))
    if mon.flash_fire_active:
        parts.append(STATUS_EMOJI.get("flash_fire", "🔥"))
    return "".join(p for p in parts if p)


def _crit_bonus(mon: BattlePokemon) -> int:
    return int(getattr(mon, "crit_bonus", 0))


# ==========================================================================
#  ИНВЕНТАРЬ В БОЮ
# ==========================================================================
class BattleItemSelect(discord.ui.Select):
    def __init__(self, battle: "Battle", uid: int, items: dict[str, int]):
        self.battle = battle
        self.uid = uid
        options: list[discord.SelectOption] = []
        for key, qty in items.items():
            if qty <= 0 or not is_battle_item(key):
                continue
            info = BATTLE_ITEMS[key]
            options.append(
                discord.SelectOption(
                    label=f"{info['name']} ×{qty}"[:100], value=key,
                )
            )
            if len(options) >= 25:
                break
        if not options:
            options.append(
                discord.SelectOption(label="Нет доступных предметов", value="-1")
            )
        super().__init__(placeholder="Выбери предмет…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.uid:
            await interaction.response.send_message("Это не ваш выбор.", ephemeral=True)
            return
        if self.values[0] == "-1":
            await interaction.response.send_message("Нет предметов.", ephemeral=True)
            return
        await self.battle.register_action(
            interaction, self.uid,
            {"type": "item", "item_key": self.values[0]},
        )


class BattleItemView(discord.ui.View):
    def __init__(self, battle: "Battle", uid: int):
        super().__init__(timeout=60)
        self.add_item(BattleItemSelect(battle, uid, battle.inventories.get(uid, {})))


# ==========================================================================
#  СМЕНА ПОКЕМОНА
# ==========================================================================
class SwitchSelect(discord.ui.Select):
    def __init__(self, battle: "Battle", uid: int, reason: Optional[str]):
        self.battle = battle
        self.uid = uid
        self.reason = reason
        options: list[discord.SelectOption] = []
        party = battle.parties[uid]
        current_id = battle.active_index[uid]
        for i, mon in enumerate(party):
            if i == current_id:
                continue
            hp = battle.party_hp[uid].get(i, 0)
            if hp <= 0:
                continue
            name = mon.get("nickname") or f"#{mon.get('species_id')}"
            options.append(
                discord.SelectOption(label=f"{name} • {hp} HP"[:100], value=str(i))
            )
            if len(options) >= 25:
                break
        if not options:
            options.append(
                discord.SelectOption(label="Нет доступных покемонов", value="-1")
            )
        super().__init__(placeholder="Выбери покемона…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.uid:
            await interaction.response.send_message("Это не ваш выбор.", ephemeral=True)
            return
        if self.values[0] == "-1":
            await interaction.response.send_message(
                "Нет живых покемонов для смены.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.battle.handle_switch_pick(
            self.uid, int(self.values[0]), reason=self.reason
        )


class SwitchView(discord.ui.View):
    def __init__(self, battle: "Battle", uid: int, reason: Optional[str] = None):
        super().__init__(timeout=180)
        self.add_item(SwitchSelect(battle, uid, reason))


# ==========================================================================
#  КНОПКИ АТАК
# ==========================================================================
class BattleMoveButton(discord.ui.Button):
    def __init__(self, battle: "Battle", owner: int, move: dict, idx: int):
        raw = move.get("raw_name", "")
        if move.get("broken"):
            style = discord.ButtonStyle.danger
        elif is_status_move(raw) or is_baton_pass_move(raw):
            style = discord.ButtonStyle.secondary
        elif is_pivot_move(raw):
            style = discord.ButtonStyle.success
        else:
            style = discord.ButtonStyle.primary
        super().__init__(
            label=move["name"][:80],
            style=style,
            row=0 if idx < 2 else 1,
        )
        self.battle = battle
        self.owner = owner
        self.move = move

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner:
            await interaction.response.send_message("Это не ваш ход.", ephemeral=True)
            return
        if self.move.get("broken"):
            await interaction.response.send_message(
                "❌ Эта атака не распознана — обратитесь к мастеру, чтобы "
                "он поправил название через `/gm_set_moves`.",
                ephemeral=True,
            )
            return
        await self.battle.register_action(
            interaction, self.owner,
            {"type": "move", "move": self.move},
        )


class BattleView(discord.ui.View):
    def __init__(self, battle: "Battle", owner: int):
        super().__init__(timeout=180)
        self.battle = battle
        self.owner = owner

        attacker = battle.current[owner]
        for i, move in enumerate(attacker.moves[:4]):
            self.add_item(BattleMoveButton(battle, owner, move, i))

        switch_btn = discord.ui.Button(
            label="Сменить покемона", style=discord.ButtonStyle.secondary,
            emoji="🔄", row=2,
        )
        switch_btn.callback = self._on_switch
        self.add_item(switch_btn)

        item_btn = discord.ui.Button(
            label="Инвентарь", style=discord.ButtonStyle.success,
            emoji="🎒", row=2,
        )
        item_btn.callback = self._on_item
        self.add_item(item_btn)

    async def _on_switch(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner:
            await interaction.response.send_message("Это не ваш ход.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.battle.register_action(
            interaction, self.owner, {"type": "manual_switch"}
        )

    async def _on_item(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner:
            await interaction.response.send_message("Это не ваш ход.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Какой предмет использовать?",
            view=BattleItemView(self.battle, self.owner),
            ephemeral=True,
        )


# ==========================================================================
#  САМ БОЙ
# ==========================================================================
class Battle:
    def __init__(self, channel: discord.TextChannel, p1: int, p2: int):
        self.channel = channel
        self.players = [p1, p2]
        self.fields = {p1: SideField(), p2: SideField()}
        self.weather = WeatherField()
        self.current: dict[int, BattlePokemon] = {}
        self.parties: dict[int, list[dict]] = {}
        self.active_index: dict[int, int] = {p1: 0, p2: 0}
        self.party_hp: dict[int, dict[int, int]] = {p1: {}, p2: {}}
        self.inventories: dict[int, dict[str, int]] = {p1: {}, p2: {}}
        self.messages: list[discord.Message] = []
        self.log_lines: list[str] = []
        self.views: dict[int, discord.Message] = {}
        self.finished = False

        self.turn_actions: dict[int, dict] = {}
        self.turn_number: int = 0

        self.pending_switch: dict[int, str] = {}
        self.switch_futures: dict[int, asyncio.Future] = {}

    # ------------------------------------------------------------------ #
    async def start(self) -> bool:
        for uid in self.players:
            t = await get_trainer(uid)
            if not t["party"]:
                await self.channel.send(f"❌ <@{uid}> — нет покемонов в команде.")
                return False
            self.parties[uid] = list(t["party"])
            self.inventories[uid] = dict(t.get("inventory", {}) or {})

        for uid in self.players:
            if not await self._load_active(uid, 0):
                await self.channel.send(f"❌ Не удалось загрузить покемона у <@{uid}>.")
                return False
            for i, _ in enumerate(self.parties[uid]):
                self.party_hp[uid].setdefault(i, 100)

        await self.channel.send(
            f"⚔️ **Бой начался!** <@{self.players[0]}> против <@{self.players[1]}>"
        )

        self.log_lines = []
        for uid in self.players:
            mon = self.current[uid]
            for line in on_switch_in_ability(mon):
                self.log_lines.append(line)
            if (mon.ability or "").lower() == "intimidate":
                opp = self.current.get(self._other_player(uid))
                if opp:
                    self.log_lines.append(apply_intimidate(opp))
            w = ability_weather_on_switch(mon)
            if w:
                self.weather.set(w)
                self.log_lines.append(
                    msg.pick(msg.WEATHER_LINES.get(w, ["Погода меняется!"]))
                )

        await self.send_main_message()
        await self.send_move_views()
        return True

    async def _load_active(self, uid: int, idx: int) -> bool:
        party = self.parties[uid]
        if idx < 0 or idx >= len(party):
            return False
        mon = party[idx]
        data = await _load_mon_data(mon)
        if not data:
            return False

        moves = await _load_moves(mon.get("moves", []))
        if not moves:
            moves = [{
                "name": "Struggle",
                "raw_name": "struggle",
                "power": 50,
                "type": "normal",
                "accuracy": None,
                "damage_class": "physical",
            }]

        bp = BattlePokemon(
            data, mon.get("level", 5), moves, nature=mon.get("nature", "hardy")
        )
        saved_hp = self.party_hp.get(uid, {}).get(idx)
        if saved_hp is not None and saved_hp > 0:
            bp.hp = min(saved_hp, bp.max_hp)
        self.current[uid] = bp
        self.active_index[uid] = idx
        self.party_hp.setdefault(uid, {})[idx] = bp.hp
        return True

    def _save_active_hp(self, uid: int) -> None:
        idx = self.active_index[uid]
        if uid in self.current:
            self.party_hp[uid][idx] = self.current[uid].hp

    def _other_player(self, uid: int) -> int:
        return self.players[1] if uid == self.players[0] else self.players[0]

    def _me_uid(self, mon: BattlePokemon) -> int:
        for uid, m in self.current.items():
            if m is mon:
                return uid
        return self.players[0]

    # ------------------------------------------------------------------ #
    #  ОЧЕРЕДЬ ХОДОВ
    # ------------------------------------------------------------------ #
    async def register_action(
        self, interaction: discord.Interaction, uid: int, action: dict
    ) -> None:
        if self.finished:
            await interaction.response.send_message("Бой уже завершён.", ephemeral=True)
            return
        if uid in self.turn_actions:
            await interaction.response.send_message(
                "Вы уже выбрали действие в этом ходу.", ephemeral=True
            )
            return

        if action["type"] == "manual_switch":
            await interaction.followup.send(
                "Кого выпустить?",
                view=SwitchView(self, uid, reason=None),
                ephemeral=True,
            )
            return

        self.turn_actions[uid] = action
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "✅ Ход принят. Ждём соперника…", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "✅ Ход принят. Ждём соперника…", ephemeral=True
                )
        except discord.HTTPException:
            pass

        if len(self.turn_actions) >= len(self.players):
            await self._resolve_turn()

    def _order_actions(
        self, actions: dict[int, dict]
    ) -> list[tuple[int, dict]]:
        rows: list[tuple[int, dict, int, float]] = []
        for uid, action in actions.items():
            if action["type"] == "switch":
                prio = 6
            elif action["type"] == "item":
                prio = 6
            else:
                move = action.get("move") or {}
                prio = get_move_priority(move.get("raw_name", ""))
            mon = self.current.get(uid)
            speed = mon.effective_speed() if mon else 0
            rows.append((uid, action, prio, speed))
        rows.sort(key=lambda x: (-x[2], -x[3], random.random()))
        return [(uid, action) for uid, action, _, _ in rows]

    async def _resolve_turn(self) -> None:
        self.turn_number += 1
        actions = dict(self.turn_actions)
        self.turn_actions = {}
        await self._cleanup_views()
        self.log_lines = []

        order = self._order_actions(actions)
        for uid, action in order:
            if self.finished:
                return
            mon = self.current.get(uid)
            if not mon or mon.fainted:
                continue
            try:
                await self._execute_action(uid, action)
            except Exception:
                log.exception("Ошибка при выполнении действия")

        await self._post_turn()
        await self._handle_faints()

    async def _execute_action(self, uid: int, action: dict) -> None:
        if action["type"] == "switch":
            await self._do_switch(uid, action["index"])
        elif action["type"] == "item":
            await self._do_item(uid, action["item_key"])
        elif action["type"] == "move":
            await self._do_move(uid, action["move"])

    # ------------------------------------------------------------------ #
    #  ХОД АТАКИ
    # ------------------------------------------------------------------ #
    async def _do_move(self, uid: int, move: dict) -> None:
        attacker = self.current[uid]
        defender = self.current.get(self._other_player(uid))
        if defender is None:
            return

        if not self._pre_move_check(attacker):
            return

        raw_name = move.get("raw_name", move["name"].lower().replace(" ", "-"))

        # --- Encore ---
        encored = attacker.volatile.get("encore", 0)
        encored_move = getattr(attacker, "encored_move", None)
        if encored and encored_move:
            if raw_name != encored_move:
                forced = next(
                    (m for m in attacker.moves if m.get("raw_name") == encored_move),
                    None,
                )
                if forced:
                    move = forced
                    raw_name = encored_move

        # --- Disable ---
        if attacker.disabled_move and raw_name == attacker.disabled_move:
            self.log_lines.append(
                f"🚫 **{move['name']}** заблокирован (Disable)!"
            )
            return

        # --- Taunt ---
        if attacker.volatile.get("taunt", 0) > 0 and is_status_move(raw_name):
            self.log_lines.append(
                f"😤 **{attacker.name}** под Taunt — статусные атаки запрещены!"
            )
            return

        # --- Baton Pass ---
        if is_baton_pass_move(raw_name):
            self.log_lines.append(
                msg.pick(msg.ATTACK_TEMPLATES).format(
                    who=attacker.name, move=move["name"]
                )
            )
            attacker.last_move = raw_name
            await self._wait_for_switch(uid, reason="baton")
            return

        # --- Погода ---
        weather_key = is_weather_move(raw_name)
        if weather_key:
            self.weather.set(weather_key)
            self.log_lines.append(
                msg.pick(msg.ATTACK_TEMPLATES).format(who=attacker.name, move=move["name"])
            )
            self.log_lines.append(
                msg.pick(msg.WEATHER_LINES.get(weather_key, ["Погода меняется!"]))
            )
            attacker.last_move = raw_name
            return

        # --- Полевые ---
        effect_key = is_field_move(move["name"])
        if effect_key:
            await self._resolve_field_move(attacker, defender, move, effect_key, uid)
            attacker.last_move = raw_name
            return

        # --- Статусные ---
        if is_status_move(raw_name):
            await self._do_status_move(attacker, defender, move, uid)
            attacker.last_move = raw_name
            return

        # --- Обычный урон ---
        await self._resolve_attack(attacker, defender, move)
        attacker.last_move = raw_name

        # --- Pivot ---
        if is_pivot_move(raw_name):
            self.log_lines.append(
                f"🔄 **{attacker.name}** собирается отступить после атаки!"
            )
            await self._wait_for_switch(uid, reason="pivot")

    def _pre_move_check(self, mon: BattlePokemon) -> bool:
        if mon.status == "sleep":
            mon.status_counter -= 1
            if mon.status_counter <= 0:
                mon.status = "none"
                self.log_lines.append(msg.pick(msg.WAKE_UP).format(name=mon.name))
                return True
            self.log_lines.append(msg.pick(msg.SLEEP_SKIP).format(name=mon.name))
            return False

        if mon.status == "freeze":
            if random.random() < 0.2:
                mon.status = "none"
                self.log_lines.append(msg.pick(msg.THAW).format(name=mon.name))
                return True
            self.log_lines.append(msg.pick(msg.FROZEN_SKIP).format(name=mon.name))
            return False

        if mon.status == "paralysis" and random.random() < 0.25:
            self.log_lines.append(msg.pick(msg.PARALYSIS_SKIP).format(name=mon.name))
            return False

        if "infatuated" in mon.volatile:
            if random.random() < 0.5:
                self.log_lines.append(
                    msg.pick(msg.INFATUATED_SKIP).format(name=mon.name)
                )
                return False
            if random.random() < 0.3:
                mon.volatile.pop("infatuated", None)
                self.log_lines.append(
                    msg.pick(msg.INFATUATED_END).format(name=mon.name)
                )

        if "confused" in mon.volatile:
            mon.volatile["confused"] -= 1
            if mon.volatile["confused"] <= 0:
                mon.volatile.pop("confused", None)
                self.log_lines.append(msg.pick(msg.CONFUSED_END).format(name=mon.name))
            else:
                if random.random() < 0.33:
                    dmg = max(1, int(mon.max_hp / 8))
                    mon.take_damage(dmg)
                    self.log_lines.append(
                        msg.pick(msg.CONFUSED_SELF_HIT).format(
                            name=mon.name, dmg=dmg
                        )
                    )
                    return False

        return True

    async def _resolve_attack(
        self, attacker: BattlePokemon, defender: BattlePokemon, move: dict
    ) -> None:
        self.log_lines.append(
            msg.pick(msg.ATTACK_TEMPLATES).format(who=attacker.name, move=move["name"])
        )
        if defender.protect:
            self.log_lines.append(
                f"🛡️ **{defender.name}** блокирует атаку — Protect!"
            )
            return

        hit, _ = accuracy_check(attacker, defender, move, self.weather)
        if not hit:
            self.log_lines.append(
                msg.pick(msg.MISS_TEMPLATES).format(target=defender.name)
            )
            return

        raw_name = move.get("raw_name", "")
        crit_bonus = _crit_bonus(attacker)
        is_crit = crit_check(stage=crit_bonus, raw_name=raw_name)

        uid = self._me_uid(attacker)
        result = calc_damage(
            attacker, defender, move,
            defender_side=self.fields[self._other_player(uid)],
            attacker_side=self.fields[uid],
            weather=self.weather,
            crit=is_crit,
            crit_stage=crit_bonus,
        )

        immunity = result.get("ability_immunity")
        if immunity:
            effect = immunity.get("effect")
            ability = immunity.get("ability", "")
            if effect == "wonder_guard":
                self.log_lines.append(
                    msg.pick(msg.ABILITY_IMMUNITY_LINES.get(
                        "wonder-guard", ["🛡️ Wonder Guard!"]
                    )).format(name=defender.name)
                )
                return
            tmpl = msg.ABILITY_IMMUNITY_LINES.get(
                ability, ["🛡️ **{name}** невосприимчив!"]
            )
            self.log_lines.append(msg.pick(tmpl).format(name=defender.name))
            if immunity.get("heal"):
                self.log_lines.append(
                    f"💚 Восстановлено **{immunity['heal']}** HP."
                )
            if immunity.get("boost"):
                self.log_lines.append(
                    f"📈 {STAT_RU.get(immunity['boost'], immunity['boost'])} "
                    f"повышена!"
                )
            return

        if result["mult"] == 0:
            self.log_lines.append(
                msg.pick(msg.IMMUNE_TEMPLATES).format(target=defender.name)
            )
            return

        if defender.has_substitute:
            dmg = result["dmg"]
            if dmg >= defender.substitute_hp:
                defender.substitute_hp = 0
                self.log_lines.append(
                    msg.pick(msg.SUBSTITUTE_BREAK).format(name=defender.name)
                )
            else:
                defender.substitute_hp -= dmg
                self.log_lines.append(
                    msg.pick(msg.SUBSTITUTE_ABSORB).format(
                        name=defender.name, dmg=dmg
                    )
                )
            return

        if is_crit:
            self.log_lines.append(msg.pick(msg.CRIT_LINES))

        defender.take_damage(result["dmg"])
        self.log_lines.append(
            msg.pick(msg.HIT_TEMPLATES).format(target=defender.name, dmg=result["dmg"])
        )

        if result.get("sturdy_triggered"):
            self.log_lines.append(
                msg.pick(msg.ABILITY_STURDY_LINE).format(name=defender.name)
            )
        if result.get("multiscale_triggered"):
            self.log_lines.append(
                msg.pick(msg.ABILITY_MULTISCALE_LINE).format(name=defender.name)
            )

        lbl = damage_label(result["mult"])
        if lbl:
            self.log_lines.append(lbl)

    # ------------------------------------------------------------------ #
    #  СТАТУСНЫЕ АТАКИ
    # ------------------------------------------------------------------ #
    async def _do_status_move(
        self, attacker: BattlePokemon, defender: BattlePokemon,
        move: dict, uid: int
    ) -> None:
        raw = move.get("raw_name", "")
        data = get_status_move(raw)
        if not data:
            return

        self.log_lines.append(
            msg.pick(msg.ATTACK_TEMPLATES).format(who=attacker.name, move=move["name"])
        )

        acc = move.get("accuracy")
        target_name = data.get("target", "opponent")
        target = attacker if target_name == "self" else defender

        if target_name == "opponent" and defender.has_substitute:
            self.log_lines.append(
                msg.pick(msg.SUBSTITUTE_BLOCK).format(name=defender.name)
            )
            return

        if acc is not None and target_name == "opponent":
            chance = float(acc) / 100.0
            chance *= attacker.stage_value("accuracy")
            chance /= defender.stage_value("evasion")
            chance = max(0.05, min(1.0, chance))
            if random.random() >= chance:
                self.log_lines.append(
                    msg.pick(msg.MISS_TEMPLATES).format(target=defender.name)
                )
                return

        category = data.get("category")

        if category == "inflict":
            self._apply_status(target, data.get("status"), source=attacker)
        elif category in ("boost", "debuff"):
            self._change_stage(target, data["stat"], int(data["stages"]))
        elif category == "heal":
            await self._do_heal(data, attacker, uid)
        elif category == "substitute":
            self._do_substitute(attacker, data)
        elif category == "leech_seed":
            self._do_leech_seed(attacker, defender)
        elif category == "taunt":
            self._do_taunt(attacker, defender, data)
        elif category == "encore":
            self._do_encore(attacker, defender, data)
        elif category == "disable":
            self._do_disable(attacker, defender, data)
        else:
            self.log_lines.append(f"⚠️ Атака **{move['name']}** не сработала.")

    def _apply_status(
        self, target: BattlePokemon, status: Optional[str],
        source: Optional[BattlePokemon] = None,
    ) -> None:
        if not status:
            return

        immune_by_type = TYPE_STATUS_IMMUNITY.get(status, set())
        if any(t in immune_by_type for t in target.types):
            self.log_lines.append(
                f"🛡️ **{target.name}** не поддаётся эффекту ({status})."
            )
            return

        ability = (target.ability or "").lower()
        if ability in ABILITY_STATUS_IMMUNITY.get(status, set()):
            self.log_lines.append(
                f"🛡️ **{target.name}** защищён способностью."
            )
            return

        if status in ("confused", "infatuated"):
            if status in target.volatile:
                self.log_lines.append(f"⚠️ **{target.name}** уже под эффектом.")
                return

            if status == "infatuated":
                if source is None:
                    return
                if (source.gender == "genderless"
                        or target.gender == "genderless"
                        or source.gender == target.gender):
                    self.log_lines.append(
                        msg.pick(msg.INFATUATED_FAIL).format(name=target.name)
                    )
                    return

            turns = random.randint(2, 5) if status == "confused" else 5
            target.volatile[status] = turns
            tmpl = msg.STATUS_INFLICT.get(status)
            if tmpl:
                self.log_lines.append(msg.pick(tmpl).format(name=target.name))
            else:
                emoji = STATUS_EMOJI.get(status, "")
                self.log_lines.append(
                    f"{emoji} **{target.name}** — {STATUS_RU.get(status, status)}!"
                )
            return

        if target.status != "none":
            self.log_lines.append(f"⚠️ **{target.name}** уже имеет статус.")
            return

        target.status = status
        if status == "sleep":
            target.status_counter = random.randint(2, 4)
        elif status == "badly_poison":
            target.toxic_counter = 1
        else:
            target.status_counter = 0

        templates = msg.STATUS_INFLICT.get(status)
        if templates:
            self.log_lines.append(msg.pick(templates).format(name=target.name))
        else:
            self.log_lines.append(
                f"{STATUS_EMOJI.get(status, '')} "
                f"**{target.name}** — {STATUS_RU.get(status, status)}!"
            )

    def _change_stage(self, mon: BattlePokemon, stat: str, stages: int) -> None:
        if stat not in mon.stages:
            return
        old = mon.stages[stat]
        new = max(-6, min(6, old + stages))
        name = STAT_RU.get(stat, stat)

        if new == old:
            if stages > 0:
                self.log_lines.append(
                    f"⚠️ {name} **{mon.name}** уже на максимуме!"
                )
            else:
                self.log_lines.append(
                    f"⚠️ {name} **{mon.name}** уже на минимуме!"
                )
            return

        mon.stages[stat] = new
        if stages > 0:
            self.log_lines.append(f"📈 {name} **{mon.name}** повышена!")
        else:
            self.log_lines.append(f"📉 {name} **{mon.name}** понижена!")

    async def _do_heal(self, data: dict, attacker: BattlePokemon, uid: int) -> None:
        if data.get("cure_team"):
            if attacker.status != "none":
                attacker.status = "none"
                attacker.status_counter = 0
                attacker.toxic_counter = 0
                self.log_lines.append(f"✨ Статус **{attacker.name}** снят!")
            else:
                self.log_lines.append("✨ Нечего лечить.")
            return

        if data.get("self_status"):
            if attacker.status != "none":
                self.log_lines.append(
                    f"⚠️ **{attacker.name}** уже имеет статус."
                )
                return
            attacker.status = data["self_status"]
            attacker.status_counter = int(data.get("sleep_turns", 2))
            healed = attacker.heal(attacker.max_hp)
            self.log_lines.append(
                f"💤 **{attacker.name}** засыпает и восстанавливает "
                f"**{healed}** HP."
            )
            return

        fraction = int(data.get("fraction", 2))
        amount = max(1, attacker.max_hp // fraction)
        healed = attacker.heal(amount)
        if healed > 0:
            self.log_lines.append(
                f"💚 **{attacker.name}** восстанавливает **{healed}** HP."
            )
        else:
            self.log_lines.append(f"⚠️ **{attacker.name}** уже на полном HP.")

    # ------------------------------------------------------------------ #
    #  SUBSTITUTE / LEECH SEED / TAUNT / ENCORE / DISABLE
    # ------------------------------------------------------------------ #
    def _do_substitute(self, attacker: BattlePokemon, data: dict) -> None:
        if attacker.has_substitute:
            self.log_lines.append(
                msg.pick(msg.SUBSTITUTE_ALREADY).format(name=attacker.name)
            )
            return
        cost = max(1, attacker.max_hp // int(data.get("fraction", 4)))
        if attacker.hp <= cost:
            self.log_lines.append(
                msg.pick(msg.SUBSTITUTE_TOO_LOW).format(name=attacker.name)
            )
            return
        attacker.take_damage(cost)
        attacker.substitute_hp = cost
        self.log_lines.append(
            msg.pick(msg.SUBSTITUTE_CREATE).format(name=attacker.name, hp=cost)
        )

    def _do_leech_seed(
        self, attacker: BattlePokemon, defender: BattlePokemon
    ) -> None:
        if "grass" in defender.types:
            self.log_lines.append(
                f"🌱 **{defender.name}** не поддаётся Leech Seed (трава)."
            )
            return
        if defender.leech_seed:
            self.log_lines.append(
                msg.pick(msg.LEECH_SEED_ALREADY).format(name=defender.name)
            )
            return
        defender.leech_seed = True
        self.log_lines.append(
            msg.pick(msg.LEECH_SEED_INFLICT).format(name=defender.name)
        )

    def _do_taunt(
        self, attacker: BattlePokemon, defender: BattlePokemon, data: dict
    ) -> None:
        if defender.volatile.get("taunt", 0) > 0:
            self.log_lines.append(msg.pick(msg.TAUNT_ALREADY).format(name=defender.name))
            return
        turns = int(data.get("turns", 3))
        defender.volatile["taunt"] = turns
        self.log_lines.append(
            msg.pick(msg.TAUNT_INFLICT).format(name=defender.name)
        )

    def _do_encore(
        self, attacker: BattlePokemon, defender: BattlePokemon, data: dict
    ) -> None:
        if defender.volatile.get("encore", 0) > 0:
            self.log_lines.append(
                msg.pick(msg.ENCORE_ALREADY).format(name=defender.name)
            )
            return
        last = getattr(defender, "last_move", None)
        if not last:
            self.log_lines.append(
                msg.pick(msg.ENCORE_NO_MOVE).format(name=defender.name)
            )
            return
        turns = int(data.get("turns", 3))
        defender.volatile["encore"] = turns
        defender.encored_move = last
        self.log_lines.append(
            msg.pick(msg.ENCORE_INFLICT).format(
                name=defender.name, move=last.replace("-", " ").title()
            )
        )

    def _do_disable(
        self, attacker: BattlePokemon, defender: BattlePokemon, data: dict
    ) -> None:
        if defender.volatile.get("disable", 0) > 0:
            self.log_lines.append(
                msg.pick(msg.DISABLE_ALREADY).format(name=defender.name)
            )
            return
        last = getattr(defender, "last_move", None)
        if not last:
            self.log_lines.append(
                msg.pick(msg.DISABLE_NO_MOVE).format(name=defender.name)
            )
            return
        turns = int(data.get("turns", 4))
        defender.volatile["disable"] = turns
        defender.disabled_move = last
        self.log_lines.append(
            msg.pick(msg.DISABLE_INFLICT).format(
                name=defender.name, move=last.replace("-", " ").title()
            )
        )

    # ------------------------------------------------------------------ #
    #  ПОЛЕВЫЕ АТАКИ
    # ------------------------------------------------------------------ #
    async def _resolve_field_move(
        self, attacker: BattlePokemon, defender: BattlePokemon,
        move: dict, effect_key: str, uid: int
    ) -> None:
        self.log_lines.append(
            msg.pick(msg.ATTACK_TEMPLATES).format(who=attacker.name, move=move["name"])
        )
        if effect_key == "protect":
            attacker.protect = True
            self.log_lines.append(
                msg.pick(msg.PROTECT_LINES).format(who=attacker.name)
            )
            return

        opponent_id = self._other_player(uid)
        if effect_key in ("reflect", "light_screen", "tailwind"):
            self.log_lines.append(apply_field_move(effect_key, self.fields[uid]))
        elif effect_key in ("spikes", "toxic_spikes", "stealth_rock", "sticky_web"):
            self.log_lines.append(
                apply_field_move(effect_key, self.fields[opponent_id])
            )

    # ------------------------------------------------------------------ #
    #  СМЕНА / ПРЕДМЕТ
    # ------------------------------------------------------------------ #
    async def _do_switch(
        self, uid: int, new_idx: int, *, transfer_state: bool = False
    ) -> None:
        old = self.current.get(uid)

        saved_stages = dict(old.stages) if old and transfer_state else None
        saved_volatile = dict(old.volatile) if old and transfer_state else None
        saved_sub_hp = old.substitute_hp if old and transfer_state else 0

        if old:
            line = apply_switch_heal(old)
            if line:
                self.log_lines.append(line)
            line = apply_switch_cure(old)
            if line:
                self.log_lines.append(line)

        self._save_active_hp(uid)
        if not await self._load_active(uid, new_idx):
            self.log_lines.append("❌ Не удалось сменить покемона.")
            return

        new = self.current[uid]
        if saved_stages is not None:
            new.stages = saved_stages
        if saved_volatile is not None:
            new.volatile = saved_volatile
            new.substitute_hp = saved_sub_hp

        self.log_lines.append(
            msg.pick(msg.SWITCH_LINES).format(who=f"<@{uid}>", next_mon=new.name)
        )

        for line in apply_switch_in_hazards(new, self.fields[uid]):
            self.log_lines.append(line)

        for line in on_switch_in_ability(new):
            self.log_lines.append(line)

        if (new.ability or "").lower() == "intimidate":
            opp = self.current.get(self._other_player(uid))
            if opp:
                self.log_lines.append(apply_intimidate(opp))

        w = ability_weather_on_switch(new)
        if w and self.weather.kind != w:
            self.weather.set(w)
            self.log_lines.append(
                msg.pick(msg.WEATHER_LINES.get(w, ["Погода меняется!"]))
            )
        self._save_active_hp(uid)

    async def handle_switch_pick(
        self, uid: int, idx: int, reason: Optional[str] = None
    ) -> None:
        if self.finished:
            return
        await self._do_switch(uid, idx, transfer_state=(reason == "baton"))
        self.pending_switch.pop(uid, None)
        fut = self.switch_futures.pop(uid, None)
        if fut and not fut.done():
            fut.set_result(True)

    async def _wait_for_switch(self, uid: int, *, reason: str) -> None:
        self.pending_switch[uid] = reason
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self.switch_futures[uid] = fut

        reason_label = {
            "baton": "Baton Pass",
            "pivot": "после атаки",
            "faint": "твой покемон выбыл",
        }.get(reason, "смена")

        await self.channel.send(
            f"🔄 <@{uid}>, выбери, кто выйдет следующим ({reason_label})..."
        )
        await self.channel.send(view=SwitchView(self, uid, reason=reason))
        try:
            await asyncio.wait_for(fut, timeout=180)
            if self.finished:
                return
        except asyncio.TimeoutError:
            self.log_lines.append(
                f"⚠️ <@{uid}> не выбрал покемона вовремя — смена пропущена."
            )
            self.pending_switch.pop(uid, None)
        except Exception:
            log.exception("Ошибка при ожидании смены покемона")
            self.pending_switch.pop(uid, None)

    async def _do_item(self, uid: int, item_key: str) -> None:
        inv = self.inventories.get(uid, {})
        if inv.get(item_key, 0) <= 0:
            self.log_lines.append("⚠️ Предмета нет в инвентаре.")
            return
        mon = self.current[uid]
        log_line = apply_battle_item(item_key, mon)
        if log_line is None:
            self.log_lines.append("⚠️ Предмет не сработал.")
            return
        await take_item(uid, item_key, 1)
        inv[item_key] = max(0, inv.get(item_key, 1) - 1)
        self.log_lines.append(log_line)

        if item_key == "dire_hit":
            mon.crit_bonus = _crit_bonus(mon) + 1

    # ------------------------------------------------------------------ #
    #  КОНЕЦ ХОДА
    # ------------------------------------------------------------------ #
    async def _post_turn(self) -> None:
        leech_heals: dict[int, int] = {}

        for uid in self.players:
            mon = self.current.get(uid)
            if not mon or mon.fainted:
                continue
            events = apply_end_of_turn(mon, self.weather)
            for ev in events:
                t = ev["type"]
                if t == "tick_burn":
                    self.log_lines.append(
                        f"🟥 **{mon.name}** страдает от ожога (−{ev['dmg']} HP)."
                    )
                elif t == "tick_poison":
                    self.log_lines.append(
                        f"🟪 **{mon.name}** страдает от яда (−{ev['dmg']} HP)."
                    )
                elif t == "tick_badly_poison":
                    self.log_lines.append(
                        f"🟪 **{mon.name}** мучается от сильного яда "
                        f"(−{ev['dmg']} HP, счётчик ×{ev['counter']})."
                    )
                elif t == "tick_weather":
                    tmpl = msg.pick(
                        msg.WEATHER_TICK_LINES.get(ev["kind"], ["Погода бьёт {name}."])
                    )
                    self.log_lines.append(tmpl.format(name=mon.name, dmg=ev["dmg"]))
                elif t == "tick_leech_seed":
                    tmpl = msg.pick(msg.LEECH_SEED_TICK)
                    self.log_lines.append(tmpl.format(name=mon.name, dmg=ev["dmg"]))
                    leech_heals[uid] = leech_heals.get(uid, 0) + ev["dmg"]
                elif t == "heal_ability":
                    ab = ev["ability"]
                    tmpl = msg.pick(
                        msg.ABILITY_END_HEAL.get(
                            ab, ["💚 **{name}** восстанавливает {hp} HP."]
                        )
                    )
                    self.log_lines.append(
                        tmpl.format(name=mon.name, hp=ev["hp"])
                    )
                elif t == "hurt_ability":
                    ab = ev["ability"]
                    tmpl = msg.pick(
                        msg.ABILITY_END_HURT.get(
                            ab, ["⚠️ **{name}** теряет {dmg} HP ({ability})."]
                        )
                    )
                    self.log_lines.append(
                        tmpl.format(name=mon.name, dmg=ev["dmg"], ability=ab)
                    )
                elif t == "boost_ability":
                    ab = ev["ability"]
                    tmpl = msg.pick(
                        msg.ABILITY_END_BOOST.get(ab, ["📈 **{name}** усиливается!"])
                    )
                    self.log_lines.append(
                        tmpl.format(name=mon.name, stat=ev["stat"])
                    )

        for uid, healed in leech_heals.items():
            other_uid = self._other_player(uid)
            healer = self.current.get(other_uid)
            if healer and not healer.fainted:
                got = healer.heal(healed)
                if got > 0:
                    self.log_lines.append(
                        f"🌱 **{healer.name}** восстанавливает **{got}** HP "
                        f"от Leech Seed."
                    )

        for uid in self.players:
            mon = self.current.get(uid)
            if not mon:
                continue
            for key, end_msg in (
                ("taunt", msg.TAUNT_END),
                ("encore", msg.ENCORE_END),
                ("disable", msg.DISABLE_END),
            ):
                if key in mon.volatile:
                    mon.volatile[key] -= 1
                    if mon.volatile[key] <= 0:
                        mon.volatile.pop(key, None)
                        self.log_lines.append(
                            msg.pick(end_msg).format(name=mon.name)
                        )
                        if key == "encore":
                            mon.encored_move = None
                        if key == "disable":
                            mon.disabled_move = None

        for uid in self.players:
            self._save_active_hp(uid)
            self.fields[uid].tick()

        old = self.weather.kind
        self.weather.tick()
        if old != "none" and self.weather.kind == "none":
            self.log_lines.append(msg.pick(msg.WEATHER_END_LINES))

    async def _handle_faints(self) -> None:
        # --- Сообщения о выбывании ---
        for uid in self.players:
            mon = self.current.get(uid)
            if mon and mon.fainted:
                self._save_active_hp(uid)
                already = any(
                    mon.name in line and ("без сил" in line or "сознание" in line)
                    for line in self.log_lines[-3:]
                )
                if not already:
                    self.log_lines.append(
                        msg.pick(msg.FAINT_LINES).format(name=mon.name)
                    )

        # --- Проверка, у кого ещё есть живые ---
        alive: dict[int, bool] = {}
        for uid in self.players:
            alive[uid] = any(hp > 0 for hp in self.party_hp[uid].values())

        if not all(alive.values()):
            losers = [u for u, ok in alive.items() if not ok]
            winners = [u for u, ok in alive.items() if ok]
            if losers and winners:
                await self._end_battle(winners[0], losers[0])
            else:
                await self._end_battle(None, None)
            return

        # --- Показываем состояние боя после хода ---
        await self.send_main_message()

        # --- Принудительная смена после faint ---
        fainted_uids = [
            uid for uid in self.players
            if self.current.get(uid) and self.current[uid].fainted
        ]

        if fainted_uids:
            for uid in fainted_uids:
                if uid not in self.pending_switch:
                    other = self._other_player(uid)
                    await self.channel.send(
                        f"<@{other}>, ждём, пока соперник выберет покемона…"
                    )
                    await self._wait_for_switch(uid, reason="faint")

            # После всех смен — обновляем состояние и показываем новые кнопки
            await self.send_main_message()

        # --- Ход следующего раунда ---
        await self.send_move_views()

    # ------------------------------------------------------------------ #
    #  UI / ЛОГ
    # ------------------------------------------------------------------ #
    async def send_main_message(self) -> None:
        p1, p2 = self.players
        m1 = self.current[p1]
        m2 = self.current[p2]

        weather_str = self.weather.label
        if self.weather.kind != "none" and self.weather.turns > 0:
            weather_str += f" ({self.weather.turns})"

        embed = discord.Embed(
            title=f"⚔️ Ход {self.turn_number} — {weather_str}",
            color=0xE63946,
        )
        embed.add_field(
            name=f"👤 <@{p1}>",
            value=(
                f"**{m1.name}** • Ур. {m1.level}\n"
                f"HP: {m1.hp}/{m1.max_hp} {_hp_bar(m1)} {_status_emoji_str(m1)}\n"
                f"Способность: `{m1.ability or '—'}`\n"
                f"Поле: {' '.join(self.fields[p1].summary()) or '—'}"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"👤 <@{p2}>",
            value=(
                f"**{m2.name}** • Ур. {m2.level}\n"
                f"HP: {m2.hp}/{m2.max_hp} {_hp_bar(m2)} {_status_emoji_str(m2)}\n"
                f"Способность: `{m2.ability or '—'}`\n"
                f"Поле: {' '.join(self.fields[p2].summary()) or '—'}"
            ),
            inline=False,
        )
        if self.log_lines:
            embed.add_field(
                name="📜 Лог",
                value="\n".join(self.log_lines[-10:])[:1024],
                inline=False,
            )
        if m1.sprite:
            embed.set_thumbnail(url=m1.sprite)

        self.messages.append(await self.channel.send(embed=embed))

    async def send_move_views(self) -> None:
        for uid in self.players:
            if uid in self.pending_switch:
                continue
            attacker = self.current[uid]
            if attacker.fainted:
                continue
            embed = discord.Embed(
                title=f"🎯 Твой ход, <@{uid}>",
                description=f"**{attacker.name}** — выбери действие:",
                color=0x457B9D,
            )
            m = await self.channel.send(
                content=f"<@{uid}>",
                embed=embed,
                view=BattleView(self, uid),
            )
            self.views[uid] = m
            self.messages.append(m)

    async def _cleanup_views(self) -> None:
        for m in self.views.values():
            try:
                await m.edit(view=None)
            except discord.HTTPException:
                pass
        self.views.clear()

    # ------------------------------------------------------------------ #
    async def _end_battle(
        self, winner_id: Optional[int], loser_id: Optional[int]
    ) -> None:
        self.finished = True
        await self._cleanup_views()
        if winner_id and loser_id:
            embed = discord.Embed(
                title="🏁 Бой завершён!",
                description=(
                    f"🏆 Победитель: <@{winner_id}>\n"
                    f"💔 Проигравший: <@{loser_id}>"
                ),
                color=0x2A9D8F,
            )
            await inc_wins(winner_id)
            await inc_losses(loser_id)
        else:
            embed = discord.Embed(
                title="🏁 Ничья!",
                description="Оба тренера потеряли всех покемонов.",
                color=0x2A9D8F,
            )
        await self.channel.send(embed=embed)

    # ------------------------------------------------------------------ #
    async def force_end(self, reason: str) -> None:
        """Прерывает бой без начисления побед/поражений и без наград."""
        if self.finished:
            return
        self.finished = True

        await self._cleanup_views()

        # Разбудить тех, кто сейчас ждёт выбора покемона
        for uid, fut in list(self.switch_futures.items()):
            if not fut.done():
                fut.set_result(False)
        self.switch_futures.clear()
        self.pending_switch.clear()

        embed = discord.Embed(
            title="🏁 Бой прерван",
            description=reason,
            color=0xE63946,
        )
        await self.channel.send(embed=embed)


# ==========================================================================
#  ПРИГЛАШЕНИЕ
# ==========================================================================
class InviteView(discord.ui.View):
    def __init__(self, host: int, target: int, cog: "BattleCog"):
        super().__init__(timeout=60)
        self.host = host
        self.target = target
        self.cog = cog

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target:
            await interaction.response.send_message("Это не ваш вызов.", ephemeral=True)
            return
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        battle = Battle(interaction.channel, self.host, self.target)
        self.cog.active_battles[interaction.channel_id] = battle
        if not await battle.start():
            self.cog.active_battles.pop(interaction.channel_id, None)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target:
            await interaction.response.send_message("Это не ваш вызов.", ephemeral=True)
            return
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"❌ <@{self.target}> отклонил вызов.")


class BattleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_battles: dict[int, Battle] = {}

    @app_commands.command(name="battle", description="Вызвать игрока на бой")
    @app_commands.describe(user="Кого вызвать на бой")
    async def battle(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "Нельзя вызвать самого себя.", ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "Нельзя вызвать бота.", ephemeral=True
            )
            return
        if interaction.channel_id in self.active_battles:
            await interaction.response.send_message(
                "В этом канале уже идёт бой.", ephemeral=True
            )
            return

        p1 = await get_active_profile(interaction.user.id)
        p2 = await get_active_profile(user.id)
        if not p1 or p1["profile_type"] != "trainer":
            await interaction.response.send_message(
                "У вас нет активного тренера.", ephemeral=True
            )
            return
        if not p2 or p2["profile_type"] != "trainer":
            await interaction.response.send_message(
                f"У <@{user.id}> нет активного тренера.", ephemeral=True
            )
            return

        view = InviteView(interaction.user.id, user.id, self)
        embed = discord.Embed(
            title="⚔️ Вызов на бой!",
            description=(
                f"<@{interaction.user.id}> вызывает <@{user.id}> на бой!\n"
                f"У вас 60 секунд, чтобы принять."
            ),
            color=0xE63946,
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="battle_end",
        description="Завершить бой в этом канале без результатов (без побед и поражений)",
    )
    async def battle_end(self, interaction: discord.Interaction) -> None:
        battle = self.active_battles.get(interaction.channel_id)
        if battle is None:
            await interaction.response.send_message(
                "В этом канале нет активного боя.", ephemeral=True
            )
            return

        if battle.finished:
            self.active_battles.pop(interaction.channel_id, None)
            await interaction.response.send_message(
                "Бой уже завершён.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        await battle.force_end(
            f"Бой прерван по инициативе {interaction.user.mention}.\n"
            f"Побед и поражений никому не начислено."
        )
        self.active_battles.pop(interaction.channel_id, None)
        await interaction.followup.send(
            "✅ Бой завершён без результатов.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))
