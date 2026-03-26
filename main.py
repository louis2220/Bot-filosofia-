"""
Bot Filosofia — Discord Bot Academico
Desenvolvido para pesquisa filosofica, moderacao e utilitarios.
"""

import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
import sys
from utils.db import Database
from utils.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("filosofia")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

COGS = [
    "cogs.philosophy",
    "cogs.academia",
    "cogs.moderation",
    "cogs.automod",
    "cogs.utility",
    "cogs.pesquisa",
    "cogs.cores",
    "cogs.tickets",
]

PRESENCES = [
    discord.Activity(type=discord.ActivityType.watching,  name="O Mito da Caverna"),
    discord.Activity(type=discord.ActivityType.listening, name="/ajuda — Filosofia"),
    discord.Activity(type=discord.ActivityType.watching,  name="Platao, Kant, Nietzsche..."),
    discord.Activity(type=discord.ActivityType.listening, name="A Critica da Razao Pura"),
    discord.Activity(type=discord.ActivityType.watching,  name="Ser e Tempo — Heidegger"),
]


class FilosofiaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self._presence_index = 0
        self.storage = Storage()  # inicializa o storage aqui

    async def setup_hook(self):
        # Conecta ao banco antes de qualquer coisa
        try:
            await Database.connect()
        except Exception as e:
            log.critical(f"[DB] Falha ao conectar ao banco: {e}")
            sys.exit(1)

        # Carrega os dados do banco para o cache do storage
        await self.storage.preload()

        failed = []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"[COG] {cog} carregado.")
            except Exception as e:
                log.error(f"[COG] Falha em {cog}: {e}", exc_info=True)
                failed.append(cog)
        if failed:
            log.warning(f"[COG] Cogs com falha: {failed}")

        try:
            synced = await self.tree.sync()
            log.info(f"[SYNC] {len(synced)} slash commands sincronizados.")
        except Exception as e:
            log.error(f"[SYNC] Falha: {e}", exc_info=True)

    async def on_ready(self):
        log.info(f"[BOT] Online como {self.user} (ID: {self.user.id})")
        log.info(f"[BOT] Conectado a {len(self.guilds)} servidor(es).")
        self.rotate_presence.start()

    @tasks.loop(minutes=10)
    async def rotate_presence(self):
        activity = PRESENCES[self._presence_index % len(PRESENCES)]
        await self.change_presence(status=discord.Status.online, activity=activity)
        self._presence_index += 1

    @rotate_presence.before_loop
    async def before_rotate(self):
        await self.wait_until_ready()

    async def on_application_command_error(self, inter: discord.Interaction, error):
        msg = str(error)
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "Voce nao tem permissao para usar este comando."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            msg = "O bot nao tem as permissoes necessarias."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"Comando em cooldown. Tente novamente em {error.retry_after:.1f}s."
        emb = discord.Embed(description=msg, color=0xE74C3C)
        try:
            if inter.response.is_done():
                await inter.followup.send(embed=emb, ephemeral=True)
            else:
                await inter.response.send_message(embed=emb, ephemeral=True)
        except Exception:
            pass

    async def on_guild_join(self, guild: discord.Guild):
        log.info(f"[GUILD] Entrou em: {guild.name} ({guild.id})")

    async def on_guild_remove(self, guild: discord.Guild):
        log.info(f"[GUILD] Saiu de: {guild.name} ({guild.id})")


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        log.critical("[BOT] DISCORD_TOKEN nao definido!")
        sys.exit(1)

    bot = FilosofiaBot()

    async def runner():
        async with bot:
            await bot.start(token)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        log.info("[BOT] Encerrado por KeyboardInterrupt.")
    except discord.LoginFailure:
        log.critical("[BOT] Token invalido!")
        sys.exit(1)


if __name__ == "__main__":
    main()
