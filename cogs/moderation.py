import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import logging
from utils.helpers import embed_mod, embed_success, embed_error, embed_info, duration_to_seconds
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("sophosbot.moderation")


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.storage: Storage = bot.storage

    def _log_channel(self, guild):
        ch_id = self.storage.guild_get(guild.id, "config", "mod_log_channel")
        return guild.get_channel(int(ch_id)) if ch_id else None

    async def _send_log(self, guild, embed):
        ch = self._log_channel(guild)
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception as ex:
                log.warning(f"Log falhou: {ex}")

    async def _notify_user(self, user, action: str, reason: str, guild):
        try:
            e = discord.Embed(
                title=f"{E['exclaim']} Ação em **{guild.name}**",
                description=f"{E['arrow_white']} **Ação:** {action}\n{E['rules']} **Motivo:** {reason or 'Não especificado'}",
                color=0xED4245
            )
            await user.send(embed=e)
        except Exception:
            pass

    @app_commands.command(name="ban", description="Bane um membro do servidor")
    @app_commands.describe(membro="Membro a ser banido", motivo="Motivo", delete_days="Dias de msgs a apagar (0-7)")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo", delete_days: int = 0):
        await inter.response.defer(ephemeral=True)
        if membro.top_role >= inter.user.top_role:
            return await inter.followup.send(embed=embed_error("Sem permissão", "Você não pode banir alguém com cargo igual ou superior."), ephemeral=True)
        await self._notify_user(membro, "Banido", motivo, inter.guild)
        await inter.guild.ban(membro, reason=f"[{inter.user}] {motivo}", delete_message_days=min(delete_days, 7))
        await self._send_log(inter.guild, embed_mod("Ban", membro, inter.user, motivo))
        await inter.followup.send(embed=embed_success("Banido!", f"{membro.mention} foi banido.\n{E['rules']} **Motivo:** {motivo}"), ephemeral=True)

    @app_commands.command(name="unban", description="Remove o banimento de um usuário pelo ID")
    @app_commands.describe(user_id="ID do usuário", motivo="Motivo")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, inter: discord.Interaction, user_id: str, motivo: str = "Sem motivo"):
        await inter.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await inter.guild.unban(user, reason=f"[{inter.user}] {motivo}")
            await self._send_log(inter.guild, embed_mod("Unban", user, inter.user, motivo))
            await inter.followup.send(embed=embed_success("Desbanido!", f"**{user}** foi desbanido."), ephemeral=True)
        except Exception as ex:
            await inter.followup.send(embed=embed_error("Erro", str(ex)), ephemeral=True)

    @app_commands.command(name="kick", description="Expulsa um membro do servidor")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo"):
        await inter.response.defer(ephemeral=True)
        if membro.top_role >= inter.user.top_role:
            return await inter.followup.send(embed=embed_error("Sem permissão", "Cargo igual ou superior."), ephemeral=True)
        await self._notify_user(membro, "Expulso", motivo, inter.guild)
        await inter.guild.kick(membro, reason=f"[{inter.user}] {motivo}")
        await self._send_log(inter.guild, embed_mod("Kick", membro, inter.user, motivo))
        await inter.followup.send(embed=embed_success("Expulso!", f"{membro.mention} foi expulso."), ephemeral=True)

    @app_commands.command(name="timeout", description="Silencia um membro temporariamente")
    @app_commands.describe(membro="Membro", duracao="Ex: 10m, 2h, 1d", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, inter: discord.Interaction, membro: discord.Member, duracao: str = "10m", motivo: str = "Sem motivo"):
        await inter.response.defer(ephemeral=True)
        secs = duration_to_seconds(duracao)
        if secs <= 0:
            return await inter.followup.send(embed=embed_error("Duração inválida", "Use ex: 10m, 2h, 1d"), ephemeral=True)
        await membro.timeout(discord.utils.utcnow() + timedelta(seconds=secs), reason=f"[{inter.user}] {motivo}")
        await self._notify_user(membro, f"Silenciado por {duracao}", motivo, inter.guild)
        await self._send_log(inter.guild, embed_mod("Timeout", membro, inter.user, motivo, f"Duração: {duracao}"))
        await inter.followup.send(embed=embed_success("Silenciado!", f"{E['muted']} {membro.mention} silenciado por `{duracao}`."), ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove o silêncio de um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo"):
        await inter.response.defer(ephemeral=True)
        await membro.timeout(None, reason=f"[{inter.user}] {motivo}")
        await self._send_log(inter.guild, embed_mod("Untimeout", membro, inter.user, motivo))
        await inter.followup.send(embed=embed_success("Silêncio removido!", f"{membro.mention} pode falar novamente."), ephemeral=True)

    @app_commands.command(name="warn", description="Avisa um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, inter: discord.Interaction, membro: discord.Member, motivo: str):
        await inter.response.defer(ephemeral=True)
        warns = self.storage.guild_get(inter.guild.id, "warns", str(membro.id)) or []
        warns.append({"motivo": motivo, "moderador": str(inter.user.id)})
        self.storage.guild_set(inter.guild.id, "warns", str(membro.id), warns)
        await self._notify_user(membro, f"Avisado (aviso #{len(warns)})", motivo, inter.guild)
        await self._send_log(inter.guild, embed_mod("Warn", membro, inter.user, motivo, f"Total de avisos: {len(warns)}"))
        await inter.followup.send(embed=embed_success("Aviso registrado!", f"{E['warning']} {membro.mention} — Aviso #{len(warns)}\n{E['rules']} **Motivo:** {motivo}"), ephemeral=True)

    @app_commands.command(name="warnings", description="Lista os avisos de um membro")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, inter: discord.Interaction, membro: discord.Member):
        warns = self.storage.guild_get(inter.guild.id, "warns", str(membro.id)) or []
        if not warns:
            return await inter.response.send_message(embed=embed_info("Sem avisos", f"{membro.mention} não tem avisos."), ephemeral=True)
        e = discord.Embed(title=f"{E['warning']} Avisos de {membro}", color=0xFEE75C)
        for i, w in enumerate(warns, 1):
            mod = inter.guild.get_member(int(w["moderador"]))
            e.add_field(name=f"{E['arrow_white']} Aviso #{i}", value=f"{E['rules']} {w['motivo']}\n{E['pin']} {mod.mention if mod else 'Desconhecido'}", inline=False)
        await inter.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="clearwarn", description="Remove todos os avisos de um membro")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def clearwarn(self, inter: discord.Interaction, membro: discord.Member):
        self.storage.guild_set(inter.guild.id, "warns", str(membro.id), [])
        await inter.response.send_message(embed=embed_success("Avisos limpos!", f"Avisos de {membro.mention} removidos."), ephemeral=True)

    @app_commands.command(name="purge", description="Apaga mensagens em massa")
    @app_commands.describe(quantidade="Quantidade (max 100)", membro="Filtrar por membro (opcional)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, inter: discord.Interaction, quantidade: int, membro: discord.Member = None):
        await inter.response.defer(ephemeral=True)
        check = (lambda m: m.author == membro) if membro else None
        deleted = await inter.channel.purge(limit=min(quantidade, 100), check=check)
        await inter.followup.send(embed=embed_success("Mensagens apagadas!", f"`{len(deleted)}` mensagens deletadas."), ephemeral=True)

    @app_commands.command(name="slowmode", description="Define o slowmode do canal")
    @app_commands.describe(segundos="Segundos (0 para desativar)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, inter: discord.Interaction, segundos: int):
        await inter.channel.edit(slowmode_delay=segundos)
        msg = f"Slowmode definido para `{segundos}s`." if segundos else "Slowmode desativado."
        await inter.response.send_message(embed=embed_success("Slowmode", msg), ephemeral=True)

    @app_commands.command(name="lock", description="Bloqueia o canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = False
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(embed=embed_success("Canal bloqueado", f"{E['deafened']} {inter.channel.mention} bloqueado."))

    @app_commands.command(name="unlock", description="Desbloqueia o canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = None
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(embed=embed_success("Canal desbloqueado", f"{inter.channel.mention} desbloqueado."))

    @app_commands.command(name="setlogchannel", description="Define o canal de logs de moderação")
    @app_commands.describe(canal="Canal de logs")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, inter: discord.Interaction, canal: discord.TextChannel):
        self.storage.guild_set(inter.guild.id, "config", "mod_log_channel", str(canal.id))
        await inter.response.send_message(embed=embed_success("Canal de log definido", f"Logs em {canal.mention}."), ephemeral=True)

    @app_commands.command(name="userinfo", description="Informações sobre um membro")
    @app_commands.describe(membro="Membro (opcional)")
    async def userinfo(self, inter: discord.Interaction, membro: discord.Member = None):
        m = membro or inter.user
        warns = self.storage.guild_get(inter.guild.id, "warns", str(m.id)) or []
        e = discord.Embed(title=f"{E['star']} {m}", color=m.color or 0x5865F2)
        e.set_thumbnail(url=m.display_avatar.url)
        e.add_field(name="ID", value=m.id, inline=True)
        e.add_field(name="Apelido", value=m.display_name, inline=True)
        e.add_field(name="Conta criada", value=discord.utils.format_dt(m.created_at, "R"), inline=True)
        e.add_field(name="Entrou", value=discord.utils.format_dt(m.joined_at, "R"), inline=True)
        e.add_field(name="Bot?", value="Sim" if m.bot else "Não", inline=True)
        e.add_field(name=f"{E['warning']} Avisos", value=str(len(warns)), inline=True)
        roles = [r.mention for r in reversed(m.roles) if r != inter.guild.default_role]
        e.add_field(name=f"Cargos ({len(roles)})", value=" ".join(roles[:10]) or "Nenhum", inline=False)
        await inter.response.send_message(embed=e, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
