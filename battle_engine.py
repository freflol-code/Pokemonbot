"""Движок боя: покемон, урон, статусы, поле, погода."""
from __future__ import annotations

import random
from typing import Any, Optional

from battle_data import (
    WEATHER_ABILITIES,
    WEATHER_ACCURACY_MULT,
    WEATHER_DAMAGE_MULT,
    WEATHER_DURATION_DEFAULT,
    WEATHER_DURATION_EXTENDED,
    WEATHER_LABEL,
    WEATHER_MOVES,
    WEATHER_ROCKS,
    WEATHER_TICK_DAMAGE,
    damage_label,
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

        self.status: str = "none"
        self.status_counter: int = 0
        self.stages: dict[str, int] = {
            "attack": 0, "defense": 0, "sp_attack": 0,
            "sp_defense": 0, "speed": 0,
            "accuracy": 0, "evasion": 0,
        }
        self.protect: bool = False
        self.flinched: bool = False

    # ------------------------------------------------------------------ #
    def _calc_hp(self, base: int) -> int:
        return int(2 * base * self.level / 100) + self.level + 10

    def _calc_stat(self, base: int, key: str) -> int:
        val = int(2 * base * self.level / 100) + 5
        val = int(val * nature_multiplier(self.nature)[key])
        return max(1, val)

    # ------------------------------------------------------------------ #
    @property
    def fainted(self) -> bool:
        return self.hp <= 0

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

    def effective_speed(self, weather: "WeatherField") -> int:
        base = self.stats["speed"] * self.stage_value("speed")
        if (self.ability or "").lower() == "swift-swim" and weather.kind == "rain":
            base *= 2
        if (self.ability or "").lower() == "chlorophyll" and weather.kind == "sunny":
            base *= 2
        if (self.ability or "").lower() == "sand-rush" and weather.kind == "sandstorm":
            base *= 2
        if (self.ability or "").lower() == "slush-rush" and weather.kind == "snow":
            base *= 2
        return int(base)

    def reset_stages(self) -> None:
        for k in self.stages:
            self.stages[k] = 0

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
            "stages": dict(self.stages),
            "sprite": self.sprite,
            "ability": self.ability,
            "item": self.item,
            "gender": self.gender,
        }


# ==========================================================================
#  ПОЛЕ БОЯ (одна сторона)
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
        """Возвращает 100 если атака всегда попадает в этой погоде."""
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
            mon.status = "poison"
            lines.append(f"☠️ **{mon.name}** отравлен Toxic Spikes.")

    if field.sticky_web:
        if "flying" not in mon.types and (mon.ability or "").lower() != "levitate":
            mon.stages["speed"] = max(-6, mon.stages["speed"] - 1)
            lines.append(f"🕸️ **{mon.name}** замедлен Sticky Web (−1 Speed).")

    return lines


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
) -> dict:
    power = int(move.get("power") or 0)
    move_type = move.get("type", "normal")
    damage_class = move.get("damage_class", "physical")

    if power <= 0:
        return {"dmg": 0, "mult": 1.0, "crit": False}

    if damage_class == "physical":
        atk = attacker.stats["attack"] * attacker.stage_value("attack")
        dfn = defender.stats["defense"] * defender.stage_value("defense")
        if defender_side.reflect > 0:
            dfn *= 2
    else:
        atk = attacker.stats["sp_attack"] * attacker.stage_value("sp_attack")
        dfn = defender.stats["sp_defense"] * defender.stage_value("sp_defense")
        if defender_side.light_screen > 0:
            dfn *= 2

    if crit:
        atk *= 1.5

    mult = get_type_multiplier(move_type, defender.types)
    if mult == 0:
        return {"dmg": 0, "mult": 0, "crit": crit}

    if move_type == "ground" and (defender.ability or "").lower() == "levitate":
        return {"dmg": 0, "mult": 0, "crit": crit}

    stab = 1.5 if move_type in attacker.types else 1.0
    weather_mult = weather.damage_mult(move_type)

    # Защита от песка: Rock получает больше SP DEF (уже не критично)
    base = (
        ((2 * attacker.level / 5 + 2) * power * atk / dfn) / 50
    ) + 2

    rand = random.uniform(0.85, 1.0)
    dmg = int(base * mult * stab * weather_mult * rand)

    return {"dmg": max(1, dmg), "mult": mult, "crit": crit}


def accuracy_check(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: dict,
    weather: WeatherField,
) -> tuple[bool, float]:
    # Погодные override
    override = weather.accuracy_override(move["name"])
    acc = move.get("accuracy") if override is None else override
    if acc is None:
        return True, 1.0
    acc_pct = float(acc) / 100.0
    acc_pct *= attacker.stage_value("accuracy")
    acc_pct /= defender.stage_value("evasion")
    acc_pct = max(0.05, min(1.0, acc_pct))
    return random.random() < acc_pct, acc_pct


def crit_check(stage: int = 0) -> bool:
    chances = {0: 1 / 24, 1: 1 / 8, 2: 1 / 2}
    return random.random() < chances.get(max(0, min(2, stage)), 1 / 24)


# ==========================================================================
#  СПОСОБНОСТИ
# ==========================================================================
def on_switch_in_ability(mon: BattlePokemon) -> list[str]:
    lines: list[str] = []
    ability = (mon.ability or "").lower()
    if ability == "intimidate":
        lines.append(f"⚡ **{mon.name}** запугивает соперника — Intimidate.")
    return lines


def ability_weather_on_switch(mon: BattlePokemon) -> Optional[str]:
    """Возвращает погоду, которую вызывает способность."""
    return WEATHER_ABILITIES.get((mon.ability or "").lower())


def apply_intimidate(target: BattlePokemon) -> str:
    target.stages["attack"] = max(-6, target.stages["attack"] - 1)
    return f"⚡ Атака **{target.name}** понижена (Intimidate)."


# ==========================================================================
#  СТАТУСЫ + ПОГОДА В КОНЦЕ ХОДА
# ==========================================================================
def apply_end_of_turn(
    mon: BattlePokemon, weather: WeatherField
) -> list[dict]:
    """Возвращает список событий за конец хода."""
    events: list[dict] = []
    if mon.fainted:
        return events

    # Статусы
    if mon.status == "burn":
        dmg = max(1, mon.max_hp // 16)
        mon.take_damage(dmg)
        events.append({"type": "tick_burn", "dmg": dmg})

    elif mon.status == "poison":
        dmg = max(1, mon.max_hp // 8)
        mon.take_damage(dmg)
        events.append({"type": "tick_poison", "dmg": dmg})

    # Погода
    config = WEATHER_TICK_DAMAGE.get(weather.kind)
    if config and not mon.fainted:
        immune = config.get("immune_types", [])
        if not any(t in immune for t in mon.types):
            # Magic Guard / Overcoat иммунитет
            ability = (mon.ability or "").lower()
            if ability not in ("magic-guard", "overcoat", "sand-veil", "sand-rush",
                               "snow-cloak", "ice-body"):
                frac = config.get("fraction", 16)
                dmg = max(1, mon.max_hp // frac)
                mon.take_damage(dmg)
                events.append({
                    "type": "tick_weather",
                    "dmg": dmg,
                    "kind": weather.kind,
                })
        # Ice Body / Rain Dish / Dry Skin — лечат
        ability = (mon.ability or "").lower()
        if ability == "ice-body" and weather.kind == "snow":
            healed = mon.heal(max(1, mon.max_hp // 16))
            if healed:
                events.append({"type": "heal_weather", "hp": healed, "kind": weather.kind})
        elif ability == "rain-dish" and weather.kind == "rain":
            healed = mon.heal(max(1, mon.max_hp // 16))
            if healed:
                events.append({"type": "heal_weather", "hp": healed, "kind": weather.kind})

    return events
