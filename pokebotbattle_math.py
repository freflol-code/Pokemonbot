"""Боевая математика: шансы поимки покеболами, уклонения, точность атак.

Этот модуль ничего не делает сам — просто даёт функции,
которые можно вызывать из боевой системы, команд мастеров или тестов.
"""
from __future__ import annotations

import random
from typing import Optional

# ==========================================================================
#  БОНУСЫ ПОКЕБОЛОВ
#  Стандартные множители из игр. Для контекстных (Net Ball, Dusk Ball и т.д.)
#  есть функция get_ball_bonus(), которая учитывает условия боя.
# ==========================================================================
BALL_BONUS: dict[str, float] = {
    "pokeball":     1.0,
    "greatball":    1.5,
    "ultraball":    2.0,
    "masterball":   255.0,  # гарантированная поимка
    "net_ball":     1.0,    # ×3.5 если Water или Bug — см. get_ball_bonus
    "dive_ball":    1.0,    # ×3.5 если ловишь под водой
    "nest_ball":    1.0,    # зависит от уровня
    "repeat_ball":  1.0,    # ×3.5 если вид уже пойман
    "timer_ball":   1.0,    # растёт со временем боя
    "heal_ball":    1.0,
    "luxury_ball":  1.0,
    "quick_ball":   1.0,    # ×5 в первый ход боя
    "dusk_ball":    1.0,    # ×3 ночью и в пещерах
}

# ==========================================================================
#  БОНУСЫ СТАТУСОВ
# ==========================================================================
STATUS_BONUS: dict[str, float] = {
    "none":      1.0,
    "poison":    1.5,
    "burn":      1.5,
    "paralysis": 1.5,
    "sleep":     2.5,
    "freeze":    2.5,
}

# ==========================================================================
#  МНОЖИТЕЛИ СТАДИЙ (accuracy / evasion)
#  Диапазон от -6 до +6. Значение 0 = 1.0 (нейтрально).
# ==========================================================================
STAGE_MULTIPLIERS: dict[int, float] = {
    -6: 3 / 9,
    -5: 3 / 8,
    -4: 3 / 7,
    -3: 3 / 6,
    -2: 3 / 5,
    -1: 3 / 4,
     0: 1.0,
     1: 4 / 3,
     2: 5 / 3,
     3: 6 / 3,
     4: 7 / 3,
     5: 8 / 3,
     6: 9 / 3,
}


# ==========================================================================
#  ПОКЕБОЛЫ
# ==========================================================================

def get_ball_bonus(
    ball_key: str,
    *,
    target_types: Optional[list[str]] = None,
    turn_number: int = 1,
    is_night: bool = False,
    in_cave: bool = False,
    already_caught: bool = False,
    target_level: int = 5,
    is_underwater: bool = False,
) -> float:
    """Возвращает реальный множитель покебола с учётом условий боя.

    Для базовых покеболов (Poké, Great, Ultra, Master) — просто значение из BALL_BONUS.
    Для ситуативных — считает по правилам игр.
    """
    ball_key = ball_key.lower()
    base = BALL_BONUS.get(ball_key, 1.0)

    if ball_key == "net_ball":
        if target_types and ("water" in target_types or "bug" in target_types):
            return 3.5
        return 1.0

    if ball_key == "dive_ball":
        return 3.5 if is_underwater else 1.0

    if ball_key == "nest_ball":
        # Формула: (41 - уровень) / 10, но не ниже 1.0 и не выше 3.9
        if target_level < 30:
            mult = (41 - target_level) / 10
            return max(1.0, min(3.9, mult))
        return 1.0

    if ball_key == "repeat_ball":
        return 3.5 if already_caught else 1.0

    if ball_key == "timer_ball":
        # Растёт с ходами: 1.0 → 4.0 к 10-му ходу
        if turn_number <= 1:
            return 1.0
        mult = min(4.0, 1.0 + 0.3 * (turn_number - 1))
        return mult

    if ball_key == "quick_ball":
        return 5.0 if turn_number == 1 else 1.0

    if ball_key == "dusk_ball":
        return 3.0 if (is_night or in_cave) else 1.0

    # heal_ball, luxury_ball, masterball и базовые — без условий
    return base


def catch_chance(
    *,
    current_hp: int,
    max_hp: int,
    catch_rate: int,
    ball_key: str = "pokeball",
    status: str = "none",
    **ball_kwargs,
) -> float:
    """Вероятность поимки (0.0 – 1.0) за один бросок покебола.

    - current_hp / max_hp — текущее и максимальное HP покемона.
    - catch_rate — базовая скорость поимки (берётся из PokéAPI: species.capture_rate).
    - ball_key — ключ покебола из BALL_BONUS.
    - status — 'none' / 'poison' / 'burn' / 'paralysis' / 'sleep' / 'freeze'.
    - ball_kwargs — условия боя для ситуативных покеболов.
    """
    if max_hp <= 0:
        max_hp = 1
    if current_hp < 1:
        current_hp = 1
    if current_hp > max_hp:
        current_hp = max_hp

    ball_bonus = get_ball_bonus(ball_key, **ball_kwargs)
    status_bonus = STATUS_BONUS.get(status.lower(), 1.0)

    # Формула Gen III+
    a = (
        (3 * max_hp - 2 * current_hp)
        * catch_rate
        * ball_bonus
    ) / (3 * max_hp)
    a *= status_bonus

    if a >= 255:
        return 1.0  # гарантированная поимка

    # 4 «встряхивания» покебола
    b = 65536 / ((255 / a) ** 0.25)
    chance_per_shake = b / 65536
    return chance_per_shake ** 4


def try_catch(
    *,
    current_hp: int,
    max_hp: int,
    catch_rate: int,
    ball_key: str = "pokeball",
    status: str = "none",
    **ball_kwargs,
) -> tuple[bool, float]:
    """Пробует поймать покемона. Возвращает (успех, шанс_поимки)."""
    chance = catch_chance(
        current_hp=current_hp,
        max_hp=max_hp,
        catch_rate=catch_rate,
        ball_key=ball_key,
        status=status,
        **ball_kwargs,
    )
    return random.random() < chance, chance


# ==========================================================================
#  ТОЧНОСТЬ И УКЛОНЕНИЕ
# ==========================================================================

def stage_multiplier(stage: int) -> float:
    """Множитель для стадии -6..+6. 0 → 1.0, +6 → 3.0, -6 → 1/3."""
    stage = max(-6, min(6, int(stage)))
    return STAGE_MULTIPLIERS[stage]


def effective_accuracy(
    move_accuracy: Optional[int],
    *,
    accuracy_stage: int = 0,
    evasion_stage: int = 0,
) -> float:
    """Итоговая точность атаки (0.0 – 1.0).

    - move_accuracy — базовая точность атаки из PokéAPI (в процентах: 100, 90, ...).
      Если None — атака не может промахнуться (например, Swift, Aerial Ace).
    - accuracy_stage — стадия точности атакующего (-6..+6).
    - evasion_stage — стадия уклонения цели (-6..+6).
    """
    if move_accuracy is None:
        return 1.0

    acc_mult = stage_multiplier(accuracy_stage)
    eva_mult = stage_multiplier(evasion_stage)

    final_percent = move_accuracy * acc_mult / eva_mult
    # Ограничиваем 0..100
    final_percent = max(0.0, min(100.0, final_percent))
    return final_percent / 100.0


def roll_hit(
    move_accuracy: Optional[int],
    *,
    accuracy_stage: int = 0,
    evasion_stage: int = 0,
) -> tuple[bool, float]:
    """Бросает проверку на попадание. Возвращает (попал, шанс)."""
    chance = effective_accuracy(
        move_accuracy,
        accuracy_stage=accuracy_stage,
        evasion_stage=evasion_stage,
    )
    return random.random() < chance, chance


def accuracy_label(stage: int) -> str:
    """Человекочитаемое описание стадии для эмбедов: '+2 (×1.67)'."""
    stage = max(-6, min(6, int(stage)))
    mult = STAGE_MULTIPLIERS[stage]
    sign = "+" if stage > 0 else ""
    return f"{sign}{stage} (×{mult:.2f})"


def describe_accuracy_effect(stage: int) -> str:
    """Текст для сообщения вида 'Точность повышена на 2 стадии!'"""
    if stage == 0:
        return "Точность не изменена."
    if stage > 0:
        return f"Точность повышена на {stage} стадию!" if stage == 1 else f"Точность повышена на {stage} стадии!"
    return f"Точность понижена на {abs(stage)} стадию!" if stage == -1 else f"Точность понижена на {abs(stage)} стадии!"


def describe_evasion_effect(stage: int) -> str:
    """Текст для уклонения."""
    if stage == 0:
        return "Уклонение не изменено."
    if stage > 0:
        return f"Уклонение повышено на {stage} стадию!" if stage == 1 else f"Уклонение повышено на {stage} стадии!"
    return f"Уклонение понижено на {abs(stage)} стадию!" if stage == -1 else f"Уклонение понижено на {abs(stage)} стадии!"
