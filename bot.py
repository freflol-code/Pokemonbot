"""Точка входа: запуск бота, загрузка cog'ов и синхронизация слэш-команд."""
from __future__ import annotations

import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
import pokeapi_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pokebot")

EXTENSIONS = [
    "cogs.profile",
    "cogs.team",
    "cogs.inventory",
    "cogs.pokedex",
    "cogs.admin",
    "cogs.travel",
]


class PokeBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=discord.Intents.default(),
            help_command=None,
        )
        self.tree.on_error = self.on_tree_error

    # --- Запуск и загрузка cog'ов -------------------------------------------
    async def setup_hook(self) -> None:
        # SQLite инициализируется здесь. Путь: SQLITE_DB из .env или pokebot.db
        await database.connect(os.getenv("SQLITE_DB", "pokebot.db"))

        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Загружен модуль %s", ext)
            except Exception:
                log.exception("Не удалось загрузить %s", ext)
                raise

        guild_id = os.getenv("GUILD_ID", "").strip()
        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info(
                    "Синхронизировано %d команд на сервере %s", len(synced), guild_id
                )
            else:
                synced = await self.tree.sync()
                log.info(
                    "Глобально синхронизировано %d команд "
                    "(появление может занять до часа; укажите GUILD_ID в .env для мгновенной синхронизации)",
                    len(synced),
                )
        except discord.HTTPException:
            log.exception("Ошибка синхронизации команд с Discord")

    async def on_ready(self) -> None:
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id)

    # --- Корректное завершение ----------------------------------------------
    async def close(self) -> None:
        log.info("Завершение работы…")
        try:
            await pokeapi_client.close()
        finally:
            await database.close()
            await super().close()

    # --- Логирование вызовов ------------------------------------------------
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command | app_commands.ContextMenu,
    ) -> None:
        where = f"guild={interaction.guild_id}" if interaction.guild_id else "DM"
        log.info(
            "Команда /%s • user=%s • %s",
            getattr(command, "qualified_name", command.name),
            interaction.user.id,
            where,
        )

    # --- Обработка ошибок ---------------------------------------------------
    async def on_tree_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        log.exception("Ошибка в команде", exc_info=error)

        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Подождите {error.retry_after:.1f} сек. и попробуйте снова."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "🚫 У вас нет прав для этой команды."
        elif isinstance(error, app_commands.CheckFailure):
            msg = "🚫 Вы не можете использовать эту команду."
        else:
            msg = "⚠️ Произошла ошибка при выполнении команды. Попробуйте ещё раз."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            log.warning("Не удалось отправить сообщение об ошибке пользователю")


def _check_env() -> None:
    """Проверяет наличие обязательных переменных окружения."""
    missing = [k for k in ("DISCORD_TOKEN",) if not os.getenv(k)]
    if missing:
        print(
            "❌ Заполните переменные окружения в файле .env: " + ", ".join(missing),
            file=sys.stderr,
        )
        raise SystemExit(1)


def main() -> None:
    _check_env()
    bot = PokeBot()
    try:
        bot.run(os.environ["DISCORD_TOKEN"], log_handler=None)
    except KeyboardInterrupt:
        log.info("Получен Ctrl+C, останавливаюсь…")


if __name__ == "__main__":
    main()
