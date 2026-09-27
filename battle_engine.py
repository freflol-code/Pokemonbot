"""Движок боя: покемон, урон, статусы, поле, погода, предметы, способности."""
from __future__ import annotations

import random
from typing import Any, Optional

from battle_data import (
    ABILITY_ATTACK_MULT,
    ABILITY_DAMAGE_TAKEN_MULT,
    ABILITY_DEFENSE_MULT,
    ABILITY_IMMUNITY_BOOST,
    ABILITY_OUTGOING_MULT,
    ABILITY_PERSISTING_BOOST,
    ABILITY_TYPE_IMMUNITY,
    BATON_PASS_MOVES,
    CRIT_CHANCES,
    END_OF_TURN_ABILITIES,
    END_TURN_BOOST_ABILITIES,
    HALVE_AT_FULL_HP,
    INDIRECT_DAMAGE_IMMUNE,
    PIVOT_MOVES,
    STURDY_ABILITIES,
    SWITCH_CURE_ABILITIES,
    SWITCH_HEAL_ABILITIES,
    WEATHER_ABILITIES,
    WEATHER_ACCURACY_MULT,
    WEATHER_DAMAGE_MULT,
    WEATHER_DURATION_DEFAULT,
    WEATHER_DURATION_EXTENDED,
    WEATHER_IMMUNE,
    WEATHER_LABEL,
    WEATHER_MOVES,
    WEATHER_TICK_DAMAGE,
    WONDER_GUARD,
    damage_label,
    get_attack_mult,
    get_crit_stage,
    get_damage_taken_mult,
    get_defense_mult,
    get_type_immunity,
    get_type_multiplier,
    nature_multiplier,
    stage_mult,
)


# ==========================================================================
#  СОСТОЯНИЕ ПОКЕМОНА В БОЮ
# ==========================================================================
class BattlePokemon:
    def __init__(self, data: dict, level: int, moves: list[dict], nature: str = "hardy"):
        self.instance_id: str = data.get("instance_id", "")
        self.name: str = (data.get("nickname") or data.get("name", "?"))
        self.species_name: str = data.get("name", "?")
        self.types: list[str] = data.get("types", [])
        self.ability: Optional[str] = data.get("ability")
        self.item: Optional[str] = data.get("item")
        self.level: int = max(1, min(100, level))
        self.nature: str = (nature or "hardy").lower()
        self.moves: list[dict] = moves
        self.gender: str = data.get("gender", "genderless")
        self.sprite: Optional[str] = data.get("artwork") or data.get("sprite")

        stats_base: dict[str, int] = data.get("stats", {}) or {}
        self.max_hp = self._calc_hp(stats_base.get("hp", 60))
        self.hp = self.max_hp
        self.stats = {
            "attack":     self._calc_stat(stats_base.get("attack", 60), "attack"),
            "defense":    self._calc_stat(stats_base.get("defense", 60), "defense"),
            "sp_attack":  self._calc_stat(stats_base.get("special-attack", 60), "sp_attack"),
            "sp_defense": self._calc_stat(stats_base.get("special-defense", 60), "sp_defense"),
            "speed":      self._calc_stat(stats_base.get("speed", 60), "speed"),
        }

        # Основной статус (один за раз)
        self.status: str = "none"
        self.status_counter: int = 0          # для badly_poison — растёт, для sleep — уменьшается
        self.toxic_counter: int = 0           # отдельный счётчик для badly_poison

        # Волатильные статусы (можно совмещать)
        self.volatile: dict[str, int] = {}    # {status: remaining_turns}
        self.substitute_hp: int = 0           # HP заменителя
        self.leech_seed: bool = False
        self.flash_fire_active: bool = False  # persisting boost от Flash Fire

        # Стадии статов
        self.stages: dict[str, int] = {
            "attack": 0, "defense": 0, "sp_attack": 0,
            "sp_defense": 0, "speed": 0,
            "accuracy": 0, "evasion": 0,
        }

        self.protect: bool = False
        self.flinched: bool = False

        # Для Encore / Disable — последняя использованная атака
        self.last_move: Optional[str] = None
        self.disabled_move: Optional[str] = None

    def _calc_hp(self, base: int) -> int:
        return int(2 * base * self.level / 100) + self.level + 10

    def _calc_stat(self, base: int, key: str) -> int:
        val = int(2 * base * self.level / 100) + 5
        val = int(val * nature_multiplier(self.nature)[key])
        return max(1, val)

    @property
    def fainted(self) -> bool:
        return self.hp <= 0

    @property
    def has_substitute(self) -> bool:
        return self.substitute_hp > 0

    def heal(self, amount: int) -> int:
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    def take_damage(self, dmg: int) -> int:
        old = self.hp
        self.hp = max(0, self.hp - dmg)
        return old - self.hp

    def stage_value(self, key: str) -> float:
        return stage_mult(self.stages.get(key, 0))

    def effective_speed(self) -> float:
        """Скорость с учётом стадии и паралича (×0.5)."""
        base = self.stats["speed"] * self.stage_value("speed")
        if self.status == "paralysis":
            base *= 0.5
        return base

    def reset_stages(self) -> None:
        for k in self.stages:
            self.stages[k] = 0

    def reset_volatile(self) -> None:
        """Сброс волатильных статусов (не переносится Baton Pass)."""
        self.volatile.clear()
        self.substitute_hp = 0
        self.leech_seed = False
        self.flash_fire_active = False
        self.disabled_move = None

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "name": self.name,
            "species_name": self.species_name,
            "types": self.types,
            "level": self.level,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "status": self.status,
            "volatile": dict(self.volatile),
            "substitute_hp": self.substitute_hp,
            "leech_seed": self.leech_seed,
            "flash_fire_active": self.flash_fire_active,
            "stages": dict(self.stages),
            "sprite": self.sprite,
            "ability": self.ability,
            "item": self.item,
            "gender": self.gender,
        }


# ==========================================================================
#  ПОЛЕ БОЯ
# ==========================================================================
class SideField:
    def __init__(self) -> None:
        self.reflect: int = 0
        self.light_screen: int = 0
        self.tailwind: int = 0
        self.spikes: int = 0
        self.toxic_spikes: int = 0
        self.stealth_rock: bool = False
        self.sticky_web: bool = False

    def tick(self) -> None:
        for k in ("reflect", "light_screen", "tailwind"):
            v = getattr(self, k)
            if v > 0:
                setattr(self, k, v - 1)

    def summary(self) -> list[str]:
        out = []
        if self.reflect > 0:
            out.append(f"🛡️ Reflect ({self.reflect})")
        if self.light_screen > 0:
            out.append(f"✨ Light Screen ({self.light_screen})")
        if self.tailwind > 0:
            out.append(f"💨 Tailwind ({self.tailwind})")
        if self.spikes > 0:
            out.append(f"🌵 Spikes ×{self.spikes}")
        if self.toxic_spikes > 0:
            out.append(f"☠️ Toxic Spikes ×{self.toxic_spikes}")
        if self.stealth_rock:
            out.append("🪨 Stealth Rock")
        if self.sticky_web:
            out.append("🕸️ Sticky Web")
        return out


# ==========================================================================
#  ПОГОДА
# ==========================================================================
class WeatherField:
    def __init__(self) -> None:
        self.kind: str = "none"
        self.turns: int = 0

    def set(self, kind: str, *, extended: bool = False) -> None:
        self.kind = kind
        self.turns = WEATHER_DURATION_EXTENDED if extended else WEATHER_DURATION_DEFAULT

    def tick(self) -> None:
        if self.turns > 0:
            self.turns -= 1
            if self.turns <= 0:
                self.kind = "none"

    @property
    def label(self) -> str:
        return WEATHER_LABEL.get(self.kind, self.kind)

    def damage_mult(self, move_type: str) -> float:
        return WEATHER_DAMAGE_MULT.get(self.kind, {}).get(move_type, 1.0)

    def accuracy_override(self, move_name: str) -> Optional[int]:
        low = move_name.lower().replace(" ", "-")
        if low in WEATHER_ACCURACY_MULT.get(self.kind, {}):
            return 100
        return None


# ==========================================================================
#  ПОЛЕВЫЕ ЭФФЕКТЫ
# ==========================================================================
FIELD_MOVES = {
    "reflect":            "reflect",
    "light screen":       "light_screen",
    "tailwind":           "tailwind",
    "spikes":             "spikes",
    "toxic spikes":       "toxic_spikes",
    "stealth rock":       "stealth_rock",
    "sticky web":         "sticky_web",
    "protect":            "protect",
}

FIELD_DURATION = {
    "reflect":      5,
    "light_screen": 5,
    "tailwind":     4,
}


def is_field_move(move_name: str) -> Optional[str]:
    low = move_name.lower().replace("-", " ").strip()
    return FIELD_MOVES.get(low)


def is_weather_move(move_name: str) -> Optional[str]:
    low = move_name.lower().replace(" ", "-").strip()
    return WEATHER_MOVES.get(low)


def is_baton_pass_move(move_name: str) -> bool:
    return move_name.lower().replace(" ", "-").strip() in BATON_PASS_MOVES


def is_pivot_move(move_name: str) -> bool:
    return move_name.lower().replace(" ", "-").strip() in PIVOT_MOVES


def apply_field_move(effect_key: str, side: SideField) -> str:
    if effect_key == "reflect":
        side.reflect = FIELD_DURATION["reflect"]
        return "🛡️ На стороне появился **Reflect** (5 ходов)."
    if effect_key == "light_screen":
        side.light_screen = FIELD_DURATION["light_screen"]
        return "✨ На стороне появился **Light Screen** (5 ходов)."
    if effect_key == "tailwind":
        side.tailwind = FIELD_DURATION["tailwind"]
        return "💨 **Tailwind** ускоряет союзников (4 хода)."
    if effect_key == "spikes":
        if side.spikes < 3:
            side.spikes += 1
            return f"🌵 На поле соперника **Spikes** ×{side.spikes}."
        return "🌵 Spikes уже на максимуме (×3)."
    if effect_key == "toxic_spikes":
        if side.toxic_spikes < 2:
            side.toxic_spikes += 1
            return f"☠️ На поле соперника **Toxic Spikes** ×{side.toxic_spikes}."
        return "☠️ Toxic Spikes уже на максимуме (×2)."
    if effect_key == "stealth_rock":
        side.stealth_rock = True
        return "🪨 На поле соперника **Stealth Rock**."
    if effect_key == "sticky_web":
        side.sticky_web = True
        return "🕸️ На поле соперника **Sticky Web**."
    return ""


def apply_switch_in_hazards(mon: BattlePokemon, field: SideField) -> list[str]:
    lines: list[str] = []

    if field.stealth_rock:
        mult = 1.0
        for t in mon.types:
            if t in ("fire", "flying", "bug", "ice"):
                mult *= 2
            elif t in ("fighting", "ground", "steel"):
                mult *= 2
        dmg = max(1, int(mon.max_hp * mult / 8))
        mon.take_damage(dmg)
        lines.append(f"🪨 **{mon.name}** ранен осколками Stealth Rock (−{dmg} HP).")

    if field.spikes > 0:
        parts = {1: 8, 2: 6, 3: 4}
        dmg = max(1, mon.max_hp // parts.get(field.spikes, 8))
        mon.take_damage(dmg)
        lines.append(
            f"🌵 **{mon.name}** наступает на Spikes ×{field.spikes} (−{dmg} HP)."
        )

    if field.toxic_spikes > 0 and mon.status == "none":
        if not ("poison" in mon.types or "steel" in mon.types or "flying" in mon.types):
            mon.status = "badly_poison"
            mon.toxic_counter = 1
            lines.append(f"☠️ **{mon.name}** отравлен Toxic Spikes (растёт).")

    if field.sticky_web:
        if "flying" not in mon.types and (mon.ability or "").lower() != "levitate":
            mon.stages["speed"] = max(-6, mon.stages["speed"] - 1)
            lines.append(f"🕸️ **{mon.name}** замедлен Sticky Web (−1 Speed).")

    return lines


# ==========================================================================
#  ПРОВЕРКА ТИП-ИММУНИТЕТОВ ОТ СПОСОБНОСТЕЙ
# ==========================================================================
def check_ability_type_immunity(
    attacker: BattlePokemon, defender: BattlePokemon, move_type: str
) -> Optional[dict]:
    """Возвращает {"effect": ..., "boost": ..., "heal": ...} если сработал иммунитет.

    Либо None, если иммунитета нет.
    """
    ability = (defender.ability or "").lower()
    entry = ABILITY_TYPE_IMMUNITY.get(ability)
    if not entry:
        return None
    immune_type, effect = entry
    if immune_type != move_type:
        return None

    result: dict = {"effect": effect, "ability": ability}

    if effect == "heal":
        healed = defender.heal(max(1, defender.max_hp // 4))
        result["heal"] = healed
    elif effect == "boost":
        stat = ABILITY_IMMUNITY_BOOST.get(ability)
        if stat:
            old = defender.stages.get(stat, 0)
            defender.stages[stat] = min(6, old + 1)
            result["boost"] = stat
        if ability in ABILITY_PERSISTING_BOOST:
            defender.flash_fire_active = True

    return result


# ==========================================================================
#  РАСЧЁТ УРОНА
# ==========================================================================
def calc_damage(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: dict,
    *,
    defender_side: SideField,
    attacker_side: SideField,
    weather: WeatherField,
    crit: bool = False,
    crit_stage: int = 0,
) -> dict:
    """Полная формула урона с учётом способностей, статусов и крит-стадий.

    Возвращает dict:
        dmg, mult, crit, ability_immunity, sturdy_triggered, multiscale_triggered
    """
    power = int(move.get("power") or 0)
    move_type = move.get("type", "normal")
    damage_class = move.get("damage_class", "physical")

    if power <= 0:
        return {"dmg": 0, "mult": 1.0, "crit": False}

    # --- Тип-иммунитет от способности (Volt Absorb, Flash Fire и т.д.) ---
    immunity = check_ability_type_immunity(attacker, defender, move_type)
    if immunity:
        return {
            "dmg": 0,
            "mult": 0,
            "crit": False,
            "ability_immunity": immunity,
        }

    # --- Wonder Guard: пропускает только суперэффективные атаки ---
    if (defender.ability or "").lower() == WONDER_GUARD:
        type_mult_raw = get_type_multiplier(move_type, defender.types)
        if type_mult_raw < 2:
            return {
                "dmg": 0,
                "mult": 0,
                "crit": False,
                "ability_immunity": {
                    "effect": "wonder_guard",
                    "ability": "wonder-guard",
                },
            }

    # --- Атака ---
    if damage_class == "physical":
        atk = attacker.stats["attack"] * attacker.stage_value("attack")

        # Ожог снижает физическую атаку вдвое
        if attacker.status == "burn":
            atk *= 0.5

        # Guts: при статусе ×1.5
        atk *= get_attack_mult(
            attacker.ability or "", attacker.status != "none", attacker.status
        )

        dfn = defender.stats["defense"] * defender.stage_value("defense")
        dfn *= get_defense_mult(defender.ability or "", defender.status != "none")
        if defender_side.reflect > 0:
            dfn *= 2
    else:
        atk = attacker.stats["sp_attack"] * attacker.stage_value("sp_attack")
        atk *= get_attack_mult(
            attacker.ability or "", attacker.status != "none", attacker.status
        )

        dfn = defender.stats["sp_defense"] * defender.stage_value("sp_defense")
        dfn *= get_defense_mult(defender.ability or "", defender.status != "none")
        if defender_side.light_screen > 0:
            dfn *= 2

    # Flash Fire активен — Fire-атаки ×1.5
    if attacker.flash_fire_active and move_type == "fire":
        atk *= 1.5

    if crit:
        # Крит игнорирует негативные стадии атакующего и позитивные защитника
        atk = attacker.stats[
            "attack" if damage_class == "physical" else "sp_attack"
        ] * max(1.0, attacker.stage_value(
            "attack" if damage_class == "physical" else "sp_attack"
        ))
        if attacker.status == "burn":
            atk *= 0.5
        atk *= get_attack_mult(
            attacker.ability or "", attacker.status != "none", attacker.status
        )
        dfn = defender.stats[
            "defense" if damage_class == "physical" else "sp_defense"
        ] * min(1.0, defender.stage_value(
            "defense" if damage_class == "physical" else "sp_defense"
        ))
        dfn *= get_defense_mult(defender.ability or "", defender.status != "none")
        atk *= 1.5

    atk = max(1.0, atk)
    dfn = max(1.0, dfn)

    mult = get_type_multiplier(move_type, defender.types)
    if mult == 0:
        return {"dmg": 0, "mult": 0, "crit": crit}

    # Levitate обрабатывается через ABILITY_TYPE_IMMUNITY, но оставим fallback
    if move_type == "ground" and (defender.ability or "").lower() == "levitate":
        return {"dmg": 0, "mult": 0, "crit": crit}

    # STAB
    stab = 1.5 if move_type in attacker.types else 1.0
    # Adaptability: STAB ×2
    if (attacker.ability or "").lower() == "adaptability" and move_type in attacker.types:
        stab = 2.0

    # Погодный множитель
    weather_mult = weather.damage_mult(move_type)

    # --- Универсальные модификаторы атакующего ---
    outgoing = 1.0
    atk_ab = (attacker.ability or "").lower()
    if atk_ab == "technician" and power <= 60:
        outgoing *= 1.5
    if atk_ab == "tinted-lens" and mult < 1.0:
        outgoing *= 2.0

    # --- Универсальные модификаторы защитника ---
    incoming = 1.0
    incoming *= get_damage_taken_mult(defender.ability or "", move_type, damage_class)
    def_ab = (defender.ability or "").lower()
    if def_ab in ("filter", "solid-rock", "prism-armor") and mult > 1.0:
        incoming *= 0.75

    # --- Базовая формула ---
    base = (
        ((2 * attacker.level / 5 + 2) * power * atk / dfn) / 50
    ) + 2

    rand = random.uniform(0.85, 1.0)
    dmg = base * mult * stab * weather_mult * rand * outgoing * incoming
    dmg = int(dmg)

    # --- Multiscale / Shadow Shield: ÷2 при полном HP ---
    multiscale_triggered = False
    if (defender.ability or "").lower() in HALVE_AT_FULL_HP:
        if defender.hp == defender.max_hp:
            dmg = max(1, dmg // 2)
            multiscale_triggered = True

    # --- Sturdy: не даёт упасть ниже 1 HP с полного HP ---
    sturdy_triggered = False
    if (defender.ability or "").lower() in STURDY_ABILITIES:
        if defender.hp == defender.max_hp and dmg >= defender.hp:
            dmg = max(1, defender.hp - 1)
            sturdy_triggered = True

    return {
        "dmg": max(1, dmg),
        "mult": mult,
        "crit": crit,
        "multiscale_triggered": multiscale_triggered,
        "sturdy_triggered": sturdy_triggered,
    }


def accuracy_check(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: dict,
    weather: WeatherField,
) -> tuple[bool, float]:
    override = weather.accuracy_override(move["name"])
    acc = move.get("accuracy") if override is None else override
    if acc is None:
        return True, 1.0
    acc_pct = float(acc) / 100.0
    acc_pct *= attacker.stage_value("accuracy")
    acc_pct /= defender.stage_value("evasion")
    acc_pct = max(0.05, min(1.0, acc_pct))
    return random.random() < acc_pct, acc_pct


def crit_check(stage: int = 0, raw_name: str = "") -> bool:
    """Проверка крита с учётом high-crit атак.

    stage — внешние бонусы (Scope Lens, Super Luck, Focus Energy и т.д.).
    """
    total = get_crit_stage(raw_name, extra=stage)
    chance = CRIT_CHANCES.get(total, 1 / 24)
    return random.random() < chance


# ==========================================================================
#  СПОСОБНОСТИ
# ==========================================================================
def on_switch_in_ability(mon: BattlePokemon) -> list[str]:
    lines: list[str] = []
    ability = (mon.ability or "").lower()
    if ability == "intimidate":
        lines.append(f"⚡ **{mon.name}** запугивает соперника — Intimidate.")
    if ability == "download":
        lines.append(f"📡 **{mon.name}** сканирует соперника — Download.")
    return lines


def ability_weather_on_switch(mon: BattlePokemon) -> Optional[str]:
    return WEATHER_ABILITIES.get((mon.ability or "").lower())


def apply_intimidate(target: BattlePokemon) -> str:
    target.stages["attack"] = max(-6, target.stages["attack"] - 1)
    return f"⚡ Атака **{target.name}** понижена (Intimidate)."


def apply_switch_heal(mon: BattlePokemon) -> Optional[str]:
    """Regenerator при смене — лечит 1/3 HP."""
    ability = (mon.ability or "").lower()
    if ability in SWITCH_HEAL_ABILITIES and not mon.fainted:
        amount = max(1, int(mon.max_hp * SWITCH_HEAL_ABILITIES[ability]))
        healed = mon.heal(amount)
        if healed > 0:
            return f"💚 **{mon.name}** восстанавливает {healed} HP (Regenerator)."
    return None


def apply_switch_cure(mon: BattlePokemon) -> Optional[str]:
    """Natural Cure при смене — снимает статус."""
    ability = (mon.ability or "").lower()
    if ability in SWITCH_CURE_ABILITIES and mon.status != "none":
        old = mon.status
        mon.status = "none"
        mon.status_counter = 0
        mon.toxic_counter = 0
        return f"✨ **{mon.name}** избавляется от статуса ({old})."
    return None


# ==========================================================================
#  СТАТУСЫ + ПОГОДА + СПОСОБНОСТИ В КОНЦЕ ХОДА
# ==========================================================================
def apply_end_of_turn(mon: BattlePokemon, weather: WeatherField) -> list[dict]:
    """Возвращает список событий для лога.

    События:
        tick_burn, tick_poison, tick_badly_poison, tick_weather,
        tick_leech_seed, heal_ability, hurt_ability, boost_ability
    """
    events: list[dict] = []
    if mon.fainted:
        return events

    ability = (mon.ability or "").lower()
    indirect_immune = ability in INDIRECT_DAMAGE_IMMUNE

    # --- Ожог ---
    if mon.status == "burn" and not indirect_immune:
        dmg = max(1, mon.max_hp // 16)
        mon.take_damage(dmg)
        events.append({"type": "tick_burn", "dmg": dmg})

    # --- Обычное отравление ---
    elif mon.status == "poison" and not indirect_immune:
        dmg = max(1, mon.max_hp // 8)
        mon.take_damage(dmg)
        events.append({"type": "tick_poison", "dmg": dmg})

    # --- Сильное отравление (нарастающее) ---
    elif mon.status == "badly_poison" and not indirect_immune:
        mon.toxic_counter = max(1, mon.toxic_counter)
        dmg = max(1, mon.max_hp * mon.toxic_counter // 16)
        mon.take_damage(dmg)
        mon.toxic_counter += 1
        events.append({"type": "tick_badly_poison", "dmg": dmg,
                       "counter": mon.toxic_counter - 1})

    # --- Погодный тик-дамаг ---
    config = WEATHER_TICK_DAMAGE.get(weather.kind)
    if config and not mon.fainted and not indirect_immune:
        immune = config.get("immune_types", [])
        if not any(t in immune for t in mon.types):
            if ability not in WEATHER_IMMUNE:
                frac = config.get("fraction", 16)
                dmg = max(1, mon.max_hp // frac)
                mon.take_damage(dmg)
                events.append({
                    "type": "tick_weather",
                    "dmg": dmg,
                    "kind": weather.kind,
                })

    # --- Leech Seed ---
    if mon.leech_seed and not mon.fainted and not indirect_immune:
        dmg = max(1, mon.max_hp // 8)
        mon.take_damage(dmg)
        events.append({"type": "tick_leech_seed", "dmg": dmg})

    # --- End-of-turn способности (Rain Dish, Ice Body, Dry Skin, Solar Power) ---
    entry = END_OF_TURN_ABILITIES.get(ability)
    if entry and not mon.fainted:
        if entry.get("weather") == weather.kind and "fraction" in entry:
            amount = max(1, mon.max_hp // entry["fraction"])
            healed = mon.heal(amount)
            if healed > 0:
                events.append({"type": "heal_ability", "hp": healed,
                               "ability": ability})
        if entry.get("hurt_weather") == weather.kind and "fraction" in entry:
            dmg = max(1, mon.max_hp // entry["fraction"])
            mon.take_damage(dmg)
            events.append({"type": "hurt_ability", "dmg": dmg,
                           "ability": ability})
        if entry.get("hurt_sunny") and weather.kind == "sunny":
            dmg = max(1, mon.max_hp // 8)
            mon.take_damage(dmg)
            events.append({"type": "hurt_ability", "dmg": dmg,
                           "ability": ability})

    # --- Speed Boost / Moody ---
    boost_stat = END_TURN_BOOST_ABILITIES.get(ability)
    if boost_stat and not mon.fainted:
        if boost_stat == "random":
            boost_stat = random.choice(
                ["attack", "defense", "sp_attack", "sp_defense", "speed"]
            )
        old = mon.stages.get(boost_stat, 0)
        if old < 6:
            mon.stages[boost_stat] = old + 1
            events.append({"type": "boost_ability", "stat": boost_stat,
                           "ability": ability})

    return events


# ==========================================================================
#  ПРЕДМЕТЫ В БОЮ
# ==========================================================================
BATTLE_ITEMS: dict[str, dict] = {
    # Зелья
    "potion":         {"category": "heal", "amount": 20,   "name": "Зелье"},
    "super_potion":   {"category": "heal", "amount": 50,   "name": "Супер-зелье"},
    "hyper_potion":   {"category": "heal", "amount": 120,  "name": "Гипер-зелье"},
    "max_potion":     {"category": "heal", "amount": 9999, "name": "Макс-зелье"},
    "fresh_water":    {"category": "heal", "amount": 30,   "name": "Свежая вода"},
    "soda_pop":       {"category": "heal", "amount": 50,   "name": "Газировка"},
    "lemonade":       {"category": "heal", "amount": 70,   "name": "Лимонад"},
    "moomoo_milk":    {"category": "heal", "amount": 100,  "name": "Молоко Му-Му"},
    "full_restore":   {"category": "full_heal",            "name": "Полное восстановление"},
    "max_honey":      {"category": "full_heal",            "name": "Макс-мёд"},

    # Статусы
    "antidote":       {"category": "cure_status",          "name": "Антидот"},
    "full_heal":      {"category": "cure_status",          "name": "Полное лечение"},
    "lum_berry":      {"category": "cure_status",          "name": "Ягода Лум"},

    # Оживитель
    "revive":         {"category": "revive", "hp_pct": 0.5, "name": "Оживитель"},
    "max_revive":     {"category": "revive", "hp_pct": 1.0, "name": "Макс-оживитель"},
    "revival_herb":   {"category": "revive", "hp_pct": 1.0, "name": "Трава возрождения"},

    # X-предметы
    "x_attack":       {"category": "boost", "stat": "attack",    "stages": 1, "name": "X Атака"},
    "x_defense":      {"category": "boost", "stat": "defense",   "stages": 1, "name": "X Защита"},
    "x_sp_atk":       {"category": "boost", "stat": "sp_attack", "stages": 1, "name": "X Спец. Атака"},
    "x_sp_def":       {"category": "boost", "stat": "sp_defense","stages": 1, "name": "X Спец. Защита"},
    "x_speed":        {"category": "boost", "stat": "speed",     "stages": 1, "name": "X Скорость"},
    "x_accuracy":     {"category": "boost", "stat": "accuracy",  "stages": 1, "name": "X Точность"},
    "dire_hit":       {"category": "crit_boost",                 "name": "Dire Hit"},
}


def is_battle_item(item_key: str) -> bool:
    return item_key in BATTLE_ITEMS


def apply_battle_item(
    item_key: str,
    target: BattlePokemon,
) -> Optional[str]:
    """Применяет предмет к покемону. Возвращает строку для лога или None."""
    data = BATTLE_ITEMS.get(item_key)
    if not data:
        return None

    cat = data["category"]

    if cat == "heal":
        if target.fainted:
            return None
        healed = target.heal(int(data["amount"]))
        if healed <= 0:
            return f"⚠️ **{target.name}** уже с полным HP."
        return f"💊 **{target.name}** восстанавливает **{healed}** HP ({data['name']})."

    if cat == "full_heal":
        if target.fainted:
            return None
        healed = target.heal(target.max_hp)
        target.status = "none"
        target.status_counter = 0
        target.toxic_counter = 0
        target.volatile.clear()
        return f"💚 **{target.name}** полностью восстановлен ({data['name']})."

    if cat == "cure_status":
        if target.status == "none" and not target.volatile:
            return f"⚠️ У **{target.name}** нет статуса."
        target.status = "none"
        target.status_counter = 0
        target.toxic_counter = 0
        target.volatile.clear()
        return f"✨ Статус **{target.name}** снят ({data['name']})."

    if cat == "revive":
        if not target.fainted:
            return f"⚠️ **{target.name}** не выбыл."
        target.hp = max(1, int(target.max_hp * float(data["hp_pct"])))
        return f"💫 **{target.name}** возрождён с **{target.hp}** HP ({data['name']})."

    if cat == "boost":
        stat = data["stat"]
        target.stages[stat] = min(6, target.stages[stat] + int(data["stages"]))
        return f"📈 **{stat}** покемона **{target.name}** повышен ({data['name']})."

    if cat == "crit_boost":
        # Считаем как +1 крит-стадию — вернём строку, а в battle.py прибавим к счётчику
        return f"🎯 Шанс крита **{target.name}** повышен ({data['name']})."

    return None
