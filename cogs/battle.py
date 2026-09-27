"""Боевая система: /battle @юзер — с погодой, полем, способностями, сменой."""
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import battle_messages as msg
import pokeapi_client
from battle_data import STATUS_EMOJI, damage_label
from battle_engine import (
    BattlePokemon,
    SideField,
    WeatherField,
    ability_weather_on_switch,
    accuracy_check,
    apply_end_of_turn,
    apply_field_move,
    apply_intimidate,
    apply_switch_in_hazards,
    calc_damage,
    crit_check,
    is_field_move,
    is_weather_move,
    on_switch_in_ability,
)
from database import get_active_profile, get_trainer, inc_losses, inc_wins
from pokeapi_client import PokeAPIError

log = logging.getLogger(__name__)


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
        "name": data["name"].title(),
        "types": data.get("types", []),
        "stats": data.get("stats", {}),
        "artwork": data.get("artwork"),
        "ability": ability,
        "item": mon.get("item"),
        "gender": mon.get("gender", "genderless"),
    }


async def _load_moves(move_names: list[str]) -> list[dict]:
    out = []
    for name in move_names[:4]:
        try:
            m = await pokeapi_client._fetch_json(
                f"https://pokeapi.co/api/v2/move/{name}"
            )
        except PokeAPIError:
            continue
        out.append({
            "name": name.replace("-", " ").title(),
            "raw_name": name,
            "power": m.get("power") or 0,
            "type": (m.get("type") or {}).get("name", "normal"),
            "accuracy": m.get("accuracy"),
            "damage_class": (m.get("damage_class") or {}).get("name", "physical"),
        })
    return out


def _hp_bar(mon: "BattlePokemon") -> str:
    ratio = mon.hp / mon.max_hp if mon.max_hp else 0
    filled = int(round(ratio * 10))
    return f"`{'█' * filled}{'░' * (10 - filled)}`"


# ==========================================================================
#                          ВЫБОР ПОКЕМОНА ДЛЯ СМЕНЫ
# ==========================================================================
class SwitchSelect(discord.ui.Select):
    def __init__(self, battle: "Battle", uid: int):
        self.battle = battle
        self.uid = uid
        options: list[discord.SelectOption] = []
        party = battle.parties[uid]
        current_id = battle.active_index[uid]
        for i, mon in enumerate(party):
            if i == current_id:
                continue
            bp = battle.party_hp[uid].get(i, 0)
            if bp <= 0:
                continue
            name = mon.get("nickname") or f"#{mon.get('species_id')}"
            options.append(
                discord.SelectOption(label=f"{name} • {bp} HP"[:100], value=str(i))
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
        await self.battle.switch_pokemon(interaction, self.uid, int(self.values[0]))


class SwitchView(discord.ui.View):
    def __init__(self, battle: "Battle", uid: int):
        super().__init__(timeout=60)
        self.add_item(SwitchSelect(battle, uid))


# ==========================================================================
#                          КНОПКИ АТАК
# ==========================================================================
class BattleMoveButton(discord.ui.Button):
    def __init__(self, battle: "Battle", owner: int, move: dict, idx: int):
        super().__init__(
            label=move["name"][:80],
            style=discord.ButtonStyle.primary,
            row=0 if idx < 2 else 1,
        )
        self.battle = battle
        self.owner = owner
        self.move = move

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner:
            await interaction.response.send_message("Это не ваш ход.", ephemeral=True)
            return
        await self.battle.submit_move(interaction, self.owner, self.move)


class BattleView(discord.ui.View):
    def __init__(self, battle: "Battle", owner: int):
        super().__init__(timeout=180)
        self.battle = battle
        self.owner = owner

        attacker = battle.current[owner]
        for i, move in enumerate(attacker.moves[:4]):
            self.add_item(BattleMoveButton(battle, owner, move, i))

        switch_btn = discord.ui.Button(
            label="Сменить покемона",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            row=2,
        )
        switch_btn.callback = self._on_switch
        self.add_item(switch_btn)

    async def _on_switch(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner:
            await interaction.response.send_message("Это не ваш ход.", ephemeral=True)
            return
        view = SwitchView(self.battle, self.owner)
        await interaction.response.send_message(
            "Кого выпустить?", view=view, ephemeral=True
        )


# ==========================================================================
#                            САМ БОЙ
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
        self.messages: list[discord.Message] = []
        self.log_lines: list[str] = []
        self.views: dict[int, BattleView] = {}
        self.finished = False

    # ------------------------------------------------------------------ #
    async def start(self) -> bool:
        for uid in self.players:
            t = await get_trainer(uid)
            if not t["party"]:
                await self.channel.send(f"❌ <@{uid}> — нет покемонов в команде.")
                return False
            self.parties[uid] = list(t["party"])

        for uid in self.players:
            ok = await self._load_active(uid, 0)
            if not ok:
                await self.channel.send(f"❌ Не удалось загрузить покемона у <@{uid}>.")
                return False
            for i, mon in enumerate(self.parties[uid]):
                if i not in self.party_hp[uid]:
                    self.party_hp[uid][i] = self._calc_max_hp(mon)

        await self.channel.send(
            f"⚔️ **Бой начался!** <@{self.players[0]}> против <@{self.players[1]}>"
        )

        self.log_lines = []
        # Switch-in способности
        for uid in self.players:
            mon = self.current[uid]
            for line in on_switch_in_ability(mon):
                self.log_lines.append(line)
            if (mon.ability or "").lower() == "intimidate":
                opponent_id = self._other(mon)
                opp = self.current.get(opponent_id)
                if opp:
                    self.log_lines.append(apply_intimidate(opp))
            # Авто-погода от способности
            w = ability_weather_on_switch(mon)
            if w:
                self.weather.set(w)
                self.log_lines.append(
                    msg.pick(msg.WEATHER_LINES.get(w, ["Погода меняется!"]))
                )

        await self.send_main_message()
        await self.send_move_views()
        return True

    # ------------------------------------------------------------------ #
    def _calc_max_hp(self, mon: dict) -> int:
        return 100

    async def _load_active(self, uid: int, idx: int) -> bool:
        party = self.parties[uid]
        if idx < 0 or idx >= len(party):
            return False
        mon = party[idx]
        data = await _load_mon_data(mon)
        moves = await _load_moves(mon.get("moves", []))
        if not data:
            return False

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

    # ------------------------------------------------------------------ #
    async def send_main_message(self) -> None:
        p1, p2 = self.players
        m1 = self.current[p1]
        m2 = self.current[p2]

        weather_str = self.weather.label
        if self.weather.kind != "none" and self.weather.turns > 0:
            weather_str += f" ({self.weather.turns})"

        embed = discord.Embed(
            title=f"⚔️ Состояние боя — {weather_str}",
            color=0xE63946,
        )
        embed.add_field(
            name=f"👤 <@{p1}>",
            value=(
                f"**{m1.name}** • Ур. {m1.level}\n"
                f"HP: {m1.hp}/{m1.max_hp} {_hp_bar(m1)}"
                f"{STATUS_EMOJI.get(m1.status, '')}\n"
                f"Способность: `{m1.ability or '—'}`\n"
                f"Поле: {' '.join(self.fields[p1].summary()) or '—'}"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"👤 <@{p2}>",
            value=(
                f"**{m2.name}** • Ур. {m2.level}\n"
                f"HP: {m2.hp}/{m2.max_hp} {_hp_bar(m2)}"
                f"{STATUS_EMOJI.get(m2.status, '')}\n"
                f"Способность: `{m2.ability or '—'}`\n"
                f"Поле: {' '.join(self.fields[p2].summary()) or '—'}"
            ),
            inline=False,
        )
        if self.log_lines:
            embed.add_field(
                name="📜 Лог",
                value="\n".join(self.log_lines[-8:]),
                inline=False,
            )
        if m1.sprite:
            embed.set_thumbnail(url=m1.sprite)

        m = await self.channel.send(embed=embed)
        self.messages.append(m)

    async def send_move_views(self) -> None:
        for uid in self.players:
            attacker = self.current[uid]
            view = BattleView(self, uid)
            embed = discord.Embed(
                title=f"🎯 Твой ход, <@{uid}>",
                description=f"**{attacker.name}** — выбери действие:",
                color=0x457B9D,
            )
            m = await self.channel.send(content=f"<@{uid}>", embed=embed, view=view)
            self.views[uid] = view
            self.messages.append(m)

    # ------------------------------------------------------------------ #
    async def _cleanup_views(self) -> None:
        for m in self.views.values():
            try:
                await m.edit(view=None)
            except discord.HTTPException:
                pass
        self.views.clear()

    # ------------------------------------------------------------------ #
    async def submit_move(
        self, interaction: discord.Interaction, uid: int, move: dict
    ) -> None:
        if self.finished:
            await interaction.response.send_message("Бой уже завершён.", ephemeral=True)
            return

        await interaction.response.defer()
        await self._cleanup_views()

        attacker = self.current[uid]
        opponent_id = self.players[0] if uid == self.players[1] else self.players[1]
        defender = self.current[opponent_id]

        self.log_lines = []

        skip_line = self._status_precheck(attacker)
        if skip_line:
            self.log_lines.append(skip_line)
        else:
            weather_key = is_weather_move(move.get("raw_name", move["name"]))
            effect_key = is_field_move(move["name"])

            if weather_key:
                await self._resolve_weather_move(attacker, weather_key)
            elif effect_key:
                await self._resolve_field_move(
                    attacker, defender, move, effect_key, uid, opponent_id
                )
            else:
                await self._resolve_attack(attacker, defender, move)

        # End-of-turn: статусы + погода
        for mon in (attacker, defender):
            events = apply_end_of_turn(mon, self.weather)
            for ev in events:
                if ev["type"] == "tick_burn":
                    self.log_lines.append(
                        f"🟥 **{mon.name}** страдает от ожога (−{ev['dmg']} HP)."
                    )
                elif ev["type"] == "tick_poison":
                    self.log_lines.append(
                        f"🟪 **{mon.name}** страдает от яда (−{ev['dmg']} HP)."
                    )
                elif ev["type"] == "tick_weather":
                    tmpl = msg.pick(
                        msg.WEATHER_TICK_LINES.get(ev["kind"], ["Погода бьёт {name}."])
                    )
                    self.log_lines.append(tmpl.format(name=mon.name, dmg=ev["dmg"]))
                elif ev["type"] == "heal_weather":
                    tmpl = msg.pick(
                        msg.WEATHER_HEAL_LINES.get(ev["kind"], ["{name} восстанавливает HP."])
                    )
                    self.log_lines.append(tmpl.format(name=mon.name, hp=ev["hp"]))

        attacker.protect = False
        defender.protect = False

        self._save_active_hp(uid)
        self._save_active_hp(opponent_id)
        self.fields[uid].tick()
        self.fields[opponent_id].tick()

        # Погода тикает раз в ход
        old_weather = self.weather.kind
        self.weather.tick()
        if old_weather != "none" and self.weather.kind == "none":
            self.log_lines.append(msg.pick(msg.WEATHER_END_LINES))

        await self._handle_faints()

    # ------------------------------------------------------------------ #
    async def _resolve_weather_move(self, attacker: BattlePokemon, kind: str) -> None:
        self.weather.set(kind)
        self.log_lines.append(
            msg.pick(msg.WEATHER_LINES.get(kind, ["Погода меняется!"]))
        )

    async def _resolve_field_move(
        self,
        attacker: BattlePokemon,
        defender: BattlePokemon,
        move: dict,
        effect_key: str,
        uid: int,
        opponent_id: int,
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

        if effect_key in ("reflect", "light_screen", "tailwind"):
            line = apply_field_move(effect_key, self.fields[uid])
            self.log_lines.append(line)
            return

        if effect_key in ("spikes", "toxic_spikes", "stealth_rock", "sticky_web"):
            line = apply_field_move(effect_key, self.fields[opponent_id])
            self.log_lines.append(line)
            return

    # ------------------------------------------------------------------ #
    def _status_precheck(self, attacker: BattlePokemon) -> Optional[str]:
        if attacker.status == "sleep":
            attacker.status_counter -= 1
            if attacker.status_counter <= 0:
                attacker.status = "none"
                return msg.pick(msg.WAKE_UP).format(name=attacker.name)
            return msg.pick(msg.SLEEP_SKIP).format(name=attacker.name)
        if attacker.status == "freeze":
            if random.random() < 0.2:
                attacker.status = "none"
                return msg.pick(msg.THAW).format(name=attacker.name)
            return msg.pick(msg.FROZEN_SKIP).format(name=attacker.name)
        if attacker.status == "paralysis" and random.random() < 0.25:
            return msg.pick(msg.PARALYSIS_SKIP).format(name=attacker.name)
        return None

    # ------------------------------------------------------------------ #
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

        is_crit = crit_check()
        result = calc_damage(
            attacker, defender, move,
            defender_side=self.fields[self._other(attacker)],
            attacker_side=self.fields[self._me(attacker)],
            weather=self.weather,
            crit=is_crit,
        )
        mult = result["mult"]

        if mult == 0:
            self.log_lines.append(
                msg.pick(msg.IMMUNE_TEMPLATES).format(target=defender.name)
            )
            return

        if is_crit:
            self.log_lines.append(msg.pick(msg.CRIT_LINES))

        defender.take_damage(result["dmg"])
        self.log_lines.append(
            msg.pick(msg.HIT_TEMPLATES).format(
                target=defender.name, dmg=result["dmg"]
            )
        )
        lbl = damage_label(mult)
        if lbl:
            self.log_lines.append(lbl)

    # ------------------------------------------------------------------ #
    def _me(self, mon: BattlePokemon) -> int:
        for uid, m in self.current.items():
            if m is mon:
                return uid
        return self.players[0]

    def _other(self, mon: BattlePokemon) -> int:
        me = self._me(mon)
        return self.players[1] if me == self.players[0] else self.players[0]

    # ------------------------------------------------------------------ #
    async def switch_pokemon(
        self, interaction: discord.Interaction, uid: int, new_idx: int
    ) -> None:
        if self.finished:
            await interaction.response.send_message("Бой уже завершён.", ephemeral=True)
            return

        await interaction.response.defer()
        await self._cleanup_views()

        self._save_active_hp(uid)
        if not await self._load_active(uid, new_idx):
            await self.channel.send(f"❌ Не удалось сменить покемона у <@{uid}>.")
            return

        new = self.current[uid]
        self.log_lines = [
            msg.pick(msg.SWITCH_LINES).format(who=f"<@{uid}>", next_mon=new.name)
        ]

        for line in apply_switch_in_hazards(new, self.fields[uid]):
            self.log_lines.append(line)

        for line in on_switch_in_ability(new):
            self.log_lines.append(line)
        if (new.ability or "").lower() == "intimidate":
            opponent_id = self.players[0] if uid == self.players[1] else self.players[1]
            opp = self.current.get(opponent_id)
            if opp:
                self.log_lines.append(apply_intimidate(opp))

        # Погода от способности
        w = ability_weather_on_switch(new)
        if w and self.weather.kind != w:
            self.weather.set(w)
            self.log_lines.append(msg.pick(msg.WEATHER_LINES.get(w, ["Погода меняется!"])))

        if new.fainted:
            self.log_lines.append(msg.pick(msg.FAINT_LINES).format(name=new.name))

        self._save_active_hp(uid)
        await self._handle_faints()

    # ------------------------------------------------------------------ #
    async def _handle_faints(self) -> None:
        for uid in self.players:
            mon = self.current.get(uid)
            if mon and mon.fainted:
                self._save_active_hp(uid)
                if not any(
                    "теряет сознание" in l or "падает без сил" in l for l in self.log_lines
                ):
                    self.log_lines.append(
                        msg.pick(msg.FAINT_LINES).format(name=mon.name)
                    )

        alive_status: dict[int, bool] = {}
        for uid in self.players:
            alive = any(hp > 0 for hp in self.party_hp[uid].values())
            alive_status[uid] = alive

        if all(alive_status.values()):
            await self.send_main_message()

            someone_switching = False
            for uid in self.players:
                mon = self.current.get(uid)
                if mon and mon.fainted:
                    someone_switching = True
                    view = SwitchView(self, uid)
                    await self.channel.send(
                        f"<@{uid}>, твой покемон выбыл. Выбери следующего:",
                        view=view,
                    )

            if not someone_switching:
                await self.send_move_views()
            return

        losers = [uid for uid, alive in alive_status.items() if not alive]
        winners = [uid for uid, alive in alive_status.items() if alive]

        if losers and winners:
            await self._end_battle(winners[0], losers[0])
        else:
            await self._end_battle(None, None)

    # ------------------------------------------------------------------ #
    async def _end_battle(self, winner_id: Optional[int], loser_id: Optional[int]) -> None:
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


# ==========================================================================
#                          ПРИГЛАШЕНИЕ
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
        await interaction.response.send_message(embed=view and view or None)
        # Правильный вызов:
        await interaction.edit_original_response(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BattleCog(bot))
