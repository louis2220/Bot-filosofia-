"""
cogs/utility.py
Comandos de utilidade: ping, uptime, serverinfo, userinfo, avatar, anuncio, roleinfo, channelinfo, botinfo.
"""

import discord
from discord import app_commands
from discord.ext import commands
import time
import sys
import logging
from utils.helpers import embed_info, embed_error, PHILO_COLOR
from utils.emojis import E

log = logging.getLogger("filosofia.utility")

START_TIME = time.time()


class Utility(commands.Cog):
    """Comandos utilitários de informação e administração."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /ping ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="ping", description="Verifica a latência do bot e a conexão com o Discord")
    async def ping(self, inter: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = 0x57F287 if latency < 100 else (0xFEE75C if latency < 200 else 0xED4245)
        status = "Excelente" if latency < 100 else ("Razoável" if latency < 200 else "Alta latência")
        emb = discord.Embed(title=f"{E['loading']} Pong!", color=color)
        emb.add_field(name="WebSocket", value=f"`{latency}ms`", inline=True)
        emb.add_field(name="Status",    value=status,           inline=True)
        emb.set_footer(text="Filosofia Bot • /ping")
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /uptime ───────────────────────────────────────────────────────────────
    @app_commands.command(name="uptime", description="Exibe há quanto tempo o bot está online")
    async def uptime(self, inter: discord.Interaction):
        elapsed = int(time.time() - START_TIME)
        d, rem  = divmod(elapsed, 86400)
        h, rem  = divmod(rem, 3600)
        m, s    = divmod(rem, 60)
        parts   = []
        if d: parts.append(f"{d}d")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        parts.append(f"{s}s")
        emb = discord.Embed(
            title=f"{E['star']} Uptime",
            description=f"`{'  '.join(parts)}`",
            color=PHILO_COLOR,
        )
        emb.set_footer(text="Filosofia Bot • /uptime")
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /botinfo ──────────────────────────────────────────────────────────────
    @app_commands.command(name="botinfo", description="Informações técnicas do Bot Filosofia")
    async def botinfo(self, inter: discord.Interaction):
        elapsed = int(time.time() - START_TIME)
        d, rem  = divmod(elapsed, 86400)
        h, rem  = divmod(rem, 3600)
        m, s    = divmod(rem, 60)
        uptime_str = f"{d}d {h}h {m}m {s}s" if d else f"{h}h {m}m {s}s"

        emb = discord.Embed(title=f"{E['fire_blue']} Bot Filosofia — Informações Técnicas", color=PHILO_COLOR)
        emb.set_thumbnail(url=self.bot.user.display_avatar.url)
        emb.add_field(name="Nome",            value=str(self.bot.user),        inline=True)
        emb.add_field(name="ID",              value=str(self.bot.user.id),     inline=True)
        emb.add_field(name="discord.py",      value=discord.__version__,      inline=True)
        emb.add_field(name="Python",          value=sys.version.split()[0],   inline=True)
        emb.add_field(name="Uptime",          value=f"`{uptime_str}`",         inline=True)
        emb.add_field(name="Servidores",      value=str(len(self.bot.guilds)), inline=True)
        emb.add_field(name=f"{E['loading']} Latência", value=f"`{round(self.bot.latency*1000)}ms`", inline=True)
        emb.add_field(
            name=f"{E['bulb']} Pesquisa",
            value="SEP · PhilPapers · Open Library · CrossRef · Wikipedia",
            inline=False,
        )
        emb.set_footer(text="Filosofia Bot • «Conhece-te a ti mesmo.» — Delfos")
        await inter.response.send_message(embed=emb)

    # ── /serverinfo ───────────────────────────────────────────────────────────
    @app_commands.command(name="serverinfo", description="Exibe informações detalhadas sobre este servidor")
    async def serverinfo(self, inter: discord.Interaction):
        g = inter.guild
        emb = discord.Embed(title=f"{E['fire_blue']} {g.name}", color=PHILO_COLOR)
        if g.icon:
            emb.set_thumbnail(url=g.icon.url)
        emb.add_field(name=f"{E['pin']} Dono",     value=g.owner.mention if g.owner else "?",     inline=True)
        emb.add_field(name=f"{E['star']} Membros", value=str(g.member_count),                      inline=True)
        emb.add_field(name="Canais",               value=str(len(g.channels)),                     inline=True)
        emb.add_field(name="Cargos",               value=str(len(g.roles)),                        inline=True)
        emb.add_field(name="Emojis",               value=str(len(g.emojis)),                       inline=True)
        emb.add_field(name="Boosts",               value=str(g.premium_subscription_count),        inline=True)
        emb.add_field(name="ID",                   value=str(g.id),                                inline=True)
        emb.add_field(name="Nível Boost",          value=f"Nível {g.premium_tier}",                inline=True)
        emb.add_field(name="Verificação",          value=str(g.verification_level).replace("_", " ").title(), inline=True)
        emb.add_field(name="Criado",               value=discord.utils.format_dt(g.created_at, "R"), inline=False)
        emb.set_footer(text="Filosofia Bot • /serverinfo")
        await inter.response.send_message(embed=emb)

    # ── /avatar ───────────────────────────────────────────────────────────────
    @app_commands.command(name="avatar", description="Exibe o avatar de um membro em tamanho grande")
    @app_commands.describe(membro="Membro (deixe vazio para o seu avatar)")
    async def avatar(self, inter: discord.Interaction, membro: discord.Member = None):
        m = membro or inter.user
        emb = discord.Embed(title=f"{E['star']} Avatar de {m}", color=PHILO_COLOR)
        emb.set_image(url=m.display_avatar.url)
        emb.set_footer(text=f"Filosofia Bot • ID: {m.id}")
        await inter.response.send_message(embed=emb)

    # ── /anuncio ──────────────────────────────────────────────────────────────
    @app_commands.command(name="anuncio", description="Publica um anúncio formatado em um canal")
    @app_commands.describe(
        titulo="Título do anúncio",
        mensagem="Conteúdo do anúncio (suporta Markdown)",
        cor="Cor hexadecimal (ex: #9B59B6) — opcional",
        canal="Canal de destino (padrão: canal atual)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def anuncio(self, inter: discord.Interaction, titulo: str, mensagem: str,
                      cor: str = "#9B59B6", canal: discord.TextChannel = None):
        try:
            color = int(cor.lstrip("#"), 16)
        except (ValueError, AttributeError):
            color = PHILO_COLOR
        ch = canal or inter.channel
        emb = discord.Embed(title=titulo, description=mensagem, color=color)
        emb.set_footer(text=f"Anúncio por {inter.user} • Filosofia Bot")
        await ch.send(embed=emb)
        await inter.response.send_message(
            embed=embed_info("Anúncio publicado", f"Anúncio enviado em {ch.mention}."),
            ephemeral=True,
        )

    # ── /roleinfo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="roleinfo", description="Exibe informações detalhadas sobre um cargo")
    @app_commands.describe(cargo="Cargo a consultar")
    async def roleinfo(self, inter: discord.Interaction, cargo: discord.Role):
        emb = discord.Embed(title=f"{E['arrow_white']} {cargo.name}", color=cargo.color or PHILO_COLOR)
        emb.add_field(name="ID",           value=str(cargo.id),              inline=True)
        emb.add_field(name="Membros",      value=str(len(cargo.members)),    inline=True)
        emb.add_field(name="Cor",          value=str(cargo.color),           inline=True)
        emb.add_field(name="Posição",      value=str(cargo.position),        inline=True)
        emb.add_field(name="Mencionável?", value="Sim" if cargo.mentionable else "Não", inline=True)
        emb.add_field(name="Gerenciado?",  value="Sim" if cargo.managed else "Não",     inline=True)
        emb.add_field(name="Hoisted?",     value="Sim" if cargo.hoist else "Não",       inline=True)
        emb.add_field(name="Criado",       value=discord.utils.format_dt(cargo.created_at, "R"), inline=False)
        emb.set_footer(text="Filosofia Bot • /roleinfo")
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /channelinfo ──────────────────────────────────────────────────────────
    @app_commands.command(name="channelinfo", description="Exibe informações sobre o canal atual")
    async def channelinfo(self, inter: discord.Interaction):
        ch = inter.channel
        emb = discord.Embed(title=f"{E['rules']} #{ch.name}", color=PHILO_COLOR)
        emb.add_field(name="ID",     value=str(ch.id),                                       inline=True)
        emb.add_field(name="Tipo",   value=str(ch.type).replace("ChannelType.", "").title(), inline=True)
        emb.add_field(name="Criado", value=discord.utils.format_dt(ch.created_at, "R"),      inline=True)
        if hasattr(ch, "topic") and ch.topic:
            emb.add_field(name="Tópico", value=ch.topic[:200], inline=False)
        if hasattr(ch, "slowmode_delay"):
            emb.add_field(name="Modo lento", value=f"`{ch.slowmode_delay}s`", inline=True)
        if hasattr(ch, "nsfw"):
            emb.add_field(name="NSFW", value="Sim" if ch.nsfw else "Não", inline=True)
        emb.set_footer(text="Filosofia Bot • /channelinfo")
        await inter.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
