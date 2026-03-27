"""
cogs/moderation.py
Moderacao avancada com PostgreSQL — inspirado no Security e Wick.
Inclui: ban, kick, timeout, warn, purge, lock, lockdown, antiraid automatico,
anti-nuke, antispam, quarentena, softban, rolepurge, banlist, conta nova, whitelist.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta, datetime, timezone
from collections import defaultdict
import asyncio
import logging

from utils.helpers import (
    embed_mod, embed_success, embed_error, embed_info, embed_warn,
    duration_to_seconds, format_duration,
)
from utils.db import Database

log = logging.getLogger("filosofia.moderation")

# ── Limites de avisos para acoes automaticas escalonadas ─────────────────────
WARN_THRESHOLDS = {
    3:  ("timeout", "15m"),
    5:  ("timeout", "1h"),
    7:  ("kick",    None),
    10: ("ban",     None),
}

# Canais que nunca devem ser bloqueados no lockdown total (por nome parcial)
LOCKDOWN_EXEMPT_NAMES = {"log", "logs", "staff", "mod", "admin", "moderacao"}

# ── Antispam: janela de deteccao ──────────────────────────────────────────────
SPAM_WINDOW   = 5    # segundos
SPAM_LIMIT    = 6    # mensagens no intervalo para acionar
SPAM_TIMEOUT  = 300  # segundos de timeout ao detectar spam (5 min)

# ── Anti-raid: joins por janela ───────────────────────────────────────────────
RAID_WINDOW   = 10   # segundos
RAID_LIMIT    = 8    # joins no intervalo para acionar modo raid
RAID_LOCKOUT  = 300  # segundos de lockout automatico

# ── Anti-nuke: acoes destrutivas por janela ───────────────────────────────────
NUKE_WINDOW   = 15   # segundos
NUKE_LIMIT    = 3    # delecoes/criacoes em massa para acionar


class Moderation(commands.Cog):
    """Moderacao avancada: ban, kick, timeout, warn, purge, lock, unlock,
    lockdown, antiraid, anti-nuke, antispam, quarentena, softban e mais."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Antispam: {guild_id: {user_id: [timestamps]}}
        self._spam_tracker: dict = defaultdict(lambda: defaultdict(list))

        # Anti-raid: {guild_id: [join_timestamps]}
        self._join_tracker: dict = defaultdict(list)
        self._raid_mode:    set  = set()  # guild_ids em modo raid

        # Anti-nuke: {guild_id: {user_id: [timestamps_de_acao_destrutiva]}}
        self._nuke_tracker: dict = defaultdict(lambda: defaultdict(list))

        self._cleanup_task.start()

    def cog_unload(self):
        self._cleanup_task.cancel()

    # ── Limpeza periodica de trackers ─────────────────────────────────────────
    @tasks.loop(minutes=2)
    async def _cleanup_task(self):
        now = datetime.now(timezone.utc).timestamp()
        for gid in list(self._spam_tracker):
            for uid in list(self._spam_tracker[gid]):
                self._spam_tracker[gid][uid] = [
                    t for t in self._spam_tracker[gid][uid] if now - t < SPAM_WINDOW
                ]
        for gid in list(self._join_tracker):
            self._join_tracker[gid] = [
                t for t in self._join_tracker[gid] if now - t < RAID_WINDOW
            ]
        for gid in list(self._nuke_tracker):
            for uid in list(self._nuke_tracker[gid]):
                self._nuke_tracker[gid][uid] = [
                    t for t in self._nuke_tracker[gid][uid] if now - t < NUKE_WINDOW
                ]

    # ── Helpers internos ──────────────────────────────────────────────────────
    async def _log(self, guild: discord.Guild, emb: discord.Embed):
        ch_id = await Database.guild_get(guild.id, "config", "mod_log_channel")
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            try:
                await ch.send(embed=emb)
            except Exception as ex:
                log.warning(f"[MOD] Log falhou: {ex}")

    async def _dm(self, user: discord.abc.User, action: str, reason: str, guild: discord.Guild):
        try:
            emb = discord.Embed(
                title=f"Acao disciplinar em {guild.name}",
                description=f"Acao: {action}\nMotivo: {reason or 'Nao especificado'}",
                color=0xE74C3C,
            )
            await user.send(embed=emb)
        except Exception:
            pass

    def _hier_check(self, inter: discord.Interaction, membro: discord.Member) -> str | None:
        if membro == inter.guild.owner:
            return "Nao e possivel agir contra o dono do servidor."
        if membro.top_role >= inter.guild.me.top_role:
            return "O cargo do membro e igual ou superior ao meu."
        if membro.top_role >= inter.user.top_role and inter.user != inter.guild.owner:
            return "O cargo do membro e igual ou superior ao seu."
        return None

    def _is_exempt_channel(self, channel: discord.TextChannel) -> bool:
        name = channel.name.lower()
        return any(ex in name for ex in LOCKDOWN_EXEMPT_NAMES)

    async def _is_whitelisted(self, guild_id: int, user_id: int) -> bool:
        wl = await Database.guild_get(guild_id, "security", "whitelist") or []
        return str(user_id) in wl

    # ════════════════════════════════════════════════════════════════════════
    # COMANDOS DE MODERACAO BASE (mantidos integralmente)
    # ════════════════════════════════════════════════════════════════════════

    @app_commands.command(name="ban", description="Bane um membro do servidor")
    @app_commands.describe(membro="Membro a ser banido", motivo="Motivo do banimento",
                           delete_days="Dias de mensagens a apagar (0 a 7)")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, inter: discord.Interaction, membro: discord.Member,
                  motivo: str = "Sem motivo especificado",
                  delete_days: app_commands.Range[int, 0, 7] = 0):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        await self._dm(membro, "Banimento", motivo, inter.guild)
        await inter.guild.ban(membro, reason=f"[{inter.user}] {motivo}", delete_message_days=delete_days)
        await self._log(inter.guild, embed_mod("Ban", membro, inter.user, motivo))
        await Database.log_security(inter.guild.id, membro.id, "ban", f"Por {inter.user.id}: {motivo}")
        await inter.followup.send(
            embed=embed_success("Membro banido", f"{membro.mention} foi banido.\nMotivo: {motivo}"),
            ephemeral=True)

    @app_commands.command(name="unban", description="Remove o banimento de um usuario pelo ID")
    @app_commands.describe(user_id="ID do usuario banido", motivo="Motivo")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, inter: discord.Interaction, user_id: str,
                    motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await inter.guild.unban(user, reason=f"[{inter.user}] {motivo}")
            await self._log(inter.guild, embed_mod("Unban", user, inter.user, motivo))
            await inter.followup.send(
                embed=embed_success("Usuario desbanido", f"{user} foi desbanido."), ephemeral=True)
        except discord.NotFound:
            await inter.followup.send(
                embed=embed_error("Nao encontrado", f"ID `{user_id}` nao esta banido ou nao existe."),
                ephemeral=True)
        except ValueError:
            await inter.followup.send(
                embed=embed_error("ID invalido", "Informe um ID numerico valido."), ephemeral=True)

    @app_commands.command(name="kick", description="Expulsa um membro do servidor")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, inter: discord.Interaction, membro: discord.Member,
                   motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        await self._dm(membro, "Expulsao", motivo, inter.guild)
        await inter.guild.kick(membro, reason=f"[{inter.user}] {motivo}")
        await self._log(inter.guild, embed_mod("Kick", membro, inter.user, motivo))
        await Database.log_security(inter.guild.id, membro.id, "kick", f"Por {inter.user.id}: {motivo}")
        await inter.followup.send(
            embed=embed_success("Membro expulso", f"{membro.mention} foi expulso.\nMotivo: {motivo}"),
            ephemeral=True)

    @app_commands.command(name="timeout", description="Silencia um membro temporariamente")
    @app_commands.describe(membro="Membro", duracao="Duracao: ex. 10m, 2h, 1d (maximo 28d)", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, inter: discord.Interaction, membro: discord.Member,
                      duracao: str = "10m", motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        secs = duration_to_seconds(duracao)
        if secs <= 0:
            return await inter.followup.send(
                embed=embed_error("Duracao invalida", "Use o formato: 10s, 5m, 2h, 1d. Maximo: 28d."),
                ephemeral=True)
        until = discord.utils.utcnow() + timedelta(seconds=secs)
        await membro.timeout(until, reason=f"[{inter.user}] {motivo}")
        await self._dm(membro, f"Silenciado por {duracao}", motivo, inter.guild)
        await self._log(inter.guild, embed_mod("Timeout", membro, inter.user, motivo, f"Duracao: {duracao}"))
        await inter.followup.send(
            embed=embed_success("Membro silenciado",
                f"{membro.mention} silenciado por {duracao}.\nMotivo: {motivo}"),
            ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove o silencio de um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, inter: discord.Interaction, membro: discord.Member,
                        motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        await membro.timeout(None, reason=f"[{inter.user}] {motivo}")
        await self._log(inter.guild, embed_mod("Untimeout", membro, inter.user, motivo))
        await inter.followup.send(
            embed=embed_success("Silencio removido", f"{membro.mention} pode enviar mensagens novamente."),
            ephemeral=True)

    @app_commands.command(name="warn", description="Registra um aviso formal para um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo do aviso")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, inter: discord.Interaction, membro: discord.Member, motivo: str):
        await inter.response.defer(ephemeral=True)
        count = await Database.add_warn(inter.guild.id, membro.id, inter.user.id, motivo)
        await self._dm(membro, f"Aviso numero {count}", motivo, inter.guild)
        await self._log(inter.guild, embed_mod("Warn", membro, inter.user, motivo, f"Total de avisos: {count}"))
        await Database.log_security(inter.guild.id, membro.id, "warn", f"Por {inter.user.id}: {motivo}")
        extra = ""
        if count in WARN_THRESHOLDS:
            action, dur = WARN_THRESHOLDS[count]
            try:
                reason_auto = f"[AutoWarn] Limite de {count} avisos atingido"
                if action == "timeout" and dur:
                    secs = duration_to_seconds(dur)
                    await membro.timeout(discord.utils.utcnow() + timedelta(seconds=secs), reason=reason_auto)
                    extra = f"\nMembro silenciado automaticamente por {dur} ({count} avisos)."
                elif action == "kick":
                    await inter.guild.kick(membro, reason=reason_auto)
                    extra = f"\nMembro expulso automaticamente ({count} avisos)."
                elif action == "ban":
                    await inter.guild.ban(membro, reason=reason_auto, delete_message_days=0)
                    extra = f"\nMembro banido automaticamente ({count} avisos)."
            except Exception as ex:
                log.warning(f"[MOD] Escalonamento falhou: {ex}")
                extra = f"\nEscalonamento automatico falhou: {ex}"
        await inter.followup.send(
            embed=embed_success(f"Aviso numero {count} registrado",
                f"{membro.mention}\nMotivo: {motivo}{extra}"),
            ephemeral=True)

    @app_commands.command(name="warnings", description="Lista os avisos de um membro")
    @app_commands.describe(membro="Membro a verificar")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, inter: discord.Interaction, membro: discord.Member):
        warns = await Database.get_warns(inter.guild.id, membro.id)
        if not warns:
            return await inter.response.send_message(
                embed=embed_info("Sem avisos", f"{membro.mention} nao possui avisos registrados."),
                ephemeral=True)
        emb = discord.Embed(title=f"Avisos de {membro}", description=f"Total: {len(warns)} aviso(s)", color=0xF39C12)
        for i, w in enumerate(warns[:10], 1):
            mod = inter.guild.get_member(w["moderator_id"])
            ts  = w["created_at"].strftime("%d/%m/%Y")
            emb.add_field(
                name=f"Aviso {i}",
                value=f"Motivo: {w['reason']}\nModerador: {mod.mention if mod else w['moderator_id']}\nData: {ts}",
                inline=False)
        await inter.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(name="clearwarn", description="Remove todos os avisos de um membro")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def clearwarn(self, inter: discord.Interaction, membro: discord.Member):
        await Database.clear_warns(inter.guild.id, membro.id)
        await inter.response.send_message(
            embed=embed_success("Avisos removidos", f"Todos os avisos de {membro.mention} foram removidos."),
            ephemeral=True)

    @app_commands.command(name="purge", description="Apaga mensagens em massa no canal atual")
    @app_commands.describe(quantidade="Numero de mensagens (1 a 100)", membro="Filtrar por membro (opcional)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, inter: discord.Interaction, quantidade: app_commands.Range[int, 1, 100],
                    membro: discord.Member = None):
        await inter.response.defer(ephemeral=True)
        check   = (lambda m: m.author == membro) if membro else None
        deleted = await inter.channel.purge(limit=quantidade, check=check)
        desc = f"{len(deleted)} mensagem(ns) apagada(s)"
        if membro:
            desc += f" de {membro.mention}"
        await inter.followup.send(embed=embed_success("Limpeza concluida", desc), ephemeral=True)

    @app_commands.command(name="slowmode", description="Define o modo lento do canal")
    @app_commands.describe(segundos="Intervalo em segundos (0 para desativar, maximo 21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, inter: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]):
        await inter.channel.edit(slowmode_delay=segundos)
        msg = f"Modo lento definido para {segundos}s." if segundos else "Modo lento desativado."
        await inter.response.send_message(embed=embed_success("Modo Lento", msg), ephemeral=True)

    @app_commands.command(name="lock", description="Bloqueia o envio de mensagens no canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = False
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(
            embed=embed_success("Canal bloqueado", f"{inter.channel.mention} foi bloqueado."))

    @app_commands.command(name="unlock", description="Desbloqueia o canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = None
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(
            embed=embed_success("Canal desbloqueado", f"{inter.channel.mention} foi desbloqueado."))

    @app_commands.command(name="lockdown", description="Bloqueia TODOS os canais de texto do servidor")
    @app_commands.describe(motivo="Motivo do lockdown")
    @app_commands.default_permissions(administrator=True)
    async def lockdown(self, inter: discord.Interaction, motivo: str = "Lockdown ativado pela moderacao."):
        await inter.response.defer()
        bloqueados = 0
        ignorados  = 0
        for channel in inter.guild.text_channels:
            if self._is_exempt_channel(channel):
                ignorados += 1
                continue
            try:
                ow = channel.overwrites_for(inter.guild.default_role)
                ow.send_messages = False
                await channel.set_permissions(inter.guild.default_role, overwrite=ow)
                await channel.send(embed=discord.Embed(
                    title="Canal bloqueado",
                    description=f"Este canal foi bloqueado temporariamente.\nMotivo: {motivo}",
                    color=0xE74C3C))
                bloqueados += 1
            except Exception as ex:
                log.warning(f"[LOCKDOWN] Falha em #{channel.name}: {ex}")
                ignorados += 1
        await self._log(inter.guild, discord.Embed(
            title="Lockdown ativado",
            description=f"Moderador: {inter.user.mention}\nMotivo: {motivo}\nCanais bloqueados: {bloqueados}",
            color=0xE74C3C, timestamp=discord.utils.utcnow()))
        await inter.followup.send(embed=embed_success(
            "Lockdown ativado",
            f"{bloqueados} canal(is) bloqueado(s).\n{ignorados} ignorado(s).\nMotivo: {motivo}"))

    @app_commands.command(name="unlockdown", description="Remove o bloqueio de TODOS os canais de texto")
    @app_commands.default_permissions(administrator=True)
    async def unlockdown(self, inter: discord.Interaction):
        await inter.response.defer()
        desbloqueados = 0
        for channel in inter.guild.text_channels:
            try:
                ow = channel.overwrites_for(inter.guild.default_role)
                ow.send_messages = None
                await channel.set_permissions(inter.guild.default_role, overwrite=ow)
                desbloqueados += 1
            except Exception as ex:
                log.warning(f"[UNLOCKDOWN] Falha em #{channel.name}: {ex}")
        await self._log(inter.guild, discord.Embed(
            title="Lockdown encerrado",
            description=f"Moderador: {inter.user.mention}\nCanais desbloqueados: {desbloqueados}",
            color=0x2ECC71, timestamp=discord.utils.utcnow()))
        await inter.followup.send(
            embed=embed_success("Lockdown encerrado", f"{desbloqueados} canal(is) desbloqueado(s)."))

    @app_commands.command(name="setlogchannel", description="Define o canal de logs de moderacao")
    @app_commands.describe(canal="Canal de texto para os logs")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, inter: discord.Interaction, canal: discord.TextChannel):
        await Database.guild_set(inter.guild.id, "config", "mod_log_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success("Canal de log definido", f"Logs de moderacao serao enviados em {canal.mention}."),
            ephemeral=True)

    @app_commands.command(name="userinfo", description="Exibe informacoes detalhadas sobre um membro")
    @app_commands.describe(membro="Membro (deixe vazio para suas proprias informacoes)")
    async def userinfo(self, inter: discord.Interaction, membro: discord.Member = None):
        m     = membro or inter.user
        count = await Database.count_warns(inter.guild.id, m.id)
        emb   = discord.Embed(title=str(m), color=m.color or 0x5865F2)
        emb.set_thumbnail(url=m.display_avatar.url)
        emb.add_field(name="ID",           value=str(m.id),          inline=True)
        emb.add_field(name="Apelido",      value=m.display_name,     inline=True)
        emb.add_field(name="Conta criada", value=discord.utils.format_dt(m.created_at, "R"), inline=True)
        emb.add_field(name="Entrou",       value=discord.utils.format_dt(m.joined_at, "R"),  inline=True)
        emb.add_field(name="Bot",          value="Sim" if m.bot else "Nao", inline=True)
        emb.add_field(name="Avisos",       value=str(count), inline=True)
        # Idade da conta em dias
        age_days = (discord.utils.utcnow() - m.created_at).days
        emb.add_field(name="Idade da conta", value=f"{age_days} dia(s)", inline=True)
        # Status de timeout
        timed_out = m.timed_out_until and m.timed_out_until > discord.utils.utcnow()
        emb.add_field(name="Silenciado", value="Sim" if timed_out else "Nao", inline=True)
        roles = [r.mention for r in reversed(m.roles) if r != inter.guild.default_role]
        emb.add_field(name=f"Cargos ({len(roles)})", value=" ".join(roles[:12]) or "Nenhum", inline=False)
        emb.set_footer(text="Filosofia Bot")
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # NOVOS COMANDOS
    # ════════════════════════════════════════════════════════════════════════

    # ── /softban ──────────────────────────────────────────────────────────────
    @app_commands.command(name="softban", description="Bane e desbane para limpar mensagens recentes")
    @app_commands.describe(membro="Membro", motivo="Motivo",
                           delete_days="Dias de mensagens a apagar (1 a 7)")
    @app_commands.default_permissions(ban_members=True)
    async def softban(self, inter: discord.Interaction, membro: discord.Member,
                      motivo: str = "Softban — limpeza de mensagens",
                      delete_days: app_commands.Range[int, 1, 7] = 1):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        await self._dm(membro, "Softban (voce pode entrar novamente)", motivo, inter.guild)
        await inter.guild.ban(membro, reason=f"[Softban] [{inter.user}] {motivo}", delete_message_days=delete_days)
        await inter.guild.unban(membro, reason="[Softban] Desban automatico")
        await self._log(inter.guild, embed_mod("Softban", membro, inter.user, motivo,
                                               f"{delete_days} dia(s) de mensagens apagadas"))
        await Database.log_security(inter.guild.id, membro.id, "softban", f"Por {inter.user.id}: {motivo}")
        await inter.followup.send(
            embed=embed_success("Softban aplicado",
                f"{membro.mention} foi banido e desbanido.\n{delete_days} dia(s) de mensagens apagadas."),
            ephemeral=True)

    # ── /quarantine ───────────────────────────────────────────────────────────
    @app_commands.command(name="quarantine", description="Isola um membro removendo todos os seus cargos")
    @app_commands.describe(membro="Membro a isolar", motivo="Motivo")
    @app_commands.default_permissions(administrator=True)
    async def quarantine(self, inter: discord.Interaction, membro: discord.Member,
                         motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)

        # Salva os cargos no banco para restaurar depois
        role_ids = [str(r.id) for r in membro.roles if r != inter.guild.default_role]
        await Database.guild_set(inter.guild.id, "quarantine", str(membro.id), role_ids)

        # Remove todos os cargos
        removable = [r for r in membro.roles if r != inter.guild.default_role and r < inter.guild.me.top_role]
        if removable:
            await membro.remove_roles(*removable, reason=f"[Quarentena] {inter.user}: {motivo}")

        # Timeout de 28 dias (maximo)
        until = discord.utils.utcnow() + timedelta(days=28)
        try:
            await membro.timeout(until, reason=f"[Quarentena] {motivo}")
        except Exception:
            pass

        await self._dm(membro, "Quarentena", motivo, inter.guild)
        await self._log(inter.guild, embed_mod("Quarentena", membro, inter.user, motivo,
                                               f"Cargos salvos: {len(role_ids)}"))
        await Database.log_security(inter.guild.id, membro.id, "quarantine", f"Por {inter.user.id}: {motivo}")
        await inter.followup.send(
            embed=embed_success("Membro em quarentena",
                f"{membro.mention} foi isolado. Use `/unquarantine` para restaurar."),
            ephemeral=True)

    # ── /unquarantine ─────────────────────────────────────────────────────────
    @app_commands.command(name="unquarantine", description="Remove a quarentena e restaura os cargos do membro")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(administrator=True)
    async def unquarantine(self, inter: discord.Interaction, membro: discord.Member,
                           motivo: str = "Quarentena encerrada"):
        await inter.response.defer(ephemeral=True)
        role_ids = await Database.guild_get(inter.guild.id, "quarantine", str(membro.id))
        if not role_ids:
            return await inter.followup.send(
                embed=embed_error("Sem dados", f"{membro.mention} nao esta em quarentena ou os dados foram perdidos."),
                ephemeral=True)

        # Remove timeout
        try:
            await membro.timeout(None, reason=f"[Unquarantine] {motivo}")
        except Exception:
            pass

        # Restaura cargos
        restored = 0
        for rid in role_ids:
            role = inter.guild.get_role(int(rid))
            if role and role < inter.guild.me.top_role:
                try:
                    await membro.add_roles(role, reason=f"[Unquarantine] {motivo}")
                    restored += 1
                except Exception:
                    pass

        await Database.guild_delete(inter.guild.id, "quarantine", str(membro.id))
        await self._log(inter.guild, embed_mod("Unquarantine", membro, inter.user, motivo,
                                               f"Cargos restaurados: {restored}"))
        await inter.followup.send(
            embed=embed_success("Quarentena encerrada",
                f"{membro.mention} liberado. {restored} cargo(s) restaurado(s)."),
            ephemeral=True)

    # ── /banlist ──────────────────────────────────────────────────────────────
    @app_commands.command(name="banlist", description="Lista os usuarios banidos do servidor")
    @app_commands.default_permissions(ban_members=True)
    async def banlist(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        bans = [entry async for entry in inter.guild.bans(limit=20)]
        if not bans:
            return await inter.followup.send(
                embed=embed_info("Sem banimentos", "Nenhum usuario banido no servidor."), ephemeral=True)
        emb = discord.Embed(title=f"Lista de banimentos ({len(bans)} exibidos)", color=0xE74C3C)
        for entry in bans[:20]:
            emb.add_field(
                name=str(entry.user),
                value=f"ID: `{entry.user.id}`\nMotivo: {entry.reason or 'Sem motivo'}",
                inline=False)
        await inter.followup.send(embed=emb, ephemeral=True)

    # ── /rolepurge ────────────────────────────────────────────────────────────
    @app_commands.command(name="rolepurge", description="Remove um cargo de todos os membros que o possuem")
    @app_commands.describe(cargo="Cargo a remover", motivo="Motivo")
    @app_commands.default_permissions(administrator=True)
    async def rolepurge(self, inter: discord.Interaction, cargo: discord.Role,
                        motivo: str = "Remocao em massa de cargo"):
        await inter.response.defer(ephemeral=True)
        if cargo >= inter.guild.me.top_role:
            return await inter.followup.send(
                embed=embed_error("Sem permissao", "Nao posso remover esse cargo (hierarquia)."), ephemeral=True)
        targets = [m for m in cargo.members]
        removed = 0
        for m in targets:
            try:
                await m.remove_roles(cargo, reason=f"[RolePurge] {inter.user}: {motivo}")
                removed += 1
            except Exception:
                pass
        await self._log(inter.guild, discord.Embed(
            title="RolePurge",
            description=f"Cargo: {cargo.mention}\nModerador: {inter.user.mention}\nRemovido de: {removed} membro(s)\nMotivo: {motivo}",
            color=0xF39C12, timestamp=discord.utils.utcnow()))
        await inter.followup.send(
            embed=embed_success("Cargo removido em massa",
                f"Cargo {cargo.mention} removido de {removed} membro(s)."),
            ephemeral=True)

    # ── /massnick ─────────────────────────────────────────────────────────────
    @app_commands.command(name="massnick", description="Altera o apelido de membros com um cargo especifico")
    @app_commands.describe(cargo="Cargo alvo", apelido="Novo apelido (deixe vazio para resetar)")
    @app_commands.default_permissions(manage_nicknames=True)
    async def massnick(self, inter: discord.Interaction, cargo: discord.Role,
                       apelido: str = ""):
        await inter.response.defer(ephemeral=True)
        altered = 0
        for m in cargo.members:
            if m == inter.guild.me or m == inter.guild.owner:
                continue
            try:
                await m.edit(nick=apelido or None, reason=f"[MassNick] {inter.user}")
                altered += 1
            except Exception:
                pass
        msg = f"Apelido definido para '{apelido}'" if apelido else "Apelidos resetados"
        await inter.followup.send(
            embed=embed_success("MassNick concluido", f"{msg} em {altered} membro(s) com o cargo {cargo.mention}."),
            ephemeral=True)

    # ── /nick ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Altera o apelido de um membro")
    @app_commands.describe(membro="Membro", apelido="Novo apelido (deixe vazio para resetar)")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick(self, inter: discord.Interaction, membro: discord.Member, apelido: str = ""):
        await inter.response.defer(ephemeral=True)
        try:
            await membro.edit(nick=apelido or None, reason=f"[Nick] {inter.user}")
            msg = f"Apelido de {membro.mention} alterado para `{apelido}`." if apelido else f"Apelido de {membro.mention} resetado."
            await inter.followup.send(embed=embed_success("Apelido alterado", msg), ephemeral=True)
        except discord.Forbidden:
            await inter.followup.send(embed=embed_error("Sem permissao", "Nao foi possivel alterar o apelido."), ephemeral=True)

    # ── /contanova ────────────────────────────────────────────────────────────
    @app_commands.command(name="contanova", description="Configura a idade minima de conta para entrar no servidor")
    @app_commands.describe(dias="Minimo de dias de existencia da conta (0 para desativar)",
                           acao="Acao ao detectar conta nova")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Apenas alertar", value="alert"),
        app_commands.Choice(name="Expulsar",        value="kick"),
        app_commands.Choice(name="Banir",           value="ban"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def contanova(self, inter: discord.Interaction, dias: app_commands.Range[int, 0, 365],
                        acao: str = "alert"):
        await Database.guild_set(inter.guild.id, "security", "new_account_days", dias)
        await Database.guild_set(inter.guild.id, "security", "new_account_action", acao)
        if dias == 0:
            return await inter.response.send_message(
                embed=embed_success("Conta nova desativado", "Verificacao de conta nova desativada."), ephemeral=True)
        await inter.response.send_message(
            embed=embed_success("Conta nova configurado",
                f"Contas com menos de {dias} dia(s) serao: **{acao}**."),
            ephemeral=True)

    # ── /whitelist ────────────────────────────────────────────────────────────
    mod_group = app_commands.Group(name="whitelist", description="Gerenciar whitelist do anti-nuke")

    @mod_group.command(name="add", description="Adiciona um usuario a whitelist do anti-nuke")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_add(self, inter: discord.Interaction, membro: discord.Member):
        wl = await Database.guild_get(inter.guild.id, "security", "whitelist") or []
        if str(membro.id) not in wl:
            wl.append(str(membro.id))
            await Database.guild_set(inter.guild.id, "security", "whitelist", wl)
        await inter.response.send_message(
            embed=embed_success("Whitelist", f"{membro.mention} adicionado a whitelist do anti-nuke."),
            ephemeral=True)

    @mod_group.command(name="remove", description="Remove um usuario da whitelist do anti-nuke")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_remove(self, inter: discord.Interaction, membro: discord.Member):
        wl = await Database.guild_get(inter.guild.id, "security", "whitelist") or []
        wl = [x for x in wl if x != str(membro.id)]
        await Database.guild_set(inter.guild.id, "security", "whitelist", wl)
        await inter.response.send_message(
            embed=embed_success("Whitelist", f"{membro.mention} removido da whitelist."), ephemeral=True)

    @mod_group.command(name="ver", description="Exibe a whitelist atual do anti-nuke")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_view(self, inter: discord.Interaction):
        wl = await Database.guild_get(inter.guild.id, "security", "whitelist") or []
        if not wl:
            return await inter.response.send_message(
                embed=embed_info("Whitelist vazia", "Nenhum usuario na whitelist."), ephemeral=True)
        membros = []
        for uid in wl:
            m = inter.guild.get_member(int(uid))
            membros.append(m.mention if m else f"`{uid}`")
        await inter.response.send_message(
            embed=embed_info("Whitelist do anti-nuke", "\n".join(membros)), ephemeral=True)

    # ── /antispam ─────────────────────────────────────────────────────────────
    @app_commands.command(name="antispam", description="Ativa ou desativa o antispam automatico")
    @app_commands.describe(ativo="Ativar ou desativar")
    @app_commands.choices(ativo=[
        app_commands.Choice(name="Ativar",   value="on"),
        app_commands.Choice(name="Desativar", value="off"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def antispam_cmd(self, inter: discord.Interaction, ativo: str):
        await Database.guild_set(inter.guild.id, "security", "antispam", ativo)
        msg = "Antispam ativado." if ativo == "on" else "Antispam desativado."
        await inter.response.send_message(embed=embed_success("Antispam", msg), ephemeral=True)

    # ── /antiraid config ──────────────────────────────────────────────────────
    @app_commands.command(name="antiraid", description="Ativa ou desativa o antiraid automatico")
    @app_commands.describe(ativo="Ativar ou desativar")
    @app_commands.choices(ativo=[
        app_commands.Choice(name="Ativar",    value="on"),
        app_commands.Choice(name="Desativar", value="off"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def antiraid_cmd(self, inter: discord.Interaction, ativo: str):
        await Database.guild_set(inter.guild.id, "security", "antiraid", ativo)
        msg = "Antiraid automatico ativado." if ativo == "on" else "Antiraid automatico desativado."
        await inter.response.send_message(embed=embed_success("Antiraid", msg), ephemeral=True)

    # ── /raidkick ─────────────────────────────────────────────────────────────
    @app_commands.command(name="raidkick", description="Expulsa manualmente membros que entraram nos ultimos N minutos")
    @app_commands.describe(minutos="Janela de tempo (1 a 60)")
    @app_commands.default_permissions(administrator=True)
    async def raidkick(self, inter: discord.Interaction, minutos: app_commands.Range[int, 1, 60]):
        await inter.response.defer(ephemeral=True)
        cutoff  = discord.utils.utcnow() - timedelta(minutes=minutos)
        targets = [m for m in inter.guild.members
                   if m.joined_at and m.joined_at >= cutoff and not m.bot and m != inter.user]
        if not targets:
            return await inter.followup.send(
                embed=embed_info("Nenhum alvo", f"Nenhum membro entrou nos ultimos {minutos} minuto(s)."),
                ephemeral=True)
        kicked = 0
        for m in targets:
            try:
                await inter.guild.kick(m, reason=f"[RaidKick] Por {inter.user}")
                await Database.log_security(inter.guild.id, m.id, "raidkick",
                                            f"Expulso por raidkick por {inter.user.id}")
                kicked += 1
            except Exception:
                pass
        await self._log(inter.guild, discord.Embed(
            title="RaidKick executado",
            description=f"Moderador: {inter.user.mention}\nJanela: {minutos} min\nExpulsos: {kicked}",
            color=0xE74C3C, timestamp=discord.utils.utcnow()))
        await inter.followup.send(
            embed=embed_success("RaidKick concluido", f"{kicked} membro(s) expulso(s)."), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # LISTENERS — SEGURANCA AUTOMATICA
    # ════════════════════════════════════════════════════════════════════════

    # ── Antispam automatico ───────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.author.guild_permissions.manage_messages:
            return

        enabled = await Database.guild_get(message.guild.id, "security", "antispam")
        if enabled != "on":
            return

        now = datetime.now(timezone.utc).timestamp()
        gid = message.guild.id
        uid = message.author.id

        self._spam_tracker[gid][uid].append(now)
        self._spam_tracker[gid][uid] = [
            t for t in self._spam_tracker[gid][uid] if now - t <= SPAM_WINDOW
        ]

        if len(self._spam_tracker[gid][uid]) >= SPAM_LIMIT:
            self._spam_tracker[gid][uid] = []
            try:
                until = discord.utils.utcnow() + timedelta(seconds=SPAM_TIMEOUT)
                await message.author.timeout(until, reason="[AutoMod] Spam detectado")
                await message.channel.purge(limit=10, check=lambda m: m.author == message.author)
                await self._log(message.guild, discord.Embed(
                    title="Antispam — Timeout automatico",
                    description=f"Usuario: {message.author.mention} (`{message.author.id}`)\nCanal: {message.channel.mention}\nTimeout: {SPAM_TIMEOUT}s",
                    color=0xFEE75C, timestamp=discord.utils.utcnow()))
                try:
                    await message.author.send(embed=discord.Embed(
                        title="Voce foi silenciado por spam",
                        description=f"Spam detectado em **{message.guild.name}**. Timeout de {SPAM_TIMEOUT}s aplicado.",
                        color=0xFEE75C))
                except Exception:
                    pass
            except Exception as ex:
                log.warning(f"[ANTISPAM] Falhou: {ex}")

    # ── Anti-raid automatico ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        # Verificacao de conta nova
        min_days = await Database.guild_get(guild.id, "security", "new_account_days")
        if min_days and int(min_days) > 0:
            age_days = (discord.utils.utcnow() - member.created_at).days
            if age_days < int(min_days):
                action = await Database.guild_get(guild.id, "security", "new_account_action") or "alert"
                await Database.log_security(guild.id, member.id, "new_account",
                                            f"Conta com {age_days} dia(s), minimo: {min_days}")
                await self._log(guild, discord.Embed(
                    title="Alerta — Conta nova detectada",
                    description=f"Membro: {member.mention} (`{member.id}`)\nIdade da conta: {age_days} dia(s)\nMinimo configurado: {min_days} dia(s)\nAcao: {action}",
                    color=0xF39C12, timestamp=discord.utils.utcnow()))
                if action == "kick":
                    try:
                        await member.send(embed=discord.Embed(
                            description=f"Sua conta e muito nova para entrar em **{guild.name}**. Tente novamente em {int(min_days) - age_days} dia(s).",
                            color=0xE74C3C))
                    except Exception:
                        pass
                    await guild.kick(member, reason=f"[ContaNova] Conta com {age_days} dia(s), minimo: {min_days}")
                    return
                elif action == "ban":
                    await guild.ban(member, reason=f"[ContaNova] Conta com {age_days} dia(s), minimo: {min_days}")
                    return

        # Anti-raid automatico
        enabled = await Database.guild_get(guild.id, "security", "antiraid")
        if enabled != "on":
            return

        now = datetime.now(timezone.utc).timestamp()
        self._join_tracker[guild.id].append(now)
        self._join_tracker[guild.id] = [
            t for t in self._join_tracker[guild.id] if now - t <= RAID_WINDOW
        ]

        if len(self._join_tracker[guild.id]) >= RAID_LIMIT and guild.id not in self._raid_mode:
            self._raid_mode.add(guild.id)
            self._join_tracker[guild.id] = []

            # Bloqueia todos os canais
            bloqueados = 0
            for ch in guild.text_channels:
                if self._is_exempt_channel(ch):
                    continue
                try:
                    ow = ch.overwrites_for(guild.default_role)
                    ow.send_messages = False
                    await ch.set_permissions(guild.default_role, overwrite=ow)
                    bloqueados += 1
                except Exception:
                    pass

            await self._log(guild, discord.Embed(
                title="RAID DETECTADO — Lockdown automatico ativado",
                description=f"Mais de {RAID_LIMIT} joins em {RAID_WINDOW}s detectados.\n{bloqueados} canal(is) bloqueado(s).\nLockdown sera removido automaticamente em {RAID_LOCKOUT}s.",
                color=0xFF0000, timestamp=discord.utils.utcnow()))

            # Remove lockdown apos o tempo
            await asyncio.sleep(RAID_LOCKOUT)
            for ch in guild.text_channels:
                try:
                    ow = ch.overwrites_for(guild.default_role)
                    ow.send_messages = None
                    await ch.set_permissions(guild.default_role, overwrite=ow)
                except Exception:
                    pass
            self._raid_mode.discard(guild.id)
            await self._log(guild, discord.Embed(
                title="Lockdown anti-raid encerrado automaticamente",
                color=0x2ECC71, timestamp=discord.utils.utcnow()))

    # ── Anti-nuke automatico ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        await self._log(guild, discord.Embed(
            title="Alerta — Canal deletado",
            description=f"Canal: **#{channel.name}**",
            color=0xF39C12, timestamp=discord.utils.utcnow()))

        # Detecta nuke: multiplas delecoes rapidas
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if await self._is_whitelisted(guild.id, entry.user.id):
                return
            now = datetime.now(timezone.utc).timestamp()
            self._nuke_tracker[guild.id][entry.user.id].append(now)
            self._nuke_tracker[guild.id][entry.user.id] = [
                t for t in self._nuke_tracker[guild.id][entry.user.id] if now - t <= NUKE_WINDOW
            ]
            if len(self._nuke_tracker[guild.id][entry.user.id]) >= NUKE_LIMIT:
                self._nuke_tracker[guild.id][entry.user.id] = []
                try:
                    suspect = guild.get_member(entry.user.id)
                    if suspect and suspect != guild.owner:
                        await suspect.timeout(
                            discord.utils.utcnow() + timedelta(hours=24),
                            reason="[AntiNuke] Delecao em massa de canais detectada")
                        await Database.log_security(guild.id, suspect.id, "antinuke_timeout",
                                                    "Timeout por delecao em massa de canais")
                        await self._log(guild, discord.Embed(
                            title="ANTI-NUKE — Timeout aplicado",
                            description=f"Usuario: {suspect.mention} (`{suspect.id}`)\nMotivo: Delecao em massa de canais detectada.\nTimeout: 24h",
                            color=0xFF0000, timestamp=discord.utils.utcnow()))
                except Exception as ex:
                    log.warning(f"[ANTINUKE] Falhou: {ex}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if await self._is_whitelisted(guild.id, entry.user.id):
                return
            now = datetime.now(timezone.utc).timestamp()
            uid = entry.user.id
            self._nuke_tracker[guild.id][uid].append(now)
            self._nuke_tracker[guild.id][uid] = [
                t for t in self._nuke_tracker[guild.id][uid] if now - t <= NUKE_WINDOW
            ]
            if len(self._nuke_tracker[guild.id][uid]) >= NUKE_LIMIT:
                self._nuke_tracker[guild.id][uid] = []
                suspect = guild.get_member(uid)
                if suspect and suspect != guild.owner:
                    try:
                        await suspect.timeout(
                            discord.utils.utcnow() + timedelta(hours=24),
                            reason="[AntiNuke] Delecao em massa de cargos detectada")
                        await self._log(guild, discord.Embed(
                            title="ANTI-NUKE — Timeout aplicado",
                            description=f"Usuario: {suspect.mention}\nMotivo: Delecao em massa de cargos detectada.\nTimeout: 24h",
                            color=0xFF0000, timestamp=discord.utils.utcnow()))
                    except Exception as ex:
                        log.warning(f"[ANTINUKE] Cargo falhou: {ex}")

    # ── Detector de admin malicioso ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        had_admin = before.guild_permissions.administrator
        has_admin = after.guild_permissions.administrator
        if had_admin or not has_admin:
            return
        await Database.log_security(after.guild.id, after.id, "admin_grant",
                                    f"Membro {after} recebeu permissao de administrador.")
        await self._log(after.guild, discord.Embed(
            title="Alerta — Administrador concedido",
            description=f"{after.mention} recebeu permissao de **Administrador**.\nSe nao foi intencional, revogue o cargo imediatamente.",
            color=0xE74C3C, timestamp=discord.utils.utcnow()))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if not role.permissions.administrator:
            return
        await self._log(role.guild, discord.Embed(
            title="Alerta — Cargo administrativo criado",
            description=f"O cargo **{role.name}** foi criado com permissao de Administrador.",
            color=0xE74C3C, timestamp=discord.utils.utcnow()))

    # ── /security-log ─────────────────────────────────────────────────────────
    @app_commands.command(name="security-log", description="Exibe os ultimos eventos de seguranca do servidor")
    @app_commands.default_permissions(administrator=True)
    async def security_log(self, inter: discord.Interaction):
        rows = await Database.pool.fetch(
            "SELECT * FROM security_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 15",
            inter.guild.id)
        if not rows:
            return await inter.response.send_message(
                embed=embed_info("Sem registros", "Nenhum evento de seguranca registrado."), ephemeral=True)
        emb = discord.Embed(title="Log de Seguranca", color=0xE74C3C)
        for r in rows:
            member = inter.guild.get_member(r["user_id"])
            name   = str(member) if member else str(r["user_id"])
            ts     = r["created_at"].strftime("%d/%m/%Y %H:%M")
            emb.add_field(
                name=f"{r['action']} — {ts}",
                value=f"Usuario: {name}\nDetalhe: {r['detail'] or '—'}",
                inline=False)
        await inter.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
