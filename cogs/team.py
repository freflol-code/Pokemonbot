"""Команда, ПК, перемещение покемонов и клички."""
import math
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from database import (
    MAX_PARTY_SIZE,
    get_pokemon,
    get_trainer,
    move_pokemon,
    update_pokemon,
)
from utils import (
    EMBED_COLOR,
    format_ability,
    format_moves,
    load_abilities_ru,
    load_species,
    mon_title,
)

PC_PER_PAGE = 10


def _mon_choices(
    trainer: dict[str, Any], sources: tuple[str, ...], current: str
) -> list[app_commands.Choice[str]]:
    out: list[app_commands.Choice[str]] = []
    cur = current.strip().lower()
    for src in sources:
        for m in trainer.get(src, []):
            nick = m.get("nickname") or f"Покемон #{m['species_id']}"
            label = f"{nick} • Ур.{m['level']} • {m['instance_id']}"
            if not cur or cur in label.lower() or cur in m["instance_id"]:
                out.append(
                    app_commands.Choice(name=label[:100], value=m["instance_id"])
                )
            if len(out) >= 25:
                return out
    return out


def _pretty_ability(ability_en: str | None, abilities_ru: dict[str, str]) -> str:
    """Русское название, если есть. Иначе — красиво оформленное английское."""
    if not ability_en:
        return "—"
    ru = abilities_ru.get(ability_en)
    if ru and ru != ability_en:
        return ru
    return str(ability_en).replace("-", " ").title()


class PCView(discord.ui.View):
    """Пагинация ПК по 10 покемонов на страницу."""

    def __init__(self, owner_id: int, pc: list[dict[str, Any]]) -> None:
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.pc = pc
        self.page = 0
        self.message: discord.Message | None = None
        self._update_buttons()

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(len(self.pc) / PC_PER_PAGE))

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    async def build_embed(self) -> discord.Embed:
        chunk = self.pc[self.page * PC_PER_PAGE : (self.page + 1) * PC_PER_PAGE]
        species = await load_species(chunk)
        abilities_ru = await load_abilities_ru(chunk)
        start = self.page * PC_PER_PAGE
        lines = []
        for i, m in enumerate(chunk, 1):
            ability = _pretty_ability(m.get("ability"), abilities_ru)
            lines.append(
                f"`{start + i}.` **{mon_title(m, species)}** • Ур. {m['level']} • "
                f"Способность: {ability} • ID: `{m['instance_id']}`"
            )
        embed = discord.Embed(
            title=f"🖥️ ПК ({len(self.pc)} покемонов)",
            description="\n".join(lines) if lines else "ПК пуст.",
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Страница {self.page + 1}/{self.total_pages}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Это не ваш ПК. Используйте /pc сами.", ephemeral=True
            )
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self._update_buttons()
        await interaction.edit_original_response(
            embed=await self.build_embed(), view=self
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page += 1
        await self._refresh(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Team(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="party", description="Показать команду тренера")
    @app_commands.describe(user="Чью команду посмотреть (по умолчанию — свою)")
    async def party(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        t = await get_trainer(target.id)
        party = t["party"]

        if target.id == interaction.user.id:
            title = f"🎒 Команда {target.display_name} ({len(party)}/{MAX_PARTY_SIZE})"
        else:
            title = (
                f"🎒 Команда {target.display_name} "
                f"({len(party)}/{MAX_PARTY_SIZE}) — чужая"
            )

        embed = discord.Embed(title=title, color=EMBED_COLOR)
        if not party:
            embed.description = (
                "Команда пуста. Добавьте покемона: /team_add"
                if target.id == interaction.user.id
                else f"У {target.display_name} команда пуста."
            )
        species = await load_species(party)
        abilities_ru = await load_abilities_ru(party)
        for i, m in enumerate(party, 1):
            ability = _pretty_ability(m.get("ability"), abilities_ru)
            embed.add_field(
                name=f"{i}. {mon_title(m, species)}",
                value=(
                    f"Ур. **{m['level']}**\n"
                    f"Способность: **{ability}**\n"
                    f"Атаки: {format_moves(m['moves'])}\n"
                    f"ID: `{m['instance_id']}`"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pc", description="Показать покемонов в ПК")
    async def pc(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        t = await get_trainer(interaction.user.id)
        view = PCView(interaction.user.id, t["pc"])
        embed = await view.build_embed()
        if view.total_pages == 1:
            await interaction.followup.send(embed=embed)
        else:
            view.message = await interaction.followup.send(
                embed=embed, view=view, wait=True
            )

    @app_commands.command(
        name="team_add", description="Переместить покемона из ПК в команду"
    )
    @app_commands.describe(instance_id="ID покемона (см. /pc)")
    async def team_add(
        self, interaction: discord.Interaction, instance_id: str
    ) -> None:
        iid = instance_id.strip().lower()
        uid = interaction.user.id
        trainer = await get_trainer(uid)

        if not any(m["instance_id"] == iid for m in trainer["pc"]):
            if any(m["instance_id"] == iid for m in trainer["party"]):
                msg = "Этот покемон уже в команде."
            else:
                msg = "Покемон с таким ID не найден в ПК."
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        ok, reason = await move_pokemon(uid, iid, to_party=True)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        mon = await get_pokemon(uid, iid)
        species = await load_species([mon]) if mon else {}
        title = mon_title(mon, species) if mon else iid
        await interaction.response.send_message(f"✅ **{title}** теперь в команде!")

    @app_commands.command(
        name="team_remove", description="Переместить покемона из команды в ПК"
    )
    @app_commands.describe(instance_id="ID покемона (см. /party)")
    async def team_remove(
        self, interaction: discord.Interaction, instance_id: str
    ) -> None:
        iid = instance_id.strip().lower()
        uid = interaction.user.id

        ok, reason = await move_pokemon(uid, iid, to_party=False)
        if not ok:
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return

        mon = await get_pokemon(uid, iid)
        species = await load_species([mon]) if mon else {}
        title = mon_title(mon, species) if mon else iid
        await interaction.response.send_message(f"✅ **{title}** отправлен в ПК.")

    @app_commands.command(name="setnick", description="Задать кличку покемону")
    @app_commands.describe(
        instance_id="ID покемона (в команде или ПК)",
        nickname="Кличка до 20 символов ('-' — сбросить)",
    )
    async def setnick(
        self, interaction: discord.Interaction, instance_id: str, nickname: str
    ) -> None:
        iid = instance_id.strip().lower()
        nick = nickname.strip()
        if len(nick) > 20:
            await interaction.response.send_message(
                "❌ Кличка не должна быть длиннее 20 символов.", ephemeral=True
            )
            return
        new_value = None if nick in ("", "-") else nick

        ok = await update_pokemon(interaction.user.id, iid, nickname=new_value)
        if not ok:
            await interaction.response.send_message(
                "❌ Покемон с таким ID не найден.", ephemeral=True
            )
            return

        if new_value is None:
            await interaction.response.send_message("✅ Кличка сброшена.")
        else:
            await interaction.response.send_message(
                f"✅ Кличка установлена: **{discord.utils.escape_markdown(new_value)}**"
            )

    # --- автодополнение ID ------------------------------------------------
    @team_add.autocomplete("instance_id")
    async def _ac_add(self, interaction: discord.Interaction, current: str):
        t = await get_trainer(interaction.user.id)
        return _mon_choices(t, ("pc",), current)

    @team_remove.autocomplete("instance_id")
    async def _ac_remove(self, interaction: discord.Interaction, current: str):
        t = await get_trainer(interaction.user.id)
        return _mon_choices(t, ("party",), current)

    @setnick.autocomplete("instance_id")
    async def _ac_nick(self, interaction: discord.Interaction, current: str):
        t = await get_trainer(interaction.user.id)
        return _mon_choices(t, ("party", "pc"), current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Team(bot))
