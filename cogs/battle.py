"""Боевая система: /battle @юзер + кнопки."""
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
    get_type_multiplier,
)
from battle_engine import (
    BattlePokemon,
    SideField,
    accuracy_check,
    apply_end_of_turn,
    calc_damage,
    crit_check,
)
from database import get_active_profile, get_trainer
from pokeapi_client import PokeAPIError

log = logging.getLogger(__name__)


async def _load_mon_data(mon: dict) -> Optional[dict]:
    """Догружает данные покемона из PokéAPI + способности/спрайт."""
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
            "power": m.get("power") or 0,
            "type": (m.get("type") or {}).get("name", "normal"),
            "accuracy": m.get("accuracy"),
            "damage_class": (m.get("damage_class") or {}).get("name", "physical"),
        })
    return out


class BattleView(discord.ui.View):
    """Кнопки атак для конкретного игрока."""

    def __init__(self, battle: "Battle", owner: int):
        super().__init__(timeout=180)
        self.battle = battle
        self.owner = owner

        attacker = battle.current[owner]
        for i, move in enumerate(attacker.moves[:4]):
            self.add_item(BattleMoveButton(battle, owner, move, i))


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
            await interaction.response.send_message(
                "Это не ваш ход.", ephemeral=True
            )
            return
        await self.battle.submit_move(interaction, self.owner, self.move)


class Battle:
    def __init__(self, channel: discord.TextChannel, p1: int, p2: int):
        self.channel = channel
        self.players = [p1, p2]
        self.fields = {p1: SideField(), p2: SideField()}
        self.current: dict[int, BattlePokemon] = {}
        self.parties: dict[int, list[dict]] = {}
        self.active_index: dict[int, int] = {p1: 0, p2: 0}
        self.messages: list[discord.Message] = []
        self.log_lines: list[str] = []
        self.views: dict[int, BattleView] = {}
        self.ready_views = False
        self.turn_winner: Optional[int] = None
        self.finished = False

    # ------------------------------------------------------------------ #
    async def start(self) -> bool:
        for uid in self.players:
            t = await get_trainer(uid)
            if not t["party"]:
                await self.channel.send(
                    f"❌ <@{uid}> — нет покемонов в команде."
                )
                return False
            self.parties[uid] = list(t["party"])

        for uid in self.players:
            mon = self.parties[uid][0]
            data = await _load_mon_data(mon)
            moves = await _load_moves(mon.get("moves", []))
            if not data:
                await self.channel.send(f"❌ Не удалось загрузить покемона у <@{uid}>.")
                return False
            self.current[uid] = BattlePokemon(
                data, mon.get("level", 5), moves, nature=mon.get("nature", "hardy")
            )

        await self.channel.send(
            f"⚔️ **Бой начался!** <@{self.players[0]}> против <@{self.players[1]}>"
        )
        await self.send_main_message()
        await self.send_move_views()
        return True

    # ------------------------------------------------------------------ #
    async def send_main_message(self) -> None:
        p1, p2 = self.players
        m1 = self.current[p1]
        m2 = self.current[p2]

        embed = discord.Embed(title="⚔️ Состояние боя", color=0xE63946)
        embed.add_field(
            name=f"👤 <@{p1}>",
            value=(
                f"**{m1.name}** • Ур. {m1.level}\n"
                f"HP: {m1.hp}/{m1.max_hp} {self.hp_bar(m1)}"
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
                f"HP: {m2.hp}/{m2.max_hp} {self.hp_bar(m2)}"
                f"{STATUS_EMOJI.get(m2.status, '')}\n"
                f"Способность: `{m2.ability or '—'}`\n"
                f"Поле: {' '.join(self.fields[p2].summary()) or '—'}"
            ),
            inline=False,
        )
        if self.log_lines:
            embed.add_field(
                name="📜 Лог",
                value="\n".join(self.log_lines[-6:]),
                inline=False,
            )
        if m1.sprite:
            embed.set_thumbnail(url=m1.sprite)

        m = await self.channel.send(embed=embed)
        self.messages.append(m)

    # ------------------------------------------------------------------ #
    async def send_move_views(self) -> None:
        for uid in self.players:
            attacker = self.current[uid]
            view = BattleView(self, uid)
            embed = discord.Embed(
                title=f"🎯 Твой ход, <@{uid}>",
                description=f"**{attacker.name}** — выбери атаку:",
                color=0x457B9D,
            )
            m = await self.channel.send(
                content=f"<@{uid}>", embed=embed, view=view
            )
            self.views[uid] = view
            self.messages.append(m)

    # ------------------------------------------------------------------ #
    @staticmethod
    def hp_bar(mon: BattlePokemon) -> str:
        ratio = mon.hp / mon.max_hp if mon.max_hp else 0
        filled = int(round(ratio * 10))
        return f"`{'█' * filled}{'░' * (10 - filled)}`"

    # ------------------------------------------------------------------ #
    async def submit_move(
        self, interaction: discord.Interaction, uid: int, move: dict
    ) -> None:
        if self.finished:
            await interaction.response.send_message("Бой уже завершён.", ephemeral=True)
            return

        attacker = self.current[uid]
        opponent_id = self.players[0] if uid == self.players[1] else self.players[1]
        defender = self.current[opponent_id]

        # Проверка статусов
        skip_line = None
        if attacker.status == "sleep":
            attacker.status_counter -= 1
            if attacker.status_counter <= 0:
                attacker.status = "none"
                skip_line = msg.pick(msg.WAKE_UP).format(name=attacker.name)
            else:
                skip_line = msg.pick(msg.SLEEP_SKIP).format(name=attacker.name)
        elif attacker.status == "freeze":
            if random.random() < 0.2:
                attacker.status = "none"
                skip_line = msg.pick(msg.THAW).format(name=attacker.name)
            else:
                skip_line = msg.pick(msg.FROZEN_SKIP).format(name=attacker.name)
        elif attacker.status == "paralysis" and random.random() < 0.25:
            skip_line = msg.pick(msg.PARALYSIS_SKIP).format(name=attacker.name)

        self.log_lines = []

        if skip_line:
            self.log_lines.append(skip_line)
        else:
            await self._resolve_attack(attacker, defender, move)

        # End-of-turn
        for mon in (attacker, defender):
            tick = apply_end_of_turn(mon)
            if tick:
                if tick["type"] == "tick_burn":
                    self.log_lines.append(
                        f"🟥 **{mon.name}** страдает от ожога (−{tick['dmg']} HP)."
                    )
                elif tick["type"] == "tick_poison":
                    self.log_lines.append(
                        f"🟪 **{mon.name}** страдает от яда (−{tick['dmg']} HP)."
                    )
            if mon.fainted:
                self.log_lines.append(msg.pick(msg.FAINT_LINES).format(name=mon.name))

        self.fields[uid].tick()
        self.fields[opponent_id].tick()

        # Проверка конца боя
        if defender.fainted or attacker.fainted:
            await self.end_battle(interaction, loser_id=opponent_id if defender.fainted else uid)
            return

        # Отвечаем в лог
        for m in self.views.values():
            try:
                await m.edit(view=None)
            except discord.HTTPException:
                pass
        self.views.clear()

        await interaction.response.defer()
        await self.send_main_message()
        await self.send_move_views()

    # ------------------------------------------------------------------ #
    async def _resolve_attack(
        self, attacker: BattlePokemon, defender: BattlePokemon, move: dict
    ) -> None:
        self.log_lines.append(
            msg.pick(msg.ATTACK_TEMPLATES).format(who=attacker.name, move=move["name"])
        )

        hit, _ = accuracy_check(attacker, defender, move)
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
    async def end_battle(self, interaction: discord.Interaction, loser_id: int) -> None:
        self.finished = True
        winner_id = self.players[0] if loser_id == self.players[1] else self.players[1]

        embed = discord.Embed(
            title="🏁 Бой завершён!",
            description=(
                f"🏆 Победитель: <@{winner_id}>\n"
                f"💔 Проигравший: <@{loser_id}>"
            ),
            color=0x2A9D8F,
        )
        await self.channel.send(embed=embed)

        # Обновляем БД: победы/поражения
        from database import inc_losses, inc_wins
        await inc_wins(winner_id)
        await inc_losses(loser_id)

        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass


class Battle(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_battles: dict[int, Battle] = {}

    @app_commands.command(
        name="battle",
        description="Вызвать игрока на бой",
    )
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


class InviteView(discord.ui.View):
    def __init__(self, host: int, target: int, cog: Battle):
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
        await interaction.followup.send(
            f"❌ <@{self.target}> отклонил вызов."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Battle(bot))