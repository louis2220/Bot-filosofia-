"""
Bot Filosofia — Discord Bot Acadêmico
Desenvolvido para pesquisa filosófica, moderação e utilitários.
"""

import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
import sys
from utils.storage import Storage

# ── Logging estruturado ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("filosofia")

# ── Intents ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# ── Cogs a carregar (tickets removido conforme solicitado) ───────────────────
COGS = [
    "cogs.philosophy",
    "cogs.academia",
    "cogs.moderation",
    "cogs.automod",
    "cogs.utility",
    "cogs.pesquisa",   # pesquisa acadêmica (SEP, PhilPapers, etc.)
    "cogs.cores",      # sistema de Nick Color (cores normais + degradê)
]

# ── Presences rotativas ──────────────────────────────────────────────────────
PRESENCES = [
    discord.Activity(type=discord.ActivityType.watching, name="O Mito da Caverna"),
    discord.Activity(type=discord.ActivityType.listening, name="/ajuda · Filosofia"),
    discord.Activity(type=discord.ActivityType.watching, name="Platão, Kant, Nietzsche..."),
    discord.Activity(type=discord.ActivityType.listening, name="A Crítica da Razão Pura"),
    discord.Activity(type=discord.ActivityType.watching, name="Ser e Tempo — Heidegger"),
]


class FilosofiaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,   # prefix prefix!= usado pois bot é slash-only
            intents=intents,
            help_command=None,
            # Sincronização global de slash commands
            application_id=None,   # preenchido automaticamente pelo token
        )
        self.storage = Storage()
        self._presence_index = 0

    # ── Setup hook: carrega todos os cogs ANTES de sincronizar ───────────────
    async def setup_hook(self):
        failed = []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"[COG] ✓ {cog}")
            except Exception as e:
                log.error(f"[COG] ✗ {cog}: {e}", exc_info=True)
                failed.append(cog)

        if failed:
            log.warning(f"[COG] Cogs com falha: {failed}")

        # Sincroniza slash commands globalmente
        try:
            synced = await self.tree.sync()
            log.info(f"[SYNC] {len(synced)} slash commands sincronizados globalmente.")
        except Exception as e:
            log.error(f"[SYNC] Falha ao sincronizar: {e}", exc_info=True)

    # ── on_ready ──────────────────────────────────────────────────────────────
    async def on_ready(self):
        log.info(f"[BOT] Online como {self.user} (ID: {self.user.id})")
        log.info(f"[BOT] Conectado a {len(self.guilds)} servidor(es).")
        self.rotate_presence.start()

    # ── Rotação de presence ───────────────────────────────────────────────────
    @tasks.loop(minutes=10)
    async def rotate_presence(self):
        activity = PRESENCES[self._presence_index % len(PRESENCES)]
        await self.change_presence(status=discord.Status.online, activity=activity)
        self._presence_index += 1

    @rotate_presence.before_loop
    async def before_rotate(self):
        await self.wait_until_ready()

    # ── Tratamento global de erros de interação ───────────────────────────────
    async def on_application_command_error(self, inter: discord.Interaction, error):
        msg = str(error)
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "Você não tem permissão para usar este comando."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            msg = "O bot não tem as permissões necessárias para executar esta ação."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"Comando em cooldown. Tente novamente em `{error.retry_after:.1f}s`."

        emb = discord.Embed(
            description=f"<a:i_exclamation:1446591025622679644> {msg}",
            color=0xED4245
        )
        try:
            if inter.response.is_done():
                await inter.followup.send(embed=emb, ephemeral=True)
            else:
                await inter.response.send_message(embed=emb, ephemeral=True)
        except Exception:
            pass

    # ── Guild join: log ───────────────────────────────────────────────────────
    async def on_guild_join(self, guild: discord.Guild):
        log.info(f"[GUILD] Entrou em: {guild.name} ({guild.id}) — {guild.member_count} membros")

    async def on_guild_remove(self, guild: discord.Guild):
        log.info(f"[GUILD] Saiu de: {guild.name} ({guild.id})")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        log.critical("[BOT] Variável de ambiente DISCORD_TOKEN não definida!")
        sys.exit(1)

    bot = FilosofiaBot()

    async def runner():
        async with bot:
            await bot.start(token)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        log.info("[BOT] Encerrando por KeyboardInterrupt.")
    except discord.LoginFailure:
        log.critical("[BOT] Token inválido! Verifique a variável DISCORD_TOKEN.")
        sys.exit(1)


if __name__ == "__main__":
    main()
