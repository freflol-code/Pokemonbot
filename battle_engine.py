"""Движок боя: состояние покемона, урон, статусы, поле, полевые эффекты."""
from __future__ import annotations

import random
from typing import Any, Optional

from battle_data import (
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
        self.protect: bool = False   # активен ли Protect в этом ходу
        self.flinched: bool = False  # пропуск хода

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
        self.spikes: int = 0            # 0-3
        self.toxic_spikes: int = 0      # 0-2
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
#  ПОЛЕВЫЕ ЭФФЕКТЫ — распознавание и применение
# ==========================================================================

# Названия в PokéAPI, которые мы считаем «полевыми»
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

# Продолжительность (ходов)
FIELD_DURATION = {
    "reflect":      5,
    "light_screen": 5,
    "tailwind":     4,
}


def is_field_move(move_name: str) -> Optional[str]:
    """Возвращает ключ полевого эффекта или None."""
    low = move_name.lower().replace("-", " ").strip()
    return FIELD_MOVES.get(low)


def apply_field_move(
    effect_key: str,
    side: SideField,
    *,
    target_side: Optional[SideField] = None,
) -> str:
    """Применяет полевой эффект. Возвращает строку для лога."""
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


def apply_switch_in_hazards(
    mon: BattlePokemon,
    field: SideField,
) -> list[str]:
    """Применяет урон/эффекты от шипов при появлении покемона."""
    lines: list[str] = []

    if field.stealth_rock:
        # Урон: 1/8, 1/4, 1/2 от типа
        from battle_data import TYPE_CHART
        mult = 1.0
        for t in mon.types:
            if t == "fire" or t == "flying" or t == "bug" or t == "ice":
                mult *= 2
            elif t == "fighting" or t == "ground" or t == "steel":
                mult *= 2
        dmg = max(1, int(mon.max_hp * mult / 8))
        mon.take_damage(dmg)
        lines.append(f"🪨 **{mon.name}** ранен осколками Stealth Rock (−{dmg} HP).")

    if field.spikes > 0:
        # Урон: 1/8, 1/6, 1/4 от max HP
        parts = {1: 8, 2: 6, 3: 4}
        dmg = max(1, mon.max_hp // parts.get(field.spikes, 8))
        mon.take_damage(dmg)
        lines.append(
            f"🌵 **{mon.name}** наступает на Spikes ×{field.spikes} (−{dmg} HP)."
        )

    if field.toxic_spikes > 0 and mon.status == "none":
        # Покемоны Poison/Steel/Flying иммунны
        if "poison" in mon.types or "steel" in mon.types or "flying" in mon.types:
            pass
        elif field.toxic_spikes >= 2:
            mon.status = "poison"
            lines.append(f"☠️ **{mon.name}** отравлен Toxic Spikes.")
        else:
            mon.status = "poison"
            lines.append(f"☠️ **{mon.name}** отравлен Toxic Spikes.")

    if field.sticky_web:
        # Замедление: −1 speed
        if "flying" not in mon.types and "levitate" != (mon.ability or "").lower():
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

    # Способность Levitate — иммунитет к Ground
    if (
        move_type == "ground"
        and (defender.ability or "").lower() == "levitate"
    ):
        return {"dmg": 0, "mult": 0, "crit": crit}

    stab = 1.5 if move_type in attacker.types else 1.0

    base = (
        ((2 * attacker.level / 5 + 2) * power * atk / dfn) / 50
    ) + 2

    rand = random.uniform(0.85, 1.0)
    dmg = int(base * mult * stab * rand)

    return {"dmg": max(1, dmg), "mult": mult, "crit": crit}


def accuracy_check(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: dict,
) -> tuple[bool, float]:
    acc = move.get("accuracy")
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
#  СПОСОБНОСТИ (пассивные, срабатывают при появлении/в бою)
# ==========================================================================
def on_switch_in_ability(mon: BattlePokemon) -> list[str]:
    """Способности, срабатывающие при выходе на поле. Возвращает лог."""
    lines: list[str] = []
    ability = (mon.ability or "").lower()
    if ability == "intimidate":
        lines.append(f"⚡ **{mon.name}** запугивает соперника — Intimidate.")
    if ability == "drought":
        lines.append(f"☀️ **{mon.name}** вызывает засуху — Drought.")
    if ability == "drizzle":
        lines.append(f"🌧️ **{mon.name}** вызывает дождь — Drizzle.")
    if ability == "sand-stream":
        lines.append(f"🏜️ **{mon.name}** поднимает песчаную бурю — Sand Stream.")
    if ability == "snow-warning":
        lines.append(f"❄️ **{mon.name}** вызывает снег — Snow Warning.")
    return lines


def apply_intimidate(target: BattlePokemon) -> str:
    """Понижает атаку цели на 1 стадию."""
    target.stages["attack"] = max(-6, target.stages["attack"] - 1)
    return f"⚡ Атака **{target.name}** понижена (Intimidate)."


# ==========================================================================
#  ОБРАБОТКА СТАТУСОВ
# ==========================================================================
def apply_end_of_turn(mon: BattlePokemon) -> Optional[dict]:
    if mon.fainted:
        return None

    if mon.status == "burn":
        dmg = max(1, mon.max_hp // 16)
        mon.take_damage(dmg)
        return {"type": "tick_burn", "dmg": dmg}

    if mon.status == "poison":
        dmg = max(1, mon.max_hp // 8)
        mon.take_damage(dmg)
        return {"type": "tick_poison", "dmg": dmg}

    return None
