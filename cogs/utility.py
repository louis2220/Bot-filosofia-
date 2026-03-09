import discord
from discord import app_commands
from discord.ext import commands
import time
from utils.helpers import embed_info, PHILO_COLOR
from utils.emojis import E

START_TIME = time.time()


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Verifica a latência do bot")
    async def ping(self, inter: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = 0x57F287 if latency < 100 else (0xFEE75C if latency < 200 else 0xED4245)
        e = discord.Embed(title=f"{E['loading']} Pong!", color=color)
        e.add_field(name="WebSocket", value=f"`{latency}ms`")
        await inter.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="uptime", description="Tempo que o bot está online")
    async def uptime(self, inter: discord.Interaction):
        elapsed = int(time.time() - START_TIME)
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        e = discord.Embed(title=f"{E['star']} Uptime", description=f"`{h}h {m}m {s}s`", color=PHILO_COLOR)
        await inter.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Informações do servidor")
    async def serverinfo(self, inter: discord.Interaction):
        g = inter.guild
        e = discord.Embed(title=f"{E['fire_blue']} {g.name}", color=PHILO_COLOR)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        e.add_field(name=f"{E['pin']} Dono",     value=g.owner.mention if g.owner else "?", inline=True)
        e.add_field(name=f"{E['star']} Membros", value=str(g.member_count), inline=True)
        e.add_field(name="Canais",               value=str(len(g.channels)), inline=True)
        e.add_field(name="Cargos",               value=str(len(g.roles)), inline=True)
        e.add_field(name="ID",                   value=str(g.id), inline=True)
        e.add_field(name="Criado",               value=discord.utils.format_dt(g.created_at, "R"), inline=True)
        e.set_footer(text="SophosBot • /serverinfo")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="avatar", description="Exibe o avatar de um membro")
    @app_commands.describe(membro="Membro (opcional)")
    async def avatar(self, inter: discord.Interaction, membro: discord.Member = None):
        m = membro or inter.user
        e = discord.Embed(title=f"{E['star']} Avatar de {m}", color=PHILO_COLOR)
        e.set_image(url=m.display_avatar.url)
        await inter.response.send_message(embed=e)

    @app_commands.command(name="anuncio", description="Envia um anúncio formatado no canal")
    @app_commands.describe(titulo="Título", mensagem="Conteúdo", cor="Cor hex (ex: #9B59B6)", canal="Canal de destino")
    @app_commands.default_permissions(manage_messages=True)
    async def anuncio(self, inter: discord.Interaction, titulo: str, mensagem: str, cor: str = "#9B59B6", canal: discord.TextChannel = None):
        try:
            color = int(cor.lstrip("#"), 16)
        except Exception:
            color = PHILO_COLOR
        ch = canal or inter.channel
        e = discord.Embed(title=titulo, description=mensagem, color=color)
        e.set_footer(text=f"Anúncio por {inter.user}")
        await ch.send(embed=e)
        await inter.response.send_message(embed=embed_info("Enviado!", f"Anúncio publicado em {ch.mention}."), ephemeral=True)

    @app_commands.command(name="roleinfo", description="Informações sobre um cargo")
    @app_commands.describe(cargo="Cargo")
    async def roleinfo(self, inter: discord.Interaction, cargo: discord.Role):
        e = discord.Embed(title=f"{E['arrow_white']} {cargo.name}", color=cargo.color or PHILO_COLOR)
        e.add_field(name="ID",        value=cargo.id, inline=True)
        e.add_field(name="Membros",   value=str(len(cargo.members)), inline=True)
        e.add_field(name="Cor",       value=str(cargo.color), inline=True)
        e.add_field(name="Posição",   value=str(cargo.position), inline=True)
        e.add_field(name="Mencável?", value="Sim" if cargo.mentionable else "Não", inline=True)
        e.add_field(name="Gerenciado?", value="Sim" if cargo.managed else "Não", inline=True)
        e.add_field(name="Criado",    value=discord.utils.format_dt(cargo.created_at, "R"), inline=False)
        await inter.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="channelinfo", description="Informações sobre o canal atual")
    async def channelinfo(self, inter: discord.Interaction):
        ch = inter.channel
        e = discord.Embed(title=f"{E['rules']} #{ch.name}", color=PHILO_COLOR)
        e.add_field(name="ID",      value=ch.id, inline=True)
        e.add_field(name="Tipo",    value=str(ch.type).replace("ChannelType.", ""), inline=True)
        e.add_field(name="Criado",  value=discord.utils.format_dt(ch.created_at, "R"), inline=True)
        if hasattr(ch, 'topic') and ch.topic:
            e.add_field(name="Tópico", value=ch.topic, inline=False)
        await inter.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="botinfo", description="Informações técnicas do bot")
    async def botinfo(self, inter: discord.Interaction):
        import discord as dpy
        import sys
        elapsed = int(time.time() - START_TIME)
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        e = discord.Embed(title=f"{E['fire_blue']} SophosBot — Info", color=PHILO_COLOR)
        e.set_thumbnail(url=self.bot.user.display_avatar.url)
        e.add_field(name="Versão discord.py", value=dpy.__version__, inline=True)
        e.add_field(name="Python",            value=sys.version.split()[0], inline=True)
        e.add_field(name="Uptime",            value=f"`{h}h {m}m {s}s`", inline=True)
        e.add_field(name="Servidores",        value=str(len(self.bot.guilds)), inline=True)
        e.add_field(name=f"{E['loading']} Latência", value=f"`{round(self.bot.latency*1000)}ms`", inline=True)
        e.set_footer(text="SophosBot • Filosofia & Teologia")
        await inter.response.send_message(embed=e)


async def setup(bot):
    await bot.add_cog(Utility(bot))
