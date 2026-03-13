"""
cogs/moderation.py
Sistema de moderação completo: ban, kick, timeout, warn com escalonamento, purge, lock/unlock.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import logging
from utils.helpers import embed_mod, embed_success, embed_error, embed_info, duration_to_seconds, format_duration
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("filosofia.moderation")

# Limites de avisos para ações automáticas
WARN_THRESHOLDS = {
    3: ("timeout", "15m"),
    5: ("timeout", "1h"),
    7: ("kick",    None),
    10: ("ban",    None),
}


class Moderation(commands.Cog):
    """Moderação: ban, kick, timeout, warn, purge, lock/unlock."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage: Storage = bot.storage

    def _log_ch(self, guild: discord.Guild) -> discord.TextChannel | None:
        ch_id = self.storage.guild_get(guild.id, "config", "mod_log_channel")
        return guild.get_channel(int(ch_id)) if ch_id else None

    async def _log(self, guild: discord.Guild, emb: discord.Embed):
        ch = self._log_ch(guild)
        if ch:
            try:
                await ch.send(embed=emb)
            except Exception as ex:
                log.warning(f"[MOD] Log falhou: {ex}")

    async def _dm(self, user: discord.abc.User, action: str, reason: str, guild: discord.Guild):
        try:
            emb = discord.Embed(
                title=f"{E['exclaim']} Ação em **{guild.name}**",
                description=(
                    f"{E['arrow_white']} **Ação:** {action}\n"
                    f"{E['rules']} **Motivo:** {reason or 'Não especificado'}"
                ),
                color=0xED4245,
            )
            await user.send(embed=emb)
        except Exception:
            pass  # DMs fechadas — ignorar silenciosamente

    def _hier_check(self, inter: discord.Interaction, membro: discord.Member) -> str | None:
        """Retorna mensagem de erro se a hierarquia impede a ação."""
        if membro == inter.guild.owner:
            return "Não é possível agir contra o dono do servidor."
        if membro.top_role >= inter.guild.me.top_role:
            return "O cargo do membro é igual ou superior ao meu — não posso agir sobre ele."
        if membro.top_role >= inter.user.top_role and inter.user != inter.guild.owner:
            return "O cargo do membro é igual ou superior ao seu."
        return None

    # ── /ban ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Bane um membro do servidor")
    @app_commands.describe(
        membro="Membro a ser banido",
        motivo="Motivo do banimento",
        delete_days="Dias de mensagens a apagar (0–7, padrão 0)"
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, inter: discord.Interaction, membro: discord.Member,
                  motivo: str = "Sem motivo especificado", delete_days: app_commands.Range[int, 0, 7] = 0):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        await self._dm(membro, f"Banido de **{inter.guild.name}**", motivo, inter.guild)
        await inter.guild.ban(membro, reason=f"[{inter.user}] {motivo}", delete_message_days=delete_days)
        await self._log(inter.guild, embed_mod("Ban", membro, inter.user, motivo))
        await inter.followup.send(
            embed=embed_success("Membro banido", f"{membro.mention} foi banido.\n{E['rules']} **Motivo:** {motivo}"),
            ephemeral=True,
        )

    # ── /unban ────────────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Remove o banimento de um usuário pelo ID")
    @app_commands.describe(user_id="ID do usuário banido", motivo="Motivo do desbanimento")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, inter: discord.Interaction, user_id: str, motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await inter.guild.unban(user, reason=f"[{inter.user}] {motivo}")
            await self._log(inter.guild, embed_mod("Unban", user, inter.user, motivo))
            await inter.followup.send(
                embed=embed_success("Desbanido", f"**{user}** foi desbanido."), ephemeral=True
            )
        except discord.NotFound:
            await inter.followup.send(embed=embed_error("Não encontrado", f"Usuário `{user_id}` não está banido ou não existe."), ephemeral=True)
        except ValueError:
            await inter.followup.send(embed=embed_error("ID inválido", "Informe um ID numérico válido."), ephemeral=True)

    # ── /kick ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Expulsa um membro do servidor")
    @app_commands.describe(membro="Membro a ser expulso", motivo="Motivo")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        if err := self._hier_check(inter, membro):
            return await inter.followup.send(embed=embed_error("Hierarquia insuficiente", err), ephemeral=True)
        await self._dm(membro, f"Expulso de **{inter.guild.name}**", motivo, inter.guild)
        await inter.guild.kick(membro, reason=f"[{inter.user}] {motivo}")
        await self._log(inter.guild, embed_mod("Kick", membro, inter.user, motivo))
        await inter.followup.send(
            embed=embed_success("Membro expulso", f"{membro.mention} foi expulso.\n{E['rules']} **Motivo:** {motivo}"),
            ephemeral=True,
        )

    # ── /timeout ──────────────────────────────────────────────────────────────
    @app_commands.command(name="timeout", description="Silencia um membro temporariamente")
    @app_commands.describe(
        membro="Membro a ser silenciado",
        duracao="Duração: ex. 10m, 2h, 1d (máx. 28d)",
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
                embed=embed_error("Duração inválida", "Use o formato: `10s`, `5m`, `2h`, `1d`. Máximo: 28d."), ephemeral=True
            )
        until = discord.utils.utcnow() + timedelta(seconds=secs)
        await membro.timeout(until, reason=f"[{inter.user}] {motivo}")
        await self._dm(membro, f"Silenciado por {duracao}", motivo, inter.guild)
        await self._log(inter.guild, embed_mod("Timeout", membro, inter.user, motivo, f"Duração: {duracao}"))
        await inter.followup.send(
            embed=embed_success("Membro silenciado", f"{E['muted']} {membro.mention} silenciado por `{duracao}`.\n{E['rules']} **Motivo:** {motivo}"),
            ephemeral=True,
        )

    # ── /untimeout ────────────────────────────────────────────────────────────
    @app_commands.command(name="untimeout", description="Remove o silêncio (timeout) de um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, inter: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo especificado"):
        await inter.response.defer(ephemeral=True)
        await membro.timeout(None, reason=f"[{inter.user}] {motivo}")
        await self._log(inter.guild, embed_mod("Untimeout", membro, inter.user, motivo))
        await inter.followup.send(
            embed=embed_success("Silêncio removido", f"{membro.mention} pode enviar mensagens novamente."),
            ephemeral=True,
        )

    # ── /warn ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Registra um aviso formal para um membro")
    @app_commands.describe(membro="Membro", motivo="Motivo do aviso")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, inter: discord.Interaction, membro: discord.Member, motivo: str):
        await inter.response.defer(ephemeral=True)
        warns = self.storage.guild_get(inter.guild.id, "warns", str(membro.id)) or []
        warns.append({
            "motivo":    motivo,
            "moderador": str(inter.user.id),
            "timestamp": discord.utils.utcnow().isoformat(),
        })
        self.storage.guild_set(inter.guild.id, "warns", str(membro.id), warns)

        count = len(warns)
        await self._dm(membro, f"Aviso #{count}", motivo, inter.guild)
        await self._log(inter.guild, embed_mod("Warn", membro, inter.user, motivo, f"Total de avisos: {count}"))

        # ── Escalonamento automático ─────────────────────────────────────────
        extra = ""
        if count in WARN_THRESHOLDS:
            action, dur = WARN_THRESHOLDS[count]
            try:
                reason_auto = f"[AutoWarn] Limite de {count} avisos atingido"
                if action == "timeout" and dur:
                    secs = duration_to_seconds(dur)
                    until = discord.utils.utcnow() + timedelta(seconds=secs)
                    await membro.timeout(until, reason=reason_auto)
                    extra = f"\n{E['muted']} Silenciado automaticamente por `{dur}` ({count} avisos)."
                elif action == "kick":
                    await inter.guild.kick(membro, reason=reason_auto)
                    extra = f"\n{E['exclaim']} Expulso automaticamente ({count} avisos)."
                elif action == "ban":
                    await inter.guild.ban(membro, reason=reason_auto, delete_message_days=0)
                    extra = f"\n{E['fire_blue']} Banido automaticamente ({count} avisos)."
            except Exception as ex:
                log.warning(f"[MOD] Escalonamento falhou: {ex}")
                extra = f"\n{E['warning']} Escalonamento automático falhou: {ex}"

        await inter.followup.send(
            embed=embed_success(
                f"Aviso #{count} registrado",
                f"{E['warning']} {membro.mention}\n{E['rules']} **Motivo:** {motivo}{extra}"
            ),
            ephemeral=True,
        )

    # ── /warnings ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="Lista os avisos de um membro")
    @app_commands.describe(membro="Membro a verificar")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, inter: discord.Interaction, membro: discord.Member):
        warns = self.storage.guild_get(inter.guild.id, "warns", str(membro.id)) or []
        if not warns:
            return await inter.response.send_message(
                embed=embed_info("Sem avisos", f"{membro.mention} não possui avisos registrados."),
                ephemeral=True,
            )
        emb = discord.Embed(
            title=f"{E['warning']} Avisos de {membro}",
            description=f"Total: **{len(warns)}** aviso(s)",
            color=0xFEE75C,
        )
        for i, w in enumerate(warns[-10:], max(1, len(warns) - 9)):  # últimos 10
            mod_id = w.get("moderador", "?")
            mod = inter.guild.get_member(int(mod_id)) if mod_id.isdigit() else None
            ts = w.get("timestamp", "")[:10]
            emb.add_field(
                name=f"{E['arrow_white']} Aviso #{i}",
                value=(
                    f"{E['rules']} {w['motivo']}\n"
                    f"{E['pin']} {mod.mention if mod else f'`{mod_id}`'}"
                    + (f"\n{E['dash']} {ts}" if ts else "")
                ),
                inline=False,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)

    # ── /clearwarn ────────────────────────────────────────────────────────────
    @app_commands.command(name="clearwarn", description="Remove todos os avisos de um membro")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(administrator=True)
    async def clearwarn(self, inter: discord.Interaction, membro: discord.Member):
        self.storage.guild_set(inter.guild.id, "warns", str(membro.id), [])
        await inter.response.send_message(
            embed=embed_success("Avisos removidos", f"Todos os avisos de {membro.mention} foram removidos."),
            ephemeral=True,
        )

    # ── /purge ────────────────────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Apaga mensagens em massa no canal atual")
    @app_commands.describe(
        quantidade="Número de mensagens a apagar (1–100)",
        membro="Filtrar mensagens de um membro específico (opcional)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, inter: discord.Interaction,
                    quantidade: app_commands.Range[int, 1, 100],
                    membro: discord.Member = None):
        await inter.response.defer(ephemeral=True)
        check = (lambda m: m.author == membro) if membro else None
        deleted = await inter.channel.purge(limit=quantidade, check=check)
        desc = f"`{len(deleted)}` mensagem(ns) apagada(s)"
        if membro:
            desc += f" de {membro.mention}"
        await inter.followup.send(embed=embed_success("Limpeza concluída", desc), ephemeral=True)

    # ── /slowmode ─────────────────────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Define o modo lento do canal atual")
    @app_commands.describe(segundos="Intervalo em segundos (0 para desativar, máx. 21600)")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, inter: discord.Interaction, segundos: app_commands.Range[int, 0, 21600]):
        await inter.channel.edit(slowmode_delay=segundos)
        msg = f"Modo lento definido para `{segundos}s`." if segundos else "Modo lento desativado."
        await inter.response.send_message(embed=embed_success("Modo Lento", msg), ephemeral=True)

    # ── /lock ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Bloqueia o envio de mensagens no canal atual")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, inter: discord.Interaction):
        ow = inter.channel.overwrites_for(inter.guild.default_role)
        ow.send_messages = False
        await inter.channel.set_permissions(inter.guild.default_role, overwrite=ow)
        await inter.response.send_message(
            embed=embed_success("Canal bloqueado", f"{E['deafened']} {inter.channel.mention} foi bloqueado para @everyone.")
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

    # ── /setlogchannel ────────────────────────────────────────────────────────
    @app_commands.command(name="setlogchannel", description="Define o canal de logs de moderação")
    @app_commands.describe(canal="Canal de texto para os logs")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, inter: discord.Interaction, canal: discord.TextChannel):
        self.storage.guild_set(inter.guild.id, "config", "mod_log_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success("Canal de log definido", f"Logs de moderação serão enviados em {canal.mention}."),
            ephemeral=True,
        )

    # ── /userinfo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Exibe informações detalhadas sobre um membro")
    @app_commands.describe(membro="Membro (deixe vazio para ver suas próprias informações)")
    async def userinfo(self, inter: discord.Interaction, membro: discord.Member = None):
        m = membro or inter.user
        warns = self.storage.guild_get(inter.guild.id, "warns", str(m.id)) or []
        emb = discord.Embed(title=f"{E['star']} {m}", color=m.color or 0x5865F2)
        emb.set_thumbnail(url=m.display_avatar.url)
        emb.add_field(name="ID",                                          value=str(m.id),               inline=True)
        emb.add_field(name="Apelido",                                     value=m.display_name,          inline=True)
        emb.add_field(name=f"{E['dash']} Conta criada",                   value=discord.utils.format_dt(m.created_at, "R"), inline=True)
        emb.add_field(name=f"{E['arrow_white']} Entrou no servidor",      value=discord.utils.format_dt(m.joined_at, "R"),  inline=True)
        emb.add_field(name="Bot?",                                        value="Sim" if m.bot else "Não", inline=True)
        emb.add_field(name=f"{E['warning']} Avisos",                      value=str(len(warns)),         inline=True)
        roles = [r.mention for r in reversed(m.roles) if r != inter.guild.default_role]
        emb.add_field(
            name=f"Cargos ({len(roles)})",
            value=" ".join(roles[:12]) or "Nenhum",
            inline=False,
        )
        emb.set_footer(text="Filosofia Bot • /userinfo")
        await inter.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
