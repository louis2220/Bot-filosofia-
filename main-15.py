import discord
from discord.ext import commands
import os
import logging
import asyncio
from utils.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("sophosbot")
intents = discord.Intents.all()

class SophosBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.storage = Storage()

    async def setup_hook(self):
        for cog in ["cogs.moderation","cogs.tickets","cogs.automod","cogs.philosophy","cogs.utility","cogs.academia"]:
            try:
                await self.load_extension(cog)
                log.info(f"Cog: {cog}")
            except Exception as e:
                log.error(f"Erro {cog}: {e}")
        await self.tree.sync()
        log.info("Slash commands sincronizados.")

    async def on_ready(self):
        log.info(f"Online: {self.user} ({self.user.id})")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="O Mito da Caverna"))

bot = SophosBot()
if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN não definido!")
    asyncio.run(bot.start(token))
