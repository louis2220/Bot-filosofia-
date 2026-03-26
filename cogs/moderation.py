"""
cogs/moderation.py
Moderacao completa com PostgreSQL, lock/unlock em massa e protecao anti-admin malicioso.
Sem emojis em nenhuma parte do codigo.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import logging

from utils.helpers import (
    embed_mod, embed_success, embed_error, embed_info, embed_warn,
    duration_to_seconds, format_duration,
)
from utils.db import Database

log = logging.getLogger("filosofia.moderation")

# Limites de avisos para acoes automaticas escalonadas
WARN_THRESHOLDS = {
    3:  ("timeout", "15m"),
    5:  ("timeout", "1h"),
    7:  ("kick",    None),
    10: ("ban",     None),
}

# Canais que nunca devem ser bloqueados no lockdown total (por nome parcial)
LOCKDOWN_EXEMPT_NAMES = {"log", "logs", "staff", "mod", "admin", "moderacao"}


class Moderation(commands.Cog):
    """Moderacao: ban, kick, timeout, warn, purge, lock, unlock, lockdown, security."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    # ── /ban ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Bane um membro do servidor")
    @app_commands.describe(
        membro="Membro a ser banido",
        motivo="Motivo do banimento",
        delete_days="Dias de mensagens a apagar (0 a 7)"
    )
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
            ephemeral=True,
        )

    # ── /unban ────────────────────────────────────────────────────────────────
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

    # ── /kick ─────────────────────────────────────────────────────────────────
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
            ephemeral=True,
        )

    # ── /timeout ──────────────────────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Silencia um membro temporariamente")
    @app_commands.describe(
        membro="Membro",
        duracao="Duracao: ex. 10m, 2h, 1d (maximo 28d)",
        motivo="Motivo"
    )
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
            ephemeral=True,
        )

    # ── /untimeout ────────────────────────────────────────────────────────────
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
            ephemeral=True,
        )

    # ── /warn ─────────────────────────────────────────────────────────────────
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
            embed=embed_success(
                f"Aviso numero {count} registrado",
                f"{membro.mention}\nMotivo: {motivo}{extra}"
            ),
            ephemeral=True,
        )

    # ── /warnings ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Lista os avisos de um membro")
    @app_commands.describe(membro="Membro a verificar")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, inter: discord.Interaction, membro: discord.Member):
        warns = await Database.get_warns(inter.guild.id, membro.id)
        if not warns:
            return await inter.response.send_message(
                embed=embed_info("Sem avisos", f"{membro.mention} nao possui avisos registrados."),
                ephemeral=True)
        emb = discord.Embed(
            title=f"Avisos de {membro}",
            description=f"Total: {len(warns)} aviso(s)",
            color=0xF39C12,
        )
        for i, w in enumerate(warns[:10], 1):
            mod = inter.guild.get_member(w["moderator_id"])
            ts = w["created_at"].strftime("%d/%m/%Y")
            emb.add_field(
                name=f"Aviso {i}",
                value=f"Motivo: {w['reason']}\nModerador: {mod.mention if mod else w['moderator_id']}\nData: {ts}",
                inline=False,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /clearwarn ────────────────────────────────────────────────────────────
    @app_commands.command(name="clearwarn", description="Remove todos os avisos de um membro")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def clearwarn(self, inter: discord.Interaction, membro: discord.Member):
        await Database.clear_warns(inter.guild.id, membro.id)
        await inter.response.send_message(
            embed=embed_success("Avisos removidos", f"Todos os avisos de {membro.mention} foram removidos."),
            ephemeral=True)

    # ── /purge ────────────────────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Apaga mensagens em massa no canal atual")
    @app_commands.describe(
        quantidade="Numero de mensagens (1 a 100)",
        membro="Filtrar por membro especifico (opcional)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, inter: discord.Interaction,
                    quantidade: app_commands.Range[int, 1, 100],
                    membro: discord.Member = None):
        await inter.response.defer(ephemeral=True)
        check = (lambda m: m.author == membro) if membro else None
        deleted = await inter.channel.purge(limit=quantidade, check=check)
        desc = f"{len(deleted)} mensagem(ns) apagada(s)"
        if membro:
            desc += f" de {membro.mention}"
        await inter.followup.send(embed=embed_success("Limpeza concluida", desc), ephemeral=True)

    # ── /slowmode ─────────────────────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Define o modo lento do canal")
    @app_commands.describe(segundos="Intervalo em segundos (0 para desativar, maximo 21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, inter: discord.Interaction,
                       segundos: app_commands.Range[int, 0, 21600]):
        await inter.channel.edit(slowmode_delay=segundos)
        msg = f"Modo lento definido para {segundos}s." if segundos else "Modo lento desativado."
        await inter.response.send_message(embed=embed_success("Modo Lento", msg), ephemeral=True)

    # ── /lock ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Bloqueia o envio de mensagens no canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = False
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(
            embed=embed_success("Canal bloqueado", f"{inter.channel.mention} foi bloqueado para todos os membros.")
        )

    # ── /unlock ───────────────────────────────────────────────────────────────
    @app_commands.command(name="unlock", description="Desbloqueia o canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = None
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(
            embed=embed_success("Canal desbloqueado", f"{inter.channel.mention} foi desbloqueado.")
        )

    # ── /lockdown ─────────────────────────────────────────────────────────────
    @app_commands.command(name="lockdown", description="Bloqueia TODOS os canais de texto do servidor")
    @app_commands.describe(motivo="Motivo do lockdown (exibido nos canais)")
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
                await channel.send(
                    embed=discord.Embed(
                        title="Canal bloqueado",
                        description=f"Este canal foi bloqueado temporariamente.\nMotivo: {motivo}",
                        color=0xE74C3C,
                    )
                )
                bloqueados += 1
            except Exception as ex:
                log.warning(f"[LOCKDOWN] Falha em #{channel.name}: {ex}")
                ignorados += 1

        await self._log(inter.guild, discord.Embed(
            title="Lockdown ativado",
            description=f"Moderador: {inter.user.mention}\nMotivo: {motivo}\nCanais bloqueados: {bloqueados}",
            color=0xE74C3C,
            timestamp=discord.utils.utcnow(),
        ))
        await inter.followup.send(
            embed=embed_success(
                "Lockdown ativado",
                f"{bloqueados} canal(is) bloqueado(s).\n{ignorados} canal(is) ignorado(s) (canais de staff/log).\nMotivo: {motivo}"
            )
        )

    # ── /unlockdown ───────────────────────────────────────────────────────────
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
            color=0x2ECC71,
            timestamp=discord.utils.utcnow(),
        ))
        await inter.followup.send(
            embed=embed_success("Lockdown encerrado", f"{desbloqueados} canal(is) desbloqueado(s).")
        )

    # ── /setlogchannel ────────────────────────────────────────────────────────
    @app_commands.command(name="setlogchannel", description="Define o canal de logs de moderacao")
    @app_commands.describe(canal="Canal de texto para os logs")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, inter: discord.Interaction, canal: discord.TextChannel):
        await Database.guild_set(inter.guild.id, "config", "mod_log_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success("Canal de log definido", f"Logs de moderacao serao enviados em {canal.mention}."),
            ephemeral=True)

    # ── /userinfo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Exibe informacoes detalhadas sobre um membro")
    @app_commands.describe(membro="Membro (deixe vazio para suas proprias informacoes)")
    async def userinfo(self, inter: discord.Interaction, membro: discord.Member = None):
        m = membro or inter.user
        count = await Database.count_warns(inter.guild.id, m.id)
        emb = discord.Embed(title=str(m), color=m.color or 0x5865F2)
        emb.set_thumbnail(url=m.display_avatar.url)
        emb.add_field(name="ID",              value=str(m.id),          inline=True)
        emb.add_field(name="Apelido",         value=m.display_name,     inline=True)
        emb.add_field(name="Conta criada",    value=discord.utils.format_dt(m.created_at, "R"), inline=True)
        emb.add_field(name="Entrou",          value=discord.utils.format_dt(m.joined_at, "R"),  inline=True)
        emb.add_field(name="Bot",             value="Sim" if m.bot else "Nao", inline=True)
        emb.add_field(name="Avisos",          value=str(count),         inline=True)
        roles = [r.mention for r in reversed(m.roles) if r != inter.guild.default_role]
        emb.add_field(name=f"Cargos ({len(roles)})", value=" ".join(roles[:12]) or "Nenhum", inline=False)
        emb.set_footer(text="Filosofia Bot")
        await inter.response.send_message(embed=emb, ephemeral=True)


    # ════════════════════════════════════════════════════════════════════════
    # SEGURANCA AVANCADA
    # ════════════════════════════════════════════════════════════════════════

    # ── Detector de admin malicioso ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detecta quando um membro recebe permissao de administrador."""
        had_admin = before.guild_permissions.administrator
        has_admin = after.guild_permissions.administrator
        if had_admin or not has_admin:
            return
        # Membro acabou de receber admin — registra no log
        await Database.log_security(
            after.guild.id, after.id, "admin_grant",
            f"Membro {after} recebeu permissao de administrador."
        )
        ch_id = await Database.guild_get(after.guild.id, "config", "mod_log_channel")
        if not ch_id:
            return
        ch = after.guild.get_channel(int(ch_id))
        if ch:
            emb = discord.Embed(
                title="Alerta de seguranca — Administrador concedido",
                description=(
                    f"O membro {after.mention} recebeu permissao de **Administrador**.\n"
                    f"Se isso nao foi intencional, revogue o cargo imediatamente."
                ),
                color=0xE74C3C,
                timestamp=discord.utils.utcnow(),
            )
            emb.set_thumbnail(url=after.display_avatar.url)
            await ch.send(embed=emb)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Alerta quando um canal e deletado em massa (possivel raid)."""
        ch_id = await Database.guild_get(channel.guild.id, "config", "mod_log_channel")
        if not ch_id:
            return
        log_ch = channel.guild.get_channel(int(ch_id))
        if log_ch:
            emb = discord.Embed(
                title="Alerta de seguranca — Canal deletado",
                description=f"O canal **#{channel.name}** foi deletado.",
                color=0xF39C12,
                timestamp=discord.utils.utcnow(),
            )
            await log_ch.send(embed=emb)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Alerta quando um cargo com permissoes elevadas e criado."""
        dangerous = discord.Permissions(administrator=True)
        if not role.permissions.is_superset(dangerous):
            return
        ch_id = await Database.guild_get(role.guild.id, "config", "mod_log_channel")
        if not ch_id:
            return
        ch = role.guild.get_channel(int(ch_id))
        if ch:
            emb = discord.Embed(
                title="Alerta de seguranca — Cargo administrativo criado",
                description=f"O cargo **{role.name}** foi criado com permissao de Administrador.",
                color=0xE74C3C,
                timestamp=discord.utils.utcnow(),
            )
            await ch.send(embed=emb)

    # ── /security-log ─────────────────────────────────────────────────────────
    @app_commands.command(name="security-log", description="Exibe os ultimos eventos de seguranca do servidor")
    @app_commands.default_permissions(administrator=True)
    async def security_log(self, inter: discord.Interaction):
        rows = await Database.pool.fetch(
            "SELECT * FROM security_log WHERE guild_id=$1 ORDER BY created_at DESC LIMIT 15",
            inter.guild.id,
        )
        if not rows:
            return await inter.response.send_message(
                embed=embed_info("Sem registros", "Nenhum evento de seguranca registrado."),
                ephemeral=True)
        emb = discord.Embed(title="Log de Seguranca", color=0xE74C3C)
        for r in rows:
            member = inter.guild.get_member(r["user_id"])
            name = str(member) if member else str(r["user_id"])
            ts = r["created_at"].strftime("%d/%m/%Y %H:%M")
            emb.add_field(
                name=f"{r['action']} — {ts}",
                value=f"Usuario: {name}\nDetalhe: {r['detail'] or '—'}",
                inline=False,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /antiraid ─────────────────────────────────────────────────────────────
    @app_commands.command(name="antiraid", description="Expulsa todos os membros que entraram nos ultimos N minutos")
    @app_commands.describe(minutos="Janela de tempo em minutos (1 a 60)")
    @app_commands.default_permissions(administrator=True)
    async def antiraid(self, inter: discord.Interaction, minutos: app_commands.Range[int, 1, 60]):
        await inter.response.defer(ephemeral=True)
        from datetime import datetime, timezone
        cutoff = discord.utils.utcnow() - timedelta(minutes=minutos)
        targets = [
            m for m in inter.guild.members
            if m.joined_at and m.joined_at >= cutoff and not m.bot and m != inter.user
        ]
        if not targets:
            return await inter.followup.send(
                embed=embed_info("Nenhum alvo", f"Nenhum membro entrou nos ultimos {minutos} minuto(s)."),
                ephemeral=True)
        kicked = 0
        for m in targets:
            try:
                await inter.guild.kick(m, reason=f"[AntiRaid] Ativado por {inter.user}")
                await Database.log_security(inter.guild.id, m.id, "antiraid_kick",
                    f"Expulso por antiraid ativado por {inter.user.id}")
                kicked += 1
            except Exception:
                pass
        await self._log(inter.guild, discord.Embed(
            title="AntiRaid ativado",
            description=f"Moderador: {inter.user.mention}\nJanela: {minutos} minuto(s)\nExpulsos: {kicked}",
            color=0xE74C3C,
            timestamp=discord.utils.utcnow(),
        ))
        await inter.followup.send(
            embed=embed_success("AntiRaid concluido", f"{kicked} membro(s) expulso(s)."),
            ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
