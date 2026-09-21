"""Ловля покемонов: /catch с шансами от покебола и условий."""
import logging
import random
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import pokeapi_client
from database import (
    add_pokemon,
    add_to_pokedex,
    get_active_profile,
    get_item_qty,
    get_trainer,
    take_item,
)
from pokeapi_client import PokeAPIError
from utils import (
    EMBED_COLOR,
    GENDER_EMOJI,
    format_moves,
    format_types,
    load_species,
)

# Пытаемся загрузить локации, если файл залит. Иначе — fallback.
try:
    from data.locations import get_location  # type: ignore
except ImportError:
    def get_location(loc_id):  # type: ignore
        """Все локации одинаковые, если data/locations.py не залит."""
        return {"encounters": None}

log = logging.getLogger(__name__)
